import html.parser
import unittest
from unittest.mock import patch
from src.delivery.renderer import format_inline, render_bento_email, _is_safe_url

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

    @patch("src.delivery.renderer.resolver_banner_do_dia")
    def test_render_bento_email_chamada_padrao_renderiza_castelo_classico(self, mock_resolver):
        """Valida retrocompatibilidade: chamada sem data_envio renderiza com sucesso o castelo clássico."""
        from src.core.config import HEADER_BANNER_URL
        from src.delivery.banner_selector import _fallback_castelo_classico

        mock_resolver.return_value = _fallback_castelo_classico()
        sample_md = "## 📌 Destaques\n- **Novidade:** Teste de compatibilidade."
        html = render_bento_email(sample_md)

        self.assertIn(HEADER_BANNER_URL, html)
        self.assertIn("Castelo da Engenharia de Agentes", html)
        mock_resolver.assert_called_once_with(data_envio=None)


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



    def test_format_inline_escapes_raw_html_tags(self):
        """Valida que tags HTML brutas são convertidas em entidades inertes para evitar injeção de scripts."""
        sample = "Texto com <script>alert('xss')</script> e <img src='x' onerror='alert(1)'>."
        rendered = format_inline(sample)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", rendered)
        self.assertIn("&lt;img src=&#x27;x&#x27; onerror=&#x27;alert(1)&#x27;&gt;", rendered)

    def test_format_inline_rejects_unsafe_and_relative_url_schemes(self):
        """Valida que URLs sem esquema http/https válido ou sem hostname preservam apenas o texto seguro."""
        sample = (
            "Vetores: [XSS](javascript:alert(1)) e [Data](data:text/html,<script>evil</script>) "
            "e [Arquivo](file:///etc/passwd) e [Relativo](/docs/api) e [SemHost](https://)."
        )
        rendered = format_inline(sample)
        self.assertNotIn('href="javascript', rendered)
        self.assertNotIn('href="data:', rendered)
        self.assertNotIn('href="file:', rendered)
        self.assertNotIn('href="/docs/api"', rendered)
        self.assertNotIn('href="https://"', rendered)
        self.assertIn("XSS", rendered)
        self.assertIn("Data", rendered)
        self.assertIn("Arquivo", rendered)
        self.assertIn("Relativo", rendered)
        self.assertIn("SemHost", rendered)

    def test_format_inline_escapes_url_attributes_without_double_escaping(self):
        """Valida que query strings com aspas e ampersands são escapadas com quote=True sem gerar duplo escape."""
        sample = 'Link legítimo: [Busca](https://example.com/search?q="termo"&categoria=ia).'
        rendered = format_inline(sample)
        self.assertIn('href="https://example.com/search?q=&quot;termo&quot;&amp;categoria=ia"', rendered)
        self.assertNotIn("&amp;amp;", rendered)

    def test_render_bento_email_escapes_section_titles_and_raw_html(self):
        """Valida que títulos dinâmicos de seções e itens não confiáveis são escapados no HTML final."""
        sample_md = """
## 🚀 <script>alert('xss')</script> Seção Segura
* **[Injeção](javascript:alert(2))** — 🔥 100 likes:
  - Descrição segura com <iframe src='evil.com'></iframe>.
"""
        html = render_bento_email(sample_md)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn('href="javascript', html)
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", html)
        self.assertIn("&lt;iframe src=&#x27;evil.com&#x27;&gt;&lt;/iframe&gt;", html)
        self.assertIn("Injeção", html)

    def test_render_bento_email_avoids_double_escape_on_text_and_accents(self):
        """Valida que caracteres acentuados em português e conectivos comerciais não sofrem duplo escape."""
        sample_md = """
## 📌 Destaques Principais do Dia
- **Inovação & Eficiência:** Aplicação de modelos para automação e acentuação (Atenção, Ação, Épica).
"""
        html = render_bento_email(sample_md)
        self.assertIn("novação &amp; Eficiência", html)
        self.assertNotIn("&amp;amp;", html)
        self.assertIn("Atenção, Ação, Épica", html)

    def test_format_inline_rejects_malformed_authorities_and_invalid_ports(self):
        """Valida que URLs com portas fora do intervalo (0-65535), não-numéricas ou autoridades malformadas são rejeitadas."""
        sample = (
            "Malformadas: [PortaAlta](https://example.com:9999999) e [PortaTexto](https://example.com:abc) "
            "e [SemHostComPorta](https://:8080) e [Arroba](https://@) e [IPv6Quebrado](http://[invalid-ipv6) "
            "e [ValidaComPorta](https://example.com:8080/caminho)."
        )
        rendered = format_inline(sample)
        self.assertNotIn('href="https://example.com:9999999', rendered)
        self.assertNotIn('href="https://example.com:abc', rendered)
        self.assertNotIn('href="https://:8080', rendered)
        self.assertNotIn('href="https://@', rendered)
        self.assertNotIn('href="http://[invalid-ipv6', rendered)
        self.assertIn('<a href="https://example.com:8080/caminho"', rendered)
        self.assertIn("PortaAlta", rendered)
        self.assertIn("PortaTexto", rendered)
        self.assertIn("SemHostComPorta", rendered)
        self.assertIn("Arroba", rendered)
        self.assertIn("IPv6Quebrado", rendered)


    def test_render_bento_email_sanitizes_github_trending_and_papers_descriptions(self):
        """Valida que descrições de cards do GitHub Trending e Papers ArXiv sofrem sanitização completa."""
        sample_md = """
## 🔥 GitHub Trending: Repositórios de IA em Alta no Dia
* **[autor/repo-seguro](https://github.com/autor/repo-seguro)** ⭐ **1.200** (Python)
  - Descrição com payload: <script>alert('xss-gh-desc')</script> e <img src=x onerror=alert('xss-img')>.
  - Outra linha com link perigoso: [Ataque](javascript:alert('xss-link')).

---

## 📄 Papers em Destaque: Pesquisa & Estado da Arte (Hugging Face / ArXiv)
* **[Paper de IA](https://arxiv.org/abs/2610.12345)** 📄 **ArXiv: 2610.12345**
  - Resumo contendo <iframe src='https://evil.com'></iframe> e <svg/onload=alert('svg')>.
  - Referência maliciosa: [PaperEvil](data:text/html,<script>evil</script>).
"""
        html = render_bento_email(sample_md)

        # 1. Valida ausência total de tags ativas
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("<svg/onload", html)
        self.assertNotIn('href="javascript', html)
        self.assertNotIn('href="data:', html)

        # 2. Valida escape seguro das descrições nos dois componentes
        self.assertIn("&lt;script&gt;alert(&#x27;xss-gh-desc&#x27;)&lt;/script&gt;", html)
        self.assertIn("&lt;img src=x onerror=alert(&#x27;xss-img&#x27;)&gt;", html)
        self.assertIn("&lt;iframe src=&#x27;https://evil.com&#x27;&gt;&lt;/iframe&gt;", html)
        self.assertIn("&lt;svg/onload=alert(&#x27;svg&#x27;)&gt;", html)

        # 3. Valida preservação de textos seguros sem o link malicioso
        self.assertIn("Ataque", html)
        self.assertIn("PaperEvil", html)

    def test_format_inline_rejects_syntactically_invalid_hostnames(self):
        """Valida que URLs com hostnames sintaticamente inválidos são rejeitadas conforme RFC 1123/IPv4/IPv6."""
        sample = (
            "Hostnames inválidos: [Espaco](https://example .com) e [DoisPontos](https://example..com) "
            "e [PontoInicio](https://.example.com) e [HifenInicio](https://-example.com) "
            "e [HifenFim](https://example-.com) e [IPv4ForaRange](https://256.256.256.256) "
            "e [Tags](https://ex<am>ple.com) e [Valido](https://sub.domain.example.com/ok)."
        )
        rendered = format_inline(sample)

        self.assertNotIn('href="https://example .com', rendered)
        self.assertNotIn('href="https://example..com', rendered)
        self.assertNotIn('href="https://.example.com', rendered)
        self.assertNotIn('href="https://-example.com', rendered)
        self.assertNotIn('href="https://example-.com', rendered)
        self.assertNotIn('href="https://256.256.256.256', rendered)
        self.assertNotIn('href="https://ex<am>ple.com', rendered)
        self.assertIn('<a href="https://sub.domain.example.com/ok"', rendered)
        self.assertIn("Espaco", rendered)
        self.assertIn("DoisPontos", rendered)
        self.assertIn("PontoInicio", rendered)
        self.assertIn("HifenInicio", rendered)
        self.assertIn("HifenFim", rendered)
        self.assertIn("IPv4ForaRange", rendered)
        self.assertIn("Tags", rendered)

    def test_is_safe_url_rejects_userinfo_in_authority(self):
        """Valida que URLs com userinfo no netloc/autoridade (@) são rejeitadas contra phishing visual,
        enquanto URLs com @ exclusivamente no path ou query string são aceitas normalmente."""
        # 1. URLs com userinfo na autoridade devem ser rejeitadas
        self.assertFalse(_is_safe_url("https://exemplo-confiavel.com@evil.com"))
        self.assertFalse(_is_safe_url("https://usuario:senha@exemplo.com"))
        self.assertFalse(_is_safe_url("https://exemplo.com@@evil.com"))

        # 2. URLs legítimas com @ no path ou query string devem ser aceitas
        self.assertTrue(_is_safe_url("https://twitter.com/@usuario"))
        self.assertTrue(_is_safe_url("https://example.com/search?q=@mention"))
        self.assertTrue(_is_safe_url("https://example.com/profile?email=user@example.com&ref=123"))

    def test_format_inline_rejects_userinfo_and_preserves_legit_at_in_path_query(self):
        """Valida que format_inline descarta a tag <a> para URLs com userinfo (@ na autoridade)
        preservando apenas o texto visível, mas renderiza normalmente links legítimos com @ no path/query."""
        sample = (
            "Links phishing: [Phish1](https://exemplo-confiavel.com@evil.com) e "
            "[Creds](https://usuario:senha@exemplo.com) e [DuploArroba](https://exemplo.com@@evil.com). "
            "Links legítimos: [Perfil](https://twitter.com/@usuario) e "
            "[Busca](https://example.com/search?q=@mention)."
        )
        rendered = format_inline(sample)

        # URLs com userinfo devem ser desarmadas (sem tag <a>)
        self.assertNotIn('href="https://exemplo-confiavel.com@evil.com', rendered)
        self.assertNotIn('href="https://usuario:senha@exemplo.com', rendered)
        self.assertNotIn('href="https://exemplo.com@@evil.com', rendered)
        self.assertIn("Phish1", rendered)
        self.assertIn("Creds", rendered)
        self.assertIn("DuploArroba", rendered)

        # URLs legítimas com @ em path/query devem manter <a href="...">
        self.assertIn('<a href="https://twitter.com/@usuario"', rendered)
        self.assertIn('<a href="https://example.com/search?q=@mention"', rendered)
        self.assertIn("Perfil", rendered)
        self.assertIn("Busca", rendered)




