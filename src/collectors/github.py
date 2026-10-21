import json
import urllib.request
from datetime import datetime, timedelta
from src.core.config import GITHUB_DATA_FILE
from src.core.logger import get_logger
from src.core.models import GitHubRepo
from src.core.retry import retry_with_backoff

logger = get_logger("github_collector")

def _consultar_api_github(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))

def coletar_github_trending(dias_atras: int = 7, limite_top: int = 6) -> list[GitHubRepo]:
    """
    Coleta repositórios de IA em alta no GitHub criados recentemente nos tópicos
    essenciais de engenharia (llm, ai-agent, mcp, rag) com retries inteligentes.
    """
    logger.info("=" * 60)
    logger.info("Coletando Repositórios em Alta de IA no GitHub (Últimos 7 dias)...")
    logger.info("=" * 60)

    data_limite = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y-%m-%d")

    queries = [
        f"topic:llm+created:>{data_limite}",
        f"topic:ai-agent+created:>{data_limite}",
        f"topic:mcp+created:>{data_limite}",
        f"topic:rag+created:>{data_limite}"
    ]

    repos_map: dict[str, GitHubRepo] = {}

    for q in queries:
        url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=6"
        try:
            data = retry_with_backoff(
                lambda: _consultar_api_github(url),
                max_retries=3,
                initial_delay=2.0,
                operation_name=f"Consulta GitHub Search ({q})"
            )
            for item in data.get("items", []):
                full_name = item.get("full_name")
                if full_name and full_name not in repos_map:
                    repo_obj = GitHubRepo(
                        name=str(item.get("name") or ""),
                        full_name=full_name,
                        stars=int(item.get("stargazers_count") or 0),
                        description=str(item.get("description") or "Sem descrição disponível"),
                        language=str(item.get("language") or "N/A"),
                        url=str(item.get("html_url") or ""),
                        created_at=str(item.get("created_at") or ""),
                        topics=list(item.get("topics") or [])
                    )
                    repos_map[full_name] = repo_obj
        except Exception as e:
            logger.warning(f"Aviso: Não foi possível obter repositórios para '{q}' após retries: {e}")

    # Ordena pelo número de estrelas e pega os mais quentes
    trending_repos = sorted(repos_map.values(), key=lambda x: x.stars, reverse=True)[:limite_top]

    logger.info(f"Total de repositórios em alta encontrados: {len(trending_repos)}")
    for r in trending_repos:
        logger.info(f"  * {r.full_name} (Stars: {r.stars}) - {r.language}")

    # Salva em JSON serializando as Dataclasses
    with open(GITHUB_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in trending_repos], f, ensure_ascii=False, indent=2)

    logger.info(f"Dados salvos com sucesso em: {GITHUB_DATA_FILE}")
    return trending_repos

if __name__ == "__main__":
    coletar_github_trending()
