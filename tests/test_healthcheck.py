import unittest
from unittest.mock import patch, MagicMock
from src.core.config import config
from src.core.healthcheck import (
    check_openai,
    check_email,
    check_github,
    check_huggingface,
    check_twitter,
    executar_healthcheck
)

class TestHealthcheck(unittest.TestCase):

    @patch.object(config, "OPENAI_API_KEY", "sk-mock-fictional-openai-key-for-unit-test")
    @patch("urllib.request.urlopen")
    def test_check_openai_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        ok, msg = check_openai()
        self.assertTrue(ok)
        self.assertIn("200 OK", msg)

    @patch.object(config, "OPENAI_API_KEY", "")
    def test_check_openai_missing_key(self):
        ok, msg = check_openai()
        self.assertFalse(ok)
        self.assertIn("não configurada", msg)

    @patch("urllib.request.urlopen")
    def test_check_github_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        ok, msg = check_github()
        self.assertTrue(ok)

    @patch("urllib.request.urlopen")
    def test_check_huggingface_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        ok, msg = check_huggingface()
        self.assertTrue(ok)

    @patch.object(config, "get_twitter_credentials")
    def test_check_twitter_validation(self, mock_get_creds):
        mock_get_creds.return_value = ("mock_auth_token_longer_than_20_chars", "mock_ct0_value")
        ok, msg = check_twitter()
        self.assertTrue(ok)
        self.assertIn("auth_token", msg)

    @patch.object(config, "get_twitter_credentials")
    def test_check_twitter_missing_credentials(self, mock_get_creds):
        mock_get_creds.return_value = ("", "")
        ok, msg = check_twitter()
        self.assertFalse(ok)
        self.assertIn("ausente", msg)

    @patch.object(config, "get_email_credentials")
    @patch("smtplib.SMTP_SSL")
    def test_check_email_success(self, mock_smtp, mock_get_creds):
        mock_get_creds.return_value = ("sender@gmail.com", "mock_app_password_123", "dest@domain.com")
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        ok, msg = check_email()
        self.assertTrue(ok)
        self.assertIn("Login SMTP OK", msg)

    @patch.object(config, "get_email_credentials")
    def test_check_email_missing_credentials(self, mock_get_creds):
        mock_get_creds.return_value = ("", "", "")
        ok, msg = check_email()
        self.assertFalse(ok)
        self.assertIn("incompletas", msg)

    @patch("src.core.healthcheck.check_openai", return_value=(True, "OK"))
    @patch("src.core.healthcheck.check_email", return_value=(True, "OK"))
    @patch("src.core.healthcheck.check_twitter", return_value=(True, "OK"))
    @patch("src.core.healthcheck.check_github", return_value=(True, "OK"))
    @patch("src.core.healthcheck.check_huggingface", return_value=(True, "OK"))
    def test_executar_healthcheck_all_ok(self, *mocks):
        res = executar_healthcheck()
        self.assertTrue(res)

if __name__ == "__main__":
    unittest.main()
