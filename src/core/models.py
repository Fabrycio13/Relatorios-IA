import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

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


from src.core.lock import adquirir_trava_snapshot, _fsync_dir, mover_para_quarentena

SNAPSHOT_TWEETS_FILE = "tweets_coletados.json"
SNAPSHOT_GITHUB_FILE = "github_trending.json"
SNAPSHOT_PAPERS_FILE = "hf_papers.json"
SNAPSHOT_METADATA_FILE = "snapshot_metadata.json"

SNAPSHOT_PREFIXES = ("tweets_coletados", "github_trending", "hf_papers", "snapshot_metadata")

CANONICAL_SOURCES = {"twitter", "github", "papers"}
SOURCE_ALIASES_MAP: dict[str, str] = {
    "twitter": "twitter",
    "tweets": "twitter",
    "github": "github",
    "repos": "github",
    "github_trending": "github",
    "papers": "papers",
    "hf_papers": "papers",
}

SOURCE_FILE_MAP: dict[str, str] = {
    "twitter": SNAPSHOT_TWEETS_FILE,
    "github": SNAPSHOT_GITHUB_FILE,
    "papers": SNAPSHOT_PAPERS_FILE,
}


def obter_metadados_fonte(sources_meta: dict[str, Any], source_name: str) -> dict[str, Any]:
    """Obtém o dicionário de metadados da fonte resolvendo nomes canônicos e aliases.

    Suporta busca direta, busca pelo nome canônico e busca reversa através de aliases:
    - 'github' <-> 'github_trending', 'repos'
    - 'papers' <-> 'hf_papers'
    - 'twitter' <-> 'tweets'
    """
    if not isinstance(sources_meta, dict) or not source_name:
        return {}

    # 1. Correspondência exata direta
    if source_name in sources_meta and isinstance(sources_meta[source_name], dict):
        return sources_meta[source_name]

    # 2. Resolução via canonical
    norm_source = source_name.lower().removeprefix("collect-").strip()
    canonical = SOURCE_ALIASES_MAP.get(norm_source, norm_source)

    if canonical in sources_meta and isinstance(sources_meta[canonical], dict):
        return sources_meta[canonical]

    # 3. Busca reversa por equivalência canônica
    for key, val in sources_meta.items():
        if not isinstance(val, dict):
            continue
        norm_key = key.lower().removeprefix("collect-").strip()
        if SOURCE_ALIASES_MAP.get(norm_key, norm_key) == canonical:
            return val

    return {}


