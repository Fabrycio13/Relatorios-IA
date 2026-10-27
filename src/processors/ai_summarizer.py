import json
import os
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from src.core.config import (
    DATA_DIR,
    REPORTS_DIR,
    GITHUB_DATA_FILE,
    TWEETS_DATA_FILE,
    PAPERS_DATA_FILE,
    config
)
from src.core.logger import get_logger
from src.core.models import Tweet, GitHubRepo, ResearchPaper, DailyIngestionBatch
from src.core.retry import retry_with_backoff
from .prompts import get_prompt_resumo_ia, get_prompt_github, get_prompt_papers, get_prompt_takeaway

logger = get_logger("ai_summarizer")

def _executar_chamada_openai(api_key: str, payload: dict) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["choices"][0]["message"]["content"]

def chamar_openai(api_key: str, payload_conteudo: str, prompt_sistema: str) -> str:
    logger.info("Chamando OpenAI API (gpt-6-luna) com retries automáticos...")
    payload = {
        "model": "gpt-6-luna",
        "messages": [
            {"role": "system", "content": "Você é um analista sênior de Inteligência Artificial e Engenharia de Software."},
            {"role": "user", "content": f"{prompt_sistema}\n\n{payload_conteudo}"}
        ]
    }
    return retry_with_backoff(
        lambda: _executar_chamada_openai(api_key, payload),
        max_retries=3,
        initial_delay=2.0,
        operation_name="OpenAI ChatCompletion (gpt-6-luna)"
    )

def _anexar_secao_github(relatorio_md: str, openai_key: str, repos: list[GitHubRepo] | None = None) -> str:
    if repos is None:
        if not GITHUB_DATA_FILE.exists():
            return relatorio_md
        try:
            with open(GITHUB_DATA_FILE, "r", encoding="utf-8") as f:
                repos = [GitHubRepo.from_dict(r) for r in json.load(f)]
        except Exception as e:
            logger.warning(f"Aviso ao carregar GitHub Trending do disco: {e}")
            return relatorio_md

    if not repos:
        return relatorio_md

    try:
        logger.info("Traduzindo repositórios do GitHub em Português com gpt-6-luna...")
        repos_json = json.dumps([r.to_dict() for r in repos], ensure_ascii=False, indent=2)
        payload_gh = {
            "model": "gpt-6-luna",
            "messages": [{"role": "user", "content": get_prompt_github(repos_json)}]
        }
        gh_markdown = retry_with_backoff(
            lambda: _executar_chamada_openai(openai_key, payload_gh),
            max_retries=3,
            initial_delay=2.0,
            operation_name="OpenAI Tradução GitHub Trending"
        ).strip()

        secao = ["\n\n---\n\n## 🔥 GitHub Trending: Repositórios de IA em Alta no Dia\n", gh_markdown]
        return relatorio_md + "\n".join(secao)
    except Exception as e:
        logger.warning(f"Aviso ao anexar GitHub Trending: {e}")
        return relatorio_md

def _anexar_secao_papers(relatorio_md: str, openai_key: str, papers: list[ResearchPaper] | None = None) -> str:
    if papers is None:
        if not PAPERS_DATA_FILE.exists():
            return relatorio_md
        try:
            with open(PAPERS_DATA_FILE, "r", encoding="utf-8") as f:
                papers = [ResearchPaper.from_dict(p) for p in json.load(f)]
        except Exception as e:
            logger.warning(f"Aviso ao carregar Papers do disco: {e}")
            return relatorio_md

    if not papers:
        return relatorio_md

    try:
        logger.info("Traduzindo e sintetizando Papers do Hugging Face com gpt-6-luna...")
        papers_json = json.dumps([p.to_dict() for p in papers], ensure_ascii=False, indent=2)
        payload_papers = {
            "model": "gpt-6-luna",
            "messages": [{"role": "user", "content": get_prompt_papers(papers_json)}]
        }
        papers_markdown = retry_with_backoff(
            lambda: _executar_chamada_openai(openai_key, payload_papers),
            max_retries=3,
            initial_delay=2.0,
            operation_name="OpenAI Síntese de Papers"
        ).strip()

        secao = ["\n\n---\n\n## 📄 Papers em Destaque: Pesquisa & Estado da Arte (Hugging Face / ArXiv)\n", papers_markdown]
        return relatorio_md + "\n".join(secao)
    except Exception as e:
        logger.warning(f"Aviso ao anexar Papers: {e}")
        return relatorio_md

def _anexar_secao_takeaway(relatorio_md: str, openai_key: str) -> str:
    try:
        logger.info("Sintetizando Takeaway Prático de Engenharia do Dia com gpt-6-luna...")
        payload_takeaway = {
            "model": "gpt-6-luna",
            "messages": [{"role": "user", "content": get_prompt_takeaway(relatorio_md)}]
        }
        takeaway_markdown = retry_with_backoff(
            lambda: _executar_chamada_openai(openai_key, payload_takeaway),
            max_retries=3,
            initial_delay=2.0,
            operation_name="OpenAI Síntese de Takeaway"
        ).strip()

        secao = ["\n\n---\n\n## 💡 Takeaway Prático de Engenharia do Dia\n", takeaway_markdown]
        return relatorio_md + "\n".join(secao)
    except Exception as e:
        logger.warning(f"Aviso ao anexar Takeaway: {e}")
        return relatorio_md

