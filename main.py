import argparse
import sys
import time
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

# Configura encoding UTF-8 no Windows e line buffering imediato
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

from src.core.config import STATUS_FILE, config
from src.core.logger import get_logger
from src.core.healthcheck import executar_healthcheck
from src.core.notifier import notificar_windows
from src.collectors import IngestionPipeline
from src.processors.ai_summarizer import gerar_resumo_ia
from src.delivery import (
    despachar_relatorio,
    EmailDeliveryChannel,
    FilePreviewDeliveryChannel,
    resolver_banner_do_dia,
    confirmar_banner_utilizado,
    reconciliar_historico_se_necessario,
)
from src.core.lock import adquirir_trava_pipeline, ConcorrenciaDetectadaError

logger = get_logger("orchestrator")

def parse_args():
    parser = argparse.ArgumentParser(
        description="Diário de Engenharia: IA & Coding Agents - Pipeline Automatizado"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Força a execução mesmo que o relatório do dia já tenha sido enviado."
    )
    parser.add_argument(
        "--step", "-s",
        choices=["all", "collect", "collect-twitter", "collect-github", "collect-papers", "summarize", "email"],
        default="all",
        help="Executa uma etapa isolada do pipeline."
    )
    parser.add_argument(
        "--to",
        type=str,
        default=None,
        help="Sobrescreve o destinatário de e-mail nesta execução."
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Exibe o status do último envio e encerra."
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Executa diagnóstico de saúde e autenticação de todas as integrações em 5 segundos."
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Renderiza o relatório em HTML e abre no navegador padrão sem enviar e-mail."
    )
    return parser.parse_args()

def verificar_status_envio() -> str | None:
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return None

def registrar_envio_sucesso(dia_str: str):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(dia_str)
    except Exception as e:
        logger.warning(f"Não foi possível salvar status em {STATUS_FILE}: {e}")

