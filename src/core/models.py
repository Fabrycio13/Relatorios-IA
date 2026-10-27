import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

@dataclass
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
    external_links: list[str] = field(default_factory=list)

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
        return asdict(self)

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
            external_links=list(data.get("external_links") or [])
        )

@dataclass
class GitHubRepo:
    """Modelo de dados tipado para representar um repositório em alta no GitHub."""
    name: str
    full_name: str
    stars: int
    description: str
    language: str
    url: str
    created_at: str = ""
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

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
            topics=list(data.get("topics") or [])
        )

@dataclass
class ResearchPaper:
    """Modelo de dados tipado para representar um artigo científico em alta (Hugging Face / ArXiv)."""
    title: str
    arxiv_id: str
    summary: str
    authors: list[str]
    upvotes: int
    url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchPaper":
        return cls(
            title=str(data.get("title") or "Sem título"),
            arxiv_id=str(data.get("arxiv_id") or ""),
            summary=str(data.get("summary") or "Sem resumo disponível"),
            authors=list(data.get("authors") or []),
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

