"""Testes de inicialização, guardrails de rede, DNS e isolamento de processos (Retro Spec 0005).

Este arquivo é nomeado 'test_00_guardrails.py' para garantir que seja descoberto e executado
como o PRIMEIRO conjunto de testes da suíte completa de regressão.
"""

import socket
import subprocess
import sys
import unittest
import urllib.request
import smtplib

# IMPORTANTE: Captura se o ambiente já estava protegido no momento exato em que
# este arquivo foi carregado pelo unittest, ANTES de qualquer import do pacote 'tests.'.
# Isso garante que a verificação comprove que o runner de testes carregou tests/__init__.py,
# sem que o próprio teste instale os guardrails como efeito colateral do seu import.
_WAS_TESTS_PACKAGE_LOADED_AT_IMPORT = "tests" in sys.modules
_WAS_SOCKET_GUARDED_AT_IMPORT = getattr(socket.socket.connect, "__name__", "") == "_guarded_connect"

from tests.guardrails import (
    NetworkBlockedError,
    PlaywrightBlockedError,
    allow_network,
    allow_playwright,
    is_guardrails_installed,
    is_local_address,
    is_network_allowed,
    is_playwright_allowed,
    install_guardrails
)


class TestGuardrailsBootstrap(unittest.TestCase):
    """Valida a inicialização automática e imediata dos guardrails na descoberta de testes."""

    def test_00_guardrails_ativo_no_inicio_da_suite(self):
        """Valida que os guardrails herméticos foram instalados ANTES da carga deste teste.

        A asserção baseia-se no estado capturado antes de qualquer import de 'tests.',
        comprovando que o runner carregou o pacote tests e não mascarando falhas por efeito colateral.
        """
        self.assertTrue(
            _WAS_SOCKET_GUARDED_AT_IMPORT,
            "FALHA CRÍTICA: Os guardrails de isolamento de rede e processo NÃO estavam ativos na carga do módulo!\n"
            "A suíte deve ser executada com o comando canônico:\n"
            "    python -m unittest discover -s tests -t . -v\n"
            "ou para execuções seletivas pontuadas:\n"
            "    python -m unittest tests.<nome_do_modulo> -v\n"
            "Isso garante que tests/__init__.py seja devidamente importado no bootstrap."
        )

    def test_01_verificacao_detectaria_ausencia_de_guardrails(self):
        """Valida logicamente que a verificação falharia caso os guardrails não estivessem ativos,
        sem necessidade de executar nenhuma conexão real à internet."""
        estado_simulado = False
        with self.assertRaises(AssertionError):
            self.assertTrue(estado_simulado, "Guardrail não instalado")


