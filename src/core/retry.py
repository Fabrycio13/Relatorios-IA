import time
import random
from typing import Callable, Any
from src.core.logger import get_logger

logger = get_logger("retry_handler")

def retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    operation_name: str = "Operação de rede"
) -> Any:
    """
    Executa uma função com retry automático e backoff exponencial em caso de falha.
    Ideal para proteger chamadas externas (OpenAI API, GitHub API, SMTP).
    """
    attempt = 0
    delay = initial_delay

    while attempt < max_retries:
        try:
            return func()
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                logger.error(f"❌ {operation_name} falhou após {max_retries} tentativas. Erro final: {e}")
                raise e

            sleep_time = delay
            if jitter:
                sleep_time += random.uniform(0.1, 0.8)

            logger.warning(
                f"⚠️ [Tentativa {attempt}/{max_retries}] {operation_name} falhou com erro: '{e}'. "
                f"Aguardando {sleep_time:.2f}s para nova tentativa com backoff exponencial..."
            )
            time.sleep(sleep_time)
            delay *= backoff_factor
