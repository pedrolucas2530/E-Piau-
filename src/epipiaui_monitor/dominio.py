"""
Domínio de investigação configurável.

O motor de extração (PLN) é genérico: ele correlaciona, por co-ocorrência em
sentença, uma entidade de TEMA com um MUNICÍPIO do Piauí. O que define *qual*
tema é investigado (doenças, crimes, óbitos, etc.) fica neste módulo, carregado
de um arquivo de configuração JSON.

O município permanece como eixo geográfico fixo (ver piaui.py); apenas a
dimensão temática é configurável. Trocar de tema significa apontar para outro
arquivo de domínio — nenhuma alteração de código é necessária.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from epipiaui_monitor.configuracao import CAMINHO_DOMINIO_PADRAO


@dataclass(frozen=True)
class DominioInvestigacao:
    """Define o tema investigado e os rótulos exibidos na interface."""

    nome: str
    rotulo_tema: str
    categorias: dict[str, tuple[str, ...]]
    rotulo_tema_plural: str = "Categorias"
    rotulo_auxiliar: str = "Termos auxiliares"
    termos_auxiliares: tuple[str, ...] = ()
    palavras_chave_coleta: tuple[str, ...] = ()


CATEGORIAS_RESERVA: dict[str, tuple[str, ...]] = {
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

TERMOS_AUXILIARES_RESERVA: tuple[str, ...] = (
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

DOMINIO_RESERVA = DominioInvestigacao(
    nome="Arboviroses no Piauí",
    rotulo_tema="Doença",
    rotulo_tema_plural="Doenças",
    rotulo_auxiliar="Sintomas",
    categorias=CATEGORIAS_RESERVA,
    termos_auxiliares=TERMOS_AUXILIARES_RESERVA,
    palavras_chave_coleta=("dengue", "zika", "chikungunya", "arbovirose", "aedes"),
)


def _de_dados(dados: dict) -> DominioInvestigacao:
    categorias = {
        str(nome): tuple(str(v) for v in variantes)
        for nome, variantes in dados["categorias"].items()
    }
    return DominioInvestigacao(
        nome=str(dados.get("nome", "Domínio personalizado")),
        rotulo_tema=str(dados.get("rotulo_tema", "Categoria")),
        rotulo_tema_plural=str(dados.get("rotulo_tema_plural", "Categorias")),
        rotulo_auxiliar=str(dados.get("rotulo_auxiliar", "Termos auxiliares")),
        categorias=categorias,
        termos_auxiliares=tuple(str(t) for t in dados.get("termos_auxiliares", [])),
        palavras_chave_coleta=tuple(
            str(t) for t in dados.get("palavras_chave_coleta", [])
        ),
    )


def carregar_dominio(
    caminho: str | Path | None = CAMINHO_DOMINIO_PADRAO,
) -> DominioInvestigacao:
    """Carrega um domínio de um JSON; recai no domínio de reserva se falhar."""
    if caminho is None:
        return DOMINIO_RESERVA
    caminho = Path(caminho)
    if not caminho.exists():
        return DOMINIO_RESERVA
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return _de_dados(dados)
    except (ValueError, KeyError, TypeError):
        return DOMINIO_RESERVA


def termos_de_texto(texto: str) -> list[str]:
    """Divide uma string de termos separados por vírgula em uma lista limpa."""
    return [parte.strip() for parte in (texto or "").split(",") if parte.strip()]


def dominio_de_termos(
    termos: Iterable[str],
    rotulo_tema: str = "Termo",
    rotulo_tema_plural: str = "Termos",
) -> DominioInvestigacao:
    """Constrói um domínio ad-hoc a partir de termos digitados (busca livre)."""
    categorias: dict[str, tuple[str, ...]] = {}
    for termo in termos:
        termo = termo.strip()
        if termo:
            categorias.setdefault(termo.capitalize(), (termo,))
    return DominioInvestigacao(
        nome="Busca por termo",
        rotulo_tema=rotulo_tema,
        rotulo_tema_plural=rotulo_tema_plural,
        categorias=categorias,
        termos_auxiliares=(),
        palavras_chave_coleta=tuple(
            variante for variantes in categorias.values() for variante in variantes
        ),
    )
