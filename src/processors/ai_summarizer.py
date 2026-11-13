import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.core.config import (
    DATA_DIR,
    REPORTS_DIR,
    config
)
from src.core.logger import get_logger
from src.core.models import Tweet, GitHubRepo, ResearchPaper, DailyIngestionBatch, obter_metadados_fonte
from src.core.manifest import is_source_fresh, is_execucao_em_andamento
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


def _avaliar_frescor_e_qualidade(
    source_name: str,
    items: list[Any],
    sources_meta: dict[str, Any],
    collection_status: Any = None,
) -> tuple[bool, bool, bool]:
    """Avalia a elegibilidade editorial de uma fonte.

    Retorna (is_usable, is_historical, is_stale):
    - is_usable: dados podem ser sintetizados
    - is_historical: dados classificados como legacy_unverified OU consumidos em fallback histórico após falha
    - is_stale: dados com timestamp ultrapassando a janela de 36 horas
    """
    if not items:
        return False, False, False

    info = obter_metadados_fonte(sources_meta, source_name)
    quality = info.get("quality", "verified")
    updated_at = info.get("updated_at")

    is_legacy = (quality == "legacy_unverified")
    status_str = getattr(collection_status, "value", str(collection_status or "")).lower()
    is_failed_collection = (status_str == "failed")
    is_historical = is_legacy or is_failed_collection

    if updated_at:
        fresh = is_source_fresh(updated_at, max_hours=36.0)
        is_stale = not fresh
    else:
        is_stale = False

    if is_stale:
        return False, is_historical, True

    if is_legacy:
        logger.warning(f"[WARNING] Fonte {source_name} consumida sob regime de dados legados não comprovados (legacy_unverified).")
    elif is_failed_collection:
        logger.warning(f"[WARNING] Fonte {source_name} consumida sob regime de contingência com dados históricos anteriores.")

    return True, is_historical, False


def _anexar_secao_github(
    relatorio_md: str,
    openai_key: str,
    repos: list[GitHubRepo] | None = None,
    is_usable: bool = True,
    is_legacy: bool = False,
    is_stale: bool = False,
) -> str:
    repos_list = repos or []
    titulo = "\n\n---\n\n## 🔥 GitHub Trending: Repositórios de IA em Alta no Dia\n"

    if not repos_list or not is_usable:
        aviso = (
            f"{titulo}\n> ⚠️ **Aviso Editorial:** A seção de repositórios em alta do GitHub não pôde ser "
            f"atualizada nesta edição devido a limitações operacionais da fonte.\n"
        )
        return relatorio_md + aviso

    try:
        logger.info("Traduzindo repositórios do GitHub em Português com gpt-6-luna...")
        repos_json = json.dumps([r.to_dict() for r in repos_list], ensure_ascii=False, indent=2)
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

        nota_legacy = ""
        if is_legacy:
            nota_legacy = (
                "\n> ⚠️ **Aviso Editorial:** Esta seção apresenta o último estado histórico coletado "
                "anteriormente, não refletindo atualizações comprovadas de hoje.\n\n"
            )

        secao = [titulo, nota_legacy, gh_markdown]
        return relatorio_md + "".join(secao)
    except Exception as e:
        logger.warning(f"Aviso ao anexar GitHub Trending: {e}")
        return relatorio_md


def _anexar_secao_papers(
    relatorio_md: str,
    openai_key: str,
    papers: list[ResearchPaper] | None = None,
    is_usable: bool = True,
    is_legacy: bool = False,
    is_stale: bool = False,
) -> str:
    papers_list = papers or []
    titulo = "\n\n---\n\n## 📄 Papers em Destaque: Pesquisa & Estado da Arte (Hugging Face / ArXiv)\n"

    if not papers_list or not is_usable:
        aviso = (
            f"{titulo}\n> ⚠️ **Aviso Editorial:** A seção de papers científicos não pôde ser "
            f"atualizada nesta edição devido a limitações operacionais da fonte.\n"
        )
        return relatorio_md + aviso

    try:
        logger.info("Traduzindo e sintetizando Papers do Hugging Face com gpt-6-luna...")
        papers_json = json.dumps([p.to_dict() for p in papers_list], ensure_ascii=False, indent=2)
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

        nota_legacy = ""
        if is_legacy:
            nota_legacy = (
                "\n> ⚠️ **Aviso Editorial:** Esta seção apresenta o último estado histórico coletado "
                "anteriormente, não refletindo atualizações comprovadas de hoje.\n\n"
            )

        secao = [titulo, nota_legacy, papers_markdown]
        return relatorio_md + "".join(secao)
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

        secao = ["\n\n---\n\n## 💡 Dica do Autor: O que levar para o código hoje\n", takeaway_markdown]
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


def montar_payload_tweets_xml(tweets: list[Tweet]) -> str:
    """Monta o payload XML estruturado e blindado para envio dos tweets ao modelo de IA."""
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
    return "<tweets_feed>\n" + "\n".join(formatted_tweets) + "\n</tweets_feed>"


