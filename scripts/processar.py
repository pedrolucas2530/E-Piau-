from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epipiaui_monitor.banco import (
    carregar_registros_noticias,
    limpar_mencoes,
    substituir_mencoes,
)
from epipiaui_monitor.configuracao import CAMINHO_BANCO_PADRAO
from epipiaui_monitor.modelos import Noticia
from epipiaui_monitor.pln import EpiPiauiPLN


def interpretar_argumentos() -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description="Processa noticias com PLN.")
    analisador.add_argument(
        "--banco",
        dest="caminho_banco",
        default=str(CAMINHO_BANCO_PADRAO),
        help="Caminho do SQLite.",
    )
    return analisador.parse_args()


def registros_para_noticias(registros: list[dict]) -> list[Noticia]:
    noticias: list[Noticia] = []
    for linha in registros:
        noticias.append(
            Noticia(
                id=linha["id"],
                fonte=linha["fonte"],
                titulo=linha["titulo"],
                texto=linha["texto"],
                data_publicacao=linha.get("data_publicacao"),
                url=linha["url"],
                coletado_em=linha["coletado_em"],
                bruto={},
            )
        )
    return noticias


def main() -> None:
    argumentos = interpretar_argumentos()
    caminho_banco = Path(argumentos.caminho_banco)
    registros = carregar_registros_noticias(caminho_banco)
    if not registros:
        print("Nenhuma noticia encontrada. Execute scripts/coletar.py primeiro.")
        return

    processador = EpiPiauiPLN()
    mencoes = processador.processar_noticias(registros_para_noticias(registros))
    limpar_mencoes(caminho_banco)
    salvas = substituir_mencoes(mencoes, caminho_banco=caminho_banco)
    print(f"{salvas} mencoes extraidas e salvas em {caminho_banco}")


if __name__ == "__main__":
    main()
