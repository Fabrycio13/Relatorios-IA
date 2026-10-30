"""Módulo de Guardrails e Proteção Hermética da Suíte de Testes.

Garante o cumprimento estrito da Regra 3 do AGENTS.md (Testes Herméticos):
1. Bloqueia conexões de rede externas acidentais (HTTP, HTTPS, DNS, SMTP, TCP).
2. Bloqueia resolução DNS externa (socket.getaddrinfo, socket.gethostbyname) antes de qualquer handshake.
3. Bloqueia a inicialização real de instâncias de Browser e drivers do Playwright.
4. Preserva a execução legítima de subprocessos locais do interpretador Python (concorrência e locks).
5. Oferece context managers e utilitários para testes controlados de falha e autorização.

Limites Técnicos Documentados:
- Escopo do Processo: A interceptação atua sobre a biblioteca padrão 'socket' e classes do Playwright
  carregadas no processo Python corrente.
- Subprocessos Filhos: Processos independentes inicializados via subprocess.Popen([sys.executable, ...])
  possuem tabelas de símbolos e memória isoladas do processo-pai. Portanto, subprocessos filhos não
  herdam automaticamente os monkeypatches da biblioteca socket do processo-pai a menos que importem
  o pacote tests ou ativem explicitamente os guardrails.
- Binários Nativos: Binários externos compilados ou comandos do sistema operacional que possuam
  resolvers próprios em C/Go/Rust fora do runtime Python não passam pelo módulo socket do Python.
"""

from contextlib import contextmanager
import socket
import sys
import threading

logger = None


class NetworkBlockedError(RuntimeError):
    """Exceção levantada quando uma conexão de rede externa não autorizada é tentada em testes."""
    pass


class PlaywrightBlockedError(RuntimeError):
    """Exceção levantada quando uma execução real do Playwright é iniciada sem mock em testes."""
    pass


# Estado por thread para permitir controle seguro em contextos assíncronos ou concorrentes
_state = threading.local()


def is_network_allowed() -> bool:
    """Verifica se conexões de rede externas estão temporariamente autorizadas."""
    return getattr(_state, "network_allowed", False)


def is_playwright_allowed() -> bool:
    """Verifica se execuções do Playwright estão temporariamente autorizadas."""
    return getattr(_state, "playwright_allowed", False)


@contextmanager
def allow_network():
    """Context manager para permitir conexões de rede externas em testes explicitamente autorizados."""
    prev = getattr(_state, "network_allowed", False)
    _state.network_allowed = True
    try:
        yield
    finally:
        _state.network_allowed = prev


@contextmanager
def allow_playwright():
    """Context manager para permitir execução real do Playwright em testes explicitamente autorizados."""
    prev = getattr(_state, "playwright_allowed", False)
    _state.playwright_allowed = True
    try:
        yield
    finally:
        _state.playwright_allowed = prev


def _is_local_host_str(host_str: str) -> bool:
    """Verifica se uma string de hostname/IP é estritamente loopback local (127.0.0.1, localhost, ::1)."""
    if not host_str:
        return True
    h = host_str.strip().lower()
    return h in ("127.0.0.1", "localhost", "::1") or h.startswith("127.")


def is_local_address(address) -> bool:
    """Verifica se o endereço fornecido pertence ao loopback local (127.0.0.1, localhost, ::1) ou IPC local.

    Nota técnica: 0.0.0.0 NÃO é classificado como loopback (representa INADDR_ANY para bind de servidores,
    não sendo um destino de loopback seguro para conexões de saída).
    """
    if isinstance(address, (str, bytes)):
        # Endereço Unix domain socket (AF_UNIX) ou pipes IPC locais
        return True

    if isinstance(address, tuple) and len(address) >= 2:
        host = address[0]
        if host is None or host == "":
            return True
        return _is_local_host_str(str(host))

    return False


# Guardas de socket originais
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex
_orig_getaddrinfo = socket.getaddrinfo
_orig_gethostbyname = socket.gethostbyname
_orig_gethostbyname_ex = socket.gethostbyname_ex


def _guarded_connect(self, address):
    if not is_network_allowed():
        if not is_local_address(address):
            try:
                self.close()
            except Exception:
                pass
            raise NetworkBlockedError(
                f"Tentativa de conexão de rede externa não autorizada em ambiente de testes para: {address}. "
                "Todos os testes devem ser herméticos (Regra 3 do AGENTS.md)."
            )
    return _orig_connect(self, address)


