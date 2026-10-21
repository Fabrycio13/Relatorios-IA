import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Configura encoding UTF-8 no Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src.core.config import STATUS_FILE, config
from src.core.logger import get_logger
from src.collectors.github import coletar_github_trending
from src.collectors.twitter import coletar_tweets_vip
from src.collectors.huggingface import coletar_papers_huggingface
from src.processors.ai_summarizer import gerar_resumo_ia
from src.delivery.sender import enviar_relatorio_email

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

def main():
    args = parse_args()
    hoje_str = datetime.now().strftime("%Y-%m-%d")

    # Flag --status
    if args.status:
        ultimo = verificar_status_envio()
        print(f"Data de hoje: {hoje_str}")
        print(f"Último envio registrado: {ultimo or 'Nenhum envio registrado ainda'}")
        ultimo_rel = config.obter_ultimo_relatorio()
        print(f"Último relatório gerado: {ultimo_rel.name if ultimo_rel else 'Nenhum'}")
        sys.exit(0)

    # Verificação de trava diária (evita envios repetidos ao reiniciar PC)
    if args.step == "all" and not args.force:
        ultimo_envio = verificar_status_envio()
        if ultimo_envio == hoje_str:
            logger.info(f"ℹ️  [OK] O relatório de hoje ({hoje_str}) já foi enviado com sucesso mais cedo. Use --force para reenviar.")
            sys.exit(0)

    inicio = time.time()
    logger.info("=" * 70)
    logger.info(f"INICIANDO PIPELINE DIÁRIO DE IA - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 70)

    # Etapa 1: Coleta Twitter / X
    if args.step in ["all", "collect", "collect-twitter"]:
        logger.info("\n▶️  [ETAPA 1/5] Coleta de Posts no X (Seguindo + Radar VIP)...")
        tweets = coletar_tweets_vip(headless=True)
        if not tweets and args.step != "all":
            logger.warning("Nenhum tweet novo coletado nesta execução.")

    # Etapa 2: Coleta GitHub Trending
    if args.step in ["all", "collect", "collect-github"]:
        logger.info("\n▶️  [ETAPA 2/5] Coleta de Repositórios em Alta no GitHub...")
        repos = coletar_github_trending(dias_atras=7, limite_top=6)
        logger.info(f"Repositórios coletados: {len(repos)}")

    # Etapa 3: Coleta Hugging Face Daily Papers
    if args.step in ["all", "collect", "collect-papers"]:
        logger.info("\n▶️  [ETAPA 3/5] Coleta de Papers em Destaque no Hugging Face...")
        papers = coletar_papers_huggingface(limite_top=3)
        logger.info(f"Papers científicos coletados: {len(papers)}")

    # Etapa 4: Síntese Inteligente com IA
    caminho_md = None
    if args.step in ["all", "summarize"]:
        logger.info("\n▶️  [ETAPA 4/5] Síntese e Tradução Técnica com IA (OpenAI)...")
        caminho_md = gerar_resumo_ia()
        if not caminho_md:
            logger.error("❌ Falha na geração do relatório de IA. Abortando envio de e-mail.")
            sys.exit(1)

    # Etapa 5: Envio de E-mail
    if args.step in ["all", "email"]:
        logger.info("\n▶️  [ETAPA 5/5] Renderização e Envio por E-mail...")
        relatorio_para_envio = caminho_md or config.obter_ultimo_relatorio()
        sucesso_email = enviar_relatorio_email(destinatario=args.to, caminho_relatorio=relatorio_para_envio)
        if not sucesso_email:
            logger.error("❌ Falha ao enviar o e-mail.")
            sys.exit(1)

        if args.step == "all":
            registrar_envio_sucesso(hoje_str)

    tempo_total = time.time() - inicio
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ PIPELINE CONCLUÍDO COM SUCESSO EM {tempo_total:.1f}s!")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
