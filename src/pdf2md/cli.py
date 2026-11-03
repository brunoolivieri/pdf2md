"""Interface de linha de comando do pdf2md."""

import typer

app = typer.Typer(help="Converte PDFs em Markdown otimizado para LLMs.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """pdf2md: duas estratégias de conversão + comparação de semelhança."""
