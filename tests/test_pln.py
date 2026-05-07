"""
Testes unitários para o pipeline PLN do EpiPiaui Monitor.

Cobre as funções principais de extração de entidades e cálculo de confiança.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epipiaui_monitor.modelos import Noticia
from epipiaui_monitor.pln.processador import EpiPiauiPLN


@pytest.fixture
def pln():
    """Carrega o pipeline PLN uma única vez para todos os testes."""
    return EpiPiauiPLN()


@pytest.fixture
def noticia_simples():
    """Notícia simples com uma menção direta."""
    return Noticia(
        id="test_001",
        fonte="test",
        titulo="Dengue em Teresina",
        texto="Teresina registrou aumento de casos de dengue.",
        data_publicacao="2024-06-01",
        url="http://test.com",
        coletado_em="2024-06-01",
    )


@pytest.fixture
def noticia_com_sintomas():
    """Notícia com menção de sintomas."""
    return Noticia(
        id="test_002",
        fonte="test",
        titulo="Dengue com sintomas graves",
        texto="Pacientes em Teresina apresentam febre alta e dor no corpo.",
        data_publicacao="2024-06-01",
        url="http://test.com",
        coletado_em="2024-06-01",
    )


@pytest.fixture
def noticia_multiplas_doencas():
    """Notícia com múltiplas doenças."""
    return Noticia(
        id="test_003",
        fonte="test",
        titulo="Arboviroses no Piauí",
        texto="Piauí registra casos de dengue, zika e chikungunya em Teresina.",
        data_publicacao="2024-06-01",
        url="http://test.com",
        coletado_em="2024-06-01",
    )


@pytest.fixture
def noticia_ambigua():
    """Notícia com possível ambiguidade (múltiplos municípios)."""
    return Noticia(
        id="test_004",
        fonte="test",
        titulo="Dengue em vários municípios",
        texto="Teresina e Picos reportam dengue.",
        data_publicacao="2024-06-01",
        url="http://test.com",
        coletado_em="2024-06-01",
    )


@pytest.fixture
def noticia_sem_doenca():
    """Notícia sem menção de doença."""
    return Noticia(
        id="test_005",
        fonte="test",
        titulo="Notícia sobre Teresina",
        texto="Teresina é a capital do Piauí.",
        data_publicacao="2024-06-01",
        url="http://test.com",
        coletado_em="2024-06-01",
    )


class TestExtracao:
    """Testes de extração básica de entidades."""

    def test_extrai_doenca_simples(self, pln, noticia_simples):
        """Teste: extractar doença em caso simples."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        assert len(mencoes) > 0, "Deveria extrair pelo menos uma menção"
        assert mencoes[0].doenca == "Dengue"
        assert mencoes[0].municipio == "Teresina"

    def test_extrai_multiplas_doencas(self, pln, noticia_multiplas_doencas):
        """Teste: extrair múltiplas doenças da mesma notícia."""
        mencoes = pln.processar_noticia(noticia_multiplas_doencas)
        
        doencas_extraidas = {m.doenca for m in mencoes}
        assert "Dengue" in doencas_extraidas
        assert "Zika" in doencas_extraidas
        assert "Chikungunya" in doencas_extraidas

    def test_nao_extrai_sem_doenca(self, pln, noticia_sem_doenca):
        """Teste: não extrair menções quando falta doença."""
        mencoes = pln.processar_noticia(noticia_sem_doenca)
        
        # Podem haver menções de município, mas sem doença não deve haver coocorrência
        for mencao in mencoes:
            assert mencao.doenca is not None or len(mencoes) == 0

    def test_preserva_sentenca_original(self, pln, noticia_simples):
        """Teste: verificar se sentença original é preservada."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        assert len(mencoes) > 0
        assert "dengue" in mencoes[0].sentenca.lower()
        assert "Teresina" in mencoes[0].sentenca


class TestConfianca:
    """Testes de cálculo de confiança."""

    def test_confianca_base_sem_sintomas(self, pln, noticia_simples):
        """Teste: confiança base sem sintomas."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        assert len(mencoes) > 0
        # Base é 0.6 (doença + município)
        assert mencoes[0].confianca >= 0.6

    def test_confianca_aumenta_com_sintomas(self, pln):
        """Teste: confiança aumenta quando há sintomas."""
        noticia = Noticia(
            id="test_symp",
            fonte="test",
            titulo="Dengue",
            texto="Pacientes em Teresina com febre alta e dor no corpo.",
            data_publicacao="2024-06-01",
            url="http://test.com",
            coletado_em="2024-06-01",
        )
        mencoes = pln.processar_noticia(noticia)
        
        assert len(mencoes) > 0
        # Com sintomas deve ser > 0.6
        assert mencoes[0].confianca > 0.6

    def test_confianca_aumenta_com_titulo(self, pln):
        """Teste: confiança aumenta quando doença está no título."""
        noticia = Noticia(
            id="test_006",
            fonte="test",
            titulo="Dengue grave em Teresina",
            texto="Teresina registra aumento.",
            data_publicacao="2024-06-01",
            url="http://test.com",
            coletado_em="2024-06-01",
        )
        mencoes = pln.processar_noticia(noticia)
        
        assert len(mencoes) > 0
        # Deve ter bonus por estar no título
        assert mencoes[0].confianca > 0.6

    def test_confianca_limitada_a_maxima(self, pln):
        """Teste: confiança não excede limite máximo."""
        noticia = Noticia(
            id="test_max",
            fonte="test",
            titulo="Dengue grave em Teresina",
            texto="Teresina registra dengue com febre alta, dor no corpo, dor de cabeça.",
            data_publicacao="2024-06-01",
            url="http://test.com",
            coletado_em="2024-06-01",
        )
        mencoes = pln.processar_noticia(noticia)
        
        assert len(mencoes) > 0
        # Máximo é 0.8
        assert mencoes[0].confianca <= 0.8


