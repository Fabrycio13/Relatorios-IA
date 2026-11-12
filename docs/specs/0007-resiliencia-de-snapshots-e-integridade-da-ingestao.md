# Especificação Técnica 0007: Resiliência de Snapshots, Integridade Transacional e Desacoplamento da Ingestão

**Status:** Aprovada para Implementação (Versão 4.3 Consolidada com Ajustes Contratuais)  
**Área:** Core Ingestion Engine, Filesystem Resilience, Data Integrity & Pipeline Orchestration  
**Débitos de Referência:** DEF-01 (sobrescrita de snapshots válidos em falhas parciais) e ARC-01 (persistência descentralizada nos coletores)  
**Data:** 12/11/2026  

---

## 1. Problem Statement & Objetivos de Engenharia

### 1.1 Diagnóstico dos Débitos Técnicos
A auditoria técnica e a retrospectiva operacional do projeto identificaram vulnerabilidades críticas no ciclo de vida de persistência e recuperação de dados:
1. **DEF-01 (Sobrescrita Destrutiva e Perda de Snapshots):** Quando uma fonte de coleta falha (ex: rate limit ou timeout no Playwright/Twitter), execuções de fallback ou coletas parciais sobrescrevem os arquivos consolidados em `data/` (`tweets_coletados.json`, `github_trending.json`, etc.) com listas vazias `[]`, destruindo dados históricos válidos coletados em ciclos anteriores e invalidando a síntese jornalística da edição diária.
2. **ARC-01 (Violação do Princípio da Responsabilidade Única por I/O Acoplado):** Os módulos coletores (`src/collectors/twitter.py`, `src/collectors/github.py`, `src/collectors/huggingface.py`) realizam escrita direta em disco (`open(..., "w")`), misturando scraping, parseamento, formatação de log e persistência física de arquivos, o que inviabiliza testes herméticos, cria pontos cegos de concorrência e impede transações atômicas coordenadas.
3. **Fragilidade de Recuperação e Corrupção Silenciosa:** A ausência de backups atômicos (`.prev`), hash SHA-256 de integridade e locks de processo com retry controlado permite que crashes durante a gravação corrompam arquivos de dados ou manifestos, deixando o sistema em estado inconsistente sem possibilidade de recuperação idempotente.

### 1.2 Objetivos Mandatórios (Definition of Done da Arquitetura)
* **Coletores Puros em Memória:** Coletores não tocam o disco; retornam `SourceCollectionResult[T]` com estruturas de dados de domínio imutáveis e status explícito.
* **Persistência Centralizada e Transacional:** Apenas o `DailyIngestionBatch.save_snapshot()` persiste dados em disco, sob lock de processo exclusivo (`snapshot.lock`) com retry desacoplado via `contextlib.ExitStack` e `time.monotonic()`.
* **Protocolo de Escrita com Durabilidade Estrita:**
  - Preparação e rotação atômica do manifesto e arquivos de backup (`.prev`) via `os.replace()` + `_fsync_dir` (no POSIX) antes de modificar o arquivo ativo.
  - Gravação de novos dados em arquivo temporário com PID (`.tmp.<pid>`), chamada explícita de `flush()` e `os.fsync()`, substituição atômica via `os.replace()` e `_fsync_dir` no diretório pai.
* **Recuperação Idempotente e Quarentena Delimitada:**
  - Máquina de estados formal de recuperação por fonte quando o arquivo definitivo estiver ausente ou corrompido, recuperando do `.prev` íntegro.
  - Movimentação de arquivos corrompidos para `data/quarantine/` com nomes únicos (timestamp microssegundos + UUID4 de 8 caracteres).
  - Delimitação estrita da quarentena automática: opera **exclusivamente** sobre artefatos comprovadamente pertencentes ao subsistema de snapshots (`tweets_coletados.*`, `github_trending.*`, `hf_papers.*`, `snapshot_metadata.*`), preservando quaisquer outros arquivos no diretório `data/`.
* **Proibição Absoluta de Consumo de Dados Não Comprovados:**
  - `load_snapshot()` jamais injeta dados com hash divergente ou sem integridade comprovada no `DailyIngestionBatch` de produção.
  - O `ai_summarizer.py` consome apenas dados íntegros e temporalmente válidos.
* **Retrocompatibilidade de Metadados Legados:** Reconhecimento transparente do schema legado com timestamps planos em `sources`, migrando em memória com flag `quality: "legacy_unverified"` e preservando dados válidos existentes sem destruição.
* **Frescor Temporal Harmonizado:** Janela temporal válida formalizada no intervalo $[-300\text{s}, \text{max\_hours} \times 3600\text{s}]$, aceitando até 5 minutos de desvio de relógio (clock drift) no futuro e até 36h no passado.
* **Diferenciação Estrita do Estado `running`:** Um status `running` no manifesto não assume crash por padrão; valida se o lock de processo está ativo (execução em andamento) antes de classificar como execução interrompida. O sintetizador jamais consome dados de uma execução com lock ativo.

