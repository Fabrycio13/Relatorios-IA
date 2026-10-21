import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.core.config import config
from src.core.logger import get_logger
from .renderer import render_bento_email

logger = get_logger("email_sender")

def enviar_relatorio_email(destinatario: str | None = None, caminho_relatorio: str | Path | None = None) -> bool:
    """Envia o relatório diário de IA por e-mail com layout Bento Grid limpo."""
    remetente, senha_app, destinatario_padrao = config.get_email_credentials()
    destinatario_final = destinatario or destinatario_padrao

    if not caminho_relatorio:
        caminho_relatorio = config.obter_ultimo_relatorio()

    if not caminho_relatorio or not Path(caminho_relatorio).exists():
        logger.error(f"Nenhum arquivo de relatório encontrado em reports/ para envio.")
        return False

    caminho_path = Path(caminho_relatorio)
    with open(caminho_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    hora_envio = hoje.strftime("%H:%M")
    assunto = f"🧠 Resumo Diário de IA (Destaques de {ontem.strftime('%d/%m/%Y')}) • {hora_envio}"

    # Renderiza HTML Bento Grid
    html_content = render_bento_email(md_content)

    if not senha_app or len(senha_app.strip()) < 8:
        logger.error("Senha de app do Gmail não configurada no .env (GMAIL_APP_PASSWORD).")
        return False

    # Estrutura MIME 'alternative' limpa (sem anexos binários, elimina chips de anexo no Gmail)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario_final

    part_text = MIMEText(md_content, "plain", "utf-8")
    part_html = MIMEText(html_content, "html", "utf-8")

    msg.attach(part_text)
    msg.attach(part_html)

    logger.info(f"Conectando ao servidor SMTP do Gmail para enviar para {destinatario_final}...")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            senha_limpa = senha_app.replace(" ", "")
            server.login(remetente, senha_limpa)
            server.sendmail(remetente, [destinatario_final], msg.as_string())

        logger.info(f"✅ E-mail enviado com sucesso para {destinatario_final}!")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao enviar e-mail: {e}")
        return False

if __name__ == "__main__":
    import sys
    dest = sys.argv[1] if len(sys.argv) > 1 else None
    arquivo = sys.argv[2] if len(sys.argv) > 2 else None
    sucesso = enviar_relatorio_email(destinatario=dest, caminho_relatorio=arquivo)
    sys.exit(0 if sucesso else 1)
