import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.delivery.base import (
    DeliveryChannel,
    EmailDeliveryChannel,
    FilePreviewDeliveryChannel
)


class TestDeliveryChannels(unittest.TestCase):

    def test_channels_satisfy_protocol(self):
        email_chan = EmailDeliveryChannel()
        preview_chan = FilePreviewDeliveryChannel(auto_open=False)

        self.assertIsInstance(email_chan, DeliveryChannel)
        self.assertIsInstance(preview_chan, DeliveryChannel)
        self.assertEqual(email_chan.name, "email")
        self.assertEqual(preview_chan.name, "preview")

    def test_file_preview_delivery_creates_utf8_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            preview_file = Path(tmp_dir) / "preview_test.html"
            channel = FilePreviewDeliveryChannel(output_path=preview_file, auto_open=False)

            sample_html = "<html><body><h1>Relatório Bento Grid & Acentuação: ção</h1></body></html>"
            sucesso = channel.deliver(
                subject="Teste",
                html_body=sample_html,
                recipient="destinatario@exemplo.com"
            )

            self.assertTrue(sucesso)
            self.assertTrue(preview_file.exists())
            conteudo = preview_file.read_text(encoding="utf-8")
            self.assertEqual(conteudo, sample_html)

    @patch("webbrowser.open")
    def test_file_preview_delivery_triggers_browser(self, mock_browser):
        with tempfile.TemporaryDirectory() as tmp_dir:
            preview_file = Path(tmp_dir) / "preview.html"
            channel = FilePreviewDeliveryChannel(output_path=preview_file, auto_open=True)

            sucesso = channel.deliver(
                subject="Teste Browser",
                html_body="<p>OK</p>",
                recipient="destinatario@exemplo.com"
            )

            self.assertTrue(sucesso)
            mock_browser.assert_called_once()
            args, _ = mock_browser.call_args
            self.assertIn("file:", args[0])

    @patch("src.delivery.base.config.get_email_credentials", return_value=("user@gmail.com", "valid_app_password_123", "dest@example.com"))
    @patch("smtplib.SMTP_SSL")
    def test_email_delivery_channel_success(self, mock_smtp, mock_creds):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        channel = EmailDeliveryChannel()
        sucesso = channel.deliver(
            subject="Assunto de Teste",
            html_body="<h1>Corpo HTML</h1>",
            recipient="test@example.com",
            plain_text="Texto simples"
        )

        self.assertTrue(sucesso)
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()
        args, _ = mock_server.sendmail.call_args
        self.assertEqual(args[1], ["test@example.com"])
        self.assertIn("Subject: Assunto de Teste", args[2])

    @patch("src.delivery.base.config.get_email_credentials")
    def test_email_delivery_channel_missing_credentials(self, mock_creds):
        mock_creds.return_value = ("user@gmail.com", "", "dest@example.com")
        channel = EmailDeliveryChannel()
        sucesso = channel.deliver("Assunto", "<h1>HTML</h1>", "dest@example.com")
        self.assertFalse(sucesso)


if __name__ == "__main__":
    unittest.main()
