from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from epipiaui_monitor.coletores.html import interpretar_html
from epipiaui_monitor.configuracao import CAMINHO_SEMENTES_REAIS
from epipiaui_monitor.modelos import Noticia, agora_utc_iso
from epipiaui_monitor.utilitarios import (
    id_estavel,
    interpretar_data,
    normalizar_espacos,
    url_canonica,
)


class ColetorNoticiasSemeadas:
    """Carrega URLs reais verificadas e baixa o HTML original quando possivel."""

    def __init__(self, tempo_limite: int = 25) -> None:
        self.tempo_limite = tempo_limite
        self.sessao = requests.Session()
        self.sessao.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 EpiPiauiMonitor/0.1 "
                    "(prova de conceito academica)"
                )
            }
        )

    def coletar(self, caminho_sementes: Path = CAMINHO_SEMENTES_REAIS) -> list[Noticia]:
        carga = json.loads(caminho_sementes.read_text(encoding="utf-8"))
        noticias: list[Noticia] = []
        for semente in carga:
            noticias.append(self._baixar_semente(semente))
        return noticias

    def _baixar_semente(self, semente: dict[str, Any]) -> Noticia:
        url = url_canonica(semente["url"])
        fonte = semente["fonte"]
        titulo_semente = semente["titulo"]
        data_semente = semente.get("data_publicacao")
        texto_reserva = semente["texto_reserva"]
        baixar = semente.get("baixar", True)
        bruto: dict[str, Any] = {
            "semente": semente,
            "reserva_usada": False,
        }

        if baixar and not url.lower().endswith(".pdf"):
            try:
                resposta = self.sessao.get(url, timeout=self.tempo_limite)
                bruto.update(
                    {
                        "codigo_status": resposta.status_code,
                        "tipo_conteudo": resposta.headers.get("content-type"),
                        "tamanho_html": len(resposta.text),
                    }
                )
                if resposta.ok and "text/html" in resposta.headers.get("content-type", ""):
                    titulo, texto, data_publicacao = self._extrair_pagina(resposta.text)
                    if titulo and len(texto) >= 120:
                        return Noticia(
                            id=id_estavel(fonte, url),
                            fonte=fonte,
                            titulo=titulo,
                            texto=texto,
                            data_publicacao=data_publicacao or data_semente,
                            url=url,
                            coletado_em=agora_utc_iso(),
                            bruto=bruto,
                        )
            except requests.RequestException as erro:
                bruto["erro_baixar"] = str(erro)

        bruto["reserva_usada"] = True
        return Noticia(
            id=id_estavel(fonte, url),
            fonte=fonte,
            titulo=titulo_semente,
            texto=texto_reserva,
            data_publicacao=data_semente,
            url=url,
            coletado_em=agora_utc_iso(),
            bruto=bruto,
        )

    @staticmethod
    def _extrair_pagina(html: str) -> tuple[str, str, str | None]:
        pagina = interpretar_html(html)
        titulo = ""
        for candidato in (
            pagina.find("meta", property="og:title"),
            pagina.find("h1"),
            pagina.find("title"),
        ):
            if not candidato:
                continue
            titulo = normalizar_espacos(
                candidato.get("content") if candidato.name == "meta" else candidato.get_text(" ")
            )
            if titulo:
                titulo = titulo.replace(" | G1", "").strip()
                break

        data_publicacao = None
        for candidato in pagina.find_all(["time", "span", "li", "p"]):
            texto = normalizar_espacos(candidato.get_text(" "))
            if "2024" not in texto:
                continue
            if "Publicado em" in texto or "Atualizado" in texto or "/" in texto:
                data_publicacao = interpretar_data(texto)
                if data_publicacao:
                    break

        paragrafos = []
        for recipiente in (pagina.find("article"), pagina.find("main"), pagina.body, pagina):
            if not recipiente:
                continue
            candidatos = [
                normalizar_espacos(paragrafo.get_text(" ", strip=True))
                for paragrafo in recipiente.find_all("p")
            ]
            candidatos = [
                paragrafo
                for paragrafo in candidatos
                if len(paragrafo) >= 40
                and "Compartilhe esta notícia" not in paragrafo
                and "Veja também" not in paragrafo
            ]
            if candidatos:
                paragrafos = candidatos
                break
        texto = "\n".join(dict.fromkeys(paragrafos))
        return titulo, texto, data_publicacao
