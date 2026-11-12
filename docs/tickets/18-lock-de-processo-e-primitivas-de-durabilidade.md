# 18: Lock de Processo de Snapshot e Primitivas de Durabilidade de Filesystem

**What to build:**
Implementar o gerenciador de contexto de bloqueio exclusivo de persistência de snapshots (`adquirir_trava_snapshot`) em `src/core/lock.py`, com isolamento estrito entre a rotina de retentativas de aquisição e a execução do bloco do chamador via `contextlib.ExitStack` e temporizador monotônico (`time.monotonic()`).

Formalizar a hierarquia e separação de responsabilidades entre as travas do sistema:
1. **Trava de Pipeline (`adquirir_trava_pipeline`):** Já existente em `src/core/lock.py`, adquirida exclusivamente em `main.py` para proteger o ciclo macro de envio diário contra execuções duplicadas do Windows Task Scheduler (comportamento *fail-fast* imediato sem espera).
2. **Trava de Persistência de Snapshots (`adquirir_trava_snapshot`):** Nova trava focada exclusivamente em proteger a integridade física de arquivos em disco (`snapshot_metadata.json`, `tweets_coletados.json`, etc.) contra corrupção em concorrência entre passos (`--step`). É adquirida e liberada **estritamente durante o I/O em disco** (no `save_snapshot()`), sendo expressamente proibido mantê-la durante scraping ou chamadas de rede/HTTP demoradas.

Implementar também os utilitários de sincronização de metadados de sistema de arquivos (`_fsync_dir`), garantindo disciplina de durabilidade POSIX (`fsync` em descritor de diretório) e no-op documentado e seguro em Windows NTFS, rotinas de quarentena segura e teste explícito de prevenção contra deadlock e timeout configurável.

**Blocked by:**
None (independente; primitivas de infraestrutura e filesystem)

**Status:**
ready-for-agent

**Files to modify:**
- `src/core/lock.py`
- `tests/test_snapshot_lock.py` (novo)

**Acceptance criteria:**
- [ ] **Context Manager `adquirir_trava_snapshot(lock_path: Path, timeout: float = 10.0, retry_delay: float = 0.2)`:**
  - Implementado em `src/core/lock.py` utilizando `contextlib.contextmanager` e `contextlib.ExitStack`.
  - **Justificativa do Timeout Padrão (10.0s):** Como a trava protege exclusivamente gravações de arquivos e atualizações de manifesto em disco (operações locais que duram de dezenas a poucas centenas de milissegundos), o timeout padrão é configurado em 10.0s com retentativas a cada 0.2s. Isso permite que processos concorrentes de `--step` pontuais aguardem a finalização do I/O sem abortar de forma precipitada, evitando reter processos por 60s desnecessários caso ocorra qualquer contenção anômala.
  - Controle de prazo limite via `deadline = time.monotonic() + timeout` imune a ajustes de relógio do sistema (NTP/drift).
  - Loop de retry encapsulado que tenta abrir o arquivo em modo `"a+b"` e aplicar lock exclusivo não-bloqueante:
    - No Windows (`os.name == "nt"`): `msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)`.
    - No POSIX (`os.name != "nt"`): `fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)`.
  - Tratamento de exceções de contenção (`BlockingIOError`, `PermissionError`, `OSError`) com fechamento limpo do handle intermediário via `stack.close()` e espera de `retry_delay` segundos.
  - Lança `TimeoutError` detalhado caso `time.monotonic() >= deadline`.
  - **Desacoplamento Estrito do Bloco do Chamador:** Uma vez adquirido o lock com sucesso, o bloco do chamador é executado dentro de `with stack: yield lock_file`. Nenhuma exceção de negócio levantada dentro do bloco do chamador é capturada pelo loop de retry de aquisição.
  - Liberação limpa e determinística do lock e fechamento do descritor na saída normal ou excepcional do context manager.
- [ ] **Hierarquia de Travas e Prevenção de Aninhamento / Deadlock:**
  - Documentação explícita da separação: `adquirir_trava_pipeline` gerencia o ciclo macro diário no `main.py`; `adquirir_trava_snapshot` gerencia o I/O em `DailyIngestionBatch.save_snapshot()`.
  - Proibição de aquisição aninhada da mesma trava de snapshot: como `msvcrt` e `fcntl` não fornecem garantia uniforme de reentrância por thread/processo em nível de handle, o context manager valida que o caminho de lock não seja re-adquirido de forma aninhada.
  - Garantia de que nenhuma rotina mantenha `adquirir_trava_snapshot` ativa durante scraping do Playwright ou requisições HTTP de rede.
- [ ] **Primitiva de Sincronização de Diretório `_fsync_dir(dir_path: Path)`:**
  - No POSIX: abre o descritor de diretório via `os.open(str(dir_path), os.O_RDONLY)`, invoca `os.fsync(fd)` e fecha o descritor no bloco `finally`.
  - No Windows (`os.name == "nt"`): documentado explicitamente como no-op seguro, visto que o Win32 não suporta `fsync` em diretórios e delega a durabilidade de metadados ao journaling NTFS (`$LogFile`).
  - Tratamento resiliente de `OSError` no POSIX para não interromper pipelines em sistemas de arquivos que não suportem sync de diretório.
- [ ] **Helper de Quarentena Segura e Nomenclatura Única:**
  - Função auxiliar `mover_para_quarentena(file_path: Path, quarantine_dir: Path) -> Path`.
  - Criação automática do diretório de quarentena com permissões adequadas e `_fsync_dir(quarantine_dir.parent)` no POSIX.
  - Geração de nome único com formato: `<stem>_<YYYYmmddTHHMMSS_microseconds>_<uuid4[:8]><suffix>.corrupted`.
  - Movimentação atômica via `os.replace` e sincronização de metadados em ambos os diretórios (origem e destino) no POSIX via `_fsync_dir`.
- [ ] **Cobertura de Testes Unitários em `tests/test_snapshot_lock.py`:**
  - Teste de aquisição e liberação normal em diretório temporário.
  - Teste de contenção de lock: dois processos ou threads concorrentes no mesmo arquivo, comprovando que o segundo aguarda ou atinge timeout configurado.
  - Teste comprovando que exceções levantadas dentro do bloco `with adquirir_trava_snapshot(...)` não disparam novas tentativas de lock.
  - Teste de mock de `_fsync_dir` comprovando abertura com `O_RDONLY` e chamada de `os.fsync` em POSIX e no-op em Windows.
  - Teste de geração e movimentação única de quarentena sem colisão.
  - **Teste contra Deadlock:** Validação de que múltiplas aquisições e liberações sucessivas em curto intervalo não travam descritores e liberam o lock imediatamente para os próximos concorrentes.
  - **Descoberta canônica no unittest:** O arquivo possui prefixo `test_` na pasta `tests/` e é executado diretamente por `python -m unittest discover -s tests -t . -v`.

**TDD & Validation Commands:**
```bash
# Execução focada dos testes de lock e durabilidade
python -m unittest tests.test_snapshot_lock -v

# Execução canônica da suíte completa sob guardrails
python -m unittest discover -s tests -t . -v
```
