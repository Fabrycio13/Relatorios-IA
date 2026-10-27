# 06: Integrate IngestionPipeline in Main & Checkpoint 2

**What to build:**
Integrar o `IngestionPipeline` no arquivo `main.py`, desacoplando completamente o orquestrador principal das implementações individuais de coletores. Substituir as invocações procedurais e as branches de CLI (`--step collect`, `--step collect-twitter`, `--step collect-github`, `--step collect-papers`) por chamadas ao `pipeline.run(target_source)`. A saída do pipeline (`DailyIngestionBatch`) passa diretamente para a síntese em memória `gerar_resumo_ia(batch)`. Validar o Checkpoint 2 com testes de regressão de CLI e compatibilidade total de comandos.

**Blocked by:**
05: IngestionPipeline Orchestrator

**Status:**
completed

**Files to modify:**
- `main.py`
- `tests/test_main_integration.py`

**Acceptance criteria:**
- [x] `main.py` remove importações diretas de coletores específicos, importando apenas `IngestionPipeline` de `src.collectors`.
- [x] O fluxo diário padrão (`python main.py`) executa o pipeline e repassa o lote tipado em memória para o sintetizador de IA.
- [x] Comandos avulsos de CLI (`--step collect`, `--step collect-twitter`, `--step collect-github`, `--step collect-papers`) preservam comportamento e formato de saída idênticos.
- [x] Mensagens de log mantêm o padrão visual e de rastreabilidade.
- [x] A trava de idempotência (`data/ultimo_envio.txt`) continua protegendo a execução diária.
- [x] **CHECKPOINT 2 VALIDADO:** A Especificação 0002 está 100% funcional e aprovada antes de iniciar o DeliveryChannel.
