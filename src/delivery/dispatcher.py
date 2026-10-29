from datetime import datetime, timedelta
from pathlib import Path

from src.core.config import config
from src.core.logger import get_logger
from .base import DeliveryChannel, EmailDeliveryChannel
from .renderer import render_bento_email
from .banner_selector import BannerInfo

logger = get_logger("delivery.dispatcher")


def despachar_relatorio(
    caminho_relatorio: str | Path | None = None,
    channel: DeliveryChannel | None = None,
    destinatario: str | None = None,
    data_envio: datetime | None = None,
    banner_info: BannerInfo | None = None
) -> bool:
    """
    Orquestra a leitura do Markdown do relatório, renderização do HTML Bento Grid
    e delegação do transporte da mensagem ao DeliveryChannel informado.
    """
    if channel is None:
        channel = EmailDeliveryChannel()

    if not caminho_relatorio:
        caminho_relatorio = config.obter_ultimo_relatorio()

    if not caminho_relatorio or not Path(caminho_relatorio).exists():
        logger.error("Nenhum arquivo de relatório encontrado em reports/ para despacho.")
        return False

    caminho_path = Path(caminho_relatorio)
    try:
        with open(caminho_path, "r", encoding="utf-8") as f:
            md_content = f.read()
    except Exception as e:
        logger.error(f"Erro ao ler arquivo de relatório {caminho_path}: {e}")
        return False

    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    hora_envio = hoje.strftime("%H:%M")
    assunto = f"🤖 Resumo Diário de IA (Destaques de {ontem.strftime('%d/%m/%Y')}) • {hora_envio}"

    logger.info(f"Renderizando HTML Bento Grid para o relatório: {caminho_path.name}...")
    try:
        html_content = render_bento_email(
            md_content,
            data_envio=data_envio,
            banner_info=banner_info
        )
    except Exception as e:
        logger.error(f"Erro ao renderizar template Bento Grid: {e}")
        return False

    canal_nome = getattr(channel, "name", "")
    alvo_log = destinatario or ("local" if canal_nome == "preview" else "destinatário padrão")
    logger.info(f"Despachando relatório via canal [{channel.__class__.__name__}] para: {alvo_log}...")
    return channel.deliver(
        subject=assunto,
        html_body=html_content,
        recipient=destinatario or "",
        plain_text=md_content
    )
