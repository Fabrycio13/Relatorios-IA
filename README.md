# 🧠 Diário de Engenharia: IA & Coding Agents

Automação ponta a ponta para curadoria, síntese analítica por IA e entrega diária por e-mail dos principais acontecimentos, papers, ferramentas open-source, discussões técnicas do X (Twitter) e repositórios em alta no GitHub.

> 📖 **Consulte o [GLOSSARY.md](GLOSSARY.md)** para o dicionário canônico de termos do sistema, conceitos de IA e mapa de componentes.

---

## 🏛️ Arquitetura do Projeto (Clean Engineering)

O projeto adota uma arquitetura modular com separação estrita de responsabilidades:

```text
├── assets/                     # Banners públicos servidos via CDN (GitHub Raw)
├── data/                       # Caches temporários (dados brutos JSON e travas de envio)
├── logs/                       # Logs de execução com rotação automática (execucao.log)
├── reports/                    # Histórico versionado de relatórios diários Markdown
├── scripts/                    # Scripts utilitários (login interativo no X, launcher silencioso)
├── src/
│   ├── collectors/             # Coleta de dados (github.py, twitter.py)
│   ├── core/                   # Configurações centralizadas (.env), logger rotativo e caminhos
│   ├── delivery/               # Renderizador Bento Grid HTML e envio seguro via Gmail SMTP
│   └── processors/             # Síntese analítica e tradução técnica com LLM (OpenAI)
├── .env.example                # Modelo de variáveis de ambiente
├── executar.bat                # Gatilho compatível com o Agendador de Tarefas do Windows
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

### 3. Execução de Etapas Isoladas (Debug / Desenvolvimento)
Você pode rodar apenas uma etapa específica sem reexecutar o fluxo inteiro:
```powershell
# Apenas coleta do GitHub Trending
python main.py --step collect-github

# Apenas coleta de tweets no X (Radar VIP + Seguindo)
python main.py --step collect-twitter

# Apenas síntese do relatório com IA
python main.py --step summarize

# Apenas renderização e envio do e-mail com o último relatório
python main.py --step email
```

### 4. Consultar Status do Envio
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

## ⏰ Agendador de Tarefas do Windows

A automação matinal é executada pontualmente às **08:00 BRT** através do arquivo `executar.bat`:
* **Ação:** Dispara `python main.py` de forma silenciosa.
* **Logs:** Registrados e rotacionados automaticamente em `logs/execucao.log`.
* **Trava Antirrepetição:** Evita envios repetidos caso o computador seja reiniciado ao longo do dia.
