import pymupdf

from pdf2md.models import PAGE_BREAK
from pdf2md.pipeline import convert_one
from pdf2md.postprocess import (
    clean_text,
    compact_table_row,
    join_pages,
    postprocess,
    process_images,
    reflow,
    remove_page_artifacts,
)
from pdf2md.strategies import get_strategy


def _png(path, w, h, color=(255, 0, 0)):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), False)
    pix.set_rect(pix.irect, color)
    pix.save(str(path))


def test_compact_table_row():
    assert compact_table_row("|  **Produto** | Receita   |") == "|Produto|Receita|"
    assert compact_table_row("|:-----|------:|-----|") == "|:---|---:|---|"
    assert compact_table_row(r"| a \| b | c |") == r"|a \| b|c|"


def test_reflow_joins_and_dehyphenates():
    lines = [
        "Primeira linha que con-",
        "tinua aqui",
        "e termina.",
        "",
        "# Título",
        "- item",
        "  cont",
    ]
    assert reflow(lines) == [
        "Primeira linha que continua aqui e termina.",
        "",
        "# Título",
        "- item cont",
    ]


def test_remove_page_artifacts():
    pages = [
        f"ACME - Confidencial\n## Seção {n}\nParágrafo igual.\nFim {n * 7}.\n\nPágina {n}"
        for n in range(1, 5)
    ]
    out = remove_page_artifacts(pages)
    # cabeçalho e nº de página saem; título numerado e linha repetida fora da borda ficam
    assert out[1] == "## Seção 2\nParágrafo igual.\nFim 14.\n"


def test_remove_page_artifacts_needs_most_pages():
    pages = ["Rodapé raro\ntexto a", "outro\ntexto b", "mais\ntexto c", "Rodapé raro\ntexto d"]
    assert remove_page_artifacts(pages) == pages  # 2 de 4 páginas < 75%


def test_remove_page_artifacts_single_page_keeps_text():
    assert remove_page_artifacts(["Linha\nLinha\n2024 foi um ano."]) == [
        "Linha\nLinha\n2024 foi um ano."
    ]


def test_join_pages_continues_sentence():
    assert join_pages(["fim de frase.\n", "\nNovo parágrafo"]) == "fim de frase.\n\nNovo parágrafo"
    assert join_pages(["frase que conti\n", "nua na outra"]) == "frase que conti\nnua na outra"


def test_postprocess_removes_page_breaks(tmp_path):
    md = f"Texto um\n\n{PAGE_BREAK}\n\ncontinua aqui."
    assert postprocess(md, tmp_path / "images") == "Texto um continua aqui.\n"


def test_clean_text_whitespace_headings_and_code():
    md = "## **Título**\n\n\n\ntexto   com    espaços\n```\n|  manter  |\n   x\n```\n"
    assert clean_text(md) == "## Título\n\ntexto com espaços\n```\n|  manter  |\n   x\n```\n"


def test_process_images(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    _png(images / "grande.png", 100, 80)
    _png(images / "copia.png", 100, 80)  # mesmo conteúdo → duplicada
    _png(images / "icone.png", 10, 10)  # minúscula
    _png(images / "orfa.png", 50, 50, (0, 255, 0))  # não referenciada
    md = (
        "![](images/grande.png)\n![x](images/copia.png)\n![](images/icone.png)\n"
        "![](images/sumiu.png)\n![](data:image/png;base64,AAAA)\n"
    )
    out = process_images(md, images)
    assert out.strip() == "![](images/img-001.png)"
    assert [p.name for p in images.iterdir()] == ["img-001.png"]


def _gray_png(path, rows):
    h, w = len(rows), len(rows[0])
    data = bytes(v for row in rows for v in row for _ in range(3))
    pymupdf.Pixmap(pymupdf.csRGB, w, h, data, False).save(str(path))


def _qr_like(seed, size=120, module=6):
    """Padrão tipo QR: cantos fixos iguais e miolo pseudoaleatório que depende de `seed`."""
    import random

    rng = random.Random(seed)
    n = size // module
    cells = [[rng.random() < 0.5 for _ in range(n)] for _ in range(n)]
    for cy, cx in ((0, 0), (0, n - 7), (n - 7, 0)):
        for y in range(7):
            for x in range(7):
                cells[cy + y][cx + x] = y in (0, 6) or x in (0, 6) or (2 <= y <= 4 and 2 <= x <= 4)
    return [[0 if cells[y // module][x // module] else 255 for x in range(size)]
            for y in range(size)]  # fmt: skip


def test_process_images_near_duplicates(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    logo = _qr_like(1)
    copy = [[max(0, v - 2) for v in row] + [255] for row in logo]  # +1 px e leve ruído
    _gray_png(images / "logo1.png", logo)
    _gray_png(images / "logo2.png", copy)
    _gray_png(images / "outro.png", _qr_like(2))  # mesmos cantos, miolo diferente
    md = "![](images/logo1.png)\n![](images/logo2.png)\n![](images/outro.png)\n"
    out = process_images(md, images)
    assert out.split() == ["![](images/img-001.png)", "![](images/img-002.png)"]


def test_misto_without_headers_footers(pdfs, tmp_path):
    meta, cached = convert_one(
        pdfs["misto.pdf"], get_strategy("pymupdf"), tmp_path, "misto", "Misto", "sha"
    )
    md = (tmp_path / "misto__pymupdf" / "misto.md").read_text(encoding="utf-8")
    assert not cached
    assert "Confidencial" not in md and "Página" not in md
    # regressão: títulos numerados e parágrafo repetido no corpo não são cabeçalho
    assert all(f"Seção {n}" in md for n in (1, 2, 3))
    assert md.count("desperdiçar") == 3
    assert meta.images == 1 and (tmp_path / "misto__pymupdf" / "images" / "img-001.png").exists()


def test_cache_by_sha(pdfs, tmp_path):
    strategy = get_strategy("pymupdf")
    args = (pdfs["simples.pdf"], strategy, tmp_path, "simples", "Simples")
    first, cached1 = convert_one(*args, "sha-1")
    second, cached2 = convert_one(*args, "sha-1")
    third, cached3 = convert_one(*args, "sha-2")
    forced, cached4 = convert_one(*args, "sha-2", force=True)
    assert (cached1, cached2, cached3, cached4) == (False, True, False, False)
    assert second == first
    assert not (tmp_path / "simples__pymupdf.tmp").exists()
