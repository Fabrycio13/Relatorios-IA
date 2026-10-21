import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Diretórios principais do projeto
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
SCRIPTS_DIR = BASE_DIR / "scripts"
ASSETS_DIR = BASE_DIR / "assets"

# Garante que os diretórios essenciais existam
for d in [DATA_DIR, REPORTS_DIR, LOGS_DIR, SCRIPTS_DIR, ASSETS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Arquivos de dados e logs
GITHUB_DATA_FILE = DATA_DIR / "github_trending.json"
TWEETS_DATA_FILE = DATA_DIR / "tweets_coletados.json"
STATUS_FILE = DATA_DIR / "ultimo_envio.txt"
LOG_FILE = LOGS_DIR / "execucao.log"

# URLs públicas dos banners hospedados no próprio repositório
HEADER_BANNER_URL = "https://raw.githubusercontent.com/Fabrycio13/Relatorios-IA/main/assets/header_banner.jpg"
FOOTER_BANNER_URL = "https://raw.githubusercontent.com/Fabrycio13/Relatorios-IA/main/assets/footer_banner.jpg"

# Carrega variáveis do arquivo .env
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)

class Config:
    """Central de configurações do projeto com suporte a variáveis de ambiente e fallbacks seguros."""

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

    # Twitter / X
    TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    TWITTER_CT0 = os.getenv("TWITTER_CT0", "").strip()

    # Gmail SMTP
    GMAIL_USER = os.getenv("GMAIL_USER", "bermudes.fbc@gmail.com").strip()
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    GMAIL_TO = os.getenv("GMAIL_TO", "fabrycio.bermudes@usabit.com.br").strip()

    @classmethod
    def get_twitter_credentials(cls):
        """Retorna os cookies do Twitter, priorizando .env com fallback para auth.json se existir."""
        auth_token = cls.TWITTER_AUTH_TOKEN
        ct0 = cls.TWITTER_CT0

        # Fallback: auth.json legado
        if not auth_token or not ct0:
            for legacy_path in [BASE_DIR / "auth.json", DATA_DIR / "auth.json"]:
                if legacy_path.exists():
                    try:
                        with open(legacy_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            auth_token = auth_token or data.get("auth_token", "")
                            ct0 = ct0 or data.get("ct0", "")
                    except Exception:
                        pass

        return auth_token, ct0

    @classmethod
    def get_email_credentials(cls):
        """Retorna as credenciais de e-mail, priorizando .env com fallback para email_config.json."""
        remetente = cls.GMAIL_USER
        senha = cls.GMAIL_APP_PASSWORD
        destinatario = cls.GMAIL_TO

        # Fallback: email_config.json legado
        if not senha:
            for legacy_path in [BASE_DIR / "email_config.json", DATA_DIR / "email_config.json"]:
                if legacy_path.exists():
                    try:
                        with open(legacy_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            remetente = remetente or data.get("remetente", "")
                            senha = senha or data.get("senha_app", "")
                            destinatario = destinatario or data.get("destinatario", "")
                    except Exception:
                        pass

        return remetente, senha, destinatario

    @classmethod
    def obter_ultimo_relatorio(cls) -> Path | None:
        """Localiza o relatório mais recente salvo em reports/ (ou legado na raiz)."""
        arquivos = list(REPORTS_DIR.glob("Resumo_IA_*.md"))
        if not arquivos:
            arquivos = list(BASE_DIR.glob("Resumo_IA_*.md"))
        if not arquivos:
            return None
        arquivos.sort(reverse=True)
        return arquivos[0]

config = Config()
