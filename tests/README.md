# Testes do EpiPiaui Monitor

Este diretório contém testes unitários para validar as funções principais do pipeline PLN.

## Estrutura

- `test_pln.py`: Testes do pipeline de processamento de linguagem natural
  - Extração de entidades (doenças, municípios, sintomas)
  - Cálculo de confiança
  - Lógica de co-ocorrência
  - Testes de integração

- `test_utilitarios.py`: Testes de funções utilitárias
  - Normalização de chaves
  - Geração de IDs estáveis
  - Carregamento e indexação de municípios

## Como executar

### Instalar dependências de desenvolvimento

```bash
pip install -e ".[dev]"
python -m spacy download pt_core_news_lg
```

### Executar todos os testes

```bash
pytest
```

### Executar testes específicos

```bash
# Apenas testes de PLN
pytest tests/test_pln.py -v

# Apenas testes de utilitários
pytest tests/test_utilitarios.py -v

# Teste específico
pytest tests/test_pln.py::TestExtracao::test_extrai_doenca_simples -v
```

### Gerar relatório de cobertura

```bash
pytest --cov=src/epipiaui_monitor --cov-report=html
```

## Cobertura de testes

As classes de teste cobrem:

1. **TestExtracao**: Validação básica de extração de entidades
2. **TestConfianca**: Cálculo de confiança em diferentes cenários
3. **TestExtrairSintomas**: Extração de sintomas
4. **TestCoocorrencia**: Lógica de co-ocorrência doença-município
5. **TestMunicipios**: Reconhecimento de municípios piauienses
6. **TestIntegracaoCompleta**: Testes de fluxo completo
7. **TestNormalizarChave**: Normalização de texto
8. **TestIdEstavel**: Geração determinista de IDs
9. **TestCarregarMunicipios**: Carregamento de dados municipais
10. **TestIndiceMunicipios**: Indexação para acesso rápido

## Exemplo de teste

```python
def test_extrai_doenca_simples(pln, noticia_simples):
    """Teste: extrair doença em caso simples."""
    mencoes = pln.processar_noticia(noticia_simples)
    
    assert len(mencoes) > 0
    assert mencoes[0].doenca == "Dengue"
    assert mencoes[0].municipio == "Teresina"
```

## Fixtures disponíveis

- `pln`: Pipeline PLN inicializado
- `noticia_simples`: Notícia com um caso direto
- `noticia_com_sintomas`: Notícia com menção de sintomas
- `noticia_multiplas_doencas`: Notícia com múltiplas doenças
- `noticia_ambigua`: Notícia com múltiplos municípios
- `noticia_sem_doenca`: Notícia sem menção epidemiológica
