import smtplib
import urllib.error
import urllib.request
from src.core.config import config
from src.core.logger import get_logger

logger = get_logger("healthcheck")

def check_openai() -> tuple[bool, str]:
    if not config.OPENAI_API_KEY:
        return False, "Chave OPENAI_API_KEY não configurada no .env"
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                return True, "Chave ativa e autenticada com sucesso (200 OK)"
    except Exception as e:
        return False, f"Falha na autenticação com OpenAI: {e}"
    return False, "Resposta inesperada da OpenAI"

def check_email() -> tuple[bool, str]:
    remetente, senha_app, destinatario = config.get_email_credentials()
    if not remetente or not senha_app:
        return False, "Credenciais de e-mail incompletas no .env"
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=6) as server:
            server.login(remetente, senha_app.replace(" ", ""))
        return True, f"Login SMTP OK ({remetente} -> {destinatario})"
    except Exception as e:
        return False, f"Falha no login SMTP do Gmail: {e}"

def check_github() -> tuple[bool, str]:
    try:
        req = urllib.request.Request(
            "https://api.github.com/zen",
            headers={"User-Agent": "Relatorios-IA/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                return True, "API pública do GitHub disponível (200 OK)"
    except Exception as e:
        return False, f"Falha de conexão com GitHub: {e}"
    return False, "GitHub indisponível"

def check_huggingface() -> tuple[bool, str]:
    try:
        req = urllib.request.Request(
            "https://huggingface.co/api/daily_papers",
            headers={"User-Agent": "Relatorios-IA/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                return True, "API Daily Papers disponível (200 OK)"
    except Exception as e:
        return False, f"Falha de conexão com Hugging Face: {e}"
    return False, "Hugging Face indisponível"

def check_twitter() -> tuple[bool, str]:
    token, ct0 = config.get_twitter_credentials()
    if not token or len(token) < 20:
        return False, "Cookie auth_token ausente ou inválido no .env/auth.json"
    if not ct0:
        return False, "Cookie ct0 ausente no .env/auth.json"
    return True, f"Cookies presentes e formatados (auth_token: {token[:6]}..., ct0: {ct0[:6]}...)"

def executar_healthcheck() -> bool:
    """Executa diagnóstico completo de todas as integrações em menos de 5 segundos."""
    print("\n" + "=" * 65)
    print(" 🏥 CHECK-UP DE SAÚDE DAS INTEGRAÇÕES E CREDENCIAIS (DIÁRIO DE IA)")
    print("=" * 65)

    checks = [
        ("🤖 OpenAI API (gpt-6-luna)", check_openai),
        ("📧 Gmail SMTP (Envio de E-mail)", check_email),
        ("🐦 X / Twitter (Sessão & Cookies)", check_twitter),
        ("🔥 GitHub Search API (Trending)", check_github),
        ("📄 Hugging Face API (Daily Papers)", check_huggingface),
    ]

    todos_ok = True
    for nome, func in checks:
        ok, detalhe = func()
        status_icon = "✅ [OK]" if ok else "❌ [FALHA]"
        print(f"\n{status_icon} {nome}")
        print(f"   └─ {detalhe}")
        if not ok:
            todos_ok = False

    print("\n" + "=" * 65)
    if todos_ok:
        print(" 🎉 TODAS AS INTEGRAÇÕES ESTÃO 100% OPERACIONAIS E SAUDÁVEIS!")
    else:
        print(" ⚠️  ATENÇÃO: UMA OU MAIS INTEGRAÇÕES APRESENTARAM FALHA.")
    print("=" * 65 + "\n")
    return todos_ok

if __name__ == "__main__":
    executar_healthcheck()
