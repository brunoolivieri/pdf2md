"""Markdown → texto plano comparável (sem sintaxe, sem imagens, minúsculo, NFKC)."""

from __future__ import annotations

import re
import unicodedata

TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HTML = re.compile(r"<!--.*?-->|<[^>]+>")
ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>])")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
PREFIX = re.compile(r"^(#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)+")
EMPHASIS = re.compile(r"[*`~]+|(?<!\w)_+|_+(?!\w)")
RULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")


def normalize_line(line: str) -> str:
    s = line.strip()
    if not s or TABLE_SEPARATOR.match(s) or RULE.match(s) or s.startswith(("```", "~~~")):
        return ""
    s = IMAGE.sub(" ", s)
    s = LINK.sub(r"\1", s)
    s = HTML.sub(" ", s)
    if s.startswith("|"):
        s = " ".join(c.strip() for c in CELL_SPLIT.split(s.strip("|")))
    s = ESCAPE.sub(r"\1", s)
    s = PREFIX.sub("", s)
    s = EMPHASIS.sub("", s)
    s = unicodedata.normalize("NFKC", s).lower()
    return " ".join(s.split())


def to_lines(markdown: str) -> list[str]:
    """Uma entrada por bloco de texto (parágrafo, título ou linha de tabela), já normalizada."""
    return [n for line in markdown.splitlines() if (n := normalize_line(line))]


def to_text(markdown: str) -> str:
    return " ".join(to_lines(markdown))