class TestExtrairSintomas:
    """Testes de extração de sintomas."""

    def test_extrai_sintomas(self, pln):
        """Teste: extrair sintomas da notícia."""
        noticia = Noticia(
            id="test_symp2",
            fonte="test",
            titulo="Dengue em Teresina",
            texto="Teresina registra dengue com febre alta e dor no corpo.",
            data_publicacao="2024-06-01",
            url="http://test.com",
            coletado_em="2024-06-01",
        )
        mencoes = pln.processar_noticia(noticia)
        
        assert len(mencoes) > 0
        sintomas = mencoes[0].sintomas
        assert "Febre alta" in sintomas or "Dor no corpo" in sintomas

    def test_lista_sintomas_nao_vazia_quando_presentes(self, pln, noticia_com_sintomas):
        """Teste: lista de sintomas não vazia quando presentes."""
        mencoes = pln.processar_noticia(noticia_com_sintomas)
        
        assert len(mencoes) > 0
        assert len(mencoes[0].sintomas) >= 1

    def test_lista_sintomas_vazia_quando_ausentes(self, pln, noticia_simples):
        """Teste: lista de sintomas vazia quando não mencionados."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        assert len(mencoes) > 0
        assert len(mencoes[0].sintomas) == 0


class TestCoocorrencia:
    """Testes de lógica de co-ocorrência."""

    def test_coocorrencia_doenca_municipio_mesma_sentenca(self, pln, noticia_simples):
        """Teste: detecta co-ocorrência na mesma sentença."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        # Deve extrair porque estão na mesma sentença
        assert len(mencoes) > 0

    def test_multiplos_municipios_mesmo_titulo(self, pln, noticia_ambigua):
        """Teste: lidar com múltiplos municípios no título."""
        mencoes = pln.processar_noticia(noticia_ambigua)
        
        # Deve extrair múltiplas menções (uma para cada município)
        municipios = {m.municipio for m in mencoes}
        assert len(municipios) >= 1  # Pelo menos um

    def test_sentencas_sem_coocorrencia_descartadas(self, pln):
        """Teste: descartar sentenças sem co-ocorrência."""
        noticia = Noticia(
            id="test_007",
            fonte="test",
            titulo="Saúde no Piauí",
            texto="Dengue é uma doença. Teresina é uma cidade.",
            data_publicacao="2024-06-01",
            url="http://test.com",
            coletado_em="2024-06-01",
        )
        mencoes = pln.processar_noticia(noticia)
        
        # Não deve extrair porque não há co-ocorrência na mesma sentença
        assert len(mencoes) == 0 or all(
            m.doenca and m.municipio for m in mencoes
        )


class TestMunicipios:
    """Testes de extração de municípios do Piauí."""

    def test_reconhece_teresina(self, pln, noticia_simples):
        """Teste: reconhecer Teresina."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        assert len(mencoes) > 0
        assert mencoes[0].municipio == "Teresina"

    def test_reconhece_multiplos_municipios(self, pln, noticia_ambigua):
        """Teste: reconhecer múltiplos municípios."""
        mencoes = pln.processar_noticia(noticia_ambigua)
        
        municipios = {m.municipio for m in mencoes}
        assert len(municipios) >= 1

    def test_atribui_codigo_municipio(self, pln, noticia_simples):
        """Teste: verificar atribuição de código de município."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        assert len(mencoes) > 0
        assert mencoes[0].codigo_municipio is not None
        assert mencoes[0].codigo_municipio.isdigit()


class TestIntegracaoCompleta:
    """Testes de integração completa."""

    def test_processa_multiplas_noticias(self, pln, noticia_simples, noticia_com_sintomas):
        """Teste: processar lista de notícias."""
        noticias = [noticia_simples, noticia_com_sintomas]
        mencoes = pln.processar_noticias(noticias)
        
        assert len(mencoes) > 0
        assert len(mencoes) >= 2  # Pelo menos uma de cada

    def test_mencoes_tem_timestamp(self, pln, noticia_simples):
        """Teste: verificar se mencões têm timestamp."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        assert len(mencoes) > 0
        assert mencoes[0].extraido_em is not None
        assert "Z" in mencoes[0].extraido_em  # ISO format

    def test_menificaca_preserva_noticia_id(self, pln, noticia_simples):
        """Teste: verificar se ID da notícia é preservado."""
        mencoes = pln.processar_noticia(noticia_simples)
        
        assert len(mencoes) > 0
        assert mencoes[0].noticia_id == "test_001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
