# 19: Schema do Manifesto, Migração de Metadados Legados e Política de Frescor

**What to build:**
Implementar o validador de schema estrito do manifesto `snapshot_metadata.json` (v2), a rotina de detecção e migração não-destrutiva de metadados legados v1 com contrato formal para o valor de qualidade `legacy_unverified`, a função harmonizada de verificação de frescor temporal `is_source_fresh()` no intervalo $[-300\text{s}, \text{max\_hours} \times 3600\text{s}]$, e a governança do estado `running` no manifesto, tratando-o rigorosamente como execução em andamento (pendente) e evitando suposições espúrias de crash baseadas na ausência de lock de persistência.

**Blocked by:**
17 (modelos e invariantes de resultado), 18 (lock e primitivas de durabilidade para integração de verificação de concorrência)

**Status:**
blocked

**Files to modify:**
- `src/core/models.py` (ou módulo de manifesto correspondente)
- `tests/test_manifest_schema.py` (novo)

**Acceptance criteria:**
- [ ] **Validação Estrita de Schema do Manifesto v2 (`validar_schema_manifesto`):**
  - Validação da estrutura JSON contendo chaves mandatórias: `version` (int == 2), `collected_at` (string ISO 8601 válida), `last_attempt` (dict) e `sources` (dict).
  - Validação detalhada de `last_attempt`:
    - `started_at` (string ISO), `status` em `("running", "completed", "failed", "interrupted")`, `pid` (int ou None), `trigger` (string).
    - Validação de que `pid` não seja booleano (`isinstance(pid, int) and not isinstance(pid, bool)`).
  - Validação detalhada de cada entrada em `sources`:
    - `updated_at` (string ISO 8601).
    - `sha256` (string hexadecimal minúscula de exatamente 64 caracteres).
    - `count` (inteiro não negativo, rejeitando booleanos explicitamente via `not isinstance(count, bool)`).
    - `status` (string válida correspondente a `SourceStatus`).
    - `quality` (string em `("verified", "legacy_unverified", "recovered")`).
  - Retorna `True` para manifestos válidos e `False` para manifestos ausentes, malformados ou com divergência de tipo.
- [ ] **Contrato Formal de `legacy_unverified` e Migração Sem Destruição:**
  - **Contrato de Validação e Leitura:** O validador de schema aceita expressamente `quality: "legacy_unverified"`. Na leitura estrita, esse valor informa aos consumidores que os dados provêm do formato pré-Spec-0007.
  - **Não Equiparação a Dados Atuais Comprovados:** Dados classificados como `legacy_unverified` são preservados estritamente como histórico recuperável de contingência. O sistema **não os trata automaticamente como dados atuais comprovados** (`verified`), mesmo que o timestamp esteja dentro da janela temporal. Apenas dados que passaram pelo ciclo transacional completo v2 com hash comitado recebem `quality: "verified"`.
  - **Não Declaração de Integridade Retrospectiva:** O cálculo do SHA-256 executado durante a migração atesta exclusivamente a integridade física do arquivo em disco **a partir daquele instante** (para proteção contra corrupção futura), mas o sistema expressamente **não declara nem presume integridade criptográfica retrospectiva** sobre a coleta histórica original.
  - **Preservação de Histórico:** A migração opera em memória sem alterar ou sobrescrever destrutivamente os arquivos JSON de dados históricos pré-existentes.
  - **Compatibilidade com Chaves Existentes:** Reconhece e migra as chaves de fontes reais existentes no repositório (`"twitter"`, `"github"`, `"papers"` e seus aliases correspondentes).
- [ ] **Governança do Estado `running` e Proibição de Publicação Prematura:**
  - **Regra de Interpretação:** O status `running` no manifesto representa formalmente uma **execução ainda não finalizada** (em andamento), pois etapas de scraping e chamadas de rede demoradas ocorrem naturalmente sem reter o lock pontual de persistência. A ausência de `snapshot.lock` **não pode** ser interpretada como evidência de crash.
  - **Evidência Confiável de Interrupção:** Um processo em `running` só é classificado como `interrupted`/`crashed` mediante evidência confiável:
    1. Verificação se o PID registrado não existe mais na tabela de processos do sistema operacional (utilizando primitivas nativas do SO com fallback seguro); ou
    2. Verificação de que o tempo decorrido desde `started_at` ultrapassou com margem segura a duração máxima plausível de uma tentativa (ex: > 30 minutos).
  - **Proibição de Publicação de Dados Incompletos:** O sintetizador e os leitores estritos jamais consomem dados de uma execução em estado `running` pendente; utilizam snapshots comitados anteriores ou declaram indisponibilidade temporária.
- [ ] **Política Harmonizada de Frescor Temporal `is_source_fresh()`:**
  - Assinatura: `is_source_fresh(updated_at: datetime | str, max_hours: float = 36.0, now: datetime | None = None) -> bool`.
  - Normalização defensiva de strings ISO e timestamps ingênuos para o timezone local do sistema / UTC.
  - Cálculo de idade: `age_seconds = (now - updated_at).total_seconds()`.
  - Janela estrita de aceitação: `-300.0 <= age_seconds <= (max_hours * 3600.0)`.
  - Tolera avanço de relógio do sistema / NTP de até 300 segundos no futuro (`age_seconds >= -300.0`).
  - Rejeita como anomalia temporal severa qualquer timestamp além de 300 segundos no futuro (`age_seconds < -300.0`).
  - Rejeita como obsoleto (`stale`) qualquer timestamp mais antigo que `max_hours`.
- [ ] **Cobertura de Testes Unitários em `tests/test_manifest_schema.py`:**
  - Testes com manifestos v2 válidos e completos.
  - Testes de rejeição de schema com campos faltando, tipos errados e contadores booleanos (`count: True`).
  - **Teste com Metadados v1 Reais do Repositório:** Carregamento de fixture baseada no `data/snapshot_metadata.json` real existente (`"sources": {"twitter": "...", "github": "...", "papers": "..."}`) e comprovação de migração não-destrutiva para v2 com `legacy_unverified`.
  - **Teste de Primeiro Uso da v2:** Comprovação de geração limpa de manifesto v2 com `version: 2` em ambiente sem manifesto anterior.
  - Testes de limites de frescor: -300s (válido), -301s (inválido/futuro), 0s (válido), 35.9h (válido), 36.1h (inválido/stale).
  - Testes de governança do estado `running`: processo ativo não tem dados publicados; processo morto com PID inexistente é detectado como interrompido.
  - **Descoberta canônica no unittest:** O arquivo possui prefixo `test_` na pasta `tests/` e é executado diretamente por `python -m unittest discover -s tests -t . -v`.

**TDD & Validation Commands:**
```bash
# Execução focada dos testes de schema do manifesto e frescor
python -m unittest tests.test_manifest_schema -v

# Execução canônica da suíte completa sob guardrails
python -m unittest discover -s tests -t . -v
```
