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

    def test_format_inline_micro_badges(self):
        sample = "Lançamento de ferramenta [MCP] com código [Código] e artigo [Paper] [Novo]."
        rendered = format_inline(sample)
        self.assertIn("MCP</span>", rendered)
        self.assertIn("CÓDIGO</span>", rendered)
        self.assertIn("PAPER</span>", rendered)
        self.assertIn("NOVO</span>", rendered)

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

---

## 💡 Takeaway Prático de Engenharia do Dia
- **Padrão em Foco:** Agentes e MCPs locais estão substituindo pipelines em nuvem caros.
- **Recomendação Prática:** Priorize ferramentas que rodam localmente com CPU.
"""
        html = render_bento_email(sample_md)

        # Valida estrutura HTML e responsividade
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn('<meta name="viewport"', html)
        self.assertIn('class="main-container"', html)

        # Valida contêiner condicional MSO para Outlook Desktop
        self.assertIn("<!--[if mso]>", html)
        self.assertIn('width="680"', html)

        # Valida âncoras de navegação rápida
        self.assertIn('href="#destaques"', html)
        self.assertIn('href="#radar-x"', html)
        self.assertIn('href="#github-trending"', html)
        self.assertIn('href="#papers"', html)
        self.assertIn('href="#takeaway"', html)

        # Valida cards Bento Grid com IDs e Names (compatibilidade máxima com e-mails)
        self.assertIn('id="destaques"', html)
        self.assertIn('name="destaques"', html)
        self.assertIn('id="radar-x"', html)
        self.assertIn('name="radar-x"', html)
        self.assertIn('id="papers"', html)
        self.assertIn('name="papers"', html)
        self.assertIn('id="takeaway"', html)
        self.assertIn('name="takeaway"', html)
        self.assertIn("Takeaway Prático de Engenharia do Dia", html)
        self.assertIn("Destaques Principais do Dia", html)
        self.assertIn("Ferramentas Open-Source", html)
        self.assertIn("Papers em Destaque", html)

if __name__ == "__main__":
    unittest.main()
