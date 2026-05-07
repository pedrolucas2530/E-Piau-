from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from epipiaui_monitor.configuracao import CAMINHO_BANCO_PADRAO
from epipiaui_monitor.modelos import MencaoExtraida, Noticia


ESQUEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS noticias (
    id TEXT PRIMARY KEY,
    fonte TEXT NOT NULL,
    titulo TEXT NOT NULL,
    texto TEXT NOT NULL,
    data_publicacao TEXT,
    url TEXT NOT NULL UNIQUE,
    coletado_em TEXT NOT NULL,
    bruto_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mencoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    noticia_id TEXT NOT NULL,
    doenca TEXT NOT NULL,
    municipio TEXT NOT NULL,
    codigo_municipio TEXT,
    sentenca TEXT NOT NULL,
    sintomas_json TEXT NOT NULL,
    confianca REAL NOT NULL,
    extraido_em TEXT NOT NULL,
    FOREIGN KEY(noticia_id) REFERENCES noticias(id) ON DELETE CASCADE,
    UNIQUE(noticia_id, doenca, municipio, sentenca)
);

CREATE INDEX IF NOT EXISTS idx_noticias_data_publicacao ON noticias(data_publicacao);
CREATE INDEX IF NOT EXISTS idx_mencoes_doenca ON mencoes(doenca);
CREATE INDEX IF NOT EXISTS idx_mencoes_municipio ON mencoes(municipio);
"""


def obter_conexao(caminho_banco: str | Path = CAMINHO_BANCO_PADRAO) -> sqlite3.Connection:
    caminho = Path(caminho_banco)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON;")
    return conexao


def inicializar_banco(caminho_banco: str | Path = CAMINHO_BANCO_PADRAO) -> None:
    with obter_conexao(caminho_banco) as conexao:
        conexao.executescript(ESQUEMA)


def salvar_noticias(
    noticias: Iterable[Noticia],
    caminho_banco: str | Path = CAMINHO_BANCO_PADRAO,
) -> int:
    linhas = [
        (
            noticia.id,
            noticia.fonte,
            noticia.titulo,
            noticia.texto,
            noticia.data_publicacao,
            noticia.url,
            noticia.coletado_em,
            json.dumps(noticia.bruto, ensure_ascii=False),
        )
        for noticia in noticias
    ]
    if not linhas:
        return 0

    with obter_conexao(caminho_banco) as conexao:
        conexao.executemany(
            """
            INSERT INTO noticias (
                id, fonte, titulo, texto, data_publicacao, url, coletado_em, bruto_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                fonte = excluded.fonte,
                titulo = excluded.titulo,
                texto = excluded.texto,
                data_publicacao = excluded.data_publicacao,
                coletado_em = excluded.coletado_em,
                bruto_json = excluded.bruto_json;
            """,
            linhas,
        )
    return len(linhas)


def substituir_mencoes(
    mencoes: Iterable[MencaoExtraida],
    caminho_banco: str | Path = CAMINHO_BANCO_PADRAO,
) -> int:
    linhas = [
        (
            mencao.noticia_id,
            mencao.doenca,
            mencao.municipio,
            mencao.codigo_municipio,
            mencao.sentenca,
            json.dumps(mencao.sintomas, ensure_ascii=False),
            mencao.confianca,
            mencao.extraido_em,
        )
        for mencao in mencoes
    ]

    with obter_conexao(caminho_banco) as conexao:
        if linhas:
            ids_noticias = sorted({linha[0] for linha in linhas})
            marcadores = ",".join("?" for _ in ids_noticias)
            conexao.execute(
                f"DELETE FROM mencoes WHERE noticia_id IN ({marcadores})",
                ids_noticias,
            )
            conexao.executemany(
                """
                INSERT OR IGNORE INTO mencoes (
                    noticia_id, doenca, municipio, codigo_municipio,
                    sentenca, sintomas_json, confianca, extraido_em
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                linhas,
            )
    return len(linhas)


def limpar_mencoes(caminho_banco: str | Path = CAMINHO_BANCO_PADRAO) -> None:
    with obter_conexao(caminho_banco) as conexao:
        conexao.execute("DELETE FROM mencoes;")


def limpar_banco(caminho_banco: str | Path = CAMINHO_BANCO_PADRAO) -> None:
    caminho = Path(caminho_banco)
    for sufixo in ("", "-wal", "-shm"):
        arquivo = Path(f"{caminho}{sufixo}")
        if arquivo.exists():
            arquivo.unlink()


def carregar_registros_noticias(
    caminho_banco: str | Path = CAMINHO_BANCO_PADRAO,
) -> list[dict]:
    with obter_conexao(caminho_banco) as conexao:
        linhas = conexao.execute(
            """
            SELECT id, fonte, titulo, texto, data_publicacao, url, coletado_em
            FROM noticias
            ORDER BY data_publicacao DESC, coletado_em DESC;
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def carregar_noticias(caminho_banco: str | Path = CAMINHO_BANCO_PADRAO) -> pd.DataFrame:
    import pandas as pd

    with obter_conexao(caminho_banco) as conexao:
        return pd.read_sql_query(
            """
            SELECT id, fonte, titulo, texto, data_publicacao, url, coletado_em
            FROM noticias
            ORDER BY data_publicacao DESC, coletado_em DESC;
            """,
            conexao,
        )


def carregar_mencoes(caminho_banco: str | Path = CAMINHO_BANCO_PADRAO) -> pd.DataFrame:
    import pandas as pd

    with obter_conexao(caminho_banco) as conexao:
        quadro = pd.read_sql_query(
            """
            SELECT
                m.id,
                m.noticia_id,
                n.fonte,
                n.titulo,
                n.data_publicacao,
                n.url,
                m.doenca,
                m.municipio,
                m.codigo_municipio,
                m.sentenca,
                m.sintomas_json,
                m.confianca,
                m.extraido_em
            FROM mencoes m
            JOIN noticias n ON n.id = m.noticia_id
            ORDER BY n.data_publicacao DESC, m.confianca DESC;
            """,
            conexao,
        )
    if not quadro.empty:
        quadro["sintomas"] = quadro["sintomas_json"].apply(json.loads)
    return quadro
