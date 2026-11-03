"""Comparação de duas pastas de saída e geração dos relatórios (MD, JSON, CSV)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pdf2md.compare.metrics import (
    DESCRIPTIONS,
    WEIGHTS,
    divergences,
    level,
    similarity,
    weighted_score,
)
from pdf2md.models import CompareResult
from pdf2md.writer import count_structure, markdown_path, read_meta

REPORTS_DIR = "_comparacao"
SUMMARY_CSV = "resumo.csv"
STRUCTURE_LABELS = {
    "words": "Palavras",
    "headings": "Títulos",
    "tables": "Tabelas",
    "images": "Imagens",
    "tokens": "Tokens",
    "seconds": "Tempo (s)",
}


def _load(folder: Path) -> tuple[str, str, dict[str, int]]:
    """(estratégia, markdown, estrutura) de uma pasta `<slug>__<estrategia>`."""
    md = markdown_path(folder).read_text(encoding="utf-8")
    meta = read_meta(folder)
    structure = count_structure(md)
    strategy = folder.name.rsplit("__", 1)[-1]
    if meta:
        structure |= {"tokens": meta.tokens, "seconds": meta.seconds}
        strategy = meta.strategy
    return strategy, md, structure


def compare_folders(folder_a: Path, folder_b: Path) -> CompareResult:
    name_a, md_a, struct_a = _load(folder_a)
    name_b, md_b, struct_b = _load(folder_b)
    metrics = {k: round(v, 2) for k, v in similarity(md_a, md_b).items()}
    score = round(weighted_score(metrics), 2)
    return CompareResult(
        slug=folder_a.name.split("__")[0],
        strategy_a=name_a,
        strategy_b=name_b,
        metrics=metrics,
        score=score,
        level=level(score),
        structure={name_a: struct_a, name_b: struct_b},
        only_in_a=divergences(md_a, md_b),
        only_in_b=divergences(md_b, md_a),
    )


def render_markdown(r: CompareResult) -> str:
    a, b = r.strategy_a, r.strategy_b
    lines = [
        f"# Comparação: {r.slug}",
        "",
        f"**Semelhança: {r.score:.1f}/100 ({r.level})** · `{a}` × `{b}`",
        "",
        "## Métricas",
        "",
        "|Métrica|Valor|Peso|O que mede|",
        "|---|---:|---:|---|",
    ]
    for key, weight in WEIGHTS.items():
        lines.append(f"|{key}|{r.metrics[key]:.1f}|{weight:.1f}|{DESCRIPTIONS[key]}|")
    lines += ["", "## Estrutura", "", f"|Item|{a}|{b}|", "|---|---:|---:|"]
    for key, label in STRUCTURE_LABELS.items():
        va, vb = r.structure[a].get(key, "—"), r.structure[b].get(key, "—")
        lines.append(f"|{label}|{va}|{vb}|")
    lines += ["", "## Maiores divergências", ""]
    for name, items in ((a, r.only_in_a), (b, r.only_in_b)):
        lines += [f"### Só em `{name}`", ""]
        lines += [f"- {item}" for item in items] or ["- (nenhuma divergência relevante)"]
        lines.append("")
    return "\n".join(lines)


def write_reports(result: CompareResult, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / f"{result.slug}.md"
    md_path.write_text(render_markdown(result), encoding="utf-8", newline="\n")
    (reports_dir / f"{result.slug}.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    update_summary(reports_dir)
    return md_path


def update_summary(reports_dir: Path) -> Path:
    """Recria `resumo.csv` a partir de todos os JSON da pasta (idempotente)."""
    rows = []
    for path in sorted(reports_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        a, b = data["strategy_a"], data["strategy_b"]
        rows.append(
            {
                "documento": data["slug"],
                "estrategia_a": a,
                "estrategia_b": b,
                "score": data["score"],
                "nivel": data["level"],
                **{k: data["metrics"][k] for k in WEIGHTS},
                f"tokens_{a}": data["structure"][a].get("tokens", ""),
                f"tokens_{b}": data["structure"][b].get("tokens", ""),
            }
        )
    out = reports_dir / SUMMARY_CSV
    fieldnames = list(dict.fromkeys(k for row in rows for k in row))
    with out.open("w", newline="", encoding="utf-8-sig") as f:  # BOM: abre certo no Excel
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out
