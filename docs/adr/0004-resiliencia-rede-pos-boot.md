# 4. Resiliência de Rede Pós-Boot com Socket DNS e Retentativas no Agendador

## Contexto
Quando o computador liga ou retorna do modo de suspensão, o Agendador de Tarefas pode disparar a execução do pipeline antes que a placa de rede ou Wi-Fi tenha adquirido endereço IP via DHCP e estabelecido rotas de internet. Testes ingênuos de requisição HTTP (como pings a URLs arbitrárias) podem sofrer bloqueios de firewall corporativo, captive portals ou erros 403 de CDNs.

## Decisão
Implementamos uma rotina de guarda que aguarda até 60 segundos pela rede realizando uma conexão de baixo nível via **socket TCP na porta DNS pública (`8.8.8.8:53`)**, com fallback HTTP leve. Caso a conexão não seja estabelecida no prazo, o script emite uma notificação nativa no Windows (Toast), encerra com código de saída 2, e o Agendador de Tarefas do Windows retenta a execução automaticamente a cada 5 minutos (até 3 vezes).

## Consequências
- **Positivas**: Elimina falhas de DNS (`getaddrinfo failed`) no início da inicialização da máquina; a checagem é instantânea (0.02s) quando a internet já está disponível; o sistema recupera-se autonomamente sem intervenção do usuário.
- **Trade-offs**: Introduz uma espera de até 60s em situações em que a máquina está intencionalmente desconectada da rede antes de falhar formalmente.
