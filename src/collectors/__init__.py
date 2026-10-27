from .github import coletar_github_trending
from .twitter import coletar_tweets_vip
from .huggingface import coletar_papers_huggingface
from .base import IngestionSource, TwitterSource, GitHubSource, HuggingFaceSource
from .pipeline import IngestionPipeline

__all__ = [
    "coletar_github_trending",
    "coletar_tweets_vip",
    "coletar_papers_huggingface",
    "IngestionSource",
    "TwitterSource",
    "GitHubSource",
    "HuggingFaceSource",
    "IngestionPipeline",
]
