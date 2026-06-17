"""
buscar_sementes_2024.py
=======================
Busca notícias de arboviroses de 2024 no G1 Piauí, Cidade Verde e SESAPI
e enriquece o arquivo sementes_noticias_reais_2024.json do EpiPiauí Monitor.

Uso:
    python buscar_sementes_2024.py

O script:
  1. Lê as sementes existentes para não duplicar
  2. Varre RSS do G1 + páginas de listagem do Cidade Verde e SESAPI
  3. Filtra por palavras-chave de arboviroses (exige match no título ou URL)
  4. Tenta baixar o HTML de cada URL para extrair um texto_reserva real
  5. Grava as novas sementes no JSON original (backup automático antes)

Dependências: requests, beautifulsoup4 (já no requirements do projeto)
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ── Configuração ──────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
CAMINHO_SEMENTES = RAIZ / "dados" / "brutos" / "sementes_noticias_reais_2024.json"

# Palavras que DEVEM estar no título ou URL — evita capturar saúde em geral
PALAVRAS_CHAVE = {"dengue", "zika", "chikungunya", "arbovirose", "aedes"}

DATA_INICIO = date(2024, 1, 1)
DATA_FIM = date(2024, 12, 31)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 EpiPiauiMonitor/0.1 "
        "(prova de conceito academica TCC IFPI)"
    )
}
TIMEOUT = 20
PAUSA_ENTRE_REQUESTS = 1.5  # respeita os servidores

# Meses em português para o regex de datas por extenso
MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

# ── Fontes ────────────────────────────────────────────────────────────────────

FONTES = [
    {
        "nome": "G1 Piaui",
        "tipo": "rss",
        "url": "https://g1.globo.com/rss/g1/pi/piaui/",
    },
    {
        "nome": "Cidade Verde",
        "tipo": "listagem",
        "url": "https://cidadeverde.com/noticias/",
        # Testamos ?pagina={n} primeiro; se 404, tentamos /{n}/
        "url_paginacao": "https://cidadeverde.com/noticias/?pagina={n}",
        "url_paginacao_alt": "https://cidadeverde.com/noticias/{n}/",
        "paginas": 10,
        "seletor_links": "a",
    },
    {
        "nome": "SESAPI",
        "tipo": "listagem",
        "url": "https://www.saude.pi.gov.br/noticias",
        "url_paginacao": "https://www.saude.pi.gov.br/noticias?page={n}",
        "paginas": 5,
        "seletor_links": "a",
        "baixar": False,
    },
]

# ── Utilitários ───────────────────────────────────────────────────────────────

sessao = requests.Session()
sessao.headers.update(HEADERS)


def get(url: str) -> requests.Response | None:
    """Faz GET com tratamento de encoding.

    Fix #1: Quando o servidor declara iso-8859-1/latin-1/windows-1252 mas
    o conteúdo real é UTF-8 (caso do Cidade Verde), força UTF-8 para evitar
    títulos com 'Ã³' no lugar de 'ó'.
    """
    try:
        r = sessao.get(url, timeout=TIMEOUT)
        r.raise_for_status()

        # Normaliza o encoding declarado (remove hífens e coloca em minúsculas)
        enc_declarado = (r.encoding or "").lower().replace("-", "")
        if enc_declarado in ("iso88591", "latin1", "windows1252"):
            r.encoding = "utf-8"

        time.sleep(PAUSA_ENTRE_REQUESTS)
        return r
    except requests.RequestException as e:
        print(f"    ⚠ Falha ao acessar {url}: {e}")
        return None


def contem_palavra_chave(titulo: str, url: str = "") -> bool:
    """Exige match no título ou URL — evita falsos positivos de saúde em geral."""
    alvo = (titulo + " " + url).lower()
    return any(p in alvo for p in PALAVRAS_CHAVE)


def extrair_data_texto(texto: str) -> date | None:
    padrao_iso = re.search(r"(2024[-/]\d{2}[-/]\d{2})", texto)
    if padrao_iso:
        try:
            return date.fromisoformat(padrao_iso.group(1).replace("/", "-"))
        except ValueError:
            pass
    padrao_br = re.search(r"(\d{2})/(\d{2})/(2024)", texto)
    if padrao_br:
        try:
            return date(int(padrao_br.group(3)), int(padrao_br.group(2)), int(padrao_br.group(1)))
        except ValueError:
            pass
    if "2024" in texto:
        return date(2024, 1, 1)
    return None


def extrair_data_html(soup: BeautifulSoup) -> date | None:
    """Extrai a data de publicação do HTML em quatro camadas de prioridade.

    Fix #2:
      (a) meta tags article:published_time / datePublished / pubdate via
          property, name e itemprop;
      (b) tag <time> com atributo datetime;
      (c) JSON-LD (script type="application/ld+json") — datePublished /
          dateCreated / dateModified;
      (d) regex no texto visível: DD/MM/2024 e DD de mês de 2024.
    """

    # (a) Meta tags — testamos property, name e itemprop
    for campo in ("article:published_time", "datePublished", "pubdate", "date"):
        tag = (
            soup.find("meta", property=campo)
            or soup.find("meta", attrs={"name": campo})
            or soup.find("meta", attrs={"itemprop": campo})
        )
        if tag and tag.get("content"):
            d = extrair_data_texto(tag["content"])
            if d:
                return d

    # (b) Tag <time datetime="...">
    tag_time = soup.find("time", attrs={"datetime": True})
    if tag_time:
        d = extrair_data_texto(tag_time["datetime"])
        if d:
            return d

    # (c) JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            dados = json.loads(script.string or "")
            # Pode ser lista (array de objetos schema.org)
            if isinstance(dados, list):
                dados = dados[0] if dados else {}
            for campo in ("datePublished", "dateCreated", "dateModified"):
                if campo in dados:
                    d = extrair_data_texto(str(dados[campo]))
                    if d:
                        return d
        except (json.JSONDecodeError, AttributeError, IndexError):
            pass

    # (d) Regex no texto visível da página
    texto_visivel = soup.get_text(" ")

    # Padrão DD/MM/2024
    padrao_br = re.search(r"\b(\d{1,2})/(\d{1,2})/(2024)\b", texto_visivel)
    if padrao_br:
        try:
            return date(
                int(padrao_br.group(3)),
                int(padrao_br.group(2)),
                int(padrao_br.group(1)),
            )
        except ValueError:
            pass

    # Padrão "DD de mês de 2024"
    padrao_extenso = re.search(
        r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES_PT.keys()) + r")\s+de\s+(2024)\b",
        texto_visivel,
        re.IGNORECASE,
    )
    if padrao_extenso:
        try:
            mes = MESES_PT[padrao_extenso.group(2).lower()]
            return date(int(padrao_extenso.group(3)), mes, int(padrao_extenso.group(1)))
        except (KeyError, ValueError):
            pass

    return None


def extrair_texto_html(soup: BeautifulSoup, max_chars: int = 600) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside"]):
        tag.decompose()
    recipiente = soup.find("article") or soup.find("main") or soup.body or soup
    paragrafos = [
        p.get_text(" ", strip=True)
        for p in recipiente.find_all("p")
        if len(p.get_text(strip=True)) >= 40
        and "Compartilhe" not in p.get_text()
        and "Veja também" not in p.get_text()
    ]
    return " ".join(paragrafos)[:max_chars]


def extrair_titulo_html(soup: BeautifulSoup) -> str:
    for seletor in (
        soup.find("meta", property="og:title"),
        soup.find("h1"),
        soup.find("title"),
    ):
        if seletor:
            v = seletor.get("content") or seletor.get_text(" ")
            v = re.sub(r"\s+", " ", v).strip()
            v = re.sub(r"\s*\|\s*G1.*$", "", v)
            if v:
                return v
    return ""


# ── Coletores ────────────────────────────────────────────────────────────────

def coletar_rss(fonte: dict) -> list[dict]:
    print(f"\n📡 RSS: {fonte['nome']}")
    r = get(fonte["url"])
    if not r:
        return []

    try:
        raiz = ET.fromstring(r.content)
    except ET.ParseError as e:
        print(f"  ⚠ Erro ao parsear RSS: {e}")
        return []

    candidatos = []
    for item in raiz.findall(".//item"):
        link = item.findtext("link", "").strip()
        titulo = item.findtext("title", "").strip()
        pub_date = item.findtext("pubDate", "") or ""
        descricao = item.findtext("description", "")

        if not link:
            continue

        # Filtro estrito: título ou URL deve conter palavra-chave de arbovirose
        if not contem_palavra_chave(titulo, link):
            continue

        data = extrair_data_texto(pub_date + " " + link)
        if data and not (DATA_INICIO <= data <= DATA_FIM):
            continue

        candidatos.append({
            "fonte": fonte["nome"],
            "titulo": titulo,
            "url": link,
            "data_estimada": data,
            "descricao": descricao[:300],
        })
        print(f"  + {titulo[:65]}")

    print(f"  → {len(candidatos)} candidatos relevantes")
    return candidatos


def _detectar_url_paginacao(fonte: dict) -> str | None:
    """Fix #4: Detecta qual formato de paginação funciona testando a página 2.

    Testa url_paginacao primeiro; se retornar 404/erro, tenta url_paginacao_alt.
    Retorna o formato que funcionou, ou None se nenhum funcionar.
    """
    for chave in ("url_paginacao", "url_paginacao_alt"):
        url_fmt = fonte.get(chave, "")
        if not url_fmt:
            continue
        url_teste = url_fmt.format(n=2)
        print(f"  🔍 Testando paginação: {url_teste}")
        r = get(url_teste)
        if r:
            print(f"  ✓ Formato de paginação detectado: {url_fmt}")
            return url_fmt
    print("  ⚠ Nenhum formato de paginação funcionou — usando só a página inicial.")
    return None


def coletar_listagem(fonte: dict) -> list[dict]:
    print(f"\n📰 Listagem: {fonte['nome']}")
    candidatos = []
    base = fonte["url"]
    n_paginas = fonte.get("paginas", 3)
    urls_vistas: set[str] = set()

    # Fix #4: detecta o formato antes de iterar
    url_pag_fmt: str | None = None
    if n_paginas > 1:
        url_pag_fmt = _detectar_url_paginacao(fonte)

    for pagina in range(1, n_paginas + 1):
        if pagina == 1:
            url = base
        elif url_pag_fmt is None:
            # Nenhum formato funcionou — para após a primeira página
            break
        else:
            url = url_pag_fmt.format(n=pagina)

        r = get(url)
        if not r:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        host_fonte = urlparse(base).netloc.replace("www.", "")

        for ancora in soup.find_all("a", href=True):
            href = urljoin(base, ancora["href"])
            host = urlparse(href).netloc.replace("www.", "")
            if host_fonte not in host:
                continue
            if href in urls_vistas:
                continue

            texto_link = ancora.get_text(" ", strip=True)
            href_lower = href.lower()

            # Filtro estrito: texto do link ou URL deve conter palavra-chave
            if not contem_palavra_chave(texto_link, href_lower):
                continue

            # URL deve parecer uma notícia (tem /2024/ ou segmento numérico longo)
            if "2024" not in href and not re.search(r"/\d{5,}/", href):
                continue

            urls_vistas.add(href)
            data = extrair_data_texto(href + " " + texto_link)
            if data and not (DATA_INICIO <= data <= DATA_FIM):
                continue

            # Fix #3: log amigável quando o texto do link está vazio
            if texto_link:
                titulo_interno = texto_link[:200]
                titulo_log = texto_link[:65]
            else:
                titulo_interno = href  # será substituído pelo HTML no enriquecimento
                titulo_log = "[sem título — será extraído do HTML]"

            candidatos.append({
                "fonte": fonte["nome"],
                "titulo": titulo_interno,
                "url": href,
                "data_estimada": data,
                "descricao": "",
            })
            print(f"  + {titulo_log}")

    print(f"  → {len(candidatos)} candidatos relevantes")
    return candidatos


# ── Enriquecimento ───────────────────────────────────────────────────────────

def enriquecer_candidato(cand: dict, deve_baixar: bool = True) -> dict | None:
    url = cand["url"]
    fonte = cand["fonte"]

    if not deve_baixar:
        titulo = cand["titulo"]
        data = cand.get("data_estimada")
        data_str = data.isoformat() if data else "2024-01-01"
        descricao = cand.get("descricao", "")
        texto_reserva = descricao if len(descricao) > 80 else f"Notícia de {fonte} sobre arboviroses no Piauí em 2024."
        return {
            "fonte": fonte,
            "titulo": titulo,
            "data_publicacao": data_str,
            "url": url,
            "baixar": False,
            "texto_reserva": texto_reserva,
        }

    r = get(url)
    if not r:
        return None
    if "text/html" not in r.headers.get("content-type", ""):
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    titulo = extrair_titulo_html(soup) or cand["titulo"]
    texto = extrair_texto_html(soup, max_chars=600)
    data = extrair_data_html(soup) or cand.get("data_estimada")
    data_str = data.isoformat() if data else "2024-01-01"

    if not titulo or len(texto) < 80:
        print(f"    ⚠ Texto insuficiente em {url}")
        return None

    # Verificação final: o texto baixado também deve mencionar arboviroses
    if not contem_palavra_chave(titulo, texto[:200]):
        print(f"    ⚠ Conteúdo não é sobre arboviroses: {titulo[:50]}")
        return None

    if data and not (DATA_INICIO <= data <= DATA_FIM):
        print(f"    ⚠ Fora do período: {data}")
        return None

    return {
        "fonte": fonte,
        "titulo": titulo,
        "data_publicacao": data_str,
        "url": url,
        "baixar": True,
        "texto_reserva": texto[:500],
    }


# ── Validações ───────────────────────────────────────────────────────────────

def validar_e_resumir(novas_sementes: list[dict], todas: list[dict]) -> None:
    """Valida o arquivo gravado e imprime resumo final.

    Fix #5 (validações):
      - Reabre o JSON e verifica ausência de encoding quebrado (\\ufffd ou 'Ã')
      - Verifica que ≥ 50% das novas sementes têm data real (≠ 2024-01-01)
      - Imprime distribuição por fonte e por mês
      - Avisos não interrompem o script
    """
    print("\n" + "=" * 60)
    print("📊 RESUMO FINAL")
    print("=" * 60)

    # — Validação 1: encoding dos títulos no arquivo gravado —
    try:
        with open(CAMINHO_SEMENTES, encoding="utf-8") as f:
            conteudo_raw = f.read()
        titulos_ruins = [
            s["titulo"]
            for s in json.loads(conteudo_raw)
            if "�" in s.get("titulo", "") or "Ã" in s.get("titulo", "")
        ]
        if titulos_ruins:
            print(f"\n⚠ AVISO: {len(titulos_ruins)} título(s) com encoding quebrado no arquivo:")
            for t in titulos_ruins[:5]:
                print(f"   • {t[:80]}")
        else:
            print("\n✅ Encoding dos títulos gravados: OK")
    except Exception as e:
        print(f"\n⚠ Não foi possível validar encoding do arquivo: {e}")

    # — Validação 2: proporção de datas reais —
    if novas_sementes:
        datas_padrao = [s for s in novas_sementes if s["data_publicacao"] == "2024-01-01"]
        pct_padrao = len(datas_padrao) / len(novas_sementes) * 100
        if pct_padrao > 50:
            print(
                f"\n⚠ AVISO: {pct_padrao:.0f}% das novas sementes têm data padrão (2024-01-01). "
                "Verifique a extração de datas."
            )
        else:
            print(f"\n✅ Datas: {100 - pct_padrao:.0f}% das novas sementes têm data real.")

    # — Resumo: total e por fonte —
    print(f"\n📁 Total de sementes no arquivo: {len(todas)}")
    print("\n   Por fonte:")
    for fonte, qtd in sorted(Counter(s["fonte"] for s in todas).items()):
        print(f"   • {fonte}: {qtd}")

    # — Resumo: novas sementes por mês —
    if novas_sementes:
        meses: Counter = Counter()
        for s in novas_sementes:
            try:
                mes = s["data_publicacao"][:7]  # YYYY-MM
                meses[mes] += 1
            except (KeyError, TypeError):
                pass
        print("\n   Novas sementes por mês de publicação:")
        for mes in sorted(meses):
            print(f"   • {mes}: {meses[mes]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("EpiPiauí Monitor — Expansão de Sementes 2024")
    print("=" * 60)

    # Fix #5: leitura do JSON com encoding explícito
    sementes_existentes: list[dict] = []
    if CAMINHO_SEMENTES.exists():
        with open(CAMINHO_SEMENTES, encoding="utf-8") as f:
            sementes_existentes = json.load(f)
    urls_existentes = {s["url"] for s in sementes_existentes}
    print(f"\n📂 Sementes existentes: {len(sementes_existentes)}")

    todos_candidatos: list[dict] = []
    for fonte in FONTES:
        if fonte["tipo"] == "rss":
            todos_candidatos.extend(coletar_rss(fonte))
        else:
            todos_candidatos.extend(coletar_listagem(fonte))

    # Remover duplicatas e já existentes
    vistos: set[str] = set()
    novos_unicos = []
    for c in todos_candidatos:
        if c["url"] not in urls_existentes and c["url"] not in vistos:
            vistos.add(c["url"])
            novos_unicos.append(c)

    print(f"\n🔍 Novos candidatos únicos: {len(novos_unicos)}")

    if not novos_unicos:
        print("\n✅ Nenhuma nova semente encontrada.")
        return

    print("\n⬇  Baixando HTML e validando conteúdo...")
    novas_sementes: list[dict] = []
    for i, cand in enumerate(novos_unicos, 1):
        fonte_cfg = next((f for f in FONTES if f["nome"] == cand["fonte"]), {})
        deve_baixar = fonte_cfg.get("baixar", True)
        print(f"  [{i:02d}/{len(novos_unicos)}] {cand['titulo'][:55]}...")
        semente = enriquecer_candidato(cand, deve_baixar=deve_baixar)
        if semente:
            novas_sementes.append(semente)
            print(f"    ✓ {semente['data_publicacao']} | {len(semente['texto_reserva'])} chars")

    print(f"\n✅ Novas sementes válidas: {len(novas_sementes)}")

    if not novas_sementes:
        print("Nenhuma semente nova passou na validação.")
        return

    # Fix #5: backup e gravação com encoding='utf-8' explícito
    backup = CAMINHO_SEMENTES.with_suffix(".backup.json")
    with open(CAMINHO_SEMENTES, encoding="utf-8") as f:
        conteudo_original = f.read()
    with open(backup, "w", encoding="utf-8") as f:
        f.write(conteudo_original)
    print(f"💾 Backup salvo em: {backup.name}")

    todas = sementes_existentes + novas_sementes
    with open(CAMINHO_SEMENTES, "w", encoding="utf-8") as f:
        json.dump(todas, f, ensure_ascii=False, indent=2)
    print(f"📝 Arquivo atualizado: {CAMINHO_SEMENTES.name}")
    print(f"   Total de sementes: {len(todas)} (era {len(sementes_existentes)})")

    # Validações pós-gravação e resumo final
    validar_e_resumir(novas_sementes, todas)

    print("\nPróximo passo:")
    print("  python scripts/executar_pipeline.py --modo reais")


if __name__ == "__main__":
    main()
