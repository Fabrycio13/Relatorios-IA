"""Módulo de Schema do Manifesto, Migração de Metadados Legados e Governança de Frescor.

Implementa os contratos estritos da Spec 0007 v4.3 e Ticket 19:
- Validação de schema v2 de snapshot_metadata.json.
- Detecção e migração não-destrutiva de manifestos v1 com classificação 'legacy_unverified'.
- Política harmonizada de frescor temporal no intervalo [-300s, max_hours * 3600s].
- Governança do ciclo de vida em last_attempt (running vs finalizado), sem antecipar
  a política editorial de publicação (que pertence ao Ticket 22).
"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

from src.core.models import SourceStatus

logger = logging.getLogger(__name__)

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")

ARQUIVOS_FONTES_MAP: dict[str, str] = {
    "twitter": "tweets_coletados.json",
    "tweets": "tweets_coletados.json",
    "github": "github_trending.json",
    "repos": "github_trending.json",
    "github_trending": "github_trending.json",
    "papers": "hf_papers.json",
    "hf_papers": "hf_papers.json",
}


def _calcular_sha256_arquivo(caminho: Path) -> str:
    """Calcula o hash SHA-256 hexadecimal minúsculo de um arquivo existente.

    Propaga FileNotFoundError se o arquivo não existir ou OSError em falhas de leitura/I/O.
    Nunca gera ou retorna hashes fictícios para arquivos inexistentes ou corrompidos.
    """
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def _is_valid_iso(val: Any) -> bool:
    """Verifica se o valor é uma string ISO 8601 válida."""
    if not isinstance(val, str):
        return False
    try:
        datetime.fromisoformat(val)
        return True
    except Exception:
        return False


def validar_schema_manifesto(data: Any) -> bool:
    """Valida estritamente a conformidade do dicionário com o schema v2 do manifesto (Spec 0007 §3.1).

    Retorna True se for válido e False se for malformado, ausente ou contiver
    tipos divergentes (rejeitando booleanos em campos inteiros e tipos não-hashables).
    """
    if not isinstance(data, dict):
        return False

    # 1. Chave version (int estrito == 2)
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version != 2:
        return False

    # 2. Chave collected_at (string ISO 8601)
    if not _is_valid_iso(data.get("collected_at")):
        return False

    # 3. Chave last_attempt (objeto de governança do ciclo de vida)
    last_attempt = data.get("last_attempt")
    if not isinstance(last_attempt, dict):
        return False

    if not _is_valid_iso(last_attempt.get("started_at")):
        return False

    attempt_status = last_attempt.get("status")
    if not isinstance(attempt_status, str) or attempt_status not in ("running", "completed", "failed", "interrupted"):
        return False

    if not isinstance(last_attempt.get("trigger"), str):
        return False

    pid = last_attempt.get("pid")
    if pid is not None:
        if not isinstance(pid, int) or isinstance(pid, bool):
            return False

    completed_at = last_attempt.get("completed_at")
    if completed_at is not None and not _is_valid_iso(completed_at):
        return False

    # target é opcional (registra a fonte alvo em coletas isoladas da CLI)
    target = last_attempt.get("target")
    if target is not None and not isinstance(target, str):
        return False

    # 4. Chave sources (objeto mapeando identificador de fonte aos metadados)
    sources = data.get("sources")
    if not isinstance(sources, dict):
        return False

    valid_statuses = {s.value for s in SourceStatus}
    valid_qualities = {"verified", "legacy_unverified", "recovered"}

    for src_name, src_info in sources.items():
        if not isinstance(src_name, str) or not isinstance(src_info, dict):
            return False

        if not _is_valid_iso(src_info.get("updated_at")):
            return False

        # Validação defensiva prévia do tipo de status
        status = src_info.get("status")
        if not isinstance(status, str) or status not in valid_statuses:
            return False

        # Validação defensiva prévia do tipo de quality
        quality = src_info.get("quality")
        if not isinstance(quality, str) or quality not in valid_qualities:
            return False

        sha = src_info.get("sha256")
        if status in ("failed", "not_run"):
            # Em falha ou ausência de arquivo, sha256 pode ser None ou hash do arquivo corrompido em disco
            if sha is not None and (not isinstance(sha, str) or not HEX_64_PATTERN.match(sha)):
                return False
        else:
            # Em success, empty ou partial, o hash de 64 caracteres hexadecimais é estritamente obrigatório
            if not isinstance(sha, str) or not HEX_64_PATTERN.match(sha):
                return False

        # Aceita count (canônico da Spec) ou items_count como alias
        count = src_info.get("count")
        if count is None and "items_count" in src_info:
            count = src_info.get("items_count")

        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            return False

        # Invariantes de coerência de contadores
        if status in ("empty", "failed", "not_run") and count != 0:
            return False

    return True


def is_manifesto_v1(data: Any) -> bool:
    """Verifica se os dados representam estritamente o formato legado v1 de snapshot_metadata.json."""
    if not isinstance(data, dict):
        return False

    # V1 nunca continha chave 'version'
    if "version" in data and data["version"] is not None:
        return False

    # collected_at pode estar ausente na raiz em coletas isoladas da versão original
    collected_at = data.get("collected_at")
    if collected_at is not None and (not isinstance(collected_at, str) or not collected_at):
        return False

    sources = data.get("sources")
    if not isinstance(sources, dict) or len(sources) == 0:
        return False

    # Em v1, TODOS os valores em sources devem ser strings de timestamp
    if not all(isinstance(v, str) for v in sources.values()):
        return False

    return True


def migrar_manifesto_v1_para_v2(v1_data: dict[str, Any], data_dir: Path | None = None) -> dict[str, Any]:
    """Migra em memória metadados legados v1 para o schema v2.

    Garante que as fontes legadas recebam estritamente 'quality': 'legacy_unverified'.
    Diferencia arquivos JSON válidos com dados ('success'), listas vazias ('empty')
    e arquivos inexistentes ou corrompidos ('failed'), sem inventar sucesso ou hashes fictícios.
    Preserva os timestamps históricos originais sem inventar o horário atual.
    Opera estritamente em memória sem modificar arquivos de produção.
    """
    collected_at = v1_data.get("collected_at")
    raw_sources = v1_data.get("sources") if isinstance(v1_data.get("sources"), dict) else {}

    # Se collected_at não constava na raiz (ex: coleta isolada original), deriva do timestamp
    # mais recente das fontes presentes sem inventar o horário atual
    if not collected_at or not isinstance(collected_at, str):
        ts_values = [v for v in raw_sources.values() if isinstance(v, str) and v]
        collected_at = max(ts_values) if ts_values else None

    v2_sources: dict[str, Any] = {}

    for src_key, raw_val in raw_sources.items():
        # Preserva estritamente o timestamp histórico sem inventar datetime.now()
        updated_at = raw_val

        filename = ARQUIVOS_FONTES_MAP.get(src_key)
        sha256_val: str | None = None
        count_val = 0
        status_val = "failed"

        if data_dir and filename:
            file_path = data_dir / filename
            if not file_path.exists():
                # Arquivo inexistente em disco: falha explicitada sem hash fictício
                status_val = "failed"
                count_val = 0
                sha256_val = None
            else:
                # Arquivo existe: tenta calcular o hash real dos bytes em disco
                try:
                    sha256_val = _calcular_sha256_arquivo(file_path)
                except Exception:
                    sha256_val = None

                # Valida estrutura JSON
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        conteudo = json.load(f)
                    if isinstance(conteudo, list):
                        is_valid_list = True
                        count_val = len(conteudo)
                    else:
                        is_valid_list = False
                        count_val = 0
                except Exception:
                    is_valid_list = False
                    count_val = 0

                if not is_valid_list or sha256_val is None:
                    # JSON corrompido ou erro de I/O
                    status_val = "failed"
                    count_val = 0
                elif count_val > 0:
                    status_val = "success"
                else:
                    status_val = "empty"
        else:
            # Sem diretório em disco ou arquivo não mapeado: falha explícita sem hash fictício
            status_val = "failed"
            count_val = 0
            sha256_val = None

        # Regra contratual: Legado recebe OBRIGATORIAMENTE 'legacy_unverified'
        v2_sources[src_key] = {
            "updated_at": updated_at,
            "sha256": sha256_val,
            "count": count_val,
            "status": status_val,
            "quality": "legacy_unverified",
        }

    return {
        "version": 2,
        "collected_at": collected_at,
        "last_attempt": {
            "started_at": collected_at,
            "completed_at": collected_at,
            "status": "completed",
            "trigger": "legacy_migration",
            "pid": None,
        },
        "sources": v2_sources,
    }


def is_source_fresh(
    updated_at: datetime | str | Any,
    max_hours: float = 36.0,
    now: datetime | None = None,
) -> bool:
    """Verifica se o timestamp da fonte está dentro da janela válida [-300s, max_hours * 3600s].

    - Tolera avanço de relógio do sistema / NTP de até 300 segundos no futuro.
    - Timestamps ingênuos sem fuso conhecido são classificados como temporalmente não confiáveis (retorna False).
    - Rejeita valores que ultrapassam max_hours no passado ou 300s no futuro.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if isinstance(updated_at, str):
        try:
            parsed = datetime.fromisoformat(updated_at)
        except Exception:
            return False
        updated_at = parsed

    if not isinstance(updated_at, datetime):
        return False

    # Timestamps ingênuos sem fuso horário não possuem base de referência confiável
    if updated_at.tzinfo is None:
        return False

    now_utc = now.astimezone(timezone.utc)
    updated_utc = updated_at.astimezone(timezone.utc)

    age_seconds = (now_utc - updated_utc).total_seconds()

    return -300.0 <= age_seconds <= (max_hours * 3600.0)


