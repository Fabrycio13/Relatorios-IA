import logging
import sys
from logging.handlers import RotatingFileHandler
from .config import LOG_FILE

# Garante suporte seguro a emojis e UTF-8 no Windows Console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_logger = None

def get_logger(name: str = "relatorios_ia") -> logging.Logger:
    """Retorna uma instância configurada do logger padrão do projeto com saída em console e arquivo rotativo."""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Evita duplicação de handlers se chamado múltiplas vezes
    if logger.hasHandlers():
        return logger

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler para o Console / Terminal
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler para arquivo rotativo em logs/execucao.log (máx 5MB por arquivo, até 3 backups)
    try:
        file_handler = RotatingFileHandler(
            filename=str(LOG_FILE),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Não foi possível inicializar arquivo de log em {LOG_FILE}: {e}")

    _logger = logger
    return logger
