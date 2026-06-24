# Registro de Alterações — Revisão de Consistência

**Data:** 2026-06-20
**Responsável:** revisão automatizada solicitada pelo autor (Pedro Lucas Alves de Assis Cardoso)
**Escopo:** correção de inconsistências entre código e documentação identificadas em uma varredura completa do projeto. Nenhuma mudança altera o comportamento do pipeline nem os resultados de pesquisa (P/R/F1); são correções de documentação e duas pequenas correções de código sem efeito sobre a saída.

---

## Resumo

| # | Alteração | Tipo | Arquivos |
|---|-----------|------|----------|
| 1 | Fórmula de confiança documentada agora reflete o código real | Doc | `interface/painel.py`, `docs/relatorio_tecnico.md` |
| 2 | Quarta fonte de coleta (Meio News) passa a constar na documentação | Doc | `README.md`, `docs/spec.md`, `docs/relatorio_tecnico.md`, `interface/painel.py` |
| 3 | Período de cobertura corrigido de "janeiro a julho" para "janeiro a dezembro" de 2024 | Doc | `README.md`, `interface/painel.py`, `docs/relatorio_tecnico.md`, `docs/fontes_reais_2024.md`, `notebooks/01_fluxo_prototipo.ipynb` |
| 4 | Versão mínima de Python padronizada em 3.11+ | Doc | `README.md`, `docs/spec.md` |
| 5 | Substituição de `datetime.utcnow()` (depreciado) por `datetime.now(timezone.utc)` | Código | `src/epipiaui_monitor/modelos.py` |
| 6 | Contagem de municípios padronizada em 224 (e fallback offline completado) | Doc + Código | `docs/spec.md`, `notas_tcc.md`, `src/epipiaui_monitor/piaui.py` |

Total: **9 arquivos**, **21 edições**. Suíte de testes após as mudanças: **59/59 aprovados**.

---

## Detalhamento

### 1. Fórmula de confiança (documentação divergia do código)

O cálculo real está em `src/epipiaui_monitor/pln/processador.py` (`_calcular_confianca`):
base **0.62**, **+0.18** se há ≥1 sintoma na sentença, **+0.08** se há ≥2 sintomas,
**+0.08** se o título contém termo epidemiológico, teto **0.96**.

A documentação descrevia uma fórmula antiga (base 0.6, +0.1, +0.1, teto 0.8), que não
existe mais no código. Corrigido em dois lugares:

- `interface/painel.py` — aba **Sobre** → expander "Como interpretar a 'Confiança'?".
- `docs/relatorio_tecnico.md` — seção 4, item "Cálculo de Confiança".

Acrescentada a observação de que, no corpus fechado, a maioria das menções fica em
**0.70** (base + título), porque os textos de reserva raramente descrevem sintomas.

### 2. Quarta fonte de coleta (Meio News)

`src/epipiaui_monitor/configuracao.py` (`FONTES_NOTICIAS`) configura **quatro** fontes
para a coleta ao vivo — G1 Piauí, Cidade Verde, SESAPI e **Meio News** —, mas a
documentação citava apenas três. Meio News foi adicionado às listas de fontes em
`README.md`, `docs/spec.md` (RF01), `docs/relatorio_tecnico.md` (diagrama de
arquitetura) e `interface/painel.py` (FAQ "Como os dados são coletados?").

> Observação: o `buscar_sementes_2024.py` (construtor do corpus fechado) usa um conjunto
> próprio de três fontes; a documentação que descreve **esse** script (em
> `docs/manual_resumido.md`) está correta e não foi alterada.

### 3. Período de cobertura dos dados

O banco e o corpus cobrem **janeiro a dezembro de 2024** (datas no SQLite: 2024-01-01 a
2024-12-10; corpus com os 12 meses, conforme `notas_tcc.md`). A documentação dizia
"janeiro a julho de 2024". Corrigido em todos os textos voltados ao leitor.

### 4. Versão mínima de Python

`pyproject.toml` exige `requires-python = ">=3.11"` e o painel já exibia "Python 3.11",
mas `README.md` e `docs/spec.md` diziam "3.10+". Padronizado em **3.11+**, alinhando à
configuração de build (fonte da verdade).