---

## 2. Modelagem de Domínio & Invariantes de Dados

### 2.1 Imutabilidade Profunda de Domínio
As entidades de domínio em `src/core/models.py` passam a ser estritamente imutáveis (`frozen=True`):
```python
@dataclass(frozen=True)
class Tweet:
    id: str
    text: str
    author: str
    created_at: str
    metrics: dict[str, int] = field(default_factory=dict)
    media: tuple[str, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class GitHubRepo:
    name: str
    owner: str
    description: str
    stars: int
    language: str
    url: str

@dataclass(frozen=True)
class ResearchPaper:
    title: str
    authors: tuple[str, ...]
    summary: str
    url: str
    published_at: str
```

### 2.2 Status e Resultado Estruturado de Coleta (`SourceCollectionResult`)
```python
class SourceStatus(str, Enum):
    SUCCESS = "success"          # Coleta concluída com sucesso e dados obtidos
    EMPTY = "empty"              # Coleta executou com sucesso, mas a fonte não retornou itens novos
    PARTIAL = "partial"          # Coleta obteve dados parciais antes de falha não fatal ou rate limit
    FAILED = "failed"            # Falha na coleta; nenhum dado novo obtido
    NOT_RUN = "not_run"          # Fonte não executada neste ciclo

@dataclass(frozen=True)
class SourceCollectionResult(Generic[T]):
    source_name: str
    status: SourceStatus
    items: tuple[T, ...] = field(default_factory=tuple)
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    successful_operations: int = 0
    failed_operations: int = 0
    error_message: str | None = None
    rate_limited: bool = False

    def __post_init__(self) -> None:
        # Invariantes numéricos estritos (rejeitando booleanos)
        if not isinstance(self.successful_operations, int) or isinstance(self.successful_operations, bool):
            raise TypeError("successful_operations must be int")
        if not isinstance(self.failed_operations, int) or isinstance(self.failed_operations, bool):
            raise TypeError("failed_operations must be int")
        if self.successful_operations < 0 or self.failed_operations < 0:
            raise ValueError("Counters cannot be negative")

        # Conversão defensiva de listas para tuplas imutáveis
        if not isinstance(self.items, tuple):
            object.__setattr__(self, "items", tuple(self.items))

        # Coerência de status
        if len(self.items) > 0 and self.status in (SourceStatus.FAILED, SourceStatus.NOT_RUN):
            raise ValueError(f"Cannot have items when status is {self.status}")
        if self.status == SourceStatus.EMPTY and len(self.items) != 0:
            raise ValueError("Status EMPTY requires items to be empty")
        if self.status == SourceStatus.FAILED and not self.error_message:
            raise ValueError("Status FAILED requires an error_message")

    @property
    def has_usable_data(self) -> bool:
        return len(self.items) > 0 and self.status in (SourceStatus.SUCCESS, SourceStatus.PARTIAL)
```

---

## 3. Schema do Manifesto & Políticas de Frescor e Migração

### 3.1 Schema de `snapshot_metadata.json` (v2)
```json
{
  "version": 2,
  "collected_at": "2026-11-12T10:45:00.123456+00:00",
  "last_attempt": {
    "started_at": "2026-11-12T10:44:50.000000+00:00",
    "completed_at": "2026-11-12T10:45:00.123456+00:00",
    "status": "completed",
    "trigger": "scheduled",
    "pid": 12345
  },
  "sources": {
    "twitter": {
      "updated_at": "2026-11-12T10:45:00.000000+00:00",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "count": 42,
      "status": "success",
      "quality": "verified"
    },
    "github_trending": {
      "updated_at": "2026-11-12T10:45:00.000000+00:00",
      "sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
      "count": 15,
      "status": "success",
      "quality": "verified"
    },
    "hf_papers": {
      "updated_at": "2026-11-12T10:45:00.000000+00:00",
      "sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
      "count": 10,
      "status": "success",
      "quality": "verified"
    }
  }
}
```

### 3.2 Migração de Metadados Legados (Ajuste Contratual 1)
O manifesto v1 legado possuía timestamps planos:
```json
{
  "collected_at": "2026-10-27T08:00:00",
  "sources": {
    "twitter": "2026-10-27T08:00:00",
    "github_trending": "2026-10-27T08:00:00",
    "hf_papers": "2026-10-27T08:00:00"
  }
}
```
**Regra de Migração:**
- Ao detectar `isinstance(sources[src], str)` ou ausência do campo `"version"`, o carregador migra em memória para a estrutura v2.
- O hash SHA-256 do arquivo existente em disco é calculado na hora.
- O campo `quality` é marcado como `"legacy_unverified"`, indicando que não havia hash gravado previamente para prova criptográfica retrospectiva, mas os dados parseáveis válidos são preservados.
- Na próxima escrita bem-sucedida de `save_snapshot()`, o manifesto em disco é atualizado para o schema v2 de forma transparente.

