# 🤖 Diário de Engenharia: IA & Coding Agents

Automação ponta a ponta para curadoria, síntese analítica por IA e entrega diária por e-mail dos principais acontecimentos, papers, ferramentas open-source, discussões técnicas do X (Twitter) e repositórios em alta no GitHub.

> 📚 **Documentação Completa:**
> - 📖 **[GLOSSARY.md](GLOSSARY.md)**: Vocabulário ubíquo oficial e conceitos de IA.
> - 🏛️ **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: Arquitetura técnica, mapa de componentes e fluxo de dados.
> - 📋 **[docs/adr/](docs/adr/)**: Registros de Decisões de Arquitetura (ADRs).

---

## 🏛️ Arquitetura do Projeto (Clean Engineering)

O projeto adota uma arquitetura modular com separação estrita de responsabilidades:

```text
├── assets/                     # Banners públicos servidos via CDN (GitHub Raw)
├── data/                       # Caches temporários (dados brutos JSON e travas de envio)
├── logs/                       # Logs de execução com rotação automática (execucao.log)
├── reports/                    # Histórico versionado de relatórios diários Markdown
├── scripts/                    # Scripts utilitários (setup de agendamento, launcher silencioso, login no X)
├── src/
│   ├── collectors/             # Ingestão de dados (github.py, twitter.py, huggingface.py)
│   ├── core/                   # Config (.env), logger rotativo, models (Tweet, Repo, Paper) e retry
│   ├── delivery/               # Renderizador Bento Grid HTML e envio seguro via Gmail SMTP
│   └── processors/             # Síntese analítica (ai_summarizer.py) e prompts isolados (prompts.py)
├── tests/                      # Suíte de testes unitários automatizados (unittest)
├── .env.example                # Modelo de variáveis de ambiente
├── executar.bat                # Script de execução manual com janela de terminal visível
├── main.py                     # Ponto de entrada CLI unificado
└── requirements.txt            # Dependências do projeto
```

---

## 🚀 Como Executar

### 1. Execução Padrão (Agendada ou Manual)
Verifica se o dia já foi enviado; se não foi, roda a pipeline completa e dispara o e-mail:
```powershell
python main.py
```

### 2. Forçar Reenvio no Mesmo Dia
Ignora a trava de segurança diária e gera/envia novamente:
```powershell
python main.py --force
```

### 3. Pré-visualização Local (Preview no Navegador)
Renderiza o relatório em HTML Bento Grid e abre diretamente no navegador padrão sem enviar e-mails e sem alterar a trava diária de envio (`ultimo_envio.txt`):
```powershell
# Execução completa com preview visual no navegador (sem envio SMTP)
python main.py --preview

# Renderização do último relatório gerado em reports/ no navegador
python main.py --step email --preview
```

### 4. Execução de Etapas Isoladas (Debug / Desenvolvimento)
Você pode rodar apenas uma etapa específica sem reexecutar o fluxo inteiro:
```powershell
# Apenas coleta do GitHub Trending
python main.py --step collect-github

# Apenas coleta de tweets no X (Radar VIP + Seguindo)
python main.py --step collect-twitter

# Apenas coleta de Papers em alta no Hugging Face
python main.py --step collect-papers

# Apenas síntese do relatório com IA
python main.py --step summarize

# Apenas renderização e envio do e-mail com o último relatório
python main.py --step email
```

### 5. Diagnóstico de Saúde e Conexões
Verifica em menos de 5 segundos todas as credenciais e conexões ativas (OpenAI, Gmail SMTP, Twitter/X, GitHub, Hugging Face):
```powershell
python main.py --check-auth
```

### 6. Executar a Suíte de Testes Unitários
Executa todos os testes automatizados da pasta `tests/` em modo verboso:
```powershell
python -m unittest discover -s tests -t . -v

# Ou execução seletiva de módulo específico:
python -m unittest tests.test_delivery_integration -v
```

### 7. Consultar Status do Envio
Exibe a data do último envio registrado e qual o último relatório disponível em `reports/`:
```powershell
python main.py --status
```

---

## ⚙️ Configuração (.env)

Copie o arquivo `.env.example` para `.env` e preencha suas credenciais:

```env
OPENAI_API_KEY="sk-proj-..."
TWITTER_AUTH_TOKEN="..."
TWITTER_CT0="..."
GMAIL_USER="seu_email@gmail.com"
GMAIL_APP_PASSWORD="sua_senha_de_app"
GMAIL_TO="destinatario@dominio.com.br"
```

---

## ⏰ Agendador de Tarefas do Windows (Task Scheduler)

A automação matinal é executada pontualmente às **08:00 BRT** ou assim que você ligar o computador (caso tenha sido ligado após as 08:00), 100% em segundo plano sem abrir terminais.

Para gerenciar a tarefa de forma automática, use o script declarativo:

```powershell
# Instalar ou atualizar a tarefa agendada
powershell -ExecutionPolicy Bypass -File .\scripts\setup_task.ps1 -Install

# Verificar status da tarefa, última execução e próximo agendamento
powershell -ExecutionPolicy Bypass -File .\scripts\setup_task.ps1 -Status

# Disparar execução imediata em segundo plano
powershell -ExecutionPolicy Bypass -File .\scripts\setup_task.ps1 -RunNow

# Desinstalar a tarefa agendada
powershell -ExecutionPolicy Bypass -File .\scripts\setup_task.ps1 -Uninstall
```

* **Gatilho Duplo:** Disparo às 08:00 AM se a máquina estiver ligada + disparo imediato no Logon se for ligada após as 08:00 AM.
* **Execução Invisível (Agendador):** O Agendador do Windows executa através de `scripts/executar_silencioso.vbs`, garantindo processamento em segundo plano sem pop-ups de terminal na tela.
* **Execução Manual (`executar.bat`):** O script `executar.bat` permanece disponível para disparos manuais sob demanda, abrindo a janela de console para acompanhamento interativo.
* **Resiliência de Rede:** Se ligar sem internet, aguarda até 60s e retenta a cada 5 minutos até 3 vezes.
* **Logs & Notificações:** Histórico registrado em `logs/execucao.log` e alertas via Toast nativo do Windows.
* **Portabilidade de Diretório:** Os scripts `executar.bat` e `scripts/executar_silencioso.vbs` resolvem seus caminhos relativamente ao local de instalação. Caso a pasta do projeto seja movida para outro diretório ou drive, atualize o caminho registrado no Agendador de Tarefas executando `powershell -ExecutionPolicy Bypass -File .\scripts\setup_task.ps1 -Install`.
