"""Estratégia A: pymupdf4llm (heurística, sem modelos de ML, rápida)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf
import pymupdf4llm

from pdf2md.models import PAGE_BREAK, ConversionResult
from pdf2md.strategies.base import ProgressFn

# O modo "layout" do pymupdf4llm >= 1.x depende de onnxruntime, que trava (segfault) em
# alguns ambientes Windows/Anaconda; além disso queremos uma estratégia puramente
# heurística para contrastar com o docling. Por isso usamos o modo legado.
pymupdf4llm.use_layout(False)

_IMAGE_TARGET = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")
PAGES_PER_BATCH = 10  # granularidade do progresso


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

    def convert(
        self, pdf: Path, images_dir: Path, progress: ProgressFn | None = None
    ) -> ConversionResult:
        images_dir.mkdir(parents=True, exist_ok=True)
        texts: list[str] = []
        with pymupdf.open(pdf) as doc:
            total = doc.page_count
            # níveis de título calculados uma vez para o documento todo, não por lote
            headers = pymupdf4llm.IdentifyHeaders(doc)
            for start in range(0, total, PAGES_PER_BATCH):
                chunks = pymupdf4llm.to_markdown(
                    doc,
                    pages=list(range(start, min(total, start + PAGES_PER_BATCH))),
                    hdr_info=headers,
                    write_images=True,
                    image_path=str(images_dir),
                    image_format="png",
                    dpi=self.dpi,
                    table_strategy=self.table_strategy,
                    page_chunks=True,
                    show_progress=False,
                )
                texts.extend(chunk["text"] for chunk in chunks)
                if progress:
                    progress(len(texts), total)
        markdown = f"\n\n{PAGE_BREAK}\n\n".join(texts)
        return ConversionResult(
            markdown=_relative_image_links(markdown), pages=total, images_dir=images_dir
        )


def _relative_image_links(markdown: str) -> str:
    """pymupdf4llm grava o caminho absoluto; reescreve para `images/<arquivo>`."""

    def fix(m: re.Match[str]) -> str:
        name = m.group(2).replace("\\", "/").rsplit("/", 1)[-1]
        return f"{m.group(1)}images/{name}{m.group(3)}"

    return _IMAGE_TARGET.sub(fix, markdown)
