# Retrospectiva: Qualidade de Coleta e Rastreabilidade Editorial

**Data:** 27 de Outubro de 2026  
**Status do Projeto:** 95/95 testes automatizados aprovados (0.24s) | CI no GitHub Actions 100% verde  
**Escopo Analisado:** Resolução das falhas de amostragem e ausência de links no relatório diário (PRs #2 e #3), cobrindo o coletor Playwright do X/Twitter, a engenharia de prompts, a estruturação de payloads XML e a renderização HTML Bento Grid.

---

## 1. O que Funcionou Bem

1. **Desacoplamento Arquitetural como Fator de Isolamento:** A modernização prévia (Spec 0001–0003) permitiu isolar o problema rapidamente. O transporte de dados em memória (`DailyIngestionBatch`) manteve 100% de integridade; a falha estava estritamente concentrada no coletor da fonte e no prompt de síntese, sem propagação para o orquestrador ou canais de entrega.
2. **Diagnóstico Forense Baseado em Evidências:** A análise comparativa entre as edições de 26/10 e 27/10 utilizou logs reais (`logs/execucao.log`), snapshots em disco e diffs do Git, permitindo diferenciar com precisão um defeito de software (parada prematura do coletor) de uma ausência legítima de conteúdo e de uma lacuna de especificação no prompt.
3. **Ciclo de Entrega Seguro e Incremental:** Ambas as correções foram desenvolvidas em branches pontuais (`fix/twitter-collector-scroll` e `feature/twitter-link-traceability`), validadas por agentes de revisão especializados (Standards e Spec Reviewers) e testadas no GitHub Actions antes de qualquer integração.
4. **Modularização de Payloads (`montar_payload_tweets_xml`):** A extração da montagem do XML de entrada para uma função pura tornou a interface entre Python e LLM determinística, facilitando testes unitários sem chamadas de rede ou consumo de tokens.

---

## 2. O que Falhou e Por que os Testes Anteriores Não Detectaram

### Falha A: Interrupção Prematura do Coletor do X/Twitter
* **O que falhou:** O scraper assumia uma premissa ingênua de ordenação estritamente cronológica. Quando um tweet antigo aparecia fora de ordem (ex: tweet fixado no topo ou retweet de 60h atrás), a condição `tweet_dt < limite_tempo` ativava imediatamente a flag de parada, interrompendo a rolagem na 1ª página e derrubando a amostragem de 61 para 17 tweets.
* **Ponto cego dos testes:** Historicamente, o coletor era considerado "código dependente de infraestrutura externa / browser real" e não possuía uma suíte unitária hermética. A ausência de simulação do DOM virtual do Playwright mascarou o defeito em cenários não-lineares de feed.

### Falha B: Omissão de Links Permanentes no Relatório Gerado
* **O que falhou:** O prompt instruía a inclusão de links apenas para artigos externos (`external_links`), GitHub ou ArXiv. Quando a amostra encolheu para 17 tweets (dos quais 16 não tinham links externos), o modelo LLM seguiu a instrução à risca e omitiu o link do post original (`<url>`) em 10 de 11 notícias.
* **Ponto cego dos testes:** Os testes do sintetizador utilizavam mocks que retornavam strings pré-fabricadas com links em Markdown fictícios, validando apenas o fluxo do orquestrador e a gravação de arquivos, sem verificar a montagem do payload XML de entrada nem as regras de restrição do prompt.

---

## 3. Aprendizados Novos (Não Registrados na Retro 0001)

### Lição 1: Feeds de Redes Sociais não são Séries Temporais Monótonas
* **Contexto:** Timelines modernas de redes sociais (mesmo abas "Seguindo") injetam retweets, posts fixados e anúncios fora da ordem cronológica estrita de publicação.
* **Aprendizado:** Critérios de parada temporal de scraping jamais devem ser binários na primeira ocorrência fora da janela. Devem adotar limites de tolerância consecutiva (`MAX_CONSECUTIVE_OLD_TWEETS`), com reset do contador a cada item recente válido encontrado.

### Lição 2: Riscos de Complacência por Alta Amostragem
* **Contexto:** Com 61 tweets (26/10), o LLM deduzia organicamente a inclusão de `([Post](url))` devido à alta densidade de links externos no contexto. Quando o volume caiu para 17 tweets (27/10), o comportamento mudou e a lacuna de instrução no prompt veio à tona.
* **Aprendizado:** Comportamentos desejados do LLM que dependem de indução contextual falham sob baixa amostragem. Devem ser tornados mandatórios de forma imperativa nas regras de pontuação e sintaxe do prompt (`([Post](url))`).

### Lição 3: Hermetismo Completo para Automações Playwright via Mocks de DOM
* **Contexto:** Havia a crença de que testar coletores de browser exigiria executar instâncias reais do Chromium.
* **Aprendizado:** É perfeitamente viável construir mocks herméticos de localizadores e elementos do Playwright (`make_mock_article`) para cobrir regras de scroll, timeouts, janelas temporais e seletores multilíngues em microssegundos (14 testes em 0.05s).

---

## 4. Evidências: Testes Automatizados vs. Execução Real em Produção

| Dimensão | Evidência em Testes Automatizados | Evidência em Execução Real (27/10 - 09:03) |
| :--- | :--- | :--- |
| **Coleta do X** | 14 testes em `test_twitter_collector.py` simulando tweets antigos intercalados, feeds esgotados e atrasos assíncronos. | O coletor executou em produção e extraiu **80 tweets** (contra 17 da execução matinal defeituosa). |
| **Payload XML** | 5 testes em `test_summarizer.py` validando integridade de `<url>` e `<external_links>`. | O payload completo de 80 tweets foi processado pelo `gpt-6-luna` em 48 segundos. |
| **Rastreabilidade** | Testes validando presença de `([Post](url))` e atributos `target="_blank" rel="noopener noreferrer"`. | **100% dos bullets** no relatório final trouxeram links válidos para posts e fontes originais. |
| **Diversidade Editorial** | Testes de montagem e integridade estrutural. | As seções *Capacitação* (2 itens) e *Economia* (4 itens) foram totalmente restabelecidas. |
| **Entrega** | Mocks de canal SMTP e despachante. | E-mail real enviado e entregue via Gmail SMTP para o destinatário configurado em 146.0s. |

---

## 5. Melhorias Preventivas Justificadas

1. **Abertura Segura de Links no Layout Bento Grid:** A inclusão de `target="_blank"` e `rel="noopener noreferrer"` no renderizador HTML protege o leitor contra navegação indesejada na mesma aba e mitiga riscos de *reverse tabnabbing*.
2. **Blindagem contra Alucinação de URLs:** A regra explícita no prompt (`NUNCA invente URLs, não use placeholders genéricos`) assegura que a IA omita o link caso o campo esteja vazio, em vez de gerar URLs quebradas.

---

## 6. Riscos que Ainda Precisam de Validação em Produção

* **Mudança de Seletores no DOM do X:** A classe `article[data-testid='tweet']` e a aba `Seguindo / Following` permanecem sujeitas a alterações sem aviso prévio pela plataforma.
* **Comportamento sob Volume Extremo:** Em dias de notícias extraordinárias com grande volume no feed, o limite de 25 scrolls e a tolerância de 8 antigos devem ser monitorados para garantir que a coleta termine confortavelmente antes do timeout global de 300 segundos.

---

## 7. Próximas Ações Prioritárias (Máximo de 3)

1. **Métrica de Volume de Coleta no Toast Nativo:** Exibir no alerta do Windows o número de itens coletados (ex: *"Coletados 80 tweets, 6 repositórios e 3 papers"*), permitindo ao usuário detectar anomalias de amostragem no próprio alerta diário. *(Custo: Trivial | Benefício: Alto)*
2. **Validação Sintática Pós-Síntese (Regex de Links):** Adicionar verificação leve no pós-processamento do Markdown para emitir log de alerta caso mais de 50% dos bullets de notícias não contenham links clicáveis, antecipando eventuais desvios de instrução do modelo de IA. *(Custo: Baixo | Benefício: Médio)*
3. **Monitoramento do Tempo de Hidratação do Feed:** Registrar periodicamente em log o tempo médio gasto por scroll para ajustar `scroll_delay` caso a conexão local sofra lentidão transitória. *(Custo: Baixo | Benefício: Médio)*
