import smtplib
import ssl
from contextlib import contextmanager
from typing import Generator


@contextmanager
def conectar_smtp_ssl(
    remetente: str,
    senha_app: str,
    host: str = "smtp.gmail.com",
    port: int = 465,
    timeout: int = 20,
) -> Generator[smtplib.SMTP_SSL, None, None]:
    """Cria conexão SMTP SSL com validação de certificados, sanitiza credenciais e realiza autenticação.

    Ciclo de vida e encerramento:
    1. Fase de Conexão: Se smtplib.SMTP_SSL(...) falhar durante resolução de DNS, conexão TCP ou handshake TLS,
       a exceção propaga diretamente ao chamador antes da ativação do bloco de contexto.
    2. Context Manager Nativo: O bloco 'with server as s:' gerencia o ciclo de vida. Conforme a implementação
       oficial da biblioteca padrão Python (CPython 3.12 e 3.13), o método smtplib.SMTP.__enter__ retorna
       o próprio objeto (self) e smtplib.SMTP.__exit__ envia o comando protocolar QUIT (RFC 5321) e executa
       incondicionalmente self.close() dentro de uma cláusula 'finally', garantindo o fechamento determinístico
       do socket tanto em saídas bem-sucedidas quanto em caso de erro no login ou falha/timeout durante o comando QUIT.
    """
    if not remetente or not senha_app:
        raise ValueError("Remetente e senha de aplicativo são obrigatórios para conexão SMTP.")

    context = ssl.create_default_context()
    senha_limpa = senha_app.replace(" ", "")

    server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    with server as s:
        s.login(remetente, senha_limpa)
        yield s
