"""Registro das estratégias disponíveis (importação tardia para não carregar docling à toa)."""

from __future__ import annotations

from typing import Any

from pdf2md.strategies.base import Strategy

AVAILABLE = ("pymupdf", "docling")


def get_strategy(name: str, **options: Any) -> Strategy:
    if name == "pymupdf":
        from pdf2md.strategies.pymupdf_strategy import PyMuPDFStrategy

        return PyMuPDFStrategy(**options)
    if name == "docling":
        from pdf2md.strategies.docling_strategy import DoclingStrategy

        return DoclingStrategy(**options)
    raise ValueError(f"Estratégia desconhecida: {name!r}. Opções: {', '.join(AVAILABLE)}")
