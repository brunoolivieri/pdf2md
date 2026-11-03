"""Contrato comum às estratégias de conversão."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pdf2md.models import ConversionResult

# progress(páginas_concluídas, total_de_páginas)
ProgressFn = Callable[[int, int], None]


@runtime_checkable
class Strategy(Protocol):
    """Converte um PDF em markdown, gravando as imagens em `images_dir`."""

    name: str  # sufixo da pasta de saída, ex. "pymupdf"
    library: str  # pacote PyPI usado

    def library_version(self) -> str: ...

    def options(self) -> dict[str, Any]: ...

    def convert(
        self, pdf: Path, images_dir: Path, progress: ProgressFn | None = None
    ) -> ConversionResult: ...
