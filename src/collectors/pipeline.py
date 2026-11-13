import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from src.core.config import DATA_DIR
from src.core.logger import get_logger
from src.core.models import (
    DailyIngestionBatch,
    Tweet,
    GitHubRepo,
    ResearchPaper,
    SourceCollectionResult,
    SourceStatus,
)
from src.collectors.base import IngestionSource, TwitterSource, GitHubSource, HuggingFaceSource

logger = get_logger("collectors.pipeline")

ALLOWED_BATCH_FIELDS = {"tweets", "repos", "papers"}


def _marcar_inicio_execucao(data_dir: Path, trigger: str = "pipeline", target: str | None = None) -> None:
    """Atualiza o manifesto registrando last_attempt como running com PID e timestamp de início."""
    from src.core.lock import adquirir_trava_snapshot
    from src.core.models import (
        _carregar_e_validar_manifesto,
        _atomic_write_snapshot_json,
        _atomic_backup_prev,
        SNAPSHOT_METADATA_FILE,
    )
    from src.core.manifest import criar_manifesto_v2_vazio

    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / "snapshot.lock"
    try:
        with adquirir_trava_snapshot(lock_path, timeout=5.0):
            quarantine_dir = data_dir / "quarantine"
            meta, _, _ = _carregar_e_validar_manifesto(data_dir, quarantine_dir)
            if not meta or not meta.get("version"):
                meta = criar_manifesto_v2_vazio()

            # Exclusividade de Processo: verifica se há processo ativo em execução
            prev_attempt = meta.get("last_attempt", {})
            if prev_attempt.get("status") == "running":
                from src.core.manifest import is_execucao_em_andamento
                if is_execucao_em_andamento(prev_attempt, check_liveness=True):
                    prev_pid = prev_attempt.get("pid")
                    raise RuntimeError(
                        f"Execução concorrente bloqueada: processo {prev_pid} já está em andamento."
                    )
                else:
                    prev_pid = prev_attempt.get("pid")
                    logger.info(
                        f"Execução anterior (PID {prev_pid}) foi interrompida antes do término. "
                        "Iniciando nova execução."
                    )

            meta["last_attempt"] = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "running",
                "trigger": trigger,
                "pid": os.getpid(),
            }
            if target:
                meta["last_attempt"]["target"] = target
            else:
                meta["last_attempt"].pop("target", None)

            meta_file = data_dir / SNAPSHOT_METADATA_FILE
            _atomic_backup_prev(meta_file, data_dir)
            _atomic_write_snapshot_json(meta_file, meta, data_dir)
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning(f"Aviso ao inicializar last_attempt como running: {e}")


def _marcar_falha_execucao(data_dir: Path, trigger: str = "pipeline", target: str | None = None) -> None:
    """Atualiza o manifesto registrando last_attempt como failed em caso de aborto."""
    from src.core.lock import adquirir_trava_snapshot
    from src.core.models import (
        _carregar_e_validar_manifesto,
        _atomic_write_snapshot_json,
        _atomic_backup_prev,
        SNAPSHOT_METADATA_FILE,
    )

    try:
        lock_path = data_dir / "snapshot.lock"
        with adquirir_trava_snapshot(lock_path, timeout=5.0):
            quarantine_dir = data_dir / "quarantine"
            meta, _, _ = _carregar_e_validar_manifesto(data_dir, quarantine_dir)
            if meta:
                started_at = meta.get("last_attempt", {}).get("started_at") or datetime.now(timezone.utc).isoformat()
                meta["last_attempt"] = {
                    "started_at": started_at,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "status": "failed",
                    "trigger": trigger,
                    "pid": os.getpid(),
                }
                if target:
                    meta["last_attempt"]["target"] = target
                meta_file = data_dir / SNAPSHOT_METADATA_FILE
                _atomic_backup_prev(meta_file, data_dir)
                _atomic_write_snapshot_json(meta_file, meta, data_dir)
    except Exception as e:
        logger.warning(f"Não foi possível registrar falha no manifesto: {e}")


