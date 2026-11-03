# PROGRESS — estado de execução

Status possíveis: `pendente` · `em andamento` · `concluído` · `bloqueado`.
Regras de atualização em [AGENTS.md](AGENTS.md). Detalhes de cada passo em [PLAN.md](PLAN.md#8-passos-de-execução).

## Passos

| Passo | Descrição | Depende de | Status | Agente | Data |
|-------|-----------|------------|--------|--------|------|
| F0.1 | Scaffolding (pyproject, uv, ruff, pytest, CLI vazia) | — | concluído | Claude Code | 2026-11-03 |
| F0.2 | Fixtures PDF sintéticos | F0.1 | concluído | Claude Code | 2026-11-03 |
| F1.1 | Models + Strategy Protocol | F0.1 | concluído | Claude Code | 2026-11-03 |
| F1.2 | Naming (título, slug, colisão) | F0.2 | concluído | Claude Code | 2026-11-03 |
| F1.3 | Writer + contagem de tokens | F1.1 | concluído | Claude Code | 2026-11-03 |
| F2.1 | Estratégia A — pymupdf4llm | F1.2, F1.3 | concluído | Claude Code | 2026-11-03 |
| F2.2 | Estratégia B — docling | F1.2, F1.3 | concluído | Claude Code | 2026-11-03 |
| F3.1 | Pós-processamento para LLM | F2.1 | concluído | Claude Code | 2026-11-03 |
| F3.2 | Cache por sha256 | F1.3 | concluído | Claude Code | 2026-11-03 |
| F4.1 | Normalização + métricas de similaridade | F1.1 | concluído | Claude Code | 2026-11-03 |
| F4.2 | Relatórios de comparação (MD/JSON/CSV) | F4.1 | concluído | Claude Code | 2026-11-03 |
| F5.1 | CLI convert/compare | F2.*, F3.*, F4.* | concluído | Claude Code | 2026-11-03 |
| F5.2 | Teste end-to-end | F5.1 | concluído | Claude Code | 2026-11-03 |
| F6.1 | README final | F5.2 | concluído | Claude Code | 2026-11-03 |
| F6.2 | Avaliação em PDFs reais | F5.2 | concluído | Claude Code | 2026-11-03 |

## Pendências / ideias fora de escopo

- Avaliar mais tipos de PDF: artigo com tabelas mescladas, layout em colunas, escaneado com `--ocr` (ver `docs/avaliacao.md`).
- Título: metadado `Title` que é só identificador (ex. "PDF 6005449/2026-00" do SEI) poderia perder para o nome do arquivo quando este for mais descritivo.
- pymupdf4llm não detecta títulos quando toda a fonte tem o mesmo tamanho (2 contra 165 do docling no PDF SEI); avaliar `hdr_info`/TocHeaders ou heurística por negrito.
- Testar se uma versão mais antiga do `onnxruntime` permite reativar o modo layout do pymupdf4llm (talvez como 3ª estratégia `pymupdf-layout`).
- Silenciar o `DeprecationWarning` de `force_full_page_ocr` que o docling/pydantic emite nos testes.

## Log de handoff

Entradas mais recentes no fim.

### 2026-11-03 — Planejamento — Claude Code
- Feito: criados PLAN.md, AGENTS.md, CLAUDE.md, GEMINI.md, PROGRESS.md, .gitignore e pastas `samples/`, `output/`.
- Verificação: nenhuma (ainda não há código).
- Decisões: estratégia A = `pymupdf4llm` (rápida, sem GPU); estratégia B = `docling` (layout/tabelas por modelo).
  Pastas de saída irmãs `<titulo>__pymupdf` e `<titulo>__docling`; comparação em `output/_comparacao/`.
- Atenção próximo agente: `docling` baixa modelos no primeiro uso (~centenas de MB); mantê-lo como extra opcional.
- Próximo passo sugerido: F0.1

### 2026-11-03 — F0.1, F0.2 — Claude Code
- Feito: `pyproject.toml` (hatchling, extras `docling`/`dev`), CLI vazia, `tests/fixtures/make_fixtures.py` (4 PDFs) + fixture `pdfs` no conftest.
- Verificação: `pytest` 2 passed.
- Decisões: venv usa o Python 3.12 do Anaconda (`.python-version`); o download de Python pelo uv falhou nesta máquina.
- Atenção próximo agente: `uv` foi instalado em `%APPDATA%\Python\Python312\Scripts` (fora do PATH). Use `uv run --no-sync ...` depois de `uv sync --extra dev --extra docling`, senão `uv run` remove o extra docling.

### 2026-11-03 — F1.1, F1.2, F1.3 — Claude Code
- Feito: `models.py`, `strategies/base.py` + registro `get_strategy`, `naming.py` (título/slug/colisão/sha256), `writer.py`, `tokens.py`.
- Verificação: testes `test_models`, `test_naming`, `test_writer` passando.
- Decisões: contagem de tabelas/imagens/títulos é feita sobre o markdown final (`writer.count_structure`), igual para as duas estratégias. `tiktoken` baixa o encoding no 1º uso; sem rede, cai para estimativa chars/4 (registrado em `tokens_method`).

### 2026-11-03 — F2.1, F2.2 — Claude Code
- Feito: `strategies/pymupdf_strategy.py` e `strategies/docling_strategy.py`; `tests/test_strategies.py` parametrizado nas duas.
- Verificação: `pytest` 23 passed (docling incluído, ~40 s com modelos em cache).
- Decisões: **pymupdf4llm em modo legado** (`use_layout(False)`): o modo layout importa `onnxruntime`, que dá segfault neste ambiente, e o modo legado mantém a estratégia A puramente heurística. Docling: `save_as_markdown` com `artifacts_dir=Path("images")` relativo gera links `images/...`.
- Atenção próximo agente: saída da A traz cabeçalho/rodapé repetidos, linhas quebradas e às vezes funde a última linha do parágrafo na tabela (`|tokens.|Col2|Col3|`); docling usa tabelas com padding e nomes de imagem com hash. Docling baixa modelos do HuggingFace no 1º uso.

### 2026-11-03 — F3.1, F3.2 — Claude Code
- Feito: `postprocess.py` (base64, imagens minúsculas/duplicadas/órfãs, renomeia `img-NNN`, números de página, cabeçalho/rodapé repetidos, negrito em títulos/células, tabelas compactas, reflow de parágrafos com des-hifenização, colapso de espaços; blocos ``` intactos) e `pipeline.py` (`convert_one` com cache por sha256 e gravação atômica via pasta `.tmp`).
- Verificação: `pytest -m "not docling"` 28 passed.
- Decisões: novo módulo `pipeline.py` (não previsto no PLAN) concentra cache+conversão+gravação, para a CLI ficar fina. Repetição de cabeçalho exige ≥ max(3, 50% das páginas); dígitos só são ignorados em linhas curtas sem pontuação final (evita apagar frases do corpo).

### 2026-11-03 — F4.1, F4.2 — Claude Code
- Feito: `compare/normalize.py`, `compare/metrics.py` (ratio, token_set, jaccard_3gram, paragraph_diff, score ponderado, nível, divergências), `compare/report.py` (`compare_folders`, relatório MD/JSON, `resumo.csv` recriado a partir dos JSON).
- Verificação: `pytest -m "not docling"` 35 passed.
- Decisões: `line_diff` do PLAN virou `paragraph_diff` (SequenceMatcher sobre parágrafos já normalizados; linhas físicas variam muito entre estratégias). Divergências = parágrafos de A sem correspondência aproximada (`partial_ratio` < 80) em B. CSV com BOM para abrir direto no Excel.

### 2026-11-03 — F5.1, F5.2 (+ correção em F3.1) — Claude Code
- Feito: `cli.py` com `convert` (arquivo ou pasta recursiva, `--strategies`, `--ocr`, `--force`, `--workers`, `--compare/--no-compare`, tabelas `rich`, exit 1 se algum PDF falhar) e `compare`. `tests/test_cli.py` com e2e nas duas estratégias.
- Correção F3.1: a 1ª execução real mostrou score 47 (Baixa) em `misto.pdf` — a remoção de cabeçalho/rodapé por repetição no documento inteiro apagava parágrafos repetidos e títulos "Seção N". Agora as estratégias inserem `PAGE_BREAK` (`page_chunks=True` no pymupdf4llm, `page_break_placeholder` no docling) e só as 2 primeiras/últimas linhas de cada página, repetidas em ≥ 75% das páginas, são removidas (títulos/tabelas/imagens nunca). Score passou a 95.7.
- Verificação: `pytest` 45 passed (~50 s com docling); `pdf2md convert tests/fixtures -o output` OK.
- Atenção próximo agente: diferença residual em `manual-tecnico-acme` é real — pymupdf4llm move a última linha do parágrafo para dentro da tabela (`|tokens.|Col2|Col3|`).

### 2026-11-03 — F6.2 — Claude Code
- Feito: rodada 2 em PDF real (processo SEI, 80 págs) registrada em `docs/avaliacao.md`. Score 88,2 (Média); texto ~97% igual, diferença vem da segmentação. docling: 15× mais lento, 9% menos tokens, 165 títulos contra 2.
- Correção F3.1: deduplicação de imagens quase idênticas (tamanho ±2 px e diferença média de pixel ≤ 2,5, na resolução nativa). Testei dHash antes e ele fundia QR codes distintos; descartado. Calibração documentada em `postprocess.py`.
- Verificação: `pytest` 46 passed; conferência visual das imagens restantes (QR codes todos preservados).
- Decisões: o PDF de teste fica na raiz e é ignorado pelo git (`/*.pdf` no `.gitignore`), pois pode conter dados internos.

### 2026-11-03 — Pós-plano: imagens repetitivas, progresso, Linux — Claude Code
- Feito: (1) `postprocess.process_images` agrupa cópias da mesma figura (numpy, tolera recorte deslocado ±4 px e tamanho ±8 px, diferença média ≤ 9) e remove por inteiro figuras com ≥ `--image-repeat-limit` (padrão 3) ocorrências; cache agora considera as opções. (2) Estratégias aceitam `progress(done, total)`: docling via `progress_callback` nativo (`PageCompletedProgress`), pymupdf4llm em lotes de 10 páginas com `IdentifyHeaders` calculado uma vez. CLI com barra Total em %, barra de páginas por documento e painel final "Grau de semelhança". (3) `scripts/setup_linux.sh` (venv + pip, torch CPU; fallback get-pip.py se faltar `python3-venv`), `.gitattributes` com LF para `.sh`, README com instruções Linux.
- Verificação: Windows `pytest` 49 passed; WSL Ubuntu 26.04 / Python 3.14: setup em 1m43 (venv 2,1 GB), `pytest` 49 passed, PDF SEI convertido (27/31 imagens, semelhança 88,1%).
- Atenção próximo agente: um selo SEI em escala menor (57×84) que aparece 1 vez continua no docling — não é repetitivo pela contagem; pegar exigiria comparação entre escalas, com risco de fundir QR codes.
