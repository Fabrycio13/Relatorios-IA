import re
from datetime import datetime
from src.core.config import HEADER_BANNER_URL, FOOTER_BANNER_URL

def format_inline(text: str) -> str:
    """Aplica formatação inline básica em markdown (links, negrito, itálico, código, micro-badges)."""
    # Remove eventuais parênteses soltos no início ou resíduos de bug ')Palavra'
    text = re.sub(r'^[)\s]+', '', text)
    text = text.replace(" )**", " **").replace(")**", "**")

    # Links primeiro
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #2563eb; text-decoration: none; font-weight: 600;">\1</a>', text)
    # Negrito
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong style="color: #0f172a; font-weight: 600;">\1</strong>', t)
    # Itálico
    t = re.sub(r'\*([^*]+)\*', r'<em style="color: #64748b;">\1</em>', t)
    # Código inline
    t = re.sub(r'`([^`]+)`', r'<code style="background-color: #f1f5f9; color: #0f172a; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 85%; border: 1px solid #e2e8f0;">\1</code>', t)

    # Micro-badges visuais (Q4)
    badge_colors = {
        "MCP": "background-color: #ecfdf5; color: #047857; border: 1px solid #a7f3d0;",
        "NOVO": "background-color: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0;",
        "NOVA": "background-color: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0;",
        "CÓDIGO": "background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;",
        "CODIGO": "background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;",
        "GITHUB": "background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;",
        "PAPER": "background-color: #fdf2f8; color: #be185d; border: 1px solid #fbcfe8;",
        "DEMO": "background-color: #faf5ff; color: #7e22ce; border: 1px solid #e9d5ff;",
        "TENDÊNCIA": "background-color: #fff7ed; color: #c2410c; border: 1px solid #ffedd5;",
        "TENDENCIA": "background-color: #fff7ed; color: #c2410c; border: 1px solid #ffedd5;",
    }

    def _badge_replace(match):
        raw_tag = match.group(1).strip()
        tag_key = raw_tag.upper()
        style = badge_colors.get(tag_key, "background-color: #f1f5f9; color: #475569; border: 1px solid #e2e8f0;")
        return f'<span style="display: inline-block; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; {style} vertical-align: middle; margin-right: 4px; text-transform: uppercase;">{tag_key}</span>'

    t = re.sub(r'\[(MCP|NOVO|Novo|NOVA|Nova|CÓDIGO|Código|CODIGO|Codigo|GITHUB|GitHub|PAPER|Paper|DEMO|Demo|TENDÊNCIA|Tendência|TENDENCIA|Tendencia)\]', _badge_replace, t)
    # Higienização contra travessão longo artificial ' — '
    t = t.replace(" — ", " - ").replace("—", "-")
    return t

