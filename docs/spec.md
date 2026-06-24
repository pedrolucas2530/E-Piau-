# Documento de Requisitos de Produto (PRD) e Especificação de Arquitetura

**Projeto:** EpiPiauí Monitor
**Autor/Organização:** oMacaxeira (Pedro Lucas Alves de Assis Cardoso)

## 1. Visão Geral do Produto

O **EpiPiauí Monitor** é um MVP e instrumento de pesquisa concebido para validar e demonstrar a viabilidade da Epidemiologia Digital no estado do Piauí. O sistema opera extraindo automaticamente menções epidemiológicas (relacionando doenças arboviroses a municípios específicos) a partir de notícias de portais jornalísticos locais e boletins oficiais de saúde.

**Objetivo Principal:** Operar como uma ferramenta de investigação acadêmica focada na identificação de surtos locais baseada no processamento de texto. 
**Aviso:** O sistema atua como complemento experimental e não substitui os sistemas de vigilância oficiais, não realizando diagnóstico clínico ou epidemiológico.

---

## 2. Requisitos Funcionais (RF)

- **RF01 - Coleta de Fontes Públicas:** O sistema deve extrair publicações e artigos de portais pré-configurados (G1 Piauí, Cidade Verde, Secretaria de Saúde - SESAPI e Meio News).
- **RF02 - Modos de Coleta Flexíveis:** Deve ser possível rodar o sistema em múltiplos modos:
  - *Sementes/Reais:* Baseado em um corpus fechado (JSON) pré-verificado para garantia de reprodutibilidade da pesquisa.
  - *Ao Vivo:* Web scraping ativo de URLs em tempo real (filtrado por período).
  - *Amostra:* Base didática offline.
- **RF03 - Armazenamento Bruto:** A ferramenta deve registrar a versão integral e não processada do conteúdo coletado (texto, data, título, URL e metadados) para garantir total rastreabilidade.
- **RF04 - Reconhecimento de Entidades Nomeadas (NER):** O pipeline de Processamento de Linguagem Natural (PLN) deve identificar especificamente:
  - Doenças (Dengue, Zika, Chikungunya e sinônimos).
  - Municípios (Lista oficial de 224 municípios do IBGE para o Piauí).
  - Sintomas associados.
- **RF05 - Associação Heurística de Menções:** O sistema deve relacionar uma doença a um município apenas se ambos co-ocorrerem na mesma sentença, mitigando falsos positivos.
- **RF06 - Cálculo de Nível de Confiança:** Cada menção extraída deve receber um escore numérico de confiança. O cálculo considerará pesos base, presença de sintomas na mesma sentença e termos epidemiológicos no título.
- **RF07 - Deduplicação de Registros:** O sistema não deve registrar múltiplas entradas idênticas da tripla `(doença, município, sentença)` para um mesmo artigo.
- **RF08 - Painel de Monitoramento (Dashboard):** O usuário deve acessar uma interface gráfica web interativa com:
  - Filtros dinâmicos (por doença, fonte, município, datas e nível de confiança).
  - Mapa interativo do estado destacando regiões afetadas.
  - Gráficos de distribuição temporal e por patologia.
  - Tabela de dados auditável que exponha a sentença que gerou a extração e o link original.

---

## 3. Requisitos Não Funcionais (RNF)

- **RNF01 - Reprodutibilidade:** O processamento do corpus fechado deve produzir invariavelmente os mesmos resultados quantitativos, vital para o contexto de pesquisa (TCC).
- **RNF02 - Processamento Offline:** O pipeline de PLN deve rodar localmente sem dependência de APIs externas de inteligência artificial ou infraestrutura em nuvem pesada.
- **RNF03 - Rastreabilidade:** Qualquer menção visualizada no painel deve permitir a auditoria de volta à sentença extraída e ao documento fonte bruto.

---

## 4. Arquitetura do Sistema

A arquitetura escolhida por "oMacaxeira" prioriza simplicidade, transparência nos algoritmos analíticos (rule-based) e facilidade de implantação local.

### 4.1. Stack Tecnológico
- **Linguagem:** Python 3.11+
- **Processamento de Linguagem Natural:** `spaCy`
- **Banco de Dados:** `SQLite` (relacional, embutido e serverless)
- **Frontend / UI:** `Streamlit` integrado com bibliotecas de mapa interativo (`Folium`/`Leaflet`)

### 4.2. Desenho Arquitetural
A aplicação segue um pipeline clássico de extração, transformação e carga (ETL), acoplado a um visualizador, dividido em três camadas:

1. **Camada de Coleta (Ingestão)**
   - Scripts modulares (`src/coletores`) que lidam com requisições HTTP, parsing de RSS e HTML para raspar textos de páginas da web.
   - Suporte primário à extração de sementes estruturadas visando controle rígido para a pesquisa.

2. **Camada de Processamento e Persistência (Backend)**
   - O texto bruto coletado é primeiro gravado na tabela `noticias` no SQLite.
   - O pipeline NLP (`src/pln`) carrega o texto e processa sentença por sentença.
   - O spaCy é utilizado utilizando seu modelo `pt_core_news_lg` para a segmentação de frases.
   - A extração é regida por um `EntityRuler` customizado (com fallback rules) que encontra padrões exatos e flexíveis (ex: "febre do zika"), dispensando modelos probabilísticos obscuros.
   - Quando um padrão (doença + município) casa na mesma sentença, o módulo gera um registro na tabela `mencoes` associada pela Foreign Key da notícia.

3. **Camada de Visualização (Frontend)**
   - O script `interface/painel.py` levanta um servidor local pelo Streamlit.
   - O painel consulta diretamente as tabelas do SQLite, formata os DataFrames (Pandas) e renderiza componentes interativos e o mapa Folium no navegador em tempo real.

### 4.3. Trade-offs e Decisões de Design (Limitações)
- **Precisão vs Recall:** A regra rígida de "co-ocorrência na mesma sentença" garante altíssima Precisão (94.9%), mas prejudica consideravelmente o Recall (42.5%), pois o sistema falha em artigos onde a doença é dita no 1º parágrafo e os municípios são listados no 2º parágrafo.
- **Regras Estáticas em vez de LLMs:** Optou-se por NER tradicional e regras para garantir que os testes sejam determinísticos e explicáveis do ponto de vista metodológico.
- **Desconhecimento Semântico (Negações):** O modelo é ingênuo em relação a contextos semânticos invertidos ("não há casos da doença X em Y"). Isso foi aceito como limitação do escopo experimental.
