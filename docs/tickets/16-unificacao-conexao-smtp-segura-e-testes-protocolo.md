# 16: Unificação da Conexão SMTP Segura e Testes de Protocolo CPython

**What to build:**
Centralizar a lógica de conexão SMTP segura (`SMTP_SSL` na porta 465 com TLS estrito) em uma função utilitária compartilhada (`conectar_smtp_ssl`) no novo módulo `src/core/smtp.py`. Atualmente, essa conexão é duplicada de forma divergente em `src/delivery/base.py` (`EmailDeliveryChannel.deliver`) e em `src/core/healthcheck.py` (`check_email`), gerando risco de assimetria na política de segurança de transporte e forçando uma potencial inversão de camadas caso a função fosse hospedada em `delivery`.

A função é implementada como um context manager (`@contextmanager`), centralizando a validação de parâmetros, a criação de `ssl.create_default_context()`, a normalização da senha de aplicativo (remoção de espaços) e a autenticação `server.login()`. O ciclo de vida do socket apoia-se no método nativo `__exit__` de `smtplib.SMTP` (validado no CPython 3.12 e 3.13), que assegura o envio do comando `QUIT` (RFC 5321) e o fechamento do socket dentro de um bloco `finally: self.close()`.

Os dois consumidores existentes (`EmailDeliveryChannel.deliver` e `check_email`) são refatorados para consumir a nova função, mantendo intactas suas assinaturas públicas, retornos e comportamentos específicos de tratamento de erro e log. São implementados testes unitários herméticos dedicados em `tests/test_smtp.py` cobrindo detalhadamente os cenários reais de protocolo do runtime CPython, e os testes existentes que mockavam conexões SMTP são alinhados ao novo contrato.

**Blocked by:**
None (pode iniciar imediatamente; unidade autônoma de arquitetura)

**Status:**
ready-for-agent

**Files to modify:**
- `src/core/smtp.py` *(novo)*
- `src/delivery/base.py`
- `src/core/healthcheck.py`
- `tests/test_smtp.py` *(novo)*
- `tests/test_delivery_channels.py`
- `tests/test_healthcheck.py`
- `tests/test_delivery_integration.py`

**Acceptance criteria:**
- [ ] Criação do módulo `src/core/smtp.py` contendo a função geradora context manager:
  ```python
  @contextmanager
  def conectar_smtp_ssl(
      remetente: str,
      senha_app: str,
      host: str = "smtp.gmail.com",
      port: int = 465,
      timeout: int = 20,
  ) -> Generator[smtplib.SMTP_SSL, None, None]:
  ```
- [ ] Validação defensiva de parâmetros em `conectar_smtp_ssl`:
  - Lança `ValueError("Remetente e senha de aplicativo são obrigatórios para conexão SMTP.")` se `remetente` ou `senha_app` for vazio ou nulo.
- [ ] Política de Segurança e Transporte Unificada:
  - Criação de contexto TLS seguro via `ssl.create_default_context()`, garantindo validação de cadeia de certificados e verificação de hostname.
  - Normalização da senha de aplicativo: remoção obrigatória de espaços em branco via `.replace(" ", "")`.
  - Instanciação de `smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)`.
  - Autenticação e ciclo de vida gerenciados pelo bloco nativo `with server: server.login(remetente, senha_limpa); yield server`.
- [ ] Rastreabilidade Arquitetural e Direção de Dependências:
  - `src/core/smtp.py` depende exclusivamente de bibliotecas padrão (`contextlib`, `smtplib`, `ssl`, `typing`).
  - `src/core/healthcheck.py` consome `src.core.smtp` (dependência intra-camada `core`).
  - `src/delivery/base.py` consome `src.core.smtp` (dependência descendente `delivery -> core`).
  - Zero acoplamentos circulares ou importações reversas de `delivery` para `core`.
- [ ] Refatoração do Consumidor `EmailDeliveryChannel.deliver` (`src/delivery/base.py`):
  - Preserva a assinatura pública: `deliver(self, subject: str, html_body: str, recipient: str, plain_text: str = "") -> bool`.
  - Consome `with conectar_smtp_ssl(remetente, senha_app, host=self.smtp_host, port=self.smtp_port, timeout=self.timeout) as server:` para envio.
  - Em caso de exceção (`Exception as e`), preserva rigorosamente o log original `logger.error(f"❌ Erro ao enviar e-mail via SMTP: {e}")` e retorna `False`.
