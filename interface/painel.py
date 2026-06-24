from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import folium
import pandas as pd
import requests
import streamlit as st
from branca.colormap import linear
from streamlit_folium import st_folium

try:
    import plotly.express as px
except ImportError:
    px = None

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epipiaui_monitor.banco import carregar_mencoes, carregar_noticias
from epipiaui_monitor.configuracao import (
    CAMINHO_BANCO_PADRAO,
    DIR_DADOS_PROCESSADOS,
    URL_GEOJSON_IBGE,
)
from epipiaui_monitor.dominio import carregar_dominio


CACHE_GEOJSON = DIR_DADOS_PROCESSADOS / "piaui_municipios.geojson"

# Rótulos da aba de análise seguem o domínio configurado (tema investigado).
# Brecha: defina a variável de ambiente EPIPIAUI_DOMINIO=caminho/para/dominio.json
# antes de iniciar o painel para investigar outro tema — rótulos, gráficos e mapa
# se ajustam automaticamente ao domínio escolhido.
DOMINIO = carregar_dominio(os.environ.get("EPIPIAUI_DOMINIO") or None)


st.set_page_config(
    page_title="EpiPiaui Monitor",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def ler_dados_painel(
    caminho_banco: str,
    modificacao_banco: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    caminho = Path(caminho_banco)
    if not caminho.exists():
        return pd.DataFrame(), pd.DataFrame()
    try:
        noticias = carregar_noticias(caminho)
        mencoes = carregar_mencoes(caminho)
    except Exception:
        return pd.DataFrame(), pd.DataFrame()
    if not mencoes.empty:
        mencoes["data_publicacao"] = pd.to_datetime(
            mencoes["data_publicacao"],
            errors="coerce",
        )
        mencoes["mes"] = mencoes["data_publicacao"].dt.to_period("M").astype(str)
    return noticias, mencoes


@st.cache_data(show_spinner=False)
def carregar_geojson_piaui() -> dict | None:
    DIR_DADOS_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    if CACHE_GEOJSON.exists():
        return json.loads(CACHE_GEOJSON.read_text(encoding="utf-8"))
    try:
        resposta = requests.get(URL_GEOJSON_IBGE, timeout=30)
        resposta.raise_for_status()
        geojson = resposta.json()
        CACHE_GEOJSON.write_text(
            json.dumps(geojson, ensure_ascii=False),
            encoding="utf-8",
        )
        return geojson
    except (requests.RequestException, ValueError):
        return None


def normalizar_geojson(geojson: dict, contagens: dict[str, int]) -> dict:
    normalizado = copy.deepcopy(geojson)
    for feicao in normalizado.get("features", []):
        propriedades = feicao.setdefault("properties", {})
        codigo = str(
            propriedades.get("codarea")
            or propriedades.get("CD_MUN")
            or propriedades.get("id")
            or propriedades.get("geocodigo")
            or ""
        )
        nome = str(
            propriedades.get("name")
            or propriedades.get("nome")
            or propriedades.get("NM_MUN")
            or propriedades.get("municipio")
            or codigo
        )
        propriedades["codigo_epi"] = codigo
        propriedades["nome_epi"] = nome
        propriedades["mencoes_epi"] = int(contagens.get(codigo, 0))
    return normalizado


def construir_mapa(mencoes_filtradas: pd.DataFrame) -> folium.Map:
    contagens = (
        mencoes_filtradas.groupby("codigo_municipio")
        .size()
        .rename("mencoes")
        .to_dict()
        if not mencoes_filtradas.empty
        else {}
    )
    geojson = carregar_geojson_piaui()
    mapa = folium.Map(location=[-7.0, -42.0], zoom_start=6, tiles="cartodbpositron")

    if not geojson:
        folium.Marker(
            location=[-5.09, -42.8],
            tooltip="GeoJSON do IBGE indisponível no momento",
        ).add_to(mapa)
        return mapa

    geojson_normalizado = normalizar_geojson(geojson, contagens)
    contagem_maxima = max(contagens.values(), default=1)
    escala_cores = linear.YlOrRd_09.scale(0, contagem_maxima)
    escala_cores.caption = "Menções detectadas"

    def estilo(feicao: dict) -> dict:
        contagem = feicao["properties"].get("mencoes_epi", 0)
        preenchimento = "#f7fbff" if contagem == 0 else escala_cores(contagem)
        return {
            "fillColor": preenchimento,
            "color": "#607d8b",
            "weight": 0.6,
            "fillOpacity": 0.72 if contagem else 0.22,
        }

    folium.GeoJson(
        geojson_normalizado,
        name="Municípios do Piauí",
        style_function=estilo,
        tooltip=folium.GeoJsonTooltip(
            fields=["nome_epi", "mencoes_epi"],
            aliases=["Município", "Menções"],
            localize=True,
        ),
    ).add_to(mapa)
    escala_cores.add_to(mapa)
    return mapa


def mostrar_estado_vazio(motivo: str = "sem_dados") -> None:
    """Exibe mensagem de estado vazio com orientação específica ao motivo.

    motivos possíveis:
      "sem_banco"       — arquivo SQLite não existe ainda
      "sem_noticias"    — banco existe mas tabela noticias está vazia
      "sem_mencoes"     — notícias coletadas mas PLN ainda não foi executado
      "sem_dados"       — fallback genérico
    """
    st.title("EpiPiaui Monitor")

    if motivo == "sem_banco":
        st.warning("### Banco de dados não encontrado")
        st.write(
            "O arquivo SQLite ainda não foi criado. "
            "Execute o pipeline completo para gerar os dados:"
        )
        st.code("python scripts/executar_pipeline.py --modo reais", language="bash")

    elif motivo == "sem_noticias":
        st.warning("### Nenhuma notícia coletada")
        st.write("O banco existe mas está vazio. Colete notícias com:")
        st.code("python scripts/coletar.py --modo reais", language="bash")
        st.write("Em seguida processe com:")
        st.code("python scripts/processar.py", language="bash")

    elif motivo == "sem_mencoes":
        st.info("### Notícias coletadas — processamento PLN pendente")
        st.write(
            "Existem notícias no banco, mas as menções ainda não foram extraídas. "
            "Execute:"
        )
        st.code("python scripts/processar.py", language="bash")
        st.write("Ou faça coleta + processamento de uma vez:")
        st.code("python scripts/executar_pipeline.py --modo reais", language="bash")

    else:
        st.info(
            "Nenhum dado processado foi encontrado. Execute o pipeline e recarregue:"
        )
        st.code("python scripts/executar_pipeline.py --modo reais", language="bash")

    with st.expander("ℹ️ Primeiros passos"):
        st.markdown("""
**Fluxo completo do zero:**

```bash
# 1. Ativar ambiente virtual
.venv\\Scripts\\Activate.ps1

# 2. Coletar + processar em um comando
python scripts/executar_pipeline.py --modo reais

# 3. Abrir o painel
streamlit run interface/painel.py
```

O banco SQLite fica em `dados/epipiaui_monitor.sqlite`.
Para recomeçar do zero adicione `--reiniciar` ao comando de coleta.
        """)


def main() -> None:
    caminho_banco = str(CAMINHO_BANCO_PADRAO)
    banco_path = Path(caminho_banco)

    # — Banco inexistente —
    if not banco_path.exists():
        mostrar_estado_vazio("sem_banco")
        return

    modificacao_banco = banco_path.stat().st_mtime
    noticias, mencoes = ler_dados_painel(caminho_banco, modificacao_banco)

    # — Banco vazio —
    if noticias.empty:
        mostrar_estado_vazio("sem_noticias")
        return

    # — Notícias coletadas mas PLN não rodou —
    if mencoes.empty:
        mostrar_estado_vazio("sem_mencoes")
        return

    st.title("EpiPiaui Monitor")
    
    # Criar abas: Análise, Sobre e Limitações
    tab_analise, tab_sobre = st.tabs(["📊 Análise", "ℹ️ Sobre"])
    
    with tab_analise:
        with st.sidebar:
            st.header("Filtros")
            doencas = sorted(mencoes["doenca"].dropna().unique())
            doencas_selecionadas = st.multiselect(DOMINIO.rotulo_tema, doencas, default=doencas)

            fontes = sorted(mencoes["fonte"].dropna().unique())
            fontes_selecionadas = st.multiselect("Fonte", fontes, default=fontes)

            municipios = sorted(mencoes["municipio"].dropna().unique())
            busca_municipio = st.text_input(
                "🔍 Buscar município",
                placeholder="Digite para filtrar (ex: Teresina)"
            )
            if busca_municipio:
                municipios_filtrados = [
                    m for m in municipios
                    if busca_municipio.lower() in m.lower()
                ]
            else:
                municipios_filtrados = municipios
            
            municipios_selecionados = st.multiselect(
                "Município",
                municipios_filtrados,
                default=municipios_filtrados,
            )

            st.divider()
            st.subheader("Intervalo de datas")
            mencoes["data_publicacao"] = pd.to_datetime(
                mencoes["data_publicacao"],
                errors="coerce",
            )
            datas_validas = mencoes["data_publicacao"].dropna()
            if datas_validas.empty:
                # Sem nenhuma data válida: usa placeholder fixo e não filtra por data
                data_inicio = None
                data_fim = None
                st.caption("Nenhuma data válida encontrada nos dados.")
            else:
                data_min = datas_validas.min()
                data_max = datas_validas.max()
                data_inicio, data_fim = st.date_input(
                    "Selecione intervalo",
                    value=(data_min.date(), data_max.date()),
                    min_value=data_min.date(),
                    max_value=data_max.date(),
                )

            st.divider()
            confianca_minima = st.slider("Confiança mínima", 0.0, 1.0, 0.0, 0.05)

        
        mascara = (
            mencoes["doenca"].isin(doencas_selecionadas)
            & mencoes["fonte"].isin(fontes_selecionadas)
            & mencoes["municipio"].isin(municipios_selecionados)
            & (mencoes["confianca"] >= confianca_minima)
        )
        if data_inicio is not None and data_fim is not None:
            mascara &= mencoes["data_publicacao"].dt.date >= data_inicio
            mascara &= mencoes["data_publicacao"].dt.date <= data_fim

        filtradas = mencoes[mascara].copy()

        # — Sem resultados após filtros —
        if filtradas.empty:
            st.info(
                "Nenhuma menção encontrada com os filtros selecionados. "
                "Tente ampliar o intervalo de datas ou reduzir os filtros na barra lateral."
            )
            return

        metricas = st.columns(4)
        metricas[0].metric("Notícias", int(filtradas["noticia_id"].nunique()))
        metricas[1].metric("Menções", int(len(filtradas)))
        metricas[2].metric("Municípios", int(filtradas["municipio"].nunique()))
        metricas[3].metric(DOMINIO.rotulo_tema_plural, int(filtradas["doenca"].nunique()))

        coluna_mapa, coluna_graficos = st.columns([1.35, 1])
        with coluna_mapa:
            st.subheader("Mapa de menções")
            st_folium(construir_mapa(filtradas), height=540, use_container_width=True)

        with coluna_graficos:
            st.subheader(f"Distribuição por {DOMINIO.rotulo_tema.lower()}")
            contagem_doencas = (
                filtradas.groupby("doenca")
                .size()
                .reset_index(name="mencoes")
                .sort_values("mencoes", ascending=False)
            )
            if px:
                grafico_doencas = px.bar(
                    contagem_doencas,
                    x="doenca",
                    y="mencoes",
                    color="doenca",
                    labels={"doenca": DOMINIO.rotulo_tema, "mencoes": "Menções"},
                )
                grafico_doencas.update_layout(showlegend=False, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(grafico_doencas, use_container_width=True)
            else:
                st.bar_chart(contagem_doencas.set_index("doenca"))

            st.subheader("Linha temporal")
            serie_temporal = (
                filtradas.dropna(subset=["mes"])
                .groupby(["mes", "doenca"])
                .size()
                .reset_index(name="mencoes")
            )
            if px:
                grafico_tempo = px.line(
                    serie_temporal,
                    x="mes",
                    y="mencoes",
                    color="doenca",
                    markers=True,
                    labels={"mes": "Mês", "mencoes": "Menções", "doenca": DOMINIO.rotulo_tema},
                )
                grafico_tempo.update_layout(margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(grafico_tempo, use_container_width=True)
            else:
                st.line_chart(
                    serie_temporal.pivot_table(
                        index="mes",
                        columns="doenca",
                        values="mencoes",
                        aggfunc="sum",
                        fill_value=0,
                    )
                )

        st.subheader("Registros extraídos")
        tabela = filtradas[
            [
                "data_publicacao",
                "fonte",
                "titulo",
                "doenca",
                "municipio",
                "sintomas",
                "confianca",
                "sentenca",
                "url",
            ]
        ].copy()
        tabela["data_publicacao"] = tabela["data_publicacao"].dt.date.astype(str)
        tabela["sintomas"] = tabela["sintomas"].apply(lambda valores: ", ".join(valores))
        tabela = tabela.rename(
            columns={
                "data_publicacao": "Data",
                "fonte": "Fonte",
                "titulo": "Título",
                "doenca": DOMINIO.rotulo_tema,
                "municipio": "Município",
                "sintomas": "Sintomas",
                "confianca": "Confiança",
                "sentenca": "Sentença",
                "url": "URL",
            }
        )
        st.dataframe(
            tabela,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("URL"),
                "Confiança": st.column_config.ProgressColumn(
                    "Confiança",
                    min_value=0,
                    max_value=1,
                    format="%.2f",
                ),
            },
        )
    
    with tab_sobre:
        st.header("Sobre o EpiPiaui Monitor")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Objetivo")
            st.write("""
O **EpiPiaui Monitor** é um Produto Mínimo Viável (MVP) acadêmico que demonstra a aplicação prática 
de técnicas de Epidemiologia Digital no contexto do Piauí. 

Seu objetivo é validar a viabilidade técnica de um fluxo integrado de:
- Coleta de dados públicos de notícias
- Processamento de linguagem natural (PLN)
- Extração de entidades epidemiológicas
- Visualização geográfica e temporal
            """)
            
            st.subheader("Período de dados")
            st.write("""
Os dados processados cobrem o período de **janeiro a dezembro de 2024**,
com foco especial em arboviroses (Dengue, Zika, Chikungunya) no estado do Piauí.
            """)
        
        with col2:
            st.subheader("Tecnologias utilizadas")
            st.write("""
- **Python 3.11**: Linguagem de programação
- **spaCy**: Processamento de linguagem natural
- **SQLite**: Armazenamento de dados
- **Streamlit**: Interface web
- **Folium/Leaflet**: Mapas geográficos
- **Pandas**: Análise de dados
- **Plotly**: Visualizações interativas
            """)
        
        st.divider()
        st.subheader("Limitações Deliberadas")
        
        col_lim1, col_lim2 = st.columns(2)
        with col_lim1:
            st.warning("""
**NÃO é um Sistema Oficial**
- Este sistema não substitui os sistemas oficiais de vigilância epidemiológica
- Não realiza diagnóstico epidemiológico
- Não deve ser usado como fonte única de decisão em saúde pública
            """)
        
        with col_lim2:
            st.warning("""
**Escopo da Prova de Conceito**
- Utiliza dados históricos verificados de 2024
- Não realiza monitoramento contínuo
- Sujeito a variações na disponibilidade de dados em portais
- Precisão limitada pelo tratamento de linguagem natural
            """)
        
        st.divider()
        st.subheader("Questões técnicas frequentes")
        
        with st.expander("Como os dados são coletados?"):
            st.write("""
Os dados são coletados de fontes públicas do Piauí:
- **G1 Piauí**: Portal de notícias
- **Cidade Verde**: Mídia regional
- **SESAPI**: Boletins epidemiológicos oficiais
- **Meio News**: Portal regional (fonte configurada para coleta ao vivo)

O processo usa web scraping automatizado com tratamento de erros e normalização.
            """)
        
        with st.expander("Como são extraídas as entidades (doenças, municípios, sintomas)?"):
            st.write("""
Utilizamos **Named Entity Recognition (NER)** com a biblioteca spaCy:
1. Modelo spaCy em português (`pt_core_news_lg`)
2. Entity Ruler customizado com padrões epidemiológicos
3. Heurística de co-ocorrência: doença e município na mesma sentença
4. Pontuação de confiança baseada na presença de sintomas

Isso permite rastreabilidade total - cada menção preserva a sentença original.
            """)
        
        with st.expander("Por que alguns municípios têm mais menções que outros?"):
            st.write("""
As menções refletem:
- Frequência de publicação de notícias (Teresina tem mais mídia)
- Severidade ou surtos reportados
- Acessibilidade e qualidade dos dados públicos disponíveis
- Não representam necessariamente incidência epidemiológica real
            """)
        
        with st.expander("Como interpretar a 'Confiança'?"):
            st.write("""
A confiança é uma pontuação de 0 a 1 calculada por:
- **Base**: 0.62 quando doença + município aparecem na mesma sentença
- **+0.18**: Se há pelo menos um sintoma na sentença
- **+0.08**: Se há dois ou mais sintomas na sentença
- **+0.08**: Se o título contém termo epidemiológico
- **Máximo**: 0.96

No corpus fechado a maioria das menções fica em 0.70 (base + título), pois os
textos de reserva raramente descrevem sintomas; valores acima disso indicam
sintomas presentes na sentença.
            """)
        
        st.divider()
        st.subheader("Próximas melhorias")
        st.info("""
- Adicionar validação manual de menções
- Incorporar classificação supervisionada para reduzir falsos positivos
- Expandir período histórico de dados
- Integrar dados de vigilância oficial para comparação
- Documentação de API para integração com sistemas externos
        """)


if __name__ == "__main__":
    main()
