from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import urljoin, urlparse, urlunparse

try:
    from unidecode import unidecode
except ImportError:
    import unicodedata

    def unidecode(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        return normalized.encode("ascii", "ignore").decode("ascii")

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None


PADRAO_ESPACOS = re.compile(r"\s+")


def normalizar_espacos(valor: str) -> str:
    return PADRAO_ESPACOS.sub(" ", valor or "").strip()


def normalizar_chave(valor: str) -> str:
    limpo = unidecode(normalizar_espacos(valor).lower())
    limpo = re.sub(r"[^a-z0-9 ]+", " ", limpo)
    return normalizar_espacos(limpo)


def id_estavel(*partes: str) -> str:
    bruto = "|".join(partes).encode("utf-8", errors="ignore")
    return hashlib.sha256(bruto).hexdigest()[:32]


def url_canonica(url: str, url_base: str | None = None) -> str:
    absoluta = urljoin(url_base or "", url)
    analisada = urlparse(absoluta)
    analisada = analisada._replace(fragment="")
    return urlunparse(analisada)


def interpretar_data(valor: str | None) -> str | None:
    if not valor:
        return None
    valor = normalizar_espacos(valor)
    if date_parser:
        try:
            analisada = date_parser.parse(valor, dayfirst=True, fuzzy=True)
            return analisada.date().isoformat()
        except (ValueError, TypeError, OverflowError):
            return None

    for padrao in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor[:10], padrao).date().isoformat()
        except ValueError:
            continue
    return None


def dentro_do_periodo(
    data_publicacao: str | None,
    data_inicio: date | None,
    data_fim: date | None,
) -> bool:
    if not data_publicacao:
        return True
    try:
        atual = datetime.fromisoformat(data_publicacao[:10]).date()
    except ValueError:
        return True
    if data_inicio and atual < data_inicio:
        return False
    if data_fim and atual > data_fim:
        return False
    return True
