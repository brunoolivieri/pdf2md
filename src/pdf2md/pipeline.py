"""Converte um PDF com uma estratégia: cache → conversão → pós-processamento → gravação."""

from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

from pdf2md.models import DocMeta
from pdf2md.postprocess import postprocess
from pdf2md.strategies.base import Strategy
from pdf2md.tokens import count_tokens
from pdf2md.writer import IMAGES_DIR, count_structure, output_dir, read_meta, write_output


def is_cached(folder: Path, sha256: str) -> DocMeta | None:
    """Devolve o meta existente se a pasta já contém a conversão deste mesmo PDF."""
    meta = read_meta(folder)
    if meta and meta.sha256 == sha256 and (folder / f"{meta.slug}.md").exists():
        return meta
    return None


def convert_one(
    pdf: Path,
    strategy: Strategy,
    out_root: Path,
    slug: str,
    title: str,
    sha256: str,
    force: bool = False,
) -> tuple[DocMeta, bool]:
    """Devolve (meta, veio_do_cache)."""
    folder = output_dir(out_root, slug, strategy.name)
    if not force and (cached := is_cached(folder, sha256)):
        return cached, True

    # trabalha numa pasta temporária e só troca no fim: falha não deixa saída pela metade
    work = folder.with_name(folder.name + ".tmp")
    shutil.rmtree(work, ignore_errors=True)
    images_dir = work / IMAGES_DIR

    start = time.perf_counter()
    result = strategy.convert(pdf, images_dir)
    markdown = postprocess(result.markdown, images_dir, result.pages)
    seconds = round(time.perf_counter() - start, 3)

    structure = count_structure(markdown)
    tokens, method = count_tokens(markdown)
    meta = DocMeta(
        source=str(pdf),
        sha256=sha256,
        title=title,
        slug=slug,
        strategy=strategy.name,
        library=strategy.library,
        library_version=strategy.library_version(),
        pages=result.pages,
        tables=structure["tables"],
        images=structure["images"],
        words=structure["words"],
        tokens=tokens,
        tokens_method=method,
        chars=len(markdown),
        seconds=seconds,
        created_at=datetime.now().isoformat(timespec="seconds"),
        options=strategy.options(),
    )
    write_output(work, markdown, meta)
    shutil.rmtree(folder, ignore_errors=True)
    work.rename(folder)
    return meta, False
