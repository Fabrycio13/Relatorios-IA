import unittest
from pathlib import Path
from src.core.config import (
    BASE_DIR,
    DATA_DIR,
    REPORTS_DIR,
    LOGS_DIR,
    SCRIPTS_DIR,
    ASSETS_DIR,
    config
)

class TestConfig(unittest.TestCase):

    def test_paths_exist(self):
        self.assertTrue(BASE_DIR.exists())
        self.assertTrue(DATA_DIR.exists())
        self.assertTrue(REPORTS_DIR.exists())
        self.assertTrue(LOGS_DIR.exists())
        self.assertTrue(SCRIPTS_DIR.exists())
        self.assertTrue(ASSETS_DIR.exists())

    def test_email_credentials_retrieval(self):
        remetente, senha, destinatario = config.get_email_credentials()
        self.assertIsInstance(remetente, str)
        self.assertIsInstance(senha, str)
        self.assertIsInstance(destinatario, str)
        self.assertIn("@", remetente)
        self.assertIn("@", destinatario)

    def test_ultimo_relatorio_retrieval(self):
        ultimo = config.obter_ultimo_relatorio()
        if ultimo:
            self.assertTrue(ultimo.exists())
            self.assertTrue(ultimo.name.startswith("Resumo_IA_"))

if __name__ == "__main__":
    unittest.main()
