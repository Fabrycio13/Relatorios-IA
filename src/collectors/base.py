from typing import Protocol, Any, runtime_checkable
from src.core.logger import get_logger
from src.core.models import (
    Tweet,
    GitHubRepo,
    ResearchPaper,
    SourceCollectionResult,
    SourceStatus,
)
from src.collectors.twitter import coletar_tweets_vip
from src.collectors.github import coletar_github_trending
from src.collectors.huggingface import coletar_papers_huggingface

logger = get_logger("collectors.base")


@runtime_checkable
class IngestionSource(Protocol):
    """Protocolo definindo a interface padrão para qualquer fonte de dados do relatório."""
    name: str
    target_field: str

    def collect(self) -> SourceCollectionResult[Any]:
        """Executa a coleta da fonte e retorna o resultado estruturado correspondente."""
        ...


class TwitterSource:
    """Adaptador de coleta de posts VIP no X / Twitter via Playwright."""
    name: str = "twitter"
    target_field: str = "tweets"

    def __init__(self, headless: bool = True):
        self.headless = headless

    def collect(self) -> SourceCollectionResult[Tweet]:
        try:
            res = coletar_tweets_vip(headless=self.headless)
            if isinstance(res, SourceCollectionResult):
                return res
            raise TypeError(
                f"Retorno inválido de coletar_tweets_vip: esperado SourceCollectionResult, recebido {type(res).__name__}"
            )
        except Exception as e:
            logger.warning(f"Erro ao coletar dados do Twitter: {e}")
            return SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.FAILED,
                items=(),
                successful_operations=(),
                failed_operations=("scrape",),
                error_message=str(e),
            )


class GitHubSource:
    """Adaptador de coleta de repositórios em alta no GitHub via API REST."""
    name: str = "github"
    target_field: str = "repos"

    def __init__(self, dias_atras: int = 7, limite_top: int = 6):
        self.dias_atras = dias_atras
        self.limite_top = limite_top

    def collect(self) -> SourceCollectionResult[GitHubRepo]:
        try:
            res = coletar_github_trending(dias_atras=self.dias_atras, limite_top=self.limite_top)
            if isinstance(res, SourceCollectionResult):
                return res
            raise TypeError(
                f"Retorno inválido de coletar_github_trending: esperado SourceCollectionResult, recebido {type(res).__name__}"
            )
        except Exception as e:
            logger.warning(f"Erro ao coletar dados do GitHub Trending: {e}")
            return SourceCollectionResult(
                source_name="github",
                status=SourceStatus.FAILED,
                items=(),
                successful_operations=(),
                failed_operations=("search",),
                error_message=str(e),
            )


class HuggingFaceSource:
    """Adaptador de coleta de artigos científicos em alta no Hugging Face / ArXiv."""
    name: str = "papers"
    target_field: str = "papers"

    def __init__(self, limite_top: int = 3):
        self.limite_top = limite_top

    def collect(self) -> SourceCollectionResult[ResearchPaper]:
        try:
            res = coletar_papers_huggingface(limite_top=self.limite_top)
            if isinstance(res, SourceCollectionResult):
                return res
            raise TypeError(
                f"Retorno inválido de coletar_papers_huggingface: esperado SourceCollectionResult, recebido {type(res).__name__}"
            )
        except Exception as e:
            logger.warning(f"Erro ao coletar papers do Hugging Face: {e}")
            return SourceCollectionResult(
                source_name="papers",
                status=SourceStatus.FAILED,
                items=(),
                successful_operations=(),
                failed_operations=("daily_papers",),
                error_message=str(e),
            )
