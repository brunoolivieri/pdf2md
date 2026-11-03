from pathlib import Path

from pdf2md.models import CompareResult, ConversionResult, DocMeta
from pdf2md.strategies import get_strategy
from pdf2md.strategies.base import Strategy


def make_meta(**overrides) -> DocMeta:
    data = dict(
        source="a.pdf", sha256="abc", title="A", slug="a", strategy="pymupdf",
        library="pymupdf4llm", library_version="1", pages=1, tables=0, images=0, words=3,
        tokens=5, tokens_method="x", chars=10, seconds=0.1, created_at="2026-11-03T00:00:00",
    )  # fmt: skip
    data.update(overrides)
    return DocMeta(**data)


def test_docmeta_roundtrip_ignores_unknown_keys():
    meta = make_meta()
    data = meta.to_dict() | {"campo_futuro": 1}
    assert DocMeta.from_dict(data) == meta


def test_conversion_and_compare_results():
    r = ConversionResult(markdown="# x", pages=1, images_dir=Path("images"))
    assert r.pages == 1
    c = CompareResult("a", "pymupdf", "docling", {"ratio": 90.0}, 90.0, "Alta", {})
    assert c.to_dict()["only_in_a"] == []


def test_pymupdf_strategy_satisfies_protocol():
    assert isinstance(get_strategy("pymupdf"), Strategy)
