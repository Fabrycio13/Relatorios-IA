# 📚 Central de Documentação (The Engineering Gazette)

Bem-vindo à documentação oficial do **Diário de Engenharia: IA & Coding Agents**.

Este diretório reúne as especificações técnicas, registros de decisão arquitetural (ADRs), manuais operacionais e critérios de engenharia do repositório.

---

## 🧭 Mapa de Navegação da Documentação

### 🏛️ Arquitetura e Engenharia Central
* **[`ARCHITECTURE.md`](ARCHITECTURE.md)**: Documento-mãe da arquitetura. Detalha o fluxo sequencial do pipeline, padrões de Clean Architecture, isolamento de falhas, resiliência de rede e contratos de saída da CLI.

---

### 💻 Guias Práticos e Manuais Operacionais (`docs/guides/`)
* **[`guides/migracao_notebook.md`](guides/migracao_notebook.md)**: Passo a passo de 5 minutos para transformar um notebook com tela desligada e tampa fechada em servidor doméstico 24/7 para envio autônomo dos relatórios com IP residencial real.
* **[`guides/style_guide_banners.md`](guides/style_guide_banners.md)**: Manual estético de arte, dimensões (1360 × 760 px Retina 2x), paletas, pesos (220–280 KB) e playbook de prompts de IA para os estilos *Pintura Digital Japonesa* e *Chilogravura Vitoriana*.

---

### 📋 Decisões de Arquitetura (`docs/adr/`)
Registros formais de decisões arquiteturais (*Architecture Decision Records*):
* **[`adr/0001-agendamento-hibrido-windows.md`](adr/0001-agendamento-hibrido-windows.md)**: Estratégia de duplo gatilho (08:00 + Logon) no Windows Task Scheduler.
* **[`adr/0002-coleta-playwright-sessao-x.md`](adr/0002-coleta-playwright-sessao-x.md)**: Raspagem de feed e radar VIP com persistência de cookies no Playwright.
* **[`adr/0003-cdn-raw-banners-email.md`](adr/0003-cdn-raw-banners-email.md)**: Hospedagem imutável de banners de alta resolução no GitHub Raw.
* **[`adr/0004-resiliencia-rede-pos-boot.md`](adr/0004-resiliencia-rede-pos-boot.md)**: Pré-verificação de socket TCP com timeout de 60s pós-boot do sistema.

---

### 📐 Especificações Técnicas (`docs/specs/`)
Especificações de produto aprovadas e implementadas:
* **[`specs/0001-daily-ingestion-batch.md`](specs/0001-daily-ingestion-batch.md)**: Modelo unificado de lote de ingestão diária.
* **[`specs/0002-protocolo-de-ingestao.md`](specs/0002-protocolo-de-ingestao.md)**: Protocolo estrutural `IngestionSource` e orquestrador de fontes.
* **[`specs/0003-delivery-channel.md`](specs/0003-delivery-channel.md)**: Protocolo `DeliveryChannel` e despachador de entregas.
* **[`specs/0004-dizer-do-dia-takeaway-editorial.md`](specs/0004-dizer-do-dia-takeaway-editorial.md)**: Síntese editorial e citação de impacto no resumo.
* **[`specs/0005-banners-rotativos-e-comemorativos.md`](specs/0005-banners-rotativos-e-comemorativos.md)**: Sistema de hierarquia em 3 Tiers, ciclo de exaustão e feriados.
* **[`specs/0006-seguranca-sanitizacao-e-governanca.md`](specs/0006-seguranca-sanitizacao-e-governanca.md)**: Governança de segurança, invariantes anti-XSS no renderer Bento Grid, sanitização contextual, TLS com validação de certificados no SMTP e fronteiras de confiança.
* **[`specs/0007-resiliencia-de-snapshots-e-integridade-da-ingestao.md`](specs/0007-resiliencia-de-snapshots-e-integridade-da-ingestao.md)**: Resiliência transacional de snapshots, integridade de ingestão e desacoplamento de I/O.

---

### 🎟️ Tickets de Implementação ([`docs/tickets/`](tickets/))
Critérios de aceitação e rastreabilidade de tarefas executadas (Tickets 01 ao 22), agrupados por especificação técnica:

