# Especificação Técnica 0003: DeliveryChannel & Preview Local

**Status:** Aprovado para detalhamento de tickets  
**Área:** Entrega, Renderização & Experiência de Desenvolvimento  
**Prerequisitos:** Nenhum (Pode ser implementado de forma independente)  

---

## 1. Problem Statement
Atualmente, o módulo `src/delivery/sender.py` agrupa quatro responsabilidades distintas:
1. Leitura e parsing do arquivo Markdown do relatório.
2. Renderização do HTML Bento Grid responsivo (`render_bento_email`).
3. Construção dos cabeçalhos e envelopes MIME multipart.
4. Conexão física com o servidor SMTP SSL do Gmail na porta 465.

Esse acoplamento rígido:
* Obriga qualquer teste do fluxo de entrega a simular servidores SMTP inteiros ou criar mocks invasivos de socket de rede.
* Impede que o desenvolvedor inspecione visualmente o e-mail final no navegador sem antes disparar uma mensagem real para a sua própria caixa de entrada.

---

## 2. Solution
Separar a preparação da mensagem (renderização do Bento Grid) do canal de transporte físico através do protocolo `DeliveryChannel`.

Implementar dois adaptadores concretos:
1. `EmailDeliveryChannel`: Executa o envio real via Gmail SMTP SSL (lógica já existente e testada).
2. `FilePreviewDeliveryChannel`: Grava o HTML Bento Grid gerado em `reports/preview.html` e o abre automaticamente no navegador padrão do sistema operacional, **sem tocar em sockets de e-mail**.

Adicionar a flag CLI `--preview` em `main.py`, permitindo alternar de forma determinística entre o envio real e a visualização local.

---

## 3. User Stories
1. **Como desenvolvedor**, quero executar `python main.py --preview` para gerar e abrir imediatamente no meu navegador o e-mail estilizado, para que eu possa avaliar alterações visuais no layout Bento Grid com ciclo de feedback instantâneo.
2. **Como desenvolvedor**, quero ter certeza absoluta de que acionar `--preview` **nunca** conectará ao SMTP do Gmail nem enviará mensagens reais, garantindo segurança total em desenvolvimento e testes locais.
3. **Como operador**, quero que as execuções automáticas diárias (via Agendador do Windows) continuem enviando o e-mail com 100% de fidelidade via Gmail SMTP para `fabrycio.bermudes@usabit.com.br`.
4. **Como mantenedor**, quero testar a entrega completa utilizando um canal em memória (`MockDeliveryChannel`), verificando o assunto, a data no cabeçalho e o payload HTML sem necessidade de conexão com a internet.

---

## 4. Implementation Decisions

### 4.1 Interface `DeliveryChannel` (`src/delivery/base.py`)
Utilizando `typing.Protocol`:
```python
from typing import Protocol

class DeliveryChannel(Protocol):
    def deliver(self, subject: str, html_body: str, recipient: str) -> bool:
        """Transporta a mensagem renderizada para o destino configurado."""
        ...
```

### 4.2 Adaptadores de Canal
* **`EmailDeliveryChannel` (`src/delivery/channels/email.py`):**
  * Conecta ao servidor SMTP SSL (`smtp.gmail.com:465`).
  * Autentica com credenciais do `.env` (`GMAIL_USER`, `GMAIL_APP_PASSWORD`).
  * Monta MIME multipart com suporte a UTF-8 e envia a mensagem.
* **`FilePreviewDeliveryChannel` (`src/delivery/channels/preview.py`):**
  * Grava o `html_body` em `reports/preview.html` (sobrescrevendo atomicamente).
  * Emite log informativo com o caminho absoluto do arquivo gerado.
  * Executa `webbrowser.open(caminho_preview)` para abrir no navegador padrão (Chrome/Edge).
  * Retorna `True` sem realizar nenhuma chamada de rede.

### 4.3 Orquestração da Entrega (`src/delivery/dispatcher.py` ou `sender.py`)
* Função `despachar_relatorio(caminho_relatorio: Path, channel: DeliveryChannel, destinatario: str | None = None) -> bool`:
  * Lê o Markdown do relatório.
  * Invoca `render_bento_email()` para gerar o HTML do Bento Grid.
  * Extrai a data e monta o assunto padrão: `"Diário de Engenharia: IA & Coding Agents - DD/MM/YYYY"`.
  * Invoca `channel.deliver(subject, html_body, recipient)`.

### 4.4 Atualização da CLI (`main.py`)
* Adicionar o argumento `--preview` ao parser:
  ```python
  parser.add_argument(
      "--preview",
      action="store_true",
      help="Renderiza o relatório em HTML e abre no navegador padrão sem enviar e-mail."
  )
  ```
* Se `--preview` for acionado:
  * Utiliza `FilePreviewDeliveryChannel`.
  * Emite notificação Toast no Windows: *"Prévia do Diário de IA gerada no navegador"*.
  * **Não executa** o registro de sucesso na trava diária (`ultimo_envio.txt`), permitindo que a automação matinal continue elegível para rodar normalmente.

---

## 5. Testing Decisions & Acceptance Criteria

### 5.1 Critérios de Aceitação
- [ ] O comando `python main.py --preview` gera o arquivo `reports/preview.html` e o abre no navegador.
- [ ] O modo `--preview` garante **zero conexões com servidores SMTP** (verificado via mock e auditoria de código).
- [ ] O modo `--preview` não altera o arquivo `data/ultimo_envio.txt`.
- [ ] A execução regular de produção (`python main.py` ou via agendador) continua enviando o e-mail via Gmail SMTP com sucesso idêntico.
- [ ] O assunto e o corpo HTML Bento Grid permanecem com a mesma estrutura visual.

### 5.2 Testes de Regressão Automatizados
- **Teste Unitário do FilePreviewChannel:** Validar que ao chamar `deliver()`, o arquivo `reports/preview.html` é criado com o conteúdo HTML exato e encoding UTF-8.
- **Teste Unitário com MockChannel:** Executar `despachar_relatorio()` com um canal falso que armazena os argumentos e checar se `subject` e `html_body` foram gerados corretamente a partir de um Markdown de teste.
- **Teste de Regressão do Renderer:** Os testes já existentes em `tests/test_renderer.py` devem passar 100% sem alterações.

---

## 6. Out of Scope
* Suporte a envio por Telegram, Slack ou Webhooks externos.
* Alterações na tipografia ou estilos do layout Bento Grid.
