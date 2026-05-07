from __future__ import annotations

from bs4 import BeautifulSoup


def interpretar_html(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")
