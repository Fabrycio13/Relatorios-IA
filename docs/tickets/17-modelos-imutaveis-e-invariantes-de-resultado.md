# 17: Modelos Imutáveis Profundos e Invariantes de Resultado (SourceCollectionResult)

**What to build:**
Implementar e consolidar a imutabilidade profunda das entidades de domínio (`Tweet`, `GitHubRepo`, `ResearchPaper`) em `src/core/models.py`, e introduzir a estrutura tipada de retorno de coletas `SourceCollectionResult[T]` com o enumerador `SourceStatus`.

Essa alteração resolve a primeira etapa da eliminação do acoplamento de persistência nos coletores (ARC-01), estabelecendo contratos formais de dados em memória com validações rigorosas de invariantes no `__post_init__` (garantindo que contadores inteiros não aceitem booleanos, listas sejam convertidas em tuplas imutáveis e estados sejam estritamente consistentes com o conteúdo retornado).

**Blocked by:**
None (pode iniciar imediatamente; unidade autônoma de modelos de domínio e contratos de teste)

**Status:**
ready-for-agent

**Files to modify:**
- `src/core/models.py`
- `tests/test_source_result.py` (novo)

**Acceptance criteria:**
- [ ] **Imutabilidade Profunda de Domínio em `src/core/models.py`:**
  - `Tweet` configurado com `frozen=True`, com campos `id: str`, `text: str`, `author: str`, `created_at: str`, `metrics: dict[str, int]` e `media: tuple[str, ...]`.
  - `GitHubRepo` configurado com `frozen=True`, com campos `name: str`, `owner: str`, `description: str`, `stars: int`, `language: str`, `url: str`.
  - `ResearchPaper` configurado com `frozen=True`, com campos `title: str`, `authors: tuple[str, ...]`, `summary: str`, `url: str`, `published_at: str`.
  - Garantir conversão defensiva para tuplas em coleções internas passadas como lista nos construtores ou converters.
- [ ] **Enum `SourceStatus(str, Enum)`:**
  - Valores padronizados: `SUCCESS = "success"`, `EMPTY = "empty"`, `PARTIAL = "partial"`, `FAILED = "failed"`, `NOT_RUN = "not_run"`.
- [ ] **Dataclass Genérica `SourceCollectionResult[T]`:**
  - Definida como `Generic[T]` com decorador `@dataclass(frozen=True)`.
  - Campos:
    - `source_name: str`
    - `status: SourceStatus`
    - `items: tuple[T, ...] = field(default_factory=tuple)`
    - `collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))`
    - `successful_operations: int = 0`
    - `failed_operations: int = 0`
    - `error_message: str | None = None`
    - `rate_limited: bool = False`
- [ ] **Validação Estrita de Invariantes no `__post_init__`:**
  - Rejeição de valores não inteiros ou booleanos em contadores: `isinstance(val, int) and not isinstance(val, bool)` para `successful_operations` e `failed_operations`. Lança `TypeError` em caso de violação.
  - Rejeição de contadores negativos (`< 0`). Lança `ValueError`.
  - Conversão transparente de `items` fornecido como `list` ou outro iterável para `tuple` imutável.
  - Invariante de coerência 1: Se `len(items) > 0`, `status` não pode ser `SourceStatus.FAILED` nem `SourceStatus.NOT_RUN`. Lança `ValueError`.
  - Invariante de coerência 2: Se `status == SourceStatus.EMPTY`, `len(items)` deve ser rigorosamente 0. Lança `ValueError`.
  - Invariante de coerência 3: Se `status == SourceStatus.FAILED`, `error_message` não pode ser nulo ou vazio. Lança `ValueError`.
- [ ] **Propriedade Computada `has_usable_data`:**
  - Propriedade booleana que retorna `True` se e somente se `len(self.items) > 0 and self.status in (SourceStatus.SUCCESS, SourceStatus.PARTIAL)`.
- [ ] **Cobertura de Testes Unitários em `tests/test_source_result.py`:**
  - Testes cobrindo instanciação válida para cada um dos 5 status.
  - Testes cobrindo rejeição de booleanos (`True`/`False`) nos contadores de operações.
  - Testes cobrindo rejeição de itens com status `FAILED` ou `NOT_RUN`.
  - Testes cobrindo exigência de mensagem de erro em `FAILED`.
  - Testes comprovando imutabilidade (`FrozenInstanceError` ao tentar modificar atributos de `Tweet`, `GitHubRepo`, `ResearchPaper` ou `SourceCollectionResult`).
  - Execução canônica hermética sem rede nem dependências externas.
  - **Descoberta canônica no unittest:** O arquivo possui prefixo `test_` na pasta `tests/` e é executado diretamente por `python -m unittest discover -s tests -t . -v`.

**TDD & Validation Commands:**
```bash
# Execução focada dos testes de modelos e resultados
python -m unittest tests.test_source_result -v

# Execução canônica da suíte completa sob guardrails
python -m unittest discover -s tests -t . -v
```
