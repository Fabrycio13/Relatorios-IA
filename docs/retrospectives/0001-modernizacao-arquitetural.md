# Retrospectiva: Ciclo de Modernização Arquitetural

**Data:** 27 de Outubro de 2026  
**Status do Projeto:** 64/64 testes automatizados aprovados (0.12s)  
**Escopo Analisado:** Modernização arquitetural das 3 frentes (`DailyIngestionBatch`, `Protocolo de Ingestão`, `DeliveryChannel`), cobrindo os Tickets 01 a 09 e as especificações `0001`, `0002` e `0003`.

---

## 1. Análise Retrospectiva

### 1.1 O que foi planejado versus o que foi implementado
* **Fase 1 (`DailyIngestionBatch`):**
  * *Planejado:* Eliminar a dependência de arquivos JSON intermediários no fluxo em memória, mantendo persistência em disco apenas para recuperação e debug; unificar dados em dataclasses tipadas.
  * *Implementado:* Modelo `DailyIngestionBatch` criado com tipagem forte; `ai_summarizer.py` adaptado para consumir o lote em memória sem leitura de disco durante o pipeline principal; snapshot atômico em disco preservado com inclusão de `snapshot_metadata.json` para auditoria temporal e timestamps individuais por fonte.
* **Fase 2 (`Protocolo de Ingestão`):**
  * *Planejado:* Desacoplar coletores do `main.py` através de uma interface comum, facilitando a adição de novas fontes sem alterar o orquestrador; manter tolerância a falhas parciais.
  * *Implementado:* Protocolo `IngestionSource` (`name`, `target_field`, `collect()`); adaptadores `TwitterSource`, `GitHubSource` e `HuggingFaceSource`; orquestrador `IngestionPipeline`; validação restrita de campos via `ALLOWED_BATCH_FIELDS` e verificação declarativa via `batch.is_empty()` no `main.py`.
* **Fase 3 (`DeliveryChannel` e Modo Preview):**
  * *Planejado:* Separar a renderização do Bento Grid HTML do transporte SMTP; adicionar modo `--preview` local sem rede; facilitar testes unitários e de integração.
  * *Implementado:* Protocolo `DeliveryChannel`; adaptadores `EmailDeliveryChannel` (Gmail SMTP SSL 465 com fallback de texto puro) e `FilePreviewDeliveryChannel` (`reports/preview.html` atômico + abertura no navegador); orquestrador `despachar_relatorio`; flag `--preview` com garantia estrita de zero conexões SMTP e zero impacto na trava diária.

### 1.2 Decisões arquiteturais acertadas
1. **Protocolos Estruturais (`typing.Protocol`) em vez de Herança Rígida:** O uso de `@runtime_checkable` para `IngestionSource` e `DeliveryChannel` permitiu contratos estritos e testes com mocks puros em memória (`MockDeliveryChannel`), sem acoplar a hierarquias de classes abstratas (`abc.ABC`).
2. **Preservação dos Snapshots como Fallback Transparente:** Manter a persistência atômica em JSON (`save_snapshot` e `load_snapshot`) garantiu que comandos como `python main.py --step summarize` continuassem utilizáveis de forma isolada por desenvolvedores sem disparar scraping ou chamadas externas.
3. **Desacoplamento entre Renderização e Transporte:** Isolar `render_bento_email` de `EmailDeliveryChannel` assegurou que o arquivo visualizado no navegador com `--preview` seja 100% idêntico ao e-mail enviado ao destinatário final.
4. **Isolamento da Trava Diária no Modo Preview:** Garantir que `--preview` nunca acesse nem grave `data/ultimo_envio.txt` permitiu depuração e testes visuais em qualquer horário do dia sem invalidar o agendamento matinal.

### 1.3 Problemas e regressões surgidos durante o desenvolvimento
1. **Poluição de Estado em Testes de Integração (Fase 1/2):**
   * *Ocorrência:* Durante a execução de testes em `test_main_integration.py`, a chamada direta a `main.main()` executava `registrar_envio_sucesso(hoje_str)`, sobrescrevendo acidentalmente a trava de produção `data/ultimo_envio.txt` com a data atual.
   * *Mitigação:* Reversão manual imediata do arquivo para a data correta (`2026-10-26`) e aplicação obrigatória de `@patch("main.registrar_envio_sucesso")` em todos os testes do fluxo orquestrador.
2. **Ausência de Código de Erro em Coleta Exclusiva Falha (Fase 2):**
   * *Ocorrência:* A spec exigia que `python main.py --step collect-github` gerasse exit code 1 caso a fonte falhasse, mas a pipeline retornava lote vazio sem abortar o processo.
   * *Mitigação:* Adicionada validação no `main.py` para interromper com `sys.exit(1)` caso um passo exclusivo retorne lote vazio.

