from datetime import datetime
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

        batch = DailyIngestionBatch(collected_at=datetime.now().isoformat())
        # Mapa de resultados de coleta tipados (ponte de compatibilidade entre Ticket 21 e 22)
        source_results: dict[str, SourceCollectionResult] = {}

        for source in self.sources:
            if normalized_target and source.name != normalized_target:
                continue

            logger.info(f"\n▶️  Executando coleta da fonte: [{source.name}]...")
            try:
                res = source.collect()
                if isinstance(res, SourceCollectionResult):
                    source_results[source.name] = res
                    items = list(res.items)
                elif isinstance(res, list):
                    # Compatibilidade transitória restrita a testes legados ou mocks que retornam list plana
                    items = list(res)
                    st = SourceStatus.SUCCESS if items else SourceStatus.EMPTY
                    source_results[source.name] = SourceCollectionResult(
                        source_name=source.name,
                        status=st,
                        items=tuple(items),
                        successful_operations=(f"legacy_{source.name}",),
                        failed_operations=(),
                    )
                else:
                    raise TypeError(
                        f"Retorno inválido da fonte '{source.name}': esperado SourceCollectionResult ou list legada, "
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

        return batch
