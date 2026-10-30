# 💻 Guia de Migração: Servidor Doméstico no Notebook (The Engineering Gazette)

Este guia orienta a configuração do seu notebook como **servidor doméstico dedicado 24/7** para a execução autônoma do diário de IA sem depender do seu computador principal.

---

## 🎯 Por que o Notebook é a Melhor Solução?
* **Zero Bloqueios no X:** O notebook utiliza o seu **IP residencial real da sua casa**, eliminando bloqueios antibot e desafios de Cloudflare típicos de datacenters na nuvem.
* **Custo Zero:** Dispensa qualquer assinatura de VPS, proxies rotativos ou API oficial paga do Twitter (economia de mais de US$ 100/mês).
* **Consumo Mínimo de Energia:** Configurado com a tampa fechada e a tela desligada na tomada, um notebook moderno em repouso consome apenas **~5W a 8W** (menos que uma lâmpada LED).

---

## ⏱️ Roteiro de Instalação (5 Passos / ~5 Minutos)

### Passo 1: Preparar o Pendrive no PC Principal
No seu computador principal (onde tudo já está funcionando), copie para um pendrive comum apenas os dois itens confidenciais que **não** sobem para o GitHub:

1. O arquivo `.env` (contendo suas chaves da OpenAI e credenciais de e-mail).
2. A pasta `.session/` (contendo os cookies já autenticados do X/Twitter).

---

### Passo 2: Configuração de Energia no Notebook (Tampa Fechada)
Para que o notebook continue rodando o pipeline pontualmente às 08:00 AM mesmo com a tampa fechada:

1. No notebook, abra o **Menu Iniciar** e digite **Painel de Controle**.
2. Vá em **Sistema e Segurança ➔ Opções de Energia**.
3. No menu lateral esquerdo, clique em **"Escolher a função do fechamento da tampa"**.
4. Na linha *"Quando eu fechar a tampa"*, altere a coluna **Conectado à tomada** para:
   👉 **"Nada a fazer"** (deixe a bateria como "Suspender").
5. Clique em **Salvar alterações**.
6. Em *Opções de Energia*, clique em **"Escolher quando desligar o vídeo"** e configure:
   * Desligar vídeo (conectado à tomada): **2 minutos**.

> 💡 **Resultado:** Ao fechar a tampa, a tela do notebook apaga imediatamente, o aparelho opera frio e silencioso, mas o processador e o Wi-Fi continuam 100% ativos para disparar os relatórios.

---

### Passo 3: Baixar o Projeto e Injetar os Segredos
No notebook:

1. Abra o terminal (PowerShell ou Git Bash) e clone o repositório:
   ```powershell
   git clone https://github.com/Fabrycio13/Relatorios-IA.git
   cd Relatorios-IA
   ```
2. Conecte o pendrive e copie o arquivo `.env` e a pasta `.session/` para a raiz da pasta `Relatorios-IA`.

---

### Passo 4: Instalar Python e Dependências
1. Certifique-se de que o **Python 3.11+** está instalado (ao instalar, marque a caixa *"Add python.exe to PATH"*).
2. No PowerShell, dentro da pasta do projeto, execute:
   ```powershell
   pip install -r requirements.txt
   playwright install chromium
   ```

---

### Passo 5: Teste de Prévia e Ativação do Agendador
1. Valide a integridade do pipeline sem disparar e-mails reais (modo preview):
   ```powershell
   python main.py --preview
   ```
   *(O navegador deve abrir exibindo a edição do dia com o layout Bento Grid perfeitamente renderizado).*

2. Registre a tarefa oficial no Windows Task Scheduler do notebook:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_task.ps1 -Install
   ```

3. Verifique se o status está ativo:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_task.ps1 -Status
   ```

Pronto! Seu notebook agora é o executor oficial autônomo do jornal.

---

## 🔄 Como Atualizar o Notebook no Futuro?

Sempre que você criar novos banners, adicionar feriados no `manifesto.json` ou melhorar o código no seu **PC principal**, basta enviar para o GitHub normalmente:
```powershell
git commit -m "feat: novos banners"
git push origin main
```

No notebook, quando quiser sincronizar, basta rodar uma única vez:
```powershell
git pull origin main
```

*(Opcional: Você também pode adicionar a linha `git pull origin main` no topo do arquivo `executar.bat` do notebook para que ele se atualize de forma 100% automática antes do disparo matinal de cada dia).*