### 3.3 Harmonização do Frescor Temporal (Ajuste Contratual 2)
A validação de frescor em `is_source_fresh()` unifica a tolerância a clock drift de até 5 minutos com a idade máxima configurada:
```python
def is_source_fresh(updated_at: datetime, max_hours: float = 36.0, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        # Timestamps ingênuos são convertidos para o fuso local do sistema com cautela
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    
    age_seconds = (now - updated_at).total_seconds()
    
    # Tolerância a clock drift de hardware/NTP: até 300 segundos no futuro
    # Idade máxima no passado: max_hours * 3600 segundos
    return -300.0 <= age_seconds <= (max_hours * 3600.0)
```

### 3.4 Diferenciação de Estado `running` em `last_attempt` (Ajuste Contratual 3)
Ao carregar o manifesto ou iniciar nova coleta:
- Se `last_attempt.status == "running"`:
  1. Tenta obter o lock `snapshot.lock` de forma não bloqueante.
  2. Se o lock **estiver retido**, uma execução anterior **está ativamente em andamento**. O leitor ou sintetizador aborta a tentativa de leitura para evitar dirty reads.
  3. Se o lock **estiver livre**, comprova-se que o processo gravador foi abortado de forma abrupta (crash, SIGKILL, falta de energia). O status é marcado como `interrupted`/`crashed`, e o pipeline pode proceder com a recuperação idempotente.

---

## 4. Primitivas de Filesystem & Lock de Processo

### 4.1 Lock de Processo Desacoplado de Retry (`adquirir_trava_snapshot`)
Em `src/core/lock.py`, implementa-se o context manager com `ExitStack` para garantir que exceções lançadas dentro do bloco do chamador não reativem o loop de retry de aquisição:
```python
@contextmanager
def adquirir_trava_snapshot(lock_path: Path, timeout: float = 60.0, retry_delay: float = 0.5):
    """
    Adquire trava exclusiva de arquivo com retentativas baseadas em time.monotonic().
    O retry protege estritamente a aquisição; uma vez adquirido o contexto,
    o bloco do chamador executa isoladamente sem reentrância espúria.
    """
    deadline = time.monotonic() + timeout
    lock_file = None
    stack = ExitStack()
    
    try:
        while True:
            try:
                lock_file = open(lock_path, "a+b")
                stack.enter_context(lock_file)
                
                if os.name == "nt":
                    import msvcrt
                    # Bloqueio exclusivo não-bloqueante no Windows
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    # Bloqueio exclusivo não-bloqueante no POSIX
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Lock adquirido com sucesso
                break
            except (BlockingIOError, PermissionError, OSError):
                stack.close()
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timeout de {timeout}s aguardando trava em {lock_path}")
                time.sleep(retry_delay)
        
        # Executa o bloco protegido com a trava ativa
        with stack:
            yield lock_file
            
    finally:
        # Liberação determinística no encerramento do context manager
        pass
```

### 4.2 Sincronização de Diretório (`_fsync_dir`)
No POSIX, operações de criação e renomeação de arquivos (`os.replace`) modificam os metadados do diretório e requerem `fsync()` no descritor do diretório pai. No Windows NTFS, o journaling do sistema de arquivos gerencia a consistência das entradas de diretório automaticamente (`os.fsync` em diretórios não é suportado pelo Win32):
```python
def _fsync_dir(dir_path: Path) -> None:
    """Sincroniza metadados do diretório no POSIX. No-op seguro no Windows."""
    if os.name != "nt":
        try:
            fd = os.open(str(dir_path), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass
```

---

## 5. Protocolo de Persistência Transacional & Recuperação Idempotente

### 5.1 Protocolo de Escrita Transacional em `save_snapshot()`
Toda gravação de dados segue a sequência estrita:
1. **Preflight e Reconciliação:** Validação da integridade dos arquivos ativos e `.prev`. Caso um arquivo ativo esteja corrompido mas o `.prev` correspondente seja íntegro, quarentena o corrompido e restaura o `.prev` antes de tocar qualquer dado.
2. **Backup Atômico (`.prev`):**
   - Para cada arquivo de dados a ser alterado e para o manifesto, se o arquivo definitivo existe e é válido:
     - Copia para `.prev.tmp.<pid>`
     - `flush()` e `os.fsync()`
     - `os.replace(".prev.tmp.<pid>", ".prev")`
     - `_fsync_dir(data_dir)`
