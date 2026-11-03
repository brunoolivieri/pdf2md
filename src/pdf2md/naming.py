"""Extração do título do documento e geração do nome da pasta de saída."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pymupdf

MAX_SLUG = 80
GENERIC_TITLE = re.compile(
    r"^(untitled|sem t[ií]tulo|document\d*|documento\d*|microsoft (word|powerpoint|excel)\b.*"
    r"|.*\.(docx?|pptx?|xlsx?|pdf|odt|rtf|tex)|slide \d+|\d+)$",
    re.IGNORECASE,
)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_useful(title: str | None) -> bool:
    if not title:
        return False
    title = title.strip()
    return len(title) >= 3 and not GENERIC_TITLE.match(title)


def _largest_text_line(page: pymupdf.Page) -> str:
    """Linha com a maior fonte da página (primeira ocorrência em ordem de leitura)."""
    best_size, best_text = 0.0, ""
    for block in page.get_text("dict", sort=True)["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            size = max(s["size"] for s in spans)
            text = " ".join(s["text"].strip() for s in spans)
            if size > best_size + 0.5:
                best_size, best_text = size, text
    return best_text.strip()


def extract_title(pdf: Path) -> str:
    """Título: metadado do PDF → maior fonte da página 1 → nome do arquivo."""
    try:
        with pymupdf.open(pdf) as doc:
            meta_title = (doc.metadata or {}).get("title")
            if _is_useful(meta_title):
                return meta_title.strip()
            if doc.page_count:
                text = _largest_text_line(doc[0])
                if _is_useful(text):
                    return text[:200]
    except Exception:  # PDF corrompido ou protegido: cai no nome do arquivo
        pass
    return pdf.stem


def slugify(text: str, max_len: int = MAX_SLUG) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if len(slug) > max_len:
        cut = slug[:max_len]
        slug = cut.rsplit("-", 1)[0] if "-" in cut[max_len // 2 :] else cut
    return slug.strip("-") or "documento"


def _owner_sha(out_root: Path, slug: str) -> str | None:
    """sha256 do PDF que já ocupa `slug` em `out_root` (None se livre)."""
    for folder in out_root.glob(f"{slug}__*"):
        meta = folder / "meta.json"
        if folder.is_dir() and meta.exists():
            try:
                return json.loads(meta.read_text(encoding="utf-8")).get("sha256")
            except (OSError, ValueError):
                return ""
    return None


def resolve_slug(slug: str, sha256: str, out_root: Path, reserved: dict[str, str]) -> str:
    """Escolhe um slug livre: reaproveita se o mesmo PDF já o usa, senão `slug-2`, `slug-3`...

    `reserved` mapeia slug -> sha256 já atribuídos nesta execução (evita colisões no lote).
    """
    candidate, n = slug, 1
    while True:
        owner = reserved.get(candidate)
        if owner is None:
            owner = _owner_sha(out_root, candidate)
        if owner is None or owner == sha256:
            reserved[candidate] = sha256
            return candidate
        n += 1
        candidate = f"{slug}-{n}"
