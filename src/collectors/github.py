import json
import subprocess
from datetime import datetime, timedelta
from src.core.config import GITHUB_DATA_FILE
from src.core.logger import get_logger

logger = get_logger("github_collector")

def coletar_github_trending(dias_atras: int = 7, limite_top: int = 6):
    """
    Coleta repositórios de IA em alta no GitHub criados recentemente nos tópicos
    essenciais de engenharia (llm, ai-agent, mcp, rag).
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

    repos_map = {}

    for q in queries:
        url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=6"
        cmd = ["curl.exe", "-s", "-H", "User-Agent: Mozilla/5.0", url]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            if res.returncode == 0 and res.stdout:
                texto_json = res.stdout.decode("utf-8", errors="replace")
                data = json.loads(texto_json)
                for item in data.get("items", []):
                    full_name = item.get("full_name")
                    if full_name and full_name not in repos_map:
                        repos_map[full_name] = {
                            "name": item.get("name"),
                            "full_name": full_name,
                            "stars": item.get("stargazers_count", 0),
                            "description": item.get("description") or "Sem descrição disponível",
                            "language": item.get("language") or "N/A",
                            "url": item.get("html_url"),
                            "created_at": item.get("created_at"),
                            "topics": item.get("topics", [])
                        }
        except Exception as e:
            logger.warning(f"Aviso ao consultar GitHub ({q}): {e}")

    # Ordena pelo número de estrelas e pega os mais quentes
    trending_repos = sorted(repos_map.values(), key=lambda x: x["stars"], reverse=True)[:limite_top]

    logger.info(f"Total de repositórios em alta encontrados: {len(trending_repos)}")
    for r in trending_repos:
        logger.info(f"  * {r['full_name']} (Stars: {r['stars']}) - {r['language']}")

    with open(GITHUB_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(trending_repos, f, ensure_ascii=False, indent=2)

    logger.info(f"Dados salvos com sucesso em: {GITHUB_DATA_FILE}")
    return trending_repos

if __name__ == "__main__":
    coletar_github_trending()
