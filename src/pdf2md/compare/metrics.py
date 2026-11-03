"""Métricas de semelhança entre dois markdowns (0–100)."""

from __future__ import annotations

from difflib import SequenceMatcher

from rapidfuzz import fuzz

from pdf2md.compare.normalize import to_lines

WEIGHTS = {"ratio": 0.3, "token_set": 0.3, "jaccard_3gram": 0.3, "paragraph_diff": 0.1}
DESCRIPTIONS = {
    "ratio": "Caracteres em ordem (Indel/Levenshtein)",
    "token_set": "Vocabulário, ignorando ordem e repetição",
    "jaccard_3gram": "Trechos de 3 palavras em comum",
    "paragraph_diff": "Parágrafos idênticos na mesma sequência",
}
DIVERGENCE_MIN_CHARS = 25
DIVERGENCE_CUTOFF = 80
MAX_DIVERGENCE_CHECK = 1500


def _shingles(words: list[str], n: int = 3) -> set[tuple[str, ...]]:
    if len(words) < n:
        return {tuple(words)} if words else set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def jaccard(a: str, b: str, n: int = 3) -> float:
    sa, sb = _shingles(a.split(), n), _shingles(b.split(), n)
    if not sa and not sb:
        return 100.0
    return 100.0 * len(sa & sb) / len(sa | sb)


def level(score: float) -> str:
    if score >= 90:
        return "Alta"
    if score >= 70:
        return "Média"
    return "Baixa"


def similarity(md_a: str, md_b: str) -> dict[str, float]:
    lines_a, lines_b = to_lines(md_a), to_lines(md_b)
    a, b = " ".join(lines_a), " ".join(lines_b)
    if not a and not b:
        return dict.fromkeys(WEIGHTS, 100.0)
    return {
        "ratio": fuzz.ratio(a, b),
        "token_set": fuzz.token_set_ratio(a, b),
        "jaccard_3gram": jaccard(a, b),
        "paragraph_diff": 100.0 * SequenceMatcher(None, lines_a, lines_b, autojunk=False).ratio(),
    }


def weighted_score(metrics: dict[str, float]) -> float:
    return sum(metrics[k] * w for k, w in WEIGHTS.items())


def divergences(md_a: str, md_b: str, limit: int = 5, width: int = 160) -> list[str]:
    """Trechos de A que não aparecem (nem aproximadamente) em lugar nenhum de B."""
    text_b = " ".join(to_lines(md_b))
    found: list[tuple[float, str]] = []
    for line in to_lines(md_a)[:MAX_DIVERGENCE_CHECK]:
        if len(line) < DIVERGENCE_MIN_CHARS:
            continue
        score = fuzz.partial_ratio(line, text_b)
        if score < DIVERGENCE_CUTOFF:
            snippet = line if len(line) <= width else line[: width - 1] + "…"
            found.append((score, snippet))
    found.sort(key=lambda t: t[0])
    return [s for _, s in found[:limit]]
