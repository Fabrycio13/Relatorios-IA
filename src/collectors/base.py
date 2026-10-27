from typing import Protocol, Any, runtime_checkable
from src.core.logger import get_logger
from src.core.models import Tweet, GitHubRepo, ResearchPaper
from src.collectors.twitter import coletar_tweets_vip
from src.collectors.github import coletar_github_trending
from src.collectors.huggingface import coletar_papers_huggingface

logger = get_logger("collectors.base")


@runtime_checkable
class IngestionSource(Protocol):
    """Protocolo definindo a interface padrão para qualquer fonte de dados do relatório."""
    name: str
    target_field: str

    def collect(self) -> list[Any]:
        """Executa a coleta da fonte e retorna a lista de entidades de domínio correspondente."""
        ...


class TwitterSource:
    """Adaptador de coleta de posts VIP no X / Twitter via Playwright."""
    name: str = "twitter"
    target_field: str = "tweets"

    def __init__(self, headless: bool = True):
        self.headless = headless

    def collect(self) -> list[Tweet]:
        try:
            return coletar_tweets_vip(headless=self.headless) or []
        except Exception as e:
            logger.warning(f"Erro ao coletar dados do Twitter: {e}")
            return []


class GitHubSource:
    """Adaptador de coleta de repositórios em alta no GitHub via API REST."""
    name: str = "github"
    target_field: str = "repos"

    def __init__(self, dias_atras: int = 7, limite_top: int = 6):
        self.dias_atras = dias_atras
        self.limite_top = limite_top

    def collect(self) -> list[GitHubRepo]:
        try:
            return coletar_github_trending(dias_atras=self.dias_atras, limite_top=self.limite_top) or []
        except Exception as e:
            logger.warning(f"Erro ao coletar dados do GitHub Trending: {e}")
            return []


class HuggingFaceSource:
    """Adaptador de coleta de artigos científicos em alta no Hugging Face / ArXiv."""
    name: str = "papers"
    target_field: str = "papers"

    def __init__(self, limite_top: int = 3):
        self.limite_top = limite_top

    def collect(self) -> list[ResearchPaper]:
        try:
            return coletar_papers_huggingface(limite_top=self.limite_top) or []
        except Exception as e:
            logger.warning(f"Erro ao coletar papers do Hugging Face: {e}")
            return []
