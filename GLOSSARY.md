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

**Trava Antirrepetição (Trava Diária)**:
O mecanismo de estado local persistente (`data/ultimo_envio.txt`) que garante idempotência diária de calendário (YYYY-MM-DD), impedindo que múltiplos boots ou reinicializações disparem relatórios duplicados na mesma data. Diferencia-se do lock de processo (`TaskLock`/`.pipeline.lock`), pois sobrevive ao encerramento do processo.
_Avoid_: Cron cego, envio sem idempotência, trava de processo efêmera

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

**Snapshot Preventivo e Persistência Atômica**:
A gravação atômica intermediária em disco (`data/*.json`) do lote coletado centralizada em `DailyIngestionBatch.save_snapshot()`. Utiliza arquivos temporários com PID/UUID (`.tmp`), fsync explícito de dados e diretório (POSIX) e substituição atômica via `os.replace()`, prevenindo corrupção por crash e garantindo recuperação sem nova raspagem na rede.
_Avoid_: Cache permanente, escrita direta não atômica, log descartável, snapshot sem estampa temporal

**SourceCollectionResult e Estados de Coleta**:
A estrutura imutável de resultado (`src/core/models.py`) retornada pelos coletores puros em memória, parametrizada pelos estados categóricos de `SourceStatus` (`SUCCESS`, `EMPTY`, `PARTIAL`, `FAILED`, `NOT_RUN`). Encapsula itens, identificadores de operações bem-sucedidas/falhas e mensagens de erro, desacoplando totalmente a coleta de qualquer I/O físico em disco.
_Avoid_: Dicionário solto, tupla desestruturada, escrita direta em disco no coletor, mascaramento de falhas

**Backup Rotativo (.prev) e Quarentena**:
A estratégia de resiliência e tolerância a falhas que rotaciona o arquivo ativo anterior para a extensão `.prev` antes de cada nova gravação. Caso o arquivo ativo seja corrompido ou apresente divergência de hash, ele é isolado em `data/quarantine/` com timestamp e UUID4, e o `.prev` íntegro é validado e promovido a ativo.
_Avoid_: Sobrescrita destrutiva sem backup, exclusão cega de arquivos corrompidos, recuperação sem validação de integridade

**Manifesto de Ingestão v2 e Integridade SHA-256**:
O catálogo de metadados (`data/snapshot_metadata.json`) estruturado com versionamento explícito (`version: 2`), rastreabilidade de execução (`last_attempt` com status `running`/`completed`/`failed`, trigger e PID) e controle estrito por fonte, registrando o hash SHA-256 dos bytes físicos em disco, contagem de registros, status e carimbo temporal com fuso UTC.
_Avoid_: Metadados planos v1 sem versionamento, suposição de integridade sem hash, hash inventado para arquivo ausente

**Legacy Unverified e Fallback de Contingência**:
O regime de compatibilidade que classifica metadados e snapshots históricos pré-Spec 0007 como `quality: 'legacy_unverified'`. Permite hidratação de contingência pelo sintetizador quando uma fonte falha no ciclo atual, desde que os dados estejam dentro da janela de frescor (até 36h) e acompanhados de aviso editorial explícito no relatório.
_Avoid_: Suposição ingênua de integridade de dados históricos, descarte cego de dados legados, omissão de aviso editorial em fallback

**IngestionSource (Protocolo de Ingestão)**:
O protocolo estrutural (`typing.Protocol`) que padroniza como qualquer fonte externa é plugada e coletada pelo pipeline com isolamento de falhas e retorno puro em memória.
_Avoid_: Herança concreta rígida, acoplamento direto de coletores ao pipeline, I/O nos coletores

**DeliveryChannel (Canal de Entrega)**:
O adaptador de saída que desacopla a geração do relatório do seu meio de apresentação (e-mail SMTP, preview local no navegador, etc.).
_Avoid_: Envio embutido no renderizador, acoplamento com provedores específicos

**Hierarquia de Banners (3 Tiers)**:
O sistema determinístico de seleção visual que prioriza datas comemorativas fixas/móveis (Tier 1), alterna o catálogo geral por exaustão sem repetição (Tier 2) e garante imagem neutra de fallback (Tier 3).
_Avoid_: Escolha randômica cega, repetição de artes em dias seguidos, ausência de fallback

**TaskLock (Trava de SO / Lock de Processo)**:
O mecanismo de trava de exclusão mútua em nível de sistema operacional (`msvcrt` no Windows / `fcntl` no Linux) que previne execuções concorrentes do pipeline (`data/.pipeline.lock`) ou colisões durante a gravação/leitura de snapshots (`data/snapshot.lock`). É efêmero e encerra de forma limpa (`sys.exit(0)`), diferindo da trava diária persistente (`ultimo_envio.txt`).
_Avoid_: Flag booleana em memória, verificação ingênua de arquivo, polling de processos, confusão com trava diária

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
