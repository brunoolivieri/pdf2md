"""Estruturas de dados compartilhadas pelo pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

# Marcador de quebra de página que as estratégias inserem no markdown bruto; o
# pós-processamento usa as páginas para achar cabeçalhos/rodapés e depois o remove.
PAGE_BREAK = "<!-- pdf2md:page-break -->"


@dataclass
class ConversionResult:
    """Saída bruta de uma estratégia, antes do pós-processamento.

    As imagens já foram gravadas pela estratégia em `images_dir`, e o markdown as
    referencia por caminho relativo `images/<arquivo>`. Páginas são separadas por `PAGE_BREAK`.
    """

    markdown: str
    pages: int
    images_dir: Path


@dataclass
class DocMeta:
    """Conteúdo do `meta.json` de cada pasta de saída."""

    source: str
    sha256: str
    title: str
    slug: str
    strategy: str
    library: str
    library_version: str
    pages: int
    tables: int
    images: int
    words: int
    tokens: int
    tokens_method: str
    chars: int
    seconds: float
    created_at: str
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocMeta:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class CompareResult:
    """Resultado da comparação entre as saídas de duas estratégias."""

    slug: str
    strategy_a: str
    strategy_b: str
    metrics: dict[str, float]
    score: float
    level: str
    structure: dict[str, dict[str, int]]
    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
