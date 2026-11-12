# 20: Persistência Atômica de Snapshots, Recuperação Idempotente e Quarentena Delimitada

**What to build:**
Refatorar integralmente a persistência e o carregamento de lotes de ingestão (`save_snapshot()` e `load_snapshot()`) em `DailyIngestionBatch` (`src/core/models.py`), eliminando o débito DEF-01 de perda de snapshots por coletas parciais.

Implementar o protocolo transacional de escrita em disco sob bloqueio exclusivo de persistência (`adquirir_trava_snapshot`), mantido estritamente durante o intervalo de I/O em disco, com criação e sincronização atômica de backups (`.prev`) antes de qualquer substituição de arquivos ativos, verificação de preflight de consistência, máquina de estados de recuperação por fonte com hash SHA-256, migração não-destrutiva de metadados v1 com contrato de `legacy_unverified`, e quarentena delimitada aos artefatos de snapshot.

**Blocked by:**
17 (modelos e invariantes de resultado), 18 (lock e primitivas de durabilidade), 19 (schema do manifesto, migração e frescor)

**Status:**
blocked

**Files to modify:**
- `src/core/models.py`
- `tests/test_snapshot_atomic.py` (novo)

**Acceptance criteria:**
- [ ] **Protocolo Transacional de Escrita em `DailyIngestionBatch.save_snapshot()`:**
  - **Uso Estrito da Trava de Persistência:** Adquire `adquirir_trava_snapshot(lock_path, timeout=10.0)` estritamente durante o bloco de I/O em disco. A trava é liberada imediatamente ao final da gravação, sem aninhamento e sem retenção durante scraping ou chamadas externas.
  - **Fase 1: Preflight de Integridade e Reconciliação:**
    - Antes de qualquer escrita, inspeciona o estado do arquivo ativo e de seu backup `.prev` correspondente para cada fonte e para o manifesto.
    - Se o arquivo ativo estiver corrompido (JSON inválido ou hash mismatch) mas o `.prev` for válido, move o ativo para quarentena e restaura o `.prev` como ativo antes de prosseguir.
  - **Fase 2: Rotação Atômica de Backup (`.prev`):**
    - Se o arquivo ativo atual for válido e comitado, cria a cópia de segurança em `.prev.tmp.<pid>`, chama `flush()`, `os.fsync()`, substitui atomicamente via `os.replace(".prev.tmp.<pid>", ".prev")` e sincroniza o diretório pai via `_fsync_dir(data_dir)`.
    - Garante que a escrita do backup nunca corrompa o backup pré-existente caso haja interrupção prematura.
  - **Fase 3: Gravação Segura do Arquivo Ativo de Dados:**
    - Grava o conteúdo atualizado em arquivo temporário com PID (`.tmp.<pid>`).
    - Executa `flush()` explícito e `os.fsync(fileno)`.
    - Substitui atomicamente o arquivo definitivo via `os.replace()`.
    - Executa `_fsync_dir(data_dir)` no POSIX.
  - **Fase 4: Gravação Atômica do Manifesto:**
    - Constrói o manifesto v2 calculando os hashes SHA-256 dos arquivos definitivos gravados e contadores numéricos estritos.
    - Grava `snapshot_metadata.json` utilizando o mesmo protocolo temporário + fsync + replace + `_fsync_dir`.
- [ ] **Carregamento Seguro e Recuperação Idempotente em `load_snapshot()`:**
  - Valida o hash SHA-256 de cada arquivo de dados contra o hash registrado no manifesto.
  - Aplica a matriz de recuperação per-source:
    - Se o arquivo ativo for íntegro e condizente com o hash: consome normalmente.
    - Se o arquivo ativo estiver corrompido ou com divergência de hash, mas o `.prev` for válido: isola o arquivo corrompido em quarentena, promove o `.prev` para ativo via `os.replace()` + `_fsync_dir`, e consome os dados íntegros do backup.
    - Se ambos (ativo e `.prev`) forem inválidos ou corrompidos: move para quarentena e marca a fonte como vazia/degradada, sem quebrar a execução das demais fontes.
  - **Migração Transparente v1 -> v2:** Ao carregar snapshot sob metadados legados v1, reconhece as fontes (`"twitter"`, `"github"`, `"papers"`), gera em memória os registros com `quality: "legacy_unverified"` e calcula SHA-256 sem adulterar ou destruir arquivos existentes no disco.
  - **Proibição Estrita de Dados Não Comitados:** Nenhum dado não validado, de integridade não comprovada ou de execução com status `running` pendente é entregue no `DailyIngestionBatch` retornado.
- [ ] **Delimitação Estrita de Quarentena de Arquivos Órfãos:**
  - O isolamento automático em `data/quarantine/` atua **exclusivamente** sobre arquivos cujos prefixos pertençam ao subsistema de snapshot:
    - `tweets_coletados.*`
    - `github_trending.*`
    - `hf_papers.*`
    - `snapshot_metadata.*`
  - Qualquer outro arquivo presente em `data/` (ex: `ultimo_envio.txt`, logs, bancos de dados, arquivos de lock) é explicitamente preservado intacto.
  - Nomenclatura em quarentena segue o padrão único: `<stem>_<YYYYmmddTHHMMSS_microseconds>_<uuid4[:8]><ext>.corrupted`.
- [ ] **Cobertura de Testes Unitários em `tests/test_snapshot_atomic.py`:**
  - Teste de fluxo normal: `save_snapshot()` e recarga perfeita com integridade comprovada por hash.
  - Teste de isolamento de falha parcial: falha na coleta do Twitter preserva integralmente os tweets da coleta anterior em disco sem sobrescrita vazia.
  - Teste de crash na gravação: arquivo corrompido artificialmente no ativo é recuperado com sucesso a partir do `.prev`.
  - Teste de quarentena delimitada: arquivo órfão corrompido de snapshot vai para quarentena; arquivo `ultimo_envio.txt` permanece intacto.
  - Teste com fixture de metadados legados v1 comprovando que a carga recupera os dados sem destruição.
  - **Descoberta canônica no unittest:** O arquivo possui prefixo `test_` na pasta `tests/` e é executado diretamente por `python -m unittest discover -s tests -t . -v`.

**TDD & Validation Commands:**
```bash
# Execução focada dos testes de persistência atômica e recuperação
python -m unittest tests.test_snapshot_atomic -v

# Execução canônica da suíte completa sob guardrails
python -m unittest discover -s tests -t . -v
```
