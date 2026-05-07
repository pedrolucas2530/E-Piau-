from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epipiaui_monitor.banco import inicializar_banco, limpar_banco, salvar_noticias
from epipiaui_monitor.configuracao import CAMINHO_AMOSTRA_NOTICIAS, CAMINHO_BANCO_PADRAO
from epipiaui_monitor.modelos import Noticia, agora_utc_iso
from epipiaui_monitor.utilitarios import id_estavel


MODOS = {
    "reais": "reais",
    "amostra": "amostra",
    "ao-vivo": "ao-vivo",
    "ambos": "ambos",
}


def interpretar_argumentos() -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        description="Coleta noticias para o EpiPiaui Monitor."
    )
    analisador.add_argument(
        "--banco",
        dest="caminho_banco",
        default=str(CAMINHO_BANCO_PADRAO),
        help="Caminho do SQLite.",
    )
    analisador.add_argument(
        "--modo",
        dest="modo",
        choices=tuple(MODOS),
        default="reais",
        help="Usa noticias reais verificadas, amostra didatica, coleta ao vivo ou ambos.",
    )
    analisador.add_argument(
        "--reiniciar",
        dest="reiniciar",
        action="store_true",
        help="Limpa e recria o banco antes de coletar.",
    )
    analisador.add_argument(
        "--limite-por-fonte",
        dest="limite_por_fonte",
        type=int,
        default=20,
    )
    analisador.add_argument("--data-inicio", dest="data_inicio", default="2024-01-01")
    analisador.add_argument("--data-fim", dest="data_fim", default="2024-12-31")
    return analisador.parse_args()


def interpretar_data_iso(valor: str | None):
    if not valor:
        return None
    return datetime.fromisoformat(valor).date()


def carregar_amostra_noticias(caminho: Path = CAMINHO_AMOSTRA_NOTICIAS) -> list[Noticia]:
    carga = json.loads(caminho.read_text(encoding="utf-8"))
    coletado_em = agora_utc_iso()
    noticias = []
    for item in carga:
        url = item["url"]
        fonte = item["fonte"]
        noticias.append(
            Noticia(
                id=id_estavel(fonte, url),
                fonte=fonte,
                titulo=item["titulo"],
                texto=item["texto"],
                data_publicacao=item.get("data_publicacao"),
                url=url,
                coletado_em=coletado_em,
                bruto=item.get("bruto", {}),
            )
        )
    return noticias


def main() -> None:
    argumentos = interpretar_argumentos()
    caminho_banco = Path(argumentos.caminho_banco)
    if argumentos.reiniciar:
        limpar_banco(caminho_banco)
    inicializar_banco(caminho_banco)

    modo = MODOS[argumentos.modo]
    noticias: list[Noticia] = []
    if modo == "reais":
        from epipiaui_monitor.coletores import ColetorNoticiasSemeadas

        noticias.extend(ColetorNoticiasSemeadas().coletar())

    if modo in ("amostra", "ambos"):
        noticias.extend(carregar_amostra_noticias())

    if modo in ("ao-vivo", "ambos"):
        from epipiaui_monitor.coletores import ColetorNoticias

        coletor = ColetorNoticias()
        noticias_ao_vivo = coletor.coletar(
            limite_por_fonte=argumentos.limite_por_fonte,
            data_inicio=interpretar_data_iso(argumentos.data_inicio),
            data_fim=interpretar_data_iso(argumentos.data_fim),
        )
        if noticias_ao_vivo:
            coletor.salvar_recorte_bruto(noticias_ao_vivo)
        noticias.extend(noticias_ao_vivo)

    salvas = salvar_noticias(noticias, caminho_banco=caminho_banco)
    print(f"{salvas} noticias salvas em {caminho_banco}")


if __name__ == "__main__":
    main()
