import json
import os
import re
import smtplib
import sys
from datetime import datetime
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

def markdown_to_html(md_text):
    """
    Converte markdown simplificado em HTML formatado com estilo elegante para e-mails.
    """
    html_lines = []
    in_list = False

    for raw_line in md_text.splitlines():
        line = raw_line.strip()

        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        # Títulos
        if line.startswith("# "):
            if in_list: html_lines.append("</ul>"); in_list = False
            html_lines.append(f"<h1 style='color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;'>{line[2:]}</h1>")
            continue
        elif line.startswith("## "):
            if in_list: html_lines.append("</ul>"); in_list = False
            html_lines.append(f"<h2 style='color: #0f172a; margin-top: 24px; margin-bottom: 12px; font-size: 20px;'>{line[3:]}</h2>")
            continue
        elif line.startswith("### "):
            if in_list: html_lines.append("</ul>"); in_list = False
            html_lines.append(f"<h3 style='color: #2563eb; margin-top: 18px; margin-bottom: 8px; font-size: 16px;'>{line[4:]}</h3>")
            continue

        # Separador
        if line == "---":
            if in_list: html_lines.append("</ul>"); in_list = False
            html_lines.append("<hr style='border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;'>")
            continue

        # Sub-bullet / listas
        is_subbullet = raw_line.startswith("  * ") or raw_line.startswith("    * ")
        is_bullet = line.startswith("* ") or line.startswith("- ")

        # Formatação inline: links [texto](url)
        formatted_line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #2563eb; text-decoration: none; font-weight: 500;">\1</a>', line)
        # Negrito **texto**
        formatted_line = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', formatted_line)
        # Itálico *texto*
        formatted_line = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', formatted_line)
        # Código inline `código`
        formatted_line = re.sub(r'`([^`]+)`', r'<code style="background-color: #f1f5f9; padding: 2px 4px; border-radius: 4px; font-family: monospace; font-size: 90%;">\1</code>', formatted_line)

        if is_subbullet:
            content = formatted_line.replace("* ", "", 1) if formatted_line.startswith("* ") else formatted_line
            html_lines.append(f"<li style='margin-left: 20px; color: #475569; margin-bottom: 4px;'>{content}</li>")
        elif is_bullet:
            if not in_list:
                html_lines.append("<ul style='padding-left: 20px; margin: 8px 0;'>")
                in_list = True
            content = formatted_line[2:]
            html_lines.append(f"<li style='margin-bottom: 6px; color: #334155;'>{content}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p style='color: #334155; line-height: 1.6; margin: 6px 0;'>{formatted_line}</p>")

    if in_list:
        html_lines.append("</ul>")

    content_html = "\n".join(html_lines)

    full_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); padding: 32px; border: 1px solid #e2e8f0;">
            <div style="text-align: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #3b82f6;">
                <span style="font-size: 28px;">🧠</span>
                <h1 style="color: #0f172a; margin: 8px 0 4px 0; font-size: 22px;">Resumo Diário de Inteligência Artificial</h1>
                <p style="color: #64748b; font-size: 13px; margin: 0;">Relatório Automatizado do X (Twitter) • Feed Especializado</p>
            </div>
            <div style="font-size: 14px; line-height: 1.6;">
                {content_html}
            </div>
            <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #e2e8f0; text-align: center; color: #94a3b8; font-size: 12px;">
                Gerado automaticamente pelo agente de relatórios de IA em {datetime.now().strftime('%d/%m/%Y às %H:%M')}.
            </div>
        </div>
    </body>
    </html>
    """
    return full_template

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

    data_hoje = datetime.now().strftime("%d/%m/%Y")
    assunto = f"🧠 Resumo de IA - Feed do X ({data_hoje})"

    html_content = markdown_to_html(md_content)

    if not senha_app or senha_app.strip() == "sua_senha_de_app_aqui" or len(senha_app.strip()) < 8:
        print("\n" + "=" * 60)
        print("⚠️  CONFIGURAÇÃO DE E-MAIL DO GMAIL NECESSÁRIA")
        print("=" * 60)
        print("Para enviar e-mails diretamente pelo Gmail com segurança, o Google")
        print("exige uma 'Senha de Aplicativo' (App Password de 16 caracteres).")
        print("\nPasso a passo rápido:")
        print(" 1. Acesse: https://myaccount.google.com/apppasswords")
        print(" 2. Dê um nome (ex: 'Relatorios IA') e gere a senha de 16 letras.")
        print(f" 3. Salve a senha no arquivo '{CONFIG_FILE}' como mostrado abaixo:\n")
        
        exemplo_conteudo = {
            "remetente": remetente,
            "senha_app": "xxxx xxxx xxxx xxxx",
            "destinatario": destinatario_final
        }
        print(json.dumps(exemplo_conteudo, indent=2))
        print("=" * 60)

        # Cria ou atualiza template se não existir
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(exemplo_conteudo, f, indent=2, ensure_ascii=False)
            print(f"\n[OK] Criado arquivo modelo em: {CONFIG_FILE}")

        return False

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
        # Usa SSL na porta 465 ou TLS na 587
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            senha_limpa = senha_app.replace(" ", "")
            server.login(remetente, senha_limpa)
            server.sendmail(remetente, [destinatario_final], msg.as_string())

        print(f"✅ E-mail enviado com sucesso para {destinatario_final}!")
        return True
    except smtplib.SMTPAuthenticationError:
        print("\n❌ Erro de Autenticação no Gmail!")
        print("A senha de aplicativo inserida não foi aceita pelo Google.")
        print("Verifique se gerou a senha em https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"\n❌ Erro ao enviar e-mail: {e}")
        return False

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else None
    arquivo = sys.argv[2] if len(sys.argv) > 2 else None
    sucesso = enviar_relatorio_email(destinatario=dest, caminho_relatorio=arquivo)
    sys.exit(0 if sucesso else 1)
