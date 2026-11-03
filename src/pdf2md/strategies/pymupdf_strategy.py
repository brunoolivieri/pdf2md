"""Estratégia A: pymupdf4llm (heurística, sem modelos de ML, rápida)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf
import pymupdf4llm

from pdf2md.models import PAGE_BREAK, ConversionResult

# O modo "layout" do pymupdf4llm >= 1.x depende de onnxruntime, que trava (segfault) em
# alguns ambientes Windows/Anaconda; além disso queremos uma estratégia puramente
# heurística para contrastar com o docling. Por isso usamos o modo legado.
pymupdf4llm.use_layout(False)

_IMAGE_TARGET = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")


class PyMuPDFStrategy:
    name = "pymupdf"
    library = "pymupdf4llm"

    def __init__(self, table_strategy: str = "lines_strict", dpi: int = 150) -> None:
        self.table_strategy = table_strategy
        self.dpi = dpi

    def library_version(self) -> str:
        return pymupdf4llm.__version__

    def options(self) -> dict[str, Any]:
        return {"table_strategy": self.table_strategy, "dpi": self.dpi, "layout": False}

    def convert(self, pdf: Path, images_dir: Path) -> ConversionResult:
        images_dir.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(pdf) as doc:
            chunks = pymupdf4llm.to_markdown(
                doc,
                write_images=True,
                image_path=str(images_dir),
                image_format="png",
                dpi=self.dpi,
                table_strategy=self.table_strategy,
                page_chunks=True,
                show_progress=False,
            )
            pages = doc.page_count
        markdown = f"\n\n{PAGE_BREAK}\n\n".join(chunk["text"] for chunk in chunks)
        return ConversionResult(
            markdown=_relative_image_links(markdown), pages=pages, images_dir=images_dir
        )


def _relative_image_links(markdown: str) -> str:
    """pymupdf4llm grava o caminho absoluto; reescreve para `images/<arquivo>`."""

    def fix(m: re.Match[str]) -> str:
        name = m.group(2).replace("\\", "/").rsplit("/", 1)[-1]
        return f"{m.group(1)}images/{name}{m.group(3)}"

    return _IMAGE_TARGET.sub(fix, markdown)
