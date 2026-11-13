# Retrospectiva: Resiliência de Snapshots, Integridade da Ingestão e Desacoplamento Transacional (Spec 0007)

**Data:** 13 de Novembro de 2026  
**Status do Projeto:** 376/376 testes automatizados aprovados | CI pós-merge no GitHub Actions 100% verde (Run #43414053630, 22s)  
**Escopo Analisado:** Ciclo completo de engenharia da Spec 0007 v4.3 (Tickets 17 a 22 / PR [#20](https://github.com/Fabrycio13/Relatorios-IA/pull/20) / Merge Commit `f6a6db5758fa832f52e6725e8fea7ba921141e4c` via *Squash and Merge*), abrangendo: eliminação da sobrescrita destrutiva de snapshots em falhas parciais (DEF-01), desacoplamento de I/O nos coletores de dados (ARC-01), modelos imutáveis e invariantes de resultado (`SourceCollectionResult`), protocolo atômico de persistência com backup rotativo (`.prev`), lock de processo exclusivo desacoplado de retries, schema formal do manifesto v2 com verificação de integridade via SHA-256 em relação ao hash registrado, quarentena delimitada, governança de ciclo de vida com liveness e reciclagem de PID no SO, orquestração de pipeline com Zero Locks durante scraping, alinhamento estrito aos códigos de saída da CLI (`0`, `1`, `2`) e síntese editorial resiliente com aviso obrigatório de contingência.

---

## 1. Contexto e Trajetória do Ciclo

A Spec 0007 v4.3 percorreu um ciclo estruturado de engenharia de software orientado a resiliência e integridade transacional:

$$\text{Diagnóstico DEF-01 / ARC-01} \longrightarrow \text{Spec 0007 (v1 a v4.3)} \longrightarrow \text{Tickets 17-22} \longrightarrow \text{TDD em Worktree} \longrightarrow \text{Code Review} \longrightarrow \text{Correções B-01/B-03} \longrightarrow \text{PR \#20} \longrightarrow \text{Squash Merge}$$

A motivação do ciclo derivou de duas fragilidades arquiteturais crônicas identificadas na operação autônoma do gerador de relatórios:
1. **DEF-01 (Sobrescrita Destrutiva de Snapshots):** Quando uma fonte de coleta sofria falha temporária (ex: bloqueio de rate limit ou timeout de carregamento assíncrono no Playwright/Twitter), execuções de contingência sobrescreviam os arquivos consolidados em `data/` (`tweets_coletados.json`, `github_trending.json`, etc.) com listas vazias `[]`, destruindo o histórico legítimo obtido em coletas anteriores e degradando irreversivelmente a síntese jornalística do dia.
2. **ARC-01 (Acoplamento de I/O nos Coletores):** Os módulos coletores (`twitter.py`, `github.py`, `huggingface.py`) executavam chamadas diretas de escrita a disco (`open(..., "w")`), misturando a lógica de scraping, normalização de texto, tratamento de erros e persistência física, impossibilitando testes herméticos determinísticos e impedindo qualquer coordenação atômica coordenada.

A solução exigiu uma reformulação completa em duas camadas: transformar os coletores em funções puras em memória retornando estruturas imutáveis tipadas (`SourceCollectionResult[T]`) e centralizar toda a responsabilidade de durabilidade física no método `DailyIngestionBatch.save_snapshot()`, sob o controle de um lock exclusivo de processo (`snapshot.lock`) e protocolo de escrita atômica com manifesto v2 e verificação de integridade via SHA-256.

A Pull Request [#20](https://github.com/Fabrycio13/Relatorios-IA/pull/20) foi integrada à branch `main` via modalidade **Squash and Merge** no commit `f6a6db5758fa832f52e6725e8fea7ba921141e4c`, consolidando atomicamente as entregas dos Tickets 17 ao 22 e as correções pós-review.

---

## 2. O que Funcionou Bem (Práticas a Preservar)

1. **Decomposição Modular em Tickets Estritamente Delimitados (Tickets 17 a 22):**
   * A divisão do problema em etapas independentes permitiu progresso incremental com verificação formal de contratos:
     - *Ticket 17:* Imutabilidade (`frozen=True`) e invariantes de contadores em `SourceCollectionResult`.
     - *Ticket 18:* Primitivas de durabilidade, lock desacoplado via `contextlib.ExitStack`, rotação de `.prev` e quarentena delimitada.
     - *Ticket 19:* Schema v2 de `snapshot_metadata.json`, migração não-destrutiva de manifestos v1 para `legacy_unverified` e janela de frescor $[-300\text{s}, 36\text{h}]$.
     - *Ticket 20:* Persistência atômica centralizada em `DailyIngestionBatch.save_snapshot()`, máquina de estados de recuperação por fonte e prova de SHA-256.
     - *Ticket 21:* Coletores puros em memória e eliminação de chamadas de persistência física.
     - *Ticket 22:* Orquestração de pipeline com Zero Locks durante scraping, códigos de saída da CLI (`0`, `1`, `2`) e governança editorial no sintetizador.
   * Essa separação evitou commits gigantes desordenados e manteve o escopo de cada revisão estritamente controlado.

2. **Isolamento de Ambiente com Git Worktree:**
   * A utilização da worktree dedicada `D:\Projetos\relatorios-ia-spec-0007` manteve a branch `feat/resiliencia-snapshots-spec-0007` isolada dos arquivos de trabalho locais da pasta raiz `D:\Projetos\Relatorios - IA` (onde residiam modificações de banners e relatórios diários operacionais).
   * Embora Git worktrees isolem eficientemente árvores de trabalho e branches — prevenindo a inclusão acidental de arquivos locais modificados em outras branches —, elas não eliminam todos os riscos operacionais (como dependência do repositório comum `.git`, concorrência sobre recursos de infraestrutura local ou a necessidade de preflights rigorosos). Seu uso disciplinado garantiu que nenhum artefato não-rastreado, segredo ou log operacional da pasta raiz fosse versionado indevidamente.

3. **TDD Rigoroso com Suíte Hermética:**
   * A suíte expandiu de 186 para **376 testes automatizados**, mantendo 100% de aprovação em tempo médio de execução de 7 segundos.
   * Todos os testes respeitaram os guardrails (`tests/guardrails.py`): zero conexões TCP/UDP externas, zero inicializações reais de Playwright e zero toques na trava operacional de envio (`data/ultimo_envio.txt`).
   * A inclusão de um teste hermético com subprocesso real no Windows comprovou a detecção de encerramento abrupto e recuperação do manifesto diretamente via APIs do SO (`OpenProcess` e `GetExitCodeProcess`).

4. **Imutabilidade de Domínio e Contratos Fortes:**
   * A conversão de `Tweet`, `GitHubRepo` e `ResearchPaper` para dataclasses imutáveis (`frozen=True`) com tuplas nativas no lugar de listas eliminou efeitos colaterais e mutações acidentais de estado durante a orquestração.
   * As invariantes numéricas em `SourceCollectionResult` (rejeição estrita de booleanos e proibição de contadores negativos) preveniram incoerências de telemetria.

5. **Protocolo Atômico de Persistência com Backup Rotativo:**
   * O fluxo de escrita `arquivo temporário (.tmp.<pid>)` $\rightarrow$ `flush()` $\rightarrow$ `os.fsync()` $\rightarrow$ `os.replace()` $\rightarrow$ `_fsync_dir()` assegurou que o sistema nunca deixe arquivos parcialmente gravados no caminho definitivo.
   * A rotação preventiva para `.prev` permitiu recuperação idempotente automática caso o arquivo ativo seja corrompido durante gravações subsequentes.

6. **Auditoria em Dois Eixos (Code Review Baseado em Evidências):**
   * A revisão estruturada (Standards e Spec) revelou três defeitos concretos de integração (B-01, B-03 e B-02) que haviam passado despercebidos pelos testes unitários isolados, impedindo que vulnerabilidades de deadlock e falhas de transparência editorial chegassem à branch `main`.

7. **CI Rápida e Determinística:**
   * O workflow do GitHub Actions no Linux executou todos os testes em 22 segundos, comprovando independência de ambiente e portabilidade de código.

---

## 3. O que Funcionou Mal e Gerou Retrabalho (Análise Crítica)

1. **Contratos Incorretos e Permissividade entre `EMPTY` e `FAILED` (Ticket 21):**
   * Durante a migração dos coletores, o agente introduziu fallbacks defensivos permissivos com construções como `res or []` ou `res or ()`. Essa abordagem convertia retornos anômalos (`None`, strings, dicionários não conformes) em listas vazias legítimas (`EMPTY`).
   * *Impacto:* Um erro de contrato no coletor Twitter seria mascarado como uma coleta vazia bem-sucedida, correndo o risco de acionar a limpeza ou substituição de dados legítimos em vez de acionar a contingência. Foi necessária intervenção humana detalhada para impor que violações de contrato gerassem estritamente `FAILED` com mensagem diagnóstica.

2. **Fragilidade Inicial na Validação de Backups Históricos (Ticket 20):**
   * Na primeira implementação de `DailyIngestionBatch.load_snapshot()`, o carregador considerava o arquivo de backup `.prev` válido apenas por conter uma lista JSON sintaticamente parseável, sem verificar se o conteúdo correspondia ao hash SHA-256 esperado registrado no manifesto anterior.
   * *Impacto:* Backups corrompidos ou obsoletos poderiam ser indevidamente promovidos a ativos. A validação precisou ser refeita para confrontar estritamente o SHA-256 do arquivo `.prev` contra o hash registrado no manifesto.

3. **Quebra de Retrocompatibilidade com Manifestos v1 Legados (Ticket 20):**
   * O código original de coletas isoladas (`python main.py --step collect-<fonte>`) produzia arquivos `snapshot_metadata.json` contendo apenas a chave `sources`, sem o campo `collected_at` na raiz.
   * A função `is_manifesto_v1()` passou a exigir obrigatoriamente a presença de `collected_at`, fazendo com que manifestos legados reais fossem classificados como corrompidos e movidos equivocadamente para a quarentena.
   * *Impacto:* Quebra de compatibilidade em ambientes com histórico real. Foi necessário adicionar testes específicos e ajustar o reconhecedor para aceitar a estrutura real de manifestos v1.

4. **Lacuna de Integração do Fallback com o Sintetizador (Ticket 22):**
   * No Ticket 22, o pipeline preservava com sucesso os arquivos históricos em disco em caso de falha de coleta, mas ao invocar `gerar_resumo_ia(batch=batch)` passando o lote em memória, o lote continha listas vazias para as fontes que falharam. Como o parâmetro `batch` não era nulo, o sintetizador não consultava o disco, gerando relatórios com seções omitidas em vez de utilizar o fallback histórico preservado.
   * *Impacto:* A resiliência de persistência funcionava perfeitamente no disco, mas o consumidor final (a newsletter) não recebia os dados. Exigiu intervenção humana para criar um teste integrado ponta a ponta que forçou a injeção do fallback diretamente no lote retornado e a inclusão de aviso editorial.

5. **Deadlock Lógico por Processo Morto — Achado B-01 (Code Review):**
   * A função `is_execucao_em_andamento()` tratava qualquer manifesto com `last_attempt.status == "running"` como bloqueador de leituras para evitar *dirty reads*. No entanto, se o processo Python fosse encerrado abruptamente (falta de luz, encerramento via Gerenciador de Tarefas ou SIGKILL), o status `"running"` permanecia no disco indefinidamente, bloqueando todas as execuções futuras com código de saída 1.
   * *Tentativa ingênua do agente:* Propor um timeout arbitrário de 30 minutos ou verificar a ausência de `snapshot.lock`. Essa solução era perigosa e incorreta, pois durante o scraping de 60s do Playwright o lock de arquivo permanece livre por design (*Zero Locks durante scraping*), o que levaria a falsos diagnósticos de crash de processos ativos.
   * *Impacto:* Retrabalho pós-review para implementar detecção de liveness real no SO (`OpenProcess` no Windows, `os.kill(0)` no POSIX), validação de ordem temporal de criação contra `started_at` para mitigar reciclagem de PID, e transição atômica para `interrupted` sob trava.

6. **Incompatibilidade de Chaves de Aliases no Sintetizador — Achado B-03 (Code Review):**
   * Em `src/processors/ai_summarizer.py`, a verificação de frescor consultava diretamente `sources_meta.get("github")` e `sources_meta.get("papers")`. Contudo, manifestos migrados da versão 1 possuíam chaves legadas `"github_trending"` e `"hf_papers"`.
   * *Impacto:* As chaves não eram encontradas no dicionário, fazendo com que a função assumisse valores padrão (`quality: "verified"`, sem checagem de idade). Dados históricos obsoletos de 5 dias atrás eram sintetizados sem aviso editorial de contingência. A resolução teve de ser centralizada na função `obter_metadados_fonte()`.

---

## 4. Análise de Causas-Raiz e Padrões de Falha

| Categoria | Causa-Raiz | Manifestação no Ciclo | Prevenção Sistêmica |
|---|---|---|---|
| **Falhas de Especificação** | Suposição de que o salvamento físico encerrava o requisito do usuário, sem modelar como o leitor a jusante consumiria o dado. | Falha do sintetizador em consumir dados de fallback mesmo quando eles estavam íntegros em disco (Ticket 22). | Critério de aceitação de ticket exigindo teste integrado ponta a ponta conectando persistência e renderização. |
| **Lacunas de Integração** | Testar componentes em isolamento com mocks excessivos, mascarando discordâncias de nomenclatura de chaves. | Incompatibilidade de aliases (`github` vs `github_trending`) no sintetizador (B-03). | Centralização obrigatória de acesso a metadados via função única de mapeamento (`obter_metadados_fonte`). |
| **Complexidade Concorrente** | Estado persistido em disco (`status: "running"`) sem vínculo com a vida útil do processo no sistema operacional. | Deadlock lógico permanente após encerramento forçado do processo gravador (B-01). | Consulta a liveness de processo no SO (`is_pid_alive`) combinada com verificação temporal antes de assumir estado operacional. |
| **Limitações de Code Review de IA** | Sugestões automáticas baseadas em padrões genéricos da web, sem considerar as restrições da arquitetura local. | Sugestão de `replace(tzinfo=utc)` cego em timestamps legados e `except OSError: pass` no `_fsync_dir`. | Rejeição explícita de correções automáticas que contrariem contratos de durabilidade e integridade aprovados na Spec. |

---

## 5. Aprendizados de Engenharia e Princípios Fortalecidos

1. **Testes Unitários Não Substituem Testes Integrados de Contrato:**
   * Uma função de salvamento e uma função de carregamento podem ter 100% de cobertura individual, mas falharem quando orquestradas pelo pipeline se a chave de metadados divergir ou se o lote intermediário for limpo. Testes integrados de contingência são indispensáveis.

2. **Preservar Dados em Disco Não Garante sua Utilização:**
   * Garantir que o arquivo `tweets_coletados.json` não foi apagado é inútil se o componente que redige a newsletter não for avisado de que deve carregar o snapshot anterior diante da falha da coleta atual.

3. **Code Review Automatizado Não Deve Ser Seguido Cegamente:**
   * Ferramentas e agentes de revisão automatizada frequentemente sugerem supressão silenciosa de erros (`except Exception: pass`) ou atalhos de compatibilidade (como assumir UTC automaticamente para timestamps históricos ingênuos, que contraria a política aprovada da Spec 0007 v4.3 que os classifica formalmente como temporalmente não confiáveis). Toda sugestão de code review exige auditoria humana crítica antes de ser aplicada.

4. **Ortogonalidade entre Integridade, Frescor e Procedência:**
   * O ciclo consolidou a distinção matemática entre três eixos independentes da qualidade do dado:
     * *Integridade Física:* O arquivo está legível e o hash SHA-256 confere com o registrado no manifesto. Não confunde integridade local com autenticação criptográfica independente.
     * *Frescor Temporal:* O timestamp com fuso conhecido está dentro da janela válida $[-300\text{s}, \text{max\_hours} \times 3600\text{s}]$. Timestamps históricos ingênuos sem timezone permanecem temporalmente não confiáveis.
     * *Procedência Editorial:* O dado foi obtido no ciclo atual (`verified`), herdado de migração anterior (`legacy_unverified`) ou utilizado em contingência após falha recente.
   * Tratar esses conceitos de forma independente permitiu que o sistema publicasse relatórios transparentes sem travar e sem divulgar dados obsoletos como atuais.

5. **A Durabilidade em Filesystem Exige Testes de Falha Controlada:**
   * Em sistemas que lidam com estado persistente em disco, testar apenas o "caminho feliz" é insuficiente. Testes de crash simulado (arquivos corrompidos, processos mortos via SIGKILL/TerminateProcess, arquivos parciais `.tmp`) são os que comprovam a verdadeira resiliência da arquitetura.

---

## 6. Ações Institucionalizadas e Melhorias de Processo

As lições comprovadas neste ciclo passam a integrar as práticas obrigatórias do repositório:

1. **Padrão de Preflight de Reconciliação A $\rightarrow$ B $\rightarrow$ C:**
   * Toda rotina que persiste snapshots em disco deve, obrigatoriamente, verificar a integridade da geração anterior e restaurar backups `.prev` caso o arquivo ativo esteja ausente ou corrompido, antes de inicializar novos arquivos temporários.

2. **Proibição Estrita de Acesso Direto a Chaves de Fontes:**
   * Fica expressamente vedado o uso de `dict.get("twitter")` ou `sources_meta.get("github")` no código de processamento e síntese. Todo acesso a metadados de fontes deve ocorrer exclusivamente através da função de fachada [obter_metadados_fonte()](file:///D:/Projetos/relatorios-ia-spec-0007/src/core/models.py#L280-L315), garantindo interoperabilidade entre nomes canônicos e aliases.

3. **Governança de Execução com Liveness Real do SO:**
   * A checagem de execução em andamento (`is_execucao_em_andamento`) não deve basear-se exclusivamente no status gravado em JSON nem na ausência de travas de arquivo. Deve consultar a tabela de processos do sistema operacional e a ordem temporal de criação do processo contra `started_at`, preservando a condição de incerteza em caso de falha de permissão.

4. **Transparência Editorial Obrigatória na Degradação Graciosa:**
   * Toda utilização de dados históricos ou legados em contingência deve emitir um aviso explícito na newsletter gerada pelo `ai_summarizer.py`, informando a limitação operacional da fonte e prevenindo desinformação.

5. **Critério de Rejeição de Supressão Silenciosa de I/O:**
   * É terminantemente proibido silenciar exceções críticas de sistema de arquivos (`except OSError: pass`) em primitivas de sincronização de diretórios e escrita atômica, preservando a rastreabilidade de falhas de hardware ou montagens de rede.

---

## 7. Métricas Consolidadas do Ciclo

| Indicador | Antes da Spec 0007 | Após a Spec 0007 (v4.3) | Variação / Impacto |
|---|---|---|---|
| **Cobertura de Testes** | 186 testes unitários | **376 testes herméticos** | **+190 novos testes (+102%)** cobrindo concorrência, recuperação e durabilidade |
| **Tempo de Execução da Suíte** | ~1,25s | **~6,95s** | Suíte hermética completa executada localmente sem acessos externos de rede |
| **Tempo de CI (GitHub Actions)** | 23s (Run #40) | **22s (Run #43414053630)** | Execução remota veloz, hermética e 100% verde |
| **Sobrescrita Destrutiva em Falhas (DEF-01)** | Crítica (sobrescrevia com `[]`) | **Zero Sobrescrita** | Dados anteriores são 100% preservados sob fallback automático e backup `.prev` |
| **Pontos de I/O em Coletores (ARC-01)** | 3 módulos acoplados (`open("w")`) | **0 pontos de I/O** | Coletores puros em memória; persistência 100% centralizada |
| **Manifesto de Integridade** | Ausente ou v1 plano sem hash | **Manifesto v2 com SHA-256** | Verificação de integridade por fonte (SHA-256 confrontado com hash do manifesto), histórico de tentativas e governança de frescor |
| **Resiliência a Crash em Scraping** | Deadlock permanente (`running`) | **Auto-recuperação atômica** | Detecção de término de processo no SO e transição segura para `interrupted` |

---

## 8. Conclusão e Estado do Repositório

O ciclo de engenharia da **Spec 0007 v4.3** resolveu de forma definitiva os débitos técnicos mais críticos do pipeline de ingestão (**DEF-01** e **ARC-01**), transformando um subsistema frágil de scripts avulsos em um mecanismo transacional de dados robusto, auditável e imutável.

A aplicação do fluxo disciplinado `Spec → Tickets → TDD em Worktree → Code Review → Validação de Liveness → Squash Merge` demonstrou que o desenvolvimento orientado por IA atinge seu potencial máximo quando submetido a guardrails estritos de isolamento, verificação contínua e supervisão humana rigorosa.

O repositório `Fabrycio13/Relatorios-IA` encontra-se com sua branch principal `main` em estado de excelência técnica (commit `f6a6db5758fa832f52e6725e8fea7ba921141e4c`), com a suíte de 376 testes plenamente aprovada e preparado para as próximas evoluções do *Diário de Engenharia*.
