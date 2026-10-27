# 1. Agendamento Híbrido no Windows via Task Scheduler e Wrapper VBScript

## Contexto
O Diário de Engenharia precisa ser gerado e entregue diariamente às 08:00 AM na máquina local do desenvolvedor, mas a máquina frequentemente está desligada, suspensa ou inicializada mais tarde. Manter um processo Python rodando indefinidamente como daemon em segundo plano desperdiça recursos de memória e pode ser finalizado pelo sistema operacional.

## Decisão
Adotamos o **Agendador de Tarefas do Windows (Task Scheduler)** configurado com **duplo gatilho** (calendário diário às 08:00 e disparo por evento de Logon do usuário), executado através de um wrapper invisível em VBScript (`scripts/executar_silencioso.vbs`) e controlado por um arquivo de trava local (`data/ultimo_envio.txt`).

## Consequências
- **Positivas**: Zero consumo de memória em repouso; se o usuário ligar o computador às 09:20 ou 10:26, o relatório é gerado logo após o login; nenhuma janela preta de terminal pisca na tela.
- **Trade-offs**: A automação depende do ambiente Windows do usuário (não roda em servidores Linux sem adaptação para systemd/cron); o Agendador de Tarefas precisa ser configurado com políticas corretas de sessão interativa (`LogonType: Interactive`).
