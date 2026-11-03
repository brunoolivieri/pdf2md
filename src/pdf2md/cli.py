"""Interface de linha de comando do pdf2md."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from pdf2md.compare.report import REPORTS_DIR, compare_folders, write_reports
from pdf2md.models import CompareResult, DocMeta
from pdf2md.naming import extract_title, file_sha256, resolve_slug, slugify
from pdf2md.pipeline import convert_one
from pdf2md.strategies import AVAILABLE, get_strategy
from pdf2md.writer import output_dir

app = typer.Typer(help="Converte PDFs em Markdown otimizado para LLMs.", no_args_is_help=True)
console = Console()

# só a estratégia A roda em processos paralelos; o docling reaproveita um único conversor
PARALLEL_SAFE = {"pymupdf"}


@dataclass
class Job:
    pdf: Path
    sha256: str
    title: str
    slug: str


@dataclass
class Outcome:
    job: Job
    strategy: str
    meta: DocMeta | None = None
    cached: bool = False
    error: str | None = None


def collect_pdfs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def plan_jobs(pdfs: list[Path], out_root: Path) -> list[Job]:
    reserved: dict[str, str] = {}
    jobs = []
    for pdf in pdfs:
        sha = file_sha256(pdf)
        title = extract_title(pdf)
        jobs.append(Job(pdf, sha, title, resolve_slug(slugify(title), sha, out_root, reserved)))
    return jobs


def _run(job: Job, name: str, options: dict[str, Any], out_root: Path, force: bool) -> Outcome:
    """Executa uma conversão; nunca propaga exceção (pode rodar em outro processo)."""
    try:
        meta, cached = convert_one(
            job.pdf, get_strategy(name, **options), out_root, job.slug, job.title, job.sha256, force
        )
        return Outcome(job, name, meta, cached)
    except Exception as exc:  # um PDF ruim não derruba o lote
        return Outcome(job, name, error=f"{type(exc).__name__}: {exc}")


def run_strategy(
    name: str, options: dict[str, Any], jobs: list[Job], out_root: Path, force: bool, workers: int
) -> list[Outcome]:
    if workers > 1 and name in PARALLEL_SAFE and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_run, j, name, options, out_root, force) for j in jobs]
            outcomes = []
            for future in futures:
                outcomes.append(future.result())
                _report(outcomes[-1])
            return outcomes

    strategy = get_strategy(name, **options)  # instância única: conversor carregado uma vez
    outcomes = []
    for job in jobs:
        try:
            meta, cached = convert_one(
                job.pdf, strategy, out_root, job.slug, job.title, job.sha256, force
            )
            outcomes.append(Outcome(job, name, meta, cached))
        except Exception as exc:
            outcomes.append(Outcome(job, name, error=f"{type(exc).__name__}: {exc}"))
        _report(outcomes[-1])
    return outcomes


def _report(o: Outcome) -> None:
    tag = f"[bold]{o.job.slug}[/] [dim]({o.strategy})[/]"
    if o.error:
        console.print(f"  [red]ERRO[/]  {tag}: {o.error}")
    elif o.cached:
        console.print(f"  [cyan]cache[/] {tag}")
    else:
        console.print(f"  [green]ok[/]    {tag} {o.meta.seconds:.1f}s · {o.meta.tokens} tokens")


def _conversion_table(outcomes: list[Outcome]) -> Table:
    table = Table(title="Conversões")
    for col in ("Documento", "Estratégia", "Págs", "Tabelas", "Imagens", "Tokens", "Tempo (s)"):
        table.add_column(col, justify="left" if col in ("Documento", "Estratégia") else "right")
    for o in outcomes:
        if o.meta is None:
            table.add_row(o.job.slug, o.strategy, "[red]erro[/]", "", "", "", "")
            continue
        m = o.meta
        seconds = "cache" if o.cached else f"{m.seconds:.1f}"
        table.add_row(
            m.slug, m.strategy, str(m.pages), str(m.tables), str(m.images), str(m.tokens), seconds
        )
    return table


def _compare_table(results: list[CompareResult]) -> Table:
    table = Table(title="Semelhança entre estratégias")
    for col in ("Documento", "Score", "Nível", "ratio", "token_set", "jaccard", "parágrafos"):
        table.add_column(col, justify="left" if col == "Documento" else "right")
    colors = {"Alta": "green", "Média": "yellow", "Baixa": "red"}
    for r in results:
        m = r.metrics
        table.add_row(
            r.slug,
            f"{r.score:.1f}",
            f"[{colors[r.level]}]{r.level}[/]",
            f"{m['ratio']:.1f}",
            f"{m['token_set']:.1f}",
            f"{m['jaccard_3gram']:.1f}",
            f"{m['paragraph_diff']:.1f}",
        )
    return table


@app.command()
def convert(
    input: Annotated[Path, typer.Argument(exists=True, help="PDF ou pasta com PDFs")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Pasta de saída")] = Path("output"),
    strategies: Annotated[
        str, typer.Option("--strategies", "-s", help="Lista separada por vírgula")
    ] = ",".join(AVAILABLE),
    ocr: Annotated[bool, typer.Option(help="OCR no docling (PDFs escaneados)")] = False,
    force: Annotated[bool, typer.Option(help="Reconverte mesmo com cache válido")] = False,
    workers: Annotated[int, typer.Option(min=1, help="Processos paralelos (pymupdf)")] = 1,
    compare: Annotated[bool, typer.Option(help="Compara as estratégias ao final")] = True,
) -> None:
    """Converte PDF(s) com cada estratégia e compara os resultados."""
    names = [s.strip() for s in strategies.split(",") if s.strip()]
    unknown = [n for n in names if n not in AVAILABLE]
    if unknown or not names:
        raise typer.BadParameter(f"use: {', '.join(AVAILABLE)}", param_hint="--strategies")

    pdfs = collect_pdfs(input)
    if not pdfs:
        console.print(f"[yellow]Nenhum PDF encontrado em {input}[/]")
        raise typer.Exit(1)
    output.mkdir(parents=True, exist_ok=True)
    jobs = plan_jobs(pdfs, output)
    console.print(f"[bold]{len(jobs)} PDF(s)[/] → {output} · estratégias: {', '.join(names)}")

    by_strategy: dict[str, list[Outcome]] = {}
    for name in names:
        console.print(f"\n[bold]Estratégia {name}[/]")
        options = {"ocr": ocr} if name == "docling" else {}
        by_strategy[name] = run_strategy(name, options, jobs, output, force, workers)

    outcomes = [o for name in names for o in by_strategy[name]]
    console.print()
    console.print(_conversion_table(outcomes))

    if compare and len(names) >= 2:
        a, b = names[0], names[1]
        results = []
        for oa, ob in zip(by_strategy[a], by_strategy[b], strict=True):
            if oa.meta and ob.meta:
                result = compare_folders(
                    output_dir(output, oa.job.slug, a), output_dir(output, ob.job.slug, b)
                )
                write_reports(result, output / REPORTS_DIR)
                results.append(result)
        if results:
            console.print(_compare_table(results))
            console.print(f"Relatórios em [bold]{output / REPORTS_DIR}[/]")

    failures = [o for o in outcomes if o.error]
    if failures:
        console.print(f"[red]{len(failures)} conversão(ões) falharam.[/]")
        raise typer.Exit(1)


@app.command("compare")
def compare_cmd(
    folder_a: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    folder_b: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    reports: Annotated[
        Path | None, typer.Option(help="Pasta dos relatórios (padrão: <saída>/_comparacao)")
    ] = None,
) -> None:
    """Compara duas pastas de saída já existentes."""
    result = compare_folders(folder_a, folder_b)
    path = write_reports(result, reports or folder_a.parent / REPORTS_DIR)
    console.print(_compare_table([result]))
    console.print(f"Relatório: [bold]{path}[/]")
