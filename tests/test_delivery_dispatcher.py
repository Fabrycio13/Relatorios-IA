import tempfile
import unittest
from pathlib import Path

from src.delivery.base import DeliveryChannel
from src.delivery.dispatcher import despachar_relatorio


class MockDeliveryChannel:
    """Canal em memória para validação sem tocar socket ou navegador."""
    def __init__(self, succeed: bool = True):
        self.succeed = succeed
        self.delivered = False
        self.last_subject = ""
        self.last_html = ""
        self.last_recipient = ""
        self.last_plain = ""

    def deliver(self, subject: str, html_body: str, recipient: str, plain_text: str = "") -> bool:
        if not self.succeed:
            return False
        self.delivered = True
        self.last_subject = subject
        self.last_html = html_body
        self.last_recipient = recipient
        self.last_plain = plain_text
        return True


class TestDeliveryDispatcher(unittest.TestCase):

    def test_despachar_relatorio_com_canal_mock(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            rel_file = Path(tmp_dir) / "Resumo_IA_2026-10-27.md"
            rel_file.write_text("# Relatório Diário\nConteúdo de teste para Bento Grid.", encoding="utf-8")

            mock_channel = MockDeliveryChannel(succeed=True)
            sucesso = despachar_relatorio(
                caminho_relatorio=rel_file,
                channel=mock_channel,
                destinatario="fabrycio@teste.com"
            )

            self.assertTrue(sucesso)
            self.assertTrue(mock_channel.delivered)
            self.assertEqual(mock_channel.last_recipient, "fabrycio@teste.com")
            self.assertIn("Resumo Diário de IA", mock_channel.last_subject)
            self.assertIn("<!DOCTYPE html>", mock_channel.last_html)
            self.assertEqual(mock_channel.last_plain, "# Relatório Diário\nConteúdo de teste para Bento Grid.")

    def test_despachar_relatorio_arquivo_inexistente_retorna_false(self):
        mock_channel = MockDeliveryChannel(succeed=True)
        sucesso = despachar_relatorio(
            caminho_relatorio=Path("arquivo_inexistente_123.md"),
            channel=mock_channel
        )
        self.assertFalse(sucesso)
        self.assertFalse(mock_channel.delivered)

    def test_despachar_relatorio_canal_falha_retorna_false(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            rel_file = Path(tmp_dir) / "Resumo_IA_2026-10-27.md"
            rel_file.write_text("# Relatório", encoding="utf-8")

            mock_channel = MockDeliveryChannel(succeed=False)
            sucesso = despachar_relatorio(
                caminho_relatorio=rel_file,
                channel=mock_channel
            )
            self.assertFalse(sucesso)


if __name__ == "__main__":
    unittest.main()
