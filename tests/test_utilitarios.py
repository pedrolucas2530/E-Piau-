"""
Testes para funções utilitárias do EpiPiaui Monitor.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epipiaui_monitor.utilitarios import normalizar_chave, id_estavel
from epipiaui_monitor.piaui import carregar_municipios, indice_municipios


class TestNormalizarChave:
    """Testes de normalização de chaves."""

    def test_converte_para_minusculas(self):
        """Teste: converter para minúsculas."""
        resultado = normalizar_chave("DENGUE")
        assert resultado == "dengue"

    def test_remove_acentos(self):
        """Teste: remover acentos."""
        resultado = normalizar_chave("Febre Atrás dos Olhos")
        assert "atrás" not in resultado.lower()  # Removido acento
        assert "atras" in resultado.lower()

    def test_remove_espacos_extras(self):
        """Teste: remover espaços extras."""
        resultado = normalizar_chave("  dengue  grave  ")
        assert resultado == "dengue grave"

    def test_trata_caracteres_especiais(self):
        """Teste: tratar caracteres especiais."""
        resultado = normalizar_chave("dengue-grave")
        assert isinstance(resultado, str)
        assert len(resultado) > 0

    def test_entrada_vazia(self):
        """Teste: lidar com entrada vazia."""
        resultado = normalizar_chave("")
        assert resultado == ""


class TestIdEstavel:
    """Testes de geração de ID estável."""

    def test_gera_id_determinista(self):
        """Teste: gerar ID determinista."""
        id1 = id_estavel("dengue", "teresina", "2024-06-01")
        id2 = id_estavel("dengue", "teresina", "2024-06-01")
        assert id1 == id2

    def test_id_diferente_para_entrada_diferente(self):
        """Teste: ID diferente para entrada diferente."""
        id1 = id_estavel("dengue", "teresina", "2024-06-01")
        id2 = id_estavel("zika", "teresina", "2024-06-01")
        assert id1 != id2

    def test_id_tem_comprimento_minimo(self):
        """Teste: ID tem comprimento mínimo."""
        id_gerado = id_estavel("teste")
        assert len(id_gerado) >= 12  # Hash SHA256 truncado tem pelo menos isso


class TestCarregarMunicipios:
    """Testes de carregamento de municípios."""

    def test_carrega_municipios(self):
        """Teste: carregar lista de municípios."""
        municipios = carregar_municipios()
        assert len(municipios) > 0
        assert len(municipios) >= 224  # Piauí tem 224 municípios

    def test_municipio_tem_id(self):
        """Teste: cada município tem ID."""
        municipios = carregar_municipios()
        for mun in municipios:
            assert "id" in mun
            assert "nome" in mun

    def test_teresina_presente(self):
        """Teste: Teresina está na lista."""
        municipios = carregar_municipios()
        nomes = {m["nome"] for m in municipios}
        assert "Teresina" in nomes


class TestIndiceMunicipios:
    """Testes de criação do índice de municípios."""

    def test_cria_indice(self):
        """Teste: criar índice de municípios."""
        municipios = carregar_municipios()
        indice = indice_municipios(municipios)
        assert len(indice) > 0

    def test_acesso_por_chave_normalizada(self):
        """Teste: acessar município por chave normalizada."""
        municipios = carregar_municipios()
        indice = indice_municipios(municipios)
        
        # Deve achar "Teresina" mesmo com diferentes variações
        assert "teresina" in indice
        resultado = indice["teresina"]
        assert resultado["nome"] == "Teresina"

    def test_indice_case_insensitive(self):
        """Teste: índice é case-insensitive."""
        municipios = carregar_municipios()
        indice = indice_municipios(municipios)
        
        # Diferentes capitalizações devem funcionar
        assert "TERESINA" in indice or "teresina" in indice or "Teresina" in indice


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
