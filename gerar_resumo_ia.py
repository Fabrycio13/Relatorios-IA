import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(BASE_DIR, "tweets_coletados.json")
DATE_STR = datetime.now().strftime("%Y-%m-%d")
hoje = datetime.now()
ontem = hoje - timedelta(days=1)
data_hoje_str = hoje.strftime("%d/%m/%Y")
data_ontem_str = ontem.strftime("%d/%m/%Y")
OUTPUT_MD = os.path.join(BASE_DIR, f"Resumo_IA_{DATE_STR}.md")

PROMPT_SISTEMA = f"""Você é um analista sênior de tecnologia e Inteligência Artificial encarregado de criar o relatório diário oficial de novidades do X (Twitter).

Este relatório cobre o ciclo de 24 horas consolidadas do DIA ANTERIOR ({data_ontem_str}), gerado e emitido em {data_hoje_str}.
Abaixo está uma lista de tweets coletados recentemente em formato JSON.
Sua missão é selecionar, filtrar e consolidar as publicações em um relatório Markdown estruturado OBRIGATORIAMENTE nos seguintes 5 TÓPICOS TEMÁTICOS:

### 1. 🚀 Ferramentas Open-Source, Visão & Ambientes 3D
### 2. 🤖 Agentes Autônomos, MCP & Infraestrutura de Execução
### 3. 💻 Desenvolvimento, Claude Code & Eficiência de Custos
### 4. 🏆 Capacitação Profissional, Cursos & Hackathons
### 5. 🌐 Economia, Modelos de Negócio & Mercado Global de IA

Para cada publicação destacada dentro do seu respectivo tópico:
- Crie um título conciso destacando a ferramenta/inovação, seguido do autor e arroba com link markdown para o tweet original: `* **Nome da Novidade ([@handle](url)):**`
- Adicione 2 a 3 sub-bullets detalhados e concisos explicando:
  - O que é e o que faz
  - Características técnicas principais (ex: licença open-source, modelo usado, métricas de benchmark, etc.)
  - Impacto ou relevância para desenvolvedores e empresas

Cabeçalho padrão a ser incluído no topo:
# 🧠 Relatório Diário de IA - X (Twitter)
**Data de Emissão:** {data_hoje_str} (Referente ao dia {data_ontem_str})  
**Período Analisado:** Ciclo de 24h do dia anterior  
**Fonte:** Feed "Seguindo" (@Fabrycio)  
**Total de Publicações Analisadas:** <coloque a quantidade de tweets considerados>  

---

## 📌 Destaques Principais do Dia

(Siga com os 5 tópicos acima, separando cada tópico com ---)

Retorne APENAS o código Markdown pronto, sem blocos ```markdown ``` envolvendo a resposta."""

def chamar_gemini(api_key, dados_tweets):
    print("Enviando dados para a API do Google Gemini...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt_completo = f"{PROMPT_SISTEMA}\n\nTWEETS COLETADOS:\n{json.dumps(dados_tweets, ensure_ascii=False, indent=2)}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt_completo}]
            }
        ]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        texto = result["candidates"][0]["content"]["parts"][0]["text"]
        return texto

def chamar_openai(api_key, dados_tweets):
    print("Enviando dados para a API da OpenAI (gpt-4o-mini)...")
    url = "https://api.openai.com/v1/chat/completions"
    
    prompt_completo = f"{PROMPT_SISTEMA}\n\nTWEETS COLETADOS:\n{json.dumps(dados_tweets, ensure_ascii=False, indent=2)}"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt_completo}
        ],
        "temperature": 0.4
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        texto = result["choices"][0]["message"]["content"]
        return texto

def gerar_relatorio():
    if not os.path.exists(INPUT_JSON):
        print(f"[ERRO] Arquivo de tweets não encontrado: {INPUT_JSON}")
        return False
        
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        tweets = json.load(f)
        
    if not tweets:
        print("[AVISO] Nenhum tweet coletado no JSON.")
        return False

    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    
    relatorio_md = None
    
    if gemini_key:
        try:
            relatorio_md = chamar_gemini(gemini_key, tweets)
        except Exception as e:
            print(f"Erro ao chamar Gemini API: {e}")
            
    if not relatorio_md and openai_key:
        try:
            relatorio_md = chamar_openai(openai_key, tweets)
        except Exception as e:
            print(f"Erro ao chamar OpenAI API: {e}")
            
    if not relatorio_md:
        print("[ERRO] Nenhuma chave de IA (GEMINI_API_KEY ou OPENAI_API_KEY) configurada ou todas falharam.")
        return False

    # Limpeza de eventuais backticks de markdown que o modelo possa ter inserido
    relatorio_md = relatorio_md.strip()
    if relatorio_md.startswith("```markdown"):
        relatorio_md = relatorio_md[len("```markdown"):].strip()
    elif relatorio_md.startswith("```"):
        relatorio_md = relatorio_md[3:].strip()
    if relatorio_md.endswith("```"):
        relatorio_md = relatorio_md[:-3].strip()

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(relatorio_md)
        
    print(f"✅ Relatório estruturado gerado com sucesso em: {OUTPUT_MD}")
    return True

if __name__ == "__main__":
    sucesso = gerar_relatorio()
    sys.exit(0 if sucesso else 1)
