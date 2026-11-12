# 21: Coletores Puros em Memória, Adaptadores de Coleta e Desacoplamento Total de I/O

**What to build:**
Refatorar os três coletores da camada de ingestão (`src/collectors/twitter.py`, `src/collectors/github.py` e `src/collectors/huggingface.py`), o protocolo `IngestionSource` e os adaptadores de coleta em `src/collectors/base.py`, além de atualizar a suíte de testes de protocolo em `tests/test_collectors_protocol.py`, eliminando definitivamente o débito arquitetural ARC-01.

Remover completamente todas as operações de escrita em disco (`open(..., "w")`, `json.dump`, `Path.write_text`) de dentro dos coletores, transformando-os em componentes puros em memória. Migrar formalmente o retorno do método `collect()` em `IngestionSource` e nos adaptadores (`TwitterSource`, `GitHubSource`, `HuggingFaceSource`) de `list[Any]` para `SourceCollectionResult[T]`, eliminando a conversão silenciosa de exceções para listas vazias `[]`, adaptando os testes de protocolo e documentando o desacoplamento para os consumidores intermediários.

**Blocked by:**
17 (modelos imutáveis e invariantes de resultado)

**Status:**
blocked

**Files to modify:**
- `src/collectors/base.py`
- `src/collectors/twitter.py`
- `src/collectors/github.py`
- `src/collectors/huggingface.py`
- `tests/test_collectors_protocol.py`
- `tests/test_collectors_pure.py` (novo)

**Acceptance criteria:**
- [ ] **Desacoplamento de I/O nos Coletores:**
  - `src/collectors/twitter.py`: Remoção de escrita em `tweets_coletados.json`. Função `coletar_tweets_vip()` retorna `SourceCollectionResult[Tweet]`. Em caso de rate limit, retorna `status=SourceStatus.PARTIAL` ou `FAILED` com flag `rate_limited=True`. Em caso de erro de rede ou Playwright, retorna `status=SourceStatus.FAILED` com detalhes em `error_message`.
  - `src/collectors/github.py`: Remoção de escrita em `github_trending.json`. Função `coletar_github_trending()` retorna `SourceCollectionResult[GitHubRepo]`. Lista vazia legítima retorna `status=SourceStatus.EMPTY`. Exceções retornam `status=SourceStatus.FAILED`.
  - `src/collectors/huggingface.py`: Remoção de escrita em `hf_papers.json`. Função `coletar_papers_huggingface()` retorna `SourceCollectionResult[ResearchPaper]`. Exceções retornam `status=SourceStatus.FAILED`.
- [ ] **Migração Contratual do Protocolo e Adaptadores (`src/collectors/base.py`):**
  - **Atualização do Protocolo `IngestionSource`:** Assinatura formal de `collect()` migra para `def collect(self) -> SourceCollectionResult[Any]: ...`.
  - **Retorno Tipado em `TwitterSource`, `GitHubSource` e `HuggingFaceSource`:** O método `collect()` de cada classe adaptadora passa a retornar diretamente `SourceCollectionResult[T]` com entidades imutáveis (`items: tuple[T, ...]`), status explícito (`SourceStatus`) e contadores.
  - **Eliminação Absoluta da Conversão Silenciosa para `[]`:** Os blocos `try/except` dos adaptadores não mascaram falhas retornando listas vazias. Exceções são capturadas para construir um `SourceCollectionResult` com `status=SourceStatus.FAILED`, `items=()`, `failed_operations=1` e `error_message=str(e)`.
  - **Suporte a Consumidores Intermediários:** Consumidores que necessitarem de iteração plana acessam diretamente `result.items` condicionado a `result.has_usable_data`, sem ambiguidades entre "fonte vazia legítima" e "falha operacional de coleta".
- [ ] **Atualização da Suíte de Testes de Protocolo (`tests/test_collectors_protocol.py`):**
  - Adaptação das asserções de sucesso para verificar `result.status == SourceStatus.SUCCESS` e `len(result.items) == 1`.
  - Adaptação dos testes de falha graciosa: simulações de exceção (`RuntimeError`, `API Rate Limit`, `Timeout`) comprovam que `source.collect()` retorna `SourceCollectionResult` com `status=SourceStatus.FAILED`, `items == ()` e mensagem de erro preservada, e NÃO `[]`.
- [ ] **Garantia de Pureza de Memória e Zero Locks durante Scraping:**
  - Nenhum coletor ou adaptador importa funções de persistência nem interage com arquivos em `data/`.
  - Toda chamada demorada de Playwright ou requisição de rede HTTP é executada livre de travas de snapshot (`adquirir_trava_snapshot`), garantindo concorrência limpa e ausência de bloqueios em cascata.
- [ ] **Cobertura de Testes Unitários em `tests/test_collectors_pure.py`:**
  - Testes com mocks para cada coletor e adaptador validando a emissão de `SourceCollectionResult`.
  - Testes comprovando que nenhuma chamada a `open()` em modo de escrita ocorre nos coletores.
  - Testes comprovando que falhas de rede ou scraping geram `SourceCollectionResult` com `status=FAILED` e `error_message`, em vez de retornar silenciosamente lista vazia.
  - **Descoberta canônica no unittest:** O arquivo possui prefixo `test_` na pasta `tests/` e é executado diretamente por `python -m unittest discover -s tests -t . -v`.

**TDD & Validation Commands:**
```bash
# Execução focada dos testes de coletores puros em memória
python -m unittest tests.test_collectors_pure -v

# Validação da nova assinatura nos testes de protocolo
python -m unittest tests.test_collectors_protocol -v

# Execução canônica da suíte completa sob guardrails
python -m unittest discover -s tests -t . -v
```
