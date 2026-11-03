import json

from test_models import make_meta

from pdf2md.models import DocMeta
from pdf2md.tokens import count_tokens
from pdf2md.writer import count_structure, output_dir, read_meta, write_output

MD = """# Título

Texto com **negrito**.

| a | b |
|---|---|
| 1 | 2 |

![](images/img-001.png)
"""


def test_write_and_read_output(tmp_path):
    folder = output_dir(tmp_path, "meu-doc", "pymupdf")
    (folder / "images").mkdir(parents=True)
    md_path = write_output(folder, MD, make_meta(slug="meu-doc"))
    assert md_path.name == "meu-doc.md"
    assert md_path.read_text(encoding="utf-8") == MD
    assert not (folder / "images").exists()  # pasta vazia removida
    data = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    assert set(data) == set(DocMeta.__dataclass_fields__)
    assert read_meta(folder) == make_meta(slug="meu-doc")


def test_read_meta_missing(tmp_path):
    assert read_meta(tmp_path) is None


def test_count_structure():
    s = count_structure(MD)
    assert s["tables"] == 1 and s["images"] == 1 and s["headings"] == 1


def test_count_tokens():
    tokens, method = count_tokens("olá mundo, isto é um teste")
    assert tokens > 0 and method
