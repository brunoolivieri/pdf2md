"""Contrato comum às estratégias de conversão."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pdf2md.models import ConversionResult


@runtime_checkable
class Strategy(Protocol):
    """Converte um PDF em markdown, gravando as imagens em `images_dir`."""

    name: str  # sufixo da pasta de saída, ex. "pymupdf"
    library: str  # pacote PyPI usado

    def library_version(self) -> str: ...

    def options(self) -> dict[str, Any]: ...

    def convert(self, pdf: Path, images_dir: Path) -> ConversionResult: ...
