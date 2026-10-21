import re
from dataclasses import dataclass, field, asdict
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
