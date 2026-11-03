# Avaliação

## Rodada 1 — PDFs sintéticos (2026-11-03)

Ambiente: Windows 11, Python 3.12 (Anaconda), CPU apenas; pymupdf4llm 2.1, docling 2.146.0.
Comando: `pdf2md convert tests/fixtures -o output --force`.

|Documento|Págs|Tokens pymupdf|Tokens docling|Tempo pymupdf (s)|Tempo docling (s)|Score|Nível|
|---|---:|---:|---:|---:|---:|---:|---|
|documento-simples-de-teste|1|68|68|0,02|1,3|100,0|Alta|
|figura-de-exemplo|1|25|26|0,03|24,3*|100,0|Alta|
|manual-tecnico-acme|3|239|232|0,12|5,0|95,7|Alta|
|relatorio-de-vendas|1|62|62|0,04|2,1|100,0|Alta|

\* inclui o carregamento dos modelos do docling (primeiro documento do lote).

Observações:

- As duas estratégias extraem as mesmas tabelas e imagens nos fixtures; o pós-processamento
  comum deixa as saídas praticamente idênticas, o que mostra que ele também padroniza o resultado.
- `manual-tecnico-acme` (95,7): o pymupdf4llm moveu a última palavra do parágrafo da página 2
  para o cabeçalho da tabela (`|tokens.|Col2|Col3|`). O relatório de divergências aponta isso.
- A primeira execução (antes da correção em F5) deu **47,4** nesse documento: a remoção de
  cabeçalho/rodapé apagava parágrafos legítimos. A comparação entre estratégias detectou o bug.
- pymupdf é ~20 a 100× mais rápido. Para lotes grandes de PDFs "nascidos digitais", vale usar
  `-s pymupdf` e recorrer ao docling quando o score cair para Média/Baixa.

## Rodada 2 — PDFs reais (pendente)

Coloque PDFs reais em `samples/` (artigos acadêmicos com tabelas, relatórios corporativos com
cabeçalho/rodapé, um PDF escaneado) e rode:

```bash
uv run pdf2md convert samples/ -o output
uv run pdf2md convert samples/ -o output --ocr --force   # para o escaneado
```

Registre aqui a tabela de `output/_comparacao/resumo.csv`, os tempos e onde cada estratégia
foi claramente melhor.
