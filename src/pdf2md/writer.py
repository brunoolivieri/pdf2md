"""Gravação e leitura das pastas de saída (`<slug>__<estrategia>/`)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pdf2md.models import DocMeta

META_FILE = "meta.json"
IMAGES_DIR = "images"

TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
IMAGE_LINK = re.compile(r"!\[[^\]]*\]\(([^)\s]+)[^)]*\)")
HEADING = re.compile(r"^#{1,6}\s")


def output_dir(out_root: Path, slug: str, strategy: str) -> Path:
    return out_root / f"{slug}__{strategy}"


def markdown_path(folder: Path) -> Path:
    """O `.md` da pasta (nome = slug, parte antes de `__`)."""
    return folder / f"{folder.name.split('__')[0]}.md"


def count_structure(markdown: str) -> dict[str, int]:
    lines = markdown.splitlines()
    return {
        "tables": sum(1 for line in lines if TABLE_SEPARATOR.match(line.strip())),
        "images": len(IMAGE_LINK.findall(markdown)),
        "headings": sum(1 for line in lines if HEADING.match(line)),
        "words": len(markdown.split()),
    }


def write_output(folder: Path, markdown: str, meta: DocMeta) -> Path:
    """Grava `<slug>.md` e `meta.json`; remove `images/` se ficou vazia."""
    folder.mkdir(parents=True, exist_ok=True)
    md_path = markdown_path(folder)
    md_path.write_text(markdown, encoding="utf-8", newline="\n")
    (folder / META_FILE).write_text(
        json.dumps(meta.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    images = folder / IMAGES_DIR
    if images.is_dir() and not any(images.iterdir()):
        images.rmdir()
    return md_path


def read_meta(folder: Path) -> DocMeta | None:
    path = folder / META_FILE
    if not path.exists():
        return None
    try:
        return DocMeta.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None