def _carregar_e_validar_manifesto(data_dir: Path, quarantine_dir: Path) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Carrega o manifesto validando schema v2 ou migrando v1; quarentena arquivos inválidos.

    Retorna:
        (meta_ativo, meta_prev, is_compromised)
        - meta_ativo: metadados válidos ativos (ou promovidos do .prev)
        - meta_prev: metadados válidos do .prev (se existirem)
        - is_compromised: True se arquivos de manifesto existiam mas foram invalidados/quarentenados
    """
    from src.core.manifest import (
        is_manifesto_v1,
        migrar_manifesto_v1_para_v2,
        validar_schema_manifesto,
    )

    meta_file = data_dir / SNAPSHOT_METADATA_FILE
    prev_meta = data_dir / f"{SNAPSHOT_METADATA_FILE}.prev"

    def _tentar_validar(fpath: Path) -> tuple[bool, dict[str, Any]]:
        if not fpath.exists():
            return False, {}
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = json.load(f)
            if not isinstance(content, dict):
                return False, {}
            if is_manifesto_v1(content):
                migrated = migrar_manifesto_v1_para_v2(content, data_dir=data_dir)
                if validar_schema_manifesto(migrated):
                    return True, migrated
                return False, {}
            elif validar_schema_manifesto(content):
                return True, content
            return False, {}
        except Exception:
            return False, {}

    had_meta_file = meta_file.exists()
    had_prev_meta = prev_meta.exists()

    if not had_meta_file and not had_prev_meta:
        return {}, {}, False

    is_meta_valid, meta = _tentar_validar(meta_file)
    is_prev_valid, prev_meta_content = _tentar_validar(prev_meta)

    if is_meta_valid:
        return meta, (prev_meta_content if is_prev_valid else {}), False

    # meta_file existia mas era inválido/corrompido
    if had_meta_file:
        mover_para_quarentena(meta_file, quarantine_dir)

    if is_prev_valid:
        os.replace(prev_meta, meta_file)
        _fsync_dir(data_dir)
        return prev_meta_content, {}, False
    else:
        if had_prev_meta and prev_meta.exists():
            mover_para_quarentena(prev_meta, quarantine_dir)
        return {}, {}, True


def _validar_arquivo_dados(
    fpath: Path,
    expected_hashes: set[str | None],
    quality: str | None,
    tem_meta: bool,
) -> tuple[bool, list[dict[str, Any]]]:
    """Valida a integridade física e criptográfica de um arquivo de snapshot (ativo ou .prev)."""
    from src.core.manifest import _calcular_sha256_arquivo, HEX_64_PATTERN

    if not fpath.exists():
        return False, []
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        if not isinstance(parsed, list):
            return False, []

        # Se a fonte afirma ser verified, o hash SHA-256 é estritamente obrigatório e deve bater
        if quality == "verified":
            valid_hashes = {h for h in expected_hashes if h and isinstance(h, str) and HEX_64_PATTERN.match(h)}
            if not valid_hashes:
                return False, []
            actual_sha = _calcular_sha256_arquivo(fpath)
            if actual_sha not in valid_hashes:
                return False, []
            return True, parsed

        # Se temos hash esperado em outras qualidades (ex: recovered)
        valid_hashes = {h for h in expected_hashes if h and isinstance(h, str) and HEX_64_PATTERN.match(h)}
        if valid_hashes:
            actual_sha = _calcular_sha256_arquivo(fpath)
            if actual_sha not in valid_hashes:
                return False, []
            return True, parsed

        # Fontes legadas sem verificação estrita de hash (legacy_unverified, não registradas ou snapshot sem manifesto)
        if quality in ("legacy_unverified", None) or not tem_meta:
            return True, parsed

        return False, []
    except Exception:
        return False, []


def _atomic_backup_prev(active_path: Path, data_dir: Path) -> None:
    """Gera cópia atômica de backup (.prev) do arquivo ativo se ele existir e for válido."""
    if not active_path.exists():
        return
    # Valida se é JSON antes de fazer backup para não promover arquivos corrompidos
    try:
        with open(active_path, "rb") as f:
            content = f.read()
        json.loads(content.decode("utf-8"))
    except Exception:
        return

    pid = os.getpid()
    prev_tmp = data_dir / f"{active_path.name}.prev.tmp.{pid}"
    prev_final = data_dir / f"{active_path.name}.prev"

    with open(prev_tmp, "wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())

    os.replace(prev_tmp, prev_final)
    _fsync_dir(data_dir)


def _atomic_write_snapshot_json(file_path: Path, data: Any, data_dir: Path) -> None:
    """Grava dados em formato JSON com durabilidade estrita (.tmp.<pid> + fsync + replace + fsync_dir)."""
    pid = os.getpid()
    tmp_path = data_dir / f"{file_path.name}.tmp.{pid}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, file_path)
    _fsync_dir(data_dir)


def _reconciliar_arquivos_preflight(data_dir: Path) -> None:
    """Valida integridade física e hash dos arquivos ativos e .prev, recuperando ou isolando em quarentena."""
    from src.core.manifest import _calcular_sha256_arquivo

    quarantine_dir = data_dir / "quarantine"

    # 1. Reconciliação do manifesto com validação estrita de schema v2
    meta, prev_meta, _ = _carregar_e_validar_manifesto(data_dir, quarantine_dir)
    sources_meta = meta.get("sources", {}) if isinstance(meta.get("sources"), dict) else {}
    prev_sources_meta = prev_meta.get("sources", {}) if isinstance(prev_meta.get("sources"), dict) else {}
    meta_modificado = False

    # 2. Reconciliação dos arquivos de dados
    for canonical_src, fname in (
        ("twitter", SNAPSHOT_TWEETS_FILE),
        ("github", SNAPSHOT_GITHUB_FILE),
        ("papers", SNAPSHOT_PAPERS_FILE),
    ):
        active_path = data_dir / fname
        prev_path = data_dir / f"{fname}.prev"

        src_info = sources_meta.get(canonical_src) or sources_meta.get(fname.removesuffix(".json")) or {}
        prev_src_info = prev_sources_meta.get(canonical_src) or prev_sources_meta.get(fname.removesuffix(".json")) or {}

        active_hashes = {src_info.get("sha256")}
        prev_hashes = {src_info.get("sha256"), prev_src_info.get("sha256")}
        quality = src_info.get("quality") or prev_src_info.get("quality")

        is_active_valid, _ = _validar_arquivo_dados(active_path, active_hashes, quality, bool(meta))

        # Se o ativo existe mas não é válido (corrompido ou com divergência de hash em relação ao manifesto)
        if active_path.exists() and not is_active_valid:
            is_prev_valid, prev_data = _validar_arquivo_dados(prev_path, prev_hashes, quality, bool(meta or prev_meta))

            # Move o ativo não comitado/corrompido para quarentena
            mover_para_quarentena(active_path, quarantine_dir)

            if is_prev_valid:
                # Promove o backup comitado para ativo
                os.replace(prev_path, active_path)
                _fsync_dir(data_dir)
                actual_restored_sha = _calcular_sha256_arquivo(active_path)
                if meta and meta.get("version"):
                    if prev_src_info:
                        new_info = dict(prev_src_info)
                        new_info["sha256"] = actual_restored_sha
                        sources_meta[canonical_src] = new_info
                    else:
                        sources_meta[canonical_src] = {
                            "updated_at": src_info.get("updated_at") or datetime.now(timezone.utc).isoformat(),
                            "sha256": actual_restored_sha,
                            "count": len(prev_data),
                            "status": "success" if prev_data else "empty",
                            "quality": quality or "legacy_unverified",
                        }
                    meta_modificado = True
            elif prev_path.exists():
                mover_para_quarentena(prev_path, quarantine_dir)

        elif not active_path.exists() and prev_path.exists():
            # Ativo ausente, mas .prev existe
            is_prev_valid, prev_data = _validar_arquivo_dados(prev_path, prev_hashes, quality, bool(meta or prev_meta))
            if is_prev_valid:
                os.replace(prev_path, active_path)
                _fsync_dir(data_dir)
                actual_restored_sha = _calcular_sha256_arquivo(active_path)
                if meta and meta.get("version"):
                    if prev_src_info:
                        new_info = dict(prev_src_info)
                        new_info["sha256"] = actual_restored_sha
                        sources_meta[canonical_src] = new_info
                    else:
                        sources_meta[canonical_src] = {
                            "updated_at": src_info.get("updated_at") or datetime.now(timezone.utc).isoformat(),
                            "sha256": actual_restored_sha,
                            "count": len(prev_data),
                            "status": "success" if prev_data else "empty",
                            "quality": quality or "legacy_unverified",
                        }
                    meta_modificado = True
            else:
                mover_para_quarentena(prev_path, quarantine_dir)

    if meta_modificado and meta:
        meta["sources"] = sources_meta
        _atomic_write_snapshot_json(data_dir / SNAPSHOT_METADATA_FILE, meta, data_dir)


@dataclass
class DailyIngestionBatch:
    """Modelo de dados tipado para representar o lote unificado de ingestão diária."""
    tweets: list[Tweet] = field(default_factory=list)
    repos: list[GitHubRepo] = field(default_factory=list)
    papers: list[ResearchPaper] = field(default_factory=list)
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    results: dict[str, SourceCollectionResult] = field(default_factory=dict)
    sources_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)

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
            "sources_metadata": self.sources_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyIngestionBatch":
        """Reconstitui o lote tipado a partir de um dicionário."""
        return cls(
            tweets=[Tweet.from_dict(t) for t in data.get("tweets") or []],
            repos=[GitHubRepo.from_dict(r) for r in data.get("repos") or []],
            papers=[ResearchPaper.from_dict(p) for p in data.get("papers") or []],
            collected_at=str(data.get("collected_at") or datetime.now(timezone.utc).isoformat()),
            results={},
            sources_metadata=data.get("sources_metadata") or {},
        )

    def save_snapshot(
        self,
        data_dir: Path | str,
        source: str | None = None,
        status: SourceStatus | str | None = None,
        result: SourceCollectionResult | None = None,
        results: dict[str, SourceCollectionResult] | None = None,
        trigger: str = "pipeline",
    ) -> None:
        """Salva snapshot atômico dos arquivos JSON no diretório com protocolo transacional e durabilidade estrita."""
        from src.core.manifest import _calcular_sha256_arquivo

        dir_path = Path(data_dir)
        dir_path.mkdir(parents=True, exist_ok=True)
        lock_path = dir_path / "snapshot.lock"

        with adquirir_trava_snapshot(lock_path, timeout=10.0):
            # Fase 1: Preflight e Reconciliação
            _reconciliar_arquivos_preflight(dir_path)

            # Normalização e validação estrita de fontes permitidas (restrição de path traversal)
            target_sources: list[str]
            if source:
                norm = source.lower().removeprefix("collect-").strip()
                canonical = SOURCE_ALIASES_MAP.get(norm)
                if not canonical:
                    raise ValueError(f"Fonte desconhecida ou não autorizada para snapshot: {source}")
                target_sources = [canonical]
            else:
                target_sources = ["twitter", "github", "papers"]

            # Mapeamento dos itens e status por fonte
            source_payloads: dict[str, tuple[SourceStatus, list[Any]]] = {}
            for src in target_sources:
                src_status: SourceStatus
                items: list[Any]

                if result and len(target_sources) == 1:
                    src_status = result.status if isinstance(result.status, SourceStatus) else SourceStatus(result.status)
                    items = list(result.items)
                elif results is not None:
                    if src in results:
                        r = results[src]
                        src_status = r.status if isinstance(r.status, SourceStatus) else SourceStatus(r.status)
                        items = list(r.items)
                    else:
                        # results foi fornecido explicitamente, mas src não foi executada nesta rodada
                        src_status = SourceStatus.NOT_RUN
                        items = []
                else:
                    if src == "twitter":
                        raw_items = self.tweets
                    elif src == "github":
                        raw_items = self.repos
                    elif src == "papers":
                        raw_items = self.papers
                    else:
                        raw_items = []

                    items = list(raw_items)
                    if status is not None:
                        src_status = SourceStatus(status) if isinstance(status, str) else status
                    else:
                        src_status = SourceStatus.SUCCESS if len(items) > 0 else SourceStatus.EMPTY

                source_payloads[src] = (src_status, items)

            # Carrega manifesto existente com validação de schema
            quarantine_dir = dir_path / "quarantine"
            meta, _, _ = _carregar_e_validar_manifesto(dir_path, quarantine_dir)
            sources_dict = meta.setdefault("sources", {})

            # Determina quais fontes serão efetivamente gravadas no disco
            written_sources: dict[str, int] = {}
            for src, (src_status, items) in source_payloads.items():
                # Regras de preservação de dados anteriores (DEF-01):
                # - FAILED: preserva dados anteriores em disco
                # - PARTIAL sem dados: preserva dados anteriores em disco
                # - NOT_RUN: preserva dados anteriores em disco
                if src_status in (SourceStatus.FAILED, SourceStatus.NOT_RUN):
                    continue
                if src_status == SourceStatus.PARTIAL and len(items) == 0:
                    continue

                filename = SOURCE_FILE_MAP[src]
                file_path = dir_path / filename

                # Fase 2: Rotação Atômica de Backup (.prev)
                _atomic_backup_prev(file_path, dir_path)

                # Fase 3: Gravação Segura do Arquivo Ativo de Dados
                serialized = [item.to_dict() if hasattr(item, "to_dict") else item for item in items]
                _atomic_write_snapshot_json(file_path, serialized, dir_path)
                written_sources[src] = len(serialized)

            # Normalização de timestamp com timezone explícito para novos snapshots
            def _normalizar_para_utc(ts_str: str) -> str:
                try:
                    dt = datetime.fromisoformat(ts_str)
                    if dt.tzinfo is not None:
                        return dt.astimezone(timezone.utc).isoformat()
                    # Preserva timestamps ingênuos sem forçar tzinfo arbitrário com replace()
                    return ts_str
                except Exception:
                    return ts_str

            ts_com_fuso = _normalizar_para_utc(self.collected_at)
            if not ts_com_fuso:
                ts_com_fuso = datetime.now(timezone.utc).isoformat()

            # Fase 4: Atualização Atômica do Manifesto
            # Atualiza apenas as fontes gravadas; preserva estritamente timestamps históricos não alterados
            for src, count in written_sources.items():
                filename = SOURCE_FILE_MAP[src]
                file_path = dir_path / filename
                sha = _calcular_sha256_arquivo(file_path)
                src_status, _ = source_payloads[src]

                sources_dict[src] = {
                    "updated_at": ts_com_fuso,
                    "sha256": sha,
                    "count": count,
                    "status": src_status.value,
                    "quality": "verified",
                }

            # Se for fonte única não gravada (ex: FAILED ou PARTIAL vazio), mas já existia no manifesto,
            # seu updated_at e dados permanecem intactos. Se não existia, registra falha sem inventar hash.
            # Fontes com NOT_RUN são omitidas da persistência se não existirem no manifesto.
            for src in target_sources:
                if src not in written_sources and src not in sources_dict:
                    src_status, _ = source_payloads[src]
                    if src_status == SourceStatus.NOT_RUN:
                        continue
                    sources_dict[src] = {
                        "updated_at": ts_com_fuso,
                        "sha256": None,
                        "count": 0,
                        "status": src_status.value,
                        "quality": "legacy_unverified",
                    }

            meta["version"] = 2
            # Preserva collected_at anterior caso seja execução parcial ou fonte única
            if (source or (results is not None and len(written_sources) < len(CANONICAL_SOURCES))) and meta.get("collected_at"):
                pass
            else:
                meta["collected_at"] = ts_com_fuso
            meta["last_attempt"] = {
                "started_at": ts_com_fuso,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "trigger": trigger,
                "pid": os.getpid(),
            }
            if source:
                meta["last_attempt"]["target"] = source

            meta["sources"] = sources_dict

            meta_file = dir_path / SNAPSHOT_METADATA_FILE
            # Backup atômico do manifesto antes de substituir
            _atomic_backup_prev(meta_file, dir_path)

            # Grava manifesto v2
            _atomic_write_snapshot_json(meta_file, meta, dir_path)

            self.sources_metadata = dict(sources_dict)
            if results:
                self.results = dict(results)
            elif result and source:
                canonical = SOURCE_ALIASES_MAP.get(source.lower().removeprefix("collect-").strip())
                if canonical:
                    self.results[canonical] = result

    @classmethod
    def load_snapshot(cls, data_dir: Path | str, timeout: float = 10.0) -> "DailyIngestionBatch":
        """Reconstitui o DailyIngestionBatch a partir dos arquivos JSON com integridade verificada."""
        from src.core.manifest import is_execucao_em_andamento, _calcular_sha256_arquivo

        dir_path = Path(data_dir)
        if not dir_path.exists():
            return cls()

        quarantine_dir = dir_path / "quarantine"
        lock_path = dir_path / "snapshot.lock"

        with adquirir_trava_snapshot(lock_path, timeout=timeout):
            # 1. Carrega e valida o manifesto com validação estrita de schema v2
            meta, prev_meta, is_compromised = _carregar_e_validar_manifesto(dir_path, quarantine_dir)

            # Se os manifestos existiam mas foram invalidados e quarentenados, o lote é considerado vazio
            if is_compromised:
                return cls()

            # 2. Proibição estrita de dirty reads e recuperação de crash de execução interrompida
            if meta:
                last_attempt = meta.get("last_attempt", {})
                if last_attempt.get("status") == "running":
                    if is_execucao_em_andamento(last_attempt, check_liveness=True):
                        logger.warning("Execução em andamento ('running') detectada no disco. Dirty reads proibidos.")
                        return cls(collected_at=str(meta.get("collected_at") or datetime.now(timezone.utc).isoformat()))
                    else:
                        pid = last_attempt.get("pid")
                        logger.warning(
                            f"Execução anterior (PID {pid}) foi interrompida abruptamente antes da finalização. "
                            "Transicionando status para 'interrupted' sob trava."
                        )
                        meta["last_attempt"]["status"] = "interrupted"
                        meta["last_attempt"]["completed_at"] = datetime.now(timezone.utc).isoformat()
                        meta_file = dir_path / SNAPSHOT_METADATA_FILE
                        _atomic_backup_prev(meta_file, dir_path)
                        _atomic_write_snapshot_json(meta_file, meta, dir_path)

            meta_sincronizado = False

            # 3. Função interna para verificar e carregar um arquivo JSON por fonte
            def _carregar_fonte(filename: str, canonical_src: str) -> list[dict[str, Any]]:
                nonlocal meta_sincronizado
                active_file = dir_path / filename
                prev_file = dir_path / f"{filename}.prev"

                # Busca metadados da fonte no manifesto ativo e no manifesto .prev resolvendo aliases
                src_info = obter_metadados_fonte(meta.get("sources", {}), canonical_src) if meta else {}
                prev_src_info = obter_metadados_fonte(prev_meta.get("sources", {}), canonical_src) if prev_meta else {}

                src_status = src_info.get("status")
                expected_sha = src_info.get("sha256")
                prev_expected_sha = prev_src_info.get("sha256")
                quality = src_info.get("quality") or prev_src_info.get("quality")

                # Se a fonte foi marcada formalmente como failed ou not_run, não consome dados
                if src_status in ("failed", "not_run"):
                    return []

                # Se o manifesto v2 existe mas a fonte não está registrada no manifesto ativo nem no .prev,
                # o dado no disco não foi comitado; proíbe dirty reads sem deletar o arquivo do disco
                if meta and meta.get("version") and not src_info and not prev_src_info:
                    return []

                active_hashes = {expected_sha}
                prev_hashes = {expected_sha, prev_expected_sha}

                is_active_valid, active_data = _validar_arquivo_dados(active_file, active_hashes, quality, bool(meta))
                if is_active_valid:
                    return active_data

                # Se o ativo não é válido, tenta recuperação via .prev validando contra hash esperado
                is_prev_valid, prev_data = _validar_arquivo_dados(prev_file, prev_hashes, quality, bool(meta or prev_meta))

                # Move ativo corrompido/inválido/divergente para quarentena
                if active_file.exists():
                    mover_para_quarentena(active_file, quarantine_dir)

                if is_prev_valid:
                    # Promove .prev para ativo
                    os.replace(prev_file, active_file)
                    _fsync_dir(dir_path)
                    actual_restored_sha = _calcular_sha256_arquivo(active_file)
                    if meta and meta.get("version"):
                        meta_sources = meta.setdefault("sources", {})
                        if prev_src_info:
                            new_info = dict(prev_src_info)
                            new_info["sha256"] = actual_restored_sha
                            meta_sources[canonical_src] = new_info
                        else:
                            meta_sources[canonical_src] = {
                                "updated_at": src_info.get("updated_at") or datetime.now(timezone.utc).isoformat(),
                                "sha256": actual_restored_sha,
                                "count": len(prev_data),
                                "status": "success" if prev_data else "empty",
                                "quality": quality or "legacy_unverified",
                            }
                        meta_sincronizado = True
                    return prev_data
                else:
                    # .prev também inválido ou divergente: quarentena .prev se existir
                    if prev_file.exists():
                        mover_para_quarentena(prev_file, quarantine_dir)
                    return []

            tweets_raw = _carregar_fonte(SNAPSHOT_TWEETS_FILE, "twitter")
            repos_raw = _carregar_fonte(SNAPSHOT_GITHUB_FILE, "github")
            papers_raw = _carregar_fonte(SNAPSHOT_PAPERS_FILE, "papers")

            if meta_sincronizado and meta:
                meta_file = dir_path / SNAPSHOT_METADATA_FILE
                _atomic_write_snapshot_json(meta_file, meta, dir_path)

            collected_at = str(meta.get("collected_at") or "")
            if not collected_at:
                mtimes = [
                    p.stat().st_mtime
                    for p in [dir_path / SNAPSHOT_TWEETS_FILE, dir_path / SNAPSHOT_GITHUB_FILE, dir_path / SNAPSHOT_PAPERS_FILE]
                    if p.exists()
                ]
                if mtimes:
                    collected_at = datetime.fromtimestamp(max(mtimes)).isoformat()
                else:
                    collected_at = datetime.now(timezone.utc).isoformat()

            return cls(
                tweets=[Tweet.from_dict(t) for t in tweets_raw],
                repos=[GitHubRepo.from_dict(r) for r in repos_raw],
                papers=[ResearchPaper.from_dict(p) for p in papers_raw],
                collected_at=collected_at,
                sources_metadata=dict(meta.get("sources", {})) if meta else {},
            )

