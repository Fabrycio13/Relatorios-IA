import re
import json
import html
from datetime import datetime
from pathlib import Path
from src.core.config import HEADER_BANNER_URL, HEADER_FULL_HD_URL, FOOTER_BANNER_URL, DATA_DIR
from src.delivery.banner_selector import resolver_banner_do_dia

def obter_numero_edicao(data_str: str | None = None) -> str:
    """
    Retorna o número sequencial da edição formatado como '001', '002', etc.
    Persiste o histórico em data/edicoes.json para que cada nova data gere uma nova edição.
    """
    if not data_str:
        data_str = datetime.now().strftime("%Y-%m-%d")

    edicoes_file = DATA_DIR / "edicoes.json"
    edicoes = {}
    if edicoes_file.exists():
        try:
            with open(edicoes_file, "r", encoding="utf-8") as f:
                edicoes = json.load(f)
        except Exception:
            edicoes = {}

    if data_str in edicoes:
        num = edicoes[data_str]
    else:
        num = len(edicoes) + 1
        edicoes[data_str] = num
        try:
            with open(edicoes_file, "w", encoding="utf-8") as f:
                json.dump(edicoes, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return f"{num:03d}"

def format_inline(text: str) -> str:
    """Aplica formatação inline básica em markdown com estética autêntica de jornal impresso e papel de época."""
    # REGRA DE OURO: Elimina sumariamente qualquer travessão longo '\u2014' e resíduos
    text = text.replace("\u2014", "-").replace("—", "-")
    text = re.sub(r'^[)\s]+', '', text)
    text = text.replace(" )**", " **").replace(")**", "**")

    # Links primeiro (Azul Safira clássico com sublinhado nítido para destaque imediato e abertura segura em nova aba)
    t = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" target="_blank" rel="noopener noreferrer" style="color: #1d4ed8; text-decoration: underline; font-weight: 600;">\1</a>',
        text
    )
    # Negrito (Apenas o termo em destaque em negrito preto nítido)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong style="color: #111111; font-weight: 700;">\1</strong>', t)
    # Itálico (Ênfase editorial itálica)
    t = re.sub(r'\*([^*]+)\*', r'<em style="color: #444444; font-style: italic;">\1</em>', t)
    # Código inline (Fundo linotipo cinza-papel suave)
    t = re.sub(
        r'`([^`]+)`',
        r'<code style="background-color: #eee8db; color: #111111; padding: 2px 5px; border-radius: 2px; font-family: \'Courier New\', Courier, monospace; font-size: 88%; border: 1px solid #d5cdbd;">\1</code>',
        t
    )

    # Micro-badges (Carimbos de redação de jornal impresso com bordas finas)
    def _badge_replace(match):
        raw_tag = match.group(1).strip()
        tag_key = raw_tag.upper()
        return f'<span style="display: inline-block; border: 1px solid #1d4ed8; color: #1d4ed8; padding: 1px 5px; font-size: 10px; font-weight: 900; font-family: -apple-system, Arial, sans-serif; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 4px; vertical-align: middle;">{tag_key}</span>'

    t = re.sub(
        r'\[(MCP|NOVO|Novo|NOVA|Nova|CÓDIGO|Código|CODIGO|Codigo|GITHUB|GitHub|PAPER|Paper|DEMO|Demo|TENDÊNCIA|Tendência|TENDENCIA|Tendencia)\]',
        _badge_replace,
        t
    )
    # Garantia dupla contra qualquer travessão longo remanescente
    t = t.replace("\u2014", "-").replace("—", "-")
    return t

