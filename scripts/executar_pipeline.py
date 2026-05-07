from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


MODOS = {
    "reais": "reais",
    "amostra": "amostra",
    "ao-vivo": "ao-vivo",
    "ambos": "ambos",
}


def interpretar_argumentos() -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description="Executa coleta e processamento do MVP.")
    analisador.add_argument("--modo", dest="modo", choices=tuple(MODOS), default="reais")
    analisador.add_argument(
        "--banco",
        dest="caminho_banco",
        default=str(RAIZ / "dados" / "epipiaui_monitor.sqlite"),
    )
    analisador.add_argument(
        "--manter-existente",
        dest="manter_existente",
        action="store_true",
    )
    return analisador.parse_args()


def executar(comando: list[str]) -> None:
    subprocess.run(comando, cwd=RAIZ, check=True)


def main() -> None:
    argumentos = interpretar_argumentos()
    python = sys.executable
    comando_coleta = [
        python,
        "scripts/coletar.py",
        "--modo",
        MODOS[argumentos.modo],
        "--banco",
        argumentos.caminho_banco,
    ]
    if not argumentos.manter_existente:
        comando_coleta.append("--reiniciar")
    executar(comando_coleta)
    executar([python, "scripts/processar.py", "--banco", argumentos.caminho_banco])


if __name__ == "__main__":
    main()
