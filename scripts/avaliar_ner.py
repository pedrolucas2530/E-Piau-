"""
scripts/avaliar_ner.py
======================
Avaliação do pipeline de NER do EpiPiaui Monitor contra o Gold Standard.

Calcula Precisão, Recall e F1-Score por tipo de doença e agregado.

Uso:
    python scripts/avaliar_ner.py

Saída:
    Tabela de métricas em texto + arquivo dados/gold_standard/resultado_avaliacao.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ── Ajuste de PYTHONPATH para execução direta ────────────────────────────────
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from epipiaui_monitor.pln.processador import EpiPiauiPLN
from epipiaui_monitor.modelos import Noticia
from epipiaui_monitor.utilitarios import id_estavel, normalizar_chave

# ── Caminhos ─────────────────────────────────────────────────────────────────
CAMINHO_SEMENTES = RAIZ / "dados" / "brutos" / "sementes_noticias_reais_2024.json"
CAMINHO_GS = RAIZ / "dados" / "gold_standard" / "gold_standard.json"
CAMINHO_RESULTADO = RAIZ / "dados" / "gold_standard" / "resultado_avaliacao.json"


def _chave_mencao(doenca: str, municipio: str) -> tuple[str, str]:
    return (normalizar_chave(doenca), normalizar_chave(municipio))


# ── Carregar corpus ───────────────────────────────────────────────────────────
def carregar_corpus() -> list[Noticia]:
    carga = json.loads(CAMINHO_SEMENTES.read_text(encoding="utf-8"))
    noticias = []
    for s in carga:
        noticias.append(
            Noticia(
                id=id_estavel(s["fonte"], s["url"]),
                fonte=s["fonte"],
                titulo=s["titulo"],
                texto=s["texto_reserva"],
                data_publicacao=s.get("data_publicacao"),
                url=s["url"],
                coletado_em="2026-06-15T00:00:00Z",
                bruto={},
            )
        )
    return noticias


# ── Carregar gold standard ────────────────────────────────────────────────────
def carregar_gold_standard() -> dict[str, set[tuple[str, str]]]:
    """Retorna {noticia_id: {(doenca_norm, municipio_norm), ...}}"""
    gs_data = json.loads(CAMINHO_GS.read_text(encoding="utf-8"))
    gs: dict[str, set[tuple[str, str]]] = {}
    for anotacao in gs_data["anotacoes"]:
        nid = anotacao["noticia_id"]
        gs[nid] = {
            _chave_mencao(m["doenca"], m["municipio"])
            for m in anotacao["mencoes_corretas"]
        }
    return gs


# ── Coletar saída do pipeline ─────────────────────────────────────────────────
def coletar_saida_pipeline(
    pln: EpiPiauiPLN, noticias: list[Noticia]
) -> dict[str, set[tuple[str, str]]]:
    """Retorna {noticia_id: {(doenca_norm, municipio_norm), ...}} — sem duplicatas."""
    saida: dict[str, set[tuple[str, str]]] = {}
    for noticia in noticias:
        mencoes = pln.processar_noticia(noticia)
        saida[noticia.id] = {
            _chave_mencao(m.doenca, m.municipio) for m in mencoes
        }
    return saida


# ── Métricas ──────────────────────────────────────────────────────────────────
def calcular_metricas(
    sistema: dict[str, set[tuple[str, str]]],
    gold: dict[str, set[tuple[str, str]]],
    doenca_filtro: str | None = None,
) -> dict:
    """
    Calcula TP, FP, FN, Precisão, Recall e F1.
    doenca_filtro (opcional): string normalizada, ex: 'dengue'.
    """
    tp = fp = fn = 0
    todos_ids = set(sistema) | set(gold)
    detalhes: list[dict] = []

    for nid in sorted(todos_ids):
        sist = sistema.get(nid, set())
        gs = gold.get(nid, set())

        if doenca_filtro:
            sist = {m for m in sist if m[0] == doenca_filtro}
            gs = {m for m in gs if m[0] == doenca_filtro}

        tp_art = len(sist & gs)
        fp_art = len(sist - gs)
        fn_art = len(gs - sist)

        tp += tp_art
        fp += fp_art
        fn += fn_art

        if tp_art or fp_art or fn_art:
            detalhes.append(
                {
                    "noticia_id": nid,
                    "tp": tp_art,
                    "fp": fp_art,
                    "fn": fn_art,
                    "falsos_positivos": sorted(sist - gs),
                    "falsos_negativos": sorted(gs - sist),
                }
            )

    precisao = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precisao * recall / (precisao + recall)
        if (precisao + recall) > 0
        else 0.0
    )

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precisao": round(precisao, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "detalhes_por_noticia": detalhes,
    }


# ── Relatório em texto ────────────────────────────────────────────────────────
def imprimir_relatorio(resultados: dict) -> None:
    linha = "─" * 62
    print(linha)
    print("  AVALIAÇÃO DO PIPELINE NER — EpiPiaui Monitor 2024")
    print(f"  Corpus: {resultados['total_noticias']} artigos | "
          f"Gold Standard: {resultados['total_gs']} menções")
    print(linha)

    cabecalho = f"{'Tipo':<18} {'TP':>5} {'FP':>5} {'FN':>5}   {'P':>7} {'R':>7} {'F1':>7}"
    print(cabecalho)
    print("─" * 62)

    for cat, m in resultados["por_categoria"].items():
        nome = cat.capitalize()
        print(
            f"{nome:<18} {m['tp']:>5} {m['fp']:>5} {m['fn']:>5}   "
            f"{m['precisao']:>7.1%} {m['recall']:>7.1%} {m['f1']:>7.1%}"
        )

    print("─" * 62)
    m = resultados["geral"]
    print(
        f"{'GERAL':<18} {m['tp']:>5} {m['fp']:>5} {m['fn']:>5}   "
        f"{m['precisao']:>7.1%} {m['recall']:>7.1%} {m['f1']:>7.1%}"
    )
    print(linha)

    print("\n  FALSOS POSITIVOS (sistema extraiu; gold standard: incorreto)")
    for det in resultados["geral"]["detalhes_por_noticia"]:
        for fp_item in det["falsos_positivos"]:
            doenca = fp_item[0].capitalize()
            mun = fp_item[1].title()
            print(f"    [{det['noticia_id'][:8]}] {doenca:<14} × {mun}")

    print(f"\n  FALSOS NEGATIVOS: {resultados['geral']['fn']} pares "
          f"não extraídos pelo pipeline.")
    print("  Causa principal: doença e município em sentenças distintas")
    print("  (heurística de co-ocorrência sentencial).")
    print(linha)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("Carregando corpus...", end=" ", flush=True)
    noticias = carregar_corpus()
    print(f"{len(noticias)} artigos.")

    print("Carregando gold standard...", end=" ", flush=True)
    gold = carregar_gold_standard()
    total_gs = sum(len(v) for v in gold.values())
    print(f"{total_gs} menções anotadas.")

    print("Inicializando pipeline de PLN...", end=" ", flush=True)
    pln = EpiPiauiPLN()
    print("OK.")

    print("Executando pipeline...", end=" ", flush=True)
    sistema = coletar_saida_pipeline(pln, noticias)
    total_sist = sum(len(v) for v in sistema.values())
    print(f"{total_sist} pares extraídos (deduplicados por artigo).")

    # Métricas por categoria
    doencas = ["dengue", "chikungunya", "zika"]
    por_categoria = {}
    for doenca in doencas:
        m = calcular_metricas(sistema, gold, doenca_filtro=doenca)
        if m["tp"] + m["fp"] + m["fn"] > 0:
            por_categoria[doenca] = m

    geral = calcular_metricas(sistema, gold)

    resultados = {
        "total_noticias": len(noticias),
        "total_gs": total_gs,
        "total_sistema": total_sist,
        "geral": geral,
        "por_categoria": por_categoria,
    }

    imprimir_relatorio(resultados)

    # Salvar resultado JSON
    CAMINHO_RESULTADO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RESULTADO.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2, default=list),
        encoding="utf-8",
    )
    print(f"\n  Resultado salvo em: {CAMINHO_RESULTADO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
