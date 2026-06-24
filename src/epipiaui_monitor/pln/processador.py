from __future__ import annotations

import re
from collections.abc import Iterable

try:
    import spacy
    from spacy.language import Language
except ImportError:
    spacy = None
    Language = object

from epipiaui_monitor.dominio import DominioInvestigacao, carregar_dominio
from epipiaui_monitor.modelos import MencaoExtraida, Noticia, agora_utc_iso
from epipiaui_monitor.piaui import carregar_municipios, indice_municipios
from epipiaui_monitor.utilitarios import normalizar_chave, unidecode


class EpiPiauiPLN:
    """Pipeline de PLN em português com regras configuráveis por domínio.

    O domínio define o tema investigado (doenças, crimes, etc.) e seus
    vocabulários. Por padrão carrega o domínio de arboviroses, preservando o
    comportamento histórico do projeto. O município permanece o eixo geográfico
    fixo, correlacionado ao tema por co-ocorrência em sentença.
    """

    def __init__(
        self,
        dominio: DominioInvestigacao | None = None,
        caminho_dominio: str | None = None,
    ) -> None:
        if dominio is not None:
            self.dominio = dominio
        elif caminho_dominio is not None:
            self.dominio = carregar_dominio(caminho_dominio)
        else:
            self.dominio = carregar_dominio()
        self.municipios = carregar_municipios()
        self.municipio_por_chave = indice_municipios(self.municipios)
        self.tema_por_chave = {
            normalizar_chave(apelido): categoria
            for categoria, apelidos in self.dominio.categorias.items()
            for apelido in apelidos
        }
        self.auxiliar_por_chave = {
            normalizar_chave(termo): termo.capitalize()
            for termo in self.dominio.termos_auxiliares
        }
        self.pln = self._carregar_pipeline() if spacy else None
        if self.pln:
            self._instalar_regras_entidades(self.pln)

    def processar_noticias(self, noticias: Iterable[Noticia]) -> list[MencaoExtraida]:
        mencoes: list[MencaoExtraida] = []
        for noticia in noticias:
            mencoes.extend(self.processar_noticia(noticia))
        return mencoes

    def processar_noticia(self, noticia: Noticia) -> list[MencaoExtraida]:
        texto = f"{noticia.titulo}. {noticia.texto}"
        if not self.pln:
            return self._processar_noticia_com_regras(noticia, texto)

        documento = self.pln(texto)
        resultados: list[MencaoExtraida] = []
        vistos: set[tuple[str, str, str]] = set()

        titulo_chave = normalizar_chave(noticia.titulo)
        titulo_tem_termo_tema = any(
            chave_tema in titulo_chave for chave_tema in self.tema_por_chave
        )

        for sentenca in documento.sents:
            texto_sentenca = sentenca.text.strip()
            if not texto_sentenca:
                continue
            temas = self._entidades_canonicas(sentenca, "TEMA", self.tema_por_chave)
            municipios = self._entidades_municipios(sentenca)
            auxiliares = self._entidades_canonicas(
                sentenca, "AUXILIAR", self.auxiliar_por_chave
            )
            if not temas or not municipios:
                continue

            for tema in temas:
                for municipio in municipios:
                    chave = (tema, municipio["nome"], texto_sentenca)
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    resultados.append(
                        MencaoExtraida(
                            noticia_id=noticia.id,
                            doenca=tema,
                            municipio=municipio["nome"],
                            codigo_municipio=municipio["id"],
                            sentenca=texto_sentenca,
                            sintomas=sorted(auxiliares),
                            confianca=self._calcular_confianca(
                                auxiliares=auxiliares,
                                titulo_tem_termo_tema=titulo_tem_termo_tema,
                            ),
                            extraido_em=agora_utc_iso(),
                        )
                    )
        return resultados

    @staticmethod
    def _carregar_pipeline() -> Language:
        if not spacy:
            raise RuntimeError("spaCy não está instalado.")
        for nome_modelo in ("pt_core_news_lg", "pt_core_news_md", "pt_core_news_sm"):
            try:
                return spacy.load(nome_modelo)
            except OSError:
                continue
        pln = spacy.blank("pt")
        pln.add_pipe("sentencizer")
        return pln

    def _instalar_regras_entidades(self, pln: Language) -> None:
        configuracao = {"phrase_matcher_attr": "LOWER", "overwrite_ents": True}
        if "entity_ruler" in pln.pipe_names:
            regras = pln.get_pipe("entity_ruler")
        elif "ner" in pln.pipe_names:
            regras = pln.add_pipe("entity_ruler", before="ner", config=configuracao)
        else:
            regras = pln.add_pipe("entity_ruler", config=configuracao)

        padroes = []
        for categoria, apelidos in self.dominio.categorias.items():
            for apelido in apelidos:
                padroes.append({"label": "TEMA", "pattern": apelido, "id": categoria})
        for termo in self.dominio.termos_auxiliares:
            padroes.append({"label": "AUXILIAR", "pattern": termo, "id": termo})
        for municipio in self.municipios:
            nomes = {municipio["nome"], unidecode(municipio["nome"])}
            for nome in nomes:
                padroes.append(
                    {
                        "label": "MUNICIPIO",
                        "pattern": nome,
                        "id": municipio["id"],
                    }
                )
        regras.add_patterns(padroes)

        if "sentencizer" not in pln.pipe_names and "parser" not in pln.pipe_names:
            pln.add_pipe("sentencizer")

    def _entidades_canonicas(
        self,
        trecho,
        rotulo: str,
        indice: dict[str, str],
    ) -> set[str]:
        valores: set[str] = set()
        for entidade in trecho.ents:
            if entidade.label_ != rotulo:
                continue
            chave = normalizar_chave(entidade.text)
            if chave in indice:
                valores.add(indice[chave])
        return valores

    def _entidades_municipios(self, trecho) -> list[dict[str, str]]:
        valores: dict[str, dict[str, str]] = {}
        for entidade in trecho.ents:
            if entidade.label_ != "MUNICIPIO":
                continue
            municipio = self.municipio_por_chave.get(normalizar_chave(entidade.text))
            if municipio:
                valores[municipio["id"]] = municipio
        return list(valores.values())

    @staticmethod
    def _calcular_confianca(
        auxiliares: set[str],
        titulo_tem_termo_tema: bool,
    ) -> float:
        confianca = 0.62
        if auxiliares:
            confianca += 0.18
        if len(auxiliares) >= 2:
            confianca += 0.08
        if titulo_tem_termo_tema:
            confianca += 0.08
        return min(round(confianca, 2), 0.96)

    def _processar_noticia_com_regras(
        self,
        noticia: Noticia,
        texto: str,
    ) -> list[MencaoExtraida]:
        resultados: list[MencaoExtraida] = []
        vistos: set[tuple[str, str, str]] = set()
        titulo_chave = normalizar_chave(noticia.titulo)
        titulo_tem_termo_tema = any(
            chave_tema in titulo_chave for chave_tema in self.tema_por_chave
        )

        for texto_sentenca in re.split(r"(?<=[.!?])\s+", texto):
            texto_sentenca = texto_sentenca.strip()
            chave_sentenca = normalizar_chave(texto_sentenca)
            if not chave_sentenca:
                continue

            temas = {
                tema
                for chave_tema, tema in self.tema_por_chave.items()
                if chave_tema in chave_sentenca
            }
            auxiliares = {
                auxiliar
                for chave_auxiliar, auxiliar in self.auxiliar_por_chave.items()
                if chave_auxiliar in chave_sentenca
            }
            municipios = [
                municipio
                for chave_municipio, municipio in self.municipio_por_chave.items()
                if chave_municipio in chave_sentenca
            ]
            if not temas or not municipios:
                continue

            for tema in temas:
                for municipio in municipios:
                    chave = (tema, municipio["nome"], texto_sentenca)
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    resultados.append(
                        MencaoExtraida(
                            noticia_id=noticia.id,
                            doenca=tema,
                            municipio=municipio["nome"],
                            codigo_municipio=municipio["id"],
                            sentenca=texto_sentenca,
                            sintomas=sorted(auxiliares),
                            confianca=self._calcular_confianca(
                                auxiliares=auxiliares,
                                titulo_tem_termo_tema=titulo_tem_termo_tema,
                            ),
                            extraido_em=agora_utc_iso(),
                        )
                    )
        return resultados
