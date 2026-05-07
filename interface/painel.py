from __future__ import annotations

import copy
import json
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


CACHE_GEOJSON = DIR_DADOS_PROCESSADOS / "piaui_municipios.geojson"


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


def mostrar_estado_vazio() -> None:
    st.title("EpiPiaui Monitor")
    st.info(
        "Nenhum dado processado foi encontrado. Execute "
        "`python scripts/executar_pipeline.py --modo reais` e recarregue esta página."
    )


def main() -> None:
    caminho_banco = str(CAMINHO_BANCO_PADRAO)
    modificacao_banco = Path(caminho_banco).stat().st_mtime if Path(caminho_banco).exists() else 0.0
    noticias, mencoes = ler_dados_painel(caminho_banco, modificacao_banco)
    if noticias.empty or mencoes.empty:
        mostrar_estado_vazio()
        return

    st.title("EpiPiaui Monitor")

    with st.sidebar:
        st.header("Filtros")
        doencas = sorted(mencoes["doenca"].dropna().unique())
        doencas_selecionadas = st.multiselect("Doença", doencas, default=doencas)

        fontes = sorted(mencoes["fonte"].dropna().unique())
        fontes_selecionadas = st.multiselect("Fonte", fontes, default=fontes)

        municipios = sorted(mencoes["municipio"].dropna().unique())
        municipios_selecionados = st.multiselect(
            "Município",
            municipios,
            default=municipios,
        )

        confianca_minima = st.slider("Confiança mínima", 0.0, 1.0, 0.0, 0.05)

    filtradas = mencoes[
        mencoes["doenca"].isin(doencas_selecionadas)
        & mencoes["fonte"].isin(fontes_selecionadas)
        & mencoes["municipio"].isin(municipios_selecionados)
        & (mencoes["confianca"] >= confianca_minima)
    ].copy()

    metricas = st.columns(4)
    metricas[0].metric("Notícias", int(filtradas["noticia_id"].nunique()))
    metricas[1].metric("Menções", int(len(filtradas)))
    metricas[2].metric("Municípios", int(filtradas["municipio"].nunique()))
    metricas[3].metric("Doenças", int(filtradas["doenca"].nunique()))

    coluna_mapa, coluna_graficos = st.columns([1.35, 1])
    with coluna_mapa:
        st.subheader("Mapa de menções")
        st_folium(construir_mapa(filtradas), height=540, use_container_width=True)

    with coluna_graficos:
        st.subheader("Distribuição por doença")
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
                labels={"doenca": "Doença", "mencoes": "Menções"},
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
                labels={"mes": "Mês", "mencoes": "Menções", "doenca": "Doença"},
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
            "doenca": "Doença",
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


if __name__ == "__main__":
    main()
