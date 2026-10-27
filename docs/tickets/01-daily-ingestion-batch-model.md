# 01: DailyIngestionBatch Model

**What to build:**
Criar o dataclass `DailyIngestionBatch` em `src/core/models.py` para servir como estrutura tipada unificada de dados em memória entre as etapas de coleta e síntese. O modelo encapsula coleções de `Tweet`, `GitHubRepo` e `ResearchPaper`, além do timestamp de coleta `collected_at`. Deve incluir métodos para serialização (`to_dict`), desserialização (`from_dict`), verificação de vazio (`is_empty`) e persistência atômica de snapshot em disco (`save_snapshot` e `load_snapshot`).

**Blocked by:**
None (can start immediately)

**Status:**
completed

**Files to modify:**
- `src/core/models.py`
- `src/core/__init__.py`
- `tests/test_models.py`

**Acceptance criteria:**
- [x] O modelo `DailyIngestionBatch` é definido como dataclass contendo `tweets: list[Tweet]`, `repos: list[GitHubRepo]`, `papers: list[ResearchPaper]` e `collected_at: str`.
- [x] `DailyIngestionBatch.is_empty()` retorna `True` quando todas as listas de dados estiverem vazias.
- [x] `to_dict()` e `from_dict()` realizam conversão bidirecional sem perda de tipos ou campos.
- [x] `save_snapshot(data_dir)` grava atomicamente os arquivos `tweets_coletados.json`, `github_trending.json` e `hf_papers.json` no diretório fornecido.
- [x] `load_snapshot(data_dir)` reconstitui o `DailyIngestionBatch` a partir dos arquivos JSON existentes, lidando graciosamente com arquivos ausentes (retornando listas vazias).
- [x] Testes unitários novos em `tests/test_models.py` validam todos os métodos com 100% de cobertura.