* **Specs 0001 a 0003 — Modernização Arquitetural e Ingestão:**
  * [`Ticket 01`](tickets/01-daily-ingestion-batch-model.md) · [`02`](tickets/02-adapt-summarizer-to-batch.md) · [`03`](tickets/03-integrate-batch-in-main-checkpoint.md) · [`04`](tickets/04-ingestion-source-protocol-and-adapters.md) · [`05`](tickets/05-ingestion-pipeline-orchestrator.md) · [`06`](tickets/06-integrate-ingestion-pipeline-in-main-checkpoint.md) · [`07`](tickets/07-delivery-channel-protocol-and-adapters.md) · [`08`](tickets/08-delivery-dispatcher-and-preview-cli.md) · [`09`](tickets/09-e2e-delivery-integration-and-regression-checkpoint.md): lote diário `DailyIngestionBatch`, protocolos de ingestão e entrega, e testes E2E.
* **Spec 0005 — Banners Rotativos e Festivos:**
  * [`Ticket 10`](tickets/10-banner-comemorativo-feriados-e-fallback-e2e.md) · [`11`](tickets/11-catalogo-rotativo-persistencia-atomica-ciclo-envio-e2e.md) · [`12`](tickets/12-links-hd-cli-style-guide-checkpoint-e2e.md): hierarquia de seleção em 3 Tiers, catálogo geral rotativo, feriados fixos/móveis e links HD.
* **Spec 0006 — Segurança, Sanitização e Governança:**
  * [`Ticket 13`](tickets/13-invariantes-anti-xss-e-estrutura-bento-grid.md) · [`14`](tickets/14-diretriz-seguranca-por-padrao-agents-md.md) · [`15`](tickets/15-fronteiras-de-confianca-architecture-md.md) · [`16`](tickets/16-unificacao-conexao-smtp-segura-e-testes-protocolo.md): invariantes anti-XSS no Bento Grid, Safe by Default no `AGENTS.md`, fronteiras de confiança e unificação SMTP com TLS seguro.
* **Spec 0007 — Resiliência de Snapshots e Integridade:**
  * [`Ticket 17`](tickets/17-modelos-imutaveis-e-invariantes-de-resultado.md) · [`18`](tickets/18-lock-de-processo-e-primitivas-de-durabilidade.md) · [`19`](tickets/19-schema-do-manifesto-migracao-legada-e-frescor.md) · [`20`](tickets/20-persistencia-atomica-e-recuperacao-idempotente-de-snapshots.md) · [`21`](tickets/21-coletores-puros-em-memoria-e-desacoplamento-de-io.md) · [`22`](tickets/22-orquestracao-de-pipeline-cli-e-governanca-de-sintese.md): modelos imutáveis, lock de processo, manifesto v2, persistência atômica com `.prev` e quarentena, coletores puros e governança CLI.

---

### 📜 Retrospectivas & Lições Aprendidas (`docs/retrospectives/`)
* **[`retrospectives/0001-modernizacao-arquitetural.md`](retrospectives/0001-modernizacao-arquitetural.md)**: Lições da transição para Clean Architecture.
* **[`retrospectives/0002-qualidade-coleta-e-rastreabilidade.md`](retrospectives/0002-qualidade-coleta-e-rastreabilidade.md)**: Melhorias em resiliência e sanitização de fontes.
* **[`retrospectives/0003-banners-rotativos-e-concorrencia.md`](retrospectives/0003-banners-rotativos-e-concorrencia.md)**: Travas de concorrência, atomismo e rotação cíclica.
* **[`retrospectives/0004-seguranca-sanitizacao-e-governanca.md`](retrospectives/0004-seguranca-sanitizacao-e-governanca.md)**: Lições da Spec 0006, governança Git, modelagem adversarial e execução segura no Windows.
* **[`retrospectives/0005-resiliencia-snapshots-e-integridade-ingestao.md`](retrospectives/0005-resiliencia-snapshots-e-integridade-ingestao.md)**: Resiliência de snapshots (Spec 0007), persistência atômica, eliminação do DEF-01/ARC-01 e recuperação pós-crash.
