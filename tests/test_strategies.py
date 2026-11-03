import re

import pytest

from pdf2md.strategies import get_strategy

LINK = re.compile(r"!\[[^\]]*\]\((images/[^)]+)\)")


def _convert(name, pdf, tmp_path, **opts):
    images = tmp_path / "images"
    return get_strategy(name, **opts).convert(pdf, images)


@pytest.fixture(params=["pymupdf", pytest.param("docling", marks=pytest.mark.docling)])
def strategy(request):
    return request.param


def test_table_becomes_gfm(strategy, pdfs, tmp_path):
    md = _convert(strategy, pdfs["tabela.pdf"], tmp_path).markdown
    assert re.search(r"^\|.*Produto.*\|.*Trimestre.*\|.*Receita.*\|$", md, re.M)
    assert re.search(r"^\|\s*:?-{3,}", md, re.M)
    assert "3.450" in md


def test_image_written_and_linked(strategy, pdfs, tmp_path):
    result = _convert(strategy, pdfs["imagem.pdf"], tmp_path)
    links = LINK.findall(result.markdown)
    files = list(result.images_dir.iterdir())
    assert len(links) == 1 and len(files) == 1
    assert (tmp_path / links[0]).exists()


def test_pages_and_text(strategy, pdfs, tmp_path):
    result = _convert(strategy, pdfs["misto.pdf"], tmp_path)
    assert result.pages == 3
    assert "Seção 3" in result.markdown


def test_progress_reaches_total(strategy, pdfs, tmp_path):
    calls = []
    get_strategy(strategy).convert(
        pdfs["misto.pdf"], tmp_path / "images", lambda done, total: calls.append((done, total))
    )
    assert calls and calls[-1] == (3, 3)


def test_unknown_strategy():
    with pytest.raises(ValueError):
        get_strategy("nao-existe")
