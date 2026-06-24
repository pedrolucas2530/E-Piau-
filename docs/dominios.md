# Domínios de investigação configuráveis

O motor de extração do EpiPiauí Monitor é, por dentro, genérico: ele correlaciona,
por **co-ocorrência em uma mesma sentença**, uma entidade de **tema** com um
**município** do Piauí. O município é o eixo geográfico fixo (lista oficial do
IBGE, ver `piaui.py`); apenas a dimensão temática é configurável.

A mesma ferramenta pode, assim, investigar outros temas além de arboviroses — por
exemplo, criminalidade (crime × município) ou mortalidade (óbito × município) — sem
alterar uma linha de código: basta trocar o arquivo de domínio. O painel (gráficos
e mapa) já renderiza, por município, qualquer tema processado.

## O que é um domínio

Um domínio é um arquivo JSON em `config/dominios/`. Campos:

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `nome` | sim | Nome legível do domínio. |
| `rotulo_tema` | sim | Rótulo do tema, exibido no painel (ex.: "Doença", "Crime"). |
| `rotulo_tema_plural` | não | Plural do rótulo (ex.: "Doenças"). Padrão: "Categorias". |
| `categorias` | sim | Dicionário `categoria → [variantes de texto]`. É o que o NER reconhece. |
| `rotulo_auxiliar` | não | Rótulo do vocabulário auxiliar (ex.: "Sintomas", "Indicadores"). |
| `termos_auxiliares` | não | Termos que, se presentes na sentença, elevam o escore de confiança. |
| `palavras_chave_coleta` | não | Palavras-chave para filtrar matérias na coleta. |

O município **não** aparece no domínio: ele é sempre uma das pontas da relação.

## Domínios disponíveis

- `config/dominios/arboviroses.json` — **padrão**. Reproduz exatamente o
  comportamento histórico do projeto (Dengue, Zika, Chikungunya + sintomas). É o
  domínio usado em toda a pesquisa e na avaliação (gold standard).
- `config/dominios/criminalidade.json` — **exemplo** ilustrativo (homicídio,
  roubo, furto, tráfico, feminicídio) para demonstrar a troca de tema.

## Como trocar de tema

Reprocessar o banco com outro domínio (popula as menções que o painel desenha no
mapa e nos gráficos):

```powershell
python scripts/processar.py --dominio config/dominios/criminalidade.json
```

Fazer o painel exibir os rótulos do tema escolhido (variável de ambiente):

```powershell
$env:EPIPIAUI_DOMINIO = "config/dominios/criminalidade.json"
streamlit run interface/painel.py
```

Sem a flag/variável, usa-se o domínio padrão (arboviroses). No código:

```python
from epipiaui_monitor.pln.processador import EpiPiauiPLN

pln = EpiPiauiPLN()  # arboviroses (padrão)
pln = EpiPiauiPLN(caminho_dominio="config/dominios/criminalidade.json")
```

## Como criar um novo domínio

1. Copie um JSON existente em `config/dominios/`.
2. Ajuste `rotulo_tema` e `categorias` para o seu tema.
3. (Opcional) Ajuste `termos_auxiliares` e `palavras_chave_coleta`.
4. Reprocesse com `--dominio caminho/do/seu.json` e aponte `EPIPIAUI_DOMINIO` para ele.

Se o arquivo estiver ausente ou malformado, o sistema recai automaticamente no
domínio de reserva (arboviroses), no mesmo espírito de tolerância a falhas já
usado para a lista de municípios.

## Pontos de extensão (brechas para a busca-no-mapa)

O objetivo futuro é permitir que o usuário digite um termo **no painel** e veja a
correlação termo × município no **mapa e nos gráficos**, com coleta ao vivo. O
ambiente já está preparado para isso; os ganchos existentes são:

1. `dominio.dominio_de_termos(termos)` — transforma termo(s) digitado(s) em um
   `DominioInvestigacao` na hora (cada termo vira uma categoria).
2. `dominio.termos_de_texto(texto)` — divide a string digitada em lista de termos.
3. `ColetorNoticias(palavras_chave=...)` — coleta ao vivo filtrando por termos
   arbitrários (parâmetro opcional; sem ele, o comportamento padrão é mantido).
4. Painel parametrizado por `EPIPIAUI_DOMINIO` / `carregar_dominio(caminho)` —
   troca rótulos, gráficos e mapa conforme o domínio.

Roteiro sugerido para implementar a busca-no-mapa (sem refatoração grande):

1. Adicionar um campo de texto no painel (`st.text_input`) para o termo.
2. Montar o domínio: `dominio_de_termos(termos_de_texto(entrada))`.
3. Obter as notícias: reusar o banco **ou** coletar ao vivo com
   `ColetorNoticias(palavras_chave=...).coletar(...)`.
4. Extrair: `EpiPiauiPLN(dominio=...).processar_noticias(...)`.
5. Desenhar no mapa/gráficos já existentes (operam por `codigo_municipio` e pela
   coluna de tema), preferencialmente sobre um `DataFrame` em memória, **sem**
   sobrescrever as menções persistidas do domínio principal.

Costuras que faltam para a generalização total (intencionalmente não alteradas
agora, para não mexer demais no código):

- As colunas do banco chamam-se `doenca` e `sintomas_json` (semanticamente "tema"
  e "auxiliares"); renomear exigiria migração do esquema — mantidas por
  compatibilidade com os dados e a avaliação da pesquisa.
- A aba "Sobre" do painel contém texto específico de arboviroses.
- A coleta ao vivo depende da estrutura dos portais e pode ser bloqueada (é a
  parte menos estável do sistema).

## Ressalva metodológica

A flexibilidade é uma propriedade **de projeto** do artefato: a arquitetura
suporta outros temas. Isso **não** equivale a uma validação empírica para esses
outros temas. As métricas de precisão, revocação e F1 reportadas na pesquisa
foram medidas exclusivamente para o domínio de arboviroses, contra um gold
standard específico. Investigar um novo tema com rigor exigiria construir um
novo conjunto de referência para ele.
