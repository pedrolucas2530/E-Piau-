"""
Testes unitários para o módulo banco.py do EpiPiaui Monitor.

Cobre: inicialização do esquema, inserção/upsert de notícias,
substituição de menções, leitura via dict e DataFrame, e limpeza.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epipiaui_monitor.banco import (
    inicializar_banco,
    salvar_noticias,
    substituir_mencoes,
    carregar_registros_noticias,
    carregar_noticias,
    carregar_mencoes,
    limpar_mencoes,
    limpar_banco,
    obter_conexao,
)
from epipiaui_monitor.modelos import MencaoExtraida, Noticia


# Fixtures

@pytest.fixture
def banco(tmp_path: Path) -> Path:
    caminho = tmp_path / "teste.sqlite"
    inicializar_banco(caminho)
    return caminho


def _noticia(sufixo: str = "001", url: str | None = None) -> Noticia:
    return Noticia(
        id=f"id_{sufixo}",
        fonte="Teste",
        titulo=f"Dengue em Teresina noticia {sufixo}",
        texto="Teresina registrou aumento de casos de dengue em 2024.",
        data_publicacao="2024-03-15",
        url=url or f"https://exemplo.com/noticia/{sufixo}",
        coletado_em="2024-03-15T12:00:00Z",
        bruto={"origem": "teste"},
    )


def _mencao(noticia_id: str = "id_001", municipio: str = "Teresina") -> MencaoExtraida:
    return MencaoExtraida(
        noticia_id=noticia_id,
        doenca="Dengue",
        municipio=municipio,
        codigo_municipio="2211001",
        sentenca="Teresina registrou aumento de casos de dengue.",
        sintomas=["Febre alta"],
        confianca=0.7,
        extraido_em="2024-03-15T12:00:00Z",
    )


class TestInicializarBanco:
    def test_cria_arquivo(self, tmp_path: Path) -> None:
        caminho = tmp_path / "novo.sqlite"
        assert not caminho.exists()
        inicializar_banco(caminho)
        assert caminho.exists()

    def test_cria_tabelas(self, banco: Path) -> None:
        with obter_conexao(banco) as conn:
            tabelas = {
                linha[0]
                for linha in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "noticias" in tabelas
        assert "mencoes" in tabelas

    def test_idempotente(self, banco: Path) -> None:
        inicializar_banco(banco)
        with obter_conexao(banco) as conn:
            qtd = conn.execute("SELECT COUNT(*) FROM noticias").fetchone()[0]
        assert qtd == 0


class TestSalvarNoticias:
    def test_insere_e_retorna_contagem(self, banco: Path) -> None:
        qtd = salvar_noticias([_noticia("001"), _noticia("002")], banco)
        assert qtd == 2

    def test_dados_gravados_corretamente(self, banco: Path) -> None:
        salvar_noticias([_noticia("001")], banco)
        registros = carregar_registros_noticias(banco)
        assert len(registros) == 1
        assert "Dengue" in registros[0]["titulo"]
        assert registros[0]["fonte"] == "Teste"
        assert registros[0]["data_publicacao"] == "2024-03-15"

    def test_upsert_por_url(self, banco: Path) -> None:
        noticia_v1 = _noticia("001")
        salvar_noticias([noticia_v1], banco)
        noticia_v2 = Noticia(
            id="id_001_v2",
            fonte="Teste",
            titulo="Titulo atualizado",
            texto="Texto atualizado.",
            data_publicacao="2024-03-20",
            url=noticia_v1.url,
            coletado_em="2024-03-20T12:00:00Z",
            bruto={},
        )
        salvar_noticias([noticia_v2], banco)
        registros = carregar_registros_noticias(banco)
        assert len(registros) == 1
        assert registros[0]["titulo"] == "Titulo atualizado"

    def test_lista_vazia_retorna_zero(self, banco: Path) -> None:
        assert salvar_noticias([], banco) == 0

    def test_bruto_serializado_como_json(self, banco: Path) -> None:
        import subprocess
        script = (
            "import sys, json; sys.path.insert(0, 'src');"
            "from epipiaui_monitor.banco import inicializar_banco, salvar_noticias, obter_conexao;"
            "from epipiaui_monitor.modelos import Noticia;"
            "from pathlib import Path;"
            f"banco = Path(r'{banco}');"
            "n = Noticia(id='id_bruto', fonte='T', titulo='T', texto='T',"
            "  data_publicacao=None, url='http://x/bruto', coletado_em='z',"
            "  bruto={'chave': 'valor', 'numero': 42});"
            "salvar_noticias([n], banco);"
            "conn = obter_conexao(banco);"
            "raw = conn.execute('SELECT bruto_json FROM noticias WHERE id=?',(n.id,)).fetchone()[0];"
            "conn.close();"
            "d = json.loads(raw);"
            "assert d['chave'] == 'valor', d;"
            "assert d['numero'] == 42, d;"
            "print('OK')"
        )
        resultado = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        assert resultado.returncode == 0, resultado.stderr
        assert "OK" in resultado.stdout


class TestSubstituirMencoes:
    def test_insere_e_retorna_contagem(self, banco: Path) -> None:
        salvar_noticias([_noticia("001")], banco)
        qtd = substituir_mencoes([_mencao("id_001")], banco)
        assert qtd == 1

    def test_dados_gravados_corretamente(self, banco: Path) -> None:
        salvar_noticias([_noticia("001")], banco)
        substituir_mencoes([_mencao("id_001", municipio="Picos")], banco)
        df = carregar_mencoes(banco)
        assert not df.empty
        assert df.iloc[0]["municipio"] == "Picos"
        assert df.iloc[0]["doenca"] == "Dengue"
        assert df.iloc[0]["confianca"] == pytest.approx(0.7)

    def test_substituicao_apaga_mencoes_anteriores(self, banco: Path) -> None:
        salvar_noticias([_noticia("001")], banco)
        substituir_mencoes([_mencao("id_001", "Teresina"), _mencao("id_001", "Picos")], banco)
        substituir_mencoes([_mencao("id_001", "Parnaiba")], banco)
        df = carregar_mencoes(banco)
        municipios = set(df["municipio"])
        assert "Parnaiba" in municipios
        assert "Teresina" not in municipios
        assert "Picos" not in municipios

    def test_mencoes_multiplas_noticias(self, banco: Path) -> None:
        salvar_noticias([_noticia("001"), _noticia("002")], banco)
        substituir_mencoes([_mencao("id_001"), _mencao("id_002", "Floriano")], banco)
        df = carregar_mencoes(banco)
        assert len(df) == 2

    def test_sintomas_deserializados(self, banco: Path) -> None:
        salvar_noticias([_noticia("001")], banco)
        substituir_mencoes([_mencao("id_001")], banco)
        df = carregar_mencoes(banco)
        assert isinstance(df.iloc[0]["sintomas"], list)
        assert "Febre alta" in df.iloc[0]["sintomas"]


class TestCarregarDados:
    def test_carregar_registros_noticias_retorna_lista(self, banco: Path) -> None:
        salvar_noticias([_noticia("001"), _noticia("002")], banco)
        registros = carregar_registros_noticias(banco)
        assert isinstance(registros, list)
        assert len(registros) == 2
        assert isinstance(registros[0], dict)

    def test_carregar_registros_vazio(self, banco: Path) -> None:
        registros = carregar_registros_noticias(banco)
        assert registros == []

    def test_carregar_noticias_retorna_dataframe(self, banco: Path) -> None:
        import pandas as pd
        salvar_noticias([_noticia("001")], banco)
        df = carregar_noticias(banco)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "titulo" in df.columns

    def test_carregar_noticias_banco_vazio(self, banco: Path) -> None:
        import pandas as pd
        df = carregar_noticias(banco)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_carregar_mencoes_join_com_noticias(self, banco: Path) -> None:
        salvar_noticias([_noticia("001")], banco)
        substituir_mencoes([_mencao("id_001")], banco)
        df = carregar_mencoes(banco)
        assert "titulo" in df.columns
        assert "doenca" in df.columns
        assert "municipio" in df.columns
        assert "fonte" in df.columns

    def test_carregar_mencoes_banco_vazio(self, banco: Path) -> None:
        import pandas as pd
        df = carregar_mencoes(banco)
        assert isinstance(df, pd.DataFrame)
        assert df.empty


class TestLimpeza:
    def test_limpar_mencoes(self, banco: Path) -> None:
        salvar_noticias([_noticia("001")], banco)
        substituir_mencoes([_mencao("id_001")], banco)
        assert not carregar_mencoes(banco).empty
        limpar_mencoes(banco)
        assert carregar_mencoes(banco).empty

    def test_limpar_mencoes_preserva_noticias(self, banco: Path) -> None:
        salvar_noticias([_noticia("001")], banco)
        substituir_mencoes([_mencao("id_001")], banco)
        limpar_mencoes(banco)
        assert len(carregar_registros_noticias(banco)) == 1

    def test_limpar_banco_remove_arquivo(self, tmp_path: Path) -> None:
        import gc
        caminho = tmp_path / "apagar.sqlite"
        inicializar_banco(caminho)
        salvar_noticias([_noticia("001")], caminho)
        assert caminho.exists()
        gc.collect()  # fecha conexões pendentes no Windows antes de deletar
        limpar_banco(caminho)
        assert not caminho.exists()

    def test_limpar_banco_inexistente_nao_levanta(self, tmp_path: Path) -> None:
        caminho = tmp_path / "nao_existe.sqlite"
        limpar_banco(caminho)


class TestIntegridade:
    def test_chave_estrangeira_impede_mencao_orfao(self, banco: Path) -> None:
        import sqlite3
        mencao = _mencao("id_inexistente")
        sql = (
            "INSERT INTO mencoes"
            " (noticia_id, doenca, municipio, codigo_municipio,"
            "  sentenca, sintomas_json, confianca, extraido_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            mencao.noticia_id,
            mencao.doenca,
            mencao.municipio,
            mencao.codigo_municipio,
            mencao.sentenca,
            json.dumps(mencao.sintomas),
            mencao.confianca,
            mencao.extraido_em,
        )
        with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
            with obter_conexao(banco) as conn:
                conn.execute(sql, params)

    def test_url_unica_na_tabela_noticias(self, banco: Path) -> None:
        n1 = _noticia("001", url="https://exemplo.com/mesmo")
        n2 = _noticia("002", url="https://exemplo.com/mesmo")
        salvar_noticias([n1], banco)
        salvar_noticias([n2], banco)
        registros = carregar_registros_noticias(banco)
        assert len(registros) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