def render_bento_email(md_text: str, data_envio: datetime | None = None) -> str:
    """
    Renderizador Oficial estilo Jornal Impresso Tradicional (The Engineering Gazette).
    Títulos centralizados com cores temáticas distintas para cada tópico,
    textos corridos em peso normal (400) com apenas os termos-chave em negrito,
    tabelas anti-colisão e 100% de compatibilidade para mobile e desktop.
    """
    # Garantia total da REGRA DE OURO
    md_text = md_text.replace("\u2014", "-").replace("—", "-")
    banner_info = resolver_banner_do_dia(data_envio=data_envio)
    caption_escaped = html.escape(banner_info.caption, quote=True)

    sections = []
    current_section = None

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            title = line[3:].strip()
            # Substitui travessão no título se existir
            title = title.replace("\u2014", "-").replace("—", "-")
            current_section = {"title": title, "lines": []}
            sections.append(current_section)
        elif current_section is not None:
            if line != "---":
                current_section["lines"].append(raw_line)

    articles_html = []

    for sec in sections:
        title = sec["title"]
        lines = sec["lines"]

        # 1. Manchete Principal do Dia com Capitular (Drop Cap)
        if "Destaques Principais" in title:
            bullet_items = []
            for l in lines:
                l_str = l.strip()
                if l_str.startswith("- ") or l_str.startswith("* "):
                    conteudo = format_inline(l_str[2:])
                    bullet_items.append(conteudo)

            first_p_html = ""
            rest_bullets_html = []

            if bullet_items:
                primeiro = bullet_items[0]
                drop_match = re.match(r'^(<strong[^>]*>)?([A-Za-z0-9ÁÉÍÓÚÀÂÊÔÃÕÇ])(.*)$', primeiro)
                if drop_match:
                    prefix_tag, letra, resto = drop_match.groups()
                    prefix_tag = prefix_tag or ""
                    first_p_html = f"""
                    <div style="font-size: 15px; line-height: 1.65; color: #292524; font-weight: 400; margin-bottom: 12px; text-align: justify;">
                        <span class="dropcap" style="float: left; font-size: 48px; line-height: 38px; font-weight: bold; padding-top: 4px; padding-right: 8px; font-family: 'Times New Roman', Georgia, serif; color: #b45309;">{letra}</span>
                        {prefix_tag}{resto}
                    </div>
                    """
                else:
                    first_p_html = f"""
                    <div style="font-size: 15px; line-height: 1.65; color: #292524; font-weight: 400; margin-bottom: 12px; text-align: justify;">
                        {primeiro}
                    </div>
                    """

                for b in bullet_items[1:]:
                    rest_bullets_html.append(f"""
                    <li style="margin-bottom: 9px; line-height: 1.6; color: #292524; font-size: 14px; font-weight: 400;">
                        {b}
                    </li>
                    """)

            articles_html.append(f"""
            <!-- MANCHETE DO DIA: DESTAQUES PRINCIPAIS -->
            <a name="destaques" id="destaques" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <div class="newspaper-section" style="margin-bottom: 24px;">
                <div style="border-top: 3px double #b45309; border-bottom: 1px solid #b45309; padding: 7px 0; margin-bottom: 14px; text-align: center;">
                    <h2 style="font-family: 'Times New Roman', Georgia, serif; font-size: 17px; font-weight: 900; text-transform: uppercase; letter-spacing: 1px; margin: 0; color: #92400e; text-align: center;">Destaques Principais do Dia</h2>
                </div>
                {first_p_html}
                <ul style="padding-left: 20px; margin: 0;">
                    {''.join(rest_bullets_html)}
                </ul>
            </div>
            """)
            continue

        # 2. Gazeta de Código: GitHub Trending
        if "GitHub Trending" in title:
            gh_items = []
            curr_repo = None

            for l in lines:
                l_str = l.strip()
                if l_str.startswith("* **[") or l_str.startswith("- **["):
                    match_header = re.match(r'[\*\-]\s+\*\*\[([^\]]+)\]\(([^)]+)\)\*\*[:\s\-]*\s*⭐\s+\*\*([^\*]+)\*\*\s+[\(|\|]?\s*([^)\n]+)[\)]?', l_str)
                    if match_header:
                        repo_name, repo_url, stars, lang = match_header.groups()
                        curr_repo = {
                            "name": repo_name,
                            "url": repo_url,
                            "stars": stars.strip(),
                            "lang": lang.strip(),
                            "desc": []
                        }
                        gh_items.append(curr_repo)
                    else:
                        curr_repo = {
                            "raw_title": format_inline(l_str[2:]),
                            "desc": []
                        }
                        gh_items.append(curr_repo)
                elif curr_repo is not None and (l_str.startswith("- ") or l_str.startswith("* ")):
                    curr_repo["desc"].append(format_inline(l_str[2:]))

            repos_entries = []
            for r in gh_items:
                if "name" in r:
                    desc_text = " ".join(r["desc"])
                    repos_entries.append(f"""
                    <div style="margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px dotted #d4cbb8;">
                        <div style="margin-bottom: 4px;">
                            <a href="{r['url']}" style="color: #c2410c; font-weight: 700; text-decoration: underline; font-size: 14.5px; font-family: 'Courier New', monospace;">{r['name']}</a>
                            <span style="display: inline-block; border: 1px solid #78350f; color: #78350f; font-size: 10px; font-weight: 900; padding: 1px 5px; margin-left: 6px; font-family: -apple-system, sans-serif;">⭐ {r['stars']}</span>
                            <span style="display: inline-block; border: 1px solid #334155; color: #334155; font-size: 10px; font-weight: 700; padding: 1px 5px; margin-left: 3px; font-family: -apple-system, sans-serif;">{r['lang']}</span>
                        </div>
                        <p style="color: #292524; font-size: 13.5px; line-height: 1.55; margin: 0; text-align: justify; font-weight: 400;">{desc_text}</p>
                    </div>
                    """)
                else:
                    repos_entries.append(f"""
                    <div style="margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px dotted #d4cbb8;">
                        <p style="margin: 0; font-size: 14px; color: #111111; font-weight: 400;">{r.get('raw_title', '')}</p>
                        <p style="color: #292524; font-size: 13.5px; line-height: 1.55; margin: 4px 0 0 0; text-align: justify; font-weight: 400;">{' '.join(r.get('desc', []))}</p>
                    </div>
                    """)

            articles_html.append(f"""
            <!-- GITHUB TRENDING -->
            <a name="github-trending" id="github-trending" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <div class="newspaper-section" style="margin-bottom: 24px;">
                <div style="border-top: 2px solid #c2410c; border-bottom: 1px solid #c2410c; padding: 7px 0; margin-bottom: 14px; text-align: center;">
                    <h2 style="font-family: 'Times New Roman', Georgia, serif; color: #c2410c; font-size: 15px; margin: 0; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; line-height: 1.35; text-align: center;">GAZETA DE CÓDIGO: REPOSITÓRIOS GITHUB TRENDING EM ALTA NO DIA</h2>
                </div>
                {''.join(repos_entries)}
            </div>
            """)
            continue

        # 3. Folha Científica: Papers em Destaque
        if "Papers em Destaque" in title:
            paper_items = []
            curr_paper = None

            for l in lines:
                l_str = l.strip()
                if l_str.startswith("* **[") or l_str.startswith("- **["):
                    match_header = re.match(r'[\*\-]\s+\*\*\[([^\]]+)\]\(([^)]+)\)\*\*[:\s\-]*\s*📄\s+\*\*ArXiv:\s*([^\*]+)\*\*', l_str)
                    if match_header:
                        p_title, p_url, p_arxiv = match_header.groups()
                        curr_paper = {
                            "title": p_title,
                            "url": p_url,
                            "arxiv": p_arxiv.strip(),
                            "desc": []
                        }
                        paper_items.append(curr_paper)
                    else:
                        curr_paper = {
                            "raw_title": format_inline(l_str[2:]),
                            "desc": []
                        }
                        paper_items.append(curr_paper)
                elif curr_paper is not None and (l_str.startswith("- ") or l_str.startswith("* ")):
                    curr_paper["desc"].append(format_inline(l_str[2:]))

            paper_entries = []
            for p in paper_items:
                if "title" in p:
                    desc_text = " ".join(p["desc"])
                    paper_entries.append(f"""
                    <div style="margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px dotted #d4cbb8;">
                        <div style="margin-bottom: 4px;">
                            <a href="{p['url']}" style="color: #be185d; font-weight: 700; text-decoration: underline; font-size: 14.5px; font-family: 'Times New Roman', serif;">{p['title']}</a>
                            <span style="display: inline-block; border: 1px solid #be185d; color: #be185d; font-size: 10px; font-weight: 900; padding: 1px 5px; margin-left: 6px; font-family: -apple-system, sans-serif;">📄 ARXIV: {p['arxiv']}</span>
                        </div>
                        <p style="color: #292524; font-size: 13.5px; line-height: 1.55; margin: 0; text-align: justify; font-weight: 400;">{desc_text}</p>
                    </div>
                    """)
                else:
                    paper_entries.append(f"""
                    <div style="margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px dotted #d4cbb8;">
                        <p style="margin: 0; font-size: 14px; color: #111111; font-weight: 400;">{p.get('raw_title', '')}</p>
                        <p style="color: #292524; font-size: 13.5px; line-height: 1.55; margin: 4px 0 0 0; text-align: justify; font-weight: 400;">{' '.join(p.get('desc', []))}</p>
                    </div>
                    """)

            articles_html.append(f"""
            <!-- PAPERS CIENTÍFICOS -->
            <a name="papers" id="papers" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <div class="newspaper-section" style="margin-bottom: 24px;">
                <div style="border-top: 2px solid #be185d; border-bottom: 1px solid #be185d; padding: 7px 0; margin-bottom: 14px; text-align: center;">
                    <h2 style="font-family: 'Times New Roman', Georgia, serif; color: #be185d; font-size: 15px; margin: 0; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; line-height: 1.35; text-align: center;">Folha Científica: Papers em Destaque &amp; Estado da Arte</h2>
                </div>
                {''.join(paper_entries)}
            </div>
            """)
            continue

        # 4. Box Editorial: Dica do Autor (O que levar para o código hoje)
        if "Dica do Autor" in title or "Dizer do Dia" in title or "Takeaway" in title or "💡" in title:
            # Processa as linhas da Dica do Autor
            cleaned_lines = []
            for l in lines:
                l_str = l.strip()
                if not l_str:
                    continue
                # Remove marcadores residuais se existirem para manter parágrafo corrido
                if l_str.startswith("- ") or l_str.startswith("* "):
                    l_str = l_str[2:].strip()
                cleaned_lines.append(format_inline(l_str))

            paragrafo_conteudo = " ".join(cleaned_lines)

            articles_html.append(f"""
            <!-- DICA DO AUTOR: O QUE LEVAR PARA O CÓDIGO HOJE (BOX EDITORIAL) -->
            <a name="takeaway" id="takeaway" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <a name="dizer-do-dia" id="dizer-do-dia" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <a name="dica-do-autor" id="dica-do-autor" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <div class="newspaper-section" style="margin-bottom: 24px; border: 2px solid #ca8a04; padding: 18px 20px; background-color: #fefce8;">
                <div style="border-bottom: 1px solid #eab308; padding-bottom: 8px; margin-bottom: 12px; text-align: center;">
                    <h2 style="font-family: 'Times New Roman', Georgia, serif; color: #854d0e; font-size: 15.5px; margin: 0; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; text-align: center;">DICA DO AUTOR: O QUE LEVAR PARA O CÓDIGO HOJE</h2>
                </div>
                <p style="margin: 0; font-size: 14.5px; line-height: 1.65; color: #713f12; font-family: 'Times New Roman', Georgia, serif; text-align: justify; font-weight: 400;">
                    {paragrafo_conteudo}
                </p>
            </div>
            """)
            continue

        # 5. Seções Temáticas Padrão (Tópicos 1 a 7)
        items_html = []
        curr_item = None

        for l in lines:
            l_str = l.strip()
            if not l_str:
                continue

            # Remove resíduos de sintaxe
            l_str = re.sub(r'^[\*\-]\s*\)\s*', '- ', l_str)
            l_str = re.sub(r'^[\*\-]\s*\)\*\*', '- **', l_str)

            # Filtro de ausência
            l_lower = l_str.lower()
            if any(term in l_lower for term in [
                "não há publicação",
                "não ha publicação",
                "não há publicações",
                "não publicou",
                "não foi tratado como notícia"
            ]):
                continue

            if (l_str.startswith("* **") or l_str.startswith("- **")) and not l.startswith("  "):
                item_header = format_inline(l_str[2:])
                curr_item = {
                    "header": item_header,
                    "bullets": []
                }
                items_html.append(curr_item)
            elif curr_item is not None and (l.startswith("  ") or l_str.startswith("- ") or l_str.startswith("* ")):
                bullet_text = format_inline(l_str.lstrip("-* "))
                curr_item["bullets"].append(f"<li style='margin-bottom: 6px; color: #44403c; font-size: 13.5px; line-height: 1.55; font-weight: 400;'>{bullet_text}</li>")
            else:
                if not items_html:
                    items_html.append({"raw_p": format_inline(l_str)})

        rendered_items = []
        for it in items_html:
            if "raw_p" in it:
                rendered_items.append(f"<p style='color: #555; font-size: 13.5px; font-style: italic; margin: 6px 0; text-align: justify; font-weight: 400;'>{it['raw_p']}</p>")
            else:
                bullets_str = f"<ul style='margin: 6px 0 0 0; padding-left: 18px;'>{''.join(it['bullets'])}</ul>" if it['bullets'] else ""
                rendered_items.append(f"""
                <div style="margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px dotted #d4cbb8;">
                    <div style="font-size: 14px; margin-bottom: 4px; color: #292524; line-height: 1.6; font-family: 'Times New Roman', Georgia, serif; font-weight: 400; text-align: justify;">
                        {it['header']}
                    </div>
                    {bullets_str}
                </div>
                """)

        # Cores temáticas para cada tópico chamar atenção de forma elegante
        accent_color = "#b45309"  # Padrão: Dourado Âmbar

        if "1." in title or "Ferramentas" in title or "Visão" in title or "Visao" in title:
            accent_color = "#c2410c"  # Laranja Terracota (Tópico 1)
        elif "2." in title or "Agentes" in title or "MCP" in title:
            accent_color = "#7c3aed"  # Roxo Violeta (Tópico 2)
        elif "3." in title or "Harness" in title or "Evals" in title:
            accent_color = "#0e7490"  # Ciano / Petróleo (Tópico 3)
        elif "4." in title or "Desenvolvimento" in title or "Claude" in title:
            accent_color = "#047857"  # Verde Esmeralda (Tópico 4)
        elif "5." in title or "Radar" in title or "Perfis" in title:
            accent_color = "#4338ca"  # Azul Índigo (Tópico 5)
        elif "6." in title or "Capacitação" in title or "Capacitacao" in title or "Hackathons" in title:
            accent_color = "#be185d"  # Vinho Carmim (Tópico 6)
        elif "7." in title or "Economia" in title or "Mercado" in title:
            accent_color = "#b45309"  # Dourado Ocre (Tópico 7)

        # Higieniza título: remove números iniciais e emojis para estética limpa de imprensa
        title_clean = re.sub(r'^\d+\.\s*', '', title).strip()
        title_clean = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\ud83c-\ud83e][\ud000-\udfff]', '', title_clean).strip()
        if "Radar Perfis" in title_clean or "Radar" in title_clean:
            title_clean = re.sub(r'\s*\(.*?\)', '', title_clean).strip()

        is_radar = ("1." in title or "Ferramentas" in title or "Agentes" in title or "Radar" in title) and not any('name="radar-x"' in c for c in articles_html)
        radar_anchor = '<a name="radar-x" id="radar-x" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>\n        ' if is_radar else ''

        articles_html.append(f"""
        <!-- SEÇÃO: {title_clean} -->
        {radar_anchor}<div class="newspaper-section" style="margin-bottom: 24px;">
            <div style="border-top: 2px solid {accent_color}; border-bottom: 1px solid {accent_color}; padding: 7px 0; margin-bottom: 14px; text-align: center;">
                <h2 style="font-family: 'Times New Roman', Georgia, serif; color: {accent_color}; font-size: 15px; margin: 0; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; line-height: 1.35; text-align: center;">{title_clean}</h2>
            </div>
            {''.join(rendered_items)}
        </div>
        """)

    body_content = "\n".join(articles_html)
    hoje = datetime.now()
    hoje_formatada = hoje.strftime("%d/%m/%Y")
    data_iso = hoje.strftime("%Y-%m-%d")

    # Mapeamento do dia da semana em português
    dias_semana = {
        0: "SEGUNDA-FEIRA",
        1: "TERÇA-FEIRA",
        2: "QUARTA-FEIRA",
        3: "QUINTA-FEIRA",
        4: "SEXTA-FEIRA",
        5: "SÁBADO",
        6: "DOMINGO"
    }
    dia_semana_nome = dias_semana.get(hoje.weekday(), "EDIÇÃO DIÁRIA")
    numero_edicao = obter_numero_edicao(data_iso)

    full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <title>O Diário de Engenharia - Edição Impressa</title>
    <style>
        :root {{
            color-scheme: light;
            supported-color-schemes: light;
        }}
        html {{
            scroll-behavior: smooth;
        }}
        .nav-pill {{
            transition: color 0.15s ease;
        }}
        .nav-pill:hover {{
            color: #1d4ed8 !important;
            text-decoration: underline !important;
        }}
        @media only screen and (max-width: 650px) {{
            body {{
                padding: 12px 6px !important;
            }}
            .main-container {{
                max-width: 100% !important;
                padding: 20px 14px !important;
            }}
            .masthead-title {{
                font-size: 28px !important;
            }}
            .top-meta-td {{
                font-size: 9px !important;
                letter-spacing: 0.5px !important;
            }}
            .issue-bar-td {{
                font-size: 9.5px !important;
            }}
            .nav-container {{
                line-height: 2 !important;
            }}
        }}
    </style>