3. **Escrita Segura do Novo Dado:**
   - Grava em `.tmp.<pid>`
   - `flush()` e `os.fsync()`
   - `os.replace(".tmp.<pid>", "definitivo")`
   - `_fsync_dir(data_dir)`
4. **Atualização Atômica do Manifesto:**
   - Calcula os hashes SHA-256 e contadores dos arquivos definitivos gravados.
   - Atualiza `snapshot_metadata.json` seguindo o mesmo protocolo temporário + replace + `_fsync_dir`.

### 5.2 Tabela de Recuperação Idempotente de Arquivos por Fonte
Ao executar `load_snapshot()` ou o preflight de `save_snapshot()`:

| Estado Definitivo | Estado .prev | Ação do Sistema | Resultado de Leitura |
|---|---|---|---|
| **Válido** (JSON íntegro + SHA-256 match) | Indiferente | Consome definitivo; atualiza `.prev` se aplicável | Dados íntegros carregados |
| **Corrompido** (JSON inválido ou hash mismatch) | **Válido** (JSON íntegro + SHA-256 match) | Move definitivo para quarentena, promove `.prev` para definitivo via `os.replace()` + `_fsync_dir` | Dados íntegros restaurados |
| **Corrompido** | **Ausente / Inválido** | Move definitivo para quarentena se corrompido; registra falha da fonte | Fonte marcada como `EMPTY` / degradada (sem quebra fatal do processo) |
| **Ausente** | **Válido** | Promove `.prev` para definitivo via `os.replace()` + `_fsync_dir` | Dados íntegros restaurados |
| **Ausente** | **Ausente** | Inicializa lote vazio com schema válido | Lote inicial limpo |

### 5.3 Quarentena Segura e Delimitada (Ajuste Contratual 4)
- **Caminho de Quarentena:** `data/quarantine/` (criado automaticamente se inexistente, com `_fsync_dir(data)` no POSIX).
- **Padrão de Nomenclatura:** `<basename>_<timestamp_microsegundos>_<uuid4_8char>.<ext>.corrupted` (garantindo ausência de colisões e rastreabilidade total).
- **Delimitação Estrita de Escopo:** A quarentena automática **apenas e tão somente** toca em arquivos pertencentes ao subsistema de snapshot:
  - `tweets_coletados.*`
  - `github_trending.*`
  - `hf_papers.*`
  - `snapshot_metadata.*`
  Qualquer outro arquivo em `data/` (ex: `ultimo_envio.txt`, logs, bancos SQLite, etc.) é expressamente ignorado e preservado intacto.

---

## 6. Governança na Síntese & Contrato Operacional da CLI

### 6.1 Síntese Editorial em `ai_summarizer.py`
- O sintetizador consome apenas instâncias validadas de `DailyIngestionBatch`.
- Antes de montar o prompt jornalístico, verifica `is_source_fresh()` para cada fonte.
- Se uma fonte falhou ou está obsoleta:
  - Não aborta a geração da newsletter diária se houver outras fontes saudáveis.
  - Insere aviso editorial de degradação graciosa na seção correspondente (ex: *"A seção de tópicos do X/Twitter não pôde ser atualizada hoje devido a limitações operacionais na coleta"*).
  - Jamais interpola dados corrompidos ou não comitados.

### 6.2 Contrato de Códigos de Saída da CLI (`main.py`)
- **`sys.exit(0)`:** Execução concluída com sucesso (mesmo com fallback editorial gracioso documentado) ou encerramento silencioso (já enviado hoje, ou bloqueado antes das 08:00 sem `--force`).
- **`sys.exit(1)`:** Falha fatal não recuperável (corrupção irrecuperável do manifesto sem backups, erro de configuração crítica, falha catastrófica de infraestrutura). Emite Toast de erro.
- **`sys.exit(2)`:** Falha transitória de conectividade de rede com retentativas esgotadas (contrato com o Windows Task Scheduler para agendamento automático de nova tentativa em segundo plano).

---

## 7. Critérios de Homologação & Testes de Aceitação
1. **Zero Sobrescrita Destrutiva:** Coletas com falha não afetam snapshots íntegros pré-existentes em disco.
2. **Zero Poluição de I/O nos Coletores:** Verificado via análise de código e testes de spy que nenhum coletor realiza chamadas a `open()`, `Path.write_text()`, etc.
3. **Resiliência a Falhas de Gravação (Crash Simulation):** Interrupção simulada durante a escrita de `.tmp` ou `.prev` não corrompe a geração ativa.
4. **Hermeticidade Total dos Testes:** Suíte executa sob os guardrails de rede (`tests/guardrails.py`) e diretórios temporários (`tempfile.TemporaryDirectory`).
5. **Cobertura Canônica Completa:** 100% de aprovação na execução de `python -m unittest discover -s tests -t . -v`.