def _guarded_connect_ex(self, address):
    if not is_network_allowed():
        if not is_local_address(address):
            try:
                self.close()
            except Exception:
                pass
            raise NetworkBlockedError(
                f"Tentativa de conexão de rede externa (connect_ex) não autorizada em ambiente de testes para: {address}. "
                "Todos os testes devem ser herméticos (Regra 3 do AGENTS.md)."
            )
    return _orig_connect_ex(self, address)


def _guarded_getaddrinfo(host, port, *args, **kwargs):
    if not is_network_allowed():
        if host is not None and str(host) != "":
            if not _is_local_host_str(str(host)):
                raise NetworkBlockedError(
                    f"Tentativa de resolução DNS externa não autorizada em ambiente de testes para: '{host}'. "
                    "Todos os testes devem ser herméticos (Regra 3 do AGENTS.md)."
                )
    return _orig_getaddrinfo(host, port, *args, **kwargs)


def _guarded_gethostbyname(hostname):
    if not is_network_allowed():
        if hostname is not None and str(hostname) != "":
            if not _is_local_host_str(str(hostname)):
                raise NetworkBlockedError(
                    f"Tentativa de resolução DNS (gethostbyname) externa não autorizada em ambiente de testes para: '{hostname}'. "
                    "Todos os testes devem ser herméticos (Regra 3 do AGENTS.md)."
                )
    return _orig_gethostbyname(hostname)


def _guarded_gethostbyname_ex(hostname):
    if not is_network_allowed():
        if hostname is not None and str(hostname) != "":
            if not _is_local_host_str(str(hostname)):
                raise NetworkBlockedError(
                    f"Tentativa de resolução DNS (gethostbyname_ex) externa não autorizada em ambiente de testes para: '{hostname}'. "
                    "Todos os testes devem ser herméticos (Regra 3 do AGENTS.md)."
                )
    return _orig_gethostbyname_ex(hostname)


# Guardas de Playwright
_orig_playwright_enter = None
_orig_async_playwright_enter = None

try:
    from playwright.sync_api._context_manager import PlaywrightContextManager
    _orig_playwright_enter = PlaywrightContextManager.__enter__
except Exception:
    PlaywrightContextManager = None

try:
    from playwright.async_api._context_manager import PlaywrightContextManager as AsyncPlaywrightContextManager
    _orig_async_playwright_enter = AsyncPlaywrightContextManager.__aenter__
except Exception:
    AsyncPlaywrightContextManager = None


def _guarded_playwright_enter(self):
    if not is_playwright_allowed():
        raise PlaywrightBlockedError(
            "Tentativa de inicialização real do Playwright/Chromium em ambiente de testes. "
            "A coleta real de dados é proibida durante testes automatizados; utilize mocks herméticos "
            "de DOM (make_mock_article). (Regra 3 do AGENTS.md)"
        )
    return _orig_playwright_enter(self)


def _guarded_async_playwright_enter(self):
    if not is_playwright_allowed():
        raise PlaywrightBlockedError(
            "Tentativa de inicialização real do Playwright assíncrono em ambiente de testes. "
            "A coleta real de dados é proibida durante testes automatizados. (Regra 3 do AGENTS.md)"
        )
    return _orig_async_playwright_enter(self)


_installed = False


def is_guardrails_installed() -> bool:
    """Retorna True se os guardrails estiverem atualmente ativos no processo."""
    global _installed
    return _installed


def install_guardrails():
    """Instala os interceptores globais de rede e processos para isolamento estrito dos testes."""
    global _installed
    if _installed:
        return

    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.getaddrinfo = _guarded_getaddrinfo
    socket.gethostbyname = _guarded_gethostbyname
    socket.gethostbyname_ex = _guarded_gethostbyname_ex

    if PlaywrightContextManager and _orig_playwright_enter:
        PlaywrightContextManager.__enter__ = _guarded_playwright_enter

    if AsyncPlaywrightContextManager and _orig_async_playwright_enter:
        AsyncPlaywrightContextManager.__aenter__ = _guarded_async_playwright_enter

    _installed = True


def uninstall_guardrails():
    """Restaura as implementações originais (útil para teardown ou testes do guardrail)."""
    global _installed
    if not _installed:
        return

    socket.socket.connect = _orig_connect
    socket.socket.connect_ex = _orig_connect_ex
    socket.getaddrinfo = _orig_getaddrinfo
    socket.gethostbyname = _orig_gethostbyname
    socket.gethostbyname_ex = _orig_gethostbyname_ex

    if PlaywrightContextManager and _orig_playwright_enter:
        PlaywrightContextManager.__enter__ = _orig_playwright_enter

    if AsyncPlaywrightContextManager and _orig_async_playwright_enter:
        AsyncPlaywrightContextManager.__aenter__ = _orig_async_playwright_enter

    _installed = False
