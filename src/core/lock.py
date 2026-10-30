"""Módulo de Bloqueio Exclusivo e Proteção contra Concorrência do Pipeline.

Garante que múltiplas invocações simultâneas (ex: disparos concorrentes do
Windows Task Scheduler) não executem envios duplicados nem causem condições
de corrida na gravação dos estados e travas diárias.
"""

from contextlib import contextmanager
import logging
import os
from pathlib import Path
import sys

logger = logging.getLogger(__name__)


class ConcorrenciaDetectadaError(Exception):
    """Exceção levantada quando outra instância do pipeline já detém a trava exclusiva."""
    pass


@contextmanager
def adquirir_trava_pipeline(lock_path: Path):
    """Adquire uma trava exclusiva no sistema operacional para o pipeline diário.

    Utiliza msvcrt no Windows e fcntl em sistemas POSIX.
    Lança ConcorrenciaDetectadaError se o bloqueio não puder ser obtido imediatamente.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "a+")
    adquirido = False
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                adquirido = True
            except (OSError, PermissionError):
                raise ConcorrenciaDetectadaError("Execução concorrente detectada.")
        else:
            import fcntl
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                adquirido = True
            except (OSError, BlockingIOError):
                raise ConcorrenciaDetectadaError("Execução concorrente detectada.")
        yield f
    finally:
        if adquirido:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception as e:
                logger.debug(f"Aviso ao liberar lock em {lock_path}: {e}")
        try:
            f.close()
        except Exception as e:
            logger.debug(f"Aviso ao fechar handle da trava {lock_path}: {e}")