class XSSCanaryParser(html.parser.HTMLParser):
    """Parser de teste para inspeção estrutural do HTML gerado pelo renderizador."""

    PROHIBITED_TAGS = {
        "script", "iframe", "object", "embed", "svg", "math",
        "base", "form", "button", "input", "link"
    }

    ALLOWED_TEMPLATE_TAGS = {
        "html", "head", "meta", "title", "style", "body",
        "table", "tr", "td", "div", "span", "h1", "h2", "p",
        "ul", "li", "strong", "em", "code", "a", "img"
    }

    EXPECTED_STATIC_METAS = [
        {"charset": "utf-8"},
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"},
        {"name": "color-scheme", "content": "light"},
        {"name": "supported-color-schemes", "content": "light"},
    ]

    def __init__(self):
        super().__init__()
        self.html_opened: bool = False
        self.html_closed: bool = False
        self.head_opened: bool = False
        self.head_closed: bool = False
        self.body_opened: bool = False
        self.body_closed: bool = False
        self.in_head: bool = False
        self.in_body: bool = False
        self.in_style_block: bool = False

        self.matched_metas: list[dict[str, str]] = []
        self.style_tags_count: int = 0

        self.structure_anomalies: list[str] = []
        self.active_tags_found: list[str] = []
        self.unexpected_tags_found: list[str] = []
        self.unsafe_attrs_found: list[tuple[str, str, str]] = []
        self.canary_attrs_found: list[tuple[str, str, str]] = []
        self.canary_in_style_found: list[str] = []
        self.canary_data_chunks: list[str] = []
        self.legitimate_tags_found: set[str] = set()
        self.essential_classes_found: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()

        # 1. Transições de abertura da máquina de estados
        if tag_lower == "html":
            if self.html_opened or self.head_opened or self.body_opened or self.html_closed:
                self.structure_anomalies.append("Tag <html> duplicada, aninhada ou reaberta")
            else:
                self.html_opened = True
        elif tag_lower == "head":
            if not self.html_opened or self.head_opened or self.head_closed or self.body_opened or self.html_closed:
                self.structure_anomalies.append("Tag <head> duplicada, aninhada ou iniciada fora de ordem")
            else:
                self.head_opened = True
                self.in_head = True
        elif tag_lower == "body":
            if not self.html_opened or not self.head_closed or self.body_opened or self.body_closed or self.html_closed:
                self.structure_anomalies.append("Tag <body> duplicada, iniciada antes do fechamento de <head> ou fora de ordem")
            else:
                self.body_opened = True
                self.in_body = True
        elif tag_lower == "meta":
            if not self.in_head or self.head_closed:
                self.active_tags_found.append("meta_outside_head")
            else:
                # Ressalva D1: Verificar duplicidade de atributos diretamente na lista recebida antes de dict()
                attr_names = [k.lower() for k, _ in attrs]
                if len(attr_names) != len(set(attr_names)):
                    self.structure_anomalies.append(f"Tag <meta> com atributos duplicados na lista: {attrs}")

                # Normalização e comparação efetiva contra EXPECTED_STATIC_METAS
                current_meta = {k.lower(): (v or "").strip().lower() for k, v in attrs}
                if current_meta in self.EXPECTED_STATIC_METAS:
                    if current_meta in self.matched_metas:
                        self.structure_anomalies.append(f"Tag <meta> duplicada: {current_meta}")
                    else:
                        self.matched_metas.append(current_meta)
                else:
                    self.unexpected_tags_found.append(f"meta_inesperada_ou_modificada: {current_meta}")
        elif tag_lower == "style":
            if not self.in_head or self.head_closed:
                self.active_tags_found.append("style_outside_head")
            else:
                self.style_tags_count += 1
                if self.style_tags_count > 1:
                    self.structure_anomalies.append(f"Tag <style> duplicada ou excedente (count={self.style_tags_count})")
                self.in_style_block = True

        # 2. Categorização de tags
        if tag_lower in self.PROHIBITED_TAGS:
            self.active_tags_found.append(tag_lower)
        elif tag_lower not in self.ALLOWED_TEMPLATE_TAGS:
            self.unexpected_tags_found.append(tag_lower)
        else:
            self.legitimate_tags_found.add(tag_lower)

        # 3. Inspeção de atributos
        for attr_name, attr_val in attrs:
            attr_name_lower = attr_name.lower()
            val_clean = (attr_val or "").lower().strip()

            # Comprova ausência total de canários em atributos HTML
            if attr_val and "CANARY" in attr_val:
                self.canary_attrs_found.append((tag_lower, attr_name, attr_val))

            # Classes essenciais do Bento Grid
            if attr_name_lower == "class" and attr_val:
                for cls in attr_val.split():
                    self.essential_classes_found.add(cls.strip())

            # Manipuladores inline de eventos (on*)
            if attr_name_lower.startswith("on"):
                self.unsafe_attrs_found.append((tag_lower, attr_name, val_clean))

            # Proibição explícita do atributo srcset (desnecessário ao template)
            if attr_name_lower == "srcset":
                self.unsafe_attrs_found.append((tag_lower, attr_name, val_clean))

            # Bloqueio de esquemas perigosos em URLs
            if attr_name_lower in ("href", "src", "action", "formaction", "poster", "xlink:href"):
                if val_clean.startswith(("javascript:", "data:", "vbscript:")):
                    self.unsafe_attrs_found.append((tag_lower, attr_name, val_clean))

            # Checagem heurística contra construções ativas conhecidas em style inline
            if attr_name_lower == "style":
                if any(kw in val_clean for kw in ("expression", "javascript:", "behavior", "@import")):
                    self.unsafe_attrs_found.append((tag_lower, attr_name, val_clean))

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()

        # Transições de fechamento com validação estrita
        if tag_lower == "head":
            if not self.head_opened or self.head_closed or not self.in_head or self.body_opened:
                self.structure_anomalies.append("Fechamento de </head> duplicado, órfão ou fora de ordem")
            elif self.in_style_block:
                self.structure_anomalies.append("Tentativa de fechar </head> com bloco <style> ainda aberto")
            else:
                self.head_closed = True
                self.in_head = False
        elif tag_lower == "body":
            if not self.body_opened or self.body_closed or not self.in_body or self.html_closed:
                self.structure_anomalies.append("Fechamento de </body> duplicado, órfão ou fora de ordem")
            else:
                self.body_closed = True
                self.in_body = False
        elif tag_lower == "html":
            if not self.html_opened or self.html_closed or not self.body_closed:
                self.structure_anomalies.append("Fechamento de </html> prematuro, duplicado ou fora de ordem")
            else:
                self.html_closed = True
        elif tag_lower == "style":
            if not self.in_style_block:
                self.structure_anomalies.append("Fechamento de </style> órfão ou duplicado")
            else:
                self.in_style_block = False

    def handle_data(self, data: str):
        # Inspeção dedicada do bloco <style> do cabeçalho
        if self.in_style_block:
            if "CANARY" in data:
                self.canary_in_style_found.append(data)
            return

        # Nós textuais de conteúdo editorial
        if "CANARY" in data:
            self.canary_data_chunks.append(data)

    def close(self):
        super().close()
        if self.in_style_block:
            self.structure_anomalies.append("Tentativa de fechar documento com bloco <style> ainda aberto")