def gerar_resumo_ia(
    batch: DailyIngestionBatch | None = None,
    output_path: Path | None = None,
    data_dir: Path | None = None,
) -> Path | None:
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    output_md = output_path if output_path is not None else (REPORTS_DIR / f"Resumo_IA_{hoje.strftime('%Y-%m-%d')}.md")
    dir_path = Path(data_dir or DATA_DIR)

    logger.info("=" * 60)
    logger.info(f"Iniciando síntese inteligente com IA para {hoje.strftime('%d/%m/%Y')}...")
    logger.info("=" * 60)

    # Se nenhum lote em memória foi fornecido, carrega snapshot de dados do disco
    if batch is None:
        logger.info(f"Carregando snapshot de dados em disco a partir de: {dir_path}")
        batch = DailyIngestionBatch.load_snapshot(dir_path)

    # Proibição de Consumo de Execução Pendente: se last_attempt for running, aborta dirty read
    sources_meta = dict(batch.sources_metadata) if batch.sources_metadata else {}
    if not sources_meta and (dir_path / "snapshot_metadata.json").exists():
        try:
            with open(dir_path / "snapshot_metadata.json", "r", encoding="utf-8") as f:
                meta_json = json.load(f)
                if is_execucao_em_andamento(meta_json.get("last_attempt", {}), check_liveness=True):
                    logger.warning("Execução em andamento ('running') detectada no disco. Dirty reads proibidos.")
                    return None
                sources_meta = meta_json.get("sources") or {}
        except Exception:
            pass

    # Avaliação de frescor e qualidade por fonte (considerando status da execução atual se presente)
    res_tw = batch.results.get("twitter") if hasattr(batch, "results") and batch.results else None
    res_gh = batch.results.get("github") if hasattr(batch, "results") and batch.results else None
    res_hf = batch.results.get("papers") if hasattr(batch, "results") and batch.results else None

    tw_usable, tw_legacy, tw_stale = _avaliar_frescor_e_qualidade(
        "twitter", batch.tweets, sources_meta, collection_status=res_tw.status if res_tw else None
    )
    gh_usable, gh_legacy, gh_stale = _avaliar_frescor_e_qualidade(
        "github", batch.repos, sources_meta, collection_status=res_gh.status if res_gh else None
    )
    hf_usable, hf_legacy, hf_stale = _avaliar_frescor_e_qualidade(
        "papers", batch.papers, sources_meta, collection_status=res_hf.status if res_hf else None
    )

    # Se nenhuma fonte contiver dados elegíveis (frescos ou de contingência), não gera relatório vazio/falso
    if not (tw_usable or gh_usable or hf_usable):
        logger.error("❌ Nenhuma fonte possui dados elegíveis frescos ou de contingência para síntese.")
        return None

    relatorio_md = ""
    if tw_usable:
        logger.info(f"Processando {len(batch.tweets)} tweets em memória para síntese inteligente...")
        tweets_xml = montar_payload_tweets_xml(batch.tweets)
        prompt_sistema = get_prompt_resumo_ia(hoje.strftime("%d/%m/%Y"), ontem.strftime("%d/%m/%Y"))

        try:
            relatorio_md = chamar_openai(config.OPENAI_API_KEY, tweets_xml, prompt_sistema)
            if tw_legacy:
                nota_legacy = (
                    "> ⚠️ **Aviso Editorial:** Esta seção apresenta o último estado histórico coletado "
                    "anteriormente, não refletindo atualizações comprovadas de hoje.\n\n"
                )
                relatorio_md = f"# Diário de Engenharia: IA & Coding Agents\n\n*Edição de {hoje.strftime('%d/%m/%Y')}*\n\n{nota_legacy}" + relatorio_md
        except Exception as e:
            logger.error(f"Falha ao chamar OpenAI API após retries: {e}")
            return None
    else:
        logger.warning("Nenhum tweet fresco disponível no lote. Aplicando degradação graciosa e prosseguindo...")
        relatorio_md = (
            f"# Diário de Engenharia: IA & Coding Agents\n\n"
            f"*Edição de {hoje.strftime('%d/%m/%Y')}*\n\n"
            f"> ⚠️ **Aviso Editorial:** A seção de tópicos do X/Twitter não pôde ser atualizada nesta edição "
            f"devido a limitações operacionais da fonte. Nenhum post recente capturado no radar do X para este ciclo. "
            f"Apresentando os destaques de repositórios e papers científicos do dia.\n"
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
    relatorio_md = _anexar_secao_github(
        relatorio_md, config.OPENAI_API_KEY, repos=batch.repos, is_usable=gh_usable, is_legacy=gh_legacy, is_stale=gh_stale
    )
    relatorio_md = _anexar_secao_papers(
        relatorio_md, config.OPENAI_API_KEY, papers=batch.papers, is_usable=hf_usable, is_legacy=hf_legacy, is_stale=hf_stale
    )
    relatorio_md = _anexar_secao_takeaway(relatorio_md, config.OPENAI_API_KEY)

    # Higienização de pontuação: elimina travessões artificiais (' — ')
    relatorio_md = remover_travessoes(relatorio_md)

    output_md.parent.mkdir(parents=True, exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(relatorio_md)

    logger.info(f"Relatório gerado com sucesso em: {output_md}")
    return output_md


if __name__ == "__main__":
    gerar_resumo_ia()
