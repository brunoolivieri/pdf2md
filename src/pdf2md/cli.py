"""Interface de linha de comando do pdf2md."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import pymupdf
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from pdf2md.compare.report import REPORTS_DIR, compare_folders, write_reports
from pdf2md.models import CompareResult, DocMeta
from pdf2md.naming import extract_title, file_sha256, resolve_slug, slugify
from pdf2md.pipeline import convert_one
from pdf2md.postprocess import REPEAT_LIMIT
from pdf2md.strategies import AVAILABLE, get_strategy
from pdf2md.strategies.base import ProgressFn, Strategy
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
    pages: int


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
        slug = resolve_slug(slugify(title), sha, out_root, reserved)
        jobs.append(Job(pdf, sha, title, slug, _page_count(pdf)))
    return jobs


def _page_count(pdf: Path) -> int:
    try:
        with pymupdf.open(pdf) as doc:
            return max(1, doc.page_count)
    except Exception:  # PDF ilegível: a conversão vai falhar e reportar; conta como 1 unidade
        return 1


@dataclass
class Settings:
    out_root: Path
    force: bool
    image_repeat_limit: int


def _convert(job: Job, strategy: Strategy, s: Settings, progress: ProgressFn | None) -> Outcome:
    """Executa uma conversão; nunca propaga exceção (um PDF ruim não derruba o lote)."""
    try:
        meta, cached = convert_one(
            job.pdf, strategy, s.out_root, job.slug, job.title, job.sha256,
            force=s.force, image_repeat_limit=s.image_repeat_limit, progress=progress,
        )  # fmt: skip
        return Outcome(job, strategy.name, meta, cached)
    except Exception as exc:
        return Outcome(job, strategy.name, error=f"{type(exc).__name__}: {exc}")


def _convert_in_worker(job: Job, name: str, options: dict[str, Any], s: Settings) -> Outcome:
    return _convert(job, get_strategy(name, **options), s, None)


class Tracker:
    """Barra geral (porcentagem do trabalho todo) + barra de páginas do documento atual."""

    def __init__(self, total_units: int) -> None:
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("restam"),
            TimeRemainingColumn(),
            console=console,
        )
        self.total = self.progress.add_task("[bold]Total", total=total_units)
        self.current = self.progress.add_task("", total=1, visible=False)
        self._pages_done = 0  # páginas do documento atual já somadas à barra geral

    def __enter__(self) -> Tracker:
        self.progress.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.progress.stop()

    def start_doc(self, job: Job, strategy: str) -> ProgressFn:
        """Abre a barra do documento e devolve o callback de páginas para a estratégia."""
        self.progress.reset(
            self.current, total=job.pages, visible=True,
            description=f"{job.slug} [dim]({strategy})[/]",
        )  # fmt: skip
        self._pages_done = 0

        def on_pages(completed: int, total: int) -> None:
            completed = min(completed, job.pages)
            self.progress.update(self.current, completed=completed)
            self.progress.advance(self.total, completed - self._pages_done)
            self._pages_done = completed

        return on_pages

    def finish_doc(self, outcome: Outcome) -> None:
        """Completa o que faltou (cache, erro, processo paralelo) e registra o resultado."""
        self.progress.advance(self.total, max(0, outcome.job.pages - self._pages_done))
        self._pages_done = 0
        self.progress.update(self.current, visible=False)
        _report(outcome, self.progress.console)

    def step(self, description: str) -> None:
        """Etapa sem contagem de páginas (ex.: comparação): barra indeterminada."""
        self.progress.reset(self.current, total=None, description=description, visible=True)

    def advance(self, units: int = 1) -> None:
        self.progress.advance(self.total, units)


def run_strategy(
    name: str,
    options: dict[str, Any],
    jobs: list[Job],
    settings: Settings,
    workers: int,
    tracker: Tracker,
) -> list[Outcome]:
    if workers > 1 and name in PARALLEL_SAFE and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_convert_in_worker, j, name, options, settings): j for j in jobs}
            for future in as_completed(futures):
                tracker.finish_doc(future.result())
            return [f.result() for f in futures]  # ordem original dos jobs

    strategy = get_strategy(name, **options)  # instância única: conversor carregado uma vez
    outcomes = []
    for job in jobs:
        on_pages = tracker.start_doc(job, name)
        outcomes.append(_convert(job, strategy, settings, on_pages))
        tracker.finish_doc(outcomes[-1])
    return outcomes


def _report(o: Outcome, out: Console) -> None:
    tag = f"[bold]{o.job.slug}[/] [dim]({o.strategy})[/]"
    if o.error:
        out.print(f"  [red]ERRO[/]  {tag}: {o.error}")
    elif o.cached:
        out.print(f"  [cyan]cache[/] {tag}")
    else:
        out.print(f"  [green]ok[/]    {tag} {o.meta.seconds:.1f}s · {o.meta.tokens} tokens")


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
    for r in results:
        m = r.metrics
        table.add_row(
            r.slug,
            f"{r.score:.1f}",
            f"[{LEVEL_COLORS[r.level]}]{r.level}[/]",
            f"{m['ratio']:.1f}",
            f"{m['token_set']:.1f}",
            f"{m['jaccard_3gram']:.1f}",
            f"{m['paragraph_diff']:.1f}",
        )
    return table


LEVEL_COLORS = {"Alta": "green", "Média": "yellow", "Baixa": "red"}


def _similarity_panel(results: list[CompareResult]) -> Panel:
    """Destaque final: grau de semelhança de cada documento (e a média, se houver vários)."""
    lines = []
    for r in results:
        color = LEVEL_COLORS[r.level]
        lines.append(
            f"[bold]{r.slug}[/]: [bold {color}]{r.score:.1f}%[/] ({r.level}) · "
            f"{r.strategy_a} × {r.strategy_b}"
        )
    if len(results) > 1:
        mean = sum(r.score for r in results) / len(results)
        lines.append(f"\n[bold]Média: {mean:.1f}%[/]")
    return Panel("\n".join(lines), title="Grau de semelhança entre as estratégias", expand=False)


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
    image_repeat_limit: Annotated[
        int,
        typer.Option(
            min=0,
            help="Remove figuras que aparecem esta quantidade de vezes ou mais no documento "
            "(logos, selos de assinatura). 0 desliga.",
        ),
    ] = REPEAT_LIMIT,
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
    pages = sum(j.pages for j in jobs)
    console.print(
        f"[bold]{len(jobs)} PDF(s), {pages} página(s)[/] → {output} · "
        f"estratégias: {', '.join(names)}"
    )

    do_compare = compare and len(names) >= 2
    settings = Settings(output, force, image_repeat_limit)
    by_strategy: dict[str, list[Outcome]] = {}
    results: list[CompareResult] = []
    # unidades da barra geral: cada página convertida por estratégia + cada comparação
    with Tracker(pages * len(names) + (len(jobs) if do_compare else 0)) as tracker:
        for name in names:
            options = {"ocr": ocr} if name == "docling" else {}
            by_strategy[name] = run_strategy(name, options, jobs, settings, workers, tracker)

        if do_compare:
            a, b = names[0], names[1]
            for oa, ob in zip(by_strategy[a], by_strategy[b], strict=True):
                tracker.step(f"comparando {oa.job.slug}")
                if oa.meta and ob.meta:
                    result = compare_folders(
                        output_dir(output, oa.job.slug, a), output_dir(output, ob.job.slug, b)
                    )
                    write_reports(result, output / REPORTS_DIR)
                    results.append(result)
                tracker.advance()

    outcomes = [o for name in names for o in by_strategy[name]]
    console.print()
    console.print(_conversion_table(outcomes))
    if results:
        console.print(_compare_table(results))
        console.print(_similarity_panel(results))
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
    with console.status("Comparando..."):
        result = compare_folders(folder_a, folder_b)
        path = write_reports(result, reports or folder_a.parent / REPORTS_DIR)
    console.print(_compare_table([result]))
    console.print(_similarity_panel([result]))
    console.print(f"Relatório: [bold]{path}[/]")
