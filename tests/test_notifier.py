import unittest
from unittest.mock import patch
from src.core.notifier import notificar_windows

class TestNotifier(unittest.TestCase):

    @patch("subprocess.run")
    def test_notificar_windows(self, mock_run):
        notificar_windows("Teste", "Mensagem de teste")
        mock_run.assert_called_once()

if __name__ == "__main__":
    unittest.main()
