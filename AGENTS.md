# 🤖 Diretrizes para Agentes de IA (AGENTS.md)

Este documento orienta agentes de IA trabalhando neste repositório. O objetivo é garantir **simplicidade**, **segurança operacional**, **alta testabilidade** e **preservação dos comportamentos existentes**.

---

## 1. Mapa de Contexto e Referências Rápidas

Antes de planejar ou alterar código, consulte a documentação oficial existente (não duplique seus conteúdos):

* 📚 **[docs/README.md](docs/README.md)**: Índice geral e catálogo central de documentação técnica.
* 📖 **[GLOSSARY.md](GLOSSARY.md)**: Vocabulário ubíquo oficial e definições de domínio.
* 🏛️ **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: Mapa de componentes, fluxo de dados e decisões justificadas.
* 📋 **[docs/adr/](docs/adr/)**: Registros de Decisões de Arquitetura (Task Scheduler, Playwright, CDN, etc.).
* 📐 **[docs/specs/](docs/specs/)**: Especificações técnicas aprovadas.
* 🎟️ **[docs/tickets/](docs/tickets/)**: Tickets de implementação e critérios de aceitação.
* 💡 **[docs/guides/](docs/guides/)**: Guias operacionais (servidor doméstico) e manual de banners ([`style_guide_banners.md`](docs/guides/style_guide_banners.md)).
* 📜 **[docs/retrospectives/](docs/retrospectives/)**: Histórico de lições aprendidas e dívidas técnicas conhecidas.

---

## 2. Regras Mandatórias de Isolamento e Integridade (Lições Comprovadas)

1. **Isolamento de Testes e Estado de Produção:**
   * Testes automatizados **jamais** devem modificar arquivos de estado real, credenciais, agendamentos do Windows ou realizar conexões de rede / envios reais de e-mail.
   * A trava de envio diário ([`data/ultimo_envio.txt`](data/ultimo_envio.txt)) deve permanecer intocada durante qualquer execução de teste.
   * Utilize mocks, injeção de dependências ou diretórios temporários (`tempfile.TemporaryDirectory`) para isolar completamente a persistência e as chamadas externas.

2. **Resiliência de Snapshots, Integridade e Persistência Atômica (Spec 0007):**
   * **Proibição de Sobrescrita Destrutiva (Invariante DEF-01):** Falhas de coleta (`FAILED`), coletas não executadas (`NOT_RUN`) ou parciais sem novos dados (`PARTIAL`) **jamais** devem sobrescrever snapshots válidos consolidados em disco com listas vazias `[]`. A gravação física em disco só deve atualizar o arquivo ativo quando houver itens válidos ou estado `EMPTY` comprovadamente coletado com sucesso.
   * **Desacoplamento Estrito de I/O nos Coletores:** Módulos coletores (`src/collectors/`) devem operar puramente em memória (zero locks, sem escrita direta em disco) e retornar instâncias imutáveis de `SourceCollectionResult[T]` com status de `SourceStatus`. A gravação física é responsabilidade centralizada e exclusiva de `DailyIngestionBatch.save_snapshot()`.
   * **Persistência Parcial e Integridade Temporal de Snapshots:** Execuções de passos isolados de coleta (`python main.py --step collect-<fonte>`) devem atualizar **exclusivamente** o arquivo correspondente à fonte alvo (ex: `github_trending.json`) e o seu nó específico no manifesto v2 (`snapshot_metadata.json`). **Nunca** mescle dados antigos de outras fontes sob um novo `collected_at` sem coleta real. O lote em memória de uma coleta parcial reflete apenas os itens coletados naquele ciclo.
   * **Integridade e Recuperação de Backups (.prev):** A recuperação de backups `.prev` por `load_snapshot()` exige verificação estrita de integridade contra o hash SHA-256 esperado registrado no manifesto (`snapshot_metadata.json`). Arquivos corrompidos ou com hash divergente devem ser imediatamente movidos para `data/quarantine/` via `mover_para_quarentena()`. Jamais promova ou consuma backups sem validação de integridade.
   * **Diferenciação Estrita de Travas Operacionais:** Diferencie claramente a **Trava Diária** (`data/ultimo_envio.txt`, mecanismo persistente entre reinicializações para idempotência de calendário) do **Lock de Processo** (`data/.pipeline.lock` e `data/snapshot.lock`, travas efêmeras de SO via `msvcrt`/`fcntl` com encerramento limpo via `sys.exit(0)` em caso de concorrência).
   * **Reconstituição Histórica sob Demanda:** A reconstituição completa do snapshot histórico em disco deve ocorrer apenas quando solicitada explicitamente (`DailyIngestionBatch.load_snapshot()`) ou na etapa isolada de síntese (`--step summarize`).

