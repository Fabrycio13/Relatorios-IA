# 📖 Glossário Oficial: Diário de Engenharia (IA & Coding Agents)

Este glossário define a linguagem ubíqua do projeto, cobrindo o **domínio da engenharia de automação**, os **conceitos do ecossistema de Inteligência Artificial** monitorados diariamente e o **mapa dos componentes do repositório**.

---

## 1. ⚙️ Domínio da Engenharia e Automação

**Diário de Engenharia**:  
A newsletter diária técnica e automatizada com curadoria sobre IA, coding agents e repositórios open-source enviada para a Usabit.  
_Evitar_: Spam diário, bot de notícias, clipping.

**Ciclo D-1**:  
Janela de tempo retrospectiva (últimas 24 a 48 horas) utilizada pelos coletores para garantir que nenhuma notícia ou discussão relevante do dia anterior seja perdida.  
_Evitar_: Tempo real, streaming contínuo.

**Radar VIP**:  
Módulo de coleta direcionada que inspeciona ativamente perfis de referência técnica no X (Matt Pocock, Andrej Karpathy, Swyx, Jason Liu, Chip Huyen e Santiago Valdarrama).  
_Evitar_: Feed aleatório, busca aberta por hashtags.

**Trava Antirrepetição (Daily Lock)**:  
Mecanismo de estado (`data/ultimo_envio.txt`) que registra a data da última entrega bem-sucedida, impedindo reenvios duplicados caso o computador seja ligado ou reiniciado ao longo do dia.  
_Evitar_: Cron cego, envio sem idempotência.

**Bento Grid Modular (Light Premium)**:  
Padrão de design de e-mail inspirado nos dashboards modernos da Apple, baseado em cartões brancos independentes, bordas sutis, cantos arredondados e tipografia de alto contraste para leitura rápida em celulares e computadores.  
_Evitar_: Texto plano, tabelas antigas cinzas, dark mode forçado.

**CDN Raw Serving**:  
Estratégia de entrega de imagens em que os banners estáticos são servidos via URL pública direta do GitHub (`raw.githubusercontent.com`), eliminando completamente as pílulas de anexo no Gmail e deixando o e-mail ultra leve (~15 KB).  
_Evitar_: Anexo MIME (CID), base64 em linha.

**Interpolação Bicúbica MSO**:  
Diretiva de renderização (`-ms-interpolation-mode: bicubic`) e contêineres condicionais que forçam o Microsoft Word (motor do Outlook Desktop) a renderizar imagens suaves e na largura correta de 680px.  
_Evitar_: Layout estourado, imagens pixeladas no Outlook.

**Pipeline Orquestrado**:  
Execução sequencial de 4 passos com tratamento de erros isolado: Coleta X ➔ Coleta GitHub ➔ Síntese IA ➔ Envio SMTP.

---

## 2. 🧠 Conceitos Técnicos do Ecossistema de IA

**Coding Agent (Agente de Programação)**:  
Sistema autônomo baseado em LLM capaz de inspecionar diretórios, planejar tarefas, executar testes no terminal e editar código-fonte de múltiplos arquivos com intervenção humana mínima.  
_Evitar_: Chatbot simples, autocompletar de código, Copilot inline.

**Model Context Protocol (MCP)**:  
Protocolo aberto e padronizado (criado pela Anthropic) que permite conectar modelos de IA a servidores locais de dados, ferramentas e APIs através de interfaces tipadas seguras.  
_Evitar_: Plugin proprietário, script customizado de scraping.

**Harness Engineering**:  
Disciplina de engenharia focada em construir o ecossistema externo de suporte ao redor da IA (mocks, ambiente de execução hermético, evals e validação determinística de resultados) para garantir que agentes operem com segurança.  
_Evitar_: Engenharia de prompt solta, tentativa e erro manual.

**Evals (Avaliações de Modelos/Agentes)**:  
Conjunto de testes automatizados e quantitativos que medem a acurácia, taxa de alucinação, consumo de tokens e capacidade de resolução de problemas de um modelo ou agente.  
_Evitar_: "Sentir que o modelo é bom", testes manuais sem métricas.

**RAG (Retrieval-Augmented Generation)**:  
Arquitetura que consulta bases de dados vetoriais ou buscas contextuais para injetar documentos relevantes no prompt antes da geração de resposta pela LLM.  
_Evitar_: Fine-tuning desnecessário, alucinação pura.

