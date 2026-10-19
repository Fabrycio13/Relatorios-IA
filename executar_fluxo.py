import subprocess
import sys
import os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_step(step_name, command):
    print("\n" + "=" * 60)
    print(f"▶️  ETAPA: {step_name}")
    print("=" * 60)
    res = subprocess.run([sys.executable] + command, cwd=BASE_DIR)
    if res.returncode != 0:
        print(f"\n❌ [FALHA] Etapa '{step_name}' encerrou com código {res.returncode}")
        return False
    print(f"\n✅ [SUCESSO] Etapa '{step_name}' concluída!")
    return True

def main():
    print("🚀 INICIANDO FLUXO COMPLETO DO RELATÓRIO DIÁRIO DE IA...")
    
    # Etapa 1: Coletar tweets do X
    if not run_step("Coleta de Tweets do X", ["coletar_tweets.py"]):
        sys.exit(1)
        
    # Etapa 2: Gerar Resumo estruturado com IA
    if not run_step("Geração do Resumo Inteligente com IA", ["gerar_resumo_ia.py"]):
        sys.exit(1)
        
    # Etapa 3: Enviar E-mail formatado
    if not run_step("Envio do E-mail Formatado", ["enviar_email.py"]):
        sys.exit(1)
        
    print("\n" + "=" * 60)
    print("🎉 FLUXO COMPLETO CONCLUÍDO COM SUCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    main()