def render_bento_email(md_text: str) -> str:
    """
    Renderizador Bento Grid Modular estilo Apple Dashboard (Light Premium).
    100% responsivo para mobile (iPhone, Android) e desktop (Outlook, Gmail).
    """
    sections = []
    current_section = None

    # Divide o markdown por seções ##
    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            title = line[3:].strip()
            current_section = {"title": title, "lines": []}
            sections.append(current_section)
        elif current_section is not None:
            if line != "---":
                current_section["lines"].append(raw_line)

    cards_html = []

    for sec in sections:
        title = sec["title"]
        lines = sec["lines"]

        # 1. Card Hero: Destaques Principais do Dia
        if "Destaques Principais" in title:
            bullets_html = []
            for l in lines:
                l_str = l.strip()
                if l_str.startswith("- ") or l_str.startswith("* "):
                    conteudo = format_inline(l_str[2:])
                    bullets_html.append(f"""
                    <li style="margin-bottom: 8px; line-height: 1.5; color: #1e293b; font-size: 14px;">
                        {conteudo}
                    </li>
                    """)

            cards_html.append(f"""
            <!-- HERO CARD: DESTAQUES DO DIA -->
            <a name="destaques" id="destaques" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <div class="bento-card" style="background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%); border: 1px solid #bfdbfe; border-left: 4px solid #2563eb; border-radius: 16px; padding: 18px 20px; margin-bottom: 20px; box-shadow: 0 4px 12px -2px rgba(59, 130, 246, 0.08);">
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    <span style="font-size: 18px; margin-right: 8px;">📌</span>
                    <h2 style="color: #1e40af; font-size: 16px; margin: 0; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Destaques Principais do Dia</h2>
                </div>
                <ul style="padding-left: 20px; margin: 0;">
                    {''.join(bullets_html)}
                </ul>
            </div>
            """)
            continue

        # 2. Card Especial: GitHub Trending
        if "GitHub Trending" in title:
            gh_items = []
            curr_repo = None

            for l in lines:
                l_str = l.strip()
                if l_str.startswith("* **[") or l_str.startswith("- **["):
                    match_header = re.match(r'[\*\-]\s+\*\*\[([^\]]+)\]\(([^)]+)\)\*\*[:\s—\-]*\s*⭐\s+\*\*([^\*]+)\*\*\s+[\(|\|]?\s*([^)\n]+)[\)]?', l_str)
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

            repos_cards = []
            for r in gh_items:
                if "name" in r:
                    desc_text = " ".join(r["desc"])
                    repos_cards.append(f"""
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;">
                        <div style="margin-bottom: 6px;">
                            <a href="{r['url']}" style="color: #0f172a; font-weight: 700; text-decoration: none; font-size: 14px; margin-right: 8px; word-break: break-word;">{r['name']}</a>
                            <span style="display: inline-block; white-space: nowrap; background-color: #fef08a; color: #854d0e; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 999px; margin-right: 4px; margin-top: 2px;">⭐ {r['stars']}</span>
                            <span style="display: inline-block; white-space: nowrap; background-color: #e0f2fe; color: #0369a1; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 999px; margin-top: 2px;">{r['lang']}</span>
                        </div>
                        <p style="color: #475569; font-size: 13px; line-height: 1.5; margin: 0;">{desc_text}</p>
                    </div>
                    """)
                else:
                    repos_cards.append(f"""
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;">
                        <p style="margin: 0; font-size: 14px; word-break: break-word;">{r.get('raw_title', '')}</p>
                        <p style="color: #475569; font-size: 13px; line-height: 1.5; margin: 4px 0 0 0;">{' '.join(r.get('desc', []))}</p>
                    </div>
                    """)

            cards_html.append(f"""
            <!-- GITHUB TRENDING CARD -->
            <a name="github-trending" id="github-trending" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <div class="bento-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #ea580c; border-radius: 16px; padding: 20px 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);">
                <div style="border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 14px;">
                    <h2 style="color: #c2410c; font-size: 15px; margin: 0; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.4;">🔥 GitHub Trending: Repositórios de IA em Alta no Dia</h2>
                </div>
                {''.join(repos_cards)}
            </div>
            """)
            continue

        # 3. Card Especial: Papers em Destaque
        if "Papers em Destaque" in title:
            paper_items = []
            curr_paper = None

            for l in lines:
                l_str = l.strip()
                if l_str.startswith("* **[") or l_str.startswith("- **["):
                    match_header = re.match(r'[\*\-]\s+\*\*\[([^\]]+)\]\(([^)]+)\)\*\*[:\s—\-]*\s*📄\s+\*\*ArXiv:\s*([^\*]+)\*\*', l_str)
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

            paper_cards = []
            for p in paper_items:
                if "title" in p:
                    desc_text = " ".join(p["desc"])
                    paper_cards.append(f"""
                    <div style="background-color: #fdf2f8; border: 1px solid #fbcfe8; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;">
                        <div style="margin-bottom: 6px;">
                            <a href="{p['url']}" style="color: #0f172a; font-weight: 700; text-decoration: none; font-size: 14px; margin-right: 8px; word-break: break-word;">{p['title']}</a>
                            <span style="display: inline-block; white-space: nowrap; background-color: #fce7f3; color: #be185d; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 999px; margin-top: 2px;">📄 ArXiv: {p['arxiv']}</span>
                        </div>
                        <p style="color: #475569; font-size: 13px; line-height: 1.5; margin: 0;">{desc_text}</p>
                    </div>
                    """)
                else:
                    paper_cards.append(f"""
                    <div style="background-color: #fdf2f8; border: 1px solid #fbcfe8; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;">
                        <p style="margin: 0; font-size: 14px; word-break: break-word;">{p.get('raw_title', '')}</p>
                        <p style="color: #475569; font-size: 13px; line-height: 1.5; margin: 4px 0 0 0;">{' '.join(p.get('desc', []))}</p>
                    </div>
                    """)

            cards_html.append(f"""
            <!-- PAPERS CARD -->
            <a name="papers" id="papers" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <div class="bento-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #db2777; border-radius: 16px; padding: 20px 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);">
                <div style="border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 14px;">
                    <h2 style="color: #be185d; font-size: 15px; margin: 0; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.4;">📄 Papers em Destaque: Pesquisa &amp; Estado da Arte</h2>
                </div>
                {''.join(paper_cards)}
            </div>
            """)
            continue

        # 4. Card Especial: Takeaway Prático de Engenharia
        if "Takeaway" in title or "💡" in title:
            bullets_html = []
            for l in lines:
                l_str = l.strip()
                if l_str.startswith("- ") or l_str.startswith("* "):
                    conteudo = format_inline(l_str[2:])
                    bullets_html.append(f"""
                    <li style="margin-bottom: 8px; line-height: 1.55; color: #713f12; font-size: 13.5px;">
                        {conteudo}
                    </li>
                    """)

            cards_html.append(f"""
            <!-- TAKEAWAY PRÁTICO CARD -->
            <a name="takeaway" id="takeaway" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>
            <div class="bento-card" style="background: linear-gradient(135deg, #fefce8 0%, #ffffff 100%); border: 1px solid #fef08a; border-left: 4px solid #eab308; border-radius: 16px; padding: 18px 20px; margin-bottom: 20px; box-shadow: 0 4px 12px -2px rgba(234, 179, 8, 0.08);">
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    <span style="font-size: 18px; margin-right: 8px;">💡</span>
                    <h2 style="color: #854d0e; font-size: 15px; margin: 0; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Takeaway Prático de Engenharia do Dia</h2>
                </div>
                <ul style="padding-left: 20px; margin: 0;">
                    {''.join(bullets_html)}
                </ul>
            </div>
            """)
            continue

        # 3. Cards Temáticos Padrão (Tópicos 1 a 7)
        items_html = []
        curr_item = None

        for l in lines:
            l_str = l.strip()
            if not l_str:
                continue

            # Remove bug de parênteses soltos como '- )**' ou '- )'
            l_str = re.sub(r'^[\*\-]\s*\)\s*', '- ', l_str)
            l_str = re.sub(r'^[\*\-]\s*\)\*\*', '- **', l_str)

            # Filtro de itens de ausência ou meta-comentários negativos sobre autores
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

                # Substitui badge 🔥 capturando até o final ou dois-pontos
                if "🔥" in item_header:
                    item_header = re.sub(
                        r'—\s*(🔥\s*[^<*\n]+?)(?::\s*|\*\*:|\*\*|\s*$)',
                        r'<span style="display: inline-block; white-space: nowrap; background-color: #ffedd5; color: #c2410c; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; margin-left: 6px; margin-top: 2px; vertical-align: middle;">\1</span>',
                        item_header
                    )

                curr_item = {
                    "header": item_header,
                    "bullets": []
                }
                items_html.append(curr_item)
            elif curr_item is not None and (l.startswith("  ") or l_str.startswith("- ") or l_str.startswith("* ")):
                bullet_text = format_inline(l_str.lstrip("-* "))
                curr_item["bullets"].append(f"<li style='margin-bottom: 5px; color: #475569; font-size: 13.5px; line-height: 1.55;'>{bullet_text}</li>")
            else:
                if not items_html:
                    items_html.append({"raw_p": format_inline(l_str)})

        rendered_items = []
        for it in items_html:
            if "raw_p" in it:
                rendered_items.append(f"<p style='color: #64748b; font-size: 13.5px; font-style: italic; margin: 4px 0;'>{it['raw_p']}</p>")
            else:
                bullets_str = f"<ul style='margin: 6px 0 0 0; padding-left: 18px;'>{''.join(it['bullets'])}</ul>" if it['bullets'] else ""
                rendered_items.append(f"""
                <div style="margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px dashed #f1f5f9;">
                    <div style="font-size: 14.5px; margin-bottom: 4px; color: #0f172a; line-height: 1.45; word-break: break-word;">
                        {it['header']}
                    </div>
                    {bullets_str}
                </div>
                """)

        accent_color = "#3b82f6"
        title_color = "#1d4ed8"

        if "1." in title or "Ferramentas" in title or "Visão" in title or "Visao" in title:
            accent_color = "#f97316"  # Laranja Âmbar (Tópico 1: Ferramentas & Visão)
            title_color = "#c2410c"
        elif "2." in title or "Agentes" in title or "MCP" in title:
            accent_color = "#8b5cf6"  # Roxo Violeta (Tópico 2: Agentes & MCP)
            title_color = "#6d28d9"
        elif "3." in title or "Harness" in title or "Evals" in title:
            accent_color = "#06b6d4"  # Ciano / Teal (Tópico 3: Harness & RAG)
            title_color = "#0e7490"
        elif "4." in title or "Desenvolvimento" in title or "Claude" in title:
            accent_color = "#10b981"  # Verde Esmeralda (Tópico 4: Dev & Claude Code)
            title_color = "#047857"
        elif "5." in title or "Radar" in title or "Perfis" in title:
            accent_color = "#4f46e5"  # Índigo / Azul Royal (Tópico 5: Radar VIP)
            title_color = "#4338ca"
        elif "6." in title or "Capacitação" in title or "Capacitacao" in title or "Hackathons" in title:
            accent_color = "#ec4899"  # Rosa Magenta (Tópico 6: Capacitação & Hackathons)
            title_color = "#be185d"
        elif "7." in title or "Economia" in title or "Mercado" in title:
            accent_color = "#d97706"  # Dourado Ocre (Tópico 7: Economia & Negócios)
            title_color = "#b45309"

        # Remove numeração 1...2...3 do início do título
        title_clean = re.sub(r'^\d+\.\s*', '', title).strip()
        # Se for Radar de Referência, remove nomes entre parênteses (Matt Pocock, Karpathy, etc.)
        if "Radar Perfis" in title_clean or "Radar" in title_clean:
            title_clean = re.sub(r'\s*\(.*?\)', '', title_clean).strip()

        is_radar = ("1." in title or "Ferramentas" in title or "Agentes" in title or "Radar" in title) and not any('name="radar-x"' in c for c in cards_html)
        radar_anchor = '<a name="radar-x" id="radar-x" style="display: block; line-height: 0; font-size: 0; height: 0; text-decoration: none; margin: 0; padding: 0;">&nbsp;</a>\n        ' if is_radar else ''

        cards_html.append(f"""
        <!-- BENTO CARD -->
        {radar_anchor}<div class="bento-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid {accent_color}; border-radius: 16px; padding: 18px 20px; margin-bottom: 18px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);">
            <div style="border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 14px;">
                <h2 style="color: {title_color}; font-size: 15px; margin: 0; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.4;">{title_clean}</h2>
            </div>
            {''.join(rendered_items)}
        </div>
        """)

    body_content = "\n".join(cards_html)
    hoje_formatada = datetime.now().strftime("%d/%m/%Y")

    full_html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resumo Diário de IA</title>
        <style>
            html {{
                scroll-behavior: smooth;
            }}
            .nav-pill {{
                transition: transform 0.15s ease, opacity 0.15s ease;
            }}
            .nav-pill:hover {{
                opacity: 0.85;
                transform: translateY(-1px);
            }}
            @media only screen and (max-width: 600px) {{
                body {{
                    padding: 12px 8px !important;
                }}
                .main-container {{
                    max-width: 100% !important;
                }}
                .header-card {{
                    border-radius: 14px !important;
                }}
                .header-content {{
                    padding: 16px 14px !important;
                }}
                .header-title {{
                    font-size: 19px !important;
                }}
                .nav-container {{
                    text-align: center !important;
                    line-height: 2.3 !important;
                }}
                .nav-pill {{
                    padding: 5px 9px !important;
                    font-size: 11px !important;
                    margin: 3px 3px !important;
                }}
                .bento-card {{
                    padding: 16px 14px !important;
                    border-radius: 12px !important;
                }}
                .footer-card {{
                    border-radius: 14px !important;
                }}
                .footer-content {{
                    padding: 16px 14px !important;
                }}
            }}
        </style>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px 12px; color: #0f172a; -webkit-font-smoothing: antialiased;">
        <!--[if mso]>
        <table role="presentation" width="680" align="center" style="width:680px;" border="0" cellspacing="0" cellpadding="0">
        <tr>
        <td>
        <![endif]-->
        <div class="main-container" style="max-width: 680px; margin: 0 auto;">
            
            <!-- HEADER COM BANNER PANORÂMICO DO CASTELO -->
            <div class="header-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);">
                <div style="width: 100%; line-height: 0; font-size: 0; background-color: #ffffff; max-height: 280px; overflow: hidden;">
                    <img src="{HEADER_BANNER_URL}" alt="Castelo de IA &amp; Coding Agents" width="680" height="280" style="display: block; width: 100%; max-width: 680px; max-height: 280px; height: auto; object-fit: cover; object-position: center; border: 0; outline: none; text-decoration: none; -ms-interpolation-mode: bicubic;" />
                </div>
                <div class="header-content" style="padding: 10px 24px 20px 24px;">
                    <!-- TABELA ANTI-COLISÃO PARA BADGE E DATA -->
                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-bottom: 8px;">
                        <tr>
                            <td align="left" valign="middle">
                                <span style="display: inline-block; background-color: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; padding: 3px 8px; border-radius: 6px; border: 1px solid #e2e8f0;">
                                    Curadoria Diária
                                </span>
                            </td>
                            <td align="right" valign="middle" style="color: #64748b; font-size: 12px; font-weight: 500;">
                                {hoje_formatada} • 08:00
                            </td>
                        </tr>
                    </table>
                    <h1 class="header-title" style="color: #0f172a; margin: 8px 0 6px 0; font-size: 21px; font-weight: 800; letter-spacing: -0.4px;">Diário de Engenharia: IA & Coding Agents</h1>
                    <p style="color: #64748b; font-size: 13.5px; margin: 0; font-weight: 400; line-height: 1.45;">Curadoria técnica por <strong>Fabrycio Bermudes</strong> • Ecossistema de software, agentes autônomos e LLMs.</p>

                    <!-- NAVEGAÇÃO RÁPIDA (ÂNCORAS) -->
                    <div class="nav-container" style="margin-top: 16px; padding-top: 14px; border-top: 1px solid #f1f5f9; line-height: 2.2; text-align: center;">
                        <a href="#destaques" class="nav-pill" style="cursor: pointer; display: inline-block; background-color: #eff6ff; color: #1e40af; font-size: 11.5px; font-weight: 600; text-decoration: none; padding: 5px 12px; border-radius: 999px; border: 1px solid #dbeafe; margin: 3px 4px;">📌 Destaques</a>
                        <a href="#radar-x" class="nav-pill" style="cursor: pointer; display: inline-block; background-color: #f5f3ff; color: #6d28d9; font-size: 11.5px; font-weight: 600; text-decoration: none; padding: 5px 12px; border-radius: 999px; border: 1px solid #ede9fe; margin: 3px 4px;">🤖 Radar &amp; X</a>
                        <a href="#github-trending" class="nav-pill" style="cursor: pointer; display: inline-block; background-color: #fff7ed; color: #c2410c; font-size: 11.5px; font-weight: 600; text-decoration: none; padding: 5px 12px; border-radius: 999px; border: 1px solid #ffedd5; margin: 3px 4px;">🔥 GitHub</a>
                        <a href="#papers" class="nav-pill" style="cursor: pointer; display: inline-block; background-color: #fdf2f8; color: #be185d; font-size: 11.5px; font-weight: 600; text-decoration: none; padding: 5px 12px; border-radius: 999px; border: 1px solid #fce7f3; margin: 3px 4px;">📄 Papers</a>
                        <a href="#takeaway" class="nav-pill" style="cursor: pointer; display: inline-block; background-color: #fefce8; color: #a16207; font-size: 11.5px; font-weight: 600; text-decoration: none; padding: 5px 12px; border-radius: 999px; border: 1px solid #fef08a; margin: 3px 4px;">💡 Takeaway</a>
                    </div>
                </div>
            </div>

            <!-- BENTO GRID CONTAINER -->
            {body_content}

            <!-- FOOTER COM BANNER ARTE 4 E ASSINATURA -->
            <div class="footer-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; margin-top: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);">
                <div style="width: 100%; line-height: 0; font-size: 0; background-color: #0f172a; max-height: 150px; overflow: hidden;">
                    <img src="{FOOTER_BANNER_URL}" alt="Curadoria de Engenharia" width="680" height="150" style="display: block; width: 100%; max-width: 680px; max-height: 150px; height: auto; object-fit: cover; object-position: center; border: 0; outline: none; text-decoration: none; -ms-interpolation-mode: bicubic;" />
                </div>
                <div class="footer-content" style="padding: 22px 24px; text-align: center; background-color: #ffffff;">
                    <p style="font-family: Georgia, Cambria, 'Times New Roman', serif; font-style: italic; font-size: 15px; color: #334155; margin: 0; line-height: 1.5; letter-spacing: 0.2px;">
                        <strong style="color: #0f172a; font-weight: 700; font-style: italic;">Fabrycio Bermudes</strong> • Software Engineer &amp; AI Builder
                    </p>
                </div>
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
    return full_html
