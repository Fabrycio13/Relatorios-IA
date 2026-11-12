import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class SourceStatus(str, Enum):
    """Status de execução de uma fonte de coleta de dados."""
    SUCCESS = "success"
    EMPTY = "empty"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class SourceCollectionResult(Generic[T]):
    """Estrutura imutável de resultado de coleta de dados de uma fonte."""
    source_name: str
    status: SourceStatus
    items: tuple[T, ...] = field(default_factory=tuple)
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    successful_operations: tuple[str, ...] = field(default_factory=tuple)
    failed_operations: tuple[str, ...] = field(default_factory=tuple)
    error_message: str | None = None
    rate_limited: bool = False

    def __post_init__(self) -> None:
        # Validação estrita do campo status
        if isinstance(self.status, str) and not isinstance(self.status, bool):
            try:
                object.__setattr__(self, "status", SourceStatus(self.status))
            except ValueError:
                raise ValueError(f"Invalid status: {self.status!r}. Must be a valid SourceStatus value.")
        elif not isinstance(self.status, SourceStatus):
            raise TypeError(f"status must be a SourceStatus instance, got {type(self.status).__name__}")

        # Normalização e validação das sequências de identificadores de operações
        def _normalize_ops(ops: Any, field_name: str) -> tuple[str, ...]:
            if isinstance(ops, (str, bytes)) or not hasattr(ops, "__iter__"):
                raise TypeError(f"{field_name} must be a sequence of strings, got {type(ops).__name__}")
            normalized = []
            for item in ops:
                if not isinstance(item, str) or isinstance(item, bool):
                    raise TypeError(f"All operations in {field_name} must be strings, got {type(item).__name__}")
                normalized.append(item)
            return tuple(normalized)

        succ_ops = _normalize_ops(self.successful_operations, "successful_operations")
        fail_ops = _normalize_ops(self.failed_operations, "failed_operations")
        object.__setattr__(self, "successful_operations", succ_ops)
        object.__setattr__(self, "failed_operations", fail_ops)

        # Conversão defensiva de itens para tupla nativa
        if not isinstance(self.items, tuple):
            try:
                object.__setattr__(self, "items", tuple(self.items))
            except TypeError:
                raise TypeError("items must be an iterable sequence")

        # Invariantes estritos de consistência de estado:
        if self.status == SourceStatus.SUCCESS:
            if len(self.items) == 0:
                raise ValueError("SUCCESS requires at least one item. Use EMPTY when no items are collected.")
            if len(self.successful_operations) == 0:
                raise ValueError("SUCCESS requires at least one successful operation.")
            if len(self.failed_operations) > 0:
                raise ValueError("SUCCESS cannot have failed operations. Use PARTIAL if failures occurred.")
            if self.error_message:
                raise ValueError("SUCCESS cannot have an error_message.")

        elif self.status == SourceStatus.EMPTY:
            if len(self.items) != 0:
                raise ValueError("EMPTY requires items to be empty.")
            if len(self.successful_operations) == 0:
                raise ValueError("EMPTY requires at least one successful operation.")
            if len(self.failed_operations) > 0:
                raise ValueError("EMPTY cannot have failed operations.")
            if self.error_message:
                raise ValueError("EMPTY cannot have an error_message.")

        elif self.status == SourceStatus.PARTIAL:
            if len(self.successful_operations) == 0:
                raise ValueError("PARTIAL requires at least one successful operation.")
            if len(self.failed_operations) == 0:
                raise ValueError("PARTIAL requires at least one failed operation.")
            if not self.error_message:
                raise ValueError("PARTIAL requires an error_message describing the partial failure.")

        elif self.status == SourceStatus.FAILED:
            if len(self.items) != 0:
                raise ValueError("FAILED cannot have items.")
            if len(self.successful_operations) > 0:
                raise ValueError("FAILED cannot have successful operations. Use PARTIAL if some operations succeeded.")
            if len(self.failed_operations) == 0:
                raise ValueError("FAILED requires at least one failed operation.")
            if not self.error_message:
                raise ValueError("FAILED requires an error_message.")

        elif self.status == SourceStatus.NOT_RUN:
            if len(self.items) != 0:
                raise ValueError("NOT_RUN cannot have items.")
            if len(self.successful_operations) > 0:
                raise ValueError("NOT_RUN cannot have successful operations.")
            if len(self.failed_operations) > 0:
                raise ValueError("NOT_RUN cannot have failed operations.")
            if self.error_message is not None:
                raise ValueError("NOT_RUN cannot have an error_message.")

    @property
    def has_usable_data(self) -> bool:
        return len(self.items) > 0 and self.status in (SourceStatus.SUCCESS, SourceStatus.PARTIAL)


