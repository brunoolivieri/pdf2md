# PLAN — pdf2md

Conversor de PDF → Markdown otimizado para consumo por LLMs (menos tokens, estrutura limpa,
tabelas preservadas, imagens como arquivos e não base64), usando **duas estratégias
independentes** e comparando o resultado entre elas.

> Este plano é executado em cooperação por **Claude Code, Codex e Gemini CLI**.
> Antes de qualquer coisa, leia [AGENTS.md](AGENTS.md) (protocolo) e [PROGRESS.md](PROGRESS.md) (estado atual).

---

## 1. Objetivos

1. Converter cada PDF em Markdown, com texto, tabelas (em tabela Markdown) e imagens extraídas.
2. Rodar **duas estratégias com bibliotecas diferentes**, cada uma gerando sua própria pasta.
3. Comparar o texto das duas saídas e reportar o **grau de semelhança**.
4. Minimizar custo/tempo de uso com LLMs: conversão 100% local (sem chamadas de API),
   saída enxuta e estimativa de tokens por documento.

## 2. Estratégias

| ID | Nome da pasta | Biblioteca | Perfil |
|----|---------------|------------|--------|
| A  | `pymupdf`     | [`pymupdf4llm`](https://pypi.org/project/pymupdf4llm/) (PyMuPDF) | Rápida, leve, sem GPU. Heurística de layout; tabelas via `find_tables`. |
| B  | `docling`     | [`docling`](https://pypi.org/project/docling/) (IBM) | Modelos de layout + TableFormer. Mais lenta, melhor em tabelas complexas. OCR opcional. |

Ambas as bibliotecas rodam localmente → custo zero de API. Licenças: PyMuPDF é AGPL-3.0
(registrar no README), Docling é MIT.

## 3. Layout de saída

Para cada PDF, cada estratégia gera uma pasta irmã `<titulo>__<estrategia>`
(a "qualificação" é o sufixo da estratégia):

```
output/
├── relatorio-anual-2025__pymupdf/
│   ├── relatorio-anual-2025.md      # todo o texto + tabelas Markdown + links ./images/...
│   ├── images/
│   │   ├── p003-01.png
│   │   └── p007-01.png
│   └── meta.json                    # origem, sha256, páginas, nº tabelas/imagens, tokens, tempo, versão da lib
├── relatorio-anual-2025__docling/
│   ├── relatorio-anual-2025.md
│   ├── images/
│   └── meta.json
└── _comparacao/
    ├── relatorio-anual-2025.md      # relatório legível de semelhança
    ├── relatorio-anual-2025.json    # métricas brutas
    └── resumo.csv                   # uma linha por PDF (lote)
```

**Título** (`<titulo>`), em ordem de preferência:
1. metadado `Title` do PDF (se não vazio nem genérico, ex. "Microsoft Word - ...");
2. maior linha de texto (maior fonte) da página 1;
3. nome do arquivo.

Depois: slug ASCII (sem acentos), minúsculas, `-` como separador, máx. 80 caracteres.
Colisão de nomes → sufixo `-2`, `-3`...

## 4. Arquitetura

```
src/pdf2md/
├── __init__.py
├── cli.py              # Typer: comandos convert / compare
├── models.py           # dataclasses: ConversionResult, DocMeta, CompareResult
├── naming.py           # extração de título + slugify + resolução de colisão
├── writer.py           # grava .md, images/, meta.json
├── postprocess.py      # otimizações para LLM (comuns às duas estratégias)
├── tokens.py           # contagem/estimativa de tokens
├── strategies/
│   ├── base.py         # Protocol Strategy: name, convert(pdf, out_dir) -> ConversionResult
│   ├── pymupdf_strategy.py
│   └── docling_strategy.py
└── compare/
    ├── normalize.py    # Markdown → texto plano comparável
    ├── metrics.py      # métricas de similaridade
    └── report.py       # relatório MD/JSON/CSV
tests/
├── fixtures/           # PDFs sintéticos gerados por script (texto, tabela, imagem)
└── test_*.py
samples/                # PDFs reais para teste manual (não versionados, exceto pequenos)
output/                 # saída (ignorado pelo git)
```

Stack: Python ≥ 3.11, `uv`, `typer`, `rich`, `rapidfuzz`, `tiktoken`, `pytest`, `ruff`.
Dependências pesadas (`docling`) ficam em extra opcional: `uv sync --extra docling`.

## 5. Otimizações para LLM (barato + ágil)

- Conversão local, sem LLM no pipeline.
- Imagens salvas em arquivo e referenciadas por link relativo — **nunca** base64 no `.md`.
- Imagens minúsculas (< 32 px ou ícones/decoração) descartadas; dedupe por hash.
- Remoção de cabeçalhos/rodapés repetidos e números de página isolados.
- Junção de palavras hifenizadas na quebra de linha; colapso de espaços e linhas vazias.
- Tabelas em Markdown GFM compacto (sem padding de alinhamento).
- `meta.json` com contagem de tokens (`tiktoken`, `o200k_base`) para estimar custo antes de enviar ao LLM.
- Cache por `sha256` do PDF: se a saída já existe e o hash bate, pula (`--force` refaz).
- Lote: estratégia A em `ProcessPoolExecutor`; estratégia B reutiliza um único `DocumentConverter`.

## 6. Comparação

1. **Normalização** (`compare/normalize.py`): remove sintaxe Markdown (`#`, `*`, `|`, links de imagem,
   separadores de tabela), Unicode NFKC, minúsculas, colapsa espaços.
2. **Métricas** (`compare/metrics.py`):
   - `ratio` — `rapidfuzz.fuzz.ratio` (similaridade por caracteres, sensível à ordem);
   - `token_set` — `rapidfuzz.fuzz.token_set_ratio` (vocabulário, insensível à ordem);
   - `jaccard_3gram` — Jaccard de shingles de 3 palavras;
   - `line_diff` — `difflib.SequenceMatcher` sobre linhas;
   - contagens estruturais: nº de palavras, títulos, tabelas, imagens, tokens em cada saída.
3. **Score final** = média ponderada (ratio 0.3, token_set 0.3, jaccard 0.3, line_diff 0.1),
   classificado: ≥ 90 Alta · 70–90 Média · < 70 Baixa.
4. **Saída**: tabela no terminal (`rich`), `_comparacao/<titulo>.md` com métricas e
   amostra das maiores divergências, `.json` com tudo, `resumo.csv` agregado do lote.

## 7. CLI

```bash
pdf2md convert samples/arquivo.pdf -o output           # ambas estratégias + comparação
pdf2md convert samples/ -o output --strategies pymupdf # pasta inteira, só A
pdf2md convert samples/ -o output --ocr --force        # OCR no docling, ignora cache
pdf2md compare output/x__pymupdf output/x__docling     # só compara saídas existentes
```

---

## 8. Passos de execução

Cada passo é uma unidade de trabalho para **um** agente em **um** commit.
Status vive em [PROGRESS.md](PROGRESS.md), não aqui.

### Fase 0 — Fundação
- **F0.1 Scaffolding** — `pyproject.toml` (uv, extras `docling`, `dev`), `src/pdf2md/__init__.py`,
  `ruff` + `pytest` configurados, entry point `pdf2md`.
  *Aceite:* `uv sync --extra dev` e `uv run pytest` passam (0 testes ok); `uv run pdf2md --help` funciona.
- **F0.2 Fixtures** — `tests/fixtures/make_fixtures.py` gera com `pymupdf` PDFs sintéticos:
  `simples.pdf` (título + parágrafos), `tabela.pdf` (tabela 4×3 com bordas), `imagem.pdf` (PNG embutido),
  `misto.pdf` (multipágina com cabeçalho/rodapé repetidos). Dep: F0.1.
  *Aceite:* script gera os 4 PDFs; teste verifica que existem e têm o nº de páginas esperado.

### Fase 1 — Núcleo
- **F1.1 Models + Strategy Protocol** — `models.py`, `strategies/base.py`. Dep: F0.1.
  *Aceite:* tipos com type hints, testados por instanciação simples.
- **F1.2 Naming** — `naming.py` (título, slug, colisão). Dep: F0.2.
  *Aceite:* testes para metadado, fallback de fonte, fallback de arquivo, acentos, colisão.
- **F1.3 Writer + tokens** — `writer.py`, `tokens.py` (grava `.md`, `images/`, `meta.json`). Dep: F1.1.
  *Aceite:* teste grava pasta temporária e valida `meta.json` contra o schema dos models.

### Fase 2 — Estratégias
- **F2.1 Estratégia A (pymupdf4llm)** — `to_markdown(write_images=True, image_path=..., table_strategy="lines_strict")`,
  reescrever links de imagem para `./images/...`. Dep: F1.2, F1.3.
  *Aceite:* nos fixtures, `tabela.pdf` gera tabela GFM; `imagem.pdf` gera 1 arquivo em `images/` e 1 link.
- **F2.2 Estratégia B (docling)** — `DocumentConverter` com `PdfPipelineOptions(do_table_structure=True,
  generate_picture_images=True, do_ocr=<flag>)`, export com `ImageRefMode.REFERENCED`. Dep: F1.2, F1.3.
  *Aceite:* mesmos critérios de F2.1; testes marcados `@pytest.mark.docling` (pulados se extra ausente).

> F2.1 e F2.2 são independentes e podem ser feitos em paralelo por agentes diferentes.

### Fase 3 — Otimização LLM
- **F3.1 Pós-processamento** — `postprocess.py` com as regras da seção 5, aplicado às duas estratégias
  antes do writer. Dep: F2.1 (F2.2 recomendado).
  *Aceite:* testes unitários por regra; em `misto.pdf` cabeçalho/rodapé não aparecem no `.md`.
- **F3.2 Cache por hash** — pular conversão se `meta.json` tem o mesmo sha256. Dep: F1.3.

### Fase 4 — Comparação
- **F4.1 Normalização + métricas** — `compare/normalize.py`, `compare/metrics.py`. Dep: F1.1.
  *Aceite:* textos idênticos → 100; textos disjuntos → ~0; mesma tabela em formatos diferentes → alto.
- **F4.2 Relatórios** — `compare/report.py` (MD, JSON, CSV). Dep: F4.1.

### Fase 5 — CLI e integração
- **F5.1 CLI** — `cli.py` com `convert` e `compare`, entrada arquivo ou pasta, `--strategies`,
  `--ocr`, `--force`, `--workers`, saída `rich`. Dep: F2.*, F3.*, F4.*.
- **F5.2 Teste end-to-end** — roda CLI nos fixtures e valida a árvore de saída da seção 3. Dep: F5.1.

### Fase 6 — Entrega
- **F6.1 README** — instalação, uso, exemplo de saída, licenças, limitações. Dep: F5.2.
- **F6.2 Avaliação em PDFs reais** — rodar em `samples/`, registrar tempos, tokens e scores em
  `docs/avaliacao.md`; anotar casos onde uma estratégia é claramente melhor. Dep: F5.2.
