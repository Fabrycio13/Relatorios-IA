import smtplib
import ssl
import unittest
from unittest.mock import patch
from src.core.smtp import conectar_smtp_ssl


class FakeSMTPServer(smtplib.SMTP):
    """Servidor SMTP simulado que herda de smtplib.SMTP para exercer a mecânica nativa de __exit__ do CPython."""

    def __init__(
        self,
        quit_code: int = 221,
        quit_msg: bytes = b"2.0.0 Bye",
        quit_exception: Exception | None = None,
        auth_error: bool = False,
    ):
        self.quit_code = quit_code
        self.quit_msg = quit_msg
        self.quit_exception = quit_exception
        self.auth_error = auth_error
        self.docmd_calls: list[tuple[str, str]] = []
        self.close_calls: int = 0
        self.login_calls: list[tuple[str, str]] = []

    def docmd(self, cmd: str, args: str = ""):
        self.docmd_calls.append((cmd, args))
        if cmd == "QUIT" and self.quit_exception is not None:
            raise self.quit_exception
        return (self.quit_code, self.quit_msg)

    def close(self):
        self.close_calls += 1

    def login(self, user: str, password: str):
        self.login_calls.append((user, password))
        if self.auth_error:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted.")


class TestConectarSMTPSSL(unittest.TestCase):
    """Testes unitários de validação, ciclo de vida e semântica de protocolo de conectar_smtp_ssl."""

    @patch("smtplib.SMTP_SSL")
    def test_cenario_1_encerramento_normal_envia_quit_e_fecha_socket(self, mock_smtp_ssl):
        """Cenário 1: Saída normal sem erros; verifica comando QUIT com 221 e socket fechado via finally."""
        fake_server = FakeSMTPServer(quit_code=221)
        mock_smtp_ssl.return_value = fake_server

        with conectar_smtp_ssl("usuario@gmail.com", "senha_secreta") as server:
            self.assertIs(server, fake_server)

        self.assertEqual(fake_server.docmd_calls, [("QUIT", "")])
        self.assertEqual(fake_server.close_calls, 1)
        self.assertEqual(fake_server.login_calls, [("usuario@gmail.com", "senha_secreta")])

    @patch("smtplib.SMTP_SSL")
    def test_cenario_2_falha_autenticacao_preserva_excecao_e_fecha_socket(self, mock_smtp_ssl):
        """Cenário 2: Erro em login(); context manager envia QUIT, fecha socket e propaga SMTPAuthenticationError."""
        fake_server = FakeSMTPServer(quit_code=221, auth_error=True)
        mock_smtp_ssl.return_value = fake_server

        with self.assertRaises(smtplib.SMTPAuthenticationError):
            with conectar_smtp_ssl("usuario@gmail.com", "senha_errada"):
                pass

        self.assertEqual(fake_server.docmd_calls, [("QUIT", "")])
        self.assertEqual(fake_server.close_calls, 1)

    @patch("smtplib.SMTP_SSL")
    def test_cenario_3_desconexao_ou_timeout_no_quit_e_suprimida_sem_vazamento(self, mock_smtp_ssl):
        """Cenário 3: SMTPServerDisconnected durante QUIT é suprimida pelo __exit__ e socket é fechado no finally."""
        fake_server = FakeSMTPServer(quit_exception=smtplib.SMTPServerDisconnected("Connection reset by peer"))
        mock_smtp_ssl.return_value = fake_server

        # Não deve levantar exceção ao sair do bloco with
        with conectar_smtp_ssl("usuario@gmail.com", "senha_secreta") as server:
            self.assertIs(server, fake_server)

        self.assertEqual(fake_server.docmd_calls, [("QUIT", "")])
        self.assertEqual(fake_server.close_calls, 1)

    @patch("smtplib.SMTP_SSL")
    def test_cenario_4_resposta_anomala_ao_quit_levanta_smtp_response_exception(self, mock_smtp_ssl):
        """Cenário 4: Resposta ao QUIT diferente de 221 levanta SMTPResponseException e fecha socket no finally."""
        fake_server = FakeSMTPServer(quit_code=500, quit_msg=b"5.5.2 Syntax error")
        mock_smtp_ssl.return_value = fake_server

        with self.assertRaises(smtplib.SMTPResponseException) as ctx:
            with conectar_smtp_ssl("usuario@gmail.com", "senha_secreta"):
                pass

        self.assertEqual(ctx.exception.smtp_code, 500)
        self.assertEqual(fake_server.docmd_calls, [("QUIT", "")])
        self.assertEqual(fake_server.close_calls, 1)

    @patch("smtplib.SMTP_SSL")
    def test_cenario_5_ressalva_d4_substituicao_de_excecao_quando_quit_retorna_erro_apos_falha_login(self, mock_smtp_ssl):
        """Cenário 5 (Ressalva D4): Resposta anômala ao QUIT (código != 221) após falha de login substitui a exceção original."""
        fake_server = FakeSMTPServer(quit_code=500, quit_msg=b"5.5.2 Syntax error", auth_error=True)
        mock_smtp_ssl.return_value = fake_server

        # Conforme a mecânica do CPython em __exit__, a exceção levantada em __exit__ substitui a exceção ativa
        with self.assertRaises(smtplib.SMTPResponseException) as ctx:
            with conectar_smtp_ssl("usuario@gmail.com", "senha_errada"):
                pass

        self.assertEqual(ctx.exception.smtp_code, 500)
        self.assertEqual(fake_server.docmd_calls, [("QUIT", "")])
        self.assertEqual(fake_server.close_calls, 1)

    @patch("smtplib.SMTP_SSL")
    def test_cenario_6_normalizacao_de_senha_remove_espacos(self, mock_smtp_ssl):
        """Cenário 6: Valida que senhas de aplicativo com espaços têm seus espaços removidos antes do login."""
        fake_server = FakeSMTPServer()
        mock_smtp_ssl.return_value = fake_server

        with conectar_smtp_ssl("usuario@gmail.com", "abcd efgh ijkl mnop"):
            pass

        self.assertEqual(fake_server.login_calls, [("usuario@gmail.com", "abcdefghijklmnop")])

    def test_cenario_7_rejeicao_de_parametros_invalidos(self):
        """Cenário 7: Remetente ou senha nula/vazia levantam ValueError antes de tentar conexão."""
        with self.assertRaises(ValueError):
            with conectar_smtp_ssl("", "senha"):
                pass

        with self.assertRaises(ValueError):
            with conectar_smtp_ssl("usuario@gmail.com", ""):
                pass

    @patch("smtplib.SMTP_SSL")
    def test_configuracao_ssl_estrita_com_certificados_e_hostname(self, mock_smtp_ssl):
        """Valida que smtplib.SMTP_SSL é invocado com parâmetros corretos e SSLContext ativo."""
        fake_server = FakeSMTPServer()
        mock_smtp_ssl.return_value = fake_server

        with conectar_smtp_ssl("user@gmail.com", "senha", host="smtp.custom.com", port=465, timeout=15):
            pass

        mock_smtp_ssl.assert_called_once()
        args, kwargs = mock_smtp_ssl.call_args
        self.assertEqual(args[0], "smtp.custom.com")
        self.assertEqual(args[1], 465)
        self.assertEqual(kwargs["timeout"], 15)

        ctx = kwargs["context"]
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)


if __name__ == "__main__":
    unittest.main()
