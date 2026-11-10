# Diário de Engenharia (IA & Coding Agents)

Automação de inteligência técnica para engenheiros de software, curando diariamente discussões em profundidade, repositórios open-source e artigos científicos sobre Inteligência Artificial aplicada e coding agents.

## Automação e Entrega

**Diário de Engenharia**:
A newsletter técnica matinal automatizada que consolida o estado da arte diário em IA e coding agents para o time de engenharia da Usabit.
_Avoid_: Clipping de notícias, bot de resumo, feed RSS

**Radar VIP**:
A curadoria direcionada sobre perfis de engenheiros e pesquisadores de alta autoridade técnica no X.
_Avoid_: Feed aleatório, monitoramento de hashtags, busca aberta

**Ciclo D-1**:
A janela móvel retrospectiva das últimas 24 a 48 horas analisada para garantir que nenhuma discussão técnica relevante do dia anterior seja omitida.
_Avoid_: Tempo real, streaming contínuo

**Trava Antirrepetição**:
O mecanismo de estado local que garante idempotência diária, impedindo que múltiplos boots ou reinicializações disparem relatórios duplicados na mesma data.
_Avoid_: Cron cego, envio sem idempotência, trava de processo

**Bento Grid Modular**:
O padrão visual do e-mail estruturado em cartões independentes e blocos de alto contraste inspirados na interface dos produtos modernos da Apple.
_Avoid_: Layout tabular cinza, e-mail em texto puro, dark mode forçado

**CDN Raw Serving**:
A estratégia de entrega estática de imagens servidas diretamente pela URL pública do repositório no GitHub sem anexação direta na mensagem.
_Avoid_: Anexo CID, imagem embutida em base64, hospedagem paga externa

**Takeaway de Engenharia**:
A síntese analítica conclusiva ao final do relatório que traduz os acontecimentos do dia em lições arquiteturais e de implementação prática para o time.
_Avoid_: Conclusão genérica, resumo executivo superficial

## Arquitetura e Pipeline de Engenharia

**DailyIngestionBatch (Lote de Ingestão Diária)**:
A entidade central fortemente tipada que agrega em memória os dados coletados de todas as fontes (X, GitHub, Papers) antes da etapa de síntese por IA.
_Avoid_: Dicionário solto, JSON não tipado, payload dinâmico, variáveis globais

**Snapshot Preventivo**:
A gravação atômica intermediária em disco (`data/*.json`) do lote coletado acompanhado de metadados temporais, garantindo recuperação em caso de falha da LLM sem necessidade de nova raspagem na rede.
_Avoid_: Cache permanente, log descartável, snapshot sem estampa temporal

**IngestionSource (Protocolo de Ingestão)**:
O protocolo estrutural (`typing.Protocol`) que padroniza como qualquer fonte externa é plugada e coletada pelo pipeline com isolamento de falhas.
_Avoid_: Herança concreta rígida, acoplamento direto de coletores ao pipeline

**DeliveryChannel (Canal de Entrega)**:
O adaptador de saída que desacopla a geração do relatório do seu meio de apresentação (e-mail SMTP, preview local no navegador, etc.).
_Avoid_: Envio embutido no renderizador, acoplamento com provedores específicos

**Hierarquia de Banners (3 Tiers)**:
O sistema determinístico de seleção visual que prioriza datas comemorativas fixas/móveis (Tier 1), alterna o catálogo geral por exaustão sem repetição (Tier 2) e garante imagem neutra de fallback (Tier 3).
_Avoid_: Escolha randômica cega, repetição de artes em dias seguidos, ausência de fallback

**TaskLock (Trava de SO)**:
O mecanismo de trava de exclusão mútua em nível de sistema operacional (`msvcrt` no Windows / `fcntl` no Linux) que garante que colisões entre gatilhos de boot e agendamento encerrem de forma limpa (`sys.exit(0)`).
_Avoid_: Flag booleana em memória, verificação ingênua de arquivo, polling de processos

**Fronteira de Blindagem (Safe by Default)**:
A barreira determinística no renderizador que trata todo Markdown e dados de fontes externas como não confiáveis, aplicando escape contextual e validação de URLs antes de qualquer injeção no HTML.
_Avoid_: Confiança cega em saídas de LLM, sanitização permissiva com regex, bypass de escape

## Domínio de Inteligência Artificial e Agentes

**Coding Agent**:
Um sistema autônomo baseado em modelo de linguagem com capacidade de inspecionar repositórios, planejar tarefas em árvore, editar código em múltiplos arquivos e verificar a execução via terminal.
_Avoid_: Chatbot de código, autocompletar inline, Copilot simples

**Model Context Protocol (MCP)**:
O protocolo aberto de comunicação cliente-servidor que padroniza o acesso seguro de modelos de IA a ferramentas locais, dados contextuais e APIs.
_Avoid_: Plugin proprietário, script customizado de integração

**Harness Engineering**:
O ecossistema determinístico de suporte e isolamento (mocks, sandboxes, testes e regras estritas) construído ao redor de agentes de IA para garantir previsibilidade e contenção.
_Avoid_: Engenharia de prompt livre, tentativa e erro manual

**Eval**:
O conjunto padronizado e quantitativo de testes que mede acurácia, fidelidade conceitual, taxa de alucinação e consumo de tokens de modelos e agentes sob condições controladas.
_Avoid_: Teste empírico informal, impressão subjetiva

**Janela de Contexto**:
O limite físico finito de tokens que um modelo consegue carregar simultaneamente na memória de atenção de uma única requisição.
_Avoid_: Memória infinita, memória de longo prazo nativa

**Tokens de Raciocínio**:
A cadeia interna de reflexão gerada pelo modelo antes de produzir a resposta final orientada ao usuário.
_Avoid_: Resposta direta não reflexiva

**Pesos Abertos**:
Modelos de IA cujos parâmetros matriciais treinados são disponibilizados publicamente para execução e inferência local independente.
_Avoid_: Modelo fechado, API proprietária