- [ ] Refatoração do Consumidor `check_email` (`src/core/healthcheck.py`):
  - Preserva a assinatura pública: `check_email() -> tuple[bool, str]`.
  - Mantém a validação prévia de credenciais no `.env`, retornando `(False, "Credenciais de e-mail incompletas no .env")` sem tentar conexão.
  - Consome `with conectar_smtp_ssl(remetente, senha_app, timeout=6): pass` para teste de autenticação.
  - Retorna `(True, f"Login SMTP OK ({remetente} -> {destinatario})")` em caso de sucesso.
  - Em caso de exceção (`Exception as e`), retorna `(False, f"Falha no login SMTP do Gmail: {e}")` sem emitir log fatal.
- [ ] Testes Unitários de Ciclo de Vida do Protocolo CPython (`tests/test_smtp.py`):
  - **Cenário 1 — Encerramento Normal:** Execução bem-sucedida do bloco `with`; verifica que `docmd("QUIT")` retornou 221 e `server.close()` foi chamado incondicionalmente no `finally`.
  - **Cenário 2 — Falha de Autenticação com Encerramento Limpo:** `server.login()` levanta `smtplib.SMTPAuthenticationError`; o context manager aciona `__exit__`, envia `QUIT`, fecha o socket e propaga a exceção original `SMTPAuthenticationError` ao chamador.
  - **Cenário 3 — Desconexão/Timeout durante QUIT:** `docmd("QUIT")` levanta `smtplib.SMTPServerDisconnected` (gerado pelo `getreply()` do CPython ao capturar `OSError`/EOF); verifica que `__exit__` captura a exceção, executa `server.close()` no `finally` e não vaza erro espúrio.
  - **Cenário 4 — Resposta Anômala ao QUIT (Código != 221):** `docmd("QUIT")` retorna código de erro (ex: 500); verifica que `__exit__` levanta `smtplib.SMTPResponseException` e que o socket é fechado no `finally`.
  - **Cenário 5 (Ressalva de Aceitação D4) — Substituição de Exceção por Resposta Anômala ao QUIT:** Simula falha em `server.login()` (levantando `SMTPAuthenticationError`) seguida de resposta anômala do servidor ao comando `QUIT` disparado pelo `__exit__` (código 500 levantando `SMTPResponseException`). O teste comprova que, conforme a semântica de exceções do CPython, a exceção levantada em `__exit__` (`SMTPResponseException`) substitui a exceção original (`SMTPAuthenticationError`), garantindo que o fechamento do socket ocorra em `finally`.
  - **Cenário 6 — Normalização de Credenciais:** Comprova que senhas de aplicativo com espaços (ex: `"abcd efgh ijkl mnop"`) têm espaços removidos antes do `login()`.
  - **Cenário 7 — Rejeição de Parâmetros Inválidos:** Comprova que strings vazias ou nulas para remetente ou senha levantam `ValueError` antes de qualquer inicialização de socket.
- [ ] Atualização de Mocks em Testes Existentes:
  - `tests/test_delivery_channels.py`, `tests/test_healthcheck.py` e `tests/test_delivery_integration.py` são alinhados para mockar `conectar_smtp_ssl` ou `smtplib.SMTP_SSL` conforme apropriado, mantendo 100% de passagem nos testes herméticos.
- [ ] Garantia de Não-Regressão e Hermeticidade:
  - Zero conexões de rede reais (testes operam estritamente sob os guardrails de `tests/guardrails.py`).
  - Execução da suíte completa canônica (`python -m unittest discover -s tests -t . -v`) com 100% de aprovação.
  - Zero ResourceWarnings (`python -W error::ResourceWarning -m unittest discover -s tests -t .`).

**TDD & Validation Commands:**
```bash
# Execução focada dos testes do novo módulo SMTP
python -m unittest tests.test_smtp -v

# Execução dos testes de canais de entrega e healthcheck refatorados
python -m unittest tests.test_delivery_channels tests.test_healthcheck tests.test_delivery_integration -v

# Execução completa da suíte canônica sob guardrails de rede
python -m unittest discover -s tests -t . -v

# Verificação estrita de ausência de ResourceWarning
python -W error::ResourceWarning -m unittest discover -s tests -t .
```
