import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

from src.core.config import (
    BASE_DIR,
    DATA_DIR,
    REPORTS_DIR,
    GITHUB_DATA_FILE,
    TWEETS_DATA_FILE,
    config
)
from src.core.logger import get_logger

logger = get_logger("ai_summarizer")

def chamar_gemini(api_key, tweets, prompt_sistema):
    logger.info("Chamando Gemini API (gemini-2.5-flash)...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    prompt_completo = f"{prompt_sistema}\n\nTWEETS COLETADOS:\n{json.dumps(tweets, ensure_ascii=False, indent=2)}"

    payload = {
        "contents": [{"parts": [{"text": prompt_completo}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192}
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["candidates"][0]["content"]["parts"][0]["text"]

def chamar_openai(api_key, tweets, prompt_sistema):
    logger.info("Chamando OpenAI API (gpt-6-luna)...")
    url = "https://api.openai.com/v1/chat/completions"
    prompt_completo = f"{prompt_sistema}\n\nTWEETS COLETADOS:\n{json.dumps(tweets, ensure_ascii=False, indent=2)}"

    payload = {
        "model": "gpt-6-luna",
        "messages": [
            {"role": "system", "content": "Você é um analista sênior de Inteligência Artificial e Engenharia de Software."},
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["choices"][0]["message"]["content"]

def gerar_resumo_ia() -> Path | None:
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    data_hoje_str = hoje.strftime("%d/%m/%Y")
    data_ontem_str = ontem.strftime("%d/%m/%Y")
    date_str = hoje.strftime("%Y-%m-%d")
    output_md = REPORTS_DIR / f"Resumo_IA_{date_str}.md"

    logger.info("=" * 60)
    logger.info(f"Iniciando síntese inteligente com IA para {data_hoje_str}...")
    logger.info("=" * 60)

    if not TWEETS_DATA_FILE.exists():
        logger.error(f"Arquivo de tweets não encontrado em {TWEETS_DATA_FILE}")
        return None

    with open(TWEETS_DATA_FILE, "r", encoding="utf-8") as f:
        tweets = json.load(f)

    logger.info(f"Carregados {len(tweets)} tweets de {TWEETS_DATA_FILE}")

    prompt_sistema = f"""Você é um analista sênior de tecnologia e Inteligência Artificial encarregado de criar o relatório diário oficial de novidades do X (Twitter).

Este relatório consolida as principais novidades de IA gerado em {data_hoje_str} (focando no ciclo recente das últimas 24h a 48h, incluindo os destaques de {data_ontem_str} e publicações recentes dos autores VIPs no X).
Abaixo está uma lista de tweets coletados recentemente em formato JSON, contendo autor, texto, link e métricas de engajamento (likes, reposts, replies, views).

CRITÉRIOS DE SELEÇÃO E DISTRIBUIÇÃO DINÂMICA:
1. FILTRO ESTRITO DE INTELIGÊNCIA ARTIFICIAL:
   - Inclua EXCLUSIVAMENTE publicações relacionadas a Inteligência Artificial, Modelos de Linguagem (LLMs), Agentes Autônomos, Coding Agents, MCP, Visão Computacional, 3D com IA, Infraestrutura/Hardware para IA e Negócios/Economia impulsionados por IA.
   - DESCARTE tweets fora do escopo de IA.
2. RADAR PERFIS DE REFERÊNCIA (TÓPICO 5 OBRIGATÓRIO SE HOUVER TWEET NO ARQUIVO):
   - O Tópico 5 ('Radar Perfis de Referência') NÃO deve ficar vazio se houver tweets de Matt Pocock (@mattpocockuk), Santiago Valdarrama (@svpino), Jason Liu (@jxnlco), Swyx ou Karpathy no JSON fornecido!
   - Inclua as publicações recentes coletadas desses autores (mesmo postadas nas últimas horas), sintetizando o que eles defenderam sobre engenharia de software, determinismo, coding agents e custos de IA.
3. PRIORIZAÇÃO POR RELEVÂNCIA TÉCNICA E ENGAJAMENTO:
   - Dê prioridade máxima a projetos open-source com repositórios reais (GitHub), lançamentos de modelos, papers (ArXiv) e ferramentas práticas.
   - Use o número de curtidas (likes), comentários (replies) e reposts para ranquear e priorizar as discussões que mais repercutiram no dia.
   - Se o tweet mencionar ou contiver link para GitHub, ArXiv, artigos externos (`external_links`) ou demonstração direta, SEMPRE inclua esse link formatado em markdown nos sub-bullets!

Sua missão é selecionar, filtrar e consolidar as publicações em um relatório Markdown estruturado OBRIGATORIAMENTE com a seguinte hierarquia visual:

## 📌 Destaques Principais do Dia
(Liste de 3 a 5 bullets diretos com as notícias mais impactantes e relevantes de todo o relatório)

---

## 1. 🚀 Ferramentas Open-Source, Visão & Ambientes 3D
## 2. 🤖 Agentes Autônomos, MCP & Infraestrutura de Execução
## 3. 🧪 Harness Engineering, Evals & RAG Avançado
(Dedique este tópico a evals de modelos/agentes, frameworks de harness, testes automatizados de agentes, recuperação semântica, RAG, embeddings e benchmarks práticos de confiabilidade).
## 4. 💻 Desenvolvimento, Claude Code & Eficiência de Custos
## 5. 🎯 Radar Perfis de Referência (Matt Pocock, Karpathy, Swyx, Jason Liu, Chip Huyen, Santiago)
(Destaque para posts, reflexões técnicas, evals e discussões desses criadores presentes no arquivo, contextualizando o valor de suas ideias para engenharia de software com IA).
## 6. 🏆 Capacitação Profissional, Cursos & Hackathons
## 7. 🌐 Economia, Modelos de Negócio & Mercado Global de IA

ATENÇÃO À FORMATAÇÃO DOS TÍTULOS:
- Use sempre `## ` (dois sustenidos) para os números das seções (ex: `## 1. 🚀 Ferramentas Open-Source...`, `## 5. 🎯 Radar Perfis de Referência...`). NUNCA use `### ` para seções principais.
- Cada uma das 7 seções deve ser separada da anterior por uma linha contendo apenas `---`.
"""

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openai_key = config.OPENAI_API_KEY

    relatorio_md = None

    if gemini_key:
        try:
            relatorio_md = chamar_gemini(gemini_key, tweets, prompt_sistema)
        except Exception as e:
            logger.warning(f"Erro ao chamar Gemini API: {e}")

    if not relatorio_md and openai_key:
        try:
            relatorio_md = chamar_openai(openai_key, tweets, prompt_sistema)
        except Exception as e:
            logger.warning(f"Erro ao chamar OpenAI API: {e}")

    if not relatorio_md:
        logger.error("Nenhuma chave de IA configurada ou todas falharam.")
        return None

    # Limpeza de backticks
    relatorio_md = relatorio_md.strip()
    if relatorio_md.startswith("```markdown"):
        relatorio_md = relatorio_md[len("```markdown"):].strip()
    elif relatorio_md.startswith("```"):
        relatorio_md = relatorio_md[3:].strip()
    if relatorio_md.endswith("```"):
        relatorio_md = relatorio_md[:-3].strip()

    # Anexa GitHub Trending se disponível
    if GITHUB_DATA_FILE.exists():
        try:
            with open(GITHUB_DATA_FILE, "r", encoding="utf-8") as f:
                trending_repos = json.load(f)
            if trending_repos:
                logger.info("Traduzindo e resumindo repositórios do GitHub em Português com gpt-6-luna...")
                prompt_gh = (
                    "Você é um engenheiro de IA sênior. Abaixo estão repositórios em alta no GitHub em formato JSON.\n"
                    "Traduza e gere um resumo conciso, didático e em PORTUGUÊS DO BRASIL para cada um, explicando:\n"
                    "1. O que é o projeto e qual problema ele resolve.\n"
                    "2. Por que ele é útil na prática para quem trabalha com IA, agentes ou automação.\n\n"
                    "Formate cada repositório exatamente assim:\n"
                    "* **[autor/repo](url)** — ⭐ **X stars** (Linguagem)\n"
                    "  - Resumo em português de 2 a 3 linhas explicando o projeto e seu valor prático.\n\n"
                    "Retorne APENAS a lista em markdown dos repositórios, sem cabeçalhos nem blocos ```markdown.\n\n"
                    f"DADOS DOS REPOSITÓRIOS:\n{json.dumps(trending_repos, ensure_ascii=False, indent=2)}"
                )

                payload_gh = {
                    "model": "gpt-6-luna",
                    "messages": [{"role": "user", "content": prompt_gh}]
                }
                req_gh = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload_gh).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {openai_key}"
                    }
                )
                try:
                    with urllib.request.urlopen(req_gh, timeout=60) as resp_gh:
                        res_gh = json.loads(resp_gh.read().decode("utf-8"))
                        gh_markdown = res_gh["choices"][0]["message"]["content"].strip()
                except Exception as e_gh:
                    logger.warning(f"Erro ao sintetizar GitHub em PT-BR: {e_gh}")
                    gh_markdown = None

                secao_gh = ["\n\n---\n\n## 🔥 GitHub Trending: Repositórios de IA em Alta no Dia\n"]
                if gh_markdown:
                    secao_gh.append(gh_markdown)
                else:
                    for r in trending_repos:
                        stars_str = f"{r['stars']:,}".replace(",", ".")
                        desc = r.get("description", "Sem descrição disponível").strip()
                        lang = r.get("language", "N/A")
                        secao_gh.append(f"* **[{r['full_name']}]({r['url']})** — ⭐ **{stars_str} stars** ({lang})")
                        secao_gh.append(f"  - {desc}")

                relatorio_md += "\n".join(secao_gh)
        except Exception as e:
            logger.warning(f"Aviso ao anexar GitHub Trending: {e}")

    with open(output_md, "w", encoding="utf-8") as f:
        f.write(relatorio_md)

    logger.info(f"Relatório gerado com sucesso em: {output_md}")
    return output_md

if __name__ == "__main__":
    gerar_resumo_ia()
