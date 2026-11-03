"""Converte um PDF com uma estratégia: cache → conversão → pós-processamento → gravação."""

from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pdf2md.models import DocMeta
from pdf2md.postprocess import REPEAT_LIMIT, postprocess
from pdf2md.strategies.base import ProgressFn, Strategy
from pdf2md.tokens import count_tokens
from pdf2md.writer import IMAGES_DIR, count_structure, output_dir, read_meta, write_output


def is_cached(folder: Path, sha256: str, options: dict[str, Any]) -> DocMeta | None:
    """Meta existente se a pasta já contém este PDF convertido com as mesmas opções."""
    meta = read_meta(folder)
    if (
        meta
        and meta.sha256 == sha256
        and meta.options == options
        and (folder / f"{meta.slug}.md").exists()
    ):
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
    image_repeat_limit: int = REPEAT_LIMIT,
    progress: ProgressFn | None = None,
) -> tuple[DocMeta, bool]:
    """Devolve (meta, veio_do_cache)."""
    folder = output_dir(out_root, slug, strategy.name)
    options = strategy.options() | {"image_repeat_limit": image_repeat_limit}
    if not force and (cached := is_cached(folder, sha256, options)):
        return cached, True

    # trabalha numa pasta temporária e só troca no fim: falha não deixa saída pela metade
    work = folder.with_name(folder.name + ".tmp")
    shutil.rmtree(work, ignore_errors=True)
    images_dir = work / IMAGES_DIR

    start = time.perf_counter()
    result = strategy.convert(pdf, images_dir, progress)
    markdown = postprocess(result.markdown, images_dir, image_repeat_limit)
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
        options=options,
    )
    write_output(work, markdown, meta)
    shutil.rmtree(folder, ignore_errors=True)
    work.rename(folder)
    return meta, False
