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
- Cobertura geográfica: 224 municípios do Piauí (fonte: IBGE)

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

### L8 — Extensibilidade limitada (valores hardcoded)
Documentado pelo próprio `docs/manual_resumido.md`: as listas de doenças/palavras-chave (`PALAVRAS_CHAVE` em `buscar_sementes_2024.py`; `PADROES_DOENCAS`, `PADROES_SINTOMAS` em `processador.py`) e a lista de municípios (`MUNICIPIOS_RESERVA` em `piaui.py`) são constantes fixas no código, não configuráveis externamente. O pipeline está acoplado ao recorte Piauí + 3 arboviroses; generalizar para outro estado ou doença exigiria alteração de código-fonte, não apenas configuração.

**Nota documental adicional:** `docs/manual_resumido.md` (linha 70, diagrama sequenceDiagram) descreve a etapa final de processamento como gravando na tabela `mencoes_extraidas` — nome incorreto; a tabela real é `mencoes` (confirmado por consulta direta ao SQLite, ver seção 7). Indica inconsistência de nomenclatura entre a documentação técnica do projeto e o código-fonte, não apenas um erro pontual meu na primeira versão do script de avaliação.

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

## 8.1 Inventário da pasta — revisão de arquivos não analisados anteriormente

(Revisão feita em 2026-06-20, em resposta a pedido de reanálise da pasta)

### Mudanças "modificadas" no git são cosméticas
`docs/spec.md`, `docs/manual_resumido.md`, `tests/test_pln.py`, `tests/test_utilitarios.py`, `tests/__init__.py`, `tests/README.md`, `dados/brutos/amostra_noticias.json` e `dados/brutos/sementes_noticias_reais_2024.backup.json` aparecem como modificados no `git status`, mas `git diff --ignore-all-space` retorna vazio para todos — são apenas normalização de quebra de linha (CRLF/LF), sem mudança de conteúdo.

### `docs/spec.md` já incorpora os resultados do gold standard
O PRD do projeto já cita textualmente os números da avaliação NER que produzi: "A regra rígida de 'co-ocorrência na mesma sentença' garante altíssima Precisão (94.9%), mas prejudica consideravelmente o Recall (42.5%)". Útil para a monografia: mostra que a documentação do projeto já reflete a investigação empírica.

### `buscar_sementes_2024.py` (script raiz, já versionado)
Script responsável por expandir o corpus fechado de 19 para 35 artigos. Varre RSS do G1 + páginas do Cidade Verde e SESAPI, filtra por palavras-chave de arbovirose (dengue/zika/chikungunya/arbovirose/aedes) exigindo match no título ou URL, tenta baixar HTML real para gerar `texto_reserva`, e grava com backup automático. Relevante para a seção de Metodologia (descreve precisamente como o corpus fechado foi construído).

### `docs/fontes_reais_2024.md` — registro das fontes reais
Lista as URLs reais usadas no corpus, por fonte (G1, SESAPI, Cidade Verde). Contém uma observação metodológica importante: **"durante a execução local, o domínio cidadeverde.com pode retornar Cloudflare 403 para coleta automatizada. O pipeline preserva as URLs e marca esses registros com `reserva_usada=true` quando não consegue baixar o HTML original."** Isso é evidência documental direta da divergência banco × corpus fechado já registrada na seção 7 — Cidade Verde é a fonte majoritária do corpus (18/35) e é justamente a que mais sofre bloqueio, o que explica por que o modo `--modo reais` cai com frequência para `texto_reserva`.

### `docs/relatorio_tecnico.md` — diagramas de arquitetura (mermaid)
Contém dois diagramas mermaid: (1) arquitetura geral do pipeline (Fontes → Coleta → Armazenamento → PLN → Extração → Banco → Dashboard) e (2) fluxograma do processamento PLN sentença por sentença (doença? → município? → entity ruler → heurística de co-ocorrência → confiança → MencaoExtraida). Úteis como figuras na seção de Metodologia/Arquitetura da monografia.

### `notebooks/01_fluxo_prototipo.ipynb` e `02_avaliacao_ner.ipynb`
- **01**: notebook simples (6 células) demonstrando o fluxo coleta → PLN, sem avaliação.
- **02 — IMPORTANTE, é um rascunho anterior e SUPERADO pelo gold standard atual.** Modificado em 08/05/2026 (anterior à construção do gold standard de 35 artigos/87 menções desta sessão). Usa um "Gold Standard" diferente: apenas **10 notícias sintéticas escritas à mão** (não do corpus real), com avaliação **no nível de entidade** (DOENCA/MUNICIPIO/SINTOMA isolados, por igualdade de string) — não no nível de relação (par doença×município) como o `avaliar_ner.py` atual. **O notebook nunca foi executado**: todas as 7 células de código têm `execution_count: None` e zero outputs salvos. Conclusão: é um protótipo de exploração, não um resultado válido. Não deve ser citado como avaliação na monografia — o gold standard de referência é exclusivamente `dados/gold_standard/gold_standard.json` + `scripts/avaliar_ner.py`. Vale mencionar na monografia como iteração metodológica anterior (mostra evolução do desenho de avaliação: de nível de entidade/amostra sintética para nível de relação/corpus real).

### Arquivos sem relevância para a monografia
- `dados/.fuse_hidden0000001000000001/2/3`: artefatos temporários do sistema de arquivos (FUSE), gerados por acesso concorrente ao diretório montado. Não são dados do projeto; seguros para ignorar/excluir.
- `dados/brutos/ao_vivo_2026-*.json` (6 arquivos, 1–2 KB cada): capturas de teste do modo `ao-vivo` puro. Conteúdo majoritariamente ruído — ex.: uma página de rodapé do Cidade Verde sobre Ebola/manguezais, uma coluna de "Naldo Pereira" sem relação com arbovirose. **Achado útil para a monografia:** ilustra concretamente por que a coleta ao vivo pura foi descartada como prioridade — o scraping irrestrito captura muito conteúdo fora do escopo epidemiológico, reforçando a justificativa do corpus fechado curado (seção 2).

### Conclusão da revisão
Nenhum arquivo novo não-versionado foi encontrado — todos os itens acima já estavam commitados no histórico do git (commits anteriores a esta sessão), apenas não haviam sido revisados por mim. Não há, portanto, trabalho recente de terceiros a reconciliar; o que havia era documentação e scripts de suporte ao corpus que ainda não tinham sido conectados explicitamente às notas de pesquisa.

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
