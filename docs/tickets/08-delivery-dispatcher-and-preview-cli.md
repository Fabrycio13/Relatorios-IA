# 08: Delivery Dispatcher & Preview CLI

**What to build:**
Criar a função orquestradora `despachar_relatorio` em `src/delivery/dispatcher.py` (desacoplando o parsing de Markdown e a renderização do Bento Grid do canal de envio). Adicionar a flag `--preview` na CLI em `main.py`. Configurar a injeção do canal apropriado com base na flag: `FilePreviewDeliveryChannel` no modo preview e `EmailDeliveryChannel` no modo de produção. Garantir estritamente que o modo preview não invoque SMTP e não atualize a trava antirrepetição `data/ultimo_envio.txt`.

**Blocked by:**
07: DeliveryChannel Protocol and Adapters

**Status:**
completed

**Files to modify:**
- `src/delivery/dispatcher.py`
- `src/delivery/sender.py`
- `main.py`
- `tests/test_delivery_dispatcher.py`

**Acceptance criteria:**
- [x] `despachar_relatorio(caminho_relatorio, channel, destinatario)` orquestra a leitura do Markdown, a renderização com `render_bento_email` e a entrega via `channel.deliver()`.
- [x] A flag `--preview` é adicionada ao `argparse` em `main.py`.
- [x] No modo `--preview`, o sistema instancia exclusivamente o `FilePreviewDeliveryChannel`, abre o preview no navegador e exibe notificação toast do Windows.
- [x] No modo `--preview`, a trava diária `data/ultimo_envio.txt` **nunca** é gravada ou alterada.
- [x] No modo normal de produção, o sistema instancia `EmailDeliveryChannel` e atualiza a trava diária apenas mediante confirmação de sucesso de envio.
- [x] Testes unitários com um canal em memória (`MockDeliveryChannel`) verificam o despacho, assunto e corpo HTML sem necessidade de mockar conexões de socket.
