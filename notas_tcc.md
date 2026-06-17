# Notas de Pesquisa — EpiPiaui Monitor TCC
**Última atualização:** 2026-06-15  
**Autor:** Pedro Lucas Alves de Assis Cardoso  
**Propósito:** Registro contínuo de achados, observações metodológicas e dados quantitativos para uso na escrita da monografia. Atualizar a cada sessão de trabalho.

---

## 1. Escopo e enquadramento do trabalho

### Reorientação definitiva do escopo (decisão do pesquisador)
- O trabalho NÃO é um produto de software finalizado.
- O **MVP é descrito exclusivamente como instrumento de pesquisa** — nunca como "sistema", "ferramenta" ou "produto".
- A pesquisa é uma **investigação exploratória sobre a viabilidade da Epidemiologia Digital no contexto piauiense**.
- O painel/dashboard é o **instrumento metodológico de investigação**, não o objeto de entrega.
- A coleta em tempo real (scraping ativo) **não é prioridade** neste trabalho; o corpus é fechado.
- As métricas de P/R/F1 são **dados de pesquisa que sustentam a análise**, não métricas de produto.
- Prioridade do trabalho: monografia > gold standard > análise estatística > engenharia de software.

### Pergunta de pesquisa (formulação atual)
É viável aplicar técnicas de Processamento de Linguagem Natural (PLN) para extração automática de menções epidemiológicas (doença × município) a partir de notícias jornalísticas e boletins oficiais sobre arboviroses no Piauí?

---

## 2. Corpus de análise

### Descrição do corpus fechado
- **Arquivo:** `dados/brutos/sementes_noticias_reais_2024.json`
- **Tamanho:** 35 artigos (expandido de 19 para 35 em sessão de trabalho)
- **Cobertura temporal:** Janeiro a Dezembro de 2024 (todos os 12 meses representados)
- **Fontes:**
  - Cidade Verde: 18 artigos
  - SESAPI: 6 artigos
  - G1 Piauí: 5 artigos
  - Ministério da Saúde: 2 artigos
  - Portal O Dia: 1 artigo
  - Portal B1: 1 artigo
  - A10+: 1 artigo
  - Governo do Piauí / SESAPI: 1 artigo
- **Representatividade:** cobre surto de dengue 2024 (pico epidêmico), redução sazonal, e vigilância de chikungunya no 2º semestre.
- **Natureza:** corpus fechado, curado manualmente. Cada artigo possui `texto_reserva` com conteúdo substantivo verificado.

### Justificativa do corpus fechado (para a monografia)
O corpus fechado foi escolhido por três razões metodológicas:
1. **Reprodutibilidade:** permite que a avaliação seja replicada com os mesmos dados.
2. **Controle de qualidade:** os textos foram verificados manualmente antes da inclusão.
3. **Viabilidade:** a coleta ao vivo depende de disponibilidade de URLs e robustez do scraping, variáveis fora do escopo desta investigação.

---

## 3. Pipeline de PLN — funcionamento

### Arquitetura geral
- Modelo base: spaCy `pt_core_news_lg` (com fallback para `md`, `sm` e `blank+sentencizer`)
- Componente principal: `EntityRuler` com `phrase_matcher_attr="LOWER"` e `overwrite_ents=True`
- Entidades reconhecidas: `DOENCA`, `SINTOMA`, `MUNICIPIO`
- Cobertura geográfica: 221 municípios do Piauí (fonte: IBGE)

### Doenças monitoradas
- Dengue (variantes: "dengue grave", "dengue com sinais de alarme", "arbovirose dengue")
- Zika (variantes: "vírus zika", "febre do zika")
- Chikungunya (variantes: "febre chikungunya", "chikungunha")

### Heurística de extração
- Unidade de processamento: **sentença** (spaCy sentence segmentation)
- Regra de co-ocorrência: `DOENCA` + `MUNICIPIO` na **mesma sentença** → gera `MencaoExtraida`
- Produto cartesiano: se há N doenças e M municípios na mesma sentença, gera N×M menções
- Deduplicação: por `(doenca, municipio, sentenca)` dentro de cada notícia