</head>
<body style="font-family: 'Times New Roman', Times, Georgia, serif; background-color: #ffffff; margin: 0; padding: 24px 12px; color: #1a1a1a; -webkit-font-smoothing: antialiased;">
    <!--[if mso]>
    <table role="presentation" width="680" align="center" style="width:680px;" border="0" cellspacing="0" cellpadding="0">
    <tr>
    <td>
    <![endif]-->
    <div class="main-container" style="max-width: 680px; margin: 0 auto; background-color: #fbf8f1; background-image: linear-gradient(#fbf8f1, #fbf8f1); border: 1px solid #d4cbb8; box-shadow: 0 4px 16px rgba(0,0,0,0.06); padding: 36px 32px; box-sizing: border-box;">
        
        <!-- CABEÇALHO SUPERIOR DE IMPRENSA (TABELA ANTI-COLISÃO PARA CLIENTES DE EMAIL) -->
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="border-bottom: 1px solid #1a1a1a; margin-bottom: 12px; font-family: -apple-system, Arial, sans-serif; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #555555;">
            <tr>
                <td align="left" width="38%" class="top-meta-td" style="padding-bottom: 4px; white-space: nowrap; text-align: left;">
                    EDIÇÃO DIÁRIA DE TECNOLOGIA &amp; IA
                </td>
                <td align="center" width="36%" class="top-meta-td" style="padding-bottom: 4px; white-space: nowrap; padding: 0 4px; text-align: center;">
                    CIRCULAÇÃO DE ENGENHARIA
                </td>
                <td align="right" width="26%" class="top-meta-td" style="padding-bottom: 4px; white-space: nowrap; text-align: right;">
                    ANO I - Nº {numero_edicao}
                </td>
            </tr>
        </table>

        <!-- MASTHEAD DE JORNAL TRADICIONAL -->
        <div class="newspaper-header" style="text-align: center; border-bottom: 3px double #1a1a1a; padding-bottom: 12px; margin-bottom: 16px;">
            <h1 class="masthead-title" style="font-family: 'Playfair Display', Georgia, 'Times New Roman', serif; font-size: 38px; font-weight: 900; text-transform: uppercase; letter-spacing: 1.5px; margin: 6px 0; line-height: 1.05; color: #111111;">O Diário de Engenharia</h1>
            <div class="masthead-subtitle" style="font-style: italic; font-size: 13.5px; color: #444444; margin: 4px 0 10px 0;">Crônica Diária de Agentes Autônomos, Modelos de Linguagem e Sistemas de Software</div>
            
            <!-- BARRA DE DATAÇÃO (TABELA ANTI-COLISÃO) -->
            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="border-top: 1px solid #1a1a1a; border-bottom: 1px solid #1a1a1a; margin-bottom: 10px; font-family: -apple-system, Arial, sans-serif; font-size: 10.5px; font-weight: 700; text-transform: uppercase; color: #222222;">
                <tr>
                    <td align="left" width="55%" class="issue-bar-td" style="padding: 4px 0; white-space: nowrap; text-align: left;">
                        {dia_semana_nome}, {hoje_formatada}
                    </td>
                    <td align="right" width="45%" class="issue-bar-td" style="padding: 4px 0; white-space: nowrap; text-align: right;">
                        CURADORIA: FABRYCIO BERMUDES
                    </td>
                </tr>
            </table>

            <!-- NAVEGAÇÃO RÁPIDA (LINKS DE IMPRENSA) -->
            <div class="nav-container" style="margin-top: 8px; font-family: -apple-system, Arial, sans-serif; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">
                <a href="#destaques" class="nav-pill" style="color: #92400e; text-decoration: none; margin: 0 5px;">✦ Destaques</a>
                <span style="color: #ccc;">•</span>
                <a href="#radar-x" class="nav-pill" style="color: #4338ca; text-decoration: none; margin: 0 5px;">✦ Radar &amp; X</a>
                <span style="color: #ccc;">•</span>
                <a href="#github-trending" class="nav-pill" style="color: #c2410c; text-decoration: none; margin: 0 5px;">✦ GitHub Trending</a>
                <span style="color: #ccc;">•</span>
                <a href="#papers" class="nav-pill" style="color: #be185d; text-decoration: none; margin: 0 5px;">✦ Papers</a>
                <span style="color: #ccc;">•</span>
                <a href="#takeaway" class="nav-pill" style="color: #854d0e; text-decoration: none; margin: 0 5px;">✦ Dica do Autor</a>
            </div>
        </div>

        <!-- FOTO PRINCIPAL COM MOLDURA DE GRAVURA E LEGENDA DINÂMICA DA EDIÇÃO -->
        <div class="newspaper-photo" style="margin: 18px 0 24px 0; border: 1px solid #1a1a1a; padding: 5px; background: #ffffff;">
            <a href="{banner_info.full_hd_url}" target="_blank" style="display: block; text-decoration: none; border: 0; outline: none;" title="Clique para abrir a arte original em alta resolução">
                <img src="{banner_info.banner_url}" alt="Arte da Edição: {caption_escaped}" width="680" style="display: block; width: 100%; max-height: 380px; height: auto; object-fit: cover; object-position: center bottom; border: 0;" />
            </a>
            <div class="photo-caption" style="font-size: 12.5px; font-style: italic; color: #444444; padding: 6px 4px 2px 4px; border-top: 1px solid #e2dac9; text-align: center; font-family: Georgia, serif;">
                {caption_escaped}
            </div>
        </div>

        <!-- CONTEÚDO CORRIDO DO JORNAL -->
        {body_content}

        <!-- RODAPÉ DE IMPRESSÃO TIPOGRÁFICA -->
        <div class="footer-card" style="border-top: 3px double #1a1a1a; margin-top: 28px; padding-top: 16px; text-align: center;">
            <div style="border: 1px solid #1a1a1a; padding: 4px; background: #ffffff; margin-bottom: 14px;">
                <img src="{FOOTER_BANNER_URL}" alt="Curadoria de Engenharia" width="680" style="display: block; width: 100%; max-height: 120px; height: auto; object-fit: cover; object-position: center; border: 0;" />
            </div>
            <p style="font-family: 'Times New Roman', Georgia, serif; font-style: italic; font-size: 13.5px; color: #444444; margin: 0; line-height: 1.5;">
                Curadoria por <strong style="color: #111111; font-weight: 700;">Fabrycio Bermudes</strong> - Software Engineer &amp; AI Builder
            </p>
        </div>

    </div>
    <!--[if mso]>
    </td>
    </tr>
    </table>
    <![endif]-->
</body>
</html>
"""
    # Garantia final absoluta da REGRA DE OURO
    full_html = full_html.replace("\u2014", "-").replace("—", "-")
    return full_html
