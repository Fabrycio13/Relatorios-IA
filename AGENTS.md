# 🤖 Diretrizes para Agentes de IA (AGENTS.md)

Este documento orienta agentes de IA trabalhando neste repositório. O objetivo é garantir **simplicidade**, **segurança operacional**, **alta testabilidade** e **preservação dos comportamentos existentes**.

---

## 1. Mapa de Contexto e Referências Rápidas

Antes de planejar ou alterar código, consulte a documentação oficial existente (não duplique seus conteúdos):

* 📖 **[GLOSSARY.md](GLOSSARY.md)**: Vocabulário ubíquo oficial e definições de domínio.
* 🏛️ **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: Mapa de componentes, fluxo de dados e decisões justificadas.
* 📋 **[docs/adr/](docs/adr/)**: Registros de Decisões de Arquitetura (Task Scheduler, Playwright, CDN, etc.).
* 📐 **[docs/specs/](docs/specs/)**: Especificações técnicas aprovadas.
* 🎟️ **[docs/tickets/](docs/tickets/)**: Tickets de implementação e critérios de aceitação.
* 📜 **[docs/retrospectives/](docs/retrospectives/)**: Histórico de lições aprendidas e dívidas técnicas conhecidas.

---

## 2. As Três Regras Mandatórias de Isolamento (Lições Comprovadas)

1. **Isolamento de Testes e Estado de Produção:**
   * Testes automatizados **jamais** devem modificar arquivos de estado real, credenciais, agendamentos do Windows ou realizar conexões de rede / envios reais de e-mail.
   * A trava de envio diário ([`data/ultimo_envio.txt`](data/ultimo_envio.txt)) deve permanecer intocada durante qualquer execução de teste.
   * Utilize mocks, injeção de dependências ou diretórios temporários (`tempfile.TemporaryDirectory`) para isolar completamente a persistência e as chamadas externas.

2. **Persistência Parcial e Integridade Temporal de Snapshots:**
   * Execuções de passos isolados de coleta (`python main.py --step collect-<fonte>`) devem atualizar **exclusivamente** o arquivo correspondente à fonte alvo (ex: `github_trending.json`) e o seu registro pontual em `snapshot_metadata.json`.
   * **Nunca** mescle dados antigos de outras fontes sob um novo `collected_at`. O lote em memória de uma coleta parcial deve refletir apenas os itens coletados naquele ciclo.
   * A reconstituição completa do snapshot histórico em disco deve ocorrer apenas quando solicitada explicitamente (`DailyIngestionBatch.load_snapshot()`) ou na etapa isolada de síntese (`--step summarize`).

3. **Testes Herméticos:**
   * Testes devem funcionar de forma autônoma em qualquer ambiente (inclusive CI/CD limpo), sem depender da existência de `.env`, credenciais reais ou conectividade com a internet.
   * Isole chamadas de configuração de credenciais, sockets de rede e serviços externos (`smtp`, `webbrowser`, APIs de IA).
   * **Guardrails Automáticos:** A suíte utiliza `tests/guardrails.py` para interceptar sockets TCP/UDP, resolução DNS e inicialização real de navegadores Playwright.
   * **Comando Canônico:** A suíte completa deve ser executada com `python -m unittest discover -s tests -t . -v` para assegurar a carga do pacote `tests/__init__.py`. Execuções seletivas devem utilizar notação de módulo pontuada (`python -m unittest tests.<modulo> -v`).
   * **Limite de Subprocessos Filhos:** Subprocessos crus (`subprocess.Popen([sys.executable, ...])`) possuem espaço de memória independente e não herdam automaticamente os interceptores do processo-pai; testes de concorrência multiprocesso devem se ater a operações locais de lock/IPC.

---

## 3. Princípios de Engenharia e Padrões de Código

* **KISS, YAGNI e o Menor Delta:** Implemente a menor alteração suficiente para resolver o problema. Não introduza padrões, factories reflexivas, registries dinâmicos ou contêineres genéricos sem necessidade concreta e justificada.
* **Tipagem e Protocolos Pragmáticos:** Utilize `typing.Protocol` para desacoplamento de interfaces e `dataclasses` para entidades de domínio. Utilize `@runtime_checkable` **apenas** quando houver necessidade real comprovada de verificação de tipos em tempo de execução (`isinstance`).
* **Segurança de Segredos:** Jamais versione ou logue credenciais do `.env` ou cookies da pasta de sessão do Playwright (`.session/`). Senhas e tokens devem ser manipulados exclusivamente em memória e limpos de espaços em branco.
* **Preservação de Compatibilidade:** Ao refatorar funções públicas ou seams existentes (ex: `enviar_relatorio_email`), preserve a assinatura original funcionando como facade para evitar quebrar pontos de chamada legados.

---

## 4. Preservação das Automações e Comandos CLI

* **Contrato Operacional de Códigos de Saída (CLI):**
  * `sys.exit(0)`: Sucesso ou encerramento silencioso (já enviado hoje ou execução antes das 08:00 sem `--force`).
  * `sys.exit(1)`: Falha fatal de execução que requer alerta imediato via Toast.
  * `sys.exit(2)`: Falha de conexão de rede após timeout de 60s (contrato com o Windows Task Scheduler para retentativas em segundo plano).
  * *Atenção:* O código de saída é um contrato operacional, não uma garantia absoluta de entrega. Exija testes antes de modificar esse comportamento.
* **Preservação de Scripts Operacionais:** Não altere a lógica de `executar.bat`, `scripts/executar_silencioso.vbs` ou `scripts/setup_task.ps1` sem demanda explícita.
* **Segurança Estrita do Modo `--preview`:** O comando `python main.py --preview` (ou com `--step email --preview`) deve renderizar o layout Bento Grid localmente em `reports/preview.html`, disparar o navegador e emitir Toast, garantindo **zero conexões SMTP** e **zero alterações** na trava diária.

---

## 5. Rastreabilidade e Critérios de Conclusão (Definition of Done)

* **Rastreabilidade Proporcional:** Demandas complexas e novas funcionalidades devem seguir o fluxo `Spec → Ticket → Testes → Code Review`. Correções pontuais e pequenas refatorações dispensam formalização burocrática pesada, mas exigem clareza nos commits e no rationale.
* **Execução Gradual de Testes:** Execute os testes relevantes durante a implementação do código e a suíte completa canônica (`python -m unittest discover -s tests -t . -v`) antes de finalizar a integração.
* **Code Review Baseado em Evidências:** Avalie alterações sob dois eixos independentes:
  1. *Standards:* aderência aos padrões de código, ausência de smells de Fowler e manutenibilidade.
  2. *Spec:* verificação objetiva do cumprimento dos requisitos solicitados, ausência de scope creep e preservação dos comportamentos existentes.
