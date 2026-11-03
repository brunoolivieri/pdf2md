# AGENTS.md — Protocolo de cooperação

Este repositório é desenvolvido em conjunto por **Claude Code**, **Codex** e **Gemini CLI**.
Qualquer agente deve conseguir continuar exatamente do ponto onde o anterior parou.
Este arquivo é a fonte única de regras; `CLAUDE.md` e `GEMINI.md` apenas apontam para cá.

## Arquivos de coordenação

| Arquivo | Papel | Quem edita |
|---------|-------|------------|
| [PLAN.md](PLAN.md) | O quê e por quê: arquitetura, passos, critérios de aceite | Só com pedido explícito do usuário |
| [PROGRESS.md](PROGRESS.md) | Estado de cada passo + log de handoff | Todo agente, a cada passo |
| `AGENTS.md` | Este protocolo | Só com pedido explícito do usuário |

## Ciclo de trabalho (obrigatório)

1. **Sincronize**: `git pull` (se houver remoto) e `git status`. Árvore suja que não é sua → pare e avise o usuário.
2. **Leia** `PROGRESS.md` inteiro, em especial a última entrada do *Log de handoff*.
3. **Escolha** o primeiro passo `pendente` cujas dependências (ver PLAN.md) estão `concluído`.
   Se o usuário indicou um passo específico, use esse.
4. **Reivindique**: mude o status para `em andamento`, preencha *Agente* e *Data*, e faça commit
   `chore(progress): inicia F<x.y>` — isso evita que dois agentes peguem o mesmo passo.
5. **Implemente** apenas o escopo do passo. Encontrou algo fora do escopo? Registre em *Pendências* no PROGRESS.md.
6. **Verifique**: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Tudo verde.
7. **Conclua**: status `concluído`, adicione entrada no *Log de handoff* (modelo abaixo), commit único:
   `feat(F<x.y>): <resumo>` (ou `fix`/`test`/`docs`).
8. Um passo por vez. Não comece o próximo sem concluir/registrar o atual.

Passo travado (`em andamento` sem commit há mais de 1 dia, ou bloqueado)? Marque `bloqueado`,
explique no log e escolha outro passo — não sobrescreva o trabalho de outro agente.

## Modelo de entrada no Log de handoff

```markdown
### 2026-11-03 — F2.1 — Claude Code
- Feito: <o que foi implementado, arquivos principais>
- Verificação: <comandos rodados e resultado>
- Decisões: <escolhas não óbvias e por quê>
- Atenção próximo agente: <armadilhas, TODOs, testes frágeis>
- Próximo passo sugerido: F2.2
```

## Convenções de código

- Python ≥ 3.11, gerenciado com `uv`. Dependências só via `uv add` (atualiza `pyproject.toml` e `uv.lock`).
- `docling` é extra opcional; código que o importa deve fazê-lo dentro da estratégia B, nunca no topo de módulos comuns.
- Código e identificadores em **inglês**; documentação, mensagens de CLI e relatórios em **português**.
- Type hints em toda função pública; `ruff` é a lei (config no `pyproject.toml`).
- Testes em `tests/`, usando os PDFs de `tests/fixtures/` (gerados por script, nunca binários grandes versionados).
- Testes que dependem de `docling` usam `@pytest.mark.docling` e são pulados se o extra não estiver instalado.
- Nada de chamadas de rede ou APIs de LLM no pipeline de conversão.
- `output/` e `samples/*.pdf` não são versionados.

## Comandos

```bash
uv sync --extra dev                  # dev sem docling
uv sync --extra dev --extra docling  # tudo
uv run pytest                        # testes
uv run pytest -m "not docling"       # testes rápidos
uv run ruff check . --fix && uv run ruff format .
uv run pdf2md convert samples/ -o output
```
