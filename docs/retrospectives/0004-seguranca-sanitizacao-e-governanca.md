# Retrospectiva: Segurança, Sanitização, TLS e Governança (Spec 0006)

**Data:** 09 de Novembro de 2026
**Status do Projeto:** 186/186 testes automatizados aprovados | CI pós-merge no GitHub Actions 100% verde (Run #40)
**Escopo Analisado:** Ciclo completo de engenharia da Spec 0006 (Tickets 13, 14, 15 e 16 / PR #16 / Commit `d18c95b`), abrangendo: suíte canônica de testes de invariantes anti-XSS no renderer Bento Grid, governança Safe by Default em `AGENTS.md`, formalização de fronteiras de confiança em `docs/ARCHITECTURE.md`, unificação e gerenciamento de contexto seguro de conexões SMTP TLS com validação de certificados e hostname em `src/core/smtp.py`, e remoção de dependência desnecessária (`Pillow`).

---

## 1. Contexto e Trajetória do Ciclo

A Spec 0006 percorreu um ciclo completo e rigoroso de engenharia de software guiada por IA:

$$\text{Auditoria de Segurança} \longrightarrow \text{Grill-with-Docs} \longrightarrow \text{Decisões D1-D4} \longrightarrow \text{Spec (Rev 1 a 5.2)} \longrightarrow \text{Tickets 13-16} \longrightarrow \text{TDD} \longrightarrow \text{Code Review} \longrightarrow \text{CI} \longrightarrow \text{Merge}$$

A necessidade da especificação emergiu de uma auditoria preventiva de AppSec no layout tipográfico *The Engineering Gazette*, onde dados externos (provenientes de feeds RSS, ArXiv, GitHub e redes sociais) e Markdown gerado por LLMs são interpolados dinamicamente no HTML do e-mail. Embora sanitizações pontuais tivessem sido realizadas, a ausência de um teste estrutural de invariantes representava risco iminente de regressão em futuras alterações de template.

Adicionalmente, identificou-se assimetria e duplicação na conexão SMTP SSL entre o canal oficial de entrega (`src/delivery/base.py`) e a rotina de verificação de integridade (`src/core/healthcheck.py`), ambas sem injeção explícita de `SSLContext` com validação estrita de certificados e hostname.

---

## 2. O que Funcionou Bem (Práticas a Preservar)

1. **Aderência Exemplar ao Princípio do Menor Delta (KISS/YAGNI):**
   * Rejeição consciente de ferramentas pesadas desproporcionais: a adoção de SAST isolado com Bandit foi evitada (após comprovação de que não detecta TLS em `SMTP_SSL` e gera ruído em testes), assim como testes com Hypothesis ou AST parsers caseiros.
   * A dependência desnecessária `Pillow` foi removida de `requirements.txt` sem qualquer impacto, visto que a aplicação realiza renderização puramente vetorial e HTML/CSS.
   * Centralização mínima: a função `conectar_smtp_ssl` em `src/core/smtp.py` possui apenas ~35 linhas, consumindo estritamente a biblioteca padrão Python.

2. **Efetividade do `grill-with-docs` com o Código-Fonte CPython:**
   * A inspeção direta do código CPython (`smtplib.py`) nas versões 3.12 e 3.13 comprovou que `smtplib.SMTP` já implementa nativamente um context manager robusto, despachando `docmd("QUIT")` e executando `finally: self.close()`.
   * Essa investigação técnica evitou que criássemos uma camada caseira de wrapping ou gerenciamento manual de sockets, além de elucidar o comportamento exato de substituição de exceção quando o servidor responde com erro ao comando `QUIT` após uma falha de autenticação.

3. **Arquitetura de Testes Herméticos e Simulação Real de Protocolo (`FakeSMTPServer`):**
   * Em vez de mockar superficialmente `__enter__` e `__exit__`, a classe `FakeSMTPServer` em `tests/test_smtp.py` herdou diretamente de `smtplib.SMTP`, permitindo que o código real do runtime CPython executasse suas transições de contexto.
   * A suíte canônica de 186 testes rodou em apenas 1,25s de forma totalmente determinística, com zero conexões de rede ativas (bloqueadas por `tests/guardrails.py`) e zero vazamento de recursos (`ResourceWarning`).

4. **Decomposição Coesa em Tickets Independentes (Tickets 13 a 16):**
   * Os 4 tickets apresentaram fronteiras perfeitamente desacopladas: Ticket 13 (Invariantes Renderer), Ticket 14 (Governança `AGENTS.md`), Ticket 15 (Arquitetura `ARCHITECTURE.md`) e Ticket 16 (SMTP `core.smtp`).
   * A implementação pôde seguir um fluxo TDD contínuo sem bloqueios cruzados ou dependências circulares.

5. **Auditoria Dupla de Code Review (Standards & Spec):**
   * A avaliação independente comprovou que a PR não continha code smells do catálogo de Fowler, não introduziu dependências externas e atendeu a todos os critérios de aceitação formalizados na Revisão 5.2.

---

## 3. O que Funcionou Mal e Gerou Retrabalho (Análise Crítica)

1. **Contratos Iniciais "Otimistas" e Proliferação de Revisões da Spec (5.2 Revisões):**
   * A especificação exigiu 5 revisões principais e 2 sub-revisões antes da aprovação final.
   * O agente propôs reiteradamente validações superficiais que precisaram de intervenções humanas cirúrgicas para serem corrigidas:
     - *Revisão 3:* `meta` e `style` constavam contraditoriamente em `PROHIBITED_TAGS` e `ALLOWED_TEMPLATE_TAGS`.
     - *Revisão 4:* Máquina de estados ingênua baseada em flags booleanas (`in_head`), permitindo que tags `<head>` injetadas reativassem o estado de cabeçalho.
     - *Revisão 5:* Fechamento de tags em `handle_endtag` não validava ordem nem impedia fechamento de `</head>` com `<style>` aberto.
     - *Revisão 5.1:* A validação de `<meta>` limitava-se a contar `len(matched) == 4`, sem comparar os atributos reais com `EXPECTED_STATIC_METAS`.
     - *Ressalva D1 (Aprovação):* A conversão de atributos para `dict()` engolia silenciosamente atributos duplicados na lista crua do `HTMLParser`.
   * *Causa Raiz:* O agente focou na "intenção" dos requisitos em vez de exercitar cenários de evasão adversária contra seu próprio pseudo-código.

2. **Poluição da Working Tree e Coreografia Arriscada de Branches:**
   * O trabalho foi iniciado enquanto a working tree continha artefatos de desenvolvimento local (banners 36 a 38, relatórios históricos e modificações em `manifesto.json`).
   * Os commits da Spec 0006 foram inicialmente aplicados na branch `fix/python-3-12-compatibility`, misturados com commits de compatibilidade anteriores (`822f667` já mergeado e `aa22fc9` com remoção parcial de Pillow).
   * Para abrir a PR #16 de forma limpa, foi necessária intervenção humana detalhada exigindo `git stash push -u`, criação de branch limpa `feat/seguranca-governanca-spec-0006` a partir de `origin/main`, cherry-pick ordenado de 7 commits e validação cautelosa para garantir que os arquivos locais não fossem publicados.
   * *Causa Raiz:* Ausência de isolamento mandatória de branch (`git worktree` ou branch limpa isolada) antes de iniciar a fase de implementação.

3. **Incompatibilidade de Comandos Multiline no Shell Windows (PowerShell Quoting):**
   * Tentativas repetidas de invocar a API do GitHub e testes inline via `python -c "..."` falharam por interpretação do PowerShell (`op_Addition:String`, `unterminated string literal`), além de corrupção de encoding UTF-8 no título da PR (`sanitizao`), exigindo um script corretivo posterior (`fix_pr_title.py`).
   * *Causa Raiz:* Uso de strings multilinha complexas inline no PowerShell em vez de scripts dedicados no diretório `scratch/`.

4. **Dependência de Scripts REST Caseiros pela Ausência da CLI `gh`:**
   * A ausência da ferramenta GitHub CLI (`gh`) no ambiente Windows exigiu a criação de 5 scripts Python pontuais para consultar credenciais no Windows Credential Manager (`git credential fill`), abrir a PR, monitorar a CI e disparar o merge via API.
   * Embora os scripts tenham sido 100% eficazes, representaram esforço repetitivo de infraestrutura efêmera.

---

## 4. Diferenciação Epistemológica: Fatos, Observações e Hipóteses

* **Fato Comprovado 1:** A suíte de 186 testes locais e a CI remota (Run #40 no Python 3.13) aprovaram 100% das asserções de invariantes anti-XSS e testes de protocolo SMTP com TLS estrito sem quebras de regressão.
* **Fato Comprovado 2:** A PR #16 incluiu exatamente os 17 arquivos estritamente pertencentes à Spec 0006, sem vazar banners ou relatórios locais.
* **Fato Comprovado 3:** Nenhuma das falhas conceituais da máquina de estados do parser canário foi apontada pelo agente; todas foram identificadas por revisão humana minuciosa.
* **Observação 1:** As 5.2 revisões da Spec consumiram tempo significativo de contexto, mas geraram uma implementação que passou de primeira nos testes e na CI, sem nenhum bug detectado no code review final.
* **Hipótese:** Se houvesse uma checklist adversária obrigatória na skill de elaboração de specs de segurança, a máquina de estados teria sido modelada corretamente já na Revisão 2.

---

## 5. Candidatos a Melhoria do Processo

Abaixo estão os candidatos a melhoria decorrentes deste ciclo, ordenados rigorosamente por severidade.

---

### Candidato 1 (Severidade Alta): Protocolo de Isolamento de Branch e Proteção de Working Tree "Suja"
* **Problema Observado:** Implementação de nova funcionalidade iniciada em branch preexistente (`fix/python-3-12-compatibility`) contendo modificações locais não rastreadas, exigindo cherry-picks complexos e arriscando vazamento de arquivos locais em PRs.
* **Evidência Concreta:** Necessidade de intervenção humana explícita para guiar `git stash push -u`, criação de `feat/seguranca-governanca-spec-0006` off `origin/main`, cherry-pick seletivo de 7 commits e reinjeção de stash.
* **Causa Raiz:** O fluxo operacional permitiu que o agente iniciasse a implementação sem checar previamente se o branch base estava limpo e apontando diretamente para `origin/main`.
* **Melhoria Recomendada:**
  1. Formalizar no `AGENTS.md` (seção 4) a regra mandatória: *Antes de iniciar a implementação de qualquer Ticket/Spec, o agente deve verificar `git status --short`. Havendo arquivos locais não rastreados, deve isolá-los ou criar uma branch limpa baseada em `origin/main` (`git checkout -b feat/<nome> origin/main`), nunca acumulando commits de novas specs sobre branches antigas.*
* **Benefício Esperado:** Histórico Git limpo por construção, zero necessidade de cherry-picks corretivos e blindagem contra vazamento de arquivos locais não commitados.
* **Custo de Implementação:** Mínimo (apenas adição de diretriz no `AGENTS.md`).
* **Risco de Complexidade:** Zero (elimina retrabalho manual).

---

### Candidato 2 (Severidade Média): Checklist de Modelagem Adversária para Parsers e Máquinas de Estado em Specs
* **Problema Observado:** A especificação passou por 5 revisões sucessivas porque o agente propôs sucessivamente contratos fracos (flags booleanas reativáveis, ausência de validação de atributos em meta, supressão de duplicatas via `dict()`).
* **Evidência Concreta:** Revisões 3, 4, 5, 5.1 e Ressalva D1 da Spec 0006, todas apontando falhas na máquina de estados de parsing HTML.
* **Causa Raiz:** O agente projeta parsers assumindo conformidade do documento de entrada (happy path), negligenciando cenários adversários em que o atacante injeta tags parciais, fora de ordem ou atributos duplicados.
* **Melhoria Recomendada:**
  * Incluir na elaboração de especificações de segurança ou parsers estruturais a exigência de responder explicitamente à **Matriz de Resiliência de Estado**:
    1. *Como o parser reage a tags duplicadas ou reabertas fora de ordem?*
    2. *Como o parser trata atributos duplicados antes de qualquer conversão para dicionário?*
    3. *O encerramento do documento audita se blocos filhos (ex: `<style>`) foram devidamente fechados?*
* **Benefício Esperado:** Redução de retrabalho na fase de Spec, convergindo em no máximo 2 revisões para componentes de validação estrutural.
* **Custo de Implementação:** Baixo (diretriz documental).
* **Risco de Complexidade:** Zero.

---

### Candidato 3 (Severidade Média): Padrão Operacional contra Fragilidade de Aspas no PowerShell Windows
* **Problema Observado:** Falhas intermitentes ao rodar comandos inline multilinha via `run_command` no PowerShell (`python -c "..."`), gerando erros de sintaxe e quebra de encoding de caracteres UTF-8.
* **Evidência Concreta:** Falha de execução ao inspecionar a PR (`op_Addition:String`) e título com acento corrompido na PR (`sanitizao`), exigindo execução corretiva via PATCH.
* **Causa Raiz:** Diferenças de escaping de aspas, quebras de linha e interpolação de strings no PowerShell em relação a shells POSIX/Bash.
* **Melhoria Recomendada:**
  * Adotar como diretriz operacional estrita para agentes em ambiente Windows: qualquer código Python de automação, inspeção de API ou validação com mais de 2 linhas deve ser obrigatoriamente escrito em arquivo temporário no diretório de scratch persistente (`<appDataDir>/brain/<conversation-id>/scratch/script.py`) com codificação UTF-8 explícita e executado via `python <caminho>`.
* **Benefício Esperado:** Eliminação de erros de escape de shell, integridade de strings acentuadas e rastreabilidade total dos scripts utilizados.
* **Custo de Implementação:** Trivial (já validado com sucesso durante a auditoria da PR #16).
* **Risco de Complexidade:** Zero.

---

### Candidato 4 (Severidade Baixa): Instalação da GitHub CLI (`gh`) no Host Operacional
* **Problema Observado:** Criação de múltiplos scripts ad-hoc com chamadas manuais `urllib.request` para interagir com a API REST do GitHub (criação de PR, auditoria de arquivos, monitoramento de CI e merge).
* **Evidência Concreta:** Scripts `create_and_monitor_pr.py`, `monitor_ci.py`, `check_pr_details.py` e `execute_merge.py` gerados no scratch.
* **Causa Raiz:** A ferramenta de linha de comando oficial `gh` não se encontra instalada no sistema operacional.
* **Melhoria Recomendada:** Sugerir ao mantenedor a instalação opcional da GitHub CLI (`winget install GitHub.cli`), permitindo uso direto de `gh pr create`, `gh pr checks` e `gh pr merge`.
* **Benefício Esperado:** Redução de código boilerplate de API nos agentes e maior transparência nos comandos de integração.
* **Custo de Implementação:** Baixo (dependência externa do host).
* **Risco de Complexidade:** Muito baixo.

---

## 6. Próximos Passos e Decisão Humana

Nenhuma das melhorias propostas foi implementada nesta etapa. Não foram criados tickets, specs, commits ou modificações destrutivas na working tree.

A lista de candidatos acima é submetida para avaliação, refinamento e aprovação humana antes de qualquer formalização no repositório.