@dataclass(frozen=True)
class Tweet:
    """Modelo de dados tipado para representar um post coletado no X (Twitter)."""
    author_name: str
    author_handle: str
    timestamp: str
    text: str
    url: str
    likes: str = "0"
    reposts: str = "0"
    replies: str = "0"
    views: str = "0"
    external_links: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.external_links, tuple):
            object.__setattr__(self, "external_links", tuple(self.external_links or ()))

    def sanitized_text(self) -> str:
        """Remove caracteres de controle invisíveis e normaliza espaços para segurança contra prompt injection."""
        if not self.text:
            return ""
        # Remove caracteres de controle ASCII e Unicode não imprimíveis
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', self.text)
        # Normaliza quebras de linha e múltiplos espaços
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        return cleaned.strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "author_name": self.author_name,
            "author_handle": self.author_handle,
            "timestamp": self.timestamp,
            "text": self.text,
            "url": self.url,
            "likes": self.likes,
            "reposts": self.reposts,
            "replies": self.replies,
            "views": self.views,
            "external_links": list(self.external_links),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tweet":
        return cls(
            author_name=str(data.get("author_name") or "Autor Desconhecido"),
            author_handle=str(data.get("author_handle") or "@desconhecido"),
            timestamp=str(data.get("timestamp") or ""),
            text=str(data.get("text") or ""),
            url=str(data.get("url") or ""),
            likes=str(data.get("likes") or "0"),
            reposts=str(data.get("reposts") or "0"),
            replies=str(data.get("replies") or "0"),
            views=str(data.get("views") or "0"),
            external_links=tuple(data.get("external_links") or ())
        )

