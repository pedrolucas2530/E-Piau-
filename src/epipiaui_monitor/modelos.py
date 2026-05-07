from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Noticia:
    id: str
    fonte: str
    titulo: str
    texto: str
    data_publicacao: str | None
    url: str
    coletado_em: str
    bruto: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MencaoExtraida:
    noticia_id: str
    doenca: str
    municipio: str
    codigo_municipio: str | None
    sentenca: str
    sintomas: list[str]
    confianca: float
    extraido_em: str


def agora_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
