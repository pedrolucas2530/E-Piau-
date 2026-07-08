# EpiPiaui Monitor

MVP acadêmico para validar um fluxo de Epidemiologia Digital no contexto do Piauí. O protótipo coleta notícias públicas reais de 2024, armazena o material bruto, aplica regras de PLN com spaCy para detectar doenças, municípios e sintomas, e mostra os resultados em um painel Streamlit com mapa Leaflet/Folium.

O objetivo é demonstrar viabilidade técnica. O sistema não substitui vigilância oficial, não faz diagnóstico epidemiológico e não deve ser usado como fonte única de decisão em saúde pública.

## Funcionalidades

- Coleta de notícias de fontes públicas configuradas: G1 Piauí, Cidade Verde, SESAPI e Meio News.
- Armazenamento rastreável em SQLite, mantendo texto, data, URL e metadados brutos.
- NER customizado com spaCy para Dengue, Zika, Chikungunya, municípios do Piauí e sintomas.
- Heurística de coocorrência por sentença para associar doença e município.
- Painel com mapa do Piauí, distribuição temporal, distribuição por doença e tabela auditável.
- Conjunto de sementes reais de janeiro a dezembro de 2024 para apresentação reprodutível.
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

Gera o banco SQLite com notícias/documentos reais de janeiro a dezembro de 2024 e processa as menções:

```powershell
python scripts/executar_pipeline.py --modo reais
```

Abre o painel:

```powershell
streamlit run interface/painel.py
```

## Reprodução da avaliação (TCC)

Esta seção permite reexecutar a avaliação quantitativa relatada na monografia e reobter exatamente as métricas da **Tabela 3** (desempenho do NER). A avaliação é determinística e roda sobre o corpus fechado (`dados/brutos/sementes_noticias_reais_2024.json`) e o Padrão-Ouro anotado manualmente (`dados/gold_standard/gold_standard.json`).

### Métricas principais (Tabela 3)

```powershell
python scripts/avaliar_ner.py
```

Imprime a tabela de Precisão, Revocação e F1 (por doença e agregada) e atualiza `dados/gold_standard/resultado_avaliacao.json`. Resultado esperado (agregado):

```
GERAL   VP=37  FP=2  FN=50   P=94,9%  R=42,5%  F1=58,7%
```

### Análises complementares

```powershell
python scripts/analises_complementares.py
```

Reproduz as análises de rigor discutidas na monografia: (d) validade discriminativa do escore de confiança (VP e FP com escore idêntico de 0,70); (c) trade-off da janela de associação (janela de documento: P=64,9%, R=100%, F1=78,7%, como contraexemplo controlado); e os intervalos de confiança de 95% por *bootstrap* (10.000 reamostras).

> **Observação sobre reprodutibilidade:** os números da monografia foram obtidos com o modelo `pt_core_news_lg`. Versões diferentes do spaCy podem alterar contagens marginais; para reobter os valores exatos, utilize as versões fixadas em `requirements.txt`.

## Instruções Técnicas Completas

### 1. Pré-requisitos

```powershell
# Verificar versão do Python (requerido 3.11+)
python --version

# Verificar ambiente virtual ativado
# Você deve ver (.venv) no início do prompt do terminal
```

### 2. Ativar Ambiente Virtual

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Se der erro de política de execução
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 3. Coletar Dados (escolha um modo)

```powershell
# Opção A: Usar notícias reais pré-verificadas (janeiro-dezembro 2024)
python scripts/coletar.py --modo reais

# Opção B: Coletar ao vivo dos portais (com filtro de período)
python scripts/coletar.py --modo ao-vivo --data-inicio 2024-01-01 --data-fim 2024-06-30

# Opção C: Dados didáticos (amostra sintética offline)
python scripts/coletar.py --modo amostra

# Opção D: Combinar sementes + coleta ao vivo
python scripts/coletar.py --modo ambos

# Opção E: Resetar banco (limpa tudo antes de coletar)
python scripts/coletar.py --modo reais --reiniciar
```

### 4. Processar Notícias (Extração PLN)

```powershell
# Extrair doenças, municípios e sintomas usando spaCy
python scripts/processar.py

# OU fazer coleta + processamento em um passo
python scripts/executar_pipeline.py --modo reais
```

### 5. Iniciar o Painel

```powershell
# Comando básico
streamlit run interface/painel.py

# Com Python explícito (se houver conflito)
python -m streamlit run interface/painel.py

# Especificar porta diferente (padrão: 8501)
streamlit run interface/painel.py --server.port 8502
```

### 6. Acessar o Painel

O navegador abre automaticamente em:

```
http://localhost:8501
```

Se não abrir, acesse manualmente a URL acima.

### 7. Recursos do Painel

- **Barra Lateral**: Filtros por doença, fonte, município, data e nível de confiança
- **Aba Análise**: Mapa interativo do Piauí, gráficos de distribuição, série temporal e tabela de registros
- **Aba Sobre**: Informações do projeto, limitações e FAQ

### 8. Dados Persistem?

**Sim!** O banco SQLite acumula dados de múltiplas execuções. Se você executar:

```powershell
# 1ª coleta
python scripts/coletar.py --modo reais          # Salva 100 notícias

# 2ª coleta
python scripts/coletar.py --modo ao-vivo        # Adiciona mais notícias (sem deletar as 100)

# Painel mostrará: 100 + novas = todos os registros juntos
```

Para começar do zero, use a flag `--reiniciar`.

### 9. Troubleshooting

```powershell
# Erro: "ModuleNotFoundError: No module named 'streamlit'"
pip install -e ".[dev]"

# Erro: "Banco de dados não encontrado"
python scripts/coletar.py --modo reais

# Erro: Porta 8501 já em uso
streamlit run interface/painel.py --server.port 8502

# Erro: Modelo spaCy não encontrado
python -m spacy download pt_core_news_lg

# Limpar cache do Streamlit
streamlit cache clear
```

### 10. Workflow Completo (do Zero)

```powershell
# 1. Ativar ambiente
.\.venv\Scripts\Activate.ps1

# 2. Coletar dados
python scripts/coletar.py --modo reais

# 3. Processar (PLN)
python scripts/processar.py

# 4. Iniciar painel
streamlit run interface/painel.py

# 5. Navegador abre automaticamente em http://localhost:8501
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

## Domínio configurável (tema)

O motor de extração é genérico: ele correlaciona um **tema** com um **município** por co-ocorrência em sentença. O município é o eixo fixo (IBGE); o tema é configurável por um JSON em `config/dominios/`. Por padrão usa-se `arboviroses.json` (Dengue, Zika, Chikungunya), mas é possível trocar o tema sem mudar o código — por exemplo, para criminalidade:

```powershell
python scripts/processar.py --dominio config/dominios/criminalidade.json
```

Detalhes, formato do arquivo e pontos de extensão em `docs/dominios.md`.

## Limitações

- A coleta ao vivo depende da estrutura atual dos sites públicos.
- A amostra local é sintética e serve apenas para demonstrar o fluxo offline.
- A heurística por coocorrência favorece rastreabilidade, mas não substitui validação humana.
- O nível de confiança é uma pontuação operacional simples, não uma probabilidade epidemiológica.
