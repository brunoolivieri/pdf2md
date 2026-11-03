"""Pós-processamento comum: deixa o markdown enxuto (menos tokens) e uniforme entre estratégias."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from pdf2md.models import PAGE_BREAK

MIN_IMAGE_PX = 32
# Quase-duplicatas. Calibrado num PDF real (SEI, 80 págs, logos + QR codes): cópias do mesmo
# logo ficaram com diferença média 0–2 (escala 0–255); QR codes distintos, sempre ≥ 10.
# Hashes perceptuais (dHash) não separam QR codes distintos e foram descartados.
SIZE_TOLERANCE = 2
MAX_PIXEL_DIFF = 2.5
MAX_HEADER_LEN = 120
EDGE_LINES = 2
REPEAT_RATIO = 0.75

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


@dataclass(frozen=True)
class _Gray:
    """Imagem em tons de cinza na resolução nativa."""

    width: int
    height: int
    stride: int
    samples: bytes

    def same_picture(self, other: _Gray) -> bool:
        """Mesmo tamanho (±SIZE_TOLERANCE px) e diferença média de pixel ≤ MAX_PIXEL_DIFF.

        Pega a mesma figura gravada com bytes diferentes (recompressão, recorte de 1–2 px), mas
        nunca confunde figuras distintas, mesmo parecidas (QR codes de assinaturas diferentes).
        """
        if abs(self.width - other.width) > SIZE_TOLERANCE:
            return False
        if abs(self.height - other.height) > SIZE_TOLERANCE:
            return False
        w, h = min(self.width, other.width), min(self.height, other.height)
        total = 0
        for y in range(h):
            a = self.samples[y * self.stride : y * self.stride + w]
            b = other.samples[y * other.stride : y * other.stride + w]
            total += sum(abs(x - z) for x, z in zip(a, b, strict=True))
        return total / (w * h) <= MAX_PIXEL_DIFF


def _load_gray(path: Path) -> _Gray | None:
    try:
        pix = pymupdf.Pixmap(str(path))
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)
        if pix.colorspace is None or pix.colorspace.n != 1:
            pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    except Exception:
        return None
    return _Gray(pix.width, pix.height, pix.stride, bytes(pix.samples))


def process_images(markdown: str, images_dir: Path) -> str:
    """Remove base64, links quebrados, imagens minúsculas e quase duplicadas; renomeia `img-NNN`."""
    markdown = BASE64_IMAGE.sub("", markdown)
    folder = images_dir.parent
    seen: set[str] = set()  # sha256 das imagens mantidas
    kept: list[_Gray] = []
    renames: dict[Path, str] = {}

    def replace(m: re.Match[str]) -> str:
        path = folder / m.group(2)
        if path in renames or not path.is_file():  # repetida ou inexistente
            return ""
        img = _load_gray(path)
        if img is None or img.width < MIN_IMAGE_PX or img.height < MIN_IMAGE_PX:
            return ""
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen or any(img.same_picture(other) for other in kept):
            return ""
        seen.add(digest)
        kept.append(img)
        new_name = f"img-{len(kept):03d}{path.suffix.lower()}"
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


def _edge_indexes(lines: list[str]) -> set[int]:
    """Índices das primeiras e últimas linhas não vazias da página (onde ficam cabeçalho/rodapé)."""
    filled = [i for i, line in enumerate(lines) if line.strip()]
    return set(filled[:EDGE_LINES] + filled[-EDGE_LINES:])


def _removable(line: str) -> bool:
    """Títulos, tabelas e imagens nunca são tratados como cabeçalho/rodapé."""
    s = line.strip()
    return bool(s) and len(s) <= MAX_HEADER_LEN and not s.startswith(("#", "|", "!["))


def remove_page_artifacts(pages: list[str]) -> list[str]:
    """Remove números de página e cabeçalhos/rodapés das bordas de cada página.

    Uma linha de borda é cabeçalho/rodapé se (com dígitos ignorados, ver `_header_key`) ela
    aparece na borda de pelo menos 75% das páginas.
    """
    split = [page.split("\n") for page in pages]
    edges = [_edge_indexes(lines) for lines in split]
    counts: Counter[str] = Counter()
    for lines, idx in zip(split, edges, strict=True):
        counts.update({_header_key(lines[i]) for i in idx if _removable(lines[i])})
    threshold = max(2, math.ceil(len(pages) * REPEAT_RATIO))
    repeated = {k for k, n in counts.items() if n >= threshold and k} if len(pages) >= 2 else set()

    out = []
    for lines, idx in zip(split, edges, strict=True):
        kept = []
        for i, line in enumerate(lines):
            if i in idx and _removable(line):
                bare = _strip_emphasis(line)
                if PAGE_NUMBER.match(bare) or _header_key(line) in repeated:
                    continue
            kept.append(line)
        out.append("\n".join(kept))
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


def join_pages(pages: list[str]) -> str:
    """Junta as páginas; se a anterior termina no meio de uma frase, o parágrafo continua."""
    text = ""
    for page in (p.strip("\n") for p in pages):
        if not page.strip():
            continue
        if not text:
            text = page
            continue
        last = text.rstrip().rsplit("\n", 1)[-1]
        continues = _is_plain(last) and not last.rstrip().endswith((".", "!", "?", ":"))
        text = text.rstrip() + ("\n" if continues else "\n\n") + page.lstrip("\n")
    return text


def _clean_prose(lines: list[str]) -> list[str]:
    normalized = []
    for line in lines:
        m = HEADING_BOLD.match(line.strip())
        if m:
            line = f"{m.group(1)} {m.group(2).strip()}"
        is_table = _is_table(line)
        normalized.append(compact_table_row(line) if is_table else _squeeze(line))
    return reflow(normalized)


def clean_text(markdown: str) -> str:
    """Limpa o texto fora de blocos de código; blocos ``` são preservados intactos."""
    out: list[str] = []
    prose: list[str] = []
    in_code = False
    for line in markdown.replace("\r\n", "\n").split("\n"):
        if _is_fence(line) and not in_code:
            out.extend(_clean_prose(prose))
            prose = []
            in_code = True
            out.append(line)
        elif in_code:
            out.append(line)
            in_code = not _is_fence(line)
        else:
            prose.append(line)
    out.extend(_clean_prose(prose))

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + "\n"


def postprocess(markdown: str, images_dir: Path) -> str:
    """Aplica todas as regras; altera arquivos em `images_dir` (remove/renomeia).

    As estratégias separam páginas com `PAGE_BREAK`; o marcador não chega à saída final.
    """
    markdown = process_images(markdown.replace("\r\n", "\n"), images_dir)
    pages = remove_page_artifacts(markdown.split(PAGE_BREAK))
    return clean_text(join_pages(pages))