### 1.4 Problemas identificados somente no Code Review
1. **Contaminação Temporal de Snapshots em Coletas Isoladas:**
   * *Ocorrência:* Ao rodar `--step collect-github`, o pipeline carregava o snapshot anterior com dados de ontem do Twitter e Hugging Face, mesclava no lote e regravava com `collected_at = datetime.now()`, falsificando a estampa de tempo de dados antigos.
   * *Mitigação:* Implementado salvamento parcial atômico por fonte (`DailyIngestionBatch.save_snapshot(source=...)`) e remoção do pré-carregamento em passos isolados.
2. **Introspecção de Classe no Dispatcher:**
   * *Ocorrência:* `dispatcher.py` inspecionava `"Preview" in channel.__class__.__name__` para formatar mensagens de log.
   * *Mitigação:* Introduzido atributo explícito `name: str` nos canais.
3. **Falta de Hermeticidade em Testes de E-mail:**
   * *Ocorrência:* `test_email_delivery_channel_success` mockava o SMTP mas dependia da leitura de `config.get_email_credentials()` do `.env` local.
   * *Mitigação:* Injetado mock explícito de credenciais no teste.

### 1.5 Simplicidade, modularidade, testabilidade e sustentabilidade
* **Modularidade:** A suíte de testes expandiu de 20 para 64 testes automatizados em 0.12s.
* **Testabilidade:** Anteriormente, validar o envio exigia mockar sockets de rede ou disparar e-mails reais. Hoje, canais em memória (`MockDeliveryChannel`) validam o ciclo completo sem dependências externas.
* **Sustentabilidade:** Zero novas dependências de terceiros adicionadas ao `requirements.txt` (uso estrito da biblioteca padrão do Python).

### 1.6 Avaliação de overengineering e duplicações
* O projeto resistiu ativamente à tentação de criar registries dinâmicos, fábricas reflexivas ou contêineres genéricos heterogêneos. O modelo de dados mantém campos explícitos e tipados (`tweets`, `repos`, `papers`).
* Duplicações estruturais em `ai_summarizer.py` (`_anexar_secao_github` e `_anexar_secao_papers`) foram mantidas deliberadamente, pois unificá-las criaria indireção com parâmetros excessivos para uma economia marginal de código.

---

## 2. Avaliação dos Problemas Remanescentes

| Apontamento | Classificação | Gravidade | Impacto | Custo de Correção | Recomendação |
| :--- | :--- | :---: | :--- | :---: | :--- |
| **Hardcoded Paths em `executar.bat` e `executar_silencioso.vbs`** | Dívida técnica / Risco operacional | **Média** | Caminhos absolutos fixos (`D:\Projetos\...`, `Python313\python.exe`). Quebra se o projeto mudar de drive ou versão do Python. | Baixo (15 min) | **Corrigir no próximo ciclo.** Tornar os caminhos relativos ao diretório do script (`%~dp0` no `.bat` e `ScriptFullName` no `.vbs`). |
| **Tratamento de Aspas em `notifier.py`** | Bug real potencial | **Média** | Mensagens de exceção contendo aspas simples (`'`) quebram a execução do comando PowerShell inline silenciosamente. | Baixo (10 min) | **Corrigir no próximo ciclo.** Escapar aspas simples (`mensagem.replace("'", "''")`) antes da interpolação. |
| **Condicionais em `models.py:save_snapshot`** | Dívida técnica menor | **Baixa** | Blocos `if/elif` mapeiam as 3 fontes conhecidas. Funciona perfeitamente e é testado, mas poderia usar um dicionário mapeador. | Baixo (10 min) | **Melhoria opcional.** Manter como está ou refatorar se surgir uma 4ª fonte. |
| **Interpolação de Classe no log do Dispatcher** | Melhoria opcional | **Baixa** | Uso de `channel.__class__.__name__` no log informativo. | Trivial (2 min) | **Decisão intencional que deve ser mantida.** Não afeta o fluxo nem a lógica de execução. |
| **Divergências Documentadas com as Specs** | Decisão intencional | **Baixa** | Canais coesos em `base.py`, suporte a `plain_text` e assunto de e-mail com emojis/hora. | Nulo | **Manter.** Todas as decisões estão justificadas em `ARCHITECTURE.md §5`. |
| **Limitações do Teste TCP com `8.8.8.8:53`** | Risco operacional residual | **Baixa** | Testa conectividade L3/L4. Redes corporativas com bloqueio estrito de DNS externo poderiam falhar no teste primário. | Nulo | **Manter.** O método já possui fallback automático via HTTP simples (`google.com`). |

---

## 3. Aprendizado Contínuo

