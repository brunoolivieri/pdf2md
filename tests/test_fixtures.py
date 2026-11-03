import pymupdf
from make_fixtures import EXPECTED_PAGES


def test_fixtures_exist_with_expected_pages(pdfs):
    assert set(pdfs) == set(EXPECTED_PAGES)
    for name, path in pdfs.items():
        with pymupdf.open(path) as doc:
            assert doc.page_count == EXPECTED_PAGES[name], name


def test_imagem_has_embedded_image(pdfs):
    with pymupdf.open(pdfs["imagem.pdf"]) as doc:
        assert len(doc[0].get_images()) == 1
