import json
import os
import sys
import time
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
Abaixo está uma lista de tweets coletados recentemente em formato JSON, contendo autor, texto, link e métricas de engajamento (likes, reposts, replies, views).

CRITÉRIOS DE SELEÇÃO E DISTRIBUIÇÃO DINÂMICA:
1. FILTRO ESTRITO DE INTELIGÊNCIA ARTIFICIAL:
   - Inclua EXCLUSIVAMENTE publicações relacionadas a Inteligência Artificial, Modelos de Linguagem (LLMs), Agentes Autônomos, Coding Agents, MCP, Visão Computacional, 3D com IA, Infraestrutura/Hardware para IA e Negócios/Economia impulsionados por IA.
   - DESCARTE OBRIGATORIAMENTE tweets fora do escopo de IA (ex: finanças tradicionais, jogos sem IA, marketing genérico, política ou notícias não relacionadas a IA).
2. DISTRIBUIÇÃO DINÂMICA (SEM PREENCHIMENTO ARTIFICIAL):
   - A quantidade de itens por tópico deve ser DINÂMICA e orgânica, refletindo o volume real de novidades do dia (de 0 a 5+ itens por categoria).
   - Se um tópico (como 'Ferramentas' ou 'Agentes') teve 3, 4 ou mais novidades de alto impacto, inclua TODAS elas!
   - Se um tópico não teve novidades genuínas de IA no período, deixe uma nota breve e elegante informando que não houve anúncios relevantes no ciclo, sem forçar itens irrelevantes.
3. PRIORIZAÇÃO POR RELEVÂNCIA TÉCNICA E ENGAJAMENTO:
   - Dê prioridade máxima a projetos open-source com repositórios reais (GitHub), lançamentos de modelos, papers (ArXiv) e ferramentas práticas.
   - Use o número de curtidas (likes), comentários (replies) e reposts para ranquear e priorizar as discussões que mais repercutiram no dia.
   - Se o tweet mencionar ou contiver link para GitHub, ArXiv, artigos externos (`external_links`) ou demonstração direta, SEMPRE inclua esse link formatado em markdown nos sub-bullets!

Sua missão é selecionar, filtrar e consolidar as publicações em um relatório Markdown estruturado nos seguintes TÓPICOS TEMÁTICOS:

### 1. 🚀 Ferramentas Open-Source, Visão & Ambientes 3D
### 2. 🤖 Agentes Autônomos, MCP & Infraestrutura de Execução
### 3. 🧪 Harness Engineering, Evals & RAG Avançado
(Dedique este tópico a evals de modelos/agentes, frameworks de harness, testes automatizados de agentes, recuperação semântica, RAG, embeddings e benchmarks práticos de confiabilidade).
### 4. 💻 Desenvolvimento, Claude Code & Eficiência de Custos
### 5. 🎯 Radar Perfis de Referência (Matt Pocock, Karpathy, Swyx, Jason Liu, Chip Huyen, Santiago)
(Destaque exclusivo para posts, threads, análises de engenharia, evals e novidades compartilhadas por esses criadores e líderes técnicos de IA no período).
### 6. 🏆 Capacitação Profissional, Cursos & Hackathons
### 7. 🌐 Economia, Modelos de Negócio & Mercado Global de IA

Para cada publicação destacada dentro do seu respectivo tópico:
- Crie um título conciso destacando a ferramenta/inovação, seguido do autor e arroba com link markdown para o tweet original:
  `* **Nome da Novidade ([@handle](url)):**`
  (Se o tweet tiver métricas notáveis de engajamento, adicione ao lado, ex: `* **Nome da Novidade ([@handle](url)) — 🔥 1.4k likes:**`)
- Adicione 2 a 3 sub-bullets detalhados e concisos explicando:
  - O que é, o que faz e como funciona
  - Características técnicas principais (ex: licença open-source, modelo usado, métricas de benchmark, links para repositórios GitHub, papers ArXiv ou artigos detalhados quando disponíveis)
  - Impacto ou relevância prática para desenvolvedores e empresas

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
    print("Enviando dados para a API da OpenAI (gpt-6-luna)...")
    url = "https://api.openai.com/v1/chat/completions"
    
    # Envia apenas os campos úteis para a IA não ter sobrecarga de dados desnecessários
    tweets_limpos = []
    for t in dados_tweets:
        item = {
            "autor": f"{t.get('author_name')} ({t.get('author_handle')})",
            "data": t.get("timestamp"),
            "texto": t.get("text"),
            "url": t.get("url"),
            "engajamento": f"{t.get('likes', '0')} likes, {t.get('reposts', '0')} reposts, {t.get('replies', '0')} replies"
        }
        if t.get("external_links"):
            item["links_externos"] = t["external_links"]
        tweets_limpos.append(item)

    prompt_completo = f"{PROMPT_SISTEMA}\n\nTWEETS COLETADOS:\n{json.dumps(tweets_limpos, ensure_ascii=False, indent=2)}"
    payload = {
        "model": "gpt-6-luna",
        "messages": [
            {"role": "user", "content": prompt_completo}
        ]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    
    for tentativa in range(2):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                texto = result["choices"][0]["message"]["content"]
                return texto
        except Exception as err:
            if tentativa == 0:
                print(f"Tentativa 1 falhou ({err}), tentando novamente em 5s...")
                time.sleep(5)
            else:
                raise err

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

    # Anexa a seção de GitHub Trending no final do relatório se houver dados coletados
    gh_file = os.path.join(BASE_DIR, "github_trending.json")
    if os.path.exists(gh_file):
        try:
            with open(gh_file, "r", encoding="utf-8") as f:
                trending_repos = json.load(f)
            if trending_repos:
                secao_gh = ["\n\n---\n\n## 🔥 GitHub Trending: Repositórios de IA em Alta no Dia\n"]
                for r in trending_repos:
                    stars_str = f"{r['stars']:,}".replace(",", ".")
                    desc = r.get("description", "Sem descrição disponível").strip()
                    lang = r.get("language", "N/A")
                    secao_gh.append(f"* **[{r['full_name']}]({r['url']})** — ⭐ **{stars_str} stars** ({lang})")
                    secao_gh.append(f"  - {desc}")
                relatorio_md += "\n".join(secao_gh)
        except Exception as e:
            print(f"Aviso ao anexar GitHub Trending: {e}")

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(relatorio_md)
        
    print(f"✅ Relatório estruturado gerado com sucesso em: {OUTPUT_MD}")
    return True

if __name__ == "__main__":
    sucesso = gerar_relatorio()
    sys.exit(0 if sucesso else 1)