> Alternativa, caso se deseje suportar 3.10 oficialmente (a suíte de testes roda sem erros
> em 3.10): rebaixar `pyproject.toml` para `>=3.10` e ajustar o painel — em vez de subir os
> textos para 3.11+.

### 5. `datetime.utcnow()` depreciado

`src/epipiaui_monitor/modelos.py` usava `datetime.utcnow()`, que emite
`DeprecationWarning` no Python 3.12+. Substituído por
`datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"`.
A saída é idêntica à anterior (ex.: `2026-06-20T19:11:32Z`) — verificado
programaticamente — então não há impacto em dados gravados nem nos testes.

### 6. Contagem de municípios padronizada em 224

Investigada a divergência 221 × 223 × 224. **224 é o valor correto** (total oficial do
IBGE e exatamente o que o código carrega em produção via
`dados/processados/municipios_piaui.json`); os outros dois eram erros distintos:

- **223** — a lista de reserva `MUNICIPIOS_RESERVA` (`piaui.py`, fallback usado só offline)
  havia omitido **um** município, **Agricolândia** (cód. `2200103`), pulado na digitação
  manual da lista. Foi inserido na posição correta; a reserva passou a ter 224 e bate 1:1
  com o cache do IBGE (verificado por diff de IDs — nenhum faltando, nenhum extra). As
  diferenças de acento na reserva (Acaua, Agua Branca…) são propositais — o código
  normaliza com `unidecode` — e foram mantidas.
- **221** — origem rastreada à estatística do LIRAa nas notas (`notas_tcc.md` linha 202:
  "190 de 221 municípios…"), que cobre apenas os municípios do ciclo de levantamento, não
  o total do estado. Esse número havia sido carregado para a linha de "cobertura
  geográfica (fonte: IBGE)" como se fosse o total. Corrigido para 224 em `docs/spec.md` e
  em `notas_tcc.md` (linha 56). **A linha 202 (estatística real do LIRAa) foi mantida**,
  pois 221 está correto naquele contexto.

---

## Verificação

- `python -m pytest tests/ -q` → **59 passed**.
- Formato de `agora_utc_iso()` conferido por regex `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z`.
- As métricas de pesquisa (P 94,9% / R 42,5% / F1 58,7%) **não** foram afetadas: nenhuma
  mudança toca o pipeline de PLN, o corpus ou o gold standard.

> Nota: no ambiente de verificação o spaCy não estava instalado, então os 20 testes de PLN
> exercitaram o caminho de *fallback* por regex. Recomenda-se rodar a suíte localmente com
> `pt_core_news_lg` instalado para cobrir o caminho principal.

---

## Achados adicionais (NÃO alterados — aguardando decisão do autor)

1. **Contagem de municípios (divergência 221 × 223 × 224) — RESOLVIDO em 2026-06-20.**
   Padronizado em **224**; ver a seção "6. Contagem de municípios padronizada em 224"
   acima para o diagnóstico completo da origem de cada número.

2. **`src/epipiaui_monitor.egg-info/PKG-INFO`** ainda mostra os textos antigos
   ("janeiro a julho", "3.10+"). É um arquivo **gerado automaticamente** a partir do
   README/pyproject; será regenerado em `pip install -e .`. Não requer edição manual.

3. **Nome de tabela na documentação** (`docs/manual_resumido.md`, diagrama de sequência):
   referência a `mencoes_extraidas`, enquanto a tabela real é `mencoes`. Já registrado pelo
   autor em `notas_tcc.md`; deixado para correção conjunta com a monografia.

---

## Arquivos tocados

```
interface/painel.py
src/epipiaui_monitor/modelos.py
src/epipiaui_monitor/piaui.py
README.md
docs/spec.md
notas_tcc.md
docs/relatorio_tecnico.md
docs/fontes_reais_2024.md
notebooks/01_fluxo_prototipo.ipynb
docs/alteracoes_2026-06-20.md   (este arquivo)
```
