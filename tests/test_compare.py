import csv
import json

from test_models import make_meta

from pdf2md.compare.metrics import divergences, jaccard, level, similarity, weighted_score
from pdf2md.compare.normalize import to_lines, to_text
from pdf2md.compare.report import compare_folders, write_reports
from pdf2md.writer import write_output

TEXT = (
    "A conversão de documentos para Markdown reduz o custo de uso com modelos de linguagem "
    "e preserva a estrutura semântica do conteúdo original."
)
TABLE_A = "|Produto|Receita|\n|---|---|\n|Alfa|1.200|\n|Beta|3.450|"
TABLE_B = (
    "| Produto   |   Receita |\n|-----------|----------:|\n"
    "| **Alfa**  |     1.200 |\n| Beta      |     3.450 |"
)


def test_normalize_strips_markdown():
    md = "## **Título** _x_\n\n![img](images/a.png)\n- item [link](http://x)\n|a|b|\n|---|---|"
    assert to_lines(md) == ["título x", "item link", "a b"]


def test_identical_texts_score_100():
    m = similarity(TEXT, TEXT)
    assert all(v == 100 for v in m.values())
    assert weighted_score(m) == 100


def test_disjoint_texts_score_low():
    m = similarity(TEXT, "Receita de bolo: farinha, ovos, açúcar e manteiga em forno quente.")
    assert weighted_score(m) < 35
    assert level(weighted_score(m)) == "Baixa"


def test_same_table_different_format_is_high():
    m = similarity(TABLE_A, TABLE_B)
    assert to_text(TABLE_A) == to_text(TABLE_B)
    assert weighted_score(m) == 100


def test_jaccard_and_levels():
    assert jaccard("", "") == 100
    assert level(95) == "Alta" and level(75) == "Média" and level(10) == "Baixa"


def test_divergences():
    extra = "Este parágrafo extra só existe em uma das saídas e deve aparecer."
    assert divergences(f"{TEXT}\n\n{extra}", TEXT) == [extra.lower()]
    assert divergences(TEXT, f"{TEXT}\n\n{extra}") == []


def test_compare_folders_and_reports(tmp_path):
    out = tmp_path / "out"
    for strategy, md in (("pymupdf", f"# Doc\n\n{TEXT}\n\n{TABLE_A}\n"), ("docling", TEXT)):
        meta = make_meta(slug="doc", strategy=strategy, tokens=len(md) // 4)
        write_output(out / f"doc__{strategy}", md, meta)
    result = compare_folders(out / "doc__pymupdf", out / "doc__docling")
    assert result.slug == "doc" and result.strategy_b == "docling"
    assert 0 < result.score < 100
    assert result.structure["pymupdf"]["tables"] == 1

    reports = out / "_comparacao"
    md_path = write_reports(result, reports)
    assert "Semelhança" in md_path.read_text(encoding="utf-8")
    assert json.loads((reports / "doc.json").read_text(encoding="utf-8"))["score"] == result.score
    with (reports / "resumo.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["documento"] == "doc" and "tokens_docling" in rows[0]
