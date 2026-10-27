# 07: DeliveryChannel Protocol and Adapters

**What to build:**
Criar a interface `DeliveryChannel` em `src/delivery/base.py` utilizando `typing.Protocol` nativo com o método `deliver(subject: str, html_body: str, recipient: str) -> bool`. Implementar os adaptadores concretos: `EmailDeliveryChannel` (responsável pelo envio real via Gmail SMTP SSL porta 465, preservando o código testado existente) e `FilePreviewDeliveryChannel` (responsável por gravar o conteúdo HTML em `reports/preview.html` e abrir no navegador padrão com `webbrowser.open`, com garantia estrita de zero conexões de rede).

**Blocked by:**
06: Integrate IngestionPipeline in Main & Checkpoint 2

**Status:**
completed

**Files to modify:**
- `src/delivery/base.py`
- `src/delivery/__init__.py`
- `tests/test_delivery_channels.py`

**Acceptance criteria:**
- [x] O protocolo `DeliveryChannel` define `deliver(subject: str, html_body: str, recipient: str) -> bool`.
- [x] `EmailDeliveryChannel` conecta ao SMTP SSL (`smtp.gmail.com:465`), valida credenciais do `.env` e despacha o envelope MIME multipart UTF-8.
- [x] `FilePreviewDeliveryChannel` grava `reports/preview.html` em codificação UTF-8, invoca `webbrowser.open()` e retorna `True` sem realizar conexões de rede.
- [x] Nenhum mock de rede é necessário para testar o canal de preview.
- [x] Testes unitários em `tests/test_delivery_channels.py` comprovam conformidade de ambos os canais com a interface.
