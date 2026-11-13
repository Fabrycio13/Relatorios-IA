# 22: Orquestração no Pipeline, Contratos da CLI e Governança Editorial de Síntese

**What to build:**
Integrar o orquestrador de coleta (`IngestionPipeline` em `src/collectors/pipeline.py`), o ponto de entrada da aplicação (`main.py`) e o sintetizador de inteligência artificial (`src/processors/ai_summarizer.py`) à nova arquitetura resiliente de snapshots.

Garantir a coordenação atômica de persistência com separação estrita da hierarquia de travas (`adquirir_trava_pipeline` na CLI versus `adquirir_trava_snapshot` no I/O de dados), registro auditável do ciclo de vida em `last_attempt`, cumprimento dos contratos operacionais de saída da CLI (`sys.exit(0)`, `sys.exit(1)`, `sys.exit(2)`), governança editorial de frescor com tratamento transparente para `legacy_unverified` e proibição absoluta de consumo de dados em estado `running` pendente.

**Blocked by:**
20 (persistência atômica e recuperação idempotente), 21 (coletores puros em memória e adaptadores)

**Status:**
blocked

**Files to modify:**
- `src/collectors/pipeline.py`
- `main.py`
- `src/processors/ai_summarizer.py`
- `tests/test_pipeline_e2e.py` (novo)

**Acceptance criteria:**
- [ ] **Orquestração Integrada em `src/collectors/pipeline.py`:**
  - `IngestionPipeline.run()` invoca os adaptadores de `src/collectors/base.py` recebendo `SourceCollectionResult[T]` de cada fonte.
  - **Zero Locks durante Scraping:** Durante a execução de todas as fontes (scraping Playwright do Twitter, APIs GitHub e Hugging Face), nenhuma trava de snapshot é retida.
  - Atualiza o manifesto inicializando `last_attempt` com status `"running"`, timestamp de início e PID do processo atual antes de iniciar o ciclo.
  - Constrói o novo `DailyIngestionBatch` preservando snapshots históricos caso uma fonte retorne `SourceStatus.FAILED` ou `NOT_RUN` (resolvendo definitivamente DEF-01).
  - Invoca `batch.save_snapshot()`, que internamente adquire `adquirir_trava_snapshot` apenas durante o I/O em disco.
  - Finaliza `last_attempt` com status `"completed"` (ou `"failed"` se o ciclo abortar), preenchendo timestamp de término.
- [ ] **Hierarquia de Travas e Contratos Operacionais da CLI em `main.py`:**
  - **Separação Estrita de Travas:** `main.py` adquire exclusivamente `adquirir_trava_pipeline(lock_file)` para proteger o ciclo macro diário (evitando disparos concorrentes do Windows Task Scheduler). Não há aninhamento de travas de snapshot nem risco de deadlock.
  - **Preservação dos Códigos de Saída (Seção 4 do `AGENTS.md`):**
    - `sys.exit(0)`: Sucesso da execução diária ou encerramento silencioso (envio já realizado no dia, ou execução antes das 08:00 sem a flag `--force`).
    - `sys.exit(1)`: Falha fatal de execução que requer intervenção e emissão de notificação Toast de erro crítico.
    - `sys.exit(2)`: Falha transitória de conectividade de rede após esgotamento de retentativas (contrato com o Windows Task Scheduler para agendamento de nova tentativa em segundo plano).
  - Suporte ao parâmetro `--step collect-<fonte>` garantindo persistência isolada da fonte alvo sem corromper metadados de fontes não executadas.
- [ ] **Governança Editorial no Sintetizador (`src/processors/ai_summarizer.py`):**
  - O gerador de relatório valida `is_source_fresh()` para cada fonte contida no `DailyIngestionBatch`.
  - **Proibição de Consumo de Execução Pendente:** Se `last_attempt.status == "running"`, o sintetizador não consome dados transitórios dessa execução, utilizando o último snapshot comitado íntegro.
  - **Tratamento Editorial de `legacy_unverified`:**
    - Dados classificados com `quality: "legacy_unverified"` são preservados no histórico e utilizados apenas em regime de contingência se não houver dados novos comprovados frescos.
    - O sintetizador **não trata dados `legacy_unverified` automaticamente como dados atuais comprovados**.
    - O prompt jornalístico instrui o modelo de IA a contextualizar explicitamente a idade dos dados e o relatório inclui advertência editorial (ex: *"Esta seção apresenta o último estado histórico coletado anteriormente, não refletindo atualizações comprovadas de hoje"*).
    - Emissão de log explícito em nível `WARNING`: `[WARNING] Fonte <nome> consumida sob regime de dados legados não comprovados (legacy_unverified).`
  - **Degradação Graciosa:** Se os dados de uma fonte estiverem obsoletos (`stale`) ou indisponíveis:
    - Não aborta a síntese da edição diária se houver pelo menos uma fonte com dados úteis (`has_usable_data`).
    - Insere uma nota de transparência editorial na seção correspondente informando a indisponibilidade momentânea daquela fonte (ex: *"A seção de tópicos do X/Twitter não pôde ser atualizada nesta edição devido a limitações operacionais da fonte"*).
    - Proíbe categoricamente a interpolação de dados de quarentena ou corrompidos no prompt jornalístico do modelo de IA.
- [ ] **Cobertura de Testes de Integração e Regressão em `tests/test_pipeline_e2e.py`:**
  - Teste de fluxo completo E2E: execução do pipeline sob mock de rede, persistência atômica correta em disco, integridade de manifesto v2 com SHA-256 e geração de preview do relatório.
  - Teste de resiliência a falhas de coleta de uma única fonte: comprovação de que as demais fontes continuam no relatório e que os dados anteriores da fonte que falhou permanecem seguros no snapshot histórico sem sobrescrita.
  - Teste de conformidade dos códigos de saída da CLI (`0`, `1`, `2`) em ambiente hermético.
  - Teste de degradação editorial no sintetizador comprovando que o aviso de transparência é gerado no Markdown quando a fonte está ausente, stale ou sob contingência `legacy_unverified`.
  - **Teste de Concorrência e Prevenção de Deadlock:** Validação de que a execução coordenada de `adquirir_trava_pipeline` na CLI e `adquirir_trava_snapshot` no I/O de persistência ocorre em sequência limpa sem travamento mútuo.
  - **Descoberta canônica no unittest:** O arquivo possui prefixo `test_` na pasta `tests/` e é executado diretamente por `python -m unittest discover -s tests -t . -v`.

**TDD & Validation Commands:**
```bash
# Execução focada dos testes de integração do pipeline
python -m unittest tests.test_pipeline_e2e -v

# Execução canônica da suíte completa de testes sob guardrails
python -m unittest discover -s tests -t . -v
```