3. **Testes Herméticos:**
   * Testes devem funcionar de forma autônoma em qualquer ambiente (inclusive CI/CD limpo), sem depender da existência de `.env`, credenciais reais ou conectividade com a internet.
   * Isole chamadas de configuração de credenciais, sockets de rede e serviços externos (`smtp`, `webbrowser`, APIs de IA).
   * **Guardrails Automáticos:** A suíte utiliza `tests/guardrails.py` para interceptar sockets TCP/UDP, resolução DNS e inicialização real de navegadores Playwright.
   * **Comando Canônico:** A suíte completa deve ser executada com `python -m unittest discover -s tests -t . -v` para assegurar a carga do pacote `tests/__init__.py`. Execuções seletivas devem utilizar notação de módulo pontuada (`python -m unittest tests.<modulo> -v`).
   * **Limite de Subprocessos Filhos:** Subprocessos crus (`subprocess.Popen([sys.executable, ...])`) possuem espaço de memória independente e não herdam automaticamente os interceptores do processo-pai; testes de concorrência multiprocesso devem se ater a operações locais de lock/IPC.

4. **Isolamento de Branches e Preservação da Working Tree (Preflight Git):**
   * **Preflight Mandatório:** Antes de planejar código ou criar branches, execute `git status --short` e `git branch --show-current`.
   * **Working Tree Suja e Parada Obrigatória:** Se houver arquivos modificados, adicionados ou não rastreados que não pertençam à tarefa atual, **interrompa imediatamente** qualquer operação de troca ou criação de branch. Apresente o `git status --short` ao desenvolvedor e aguarde decisão humana explícita.
   * **Proibição Estrita de Comandos Destrutivos:** Jamais execute automaticamente qualquer operação que descarte, sobrescreva, mova ou oculte alterações locais (incluindo `git stash`, `git reset`, `git clean`, `git checkout`, `git switch` ou `git restore`) quando a working tree contiver alterações locais não salvas.
   * **Atualização Remota Obrigatória:** Antes de derivar novas branches de `origin/main`, execute `git fetch origin`. Caso o fetch falhe (timeout, ausência de rede ou credenciais), **interrompa o fluxo** e informe a limitação ao usuário antes de prosseguir.
   * **Git Worktree como Contingência (Exclusivamente sob Decisão Humana):** O uso de `git worktree add` não é fluxo padrão e jamais deve ser adotado automaticamente pelo agente. Trata-se de recurso de contingência para quando alterações locais conflitarem e não puderem ser comitadas de imediato, exigindo aprovação humana explícita e validação prévia de compatibilidade com o workspace e ferramentas de edição. A replicação de arquivos não rastreados necessários deve ser estritamente seletiva e autorizada, sendo expressamente proibido copiar automaticamente arquivos com credenciais ou segredos (como `.env`).

---

## 3. Princípios de Engenharia e Padrões de Código

