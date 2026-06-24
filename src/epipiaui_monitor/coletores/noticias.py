from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

from epipiaui_monitor.coletores.html import interpretar_html
from epipiaui_monitor.configuracao import (
    DIR_DADOS_BRUTOS,
    FONTES_NOTICIAS,
    ConfiguracaoFonte,
)
from epipiaui_monitor.modelos import Noticia, agora_utc_iso
from epipiaui_monitor.utilitarios import (
    dentro_do_periodo,
    id_estavel,
    interpretar_data,
    normalizar_chave,
    normalizar_espacos,
    url_canonica,
)


class ColetorNoticias:
    """Coleta noticias publicas para a prova de conceito do EpiPiaui Monitor."""

    def __init__(
        self,
        fontes: tuple[ConfiguracaoFonte, ...] = FONTES_NOTICIAS,
        tempo_limite: int = 20,
        palavras_chave: tuple[str, ...] | None = None,
    ) -> None:
        self.fontes = fontes
        self.tempo_limite = tempo_limite
        self.palavras_chave = palavras_chave
        self.sessao = requests.Session()
        self.sessao.headers.update(
            {
                "User-Agent": (
                    "EpiPiauiMonitor/0.1 "
                    "(prova de conceito academica; contato: prototipo local)"
                )
            }
        )

    def coletar(
        self,
        limite_por_fonte: int = 20,
        data_inicio: date | None = None,
        data_fim: date | None = None,
    ) -> list[Noticia]:
        coletadas: list[Noticia] = []
        urls_vistas: set[str] = set()

        for fonte in self.fontes:
            urls = self._descobrir_urls(fonte, limite=limite_por_fonte * 3)
            for url in urls:
                if url in urls_vistas:
                    continue
                urls_vistas.add(url)
                noticia = self._extrair_noticia(fonte, url)
                if not noticia:
                    continue
                if not dentro_do_periodo(noticia.data_publicacao, data_inicio, data_fim):
                    continue
                coletadas.append(noticia)
                total_fonte = len([item for item in coletadas if item.fonte == fonte.nome])
                if total_fonte >= limite_por_fonte:
                    break

        return coletadas

    def salvar_recorte_bruto(
        self,
        noticias: list[Noticia],
        diretorio_saida: Path = DIR_DADOS_BRUTOS,
    ) -> Path:
        diretorio_saida.mkdir(parents=True, exist_ok=True)
        caminho = diretorio_saida / f"ao_vivo_{agora_utc_iso().replace(':', '-')}.json"
        carga = [
            {
                "id": item.id,
                "fonte": item.fonte,
                "titulo": item.titulo,
                "texto": item.texto,
                "data_publicacao": item.data_publicacao,
                "url": item.url,
                "coletado_em": item.coletado_em,
                "bruto": item.bruto,
            }
            for item in noticias
        ]
        caminho.write_text(json.dumps(carga, ensure_ascii=False, indent=2), encoding="utf-8")
        return caminho

    def _descobrir_urls(self, fonte: ConfiguracaoFonte, limite: int) -> list[str]:
        urls: list[str] = []
        if fonte.url_rss:
            urls.extend(self._descobrir_por_rss(fonte))
        urls.extend(self._descobrir_por_listagem(fonte))

        sem_duplicatas: list[str] = []
        vistos: set[str] = set()
        for url in urls:
            if url in vistos:
                continue
            vistos.add(url)
            sem_duplicatas.append(url)
            if len(sem_duplicatas) >= limite:
                break
        return sem_duplicatas

    def _descobrir_por_rss(self, fonte: ConfiguracaoFonte) -> list[str]:
        if not fonte.url_rss:
            return []
        try:
            resposta = self.sessao.get(fonte.url_rss, timeout=self.tempo_limite)
            resposta.raise_for_status()
            raiz = ET.fromstring(resposta.content)
        except (requests.RequestException, ET.ParseError):
            return []

        urls: list[str] = []
        for item in raiz.findall(".//item"):
            link = item.findtext("link")
            if link:
                urls.append(url_canonica(link, fonte.url_base))
        for entrada in raiz.findall(".//{http://www.w3.org/2005/Atom}entry"):
            link = entrada.find("{http://www.w3.org/2005/Atom}link")
            href = link.attrib.get("href") if link is not None else None
            if href:
                urls.append(url_canonica(href, fonte.url_base))
        return urls

    def _descobrir_por_listagem(self, fonte: ConfiguracaoFonte) -> list[str]:
        try:
            resposta = self.sessao.get(fonte.url_listagem, timeout=self.tempo_limite)
            resposta.raise_for_status()
        except requests.RequestException:
            return []

        pagina = interpretar_html(resposta.text)
        urls: list[str] = []
        host_fonte = urlparse(fonte.url_base).netloc.replace("www.", "")
        palavras_fonte = self.palavras_chave if self.palavras_chave else fonte.palavras_chave_link
        palavras = tuple(normalizar_chave(palavra) for palavra in palavras_fonte)

        for ancora in pagina.find_all("a", href=True):
            href = url_canonica(ancora.get("href", ""), fonte.url_base)
            host = urlparse(href).netloc.replace("www.", "")
            if host_fonte not in host:
                continue
            texto_link = normalizar_chave(ancora.get_text(" ", strip=True))
            href_chave = normalizar_chave(href)
            if palavras and not any(palavra in texto_link or palavra in href_chave for palavra in palavras):
                continue
            urls.append(href)
        return urls

    def _extrair_noticia(self, fonte: ConfiguracaoFonte, url: str) -> Noticia | None:
        try:
            resposta = self.sessao.get(url, timeout=self.tempo_limite)
            resposta.raise_for_status()
        except requests.RequestException:
            return None

        pagina = interpretar_html(resposta.text)
        titulo = self._extrair_titulo(pagina)
        texto = self._extrair_texto(pagina)
        data_publicacao = self._extrair_data(pagina)
        if not titulo or len(texto) < 120:
            return None

        url_limpa = url_canonica(url)
        return Noticia(
            id=id_estavel(fonte.nome, url_limpa),
            fonte=fonte.nome,
            titulo=titulo,
            texto=texto,
            data_publicacao=data_publicacao,
            url=url_limpa,
            coletado_em=agora_utc_iso(),
            bruto={
                "codigo_status": resposta.status_code,
                "tipo_conteudo": resposta.headers.get("content-type"),
                "tamanho_html": len(resposta.text),
            },
        )

    @staticmethod
    def _extrair_titulo(pagina) -> str:
        candidatos = [
            pagina.find("meta", property="og:title"),
            pagina.find("meta", attrs={"name": "twitter:title"}),
            pagina.find("h1"),
            pagina.find("title"),
        ]
        for candidato in candidatos:
            if not candidato:
                continue
            valor = candidato.get("content") if candidato.name == "meta" else candidato.get_text(" ")
            valor = normalizar_espacos(valor or "")
            if valor:
                return valor
        return ""

    @staticmethod
    def _extrair_data(pagina) -> str | None:
        seletores_meta = [
            ("meta", {"property": "article:published_time"}),
            ("meta", {"name": "pubdate"}),
            ("meta", {"name": "date"}),
            ("meta", {"itemprop": "datePublished"}),
        ]
        for nome_tag, atributos in seletores_meta:
            tag = pagina.find(nome_tag, attrs=atributos)
            valor = tag.get("content") if tag else None
            analisada = interpretar_data(valor)
            if analisada:
                return analisada

        tag_tempo = pagina.find("time")
        if tag_tempo:
            analisada = interpretar_data(tag_tempo.get("datetime") or tag_tempo.get_text(" "))
            if analisada:
                return analisada
        return None

    @staticmethod
    def _extrair_texto(pagina) -> str:
        for tag in pagina(["script", "style", "noscript", "svg", "form"]):
            tag.decompose()

        artigo = pagina.find("article")
        recipiente = artigo or pagina.find("main") or pagina.body or pagina
        paragrafos = [
            normalizar_espacos(paragrafo.get_text(" ", strip=True))
            for paragrafo in recipiente.find_all("p")
        ]
        paragrafos = [item for item in paragrafos if len(item) >= 35]
        if paragrafos:
            return "\n".join(paragrafos)
        return normalizar_espacos(recipiente.get_text(" ", strip=True))
