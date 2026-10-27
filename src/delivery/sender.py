from pathlib import Path

from .base import EmailDeliveryChannel
from .dispatcher import despachar_relatorio


def enviar_relatorio_email(destinatario: str | None = None, caminho_relatorio: str | Path | None = None) -> bool:
    """Envia o relatório diário de IA por e-mail com layout Bento Grid limpo."""
    channel = EmailDeliveryChannel()
    return despachar_relatorio(
        caminho_relatorio=caminho_relatorio,
        channel=channel,
        destinatario=destinatario
    )


if __name__ == "__main__":
    import sys
    dest = sys.argv[1] if len(sys.argv) > 1 else None
    arquivo = sys.argv[2] if len(sys.argv) > 2 else None
    sucesso = enviar_relatorio_email(destinatario=dest, caminho_relatorio=arquivo)
    sys.exit(0 if sucesso else 1)
