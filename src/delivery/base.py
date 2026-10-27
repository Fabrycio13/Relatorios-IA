import os
import smtplib
import webbrowser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.core.config import REPORTS_DIR, config
from src.core.logger import get_logger

logger = get_logger("delivery.channels")


@runtime_checkable
class DeliveryChannel(Protocol):
    """Protocolo definindo a interface padrão para canais de entrega do relatório."""
    name: str

    def deliver(self, subject: str, html_body: str, recipient: str, plain_text: str = "") -> bool:
        """Transporta a mensagem renderizada para o destino configurado."""
        ...


class EmailDeliveryChannel:
    """Canal de transporte de e-mail via Gmail SMTP SSL porta 465."""
    name: str = "email"

    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 465,
        timeout: int = 20
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.timeout = timeout

    def deliver(self, subject: str, html_body: str, recipient: str, plain_text: str = "") -> bool:
        remetente, senha_app, destinatario_padrao = config.get_email_credentials()
        destinatario_final = recipient or destinatario_padrao

        if not senha_app or len(senha_app.strip()) < 8:
            logger.error("Senha de app do Gmail não configurada no .env (GMAIL_APP_PASSWORD).")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = remetente
        msg["To"] = destinatario_final

        if plain_text:
            part_text = MIMEText(plain_text, "plain", "utf-8")
            msg.attach(part_text)

        part_html = MIMEText(html_body, "html", "utf-8")
        msg.attach(part_html)

        logger.info(f"Conectando ao servidor SMTP do Gmail para enviar para {destinatario_final}...")
        try:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout) as server:
                senha_limpa = senha_app.replace(" ", "")
                server.login(remetente, senha_limpa)
                server.sendmail(remetente, [destinatario_final], msg.as_string())

            logger.info(f"✅ E-mail enviado com sucesso para {destinatario_final}!")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao enviar e-mail via SMTP: {e}")
            return False


class FilePreviewDeliveryChannel:
    """Canal de preview local: grava o HTML em arquivo e abre no navegador padrão sem usar rede."""
    name: str = "preview"

    def __init__(self, output_path: Path | str | None = None, auto_open: bool = True):
        self.output_path = Path(output_path) if output_path else (REPORTS_DIR / "preview.html")
        self.auto_open = auto_open

    def deliver(self, subject: str, html_body: str, recipient: str = "", plain_text: str = "") -> bool:
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.output_path.with_name(f"{self.output_path.name}.tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(html_body)
            os.replace(temp_path, self.output_path)

            logger.info(f"🔍 Prévia local gerada com sucesso em: {self.output_path.resolve()}")
            if self.auto_open:
                webbrowser.open(self.output_path.resolve().as_uri())
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao gerar prévia local em arquivo: {e}")
            return False
