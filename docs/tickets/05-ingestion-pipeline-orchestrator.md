# 05: IngestionPipeline Orchestrator

**What to build:**
Criar a classe `IngestionPipeline` em `src/collectors/pipeline.py` para orquestrar a execução das fontes que implementam `IngestionSource`. O pipeline centraliza o registro das fontes ativas padrão (`TwitterSource`, `GitHubSource`, `HuggingFaceSource`) e expõe o método `run(target_source: str | None = None) -> DailyIngestionBatch`. O orquestrador centraliza os logs de início e término de cada coleta, captura falhas/exceções individuais com `logger.warning` sem derrubar as outras fontes (mantendo a política de falha estável e tolerância a falhas parciais) e aciona `batch.save_snapshot()` preventivamente ao final da execução.

**Blocked by:**
04: IngestionSource Protocol and Adapters

**Status:**
completed

**Files to modify:**
- `src/collectors/pipeline.py`
- `src/collectors/__init__.py`
- `tests/test_ingestion_pipeline.py`

**Acceptance criteria:**
- [x] `IngestionPipeline` gerencia as fontes que implementam `IngestionSource`.
- [x] `pipeline.run()` sem parâmetros (ou `"all"`) executa as 3 fontes em sequência e retorna `DailyIngestionBatch` consolidado.
- [x] `pipeline.run("github")` (ou `"twitter"`, `"papers"`) executa exclusivamente a fonte requisitada.
- [x] Falha não tratada em qualquer coletor é capturada com `logger.warning`, preenchendo a entidade correspondente com lista vazia `[]` e permitindo que as outras fontes concluam.
- [x] `batch.save_snapshot()` grava o snapshot atômico em `data/` após a coleta.
- [x] Testes unitários em `tests/test_ingestion_pipeline.py` validam com mocks: execução de todas as fontes, execução isolada por nome de fonte e resiliência a exceções inesperadas.