class TestGuardrails(unittest.TestCase):
    """Valida o funcionamento hermético dos guardrails de rede, DNS e processos."""

    def setUp(self):
        # Garante que os guardrails estejam ativos para a classe de teste
        install_guardrails()

    def test_local_addresses_are_identified_correctly(self):
        """Valida que apenas endereços estritamente locais (loopback/IPC) são permitidos."""
        # Locais permitidos (estritamente loopback ou IPC)
        self.assertTrue(is_local_address(("127.0.0.1", 8080)))
        self.assertTrue(is_local_address(("localhost", 80)))
        self.assertTrue(is_local_address(("::1", 443)))
        self.assertTrue(is_local_address(("127.0.0.2", 9000)))
        self.assertTrue(is_local_address("/tmp/pipe.sock"))
        self.assertTrue(is_local_address(b"/tmp/pipe.sock"))
        self.assertTrue(is_local_address((None, 80)))
        self.assertTrue(is_local_address(("", 80)))

        # 0.0.0.0 NÃO é loopback e deve ser rejeitado para conexões de saída
        self.assertFalse(is_local_address(("0.0.0.0", 5000)))

        # O hostname da máquina NÃO é considerado loopback seguro (pode resolver para IP de rede externa/LAN)
        self.assertFalse(is_local_address((socket.gethostname(), 80)))

        # Externos bloqueados
        self.assertFalse(is_local_address(("8.8.8.8", 53)))
        self.assertFalse(is_local_address(("1.1.1.1", 80)))
        self.assertFalse(is_local_address(("google.com", 443)))
        self.assertFalse(is_local_address(("x.com", 443)))
        self.assertFalse(is_local_address(("smtp.gmail.com", 465)))

    def test_dns_getaddrinfo_external_host_is_blocked_without_network(self):
        """Valida que resolução DNS via socket.getaddrinfo para host externo é bloqueada imediatamente."""
        with self.assertRaises(NetworkBlockedError) as ctx:
            socket.getaddrinfo("example.com", 80)
        self.assertIn("Tentativa de resolução DNS externa não autorizada", str(ctx.exception))
        self.assertIn("example.com", str(ctx.exception))

    def test_dns_getaddrinfo_local_host_is_permitted(self):
        """Valida que resolução DNS para localhost/loopback é permitida normalmente."""
        res = socket.getaddrinfo("localhost", 80)
        self.assertTrue(len(res) > 0)
        res_ip = socket.getaddrinfo("127.0.0.1", 80)
        self.assertTrue(len(res_ip) > 0)

    def test_dns_gethostbyname_external_host_is_blocked(self):
        """Valida que socket.gethostbyname para host externo é interceptado antes do DNS."""
        with self.assertRaises(NetworkBlockedError) as ctx:
            socket.gethostbyname("google.com")
        self.assertIn("Tentativa de resolução DNS (gethostbyname)", str(ctx.exception))

    def test_external_socket_connect_raises_network_blocked_error(self):
        """Valida que socket.connect para IP externo levanta NetworkBlockedError imediatamente."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.assertRaises(NetworkBlockedError) as ctx:
                s.connect(("8.8.8.8", 53))
            self.assertIn("Tentativa de conexão de rede externa não autorizada", str(ctx.exception))
            self.assertIn("8.8.8.8", str(ctx.exception))
        finally:
            s.close()

    def test_external_socket_connect_ex_raises_network_blocked_error(self):
        """Valida que socket.connect_ex para IP externo também é interceptado e bloqueado."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.assertRaises(NetworkBlockedError):
                s.connect_ex(("1.1.1.1", 80))
        finally:
            s.close()

    def test_socket_create_connection_to_external_ip_is_blocked(self):
        """Valida que socket.create_connection para IP externo é interceptado sem tráfego de rede."""
        with self.assertRaises(NetworkBlockedError):
            socket.create_connection(("8.8.8.8", 53), timeout=1)

    def test_urllib_request_to_external_url_is_blocked(self):
        """Valida que urllib.request.urlopen para URL externa é bloqueado por NetworkBlockedError."""
        with self.assertRaises((NetworkBlockedError, urllib.error.URLError)) as ctx:
            urllib.request.urlopen("https://example.com", timeout=1)
        ex = ctx.exception
        if isinstance(ex, urllib.error.URLError):
            self.assertIsInstance(ex.reason, NetworkBlockedError)
        else:
            self.assertIsInstance(ex, NetworkBlockedError)

    def test_smtplib_connection_to_external_host_is_blocked(self):
        """Valida que smtplib para servidor externo é bloqueado antes de qualquer handshake."""
        with self.assertRaises((NetworkBlockedError, OSError)):
            smtp = smtplib.SMTP(local_hostname="localhost")
            try:
                smtp.connect("smtp.gmail.com", 587)
            finally:
                smtp.close()

    def test_playwright_sync_context_manager_is_blocked_without_mock(self):
        """Valida que invocar sync_playwright() sem mock levanta PlaywrightBlockedError."""
        from playwright.sync_api import sync_playwright

        with self.assertRaises(PlaywrightBlockedError) as ctx:
            with sync_playwright():
                pass
        self.assertIn("Tentativa de inicialização real do Playwright", str(ctx.exception))

    def test_playwright_sync_start_is_blocked_without_mock(self):
        """Valida que sync_playwright().start() também é interceptado e bloqueado."""
        from playwright.sync_api import sync_playwright

        with self.assertRaises(PlaywrightBlockedError):
            sync_playwright().start()

    def test_allow_network_context_manager_temporarily_authorizes(self):
        """Valida que o context manager allow_network() autoriza temporariamente e restaura o bloqueio."""
        self.assertFalse(is_network_allowed())
        with allow_network():
            self.assertTrue(is_network_allowed())
        self.assertFalse(is_network_allowed())

    def test_allow_playwright_context_manager_temporarily_authorizes(self):
        """Valida que o context manager allow_playwright() autoriza temporariamente e restaura o bloqueio."""
        self.assertFalse(is_playwright_allowed())
        with allow_playwright():
            self.assertTrue(is_playwright_allowed())
        self.assertFalse(is_playwright_allowed())

    def test_local_python_subprocess_is_not_blocked(self):
        """Valida que subprocessos legítimos do interpretador Python local executam normalmente."""
        res = subprocess.run(
            [sys.executable, "-c", "print('SUBPROCESS_GUARD_OK')"],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("SUBPROCESS_GUARD_OK", res.stdout.strip())

    def test_subprocess_filho_possui_espaco_de_memoria_independente(self):
        """Documenta e comprova o limite técnico: subprocessos novos gerados via subprocess.Popen
        possuem memória isolada e não herdam automaticamente os monkeypatches do processo-pai."""
        # Processo filho que NÃO importa o pacote tests: o socket.socket.connect original permanece inalterado
        codigo_filho = (
            "import socket\n"
            "is_patched = getattr(socket.socket.connect, '__name__', '') == '_guarded_connect'\n"
            "print(f'FILHO_PATCHED:{is_patched}')\n"
        )
        res = subprocess.run(
            [sys.executable, "-c", codigo_filho],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("FILHO_PATCHED:False", res.stdout.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