class IngestionPipeline:
    """Orquestrador unificado de coleta de dados de múltiplas fontes."""

    def __init__(
        self,
        sources: Sequence[IngestionSource] | None = None,
        data_dir: Path | str = DATA_DIR
    ):
        self.data_dir = Path(data_dir)
        if sources is not None:
            self.sources = list(sources)
        else:
            self.sources = [
                TwitterSource(),
                GitHubSource(),
                HuggingFaceSource()
            ]

    def run(self, target_source: str | None = None) -> DailyIngestionBatch:
        """
        Executa as fontes de ingestão registradas.
        Se target_source for fornecido, executa exclusivamente a fonte selecionada.
        Se target_source for None (ou 'all'/'collect'), executa todas as fontes registradas.
        """
        normalized_target = None
        if target_source:
            normalized_target = target_source.lower().removeprefix("collect-").strip()
            if normalized_target in ("all", "collect", ""):
                normalized_target = None

        logger.info("=" * 60)
        logger.info(f"Iniciando pipeline de ingestão (alvo: {normalized_target or 'todas as fontes'})...")
        logger.info("=" * 60)

        # Atualiza manifesto marcando last_attempt como running antes de iniciar o ciclo de scraping
        _marcar_inicio_execucao(self.data_dir, trigger="pipeline", target=normalized_target)

        batch = DailyIngestionBatch(collected_at=datetime.now(timezone.utc).isoformat())
        source_results: dict[str, SourceCollectionResult] = {}

        try:
            # Scraping puro em memória com Zero Locks
            for source in self.sources:
                if normalized_target and source.name != normalized_target:
                    continue

                logger.info(f"\n▶️  Executando coleta da fonte: [{source.name}]...")
                try:
                    res = source.collect()
                    if isinstance(res, SourceCollectionResult):
                        source_results[source.name] = res
                        items = list(res.items)
                    else:
                        raise TypeError(
                            f"Retorno inválido da fonte '{source.name}': esperado SourceCollectionResult, "
                            f"recebido {type(res).__name__}"
                        )

                    field_name = getattr(source, "target_field", None)
                    if field_name and field_name in ALLOWED_BATCH_FIELDS:
                        setattr(batch, field_name, items)
                        logger.info(f"Fonte [{source.name}]: {len(items)} itens obtidos.")
                    else:
                        logger.warning(
                            f"Fonte [{source.name}] possui target_field inválido ou não configurado: '{field_name}'. Itens ignorados."
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao executar coleta na fonte [{source.name}]: {e}")
                    source_results[source.name] = SourceCollectionResult(
                        source_name=source.name,
                        status=SourceStatus.FAILED,
                        items=(),
                        successful_operations=(),
                        failed_operations=(f"err_{source.name}",),
                        error_message=str(e),
                    )

            batch.results = source_results

            if normalized_target:
                if normalized_target not in source_results:
                    logger.warning(f"Nenhum coletor registrado no pipeline para a fonte alvo: [{normalized_target}]")
                    target_res = SourceCollectionResult(
                        source_name=normalized_target,
                        status=SourceStatus.NOT_RUN,
                        items=(),
                        successful_operations=(),
                        failed_operations=(),
                        error_message=None,
                    )
                    source_results[normalized_target] = target_res
                else:
                    target_res = source_results.get(normalized_target)

                batch.save_snapshot(self.data_dir, source=normalized_target, result=target_res, results=source_results)
                logger.info(f"💾 Snapshot da fonte [{normalized_target}] atualizado em {self.data_dir}")
            else:
                batch.save_snapshot(self.data_dir, results=source_results)
                logger.info(f"💾 Snapshot de ingestão consolidado atualizado em {self.data_dir}")

            # Hidratação de fallback para fontes não atualizadas nesta rodada (FAILED, NOT_RUN ou PARTIAL sem dados)
            # a partir do snapshot preservado em disco com integridade verificada via load_snapshot
            sources_needing_fallback = [
                s_name for s_name, res in source_results.items()
                if res.status in (SourceStatus.FAILED, SourceStatus.NOT_RUN) or (res.status == SourceStatus.PARTIAL and not res.items)
            ]
            if sources_needing_fallback:
                try:
                    snapshot_preservado = DailyIngestionBatch.load_snapshot(self.data_dir)
                    for src_name in sources_needing_fallback:
                        target_field = "tweets" if src_name == "twitter" else ("repos" if src_name == "github" else ("papers" if src_name == "papers" else None))
                        if target_field and not getattr(batch, target_field):
                            preservados = getattr(snapshot_preservado, target_field, [])
                            if preservados:
                                setattr(batch, target_field, list(preservados))
                                logger.info(f"Fonte [{src_name}]: {len(preservados)} itens recuperados do snapshot preservado em disco (fallback).")
                    if snapshot_preservado.sources_metadata:
                        for k, v in snapshot_preservado.sources_metadata.items():
                            if k not in batch.sources_metadata:
                                batch.sources_metadata[k] = v
                except Exception as e:
                    logger.warning(f"Aviso ao carregar fallback preservado em disco: {e}")

            return batch
        except Exception:
            _marcar_falha_execucao(self.data_dir, trigger="pipeline", target=normalized_target)
            raise
