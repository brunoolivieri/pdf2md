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

## Rodada 2 — PDF real (2026-11-03)

Documento: processo SEI exportado (wkhtmltopdf), 80 páginas, texto digital (sem OCR): termos,
notas técnicas, portarias, tabelas, gráficos, e brasão/selo de assinatura/QR code em cada
documento interno. O PDF não é versionado.

|Item|pymupdf|docling|
|---|---:|---:|
|Tempo (s)|8,2|125,2|
|Tokens (o200k)|36 873|33 514|
|Palavras|19 199|18 852|
|Títulos (`#`)|2|165|
|Tabelas|4|4|
|Imagens (após dedupe)|33|59|

**Semelhança: 88,2 (Média)**: ratio 97,2 · token_set 97,8 · jaccard_3gram 82,0 · paragraph_diff 50,7.

Observações:

- **Texto praticamente igual** (ratio e token_set ~97–98). A nota Média vem da segmentação:
  as estratégias quebram parágrafos e blocos de assinatura em lugares diferentes, o que derruba
  `paragraph_diff` e os 3-gramas.
- **docling é ~15× mais lento, mas entrega estrutura**: 165 títulos contra 2. Neste PDF toda a
  fonte tem 12 pt, e a heurística do pymupdf4llm (tamanho de fonte) não acha títulos; o modelo de
  layout do docling acha. Para RAG/chunking por seção, o docling é claramente melhor aqui.
- **docling gasta ~9% menos tokens**: remove rodapés de citação ("Fonte: … pg. N") e URLs de
  impressão que o pymupdf mantém, pois aparecem só em algumas páginas e não passam no critério
  de repetição em ≥ 75% das páginas.
- **Título da pasta**: `pdf-6005449-2026-00`, vindo do metadado `Title` gerado pelo SEI. É o
  identificador do processo; o nome do arquivo ("… rate limit") seria mais descritivo.
- **Imagens**: a 1ª execução mostrou dezenas de cópias do brasão e do selo "SEI assinatura
  eletrônica" (o docling recorta cada cópia com bytes diferentes). Testei hash perceptual (dHash)
  para colapsar quase-duplicatas, mas ele também fundia QR codes distintos. A regra adotada é
  conservadora: tamanho ±2 px e diferença média de pixel ≤ 2,5. Ela removeu as cópias exatas
  (35→33 no pymupdf, 74→59 no docling) e preservou todos os QR codes. Restam algumas cópias de
  logo recortadas com deslocamento.

**Recomendação de uso**: pymupdf para triagem rápida e barata de lotes; docling quando a
estrutura (títulos/seções) importa ou quando o score cair para Média/Baixa.

## Próximas rodadas sugeridas

Ainda faltam: artigo acadêmico com tabelas complexas (células mescladas), relatório com
múltiplas colunas e um PDF escaneado (`--ocr`).
