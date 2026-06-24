"""
Testes do dominio configuravel (tema investigado).

Verificam que o dominio padrao preserva o comportamento de arboviroses e que
trocar o dominio permite investigar outro tema (ex.: criminalidade), mantendo o
municipio como eixo fixo. Inclui a busca por termo ad-hoc (--termo).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epipiaui_monitor.dominio import (
    DOMINIO_RESERVA,
    DominioInvestigacao,
    carregar_dominio,
    dominio_de_termos,
    termos_de_texto,
)
from epipiaui_monitor.modelos import Noticia
from epipiaui_monitor.pln.processador import EpiPiauiPLN


def _noticia(titulo: str, texto: str) -> Noticia:
    return Noticia(
        id="t",
        fonte="t",
        titulo=titulo,
        texto=texto,
        data_publicacao="2024-06-01",
        url="http://x",
        coletado_em="2024-06-01",
    )


class TestCarregarDominio:
    def test_padrao_e_arboviroses(self) -> None:
        dominio = carregar_dominio()
        assert "Dengue" in dominio.categorias
        assert dominio.rotulo_tema == "Doença"

    def test_arquivo_inexistente_cai_na_reserva(self) -> None:
        dominio = carregar_dominio("/caminho/que/nao/existe.json")
        assert dominio is DOMINIO_RESERVA

    def test_carrega_dominio_de_arquivo(self, tmp_path: Path) -> None:
        cfg = tmp_path / "crime.json"
        cfg.write_text(
            json.dumps(
                {
                    "nome": "Criminalidade",
                    "rotulo_tema": "Crime",
                    "categorias": {"Homicidio": ["homicidio", "assassinato"]},
                    "termos_auxiliares": ["arma de fogo"],
                }
            ),
            encoding="utf-8",
        )
        dominio = carregar_dominio(cfg)
        assert dominio.rotulo_tema == "Crime"
        assert "Homicidio" in dominio.categorias


class TestTrocaDeTema:
    def test_dominio_padrao_extrai_dengue(self) -> None:
        pln = EpiPiauiPLN()
        mencoes = pln.processar_noticia(
            _noticia("Dengue em Teresina", "Teresina registrou casos de dengue.")
        )
        assert any(m.doenca == "Dengue" and m.municipio == "Teresina" for m in mencoes)

    def test_dominio_crime_extrai_e_ignora_dengue(self) -> None:
        dominio = DominioInvestigacao(
            nome="Criminalidade",
            rotulo_tema="Crime",
            categorias={"Homicidio": ("homicidio", "assassinato")},
            termos_auxiliares=("arma de fogo",),
        )
        pln = EpiPiauiPLN(dominio=dominio)

        mencoes = pln.processar_noticia(
            _noticia(
                "Violencia em Teresina",
                "A policia registrou um homicidio com arma de fogo em Teresina.",
            )
        )
        chaves = {(m.doenca, m.municipio) for m in mencoes}
        assert ("Homicidio", "Teresina") in chaves

        outras = pln.processar_noticia(_noticia("Saude", "Casos de dengue em Teresina."))
        assert all(m.doenca != "Dengue" for m in outras)


class TestBuscaPorTermo:
    def test_termos_de_texto_divide_e_limpa(self) -> None:
        assert termos_de_texto("enchente, alagamento ,") == ["enchente", "alagamento"]
        assert termos_de_texto("") == []

    def test_cada_termo_vira_uma_categoria(self) -> None:
        dominio = dominio_de_termos(["enchente", "alagamento"])
        assert set(dominio.categorias) == {"Enchente", "Alagamento"}
        assert dominio.rotulo_tema == "Termo"

    def test_extrai_termo_livre_por_municipio(self) -> None:
        pln = EpiPiauiPLN(dominio=dominio_de_termos(["enchente"]))
        mencoes = pln.processar_noticia(
            _noticia("Chuvas", "Uma forte enchente atingiu Teresina nesta semana.")
        )
        assert any(m.doenca == "Enchente" and m.municipio == "Teresina" for m in mencoes)
