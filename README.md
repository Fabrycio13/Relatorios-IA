# 🤖 Diário de Engenharia: IA & Coding Agents

Automação matinal autônoma que coleta os principais acontecimentos de IA no **X (Twitter)**, repositórios em alta no **GitHub** e artigos científicos no **Hugging Face Papers**, sintetizando tudo via LLM em um relatório visual moderno (**Bento Grid HTML**) entregue pontualmente às 08:00 no seu e-mail.

---

## ⚡ Como Funciona

1. **Coleta Multi-fonte:** Varredura resiliente no X (Playwright headless), GitHub Trending API e Hugging Face Papers.
2. **Síntese Editorial com IA:** Curadoria e tradução técnica com takeaways acionáveis de engenharia.
3. **Entrega Bento Grid:** E-mail HTML responsivo de alta resolução com banners rotativos e travas de segurança anti-XSS.

---

## 🚀 Início Rápido

```bash
# 1. Instale as dependências mínimas
pip install -r requirements.txt

# 2. Configure suas credenciais (OpenAI, Gmail SMTP, Twitter)
cp .env.example .env

# 3. Veja o relatório renderizado no seu navegador (sem disparar e-mails)
python main.py --preview
```

---

## 💻 Comandos Principais

| Ação | Comando |
| :--- | :--- |
| **Execução Padrão** | `python main.py` |
| **Pré-visualizar no Navegador** | `python main.py --preview` |
| **Forçar Reenvio Hoje** | `python main.py --force` |
| **Diagnóstico de Conexões** | `python main.py --check-auth` |
| **Status do Último Envio** | `python main.py --status` |
| **Suíte de Testes (186 testes)** | `python -m unittest discover -s tests -t . -v` |

---

## ⏰ Automação no Windows

O projeto inclui agendamento 100% invisível em segundo plano (08:00 AM ou no Logon pós-boot):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_task.ps1 -Install
```

---

## 📚 Documentação Técnica Aprofundada

Para detalhes de engenharia, arquitetura e especificações:
* 🏛️ **[Arquitetura do Sistema](docs/ARCHITECTURE.md):** Padrões Clean Architecture, Zonas de Confiança e tolerância a falhas.
* 📖 **[Glossário de Domínio](GLOSSARY.md):** Vocabulário ubíquo oficial.
* 📋 **[Decisões de Arquitetura (ADRs)](docs/adr/):** Registros formais de decisões técnicas.
* 💻 **[Guia do Servidor Doméstico](docs/guides/migracao_notebook.md):** Como rodar 24/7 com tela desligada.
* 📜 **[Retrospectivas e Lições](docs/retrospectives/):** Histórico de qualidade e melhorias contínuas.
* 📚 **[Central de Documentação](docs/README.md):** Índice completo de specs, tickets e manuais.
