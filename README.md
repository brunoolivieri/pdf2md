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

## Instalação no Linux (venv + pip)

Requer Python ≥ 3.11 (`python3 --version`).

```bash
git clone <url-do-repo> pdf2md && cd pdf2md
./scripts/setup_linux.sh          # cria .venv e instala tudo (torch só CPU, ~1 GB)
source .venv/bin/activate
pdf2md --help
```

Variações do script:

```bash
WITH_DOCLING=0 ./scripts/setup_linux.sh    # só a estratégia pymupdf: leve, sem torch
PYTHON=python3.12 ./scripts/setup_linux.sh # escolhe o interpretador
TORCH_INDEX=https://download.pytorch.org/whl/cu124 ./scripts/setup_linux.sh  # GPU NVIDIA
```

O que o script faz, se preferir à mão:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev,docling]"
```

No Ubuntu/Debian sem o pacote `python3-venv` (erro de `ensurepip`), o script cria o venv sem
pip e instala o pip pelo `get-pip.py` oficial; com sudo, prefira `sudo apt install python3-venv`.
O docling baixa seus modelos do HuggingFace na primeira execução (centenas de MB, uma vez só,
em `~/.cache/huggingface`).

### Windows / uv

```bash
uv sync --extra dev --extra docling
uv run pdf2md --help
```

## Uso

Com o venv ativo (`source .venv/bin/activate`), ou prefixando `uv run` se usar uv:

```bash
pdf2md convert samples/relatorio.pdf -o output   # um PDF, as duas estratégias + comparação
pdf2md convert samples/ -o output --workers 4    # pasta (recursiva); pymupdf em paralelo
pdf2md convert samples/ -s pymupdf               # só uma estratégia
pdf2md convert samples/ --ocr --force            # OCR no docling; ignora o cache
pdf2md convert samples/ --image-repeat-limit 0   # mantém logos/selos repetidos
pdf2md compare output/x__pymupdf output/x__docling
```

Durante a execução aparecem uma barra **Total** (porcentagem de todo o trabalho, tempo decorrido
e restante) e uma barra de páginas do documento atual. Ao final saem a tabela de conversões, as
métricas e um quadro com o **grau de semelhança** de cada documento (e a média, num lote).

PDFs já convertidos (mesmo sha256 e mesmas opções) são pulados; use `--force` para refazer.

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

- Imagens gravadas em arquivo e referenciadas por link (nunca base64); ícones < 32 px
  descartados; nomes curtos `img-NNN`.
- Figuras repetitivas removidas: a mesma figura (comparada pixel a pixel, tolerando recorte
  deslocado) que aparece 3+ vezes no documento — brasão, selo "SEI assinatura eletrônica",
  logo de cabeçalho — sai por inteiro; com 2 cópias, fica uma. QR codes distintos são mantidos.
  Ajuste com `--image-repeat-limit N` (0 desliga).
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
