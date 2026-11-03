"""Gera PDFs sintéticos para testes (texto, tabela, imagem, documento misto).

Uso: python tests/fixtures/make_fixtures.py [pasta_destino]
"""

import sys
from pathlib import Path

import pymupdf

PAGE_W, PAGE_H = 595, 842  # A4 em pontos
MARGIN = 72

LOREM = (
    "A conversão de documentos para Markdown reduz o custo de uso com modelos de linguagem, "
    "pois elimina formatação desnecessária e preserva a estrutura semântica do conteúdo. "
    "Tabelas e imagens precisam de tratamento específico para não desperdiçar tokens."
)

EXPECTED_PAGES = {"simples.pdf": 1, "tabela.pdf": 1, "imagem.pdf": 1, "misto.pdf": 3}


def _paragraph(page: pymupdf.Page, y: float, text: str, fontsize: float = 11) -> float:
    """Escreve um parágrafo com quebra automática e devolve o y logo abaixo dele."""
    rect = pymupdf.Rect(MARGIN, y, PAGE_W - MARGIN, y + 200)
    page.insert_textbox(rect, text, fontsize=fontsize, fontname="helv")
    lines = len(text) * fontsize * 0.5 / rect.width + 1
    return y + lines * fontsize * 1.3 + 12


def _title(page: pymupdf.Page, y: float, text: str, fontsize: float = 22) -> float:
    page.insert_text((MARGIN, y + fontsize), text, fontsize=fontsize, fontname="hebo")
    return y + fontsize * 2


def _table(page: pymupdf.Page, y: float, rows: list[list[str]]) -> float:
    """Desenha uma tabela com bordas; a primeira linha é o cabeçalho."""
    cols = len(rows[0])
    col_w = (PAGE_W - 2 * MARGIN) / cols
    row_h = 22
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            x0 = MARGIN + c * col_w
            y0 = y + r * row_h
            page.draw_rect(pymupdf.Rect(x0, y0, x0 + col_w, y0 + row_h), color=(0, 0, 0), width=0.8)
            font = "hebo" if r == 0 else "helv"
            page.insert_text((x0 + 5, y0 + 15), cell, fontsize=10, fontname=font)
    return y + len(rows) * row_h + 20


def _png(width: int, height: int, seed: int) -> bytes:
    """PNG colorido gerado em memória (gradiente) para servir de figura."""
    samples = bytearray()
    for yy in range(height):
        for xx in range(width):
            samples += bytes(((xx * 255 // width + seed) % 256, (yy * 255 // height) % 256, 160))
    pix = pymupdf.Pixmap(pymupdf.csRGB, width, height, bytes(samples), False)
    return pix.tobytes("png")


TABLE_ROWS = [
    ["Produto", "Trimestre", "Receita"],
    ["Alfa", "Q1", "1.200"],
    ["Beta", "Q2", "3.450"],
    ["Gama", "Q3", "980"],
]


def make_simples(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = _title(page, MARGIN, "Documento Simples")
    y = _paragraph(page, y, LOREM)
    _paragraph(page, y, "Segundo parágrafo com conteúdo adicional sobre otimização de contexto.")
    doc.set_metadata({"title": "Documento Simples de Teste"})
    doc.save(path)


def make_tabela(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = _title(page, MARGIN, "Relatório de Vendas")
    y = _paragraph(page, y, "Resumo das vendas por produto no ano corrente.")
    _table(page, y, TABLE_ROWS)
    doc.set_metadata({"title": ""})
    doc.save(path)


def make_imagem(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = _title(page, MARGIN, "Figura de Exemplo")
    y = _paragraph(page, y, "A figura abaixo ilustra um gradiente de cores.")
    page.insert_image(pymupdf.Rect(MARGIN, y, MARGIN + 300, y + 200), stream=_png(300, 200, 0))
    doc.set_metadata({"title": "Microsoft Word - imagem.docx"})
    doc.save(path)


def make_misto(path: Path) -> None:
    doc = pymupdf.open()
    for n in range(1, 4):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        page.insert_text((MARGIN, 40), "ACME Corp - Documento Confidencial", fontsize=9)
        page.insert_text((PAGE_W / 2 - 20, PAGE_H - 30), f"Página {n} de 3", fontsize=9)
        y = MARGIN
        if n == 1:
            y = _title(page, y, "Manual Técnico ACME")
        y = _title(page, y, f"Seção {n}", fontsize=15)
        y = _paragraph(page, y, LOREM)
        if n == 2:
            _table(page, y, TABLE_ROWS)
        if n == 3:
            page.insert_image(
                pymupdf.Rect(MARGIN, y, MARGIN + 240, y + 160), stream=_png(240, 160, 90)
            )
    doc.set_metadata({"title": "Manual Técnico ACME"})
    doc.save(path)


def build(target: Path) -> dict[str, Path]:
    """Gera (se faltarem) todos os PDFs de teste em `target` e devolve nome -> caminho."""
    target.mkdir(parents=True, exist_ok=True)
    makers = {
        "simples.pdf": make_simples,
        "tabela.pdf": make_tabela,
        "imagem.pdf": make_imagem,
        "misto.pdf": make_misto,
    }
    paths = {}
    for name, maker in makers.items():
        path = target / name
        if not path.exists():
            maker(path)
        paths[name] = path
    return paths


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    for p in build(out).values():
        print(p)
