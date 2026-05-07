# EpiPiaui Monitor

MVP acadêmico para validar um fluxo de Epidemiologia Digital no contexto do Piauí. O protótipo coleta notícias públicas reais de 2024, armazena o material bruto, aplica regras de PLN com spaCy para detectar doenças, municípios e sintomas, e mostra os resultados em um painel Streamlit com mapa Leaflet/Folium.

O objetivo é demonstrar viabilidade técnica. O sistema não substitui vigilância oficial, não faz diagnóstico epidemiológico e não deve ser usado como fonte única de decisão em saúde pública.

## Funcionalidades

- Coleta de notícias de fontes públicas configuradas: G1 Piauí, Cidade Verde e SESAPI.
- Armazenamento rastreável em SQLite, mantendo texto, data, URL e metadados brutos.
- NER customizado com spaCy para Dengue, Zika, Chikungunya, municípios do Piauí e sintomas.
- Heurística de coocorrência por sentença para associar doença e município.
- Painel com mapa do Piauí, distribuição temporal, distribuição por doença e tabela auditável.
- Conjunto de sementes reais de janeiro a julho de 2024 para apresentação reprodutível.
- Amostra didática offline mantida apenas como reserva.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download pt_core_news_lg
```

Se o modelo `pt_core_news_lg` não estiver instalado, o código tenta `pt_core_news_md`, depois `pt_core_news_sm`, e por fim usa um pipeline básico em português com regras customizadas.

## Execução Rápida

Gera o banco SQLite com notícias/documentos reais de janeiro a julho de 2024 e processa as menções:

```powershell
python scripts/executar_pipeline.py --modo reais
```

Abre o painel:

```powershell
streamlit run interface/painel.py
```

## Fontes Reais de 2024

O arquivo `dados/brutos/sementes_noticias_reais_2024.json` lista URLs reais e verificáveis usadas pelo modo `reais`. Ele inclui:

- G1 Piauí: matérias de março de 2024 sobre dengue, zika e chikungunya.
- Governo do Piauí / SESAPI: notícia oficial de janeiro de 2024.
- Cidade Verde: matérias e documentos localizados no período; quando o site bloqueia coleta automatizada, o registro fica marcado como `reserva_usada=true`.
- SESAPI: informes epidemiológicos oficiais em PDF, usados com texto de apoio rastreável.

Para reconstruir o banco mantendo registros existentes:

```powershell
python scripts/executar_pipeline.py --modo reais --manter-existente
```

## Coleta Ao Vivo

Para tentar coletar das fontes públicas configuradas:

```powershell
python scripts/executar_pipeline.py --modo ao-vivo
```

Também é possível combinar amostra e coleta ao vivo:

```powershell
python scripts/executar_pipeline.py --modo ambos
```

Por padrão, a coleta ao vivo filtra o período de `2024-01-01` a `2024-12-31`, quando a página informa data de publicação. Nem todo portal expõe histórico completo ou HTML estável; por isso o modo `reais` usa sementes verificadas.

## Estrutura

```text
interface/
  painel.py                         # Streamlit + Folium/Leaflet
dados/
  brutos/amostra_noticias.json      # amostra didática offline
  brutos/sementes_noticias_reais_2024.json
  processados/                      # cache de municípios e GeoJSON
docs/
  fontes_reais_2024.md
  relatorio_tecnico.md
notebooks/
  01_fluxo_prototipo.ipynb
scripts/
  coletar.py                        # coleta e gravação no SQLite
  processar.py                      # PLN e extração de menções
  executar_pipeline.py              # coleta + processamento
src/epipiaui_monitor/
  coletores/                        # coleta por RSS, HTML e sementes
  pln/                              # EntityRuler + coocorrência
  banco.py                          # esquema SQLite e consultas
  configuracao.py                   # caminhos e fontes
  modelos.py                        # estruturas de dados
  piaui.py                          # municípios via IBGE/cache/reserva
```

## Banco de Dados

O SQLite fica em `dados/epipiaui_monitor.sqlite` e contém:

- `noticias`: notícia bruta, fonte, título, texto, data, URL e metadados.
- `mencoes`: doença, município, sentença, sintomas, confiança e vínculo com a notícia.

## Limitações

- A coleta ao vivo depende da estrutura atual dos sites públicos.
- A amostra local é sintética e serve apenas para demonstrar o fluxo offline.
- A heurística por coocorrência favorece rastreabilidade, mas não substitui validação humana.
- O nível de confiança é uma pontuação operacional simples, não uma probabilidade epidemiológica.