**Janela de Contexto (Context Window)**:  
Limite máximo de tokens que um modelo consegue reter na memória de trabalho em uma única requisição (incluindo histórico, prompts de sistema e saída gerada).  
_Evitar_: Memória infinita, memória de longo prazo nativa.

**Tokens de Raciocínio (Reasoning Tokens)**:  
Tokens gerados internamente pelo modelo durante o processo de reflexão ("Chain-of-Thought") antes de formular a resposta visível ao usuário.  
_Evitar_: Resposta instantânea não reflexiva.

**Modelos Open-Weights**:  
Modelos de inteligência artificial cujos parâmetros matemáticos (pesos) são distribuídos publicamente para download, permitindo execução local ou self-hosted (ex: Llama, DeepSeek, Qwen).  
_Evitar_: Modelo fechado / API-only.

---

## 3. 📂 Dicionário de Componentes e Estrutura de Arquivos

| Arquivo / Pasta | Responsabilidade Única |
| :--- | :--- |
| **`main.py`** | Ponto de entrada CLI unificado com flags (`--force`, `--step`, `--status`). |
| **`executar.bat`** | Script de disparo matinal chamado diariamente às 08:00 pelo Agendador do Windows. |
| **`src/core/config.py`** | Central de configuração: lê `.env`, valida credenciais e expõe caminhos absolutos. |
| **`src/core/logger.py`** | Gerenciador de logs unificado com rotação de arquivos (`logs/execucao.log`) e saída no console. |
| **`src/core/models.py`** | Modelos tipados (`Tweet`, `GitHubRepo`) com sanitização ativa contra prompt injection. |
| **`src/core/retry.py`** | Mecanismo de resiliência com retries automáticos e backoff exponencial com jitter para APIs externas. |
| **`src/collectors/twitter.py`** | Robô Playwright headless que coleta tweets do feed e dos perfis do Radar VIP. |
| **`src/collectors/github.py`** | Coletor HTTP via API do GitHub que filtra os top repositórios recentes de IA. |
| **`src/processors/ai_summarizer.py`** | Módulo de síntese técnica: envia dados ao `gpt-6-luna`, traduz e gera o relatório `.md`. |
| **`src/delivery/renderer.py`** | Transforma o Markdown bruto no HTML Bento Grid responsivo para mobile e desktop. |
| **`src/delivery/sender.py`** | Conecta ao Gmail via SMTP SSL (porta 465) e envia o e-mail em formato limpo. |
| **`reports/`** | Pasta que armazena o histórico permanente dos relatórios (`Resumo_IA_YYYY-MM-DD.md`). |
| **`data/`** | Pasta de trabalho temporária para JSONs de coleta bruta e trava de estado diário. |
| **`logs/`** | Pasta onde são gravados e rotacionados os históricos de execução (`execucao.log`). |
| **`assets/`** | Imagens e banners públicos servidos diretamente para o e-mail via CDN. |
| **`scripts/`** | Scripts manuais e auxiliares (como `login_x.py` para renovação interativa de sessão). |

---

## 4. 🔐 Dicionário de Credenciais (`.env`)

| Variável | Finalidade | Onde Obter |
| :--- | :--- | :--- |
| **`OPENAI_API_KEY`** | Autentica as chamadas ao modelo `gpt-6-luna` para sintetizar e traduzir o relatório. | Painel da OpenAI (`platform.openai.com`). |
| **`TWITTER_AUTH_TOKEN`** | Cookie de sessão primário para autenticar no X sem precisar de API paga. | Inspecionar cookies em `x.com` (`auth_token`). |
| **`TWITTER_CT0`** | Token anti-CSRF exigido pelo X nas requisições autenticadas. | Inspecionar cookies em `x.com` (`ct0`). |
| **`GMAIL_USER`** | Conta Google utilizada como remetente oficial do e-mail. | Seu e-mail Gmail (`bermudes.fbc@gmail.com`). |
| **`GMAIL_APP_PASSWORD`** | Senha de aplicativo de 16 dígitos com permissão SMTP exclusiva. | Segurança da Conta Google ➔ Senhas de App. |
| **`GMAIL_TO`** | E-mail de destino corporativo que recebe a edição diária às 08:00. | E-mail corporativo (`fabrycio.bermudes@usabit.com.br`). |
