import json
import os
import re
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "email_config.json")
CONFIG_EXAMPLE = os.path.join(BASE_DIR, "email_config.example.json")

# URLs públicas dos banners hospedados no próprio repositório Relatorios-IA
HEADER_BANNER_URL = "https://raw.githubusercontent.com/Fabrycio13/Relatorios-IA/main/assets/header_banner.jpg"
FOOTER_BANNER_URL = "https://raw.githubusercontent.com/Fabrycio13/Relatorios-IA/main/assets/footer_banner.jpg"

def format_inline(text):
    """Aplica formatação inline básica em markdown (links, negrito, itálico, código)."""
    # Links
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #2563eb; text-decoration: none; font-weight: 600;">\1</a>', text)
    # Negrito
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong style="color: #0f172a; font-weight: 600;">\1</strong>', t)
    # Itálico
    t = re.sub(r'\*([^*]+)\*', r'<em style="color: #64748b;">\1</em>', t)
    # Código inline
    t = re.sub(r'`([^`]+)`', r'<code style="background-color: #f1f5f9; color: #0f172a; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 85%; border: 1px solid #e2e8f0;">\1</code>', t)
    return t

def render_bento_email(md_text):
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
            <div class="bento-card" style="background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%); border: 1px solid #bfdbfe; border-radius: 16px; padding: 18px 20px; margin-bottom: 20px; box-shadow: 0 4px 12px -2px rgba(59, 130, 246, 0.08);">
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
                    match_header = re.match(r'[\*\-]\s+\*\*\[([^\]]+)\]\(([^)]+)\)\*\*\s+—\s+⭐\s+\*\*([^\*]+)\*\*\s+\(([^)]+)\)', l_str)
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
            <div class="bento-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 20px 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);">
                <div style="border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 14px;">
                    <h2 style="color: #0f172a; font-size: 16px; margin: 0; font-weight: 700;">🔥 GitHub Trending: Repositórios de IA em Alta no Dia</h2>
                    <p style="color: #64748b; font-size: 12px; margin: 3px 0 0 0;">Projetos em destaque com resumo e aplicabilidade em português</p>
                </div>
                {''.join(repos_cards)}
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
        if "Radar Perfis" in title: accent_color = "#8b5cf6"
        elif "Harness" in title: accent_color = "#06b6d4"
        elif "Desenvolvimento" in title: accent_color = "#10b981"
        elif "Ferramentas" in title: accent_color = "#f59e0b"

        cards_html.append(f"""
        <!-- BENTO CARD -->
        <div class="bento-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 20px 20px; margin-bottom: 18px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);">
            <div style="display: flex; align-items: center; border-bottom: 2px solid #f8fafc; padding-bottom: 10px; margin-bottom: 14px;">
                <div style="width: 4px; height: 16px; background-color: {accent_color}; border-radius: 2px; margin-right: 8px;"></div>
                <h2 style="color: #0f172a; font-size: 15.5px; margin: 0; font-weight: 700; letter-spacing: -0.2px;">{title}</h2>
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
            
            <!-- HEADER COM BANNER PANORÂMICO -->
            <div class="header-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);">
                <div style="width: 100%; line-height: 0; font-size: 0; background-color: #0f172a;">
                    <img src="{HEADER_BANNER_URL}" alt="Diário de Engenharia: IA &amp; Coding Agents" width="680" style="display: block; width: 100%; max-width: 680px; height: auto; border: 0; outline: none; text-decoration: none; -ms-interpolation-mode: bicubic;" />
                </div>
                <div class="header-content" style="padding: 22px 24px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="display: inline-block; background-color: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; padding: 3px 8px; border-radius: 6px; border: 1px solid #e2e8f0;">
                            Curadoria Diária
                        </span>
                        <span style="color: #64748b; font-size: 12px; font-weight: 500;">
                            {hoje_formatada} • 08:00
                        </span>
                    </div>
                    <h1 class="header-title" style="color: #0f172a; margin: 8px 0 4px 0; font-size: 21px; font-weight: 800; letter-spacing: -0.4px;">Diário de Engenharia: IA & Coding Agents</h1>
                    <p style="color: #64748b; font-size: 13.5px; margin: 0; font-weight: 400; line-height: 1.4;">Curadoria técnica por <strong>Fabrycio Bermudes</strong> • Ecossistema de software, agentes autônomos e LLMs.</p>
                </div>
            </div>

            <!-- BENTO GRID CONTAINER -->
            {body_content}

            <!-- FOOTER COM BANNER ARTE 4 E ASSINATURA -->
            <div class="footer-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; margin-top: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);">
                <div style="width: 100%; line-height: 0; font-size: 0; background-color: #0f172a;">
                    <img src="{FOOTER_BANNER_URL}" alt="Curadoria de Engenharia" width="680" style="display: block; width: 100%; max-width: 680px; height: auto; border: 0; outline: none; text-decoration: none; -ms-interpolation-mode: bicubic;" />
                </div>
                <div class="footer-content" style="padding: 20px 24px; text-align: center; background-color: #ffffff;">
                    <p style="color: #0f172a; font-size: 13.5px; font-weight: 700; margin: 0 0 4px 0; letter-spacing: -0.2px;">
                        Curadoria & Automação por Fabrycio Bermudes
                    </p>
                    <p style="color: #64748b; font-size: 12px; margin: 0 0 10px 0;">
                        Desenvolvido para Usabit • Relatório diário de IA e Coding Agents
                    </p>
                    <div style="border-top: 1px solid #f1f5f9; padding-top: 10px; margin-top: 6px;">
                        <span style="color: #94a3b8; font-size: 11px;">
                            Enviado para fabrycio.bermudes@usabit.com.br • Agendado diariamente às 08:00 BRT
                        </span>
                    </div>
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

def carregar_config():
    config = {
        "remetente": os.environ.get("GMAIL_USER", "bermudes.fbc@gmail.com"),
        "senha_app": os.environ.get("GMAIL_APP_PASSWORD", ""),
        "destinatario": os.environ.get("GMAIL_TO", "fabrycio.bermudes@usabit.com.br")
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception as e:
            print(f"Aviso ao ler {CONFIG_FILE}: {e}")

    return config

def obter_ultimo_relatorio():
    arquivos = [f for f in os.listdir(BASE_DIR) if f.startswith("Resumo_IA_") and f.endswith(".md")]
    if not arquivos:
        return None
    arquivos.sort(reverse=True)
    return os.path.join(BASE_DIR, arquivos[0])

def enviar_relatorio_email(destinatario=None, caminho_relatorio=None):
    config = carregar_config()

    if destinatario:
        config["destinatario"] = destinatario

    remetente = config.get("remetente")
    senha_app = config.get("senha_app")
    destinatario_final = config.get("destinatario")

    if not caminho_relatorio:
        caminho_relatorio = obter_ultimo_relatorio()

    if not caminho_relatorio or not os.path.exists(caminho_relatorio):
        print(f"[ERRO] Nenhum arquivo de relatório encontrado em {BASE_DIR}")
        return False

    with open(caminho_relatorio, "r", encoding="utf-8") as f:
        md_content = f.read()

    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    hora_envio = hoje.strftime("%H:%M")
    assunto = f"🧠 Resumo Diário de IA (Destaques de {ontem.strftime('%d/%m/%Y')}) • {hora_envio}"

    # Renderiza com o Bento Grid Modular 100% responsivo para mobile
    html_content = render_bento_email(md_content)

    if not senha_app or senha_app.strip() == "sua_senha_de_app_aqui" or len(senha_app.strip()) < 8:
        print("[ERRO] Senha de app não configurada.")
        return False

    # Estrutura MIME 'alternative' limpa (sem anexos binários, elimina chips de anexo no Gmail)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario_final

    part_text = MIMEText(md_content, "plain", "utf-8")
    part_html = MIMEText(html_content, "html", "utf-8")

    msg.attach(part_text)
    msg.attach(part_html)

    print(f"Conectando ao servidor SMTP do Gmail para enviar para {destinatario_final}...")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            senha_limpa = senha_app.replace(" ", "")
            server.login(remetente, senha_limpa)
            server.sendmail(remetente, [destinatario_final], msg.as_string())

        print(f"✅ E-mail enviado com sucesso para {destinatario_final}!")
        return True
    except Exception as e:
        print(f"\n❌ Erro ao enviar e-mail: {e}")
        return False

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else None
    arquivo = sys.argv[2] if len(sys.argv) > 2 else None
    sucesso = enviar_relatorio_email(destinatario=dest, caminho_relatorio=arquivo)
    sys.exit(0 if sucesso else 1)
