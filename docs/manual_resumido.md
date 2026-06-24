# Manual Resumido: Busca e Processamento de Notícias

O sistema **EpiPiauí Monitor** realiza a busca, coleta e processamento de notícias relacionadas a arboviroses no estado do Piauí. O fluxo é dividido em duas etapas principais: Coleta e Processamento (PLN).

## 1. Coleta de Notícias

A coleta é responsável por buscar notícias em fontes específicas e filtrá-las.

- **Busca de Sementes (`buscar_sementes_2024.py`)**: Este script varre feeds RSS (G1 Piauí) e páginas de listagem de portais de notícias (Cidade Verde, SESAPI). Ele extrai os links, baixa o conteúdo HTML, encontra a data de publicação e o texto.
- **Filtragem Estrita**: Durante a coleta, o sistema verifica se o título ou a URL da notícia contém alguma palavra-chave relacionada a arboviroses. Apenas notícias que dão "match" com esses termos são enriquecidas e armazenadas.
- **Efetivação da Coleta (`scripts/coletar.py`)**: Insere os dados encontrados, amostras ou requisições ao vivo dentro de um banco SQLite para serem consumidas no pipeline.

> **Observação de Refatoração (Valores Hardcoded na Coleta):**
> - **Doenças (Palavras-chave):** No arquivo `buscar_sementes_2024.py`, as palavras de filtro estão fixas na constante `PALAVRAS_CHAVE = {"dengue", "zika", "chikungunya", "arbovirose", "aedes"}`.
> - **Cidades/Regiões (Fontes):** No mesmo arquivo, os alvos de coleta (portais do Piauí) estão estritamente definidos na constante `FONTES` (G1 Piaui, Cidade Verde, SESAPI).
> Para expandir o sistema para outras doenças ou localidades, esses parâmetros precisam ser injetados de forma dinâmica ou via arquivo de configuração.

## 2. Processamento de Notícias (PLN)

Após as notícias serem coletadas, a etapa de Processamento Analítico (`scripts/processar.py` interligado com `src/epipiaui_monitor/pln/processador.py`) analisa os textos extraindo menções com relevância epidemiológica.

- **Reconhecimento de Entidades (NER):** Utilizando o `spaCy` (com fallback de regex simples), o pipeline divide o texto das notícias em sentenças e extrai entidades. Ele mapeia entidades do tipo `DOENCA`, `MUNICIPIO` e `SINTOMA`.
- **Relacionamento e Cálculo de Confiança:** Quando o sistema encontra uma doença e um município referenciados dentro da mesma frase (sentença), ele gera um registro de "Menção Extraída". Ele então calcula uma nota de confiança (base, incrementada se o título da notícia tiver termos chave ou se múltiplos sintomas forem descritos na frase).

> **Configuração do tema (atualizado):**
> - **Doenças, variações e sintomas:** não estão mais fixos no código. O `src/epipiaui_monitor/pln/processador.py` carrega um **domínio de investigação** (`src/epipiaui_monitor/dominio.py`) a partir de um arquivo JSON em `config/dominios/`. O domínio padrão é `arboviroses.json` (Dengue, Zika, Chikungunya e sintomas), com o mesmo conteúdo de antes; para investigar outro tema, basta trocar o arquivo (ex.: `criminalidade.json`) via `--dominio` ou pela variável `EPIPIAUI_DOMINIO` no painel. Detalhes em `docs/dominios.md`.
> - **Cidades (Municípios):** continuam sendo o **eixo fixo**, carregadas pelo módulo `src/epipiaui_monitor/piaui.py` (lista oficial de 224 municípios do Piauí via IBGE, com `MUNICIPIOS_RESERVA` como fallback offline). Por opção de projeto, o município permanece a âncora geográfica.
> - **Coleta de sementes:** o script `buscar_sementes_2024.py` (construtor do corpus fechado) ainda mantém suas próprias constantes `PALAVRAS_CHAVE` e `FONTES`; generalizar essa etapa fica como trabalho futuro.

## 3. Fluxo Completo da Aplicação

O diagrama abaixo ilustra todo o pipeline de execução do projeto, desde a busca da notícia até o processamento das menções, baseado na ordem de chamada pelo orquestrador `scripts/executar_pipeline.py`.

```mermaid
sequenceDiagram
    autonumber
    actor Usuario
    participant BuscarSementes as buscar_sementes_2024.py
    participant Fontes as Fontes Web (G1, Cidade Verde, SESAPI)
    participant JSON as sementes_noticias_reais_2024.json
    participant Coletar as scripts/coletar.py
    participant DB as SQLite (epipiaui_monitor.sqlite)
    participant Processar as scripts/processar.py
    participant PLN as EpiPiauiPLN (spaCy/Regex)

    %% Etapa 1: Preparação de sementes (Opcional/Periódico)
    Note over Usuario, JSON: Etapa Prévia: Descoberta de Notícias Base
    Usuario->>BuscarSementes: Executa busca de sementes
    BuscarSementes->>Fontes: Faz requisições GET (RSS/HTML)
    Fontes-->>BuscarSementes: Retorna conteúdo bruto das notícias
    BuscarSementes->>BuscarSementes: Filtra por palavras-chave de arbovirose
    BuscarSementes->>JSON: Salva arquivo com notícias válidas

    %% Etapa 2: Pipeline de Coleta
    Note over Usuario, DB: Passo 1 do Pipeline: Consolidação no Banco
    Usuario->>Coletar: Executa scripts/coletar.py
    Coletar->>JSON: Carrega notícias do arquivo JSON
    Coletar->>Fontes: (Opcional) Coleta notícias 'ao-vivo'
    Fontes-->>Coletar: Retorna novas notícias frescas
    Coletar->>DB: Salva todas as notícias na tabela 'noticias'

    %% Etapa 3: Pipeline de Processamento (PLN)
    Note over Usuario, PLN: Passo 2 do Pipeline: Extração de Entidades (NER)
    Usuario->>Processar: Executa scripts/processar.py
    Processar->>DB: Lê textos armazenados na tabela 'noticias'
    DB-->>Processar: Retorna registros não processados
    Processar->>PLN: Passa os textos para processamento analítico
    PLN->>PLN: Identifica Doenças, Sintomas e Municípios na mesma sentença
    PLN-->>Processar: Retorna objetos 'MencaoExtraida' com grau de confiança
    Processar->>DB: Limpa menções antigas e salva as novas na tabela 'mencoes'
```
