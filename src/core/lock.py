"""Módulo de Bloqueio Exclusivo e Proteção contra Concorrência do Pipeline e Snapshots.

Garante que múltiplas invocações simultâneas (ex: disparos concorrentes do
Windows Task Scheduler) não executem envios duplicados nem causem condições
de corrida na gravação dos estados, travas diárias e snapshots.
"""

from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import errno
import logging
import os
from pathlib import Path
import sys
import time
import uuid

logger = logging.getLogger(__name__)

# Rastreador de travas de snapshot ativas no processo corrente para prevenção de aninhamento
_SNAPSHOT_LOCKS_ATIVOS: set[str] = set()


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


def _is_lock_contention(exc: Exception) -> bool:
    """Verifica se uma exceção decorre de contenção real de bloqueio entre processos."""
    if sys.platform == "win32":
        # No Windows, msvcrt.locking levanta PermissionError ou OSError com EACCES (13) ou EDEADLK (36)
        if isinstance(exc, PermissionError):
            return True
        if isinstance(exc, OSError) and getattr(exc, "errno", None) in (errno.EACCES, errno.EDEADLK):
            return True
        return False
    else:
        # No POSIX, fcntl.flock levanta BlockingIOError ou OSError com EAGAIN, EWOULDBLOCK ou EACCES
        if isinstance(exc, BlockingIOError):
            return True
        if isinstance(exc, OSError) and getattr(exc, "errno", None) in (
            errno.EAGAIN,
            errno.EWOULDBLOCK,
            errno.EACCES,
        ):
            return True
        return False


@contextmanager
def adquirir_trava_snapshot(lock_path: Path, timeout: float = 10.0, retry_delay: float = 0.2):
    """Adquire trava exclusiva de snapshot com retentativas baseadas em time.monotonic().

    O retry protege estritamente a fase de aquisição em caso de contenção real de lock;
    falhas de filesystem, diretório ou permissão no open() não são mascaradas como timeout
    e propagam imediatamente.
    Uma vez adquirido o contexto, o bloco do chamador executa isoladamente sem reentrância espúria.
    Impede aquisição aninhada no mesmo processo para evitar deadlocks e comportamento indefinido.
    """
    resolved_path = str(lock_path.resolve())
    if resolved_path in _SNAPSHOT_LOCKS_ATIVOS:
        raise RuntimeError(f"Aquisição aninhada da trava de snapshot não é permitida: {lock_path}")

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    stack = ExitStack()
    adquirido = False

    try:
        while True:
            # open() não é contenção de lock: se o arquivo/diretório for inacessível
            # ou houver erro de permissão/disco no open, propaga imediatamente sem retry.
            lock_file = open(lock_path, "a+b")
            stack.enter_context(lock_file)

            try:
                if sys.platform == "win32":
                    import msvcrt
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                adquirido = True
                _SNAPSHOT_LOCKS_ATIVOS.add(resolved_path)

                def _unlock():
                    try:
                        if sys.platform == "win32":
                            import msvcrt
                            lock_file.seek(0)
                            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    except Exception as e:
                        logger.debug(f"Aviso ao liberar snapshot lock em {lock_path}: {e}")

                stack.callback(_unlock)
                break
            except Exception as e:
                stack.close()
                if _is_lock_contention(e):
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Timeout de {timeout}s aguardando trava de snapshot em {lock_path}")
                    time.sleep(retry_delay)
                else:
                    # Erro não decorrente de contenção (ex: EBADF, EINVAL, etc.): fecha o handle e propaga imediatamente
                    raise

        with stack:
            yield lock_file
    finally:
        if adquirido:
            _SNAPSHOT_LOCKS_ATIVOS.discard(resolved_path)


def _fsync_dir(dir_path: Path) -> None:
    """Sincroniza metadados do diretório no POSIX. No-op documentado e seguro no Windows.

    No Windows NTFS, o journaling do sistema de arquivos ($LogFile) protege a consistência
    lógica dos metadados de diretórios contra corrupção estrutural, mas não fornece garantia
    de persistência física imediata em disco após queda abrupta de energia elétrica, não
    existindo na API Win32 suporte padrão para fsync em descritores de diretório (chamadas a
    CreateFile/FlushFileBuffers em diretórios falham ou exigem privilégios especiais). Assim,
    no Windows esta operação é um no-op documentado com essa limitação conhecida.

    No POSIX, abre o descritor de diretório com os.O_RDONLY, invoca os.fsync(fd) e fecha
    o descritor. Se a sincronização falhar (ex: erro de hardware, filesystem read-only,
    ou descritor inválido), a exceção OSError é propagada para garantir que operações
    críticas não continuem como se a durabilidade estivesse garantida.
    """
    if sys.platform != "win32":
        fd = os.open(str(dir_path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def mover_para_quarentena(file_path: Path, quarantine_dir: Path) -> Path:
    """Move arquivo corrompido para o diretório de quarentena com nome único e não colidente.

    Utiliza UUID4 completo (32 caracteres hexadecimais) e valida previamente a inexistência
    do arquivo candidato (if not candidate_path.exists()) antes de executar o os.replace().
    Essa estratégia reduz a probabilidade de colisão a níveis desprezíveis na prática, contudo
    deve-se registrar como limitação que o par exists() + os.replace() não constitui uma
    operação atômica contra escritores externos concorrentes que operem fora do ecossistema do
    pipeline. A proteção estrita contra concorrência entre passos é garantida pela integração
    do Ticket 20, que executa operações de persistência e quarentena sob a proteção exclusiva
    de adquirir_trava_snapshot.

    Sincroniza os metadados dos diretórios envolvidos no POSIX. Em caso de falha no fsync
    pós-movimentação no POSIX, a exceção é propagada; o chamador deve estar ciente de que
    o arquivo físico já foi movido (sem rollback automático).
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo alvo de quarentena não existe: {file_path}")

    quarantine_dir.mkdir(parents=True, exist_ok=True)
    _fsync_dir(quarantine_dir.parent)

    max_tentativas = 10
    dest_path = None
    for _ in range(max_tentativas):
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
        unique_id = uuid.uuid4().hex  # UUID4 completo (32 caracteres hexadecimais)
        candidate_name = f"{file_path.stem}_{timestamp_str}_{unique_id}{file_path.suffix}.corrupted"
        candidate_path = quarantine_dir / candidate_name
        if not candidate_path.exists():
            dest_path = candidate_path
            break

    if dest_path is None:
        raise FileExistsError(
            f"Não foi possível encontrar nome de quarentena livre de colisão após {max_tentativas} tentativas em {quarantine_dir}"
        )

    os.replace(file_path, dest_path)
    _fsync_dir(file_path.parent)
    _fsync_dir(quarantine_dir)

    return dest_path
