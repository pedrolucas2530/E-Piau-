from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
DIR_DADOS = RAIZ_PROJETO / "dados"
DIR_DADOS_BRUTOS = DIR_DADOS / "brutos"
DIR_DADOS_PROCESSADOS = DIR_DADOS / "processados"
CAMINHO_BANCO_PADRAO = DIR_DADOS / "epipiaui_monitor.sqlite"
CAMINHO_AMOSTRA_NOTICIAS = DIR_DADOS_BRUTOS / "amostra_noticias.json"
CAMINHO_SEMENTES_REAIS = DIR_DADOS_BRUTOS / "sementes_noticias_reais_2024.json"

# Domínio de investigação (tema configurável). O município permanece fixo;
# apontar para outro JSON aqui — ou via --dominio — troca o tema investigado.
DIR_CONFIG = RAIZ_PROJETO / "config"
CAMINHO_DOMINIO_PADRAO = DIR_CONFIG / "dominios" / "arboviroses.json"

URL_MUNICIPIOS_IBGE = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/22/municipios"
)
URL_GEOJSON_IBGE = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/22"
    "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio"
)


@dataclass(frozen=True)
class ConfiguracaoFonte:
    nome: str
    url_base: str
    url_listagem: str
    url_rss: str | None = None
    palavras_chave_link: tuple[str, ...] = ()


FONTES_NOTICIAS = (
    ConfiguracaoFonte(
        nome="G1 Piaui",
        url_base="https://g1.globo.com/pi/piaui/",
        url_listagem="https://g1.globo.com/pi/piaui/",
        url_rss="https://g1.globo.com/rss/g1/pi/piaui/",
        palavras_chave_link=("dengue", "zika", "chikungunya", "saude", "sesapi"),
    ),
    ConfiguracaoFonte(
        nome="Cidade Verde",
        url_base="https://cidadeverde.com/",
        url_listagem="https://cidadeverde.com/noticias/",
        url_rss=None,
        palavras_chave_link=("dengue", "zika", "chikungunya", "saude", "sesapi"),
    ),
    ConfiguracaoFonte(
        nome="SESAPI",
        url_base="https://www.saude.pi.gov.br/",
        url_listagem="https://www.saude.pi.gov.br/noticias",
        url_rss=None,
        palavras_chave_link=("dengue", "zika", "chikungunya", "arbovirose"),
    ),
    ConfiguracaoFonte(
        nome="Meio News",
        url_base="https://www.meionews.com/",
        url_listagem="https://www.meionews.com/noticias",
        url_rss=None,
        palavras_chave_link=("dengue", "zika", "chikungunya", "saude", "arbovirose", "piaui"),
    ),
)
