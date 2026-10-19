# 🧠 Relatórios Diários de Inteligência Artificial (Feed do X)

Automação completa para coleta, análise por IA e envio diário por e-mail dos principais acontecimentos, ferramentas e discussões de Inteligência Artificial publicadas no X (Twitter).

---

## 🚀 Arquitetura do Fluxo

```text
[X / Twitter Feed]
       │
       ▼ (Playwright Headless)
[coletar_tweets.py] ──► tweets_coletados.json
                             │
                             ▼ (Gemini / OpenAI API)
                      [gerar_resumo_ia.py] ──► Resumo_IA_<DATA>.md
                                                    │
                                                    ▼ (Gmail SMTP SSL)
                                             [enviar_email.py] ──► Caixa de Entrada ✉️
```

---

## ⏰ Execução Automática (GitHub Actions)

O workflow em `.github/workflows/relatorio_diario.yml` é executado:
* **Automaticamente todos os dias às 09:00 (Horário de Brasília / 12:00 UTC)**.
* **Manualmente a qualquer momento** através do botão **"Run workflow"** na aba *Actions* do GitHub.

---

## 🔐 Secrets Necessárias no GitHub

Configuradas em *Settings > Secrets and variables > Actions*:

| Secret | Descrição |
|---|---|
| `X_AUTH_TOKEN` | Token do cookie de sessão do X (`auth_token`) |
| `X_CT0` | Token de segurança CSRF do X (`ct0`) |
| `OPENAI_API_KEY` ou `GEMINI_API_KEY` | Chave de API para estruturar o resumo nos 5 tópicos |
| `GMAIL_USER` | E-mail do remetente (ex: `bermudes.fbc@gmail.com`) |
| `GMAIL_APP_PASSWORD` | Senha de Aplicativo de 16 letras gerada no Google |
| `GMAIL_TO` | E-mail corporativo de destino (ex: `fabrycio.bermudes@usabit.com.br`) |