def is_pid_alive(pid: int | None) -> bool:
    """Verifica se um processo com o PID fornecido está ativo no sistema operacional.

    Compatível com Windows e POSIX.
    Retorna True se o processo está em execução ativa.
    Retorna False se o processo comprovadamente não existe ou já encerrou.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return kernel32.GetLastError() == 5  # ERROR_ACCESS_DENIED (processo de outro usuário existe)

        try:
            exit_code = wintypes.DWORD()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                STILL_ACTIVE = 259
                return exit_code.value == STILL_ACTIVE
            return True
        finally:
            kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False


def is_pid_recycled(pid: int | None, started_at: datetime | str | None) -> bool:
    """Verifica se o PID ativo foi reciclado pelo SO após o timestamp started_at registrado.

    Retorna True se houver prova cabal de que o processo atualmente com o PID nasceu
    após o início da tentativa (process creation time > started_at).
    Retorna False se não houver prova de reciclagem.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or not started_at:
        return False

    if isinstance(started_at, str):
        try:
            started_at = datetime.fromisoformat(started_at)
        except Exception:
            return False

    if not isinstance(started_at, datetime) or started_at.tzinfo is None:
        return False

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False

        try:
            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

            creation_time = FILETIME()
            exit_time = FILETIME()
            kernel_time = FILETIME()
            user_time = FILETIME()

            if kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation_time),
                ctypes.byref(exit_time),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                ft_val = (creation_time.dwHighDateTime << 32) + creation_time.dwLowDateTime
                timestamp = (ft_val - 116444736000000000) / 10000000.0
                if timestamp > 0:
                    proc_created = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    if proc_created > started_at + timedelta(seconds=2):
                        return True
            return False
        finally:
            kernel32.CloseHandle(handle)

    return False


