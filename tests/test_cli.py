import json

import pytest
from typer.testing import CliRunner

from pdf2md.cli import app

runner = CliRunner()


def _invoke(*args):
    result = runner.invoke(app, [str(a) for a in args])
    assert result.exit_code == 0, result.output
    return result


def test_convert_pymupdf_batch_with_workers(pdfs, tmp_path):
    out = tmp_path / "out"
    folder = next(iter(pdfs.values())).parent
    _invoke("convert", folder, "-o", out, "-s", "pymupdf", "--workers", "2")
    expected = {
        "documento-simples-de-teste__pymupdf",
        "relatorio-de-vendas__pymupdf",
        "figura-de-exemplo__pymupdf",
        "manual-tecnico-acme__pymupdf",
    }
    assert {p.name for p in out.iterdir()} == expected
    tabela = out / "relatorio-de-vendas__pymupdf"
    assert (tabela / "relatorio-de-vendas.md").exists()
    assert json.loads((tabela / "meta.json").read_text(encoding="utf-8"))["tables"] == 1
    assert (out / "figura-de-exemplo__pymupdf" / "images" / "img-001.png").exists()

    again = _invoke("convert", folder, "-o", out, "-s", "pymupdf")
    assert "cache" in again.output


def test_convert_rejects_unknown_strategy(pdfs, tmp_path):
    result = runner.invoke(app, ["convert", str(pdfs["simples.pdf"]), "-s", "foo"])
    assert result.exit_code != 0


def test_convert_empty_folder(tmp_path):
    result = runner.invoke(app, ["convert", str(tmp_path), "-o", str(tmp_path / "o")])
    assert result.exit_code == 1


@pytest.mark.docling
def test_end_to_end_both_strategies(pdfs, tmp_path):
    out = tmp_path / "out"
    folder = next(iter(pdfs.values())).parent
    result = _invoke("convert", folder, "-o", out)
    assert "Semelhança" in result.output
    slugs = ["documento-simples-de-teste", "relatorio-de-vendas", "figura-de-exemplo",
             "manual-tecnico-acme"]  # fmt: skip
    for slug in slugs:
        for strategy in ("pymupdf", "docling"):
            folder_out = out / f"{slug}__{strategy}"
            assert (folder_out / f"{slug}.md").exists()
            assert (folder_out / "meta.json").exists()
        report = json.loads((out / "_comparacao" / f"{slug}.json").read_text(encoding="utf-8"))
        assert 0 <= report["score"] <= 100
    for strategy in ("pymupdf", "docling"):
        assert (out / f"figura-de-exemplo__{strategy}" / "images" / "img-001.png").exists()
    assert (out / "_comparacao" / "resumo.csv").exists()

    single = _invoke(
        "compare", out / "relatorio-de-vendas__pymupdf", out / "relatorio-de-vendas__docling"
    )
    assert "relatorio-de-vendas" in single.output
