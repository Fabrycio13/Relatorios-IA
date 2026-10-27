# 04: IngestionSource Protocol and Adapters

**What to build:**
Criar a interface `IngestionSource` em `src/collectors/base.py` utilizando `typing.Protocol` nativo da biblioteca padrão do Python. A interface define `name: str` e o método `collect() -> list[Any]`. Criar adaptadores leves (`TwitterSource`, `GitHubSource`, `HuggingFaceSource`) que encapsulam as chamadas existentes sem modificar a lógica interna de scraping ou HTTP. Manter a política estável de falha graciosa: qualquer erro na fonte é logado como warning e retorna lista vazia.

**Blocked by:**
03: Integrate DailyIngestionBatch in Main & Checkpoint 1

**Status:**
completed

**Files to modify:**
- `src/collectors/base.py`
- `src/collectors/__init__.py`
- `tests/test_collectors_protocol.py`

**Acceptance criteria:**
- [x] O protocolo `IngestionSource` está definido com o atributo `name: str` e o método `collect() -> list[Any]`.
- [x] `TwitterSource` implementa `IngestionSource` e invoca `coletar_tweets_vip(headless=True)`.
- [x] `GitHubSource` implementa `IngestionSource` e invoca `coletar_github_trending()`.
- [x] `HuggingFaceSource` implementa `IngestionSource` e invoca `coletar_papers_huggingface()`.
- [x] A política de falhas não é alterada: timeouts ou erros parciais de rede geram `logger.warning` e retornam `[]`.
- [x] Testes unitários comprovam a conformidade de cada adaptador com o protocolo `IngestionSource`.
