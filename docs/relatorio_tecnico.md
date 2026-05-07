# Relatório Técnico do Protótipo

## Decisões de implementação

O EpiPiaui Monitor foi estruturado como um MVP reprodutível. A coleta, o processamento e a visualização são etapas separadas para facilitar auditoria e repetição dos experimentos.

Na versão atual, o modo principal (`reais`) usa um conjunto de URLs reais localizadas em fontes piauienses entre janeiro e julho de 2024. As sementes ficam em `dados/brutos/sementes_noticias_reais_2024.json`.

O banco SQLite foi escolhido por ser leve, portátil e suficiente para a prova de conceito. O material bruto fica na tabela `noticias`, enquanto as inferências ficam na tabela `mencoes`.

Para PLN, o pipeline usa spaCy com `EntityRuler`. O modelo recomendado é `pt_core_news_lg`, mas há reserva para modelos menores ou para um pipeline básico em português. Essa decisão permite que a demonstração funcione mesmo em ambientes sem o modelo grande instalado.

## Heurística de extração

O protótipo considera uma menção válida quando uma doença e um município aparecem na mesma sentença. Sintomas na mesma sentença elevam a confiança. A presença de termo epidemiológico no título também aumenta levemente a pontuação.

Essa escolha privilegia explicabilidade: cada registro extraído preserva a sentença original, permitindo revisão manual.

## Dificuldades encontradas

- Portais de notícia podem mudar HTML, URLs, paginação e metadados sem aviso.
- O Cidade Verde retornou bloqueio Cloudflare 403 em parte das tentativas de coleta automatizada; nesses casos, o protótipo preserva a URL e usa texto curto de apoio marcado como reserva.
- Nem toda página pública expõe data de publicação em formato padronizado.
- Nomes de municípios podem aparecer com ou sem acento, exigindo normalização.
- Ambiguidade textual: uma notícia pode citar vários municípios e várias doenças sem afirmar relação epidemiológica direta.
- Dados de notícias não equivalem a notificações oficiais de saúde.

## Limites deliberados

- O MVP não realiza coleta contínua.
- O período-alvo documentado é janeiro a julho de 2024.
- O painel é exploratório e não deve ser usado como sistema oficial.
- A amostra sintética permanece apenas como reserva didática; o fluxo padrão usa notícias e informes reais de 2024.

## Possíveis melhorias

- Adicionar validação manual de menções no painel.
- Persistir HTML bruto além do texto extraído.
- Incorporar classificação supervisionada para reduzir falso positivo.
- Criar testes automatizados com páginas HTML congeladas.
- Publicar um relatório de avaliação com precisão, revocação e exemplos anotados.
