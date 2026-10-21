import subprocess
import sys
import os
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "execucao.log")
STATUS_FILE = os.path.join(BASE_DIR, "ultimo_envio.txt")

def log(msg):
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{data_hora}] {msg}"
    print(linha)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass

def run_step(step_name, command):
    log(f"▶️  INICIANDO ETAPA: {step_name}")
    res = subprocess.run([sys.executable] + command, cwd=BASE_DIR)
    if res.returncode != 0:
        log(f"❌ [FALHA] Etapa '{step_name}' encerrou com código de erro {res.returncode}")
        return False
    log(f"✅ [SUCESSO] Etapa '{step_name}' concluída com sucesso.")
    return True

def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    hoje_str = datetime.now().strftime("%Y-%m-%d")

    # Verifica se já rodou com sucesso no dia de hoje (evita duplicidade ao religar/reiniciar o PC)
    if not force and os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                ultimo_dia = f.read().strip()
            if ultimo_dia == hoje_str:
                log(f"ℹ️  [OK] O relatório de hoje ({hoje_str}) já foi enviado com sucesso mais cedo. Nenhuma ação necessária.")
                return
        except Exception:
            pass

    log("=" * 60)
    log(f"🚀 INICIANDO FLUXO COMPLETO DO RELATÓRIO DIÁRIO DE IA (D-1)")
    log("=" * 60)
    
    # Etapa 1: Coletar tweets do X
    if not run_step("Coleta de Tweets do X", ["coletar_tweets.py"]):
        log("Fluxo interrompido devido a erro na coleta de tweets.")
        sys.exit(1)

    # Etapa 2: Coletar repositórios em alta de IA no GitHub
    run_step("Coleta de Repositórios em Alta do GitHub", ["coletar_github.py"])
        
    # Etapa 3: Gerar Resumo estruturado com IA
    if not run_step("Geração do Resumo Inteligente com IA", ["gerar_resumo_ia.py"]):
        log("Fluxo interrompido devido a erro na geração com IA.")
        sys.exit(1)
        
    # Etapa 4: Enviar E-mail formatado
    if not run_step("Envio do E-mail Formatado", ["enviar_email.py"]):
        log("Fluxo interrompido devido a erro no envio de e-mail.")
        sys.exit(1)

    # Marca a data de hoje como enviada com sucesso
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(hoje_str)
    except Exception:
        pass
        
    log("=" * 60)
    log("🎉 FLUXO COMPLETO CONCLUÍDO COM SUCESSO! E-mail entregue.")
    log("=" * 60 + "\n")

if __name__ == "__main__":
    main()
