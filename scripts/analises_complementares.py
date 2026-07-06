"""
scripts/analises_complementares.py
==================================
Análises complementares de rigor sobre a avaliação do NER do EpiPiaui Monitor,
respondendo a pontos levantados em revisão de banca. Reutiliza o mesmo corpus e
o mesmo Padrão-Ouro de ``scripts/avaliar_ner.py``.

Produz três análises:

  (d) Validade discriminativa do escore de confiança:
      compara o escore médio dos verdadeiros positivos (VP) ao dos falsos
      positivos (FP). Se os grupos não se separam, o escore não distingue
      acerto de erro no corpus.

  (c) Trade-off da janela de associação:
      reprocessa o corpus com janela de documento (artigo inteiro) e reporta
      precisão/revocação/F1, para comparar empiricamente com a janela de
      sentença (padrão do sistema), em vez de apenas especular.

  (IC) Intervalos de confiança (bootstrap por artigo):
      estima IC de 95% para precisão, revocação e F1 por reamostragem dos
      artigos, dada a incerteza do tamanho amostral pequeno.

Uso:
    python scripts/analises_complementares.py

Observações:
  - Usa o mesmo pipeline de PLN do projeto (EpiPiauiPLN), portanto os números
    dependem do modelo spaCy instalado (pt_core_news_lg no ambiente de
    referência). Pequenas variações de versão do spaCy podem alterar contagens
    marginais.
  - É um script de leitura: não grava nada e não altera o banco nem os dados.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from epipiaui_monitor.pln.processador import EpiPiauiPLN
from epipiaui_monitor.modelos import Noticia
from epipiaui_monitor.utilitarios import id_estavel, normalizar_chave

CAMINHO_SEMENTES = RAIZ / "dados" / "brutos" / "sementes_noticias_reais_2024.json"
CAMINHO_GS = RAIZ / "dados" / "gold_standard" / "gold_standard.json"

N_BOOTSTRAP = 10_000
SEMENTE_ALEATORIA = 42


def _chave(doenca: str, municipio: str) -> tuple[str, str]:
    return (normalizar_chave(doenca), normalizar_chave(municipio))


def carregar_corpus() -> list[Noticia]:
    carga = json.loads(CAMINHO_SEMENTES.read_text(encoding="utf-8"))
    return [
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
        for s in carga
    ]


def carregar_gold() -> dict[str, set[tuple[str, str]]]:
    gs_data = json.loads(CAMINHO_GS.read_text(encoding="utf-8"))
    return {
        a["noticia_id"]: {
            _chave(m["doenca"], m["municipio"]) for m in a["mencoes_corretas"]
        }
        for a in gs_data["anotacoes"]
    }


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def metricas(sistema: dict[str, set], gold: dict[str, set]) -> tuple[int, int, int]:
    tp = fp = fn = 0
    for nid in set(sistema) | set(gold):
        s = sistema.get(nid, set())
        g = gold.get(nid, set())
        tp += len(s & g)
        fp += len(s - g)
        fn += len(g - s)
    return tp, fp, fn


def confusao_por_artigo(
    sistema: dict[str, set], gold: dict[str, set]
) -> list[tuple[int, int, int]]:
    unidades = []
    for nid in set(sistema) | set(gold):
        s = sistema.get(nid, set())
        g = gold.get(nid, set())
        unidades.append((len(s & g), len(s - g), len(g - s)))
    return unidades


def bootstrap_ic(
    unidades: list[tuple[int, int, int]], b: int = N_BOOTSTRAP, seed: int = SEMENTE_ALEATORIA
) -> dict[str, tuple[float, float]]:
    rng = random.Random(seed)
    ps, rs, fs = [], [], []
    n = len(unidades)
    for _ in range(b):
        amostra = [rng.choice(unidades) for _ in range(n)]
        tp = sum(u[0] for u in amostra)
        fp = sum(u[1] for u in amostra)
        fn = sum(u[2] for u in amostra)
        p, r, f = prf(tp, fp, fn)
        ps.append(p)
        rs.append(r)
        fs.append(f)

    def ic(valores: list[float]) -> tuple[float, float]:
        valores = sorted(valores)
        return valores[int(0.025 * len(valores))], valores[int(0.975 * len(valores))]

    return {"precisao": ic(ps), "revocacao": ic(rs), "f1": ic(fs)}


def main() -> None:
    noticias = carregar_corpus()
    gold = carregar_gold()
    pln = EpiPiauiPLN()

    # Baseline (janela de sentença) + escore por par
    sist_sentenca: dict[str, set] = {}
    conf_por_par: dict[str, dict[tuple[str, str], float]] = {}
    for n in noticias:
        pares: set[tuple[str, str]] = set()
        cpar: dict[tuple[str, str], float] = {}
        for m in pln.processar_noticia(n):
            p = _chave(m.doenca, m.municipio)
            pares.add(p)
            cpar[p] = max(cpar.get(p, 0.0), m.confianca)
        sist_sentenca[n.id] = pares
        conf_por_par[n.id] = cpar

    tp, fp, fn = metricas(sist_sentenca, gold)
    p, r, f = prf(tp, fp, fn)
    print("=" * 66)
    print("BASELINE — janela de sentença (padrão do sistema)")
    print(f"  VP={tp}  FP={fp}  FN={fn}  |  P={p:.1%}  R={r:.1%}  F1={f:.1%}")

    # (d) Escore de confiança: VP vs FP
    vp, fp_sc = [], []
    for nid, pares in sist_sentenca.items():
        g = gold.get(nid, set())
        for par in pares:
            (vp if par in g else fp_sc).append(conf_por_par[nid][par])
    print("\n(d) VALIDADE DISCRIMINATIVA DO ESCORE DE CONFIANÇA")
    if vp:
        print(f"  VP: n={len(vp)}  média={statistics.mean(vp):.4f}  "
              f"dist={dict(sorted(Counter(round(x, 2) for x in vp).items()))}")
    if fp_sc:
        print(f"  FP: n={len(fp_sc)}  média={statistics.mean(fp_sc):.4f}  "
              f"dist={dict(sorted(Counter(round(x, 2) for x in fp_sc).items()))}")
    print("  Interpretação: se as médias/distribuições coincidem, o escore não "
          "discrimina acerto de erro.")

    # (c) Janela de documento (artigo inteiro)
    sist_doc: dict[str, set] = {}
    for n in noticias:
        doc = pln.pln(f"{n.titulo}. {n.texto}")
        temas = pln._entidades_canonicas(doc, "TEMA", pln.tema_por_chave)
        muns = pln._entidades_municipios(doc)
        sist_doc[n.id] = {_chave(t, mu["nome"]) for t in temas for mu in muns}
    tp2, fp2, fn2 = metricas(sist_doc, gold)
    p2, r2, f2 = prf(tp2, fp2, fn2)
    print("\n(c) TRADE-OFF DA JANELA DE ASSOCIAÇÃO")
    print(f"  Sentença : P={p:.1%}  R={r:.1%}  F1={f:.1%}")
    print(f"  Documento: P={p2:.1%}  R={r2:.1%}  F1={f2:.1%}  "
          f"(VP={tp2} FP={fp2} FN={fn2})")

    # (IC) Bootstrap por artigo
    ic = bootstrap_ic(confusao_por_artigo(sist_sentenca, gold))
    print(f"\n(IC) INTERVALOS DE CONFIANÇA 95% — bootstrap por artigo "
          f"({N_BOOTSTRAP} reamostras)")
    print(f"  Precisão : {p:.1%}  IC[{ic['precisao'][0]:.1%} ; {ic['precisao'][1]:.1%}]")
    print(f"  Revocação: {r:.1%}  IC[{ic['revocacao'][0]:.1%} ; {ic['revocacao'][1]:.1%}]")
    print(f"  F1       : {f:.1%}  IC[{ic['f1'][0]:.1%} ; {ic['f1'][1]:.1%}]")
    print("=" * 66)


if __name__ == "__main__":
    main()
