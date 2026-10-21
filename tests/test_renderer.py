import unittest
from src.delivery.renderer import format_inline, render_bento_email

class TestRenderer(unittest.TestCase):

    def test_format_inline(self):
        sample = "Este é um **negrito**, este é um *itálico*, este é `código` e [link](https://example.com)."
        rendered = format_inline(sample)
        self.assertIn("<strong", rendered)
        self.assertIn("<em", rendered)
        self.assertIn("<code", rendered)
        self.assertIn('<a href="https://example.com"', rendered)

    def test_render_bento_email_structure(self):
        sample_md = """
## 📌 Destaques Principais do Dia
- Lançamento do novo modelo open-weight com raciocínio avançado.
- Ferramenta MCP para automação de tarefas.

---

## 1. 🚀 Ferramentas Open-Source, Visão & Ambientes 3D
* **[autor/repo](https://github.com/autor/repo)** — 🔥 1,5 mil likes, 200 reposts:
  - Descrição técnica do projeto em português.

---

## 📄 Papers em Destaque: Pesquisa & Estado da Arte (Hugging Face / ArXiv)
* **[Training the Whole Agent](https://huggingface.co/papers/123)** — 📄 **ArXiv: 123**
  - Proposta de treino conjunto de harness e modelo.
"""
        html = render_bento_email(sample_md)

        # Valida estrutura HTML e responsividade
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn('<meta name="viewport"', html)
        self.assertIn('class="main-container"', html)

        # Valida contêiner condicional MSO para Outlook Desktop
        self.assertIn("<!--[if mso]>", html)
        self.assertIn('width="680"', html)

        # Valida cards Bento Grid
        self.assertIn('class="bento-card"', html)
        self.assertIn("Destaques Principais do Dia", html)
        self.assertIn("Ferramentas Open-Source", html)
        self.assertIn("Papers em Destaque", html)

if __name__ == "__main__":
    unittest.main()