def aguardar_conexao_internet(timeout_segundos: int = 60) -> bool:
    """Aguarda até que a conexão de internet esteja ativa (útil para execuções logo após o boot do PC)."""
    import socket
    import urllib.request
    inicio = time.time()
    while time.time() - inicio < timeout_segundos:
        # Teste 1: Conexão socket direta com DNS público (Google 8.8.8.8:53) - mais rápido e imune a bloqueios HTTP
        try:
            with socket.create_connection(("8.8.8.8", 53), timeout=3):
                return True
        except Exception:
            pass

        # Teste 2: Fallback HTTP simples
        try:
            req = urllib.request.Request("https://www.google.com", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            pass

        time.sleep(3)
    return False

def main():
    args = parse_args()
    hoje_str = datetime.now().strftime("%Y-%m-%d")

    lock_file = STATUS_FILE.with_suffix(".lock")
    precisa_trava = (
        args.step in ["all", "email"]
        and not args.preview
        and not args.status
        and not args.check_auth
    )
    trava_mgr = adquirir_trava_pipeline(lock_file) if precisa_trava else nullcontext()

    try:
        with trava_mgr:
            # Flag --status
            if args.status:
                ultimo = verificar_status_envio()
                print(f"Data de hoje: {hoje_str}")
                print(f"Último envio registrado: {ultimo or 'Nenhum envio registrado ainda'}")
                ultimo_rel = config.obter_ultimo_relatorio()
                print(f"Último relatório gerado: {ultimo_rel.name if ultimo_rel else 'Nenhum'}")
                sys.exit(0)

            # Flag --check-auth
            if args.check_auth:
                sucesso = executar_healthcheck()
                sys.exit(0 if sucesso else 1)

            # Verificação de agendamento automático diário (quando rodando sem --force e sem --preview)
            if args.step == "all" and not args.force and not args.preview:
                agora = datetime.now()
                # Se o PC foi ligado antes das 08:00 (ex: 07:30), aguarda o gatilho das 08:00
                if agora.hour < 8:
                    logger.info(f"ℹ️  Horário atual ({agora.strftime('%H:%M')}) é anterior às 08:00. O envio diário aguardará o agendamento das 08:00.")
                    sys.exit(0)

                # Se já foi enviado hoje, encerra silenciosamente
                ultimo_envio = verificar_status_envio()
                if ultimo_envio == hoje_str:
                    logger.info(f"ℹ️  [OK] O relatório de hoje ({hoje_str}) já foi enviado com sucesso mais cedo. Use --force para reenviar.")
                    sys.exit(0)

            # Aguarda conexão de internet se for etapa de coleta/completa (caso o PC tenha acabado de ligar)
            if args.step in ["all", "collect", "collect-twitter", "collect-github", "collect-papers"]:
                logger.info("Verificando conectividade com a internet...")
                if not aguardar_conexao_internet(timeout_segundos=60):
                    logger.error("❌ Conexão com a internet indisponível após 60s. O pipeline não pode prosseguir sem rede.")
                    notificar_windows(
                        "⚠️ Diário de IA: Sem Internet",
                        "O PC está sem conexão com a internet. A execução será repetida automaticamente assim que a rede conectar."
                    )
                    sys.exit(2)

            # Notificação nativa no Windows informando início do processamento em segundo plano
            if args.step == "all":
                notificar_windows("🤖 Diário de IA", f"Iniciando coleta e geração do relatório diário ({hoje_str})...")

            inicio = time.time()
            logger.info("=" * 70)
            logger.info(f"INICIANDO PIPELINE DIÁRIO DE IA - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            logger.info("=" * 70)

            batch = None

            # Etapa de Ingestão: Coleta unificada via IngestionPipeline
            if args.step in ["all", "collect", "collect-twitter", "collect-github", "collect-papers"]:
                logger.info("\n▶️  [ETAPA 1/3] Coleta Unificada de Dados via IngestionPipeline...")
                pipeline = IngestionPipeline()
                batch = pipeline.run(target_source=args.step)

                # Aborta com código 1 caso o usuário tenha rodado um step exclusivo e a fonte não retornou dados
                if args.step in ["collect-twitter", "collect-github", "collect-papers"]:
                    if batch.is_empty():
                        logger.error(f"❌ Falha na coleta da fonte exclusiva '{args.step}'. Nenhum item obtido.")
                        sys.exit(1)

            # Etapa de Síntese Inteligente com IA
            caminho_md = None
            if args.step in ["all", "summarize"]:
                logger.info("\n▶️  [ETAPA 2/3] Síntese e Tradução Técnica com IA (OpenAI)...")
                caminho_md = gerar_resumo_ia(batch=batch)
                if not caminho_md:
                    logger.error("❌ Falha na geração do relatório de IA. Abortando envio de e-mail.")
                    notificar_windows("⚠️ Falha no Diário de IA", "Falha na síntese com OpenAI. Veja logs/execucao.log.")
                    sys.exit(1)

            # Etapa de Envio por E-mail ou Preview
            if args.step in ["all", "email"]:
                relatorio_para_envio = caminho_md or config.obter_ultimo_relatorio()

                if args.preview:
                    logger.info("\n▶️  [ETAPA 3/3] Renderização e Pré-visualização Local (Preview)...")
                    agora_preview = datetime.now()
                    banner_preview = resolver_banner_do_dia(data_envio=agora_preview)
                    channel = FilePreviewDeliveryChannel()
                    sucesso = despachar_relatorio(
                        caminho_relatorio=relatorio_para_envio,
                        channel=channel,
                        data_envio=agora_preview,
                        banner_info=banner_preview
                    )
                    if not sucesso:
                        logger.error("❌ Falha ao gerar preview local.")
                        notificar_windows("⚠️ Falha no Diário de IA", "Falha ao gerar preview local do relatório.")
                        sys.exit(1)

                    notificar_windows("👁️ Diário de IA: Preview", "Prévia do Diário de IA gerada no navegador.")
                else:
                    logger.info("\n▶️  [ETAPA 3/3] Renderização e Envio por E-mail...")
                    agora_envio = datetime.now()
                    reconciliar_historico_se_necessario(data_envio=agora_envio, status_file=STATUS_FILE)
                    banner_do_dia = resolver_banner_do_dia(data_envio=agora_envio)

                    channel = EmailDeliveryChannel()
                    sucesso_email = despachar_relatorio(
                        caminho_relatorio=relatorio_para_envio,
                        channel=channel,
                        destinatario=args.to,
                        data_envio=agora_envio,
                        banner_info=banner_do_dia
                    )
                    if not sucesso_email:
                        logger.error("❌ Falha ao enviar o e-mail.")
                        notificar_windows("⚠️ Falha no Diário de IA", "Falha ao enviar relatório por e-mail. Veja logs/execucao.log.")
                        sys.exit(1)

                    # Persiste atomicamente o uso do banner EXCLUSIVAMENTE após o envio bem-sucedido
                    confirmar_banner_utilizado(banner_info=banner_do_dia, data_envio=agora_envio)

                    if args.step == "all":
                        registrar_envio_sucesso(hoje_str)
                        notificar_windows("✅ Diário de IA Enviado!", f"Relatório de {hoje_str} gerado e enviado para {args.to or config.GMAIL_TO} com sucesso!")

            tempo_total = time.time() - inicio
            logger.info("\n" + "=" * 70)
            logger.info(f"✅ PIPELINE CONCLUÍDO COM SUCESSO EM {tempo_total:.1f}s!")
            logger.info("=" * 70)

    except ConcorrenciaDetectadaError:
        logger.info("ℹ️  Outro processo do pipeline já está em execução no momento. Encerrando para evitar concorrência.")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        logger.exception(f"❌ Erro crítico inesperado no pipeline: {e}")
        notificar_windows("⚠️ Erro Crítico no Diário de IA", f"Exceção: {str(e)[:100]}")
        sys.exit(1)

if __name__ == "__main__":
    main()
