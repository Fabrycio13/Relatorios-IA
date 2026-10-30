import unittest
from unittest.mock import patch
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
        self.assertIn("DICA DO AUTOR", html.upper())
        self.assertIn("Destaques Principais do Dia", html)
        self.assertIn("Ferramentas Open-Source", html)
        self.assertIn("Papers em Destaque", html)

    def test_format_inline_markdown_links_target_blank_and_clickable(self):
        """Valida que links Markdown são convertidos em âncoras HTML clicáveis com target=_blank e rel seguro."""
        sample = "Veja o post original ([Post](https://x.com/svpino/status/12345)) e o repo ([GitHub](https://github.com/svpino/repo))."
        rendered = format_inline(sample)

        self.assertIn('<a href="https://x.com/svpino/status/12345" target="_blank" rel="noopener noreferrer"', rendered)
        self.assertIn('>Post</a>', rendered)
        self.assertIn('<a href="https://github.com/svpino/repo" target="_blank" rel="noopener noreferrer"', rendered)
        self.assertIn('>GitHub</a>', rendered)

    def test_render_bento_email_renders_clickable_post_links_in_all_x_sections(self):
        """Valida que o renderizador Bento Grid preserva links clicáveis de posts do X em bullets e cabeçalhos de notícias."""
        sample_md = """
## 📌 Destaques Principais do Dia
- **Novo Modelo Aberto:** Lançamento de pesos abertos com raciocínio ([Post](https://x.com/author1/status/111)).

---

## 🚀 Ferramentas Open-Source, Visão & Ambientes 3D
* **Framework 3D (Ferramentas):** Novo toolkit para reconstrução neural ([Post](https://x.com/author2/status/222) | [GitHub](https://github.com/org/toolkit)):
  - Suporte completo a pipeline de visão computacional ([Doc](https://example.com/doc)).

---

## 🎯 Radar Perfis de Referência
* **Santiago Valdarrama (CLI Tools):** Discussão sobre automação em Python ([Post](https://x.com/svpino/status/333))
"""
        html = render_bento_email(sample_md)

        # Valida que todos os links de posts do X estão presentes como links HTML clicáveis
        self.assertIn('href="https://x.com/author1/status/111"', html)
        self.assertIn('href="https://x.com/author2/status/222"', html)
        self.assertIn('href="https://x.com/svpino/status/333"', html)
        self.assertIn('href="https://github.com/org/toolkit"', html)
        self.assertIn('href="https://example.com/doc"', html)

        # Valida abertura segura em nova aba
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener noreferrer"', html)

        # Valida integridade do Bento Grid
        self.assertIn('class="newspaper-section"', html)
        self.assertIn('Destaques Principais do Dia', html)
        self.assertIn('Radar Perfis de Referência', html)

    def test_render_bento_email_dica_do_autor_paragrafo_sem_ul_li(self):
        """Valida que a Dica do Autor renderiza um parágrafo justificado estilizado, sem tags <ul> ou <li>."""
        sample_md = """
## 💡 Dica do Autor: O que levar para o código hoje
A convergência do dia aponta para a consolidação de coding agents determinísticos e compressão semântica de bases vetoriais. O foco de engenharia migra da experimentação dispersa para a garantia de auditabilidade e custo previsível de execução.
"""
        html = render_bento_email(sample_md)

        # Valida cabeçalho do box editorial normalizado
        self.assertIn("DICA DO AUTOR: O QUE LEVAR PARA O CÓDIGO HOJE", html.upper())

        # Valida que o texto está contido em tag <p> com tipografia editorial serifada
        self.assertIn('<p style="margin: 0; font-size: 14.5px; line-height: 1.65; color: #713f12; font-family: \'Times New Roman\', Georgia, serif; text-align: justify; font-weight: 400;">', html)
        self.assertIn("A convergência do dia aponta para a consolidação", html)

        # Valida que NÃO foram criadas listas não-ordenadas no box do takeaway
        takeaway_block = html[html.find('id="takeaway"'):html.find('class="footer-container"')] if 'class="footer-container"' in html else html[html.find('id="takeaway"'):]
        self.assertNotIn("<ul", takeaway_block)
        self.assertNotIn("<li", takeaway_block)

        # Valida âncoras de navegação rápida
        self.assertIn('id="takeaway"', html)
        self.assertIn('id="dica-do-autor"', html)

    def test_render_bento_email_takeaway_retrocompatibilidade_com_bullets_legados(self):
        """Valida retrocompatibilidade: relatórios antigos contendo marcadores no Takeaway continuam renderizando graciosamente."""
        sample_legacy_md = """
## 💡 Takeaway Prático de Engenharia do Dia
- **Padrão em Foco:** Agentes locais com MCP estão substituindo pipelines caros.
- **Recomendação Prática:** Priorize ferramentas que rodam localmente com CPU.
"""
        html = render_bento_email(sample_legacy_md)
        self.assertIn("DICA DO AUTOR", html.upper())
        self.assertIn("Agentes locais com MCP", html)
        self.assertIn("Priorize ferramentas", html)


    @patch("src.delivery.renderer.resolver_banner_do_dia")
    def test_render_bento_email_com_banner_dinamico_e_legenda(self, mock_resolver):
        """Valida que render_bento_email injeta corretamente o banner e legenda dinâmicos resolvidos."""
        from src.delivery.banner_selector import BannerInfo
        from datetime import datetime

        mock_resolver.return_value = BannerInfo(
            banner_url="https://example.com/halloween.jpg",
            full_hd_url="https://example.com/halloween_hd.jpg",
            caption="Edição Especial de Halloween Teste",
            is_special_date=True,
            filename="halloween.jpg"
        )

        sample_md = "## 📌 Destaques\n- **Novidade:** Modelo aberto."
        html = render_bento_email(sample_md, data_envio=datetime(2026, 10, 31))

        self.assertIn("https://example.com/halloween.jpg", html)
        self.assertIn("https://example.com/halloween_hd.jpg", html)
        self.assertIn("Edição Especial de Halloween Teste", html)
        mock_resolver.assert_called_once_with(data_envio=datetime(2026, 10, 31))

    def test_render_bento_email_chamada_padrao_renderiza_castelo_classico(self):
        """Valida retrocompatibilidade: chamada sem data_envio renderiza com sucesso o castelo clássico."""
        from src.core.config import HEADER_BANNER_URL

        sample_md = "## 📌 Destaques\n- **Novidade:** Teste de compatibilidade."
        html = render_bento_email(sample_md)

        self.assertIn(HEADER_BANNER_URL, html)
        self.assertIn("Castelo da Engenharia de Agentes", html)


    @patch("src.delivery.renderer.resolver_banner_do_dia")
    def test_render_bento_email_escapa_caracteres_especiais_na_legenda(self, mock_resolver):
        """Valida que render_bento_email aplica html.escape com quote=True na legenda do banner,
        garantindo segurança contra injeção e integridade sintática do atributo alt e do texto visível."""
        from src.delivery.banner_selector import BannerInfo
        from datetime import datetime

        legenda_com_caracteres_especiais = 'Legenda com "aspas duplas", <tags> & símbolos especiais'
        mock_resolver.return_value = BannerInfo(
            banner_url="https://example.com/banner.jpg",
            full_hd_url="https://example.com/banner_hd.jpg",
            caption=legenda_com_caracteres_especiais,
            is_special_date=False,
            filename="banner.jpg"
        )

        sample_md = "## 📌 Destaques\n- **Novidade:** Teste de escape seguro."
        html = render_bento_email(sample_md, data_envio=datetime(2026, 10, 29))

        # 1. Valida escape completo no atributo alt (incluindo aspas com &quot;)
        self.assertIn('&quot;aspas duplas&quot;', html)
        self.assertIn('&lt;tags&gt;', html)
        self.assertIn('&amp; símbolos especiais', html)

        # 2. Garante que as tags e aspas brutas não foram injetadas sem escape
        self.assertNotIn('<tags>', html)
        alt_trecho = html[html.find('alt='):html.find('width="680"')]
        self.assertNotIn('"aspas duplas"', alt_trecho)


    @patch("src.delivery.renderer.resolver_banner_do_dia")
    def test_render_bento_email_link_hd_e_title_dinamico(self, mock_resolver):
        """Valida que o link <a> do banner aponta para full_hd_url e que o atributo title
        reflete dinamicamente a legenda da imagem com escape seguro."""
        from src.delivery.banner_selector import BannerInfo
        from datetime import datetime

        mock_resolver.return_value = BannerInfo(
            banner_url="https://example.com/banner_rotativo_01.jpg",
            full_hd_url="https://example.com/banner_rotativo_01_hd.jpg",
            caption="A Grande Forja dos Compiladores: Código determinístico e modelos.",
            is_special_date=False,
            filename="banner_rotativo_01.jpg"
        )

        sample_md = "## 📌 Destaques\n- Teste de link HD."
        html = render_bento_email(sample_md, data_envio=datetime(2026, 10, 29))

        # 1. Valida que o link <a> aponta para a URL em alta resolução (full_hd_url) com target="_blank" e rel="noopener noreferrer"
        self.assertIn('<a href="https://example.com/banner_rotativo_01_hd.jpg" target="_blank" rel="noopener noreferrer"', html)

        # 2. Valida que o atributo title reflete dinamicamente o tema do banner
        self.assertIn('title="A Grande Forja dos Compiladores: Código determinístico e modelos. (Clique para abrir a imagem original em alta resolução)"', html)

        # 3. Valida que o atributo alt reflete a imagem
        self.assertIn('alt="Arte da Edição: A Grande Forja dos Compiladores: Código determinístico e modelos."', html)

    @patch("src.delivery.renderer.resolver_banner_do_dia")
    def test_render_bento_email_title_escapa_caracteres_especiais(self, mock_resolver):
        """Valida que o atributo title no link <a> escapa aspas e caracteres especiais."""
        from src.delivery.banner_selector import BannerInfo
        from datetime import datetime

        mock_resolver.return_value = BannerInfo(
            banner_url="https://example.com/banner.jpg",
            full_hd_url="https://example.com/banner_hd.jpg",
            caption='Tema "Especial" <IA> & Inovação',
            is_special_date=False,
            filename="banner.jpg"
        )

        sample_md = "## 📌 Destaques\n- Teste."
        html = render_bento_email(sample_md, data_envio=datetime(2026, 10, 29))

        # O title do link <a> deve conter aspas e tags escapadas
        title_trecho = html[html.find('<a href="https://example.com/banner_hd.jpg"'):html.find('<img src=')]
        self.assertIn('title="Tema &quot;Especial&quot; &lt;IA&gt; &amp; Inovação', title_trecho)
        self.assertNotIn('"Especial"', title_trecho)


if __name__ == "__main__":
    unittest.main()