def remover_travessoes(md: str) -> str:
    """Higieniza o markdown substituindo travessões longos (' — ') por formatos naturais (dois-pontos, parênteses ou hífen)."""
    # 1. **Nome — Subtítulo:** -> **Nome (Subtítulo):**
    md = re.sub(r'\*\*([^*]+?)\s+—\s+([^*]+?):\*\*', r'**\1 (\2):**', md)
    md = re.sub(r'\*\*([^*]+?)\s+—\s+([^*]+?)\*\*', r'**\1 (\2)**', md)
    # 2. **[link](url)** — ⭐ ou 📄 -> **[link](url)** ⭐ / 📄
    md = re.sub(r'(\*\*\[[^\]]+\]\([^)]+\)\*\*)\s+—\s+', r'\1 ', md)
    # 3. Qualquer outro ' — ' solto -> substitui por ' - ' (hífen simples)
    md = re.sub(r'\s+—\s+', ' - ', md)
    md = md.replace('—', '-')
    return md

def gerar_resumo_ia(
    batch: DailyIngestionBatch | None = None,
    output_path: Path | None = None
) -> Path | None:
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    output_md = output_path if output_path is not None else (REPORTS_DIR / f"Resumo_IA_{hoje.strftime('%Y-%m-%d')}.md")

    logger.info("=" * 60)
    logger.info(f"Iniciando síntese inteligente com IA para {hoje.strftime('%d/%m/%Y')}...")
    logger.info("=" * 60)

    # Se nenhum lote em memória foi fornecido, carrega snapshot de dados do disco
    if batch is None:
        logger.info(f"Carregando snapshot de dados em disco a partir de: {DATA_DIR}")
        batch = DailyIngestionBatch.load_snapshot(DATA_DIR)

    if batch.is_empty():
        logger.error("❌ Nenhum dado disponível no lote ou snapshot (todas as fontes estão vazias).")
        return None

    tweets = batch.tweets
    if tweets:
        logger.info(f"Processando {len(tweets)} tweets em memória para síntese inteligente...")
        # Blindagem e higienização em tags XML
        formatted_tweets = []
        for i, t in enumerate(tweets, 1):
            links_str = " | ".join(t.external_links) if t.external_links else "Nenhum"
            formatted_tweets.append(
                f'<tweet_item id="{i}" author="{t.author_name} ({t.author_handle})" metrics="Likes: {t.likes}, Reposts: {t.reposts}">\n'
                f'  <content>{t.sanitized_text()}</content>\n'
                f'  <url>{t.url}</url>\n'
                f'  <external_links>{links_str}</external_links>\n'
                f'</tweet_item>'
            )

        tweets_xml = "<tweets_feed>\n" + "\n".join(formatted_tweets) + "\n</tweets_feed>"
        prompt_sistema = get_prompt_resumo_ia(hoje.strftime("%d/%m/%Y"), ontem.strftime("%d/%m/%Y"))

        try:
            relatorio_md = chamar_openai(config.OPENAI_API_KEY, tweets_xml, prompt_sistema)
        except Exception as e:
            logger.error(f"Falha ao chamar OpenAI API após retries: {e}")
            return None
    else:
        logger.warning("Nenhum tweet disponível no lote. Prosseguindo com síntese de GitHub Trending e Papers...")
        relatorio_md = (
            f"# Diário de Engenharia: IA & Coding Agents\n\n"
            f"*Edição de {hoje.strftime('%d/%m/%Y')}*\n\n"
            f"> ℹ️ *Nenhum post recente capturado no radar do X para este ciclo. "
            f"Apresentando os destaques de repositórios e papers científicos do dia.*"
        )

    # Limpeza de blocos de código
    relatorio_md = relatorio_md.strip()
    if relatorio_md.startswith("```markdown"):
        relatorio_md = relatorio_md[len("```markdown"):].strip()
    elif relatorio_md.startswith("```"):
        relatorio_md = relatorio_md[3:].strip()
    if relatorio_md.endswith("```"):
        relatorio_md = relatorio_md[:-3].strip()

    # Anexa GitHub Trending, Papers e Takeaway Prático a partir das entidades em memória
    relatorio_md = _anexar_secao_github(relatorio_md, config.OPENAI_API_KEY, repos=batch.repos)
    relatorio_md = _anexar_secao_papers(relatorio_md, config.OPENAI_API_KEY, papers=batch.papers)
    relatorio_md = _anexar_secao_takeaway(relatorio_md, config.OPENAI_API_KEY)

    # Higienização de pontuação: elimina travessões artificiais (' — ')
    relatorio_md = remover_travessoes(relatorio_md)

    with open(output_md, "w", encoding="utf-8") as f:
        f.write(relatorio_md)

    logger.info(f"Relatório gerado com sucesso em: {output_md}")
    return output_md

if __name__ == "__main__":
    gerar_resumo_ia()