### Pontuação de confiança
- Base: 0,62
- +0,18 se há pelo menos um sintoma na sentença
- +0,08 se há ≥2 sintomas na sentença
- +0,08 se o título contém termo epidemiológico
- Máximo: 0,96
- **Observação:** o corpus de texto_reserva não contém descrições de sintomas na maioria dos artigos, então a maior parte das menções fica com confiança = 0,70 (base + título).

---

## 4. Gold Standard — construção e critérios

### Arquivo
- **Localização:** `dados/gold_standard/gold_standard.json`
- **Tamanho:** 87 menções corretas anotadas manualmente nos 35 artigos
- **Unidade de anotação:** par `(doença, município)` por artigo — sem duplicatas por artigo

### Critérios de anotação (registro formal)
1. **Menção válida:** doença arbovirose (Dengue/Zika/Chikungunya) associada a município piauiense com presença confirmada ou suspeita da doença — casos, óbitos, estado de alerta, risco de infestação.
2. **Menção negativa → inválida:** artigo que informa explicitamente a **ausência** da doença no município não gera menção válida.
3. **Menção geográfica → inválida:** município citado apenas como referência espacial (ex.: "600 km de Teresina") não gera menção válida.
4. **Artigos de vacinação → válidos:** menção de município + doença em contexto de vacinação conta como dado epidemiológico relevante.
5. **Nível estadual → inválido:** menções genéricas ao "Piauí" sem município específico não contam (Piauí não é um município no índice).

### Distribuição do gold standard
- Artigos com pelo menos uma menção: 22 de 35
- Artigos sem menções válidas: 13 de 35
- Menções por doença: Dengue = 83, Chikungunya = 4, Zika = 0
- **Zika:** presente em vários artigos, mas apenas em nível estadual — nenhum município específico associado no corpus.

---

## 5. Resultados da avaliação NER (dados de pesquisa)

### Configuração da avaliação
- **Script:** `scripts/avaliar_ner.py`
- **Entrada sistema:** 35 artigos com `texto_reserva` como texto
- **Comparação:** (noticia_id, doenca, municipio) deduplicado por artigo
- **Gold standard:** 87 pares anotados manualmente

### Métricas obtidas

| Entidade | TP | FP | FN | Precisão | Recall | F1 |
|---|---|---|---|---|---|---|
| Dengue | 33 | 2 | 50 | 94,3% | 39,8% | 55,9% |
| Chikungunya | 4 | 0 | 0 | 100,0% | 100,0% | 100,0% |
| Zika | 0 | 0 | 0 | N/A | N/A | N/A |
| **Geral** | **37** | **2** | **50** | **94,9%** | **42,5%** | **58,7%** |

### Interpretação dos resultados

**Precisão alta (94,9%):** o pipeline é conservador — quando extrai, quase sempre acerta. Os 2 falsos positivos têm causas distintas e analiticamente interessantes:
1. **(Dengue, Picos)** — artigo 16: "Picos ainda não registrou casos de dengue em 2024". O sistema extraiu a co-ocorrência mas não distingue negação. Limitação semântica clássica de sistemas baseados em regras.
2. **(Dengue, Teresina)** — artigo 18: "óbito em Bom Jesus, município localizado a aproximadamente 600 km de Teresina". Teresina aparece como referência geográfica; o sistema não distingue contexto de menção.

**Recall baixo (42,5%):** 50 pares corretos não foram capturados. A causa quase exclusiva é **estrutural**: artigos que mencionam a doença em uma sentença e listam os municípios afetados em outra — padrão típico de notas de imprensa e boletins epidemiológicos. Exemplos:
- "O Piauí confirmou mais dois óbitos por dengue em 2024 [sentença 1]. Entre os municípios com mortes confirmadas estavam Teresina (3), Bom Jesus (7)... [sentença 2]"
- "...registrou aumento de dengue no Piauí [sentença 1]. O documento citou Teresina, Bom Jesus, Currais... [sentença 2]"

