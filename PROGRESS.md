# PROGRESS — estado de execução

Status possíveis: `pendente` · `em andamento` · `concluído` · `bloqueado`.
Regras de atualização em [AGENTS.md](AGENTS.md). Detalhes de cada passo em [PLAN.md](PLAN.md#8-passos-de-execução).

## Passos

| Passo | Descrição | Depende de | Status | Agente | Data |
|-------|-----------|------------|--------|--------|------|
| F0.1 | Scaffolding (pyproject, uv, ruff, pytest, CLI vazia) | — | pendente | | |
| F0.2 | Fixtures PDF sintéticos | F0.1 | pendente | | |
| F1.1 | Models + Strategy Protocol | F0.1 | pendente | | |
| F1.2 | Naming (título, slug, colisão) | F0.2 | pendente | | |
| F1.3 | Writer + contagem de tokens | F1.1 | pendente | | |
| F2.1 | Estratégia A — pymupdf4llm | F1.2, F1.3 | pendente | | |
| F2.2 | Estratégia B — docling | F1.2, F1.3 | pendente | | |
| F3.1 | Pós-processamento para LLM | F2.1 | pendente | | |
| F3.2 | Cache por sha256 | F1.3 | pendente | | |
| F4.1 | Normalização + métricas de similaridade | F1.1 | pendente | | |
| F4.2 | Relatórios de comparação (MD/JSON/CSV) | F4.1 | pendente | | |
| F5.1 | CLI convert/compare | F2.*, F3.*, F4.* | pendente | | |
| F5.2 | Teste end-to-end | F5.1 | pendente | | |
| F6.1 | README final | F5.2 | pendente | | |
| F6.2 | Avaliação em PDFs reais | F5.2 | pendente | | |

## Pendências / ideias fora de escopo

- (vazio)

## Log de handoff

Entradas mais recentes no fim.

### 2026-11-03 — Planejamento — Claude Code
- Feito: criados PLAN.md, AGENTS.md, CLAUDE.md, GEMINI.md, PROGRESS.md, .gitignore e pastas `samples/`, `output/`.
- Verificação: nenhuma (ainda não há código).
- Decisões: estratégia A = `pymupdf4llm` (rápida, sem GPU); estratégia B = `docling` (layout/tabelas por modelo).
  Pastas de saída irmãs `<titulo>__pymupdf` e `<titulo>__docling`; comparação em `output/_comparacao/`.
- Atenção próximo agente: `docling` baixa modelos no primeiro uso (~centenas de MB); mantê-lo como extra opcional.
- Próximo passo sugerido: F0.1