### Lição 1: Isolamento de Efeitos Colaterais em Testes de Orquestração
* **Situação:** Chamadas a `main.main()` em testes unitários persistiram a data atual na trava de idempotência de produção (`ultimo_envio.txt`).
* **Causa-raiz:** O teste cobria o fluxo ponta a ponta sem isolar o arquivo de estado em disco com mock ou diretório temporário.
* **Impacto:** Risco de cancelamento silencioso do envio real da automação agendada matinal.
* **Como evitar:** Testes de integração devem obrigatoriamente mockar ou isolar os arquivos de estado persistente do sistema operacional.
* **Orientação para Agentes:** **Regra Geral.** Agentes devem verificar e proteger qualquer sink de persistência global ao executar testes que chamam pontos de entrada de orquestração.

### Lição 2: Especificação de Comportamento Parcial de Persistência
* **Situação:** Ao executar a coleta de uma única fonte, o pipeline mesclava dados anteriores de outras fontes e atualizava a estampa de tempo global de forma incorreta.
* **Causa-raiz:** As especificações focavam no fluxo macro consolidado (`all`) e deixaram implícito o comportamento de persistência para passos atômicos.
* **Impacto:** Dados antigos recebiam falsamente o timestamp do dia atual.
* **Como evitar:** Especificações devem definir explicitamente a política de persistência e granularidade de timestamps para comandos parciais versus comandos completos.
* **Orientação para Agentes:** **Regra Geral.** Ao criar modelos com persistência em disco e suporte a comandos CLI parciais, especificar a política de atualização incremental por partição/fonte.

### Lição 3: Hermeticidade Absoluta em Testes de Unidade
* **Situação:** O teste de envio de e-mail mockava o servidor SMTP mas dependia da leitura de credenciais reais no `.env`.
* **Causa-raiz:** Suposição de que o ambiente de execução local sempre terá o arquivo de configuração preenchido.
* **Impacto:** Testes falhariam imediatamente em um ambiente de CI/CD ou máquina limpa.
* **Como evitar:** Testes unitários devem fornecer seus próprios dados sintéticos via mocks em todas as chamadas de configuração externa.
* **Orientação para Agentes:** **Regra Geral.** Nunca permitir que testes unitários dependam de valores de variáveis de ambiente do host para passar.

---

## 4. Rastreabilidade

| Especificação | Ticket de Origem | Arquivos Implementados | Testes Verificadores | Status no Code Review |
| :--- | :--- | :--- | :--- | :---: |
| **Spec 0001** (`DailyIngestionBatch`) | Tickets 01, 02, 03 | `src/core/models.py`<br>`src/processors/ai_summarizer.py`<br>`main.py` | `test_models.py`<br>`test_summarizer.py`<br>`test_main_integration.py` | ✅ Aprovado |
| **Spec 0002** (`Protocolo de Ingestão`) | Tickets 04, 05, 06 | `src/collectors/base.py`<br>`src/collectors/pipeline.py`<br>`main.py` | `test_collectors_protocol.py`<br>`test_ingestion_pipeline.py`<br>`test_main_integration.py` | ✅ Aprovado |
| **Spec 0003** (`DeliveryChannel`) | Tickets 07, 08, 09 | `src/delivery/base.py`<br>`src/delivery/dispatcher.py`<br>`src/delivery/sender.py`<br>`main.py` | `test_delivery_channels.py`<br>`test_delivery_dispatcher.py`<br>`test_delivery_integration.py` | ✅ Aprovado |

---

## 5. Recomendações e Propostas para um Futuro `AGENTS.md`

### 5.1 Lista Priorizada de Melhorias Pendentes (Backlog Técnico)
1. **[Prioridade Alta / Risco Operacional]** Parametrizar caminhos relativos em `scripts/executar_silencioso.vbs` e `executar.bat` para garantir portabilidade entre diretórios e versões do Python.
2. **[Prioridade Média / Robustez]** Adicionar escape de aspas simples em `src/core/notifier.py` para evitar quebras silenciosas no PowerShell diante de mensagens de erro formatadas.
3. **[Prioridade Baixa / Manutenibilidade]** Substituir blocos `if/elif` em `save_snapshot` por um mapa declarativo `_SOURCE_SNAPSHOT_MAP`.

### 5.2 Propostas de Diretrizes para o Futuro `AGENTS.md`
1. **Regra de Idempotência e Mocks:** *Ao escrever ou rodar testes em repositórios com automações agendadas, garanta que arquivos de trava (`ultimo_envio.txt`) e chamadas de envio (`smtp`, `api`) estejam estritamente mockados. Nunca permita que execuções de teste alterem o estado de produção da máquina.*
2. **Princípio do Menor Delta:** *Implemente a menor alteração que satisfaça plenamente o ticket. Evite frameworks, factories reflexivas ou camadas de indireção desnecessárias.*
3. **Isolamento de Snapshots:** *Comandos CLI que executam partes isoladas do pipeline devem afetar apenas a partição de dados correspondente, sem mesclar dados prévios nem atualizar timestamps de fontes não executadas.*
