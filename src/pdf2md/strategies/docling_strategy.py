"""Estratégia B: docling (modelos de layout + TableFormer, OCR opcional)."""

from __future__ import annotations

import os
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pdf2md.models import PAGE_BREAK, ConversionResult

RAW_MD = "_docling_raw.md"

# Windows sem modo desenvolvedor não cria symlinks no cache do HuggingFace: só um aviso ruidoso.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class DoclingStrategy:
    name = "docling"
    library = "docling"

    def __init__(self, ocr: bool = False, images_scale: float = 2.0) -> None:
        self.ocr = ocr
        self.images_scale = images_scale
        self._converter = None  # criado sob demanda e reaproveitado no lote

    def library_version(self) -> str:
        return version("docling")

    def options(self) -> dict[str, Any]:
        return {"ocr": self.ocr, "images_scale": self.images_scale, "table_structure": True}

    def _get_converter(self):
        if self._converter is None:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            opts = PdfPipelineOptions()
            opts.do_ocr = self.ocr
            opts.do_table_structure = True
            opts.generate_picture_images = True
            opts.images_scale = self.images_scale
            self._converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
            )
        return self._converter

    def convert(self, pdf: Path, images_dir: Path) -> ConversionResult:
        from docling_core.types.doc import ImageRefMode

        images_dir.mkdir(parents=True, exist_ok=True)
        doc = self._get_converter().convert(pdf).document
        # Com artifacts_dir relativo, o docling grava as imagens em <pasta do .md>/images
        # e escreve links relativos `images/<arquivo>` no markdown.
        raw = images_dir.parent / RAW_MD
        doc.save_as_markdown(
            raw,
            artifacts_dir=Path(images_dir.name),
            image_mode=ImageRefMode.REFERENCED,
            page_break_placeholder=PAGE_BREAK,
        )
        markdown = raw.read_text(encoding="utf-8")
        raw.unlink()
        return ConversionResult(markdown=markdown, pages=doc.num_pages(), images_dir=images_dir)
