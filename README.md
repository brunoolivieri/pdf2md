# pdf2md
PDF to .MD file convertion focusing on LLM usage

Converte PDFs em Markdown enxuto para LLMs usando **duas estratégias locais e independentes**,
extrai imagens e tabelas, e mede o **grau de semelhança** entre os resultados.
Nenhuma etapa chama APIs de LLM: o custo está só nos tokens que você enviar depois, e o
`meta.json` de cada documento já informa quantos são.

| Estratégia | Biblioteca | Perfil |
|---|---|---|
| `pymupdf` | [pymupdf4llm](https://pypi.org/project/pymupdf4llm/) (modo legado, heurístico) | ~0,05 s/página, sem GPU nem modelos |
| `docling` | [docling](https://pypi.org/project/docling/) | modelos de layout + TableFormer; mais lento, melhor em layouts e tabelas complexas; OCR opcional |

## Instalação

Requer Python ≥ 3.11 e [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev                  # só a estratégia pymupdf
uv sync --extra dev --extra docling  # as duas (instala torch; ~2 GB)
```

O docling baixa seus modelos do HuggingFace na primeira execução (centenas de MB, uma vez só).

## Uso

```bash
uv run pdf2md convert samples/relatorio.pdf -o output   # um PDF, as duas estratégias + comparação
uv run pdf2md convert samples/ -o output --workers 4    # pasta (recursiva); pymupdf em paralelo
uv run pdf2md convert samples/ -s pymupdf               # só uma estratégia
uv run pdf2md convert samples/ --ocr --force            # OCR no docling; ignora o cache
uv run pdf2md compare output/x__pymupdf output/x__docling
```

PDFs já convertidos (mesmo sha256) são pulados; use `--force` para refazer.

## Saída

```
output/
├── relatorio-anual-2025__pymupdf/
│   ├── relatorio-anual-2025.md    # texto + tabelas GFM + links ./images/...
│   ├── images/img-001.png
│   └── meta.json                  # páginas, tabelas, imagens, palavras, tokens, tempo, versões
├── relatorio-anual-2025__docling/
│   └── ...
└── _comparacao/
    ├── relatorio-anual-2025.md    # score, métricas, estrutura, maiores divergências
    ├── relatorio-anual-2025.json
    └── resumo.csv                 # uma linha por documento
```

O nome da pasta é o título do documento (metadado do PDF → maior fonte da página 1 → nome do
arquivo), convertido em slug, mais o sufixo da estratégia.

## O que é feito para economizar tokens

- Imagens gravadas em arquivo e referenciadas por link (nunca base64); ícones < 32 px e
  duplicatas descartados; nomes curtos `img-NNN`.
- Cabeçalhos, rodapés e números de página removidos (bordas de página repetidas em ≥ 75% das páginas).
- Parágrafos reconstituídos (linhas quebradas unidas, hifenização desfeita), espaços colapsados.
- Tabelas GFM compactas (`|a|b|`, sem preenchimento) e sem negrito redundante.

## Semelhança

O texto das duas saídas é normalizado (sem sintaxe Markdown, minúsculo, NFKC) e comparado por:

| Métrica | Peso | Mede |
|---|---:|---|
| `ratio` | 0,3 | caracteres em ordem |
| `token_set` | 0,3 | vocabulário, sem ordem |
| `jaccard_3gram` | 0,3 | trechos de 3 palavras em comum |
| `paragraph_diff` | 0,1 | parágrafos idênticos na mesma sequência |

Score ≥ 90 = **Alta**, 70–90 = **Média**, < 70 = **Baixa**. Score baixo indica que pelo menos
uma estratégia perdeu ou embaralhou conteúdo: veja "Maiores divergências" no relatório.

## Limitações conhecidas

- O modo *layout* do pymupdf4llm (que usa `onnxruntime`) é desativado: travou com segfault no
  ambiente de desenvolvimento (Windows + Python do Anaconda).
- O pymupdf4llm às vezes funde a última linha de um parágrafo ao cabeçalho de uma tabela logo abaixo.
- PDFs escaneados só têm texto com `--ocr` (apenas docling).

## Licenças

PyMuPDF/pymupdf4llm são **AGPL-3.0** (ou licença comercial da Artifex); docling é MIT.
Considere isso antes de distribuir o pdf2md embutido em outro produto.

## Desenvolvimento com agentes

Projeto preparado para Claude Code, Codex e Gemini CLI trabalharem em sequência:
plano em [PLAN.md](PLAN.md), estado e log de handoff em [PROGRESS.md](PROGRESS.md),
regras em [AGENTS.md](AGENTS.md) (`CLAUDE.md` e `GEMINI.md` importam esse arquivo).

```bash
uv run pytest                 # tudo (~1 min com docling)
uv run pytest -m "not docling"
uv run ruff check . && uv run ruff format --check .
```
