from __future__ import annotations

import re
from collections.abc import Iterable

try:
    import spacy
    from spacy.language import Language
except ImportError:
    spacy = None
    Language = object

from epipiaui_monitor.modelos import MencaoExtraida, Noticia, agora_utc_iso
from epipiaui_monitor.piaui import carregar_municipios, indice_municipios
from epipiaui_monitor.utilitarios import normalizar_chave, unidecode


PADROES_DOENCAS: dict[str, tuple[str, ...]] = {
    "Dengue": (
        "dengue",
        "dengue grave",
        "dengue com sinais de alarme",
        "arbovirose dengue",
    ),
    "Zika": (
        "zika",
        "virus zika",
        "vírus zika",
        "zika virus",
        "febre do zika",
    ),
    "Chikungunya": (
        "chikungunya",
        "febre chikungunya",
        "chikungunha",
        "chikungunya virus",
    ),
}

PADROES_SINTOMAS: tuple[str, ...] = (
    "febre",
    "febre alta",
    "febre baixa",
    "dor de cabeca",
    "dor de cabeça",
    "dor no corpo",
    "dor atras dos olhos",
    "dor atrás dos olhos",
    "dores articulares",
    "dor articular",
    "manchas vermelhas",
    "exantema",
    "nausea",
    "náusea",
    "vomito",
    "vômito",
    "coceira",
    "mal-estar",
)


class EpiPiauiPLN:
    """Pipeline de PLN em português com regras epidemiológicas customizadas."""

    def __init__(self) -> None:
        self.municipios = carregar_municipios()
        self.municipio_por_chave = indice_municipios(self.municipios)
        self.doenca_por_chave = {
            normalizar_chave(apelido): doenca
            for doenca, apelidos in PADROES_DOENCAS.items()
            for apelido in apelidos
        }
        self.sintoma_por_chave = {
            normalizar_chave(sintoma): sintoma.capitalize()
            for sintoma in PADROES_SINTOMAS
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
        titulo_tem_termo_epidemiologico = any(
            chave_doenca in titulo_chave for chave_doenca in self.doenca_por_chave
        )

        for sentenca in documento.sents:
            texto_sentenca = sentenca.text.strip()
            if not texto_sentenca:
                continue
            doencas = self._entidades_canonicas(sentenca, "DOENCA", self.doenca_por_chave)
            municipios = self._entidades_municipios(sentenca)
            sintomas = self._entidades_canonicas(sentenca, "SINTOMA", self.sintoma_por_chave)
            if not doencas or not municipios:
                continue

            for doenca in doencas:
                for municipio in municipios:
                    chave = (doenca, municipio["nome"], texto_sentenca)
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    resultados.append(
                        MencaoExtraida(
                            noticia_id=noticia.id,
                            doenca=doenca,
                            municipio=municipio["nome"],
                            codigo_municipio=municipio["id"],
                            sentenca=texto_sentenca,
                            sintomas=sorted(sintomas),
                            confianca=self._calcular_confianca(
                                sintomas=sintomas,
                                titulo_tem_termo_epidemiologico=titulo_tem_termo_epidemiologico,
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
        for doenca, apelidos in PADROES_DOENCAS.items():
            for apelido in apelidos:
                padroes.append({"label": "DOENCA", "pattern": apelido, "id": doenca})
        for sintoma in PADROES_SINTOMAS:
            padroes.append({"label": "SINTOMA", "pattern": sintoma, "id": sintoma})
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
        sintomas: set[str],
        titulo_tem_termo_epidemiologico: bool,
    ) -> float:
        confianca = 0.62
        if sintomas:
            confianca += 0.18
        if len(sintomas) >= 2:
            confianca += 0.08
        if titulo_tem_termo_epidemiologico:
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
        titulo_tem_termo_epidemiologico = any(
            chave_doenca in titulo_chave for chave_doenca in self.doenca_por_chave
        )

        for texto_sentenca in re.split(r"(?<=[.!?])\s+", texto):
            texto_sentenca = texto_sentenca.strip()
            chave_sentenca = normalizar_chave(texto_sentenca)
            if not chave_sentenca:
                continue

            doencas = {
                doenca
                for chave_doenca, doenca in self.doenca_por_chave.items()
                if chave_doenca in chave_sentenca
            }
            sintomas = {
                sintoma
                for chave_sintoma, sintoma in self.sintoma_por_chave.items()
                if chave_sintoma in chave_sentenca
            }
            municipios = [
                municipio
                for chave_municipio, municipio in self.municipio_por_chave.items()
                if chave_municipio in chave_sentenca
            ]
            if not doencas or not municipios:
                continue

            for doenca in doencas:
                for municipio in municipios:
                    chave = (doenca, municipio["nome"], texto_sentenca)
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    resultados.append(
                        MencaoExtraida(
                            noticia_id=noticia.id,
                            doenca=doenca,
                            municipio=municipio["nome"],
                            codigo_municipio=municipio["id"],
                            sentenca=texto_sentenca,
                            sintomas=sorted(sintomas),
                            confianca=self._calcular_confianca(
                                sintomas=sintomas,
                                titulo_tem_termo_epidemiologico=titulo_tem_termo_epidemiologico,
                            ),
                            extraido_em=agora_utc_iso(),
                        )
                    )
        return resultados