* **KISS, YAGNI e o Menor Delta:** Implemente a menor alteração suficiente para resolver o problema. Não introduza padrões, factories reflexivas, registries dinâmicos ou contêineres genéricos sem necessidade concreta e justificada.
* **Higiene da Raiz (Anti-Poluição):** Jamais crie scripts descartáveis, relatórios avulsos ou dumps JSON na raiz. Utilize as pastas de destino corretas (`reports/`, `data/`) ou ambiente efêmero/scratch isolado.
* **Padrão de Banners e Assets:** Novos banners devem seguir estritamente o layout de subpastas (`assets/banners/geral/`, `festivos/` ou `padrao/`), proporção 1360x760 px e registro no `assets/banners/manifesto.json` conforme [`docs/guides/style_guide_banners.md`](docs/guides/style_guide_banners.md).
* **Tipagem e Protocolos Pragmáticos:** Utilize `typing.Protocol` para desacoplamento de interfaces e `dataclasses` para entidades de domínio. Utilize `@runtime_checkable` **apenas** quando houver necessidade real comprovada de verificação de tipos em tempo de execução (`isinstance`).
* **Segurança de Segredos:** Jamais versione ou logue credenciais do `.env` ou cookies da pasta de sessão do Playwright (`.session/`). Senhas e tokens devem ser manipulados exclusivamente em memória e limpos de espaços em branco.
* **Preservação de Compatibilidade:** Ao refatorar funções públicas ou seams existentes (ex: `enviar_relatorio_email`), preserve a assinatura original funcionando como facade para evitar quebrar pontos de chamada legados.
* **Segurança por Padrão (Sanitização e TLS):** Dados externos (Markdown, feeds, redes sociais, IA) nunca devem ser interpolados diretamente no HTML sem tratamento contextual: utilize `format_inline()` para Markdown suportado e `html.escape(..., quote=True)` para atributos e textos puros. URLs devem ser validadas com `_is_safe_url()` antes da criação de hyperlinks (`<a>`); o escape isolado de caracteres não torna uma URL segura. Conexões de rede criptografadas via `smtplib.SMTP_SSL` devem obrigatoriamente fornecer `context=ssl.create_default_context()`, preservando verificação ativa de certificados e hostname. Novos campos alimentados por dados externos exigem testes de regressão correspondentes.

---

## 4. Preservação das Automações e Comandos CLI

* **Contrato Operacional de Códigos de Saída (CLI):**
  * `sys.exit(0)`: Sucesso ou encerramento silencioso (já enviado hoje ou execução antes das 08:00 sem `--force`).
  * `sys.exit(1)`: Falha fatal de execução que requer alerta imediato via Toast.
  * `sys.exit(2)`: Falha de conexão de rede após timeout de 60s (contrato com o Windows Task Scheduler para retentativas em segundo plano).
  * *Atenção:* O código de saída é um contrato operacional, não uma garantia absoluta de entrega. Exija testes antes de modificar esse comportamento.
* **Preservação de Scripts Operacionais:** Não altere a lógica de `executar.bat`, `scripts/executar_silencioso.vbs` ou `scripts/setup_task.ps1` sem demanda explícita.
* **Segurança Estrita e Limites do Modo `--preview`:** O comando `python main.py --preview` (ou com `--step email --preview`) renderiza o layout Bento Grid localmente em `reports/preview.html`, dispara o navegador e emite Toast, garantindo **zero conexões SMTP** e **zero alterações** na trava diária (`data/ultimo_envio.txt`). **Atenção:** Quando executado com `--step all --preview`, o pipeline realiza raspagem de rede real nas fontes e síntese real com a API de IA; portanto, **não constitui teste hermético** e não deve ser utilizado como substituto de testes automatizados com mocks.
* **Execução Segura no Terminal Windows (PowerShell):** Comandos simples de inspeção em uma única linha (ex: `python -c "import sys; print(sys.version)"`) são permitidos. Para rotinas que envolvam lógica multilinha, manipulação de JSON complexo ou caracteres acentuados, evite passar strings embutidas em `python -c` devido a problemas conhecidos de escape e codificação do PowerShell. Prefira gravar a rotina em um script Python temporário em pasta descartável (ex: diretório temporário do SO ou scratch do ambiente) com codificação UTF-8 explícita e executá-lo via `python <caminho>`.

---

## 5. Rastreabilidade e Critérios de Conclusão (Definition of Done)

* **Rastreabilidade Proporcional:** Demandas complexas e novas funcionalidades devem seguir o fluxo `Spec → Ticket → Testes → Code Review`. Correções pontuais e pequenas refatorações dispensam formalização burocrática pesada, mas exigem clareza nos commits e no rationale.
* **Execução Gradual de Testes:** Execute os testes relevantes durante a implementação do código e a suíte completa canônica (`python -m unittest discover -s tests -t . -v`) antes de finalizar a integração.
* **Code Review Baseado em Evidências:** Avalie alterações sob dois eixos independentes:
  1. *Standards:* aderência aos padrões de código, ausência de smells de Fowler e manutenibilidade.
  2. *Spec:* verificação objetiva do cumprimento dos requisitos solicitados, ausência de scope creep e preservação dos comportamentos existentes.
