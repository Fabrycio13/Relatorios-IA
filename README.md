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
                             ▼ (OpenAI / Gemini API)
                      [gerar_resumo_ia.py] ──► Resumo_IA_<DATA>.md
                                                    │
                                                    ▼ (Gmail SMTP SSL)
                                             [enviar_email.py] ──► fabrycio.bermudes@usabit.com.br ✉️
```

---

## ⏰ Execução Automática (Agendador de Tarefas do Windows)

A rotina é orquestrada pelo script principal `executar_fluxo.py`:
* **Horário:** Todos os dias pontualmente às **09:00 da manhã**.
* **Modo Silencioso:** Executado em segundo plano via `pythonw.exe` (sem abrir janela de console).
* **Histórico de Logs:** Registrado em `execucao.log`.
* **Janela Temporal:** Analisa o ciclo de 24 horas completo do **dia anterior (D-1)**.

---

## 🛠️ Como Executar Manualmente

Para rodar o fluxo completo a qualquer momento:

```powershell
python "D:\Projetos\Relatorios - IA\executar_fluxo.py"
```