**F1 = 58,7%:** sintetiza o trade-off. O valor reflete que o pipeline é mais útil como filtro de alta precisão do que como cobertura exaustiva.

### Sobre Chikungunya (F1 = 100%)
Resultado perfeito deve ser lido com cautela: apenas 4 instâncias no corpus (2 artigos). Base amostral insuficiente para generalização. Nenhum caso de Zika com município específico foi encontrado no corpus 2024.

---

## 6. Limitações identificadas do pipeline

### L1 — Heurística de co-ocorrência sentencial (limitação estrutural, principal)
O sistema só extrai quando doença e município aparecem na **mesma sentença**. O padrão jornalístico/epidemiológico mais comum é mencionar a doença no início do parágrafo e listar municípios depois. Isso causa ~96% dos falsos negativos.

**Dados:** 50 de 50 FN têm essa causa.

### L2 — Ausência de reconhecimento de negação
O sistema não detecta negação semântica ("não registrou", "sem casos", "negativo para"). Causa 1 dos 2 FPs.

### L3 — Ambiguidade de referência geográfica
Municípios que aparecem como referência espacial (distância, sede de hospital, comparação regional) são extraídos como se fossem locais de ocorrência. Causa 1 dos 2 FPs.

### L4 — Divergência corpus fechado vs. texto ao vivo
O gold standard foi anotado sobre `texto_reserva` (corpus fechado). O painel ao vivo baixa artigos completos da web, que contêm mais informação. Resultado: 49 menções no painel vs. 47 no corpus fechado para o mesmo período. As métricas de P/R/F1 valem especificamente para o corpus fechado.

### L5 — Zika sub-representada
Nenhum artigo do corpus 2024 associou Zika a um município específico. Impossível avaliar a cobertura do pipeline para Zika.

### L6 — Viés de cobertura das fontes
O corpus privilegia Cidade Verde (18/35 artigos). Fontes como Portal O Dia, A10+ e Portal B1 têm representação mínima (1 artigo cada). Resultados podem não ser generalizáveis a outras fontes.

### L7 — Confiança sub-ótima sem sintomas
A maioria das menções fica com confiança = 0,70 porque o corpus de texto_reserva não descreve sintomas. No corpus ao vivo, artigos com sintomas descritos pontuariam mais alto (até 0,96).

---

## 7. Observações sobre o painel (instrumento de investigação)

### Estado do banco de dados
- A tabela é `mencoes` (não `mencoes_extraidas` — atenção ao código).
- Banco com 19 artigos e 35 menções = estado anterior à expansão do corpus.
- Após expansão do corpus e re-execução: 17 notícias com menções, 49 menções totais (data range Jan–Ago 2024).

### Divergência banco × corpus fechado (nota metodológica — CORRIGIDA)
- **49 menções no painel** vs. **47 do corpus fechado puro** (texto_reserva).
- As 49 menções foram obtidas com `python scripts/executar_pipeline.py --modo reais`, que chama `ColetorNoticiasSemeadas().coletar()`.
- `ColetorNoticiasSemeadas` NÃO é coleta puramente ao vivo: **tenta baixar a URL real**, mas **cai para `texto_reserva`** se o download falhar (timeout, HTML insuficiente, URL mudada, etc.).
- Resultado: corpus **misto** — alguns artigos com texto real baixado na data da execução, outros com texto_reserva como fallback. Não é possível saber exatamente quais sem inspecionar o campo `bruto.reserva_usada` do banco.
- A pequena diferença (49 vs. 47 menções raw) provavelmente vem de 1–2 artigos que foram baixados com sucesso e continham mais texto do que o texto_reserva.
- **Implicação para TCC:** as métricas de P/R/F1 (94,9%/42,5%/58,7%) foram calculadas sobre corpus **exclusivamente texto_reserva** via `scripts/avaliar_ner.py` — isso é o gold standard. O número "49 menções" do painel reflete o modo operacional normal do sistema (download + fallback) e NÃO é diretamente comparável com as métricas de avaliação.