@dataclass(frozen=True)
class GitHubRepo:
    """Modelo de dados tipado para representar um repositório em alta no GitHub."""
    name: str
    full_name: str
    stars: int
    description: str
    language: str
    url: str
    created_at: str = ""
    topics: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.topics, tuple):
            object.__setattr__(self, "topics", tuple(self.topics or ()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "stars": self.stars,
            "description": self.description,
            "language": self.language,
            "url": self.url,
            "created_at": self.created_at,
            "topics": list(self.topics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitHubRepo":
        return cls(
            name=str(data.get("name") or ""),
            full_name=str(data.get("full_name") or ""),
            stars=int(data.get("stars") or 0),
            description=str(data.get("description") or "Sem descrição disponível"),
            language=str(data.get("language") or "N/A"),
            url=str(data.get("url") or ""),
            created_at=str(data.get("created_at") or ""),
            topics=tuple(data.get("topics") or ())
        )

@dataclass(frozen=True)
class ResearchPaper:
    """Modelo de dados tipado para representar um artigo científico em alta (Hugging Face / ArXiv)."""
    title: str
    arxiv_id: str
    summary: str
    authors: tuple[str, ...] = field(default_factory=tuple)
    upvotes: int = 0
    url: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.authors, tuple):
            object.__setattr__(self, "authors", tuple(self.authors or ()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "arxiv_id": self.arxiv_id,
            "summary": self.summary,
            "authors": list(self.authors),
            "upvotes": self.upvotes,
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchPaper":
        return cls(
            title=str(data.get("title") or "Sem título"),
            arxiv_id=str(data.get("arxiv_id") or ""),
            summary=str(data.get("summary") or "Sem resumo disponível"),
            authors=tuple(data.get("authors") or ()),
            upvotes=int(data.get("upvotes") or 0),
            url=str(data.get("url") or f"https://huggingface.co/papers/{data.get('arxiv_id', '')}")
        )


SNAPSHOT_TWEETS_FILE = "tweets_coletados.json"
SNAPSHOT_GITHUB_FILE = "github_trending.json"
SNAPSHOT_PAPERS_FILE = "hf_papers.json"
SNAPSHOT_METADATA_FILE = "snapshot_metadata.json"


def _atomic_write_json(file_path: Path, data: Any) -> None:
    """Grava dados em formato JSON de maneira atômica utilizando arquivo temporário intermediário."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_name(f"{file_path.name}.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, file_path)


@dataclass
class DailyIngestionBatch:
    """Modelo de dados tipado para representar o lote unificado de ingestão diária."""
    tweets: list[Tweet] = field(default_factory=list)
    repos: list[GitHubRepo] = field(default_factory=list)
    papers: list[ResearchPaper] = field(default_factory=list)
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def is_empty(self) -> bool:
        """Retorna True se nenhuma das fontes coletou itens."""
        return len(self.tweets) == 0 and len(self.repos) == 0 and len(self.papers) == 0

    def to_dict(self) -> dict[str, Any]:
        """Serializa o lote e suas entidades filhas em um dicionário."""
        return {
            "tweets": [t.to_dict() for t in self.tweets],
            "repos": [r.to_dict() for r in self.repos],
            "papers": [p.to_dict() for p in self.papers],
            "collected_at": self.collected_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyIngestionBatch":
        """Reconstitui o lote tipado a partir de um dicionário."""
        return cls(
            tweets=[Tweet.from_dict(t) for t in data.get("tweets") or []],
            repos=[GitHubRepo.from_dict(r) for r in data.get("repos") or []],
            papers=[ResearchPaper.from_dict(p) for p in data.get("papers") or []],
            collected_at=str(data.get("collected_at") or datetime.now().isoformat()),
        )

    def save_snapshot(self, data_dir: Path | str, source: str | None = None) -> None:
        """
        Salva snapshot atômico dos arquivos JSON no diretório especificado.
        Se source for informado ('twitter'/'tweets', 'github'/'repos', 'papers'),
        atualiza exclusivamente o arquivo JSON e o metadado daquela fonte,
        preservando a integridade e estampa temporal dos demais arquivos em disco.
        """
        dir_path = Path(data_dir)
        dir_path.mkdir(parents=True, exist_ok=True)

        meta_file = dir_path / SNAPSHOT_METADATA_FILE
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        meta = loaded
            except Exception:
                meta = {}

        sources_meta = meta.get("sources") if isinstance(meta.get("sources"), dict) else {}

        if source in ("twitter", "tweets"):
            _atomic_write_json(dir_path / SNAPSHOT_TWEETS_FILE, [t.to_dict() for t in self.tweets])
            sources_meta["twitter"] = self.collected_at
            meta["sources"] = sources_meta
            _atomic_write_json(meta_file, meta)
        elif source in ("github", "repos"):
            _atomic_write_json(dir_path / SNAPSHOT_GITHUB_FILE, [r.to_dict() for r in self.repos])
            sources_meta["github"] = self.collected_at
            meta["sources"] = sources_meta
            _atomic_write_json(meta_file, meta)
        elif source in ("papers",):
            _atomic_write_json(dir_path / SNAPSHOT_PAPERS_FILE, [p.to_dict() for p in self.papers])
            sources_meta["papers"] = self.collected_at
            meta["sources"] = sources_meta
            _atomic_write_json(meta_file, meta)
        else:
            # Full snapshot (todas as fontes consolidadas)
            _atomic_write_json(dir_path / SNAPSHOT_TWEETS_FILE, [t.to_dict() for t in self.tweets])
            _atomic_write_json(dir_path / SNAPSHOT_GITHUB_FILE, [r.to_dict() for r in self.repos])
            _atomic_write_json(dir_path / SNAPSHOT_PAPERS_FILE, [p.to_dict() for p in self.papers])
            meta["collected_at"] = self.collected_at
            meta["sources"] = {
                "twitter": self.collected_at,
                "github": self.collected_at,
                "papers": self.collected_at,
            }
            _atomic_write_json(meta_file, meta)

    @classmethod
    def load_snapshot(cls, data_dir: Path | str) -> "DailyIngestionBatch":
        """Reconstitui o DailyIngestionBatch a partir dos arquivos JSON existentes no diretório."""
        dir_path = Path(data_dir)
        if not dir_path.exists():
            return cls()

        def _carregar_json_seguro(arquivo: Path) -> list[dict[str, Any]]:
            if not arquivo.exists():
                return []
            try:
                with open(arquivo, "r", encoding="utf-8") as f:
                    conteudo = json.load(f)
                    return conteudo if isinstance(conteudo, list) else []
            except Exception:
                return []

        tweets_raw = _carregar_json_seguro(dir_path / SNAPSHOT_TWEETS_FILE)
        repos_raw = _carregar_json_seguro(dir_path / SNAPSHOT_GITHUB_FILE)
        papers_raw = _carregar_json_seguro(dir_path / SNAPSHOT_PAPERS_FILE)

        collected_at = ""
        meta_file = dir_path / SNAPSHOT_METADATA_FILE
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    collected_at = str(meta.get("collected_at") or "")
            except Exception:
                pass

        if not collected_at:
            mtimes = [
                p.stat().st_mtime
                for p in [dir_path / SNAPSHOT_TWEETS_FILE, dir_path / SNAPSHOT_GITHUB_FILE, dir_path / SNAPSHOT_PAPERS_FILE]
                if p.exists()
            ]
            if mtimes:
                collected_at = datetime.fromtimestamp(max(mtimes)).isoformat()
            else:
                collected_at = datetime.now().isoformat()

        return cls(
            tweets=[Tweet.from_dict(t) for t in tweets_raw],
            repos=[GitHubRepo.from_dict(r) for r in repos_raw],
            papers=[ResearchPaper.from_dict(p) for p in papers_raw],
            collected_at=collected_at,
        )

