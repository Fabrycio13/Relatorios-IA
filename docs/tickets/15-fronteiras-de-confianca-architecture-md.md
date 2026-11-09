# 15: Fronteiras de Confiança e Modelo de Blindagem em ARCHITECTURE.md

**What to build:**
Adicionar formalmente a seção `## 6. Fronteiras de Confiança e Modelo de Blindagem` ao documento de arquitetura oficial do sistema (`docs/ARCHITECTURE.md`). O objetivo é documentar as zonas de confiança entre fontes externas, síntese de conteúdo por modelo de linguagem (LLM), renderização determinística de e-mails e canais de saída (SMTP e prévia local no navegador). A documentação esclarece auditorias de segurança sobre a distinção entre transporte seguro, higienização determinística de saída e o vetor semântico de manipulação de IA (*Prompt Injection*).

A nova seção mapeia a matriz de 4 zonas de confiança (Z1 a Z4), formaliza as 4 ressalvas conceituais aprovadas na retrospectiva técnica e registra os 3 princípios complementares derivados aprovados na especificação técnica (risco residual de phishing, segurança relativa do HTML e papel ativo do navegador na prévia local).

**Blocked by:**
None (pode iniciar imediatamente; tarefa autônoma de arquitetura)

**Status:**
ready-for-agent

**Files to modify:**
- `docs/ARCHITECTURE.md`

**Acceptance criteria:**
- [ ] Inclusão da seção `## 6. Fronteiras de Confiança e Modelo de Blindagem` ao final de `docs/ARCHITECTURE.md`.
- [ ] Tabela comparativa estruturada com as 4 Zonas de Confiança:
  - **Z1: Fontes Externas (Não Confiável):** APIs públicas, Feeds, X/Twitter, ArXiv, GitHub. Blindagem via timeout estrito, cabeçalhos de User-Agent, parsing defensivo.
  - **Z2: Síntese de Conteúdo (Não Determinística):** Modelo de linguagem configurado (LLM). Processamento semântico guiado por prompts; o Markdown gerado é formalmente tratado como **não confiável** para inserção direta em HTML.
  - **Z3: Renderização Determinística (Fronteira de Blindagem):** `src/delivery/renderer.py`. Aplicação de `format_inline()`, `html.escape(..., quote=True)`, validação de RFC/Userinfo em `_is_safe_url()` e teste canônico de invariantes estruturais.
  - **Z4: Canais de Entrega e Apresentação (Transporte & Exibição):** `src/delivery/base.py`, SMTP Gmail, Preview no Navegador. Conexão SMTP com TLS estrito (`ssl.create_default_context()`) para entrega; gravação local em arquivo para preview (onde o navegador pode realizar requisições de rede para carregar recursos remotos referenciados no HTML, como imagens externas). A segurança do conteúdo continua sob responsabilidade do renderizador.
- [ ] Documentação integral das 4 Ressalvas Conceituais da Retrospectiva:
  1. *Fronteiras Independentes e Conteúdo Não Confiável por Definição:* Fontes externas e o Markdown sintetizado pela LLM são tratados como dados não confiáveis até passarem pelo tratamento contextual do renderizador.
  2. *Blindagem Determinística no Renderer:* A proteção contra XSS e injeção de HTML depende exclusivamente da rotina determinística do renderizador (escape contextual, validação de URLs e cobertura exaustiva de campos).
  3. *Desvinculação entre Sanitização HTML e Prompt Injection:* A sanitização de saída HTML neutraliza quebra de tags, mas não previne nem mitiga manipulações semânticas da LLM (Prompt Injection), que operam no nível semântico da IA e exigem defesas próprias de prompt.
  4. *Separação Rigorosa entre Segurança de Transporte e de Conteúdo:* A criptografia TLS no SMTP protege a confidencialidade do canal contra interceptação em trânsito, mas não confere idoneidade, veracidade ou inocuidade aos links e textos transmitidos.
- [ ] Documentação integral dos 3 Princípios Complementares Derivados:
  5. *Risco Residual de Phishing em URLs Sintaticamente Válidas:* A validação estrita de URLs via `_is_safe_url()` garante conformidade estrutural com a RFC 1123, mas não audita a reputação do domínio; links válidos ainda podem conduzir a conteúdos hostis.
  6. *Segurança Relativa do HTML Gerado:* O documento HTML gerado não é classificado como "universalmente seguro", mas como defensivo dentro do conjunto de regras ativamente testadas pela suíte canônica de invariantes.
  7. *Preview Local no Navegador como Superfície Ativa:* O modo `--preview` não transmite e-mails via rede SMTP (grava em `reports/preview.html` e abre o navegador padrão), mas o navegador interpreta ativamente o HTML e pode disparar requisições de rede para carregar ativos remotos (como imagens de CDN e fontes). Portanto, a blindagem anti-XSS no preview é tão mandatória quanto no e-mail entregue, e sua segurança depende estritamente do renderizador determinístico.
- [ ] Higiene e Rastreabilidade Documental:
  - Formatação Markdown sem erros de lint ou trailing whitespace (`git diff --check`).
  - Nenhuma modificação nas seções existentes 1 a 5 de `docs/ARCHITECTURE.md`.
  - A suíte canônica de testes do repositório permanece 100% aprovada (`python -m unittest discover -s tests -t . -v`).

**TDD & Validation Commands:**
```bash
# Verificação de formatação e ausência de trailing whitespace
git diff --check docs/ARCHITECTURE.md

# Verificação da suíte canônica de testes (garantia de não-regressão)
python -m unittest discover -s tests -t . -v
```
