import base64
import re
import sys
import unittest
from unittest.mock import patch, MagicMock

from src.core.notifier import notificar_windows, _sanitizar_texto_toast


class TestNotifier(unittest.TestCase):

    def _extract_script_from_mock(self, mock_run: MagicMock) -> str:
        """Helper para extrair e decodificar o script PowerShell a partir do -EncodedCommand."""
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        enc_idx = cmd_args.index("-EncodedCommand") + 1
        encoded_b64 = cmd_args[enc_idx]
        return base64.b64decode(encoded_b64).decode("utf-16le")

    def _extract_decoded_text_nodes(self, ps_script: str) -> tuple[str, str]:
        """Extrai os valores decodificados de Base64 de $title e $msg do script gerado."""
        title_match = re.search(r"\$title\s*=\s*\[System\.Text\.Encoding\]::UTF8\.GetString\(\[Convert\]::FromBase64String\('([^']*)'\)\)", ps_script)
        msg_match = re.search(r"\$msg\s*=\s*\[System\.Text\.Encoding\]::UTF8\.GetString\(\[Convert\]::FromBase64String\('([^']*)'\)\)", ps_script)

        self.assertIsNotNone(title_match, "Expressão de extração de $title não encontrada no script.")
        self.assertIsNotNone(msg_match, "Expressão de extração de $msg não encontrada no script.")

        title = base64.b64decode(title_match.group(1)).decode("utf-8")
        msg = base64.b64decode(msg_match.group(1)).decode("utf-8")
        return title, msg

    @patch.object(sys, "platform", "win32")
    @patch("subprocess.run")
    def test_notificar_windows_standard_call(self, mock_run):
        notificar_windows("Teste", "Mensagem de teste")
        mock_run.assert_called_once()
        ps_script = self._extract_script_from_mock(mock_run)
        title, msg = self._extract_decoded_text_nodes(ps_script)
        self.assertEqual(title, "Teste")
        self.assertEqual(msg, "Mensagem de teste")

    @patch.object(sys, "platform", "win32")
    @patch("subprocess.run")
    def test_notificar_windows_single_quotes_and_apostrophes(self, mock_run):
        """Valida que mensagens contendo aspas simples e apóstrofos não quebram o script."""
        titulo = "Erro no pipeline: 'KeyError'"
        mensagem = "Falha em dict['user_id']. It's an unexpected error with single' quotes."

        notificar_windows(titulo, mensagem)
        ps_script = self._extract_script_from_mock(mock_run)
        title, msg = self._extract_decoded_text_nodes(ps_script)

        self.assertEqual(title, titulo)
        self.assertEqual(msg, mensagem)

    @patch.object(sys, "platform", "win32")
    @patch("subprocess.run")
    def test_notificar_windows_double_quotes_and_powershell_vars(self, mock_run):
        """Valida que aspas duplas, variáveis PowerShell ($var) e crases (`) não sofrem injeção."""
        titulo = 'Alerta: "Falha Crítica"'
        mensagem = 'O processo `$proc retornou $env:PATH e texto "entre aspas"'

        notificar_windows(titulo, mensagem)
        ps_script = self._extract_script_from_mock(mock_run)
        title, msg = self._extract_decoded_text_nodes(ps_script)

        self.assertEqual(title, titulo)
        self.assertEqual(msg, mensagem)

    @patch.object(sys, "platform", "win32")
    @patch("subprocess.run")
    def test_notificar_windows_emojis_and_xml_entities(self, mock_run):
        """Valida preservação integral de emojis UTF-8 e caracteres especiais XML (<, >, &)."""
        titulo = "🤖 Diário de IA: Preview 👁️"
        mensagem = "Destaques <v1.0> & novos repositórios: 10 > 5! 🔥 ✅"

        notificar_windows(titulo, mensagem)
        ps_script = self._extract_script_from_mock(mock_run)
        title, msg = self._extract_decoded_text_nodes(ps_script)

        self.assertEqual(title, titulo)
        self.assertEqual(msg, mensagem)

    @patch.object(sys, "platform", "win32")
    @patch("subprocess.run")
    def test_notificar_windows_line_breaks(self, mock_run):
        """Valida que quebras de linha em mensagens são preservadas sem quebrar sintaxe do script."""
        titulo = "Relatório Concluído"
        mensagem = "Linha 1: Coleta OK\nLinha 2: Resumo OK\r\nLinha 3: Envio OK"

        notificar_windows(titulo, mensagem)
        ps_script = self._extract_script_from_mock(mock_run)
        title, msg = self._extract_decoded_text_nodes(ps_script)

        self.assertEqual(title, titulo)
        self.assertEqual(msg, mensagem)

    @patch.object(sys, "platform", "win32")
    @patch("subprocess.run")
    def test_notificar_windows_empty_and_none(self, mock_run):
        """Valida robustez diante de strings vazias ou valores None."""
        notificar_windows(None, None)  # type: ignore
        ps_script = self._extract_script_from_mock(mock_run)
        title, msg = self._extract_decoded_text_nodes(ps_script)

        self.assertEqual(title, "")
        self.assertEqual(msg, "")

    def test_sanitizar_texto_toast_removes_invalid_xml_control_characters(self):
        """Valida que caracteres de controle inválidos em XML (ex: null byte) são removidos."""
        entrada = "Texto\x00com\x07caracteres\x1bde\x1fcontrole\ne\ttab"
        saida = _sanitizar_texto_toast(entrada)
        self.assertEqual(saida, "Textocomcaracteresdecontrole\ne\ttab")

    @patch("subprocess.run")
    def test_notificar_windows_skips_on_non_win32(self, mock_run):
        """Valida que a notificação é ignorada graciosamente em plataformas que não sejam Windows."""
        for non_win in ("linux", "darwin", "freebsd"):
            with patch.object(sys, "platform", non_win):
                notificar_windows("Titulo", "Mensagem")
                mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
