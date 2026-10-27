# 03: Integrate DailyIngestionBatch in Main & Checkpoint 1

**What to build:**
Integrar o `DailyIngestionBatch` no fluxo de execução do arquivo `main.py`. Ao final das etapas de coleta (1 a 3), instanciar `DailyIngestionBatch` com as listas retornadas pelos coletores, salvar o snapshot preventivo em `data/` via `batch.save_snapshot()` e repassar o objeto `batch` em memória diretamente para `gerar_resumo_ia(batch)`. Executar testes de regressão para assegurar compatibilidade integral com `--step all` e `--step summarize`, concluindo o Checkpoint 1.

**Blocked by:**
02: Adapt Summarizer to DailyIngestionBatch

**Status:**
completed

**Files to modify:**
- `main.py`
- `tests/test_main_integration.py`

**Acceptance criteria:**
- [x] No comando padrão `python main.py`, a síntese consome o lote em memória sem releitura do disco.
- [x] O snapshot em `data/*.json` é atualizado atomicamente após a coleta como garantia de recuperação em falha.
- [x] O comando avulso `python main.py --step summarize` carrega os dados do snapshot em disco e gera o relatório normalmente.
- [x] A trava diária (`data/ultimo_envio.txt`) permanece registrando o dia de envio com idempotência.
- [x] Todos os testes unitários existentes e novos passam sem erros.
- [x] **CHECKPOINT 1 VALIDADO:** A Especificação 0001 está 100% funcional e aprovada antes de prosseguir para o Protocolo de Ingestão.
