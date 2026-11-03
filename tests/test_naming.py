import json

from pdf2md.naming import extract_title, file_sha256, resolve_slug, slugify


def test_title_from_metadata(pdfs):
    assert extract_title(pdfs["simples.pdf"]) == "Documento Simples de Teste"


def test_title_from_largest_font_when_metadata_empty(pdfs):
    assert extract_title(pdfs["tabela.pdf"]) == "Relatório de Vendas"


def test_title_ignores_generic_metadata(pdfs):
    assert extract_title(pdfs["imagem.pdf"]) == "Figura de Exemplo"


def test_title_falls_back_to_filename(tmp_path):
    broken = tmp_path / "meu arquivo.pdf"
    broken.write_bytes(b"isto nao e um pdf")
    assert extract_title(broken) == "meu arquivo"


def test_slugify_accents_and_length():
    assert slugify("Relatório Técnico: Ação & Reação!") == "relatorio-tecnico-acao-reacao"
    assert slugify("???") == "documento"
    long = slugify("palavra " * 30)
    assert len(long) <= 80 and not long.endswith("-")


def test_resolve_slug_collision(tmp_path):
    folder = tmp_path / "doc__pymupdf"
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"sha256": "aaa"}), encoding="utf-8")
    reserved: dict[str, str] = {}
    assert resolve_slug("doc", "aaa", tmp_path, reserved) == "doc"  # mesmo PDF reaproveita
    assert resolve_slug("doc", "bbb", tmp_path, reserved) == "doc-2"  # outro PDF
    assert resolve_slug("doc", "ccc", tmp_path, reserved) == "doc-3"  # colisão no lote


def test_file_sha256_stable(pdfs):
    assert file_sha256(pdfs["simples.pdf"]) == file_sha256(pdfs["simples.pdf"])
