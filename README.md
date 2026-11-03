# pdf2md
PDF to .MD file convertion focusing on LLM usage

Converte PDFs em Markdown enxuto para LLMs usando duas estratégias locais
(`pymupdf4llm` e `docling`), extrai imagens e tabelas, e mede a semelhança entre os resultados.

**Status:** em planejamento. Veja [PLAN.md](PLAN.md) e o andamento em [PROGRESS.md](PROGRESS.md).

## Desenvolvimento com agentes

Projeto preparado para Claude Code, Codex e Gemini CLI trabalharem em sequência.
Regras em [AGENTS.md](AGENTS.md) (Codex lê direto; `CLAUDE.md` e `GEMINI.md` importam esse arquivo).
Para continuar, basta pedir a qualquer agente: *"continue o próximo passo do PROGRESS.md"*.
