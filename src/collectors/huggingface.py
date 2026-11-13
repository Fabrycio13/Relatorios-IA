import json
import urllib.request
from src.core.logger import get_logger
from src.core.models import ResearchPaper, SourceCollectionResult, SourceStatus
from src.core.retry import retry_with_backoff

logger = get_logger("huggingface_collector")

def _consultar_api_daily_papers() -> list[dict]:
    url = "https://huggingface.co/api/daily_papers"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def coletar_papers_huggingface(limite_top: int = 3) -> SourceCollectionResult[ResearchPaper]:
    """
    Coleta os artigos científicos (papers) de IA mais votados do dia no Hugging Face Daily Papers.
    Traz os papers mais relevantes e discutidos pela comunidade global de pesquisa.
    Retorna resultado puro em memória (SourceCollectionResult) sem persistência em disco.
    """
    logger.info("=" * 60)
    logger.info(f"Coletando Top {limite_top} Papers em Destaque no Hugging Face...")
    logger.info("=" * 60)

    try:
        dados_brutos = retry_with_backoff(
            _consultar_api_daily_papers,
            max_retries=3,
            initial_delay=2.0,
            operation_name="Hugging Face Daily Papers API"
        )
    except Exception as e:
        logger.warning(f"Não foi possível obter papers do Hugging Face após retries: {e}")
        return SourceCollectionResult(
            source_name="papers",
            status=SourceStatus.FAILED,
            items=(),
            successful_operations=(),
            failed_operations=("hf_daily_papers",),
            error_message=str(e),
        )

    papers: list[ResearchPaper] = []

    for item in dados_brutos:
        paper_info = item.get("paper", {})
        arxiv_id = paper_info.get("id")
        title = paper_info.get("title")
        summary = paper_info.get("summary", "")

        if not arxiv_id or not title:
            continue

        authors = [a.get("name", "") for a in paper_info.get("authors", []) if a.get("name")]
        upvotes = item.get("numComments", 0) + item.get("mediaCount", 0)

        paper_obj = ResearchPaper(
            title=title.strip(),
            arxiv_id=arxiv_id.strip(),
            summary=summary.strip(),
            authors=tuple(authors[:4]),
            upvotes=upvotes,
            url=f"https://huggingface.co/papers/{arxiv_id.strip()}"
        )
        papers.append(paper_obj)

        if len(papers) >= limite_top:
            break

    logger.info(f"Total de papers coletados: {len(papers)}")
    for p in papers:
        logger.info(f"  * [{p.arxiv_id}] {p.title}")

    items_tuple = tuple(papers)
    status = SourceStatus.SUCCESS if len(items_tuple) > 0 else SourceStatus.EMPTY

    return SourceCollectionResult(
        source_name="papers",
        status=status,
        items=items_tuple,
        successful_operations=("hf_daily_papers",),
        failed_operations=(),
    )

if __name__ == "__main__":
    coletar_papers_huggingface()