class TestRendererCanaryInvariants(unittest.TestCase):
    """Suíte canônica de testes de invariantes anti-XSS e integridade estrutural do Bento Grid."""

    def test_canary_invariants_across_all_eight_surfaces(self):
        """Desafia todas as 8 superfícies externas com canários hostis e valida integridade estrutural e anti-XSS."""
        sample_md = """
## 📌 Destaques Principais do Dia
- **M CANARY_2_DROPCAP:** Manchete com payload <img src=x onerror=alert(2)>

---

## CANARY_1_TITLE <head><script>alert(1)</script></head>
- Descrição da seção dinâmica

---

## 🚀 GitHub Trending do Dia
* **[CANARY_3_GH_REPO](https://evil.com@attacker.com)** ⭐ **1.200** (Python)
  - CANARY_4_GH_DESC contendo <svg><a xlink:href="javascript:alert(4)">link</a></svg> e [Ataque](javascript:alert(4))

---

## 📄 Papers Recentes no ArXiv
* **[CANARY_5_PAPER_TITLE](data:text/html,<script>evil</script>)** 📄 **ArXiv: 2610.99999**
  - CANARY_6_PAPER_DESC contendo <iframe src='https://evil.com'></iframe> e <form action='javascript:alert(6)' formaction='javascript:alert(6)'>

---

## 💡 Dica do Autor / Takeaway Prático
CANARY_7_TAKEAWAY <div style='behavior:url(x); background:url(javascript:alert(7))'>Dica</div>

---

## 🌐 Radar & Novidades Tecnológicas
- **CANARY_8_BULLET:** Novidade com [Link](vbscript:msgbox(8)), <video poster='javascript:alert(8)'></video> e <img srcset='evil.jpg 1x'>
"""
        html_doc = render_bento_email(sample_md)
        parser = XSSCanaryParser()
        parser.feed(html_doc)
        parser.close()

        # 1. Estrutura e integridade da máquina de estados
        self.assertEqual(parser.structure_anomalies, [], f"Anomalias estruturais detectadas: {parser.structure_anomalies}")
        self.assertTrue(parser.html_closed, "Tag </html> não foi fechada corretamente")
        self.assertTrue(parser.head_closed, "Tag </head> não foi fechada corretamente")
        self.assertTrue(parser.body_closed, "Tag </body> não foi fechada corretamente")

        # 2. Validação efetiva das 4 META estáticas
        self.assertEqual(len(parser.matched_metas), 4, f"Esperava 4 metas estáticas correspondentes, obteve: {parser.matched_metas}")
        self.assertEqual(parser.unexpected_tags_found, [], f"Tags inesperadas ou metas modificadas: {parser.unexpected_tags_found}")

        # 3. Integridade do bloco <style>
        self.assertEqual(parser.style_tags_count, 1, f"Esperava exatamente 1 tag <style>, obteve: {parser.style_tags_count}")
        self.assertFalse(parser.in_style_block, "Bloco <style> permaneceu aberto ao término do parsing")

        # 4. Proibição de tags ativas e injeção de metas/estilos
        self.assertEqual(parser.active_tags_found, [], f"Tags ativas/proibidas encontradas no HTML: {parser.active_tags_found}")

        # 5. Atributos inseguros e proibição de srcset
        self.assertEqual(parser.unsafe_attrs_found, [], f"Atributos inseguros encontrados: {parser.unsafe_attrs_found}")

        # 6. Rejeição comprovada de URL com userinfo (@ na autoridade)
        self.assertNotIn("https://evil.com@attacker.com", html_doc)

        # 7. Presença dos 8 canários como nós de texto e ausência em atributos / <style>
        all_text = " ".join(parser.canary_data_chunks)
        for i in range(1, 9):
            canary_id = f"CANARY_{i}"
            self.assertIn(canary_id, all_text, f"Canário {canary_id} ausente dos nós de texto")
        self.assertEqual(parser.canary_attrs_found, [], f"Canários vazaram para atributos HTML: {parser.canary_attrs_found}")
        self.assertEqual(parser.canary_in_style_found, [], f"Canários injetados no bloco <style>: {parser.canary_in_style_found}")

        # 8. Validação estrutural das classes e âncoras essenciais do Bento Grid
        expected_classes = {"main-container", "newspaper-section", "dropcap", "nav-pill", "footer-card"}
        missing_classes = expected_classes - parser.essential_classes_found
        self.assertEqual(missing_classes, set(), f"Classes essenciais do Bento Grid ausentes: {missing_classes}")

        for anchor in ("#destaques", "#github-trending", "#papers", "#takeaway"):
            self.assertIn(anchor, html_doc, f"Âncora de navegação {anchor} ausente do HTML")

    def test_parser_detects_duplicate_meta_attributes_before_dict_conversion(self):
        """Valida que o parser detecta nomes de atributos duplicados na lista bruta de <meta> antes de dict()."""
        raw_html = '<!DOCTYPE html><html><head><meta name="viewport" name="viewport" content="width=device-width, initial-scale=1.0"><style>body{}</style></head><body></body></html>'
        parser = XSSCanaryParser()
        parser.feed(raw_html)
        parser.close()
        self.assertTrue(
            any("atributos duplicados na lista" in a for a in parser.structure_anomalies),
            f"Esperava anomalia de atributos duplicados, obteve: {parser.structure_anomalies}"
        )

    def test_parser_detects_style_block_still_open_on_head_close(self):
        """Valida que a tentativa de fechar </head> com <style> ainda aberto é detectada como anomalia."""
        parser = XSSCanaryParser()
        parser.head_opened = True
        parser.in_head = True
        parser.in_style_block = True
        parser.handle_endtag("head")
        self.assertTrue(
            any("Tentativa de fechar </head> com bloco <style> ainda aberto" in a for a in parser.structure_anomalies),
            f"Esperava detecção de estilo aberto no fechamento de head, obteve: {parser.structure_anomalies}"
        )

    def test_parser_detects_unexpected_or_modified_meta(self):
        """Valida que metatags com atributos inesperados (ex: http-equiv='refresh') são registradas como anômalas."""
        malformed_html = '<!DOCTYPE html><html><head><meta http-equiv="refresh" content="5;url=https://evil.com"><style>body{}</style></head><body></body></html>'
        parser = XSSCanaryParser()
        parser.feed(malformed_html)
        parser.close()
        self.assertTrue(
            any("meta_inesperada_ou_modificada" in u for u in parser.unexpected_tags_found),
            f"Esperava registro de meta inesperada, obteve: {parser.unexpected_tags_found}"
        )


if __name__ == "__main__":
    unittest.main()
