"""Pós-processamento comum: deixa o markdown enxuto (menos tokens) e uniforme entre estratégias."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from pathlib import Path

import pymupdf

MIN_IMAGE_PX = 32
MAX_HEADER_LEN = 120

BASE64_IMAGE = re.compile(r"!\[[^\]]*\]\(data:image/[^)]*\)")
IMAGE_LINK = re.compile(r"!\[([^\]]*)\]\((images/[^)\s]+)\)")
PAGE_NUMBER = re.compile(
    r"^(p[aá]g(ina)?\.?|page|p\.)?\s*\d{1,4}(\s*(/|de|of)\s*\d{1,4})?$", re.IGNORECASE
)
LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
HEADING_BOLD = re.compile(r"^(#{1,6})\s+(?:\*\*|__)(.+?)(?:\*\*|__)\s*$")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
EMPHASIS = re.compile(r"^(\*\*|__)(.*)\1$")
HYPHEN_END = re.compile(r"[A-Za-zÀ-ÿ]-$")


def _is_fence(line: str) -> bool:
    return line.lstrip().startswith(("```", "~~~"))


def _is_table(line: str) -> bool:
    return line.lstrip().startswith("|")


def _is_plain(line: str) -> bool:
    """Linha de texto corrido (candidata a ser unida ao parágrafo anterior)."""
    s = line.strip()
    if not s or _is_table(s) or _is_fence(s):
        return False
    if s.startswith(("#", "![", ">", "<", "    ")) or LIST_ITEM.match(s):
        return False
    return not re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s)


def _strip_emphasis(text: str) -> str:
    return re.sub(r"[*_`#]+", "", text).strip()


# --- imagens -------------------------------------------------------------------------------


def _image_size(path: Path) -> tuple[int, int]:
    try:
        pix = pymupdf.Pixmap(str(path))
        return pix.width, pix.height
    except Exception:
        return (0, 0)


def process_images(markdown: str, images_dir: Path) -> str:
    """Remove base64, links quebrados, imagens minúsculas e duplicadas; renomeia `img-NNN`."""
    markdown = BASE64_IMAGE.sub("", markdown)
    folder = images_dir.parent
    seen: dict[str, str] = {}  # hash do conteúdo -> novo nome
    renames: dict[Path, str] = {}

    def replace(m: re.Match[str]) -> str:
        path = folder / m.group(2)
        if path in renames:  # mesmo arquivo referenciado de novo
            return ""
        if not path.is_file():
            return ""
        w, h = _image_size(path)
        if w < MIN_IMAGE_PX or h < MIN_IMAGE_PX:
            return ""
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            return ""
        new_name = f"img-{len(seen) + 1:03d}{path.suffix.lower()}"
        seen[digest] = new_name
        renames[path] = new_name
        return f"![{m.group(1).strip()}]({images_dir.name}/{new_name})"

    markdown = IMAGE_LINK.sub(replace, markdown)

    if images_dir.is_dir():
        # duas fases para não sobrescrever um arquivo que já tenha o nome de destino
        staged = []
        for old, new in renames.items():
            tmp = old.with_name(f"__tmp__{new}")
            old.rename(tmp)
            staged.append((tmp, new))
        for path in images_dir.iterdir():
            if path.is_file() and not path.name.startswith("__tmp__"):
                path.unlink()  # imagens não referenciadas, minúsculas ou duplicadas
        for tmp, new in staged:
            tmp.rename(images_dir / new)
    return markdown


# --- texto ---------------------------------------------------------------------------------


def _header_key(line: str) -> str:
    """Chave de repetição. Dígitos só são ignorados em linhas curtas sem pontuação final
    (ex. "Relatório 2025 - 7"), para não confundir frases do corpo com cabeçalhos."""
    key = _strip_emphasis(line).lower()
    if len(key) <= 60 and not key.endswith((".", ":", ";", "!", "?")):
        key = re.sub(r"\d+", "#", key)
    return key


def remove_page_artifacts(lines: list[str], pages: int) -> list[str]:
    """Remove números de página e linhas que se repetem em boa parte das páginas."""
    candidates = Counter(
        _header_key(line)
        for line in lines
        if line.strip() and not _is_table(line) and len(line) <= MAX_HEADER_LEN
    )
    threshold = max(3, math.ceil(pages * 0.5))
    repeated = {k for k, n in candidates.items() if n >= threshold and k} if pages >= 2 else set()
    out = []
    for line in lines:
        if not _is_table(line):
            bare = _strip_emphasis(line)
            if bare and PAGE_NUMBER.match(bare):
                continue
            if line.strip() and _header_key(line) in repeated:
                continue
        out.append(line)
    return out


def compact_table_row(line: str) -> str:
    """`|  **a**  | b |` -> `|a|b|`; separadores viram `---` (preservando alinhamento)."""
    s = line.strip()
    cells = CELL_SPLIT.split(s.strip("|"))
    out = []
    for cell in cells:
        c = re.sub(r"\s+", " ", cell.strip())
        if SEPARATOR_CELL.match(c):
            c = (":" if c.startswith(":") else "") + "---" + (":" if c.endswith(":") else "")
        else:
            m = EMPHASIS.match(c)
            if m:
                c = m.group(2).strip()
        out.append(c)
    return "|" + "|".join(out) + "|"


def reflow(lines: list[str]) -> list[str]:
    """Une linhas quebradas do mesmo parágrafo (e de itens de lista), desfazendo hifenização."""
    out: list[str] = []
    for line in lines:
        prev = out[-1] if out else ""
        joinable = prev.strip() and (_is_plain(prev) or LIST_ITEM.match(prev))
        if _is_plain(line) and joinable:
            cur = line.strip()
            if HYPHEN_END.search(prev) and cur[:1].islower():
                out[-1] = prev[:-1] + cur
            else:
                out[-1] = prev.rstrip() + " " + cur
        else:
            out.append(line)
    return out


def _squeeze(line: str) -> str:
    return re.sub(r"[ \t]+", " ", line).rstrip()


def _clean_prose(lines: list[str], pages: int) -> list[str]:
    normalized = []
    for line in remove_page_artifacts(lines, pages):
        m = HEADING_BOLD.match(line.strip())
        if m:
            line = f"{m.group(1)} {m.group(2).strip()}"
        is_table = _is_table(line)
        normalized.append(compact_table_row(line) if is_table else _squeeze(line))
    return reflow(normalized)


def clean_text(markdown: str, pages: int) -> str:
    """Limpa o texto fora de blocos de código; blocos ``` são preservados intactos."""
    out: list[str] = []
    prose: list[str] = []
    in_code = False
    for line in markdown.replace("\r\n", "\n").split("\n"):
        if _is_fence(line) and not in_code:
            out.extend(_clean_prose(prose, pages))
            prose = []
            in_code = True
            out.append(line)
        elif in_code:
            out.append(line)
            in_code = not _is_fence(line)
        else:
            prose.append(line)
    out.extend(_clean_prose(prose, pages))

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + "\n"


def postprocess(markdown: str, images_dir: Path, pages: int) -> str:
    """Aplica todas as regras; altera arquivos em `images_dir` (remove/renomeia)."""
    return clean_text(process_images(markdown, images_dir), pages)