### Comportamento da linha temporal
- A linha temporal exibe corretamente o padrão sazonal de dengue 2024: crescimento Jan–Mar, pico em torno de Mar–Abr, queda posterior.
- Chikungunya aparece com intensidade menor e com pico deslocado (Aug 2024).
- Esse padrão é coerente com os dados epidemiológicos reais do Piauí.

---

## 8. Dados epidemiológicos do corpus (para contextualização da monografia)

### Dengue no Piauí — 2024 (extraído dos artigos do corpus)
- **Redução relativa no início:** -33% nas primeiras 4 semanas vs. mesmo período de 2023.
- **Crescimento posterior:** +91,5% de casos em comparação com 2023 ao longo do ano.
- **Municípios com mais casos prováveis (SE1–SE4/2024):** Teresina, Currais, Bom Jesus, Ribeiro Gonçalves, Parnaíba.
- **Municípios com mais casos prováveis (SE12/2024):** Teresina, Bom Jesus, Currais, Parnaíba, Guadalupe.
- **Óbitos confirmados 2024:** 21 mortes — maior número da última década no estado.
- **Municípios com óbitos:** Bom Jesus (7 óbitos — maior número), Teresina (3), Baixa Grande do Ribeiro (2), Esperantina (2), Floriano, Jerumenha, João Costa, Manoel Emídio, São João do Piauí, José de Freitas.
- **Primeira morte:** Bom Jesus, março de 2024.

### Chikungunya e LIRAa
- LIRAa/LIA fase 3 de 2024: 29 municípios em alerta; Alagoinha do Piauí e Morro Cabeça no Tempo com situação de risco (infestação ≥ 4%).
- 190 de 221 municípios atingiram nível satisfatório de controle vetorial.

### Vacina Butantan (Jan/2024 — evento de contexto)
- MS suspendeu preventivamente a vacina Butantan após 42 reações severas e 2 mortes suspeitas.
- Em Teresina: ~2.800 doses recebidas, ~2.300 aplicadas, ~500 recolhidas. Sem complicações nos vacinados locais.
- FMS aguardou nota técnica do MS; Sesapi orientou municípios sobre o recolhimento.

---

## 9. Divergências identificadas entre pré-TCC e estado atual do projeto

(Identificadas na análise do documento pré-TCC enviado)

1. **Twitter/X não implementado** → reconhecer na metodologia; ajustar trecho que citava como fonte prevista.
2. **Coleta ativa → corpus fechado** → reframing metodológico necessário: explicar como escolha deliberada de controle (veja seção 2).
3. **MVP como produto → MVP como instrumento** → rever linguagem em todo o texto; substituir "sistema", "ferramenta", "produto" por "instrumento de pesquisa", "protótipo metodológico".
4. **Gold Standard descrito mas não implementado** → agora implementado; atualizar seção de metodologia com os dados reais.
5. **Cronograma Jan–Jun/2026** → verificar e atualizar.
6. **Erros tipográficos:** "pelo autro" → "pelo autor"; "em peródos" → "em períodos".

---

## 10. Próximos passos para a monografia

### Imediatos
- [ ] Redigir seção de Metodologia com os dados do gold standard e critérios de anotação (seções 4 e 5 acima são a base).
- [ ] Redigir seção de Resultados com a tabela de P/R/F1 e a análise por tipo de erro.
- [ ] Redigir seção de Discussão com as limitações L1–L7 acima.

### Médio prazo
- [ ] Reescrever seção de Introdução/Fundamentação reorientando o vocabulário (instrumento vs. produto).
- [ ] Atualizar cronograma.
- [ ] Corrigir erros tipográficos listados na seção 9.
- [ ] Inserir contextualização epidemiológica do surto 2024 (seção 8 fornece os dados).

---

*Arquivo mantido como registro de pesquisa. Atualizar após cada sessão de trabalho relevante.*