def is_execucao_em_andamento(last_attempt: dict[str, Any], check_liveness: bool = False) -> bool:
    """Retorna True se last_attempt estiver no status 'running'.

    O status 'running' representa formalmente uma execução ainda não finalizada.
    Processos leitores e o sintetizador são terminantemente proibidos de consumir
    dados transitórios de uma execução em andamento (proibição de dirty reads).

    Se check_liveness for True:
    - Verifica se o PID registrado ainda está ativo e pertence à execução original.
    - Se o PID estiver comprovadamente morto ou reciclado, retorna False.
    - Se não houver prova suficiente (incerteza), retorna True para evitar dirty reads.
    """
    if not isinstance(last_attempt, dict):
        return False
    if last_attempt.get("status") != "running":
        return False

    if check_liveness:
        pid = last_attempt.get("pid")
        if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
            if not is_pid_alive(pid):
                return False
            if is_pid_recycled(pid, last_attempt.get("started_at")):
                return False

    return True


def is_execucao_finalizada(last_attempt: dict[str, Any]) -> bool:
    """Retorna True se o ciclo de vida da execução foi concluído ('completed', 'failed', 'interrupted').

    ATENÇÃO: O status 'completed' nesta função atesta EXCLUSIVAMENTE que o processo
    executou até o fim do seu ciclo de vida sem crash.
    NÃO constitui prova de que todas as fontes coletaram dados com sucesso,
    NÃO atesta a integridade física dos arquivos (avaliada via SHA-256 no Ticket 20),
    NÃO atesta a qualidade da coleta ('verified' vs 'legacy_unverified'), e
    NÃO atesta o frescor dos dados (avaliado via is_source_fresh()).
    A decisão editorial de publicação e degradação graciosa pertence estritamente ao Ticket 22.
    """
    if not isinstance(last_attempt, dict):
        return False
    return last_attempt.get("status") in ("completed", "failed", "interrupted")


def avaliar_estado_execucao(last_attempt: dict[str, Any]) -> tuple[str, str]:
    """Avalia o status operacional da última tentativa registrada no manifesto.

    O status 'running' é estritamente tratado como execução em andamento (pendente),
    não assumindo crash apenas porque locks pontuais de filesystem estejam livres.
    """
    status = last_attempt.get("status") if isinstance(last_attempt, dict) else "unknown"

    if status == "running":
        return ("running", "Execução em andamento pendente de finalização")
    elif status == "completed":
        return ("completed", "Ciclo de execução finalizado")
    elif status == "failed":
        return ("failed", "Ciclo de execução finalizou com falha")
    elif status == "interrupted":
        return ("interrupted", "Execução interrompida prematuramente")
    else:
        return ("unknown", f"Status desconhecido: {status}")


def criar_manifesto_v2_vazio(now: datetime | None = None) -> dict[str, Any]:
    """Cria um manifesto v2 novo e limpo para ambientes sem histórico."""
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    ts = now.isoformat()
    return {
        "version": 2,
        "collected_at": ts,
        "last_attempt": {
            "started_at": ts,
            "completed_at": ts,
            "status": "completed",
            "trigger": "initialization",
            "pid": None,
        },
        "sources": {},
    }
