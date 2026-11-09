# 13: Teste Canônico de Invariantes Anti-XSS e Validação Estrutural do Bento Grid

**What to build:**
Implementar a suíte canônica de testes de invariantes de segurança estrutural anti-XSS (`TestRendererCanaryInvariants`) em `tests/test_renderer.py`. O teste exercita todas as 8 superfícies de entrada externas de conteúdo dinâmico sintetizado por IA utilizando sentinelas canárias distintas (`CANARY_1` a `CANARY_8`) contendo payloads hostis de injeção de tags HTML (`<script>`, `<iframe>`, `<head>`, `<svg>`, `<video>`, `<form>`), esquemas de URL perigosos (`javascript:`, `data:`, `vbscript:`), manipuladores de eventos (`onerror`), atributos de desvio (`action`, `formaction`, `poster`, `xlink:href`), tentativa de uso de `srcset` e construções ativas em estilos inline (`expression`, `behavior`, `@import`).

A inspeção estrutural é realizada pela classe auxiliar `XSSCanaryParser` (subclasse de `html.parser.HTMLParser` nativo), atuando estritamente como ferramenta de asserção de teste automatizado e não como sanitizador de runtime. A classe opera uma máquina de estados estrita que audita o ciclo de vida de `html`, `head` e `body`, rejeitando tags anômalas, duplicadas, aninhadas ou fora de ordem sem corromper o estado interno. O parser valida a integridade do bloco `<style>` (impedindo o fechamento prematuro de `</head>` com estilo aberto e exigindo exatamente 1 bloco de estilo no documento), valida os atributos estáticos das 4 tags `<meta>` comparando diretamente contra `EXPECTED_STATIC_METAS`, rejeita atributos duplicados na lista antes de converter em dicionário, proíbe expressamente o atributo `srcset`, comprova a rejeição de URLs com userinfo (`https://evil.com@attacker.com`) via `_is_safe_url()`, assegura que todos os canários permanecem como texto inerte em `handle_data()` (sem vazar para atributos ou bloco de estilo) e valida a integridade de tags e classes essenciais do layout Bento Grid (*The Engineering Gazette*).

**Blocked by:**
None (pode iniciar imediatamente; unidade autônoma de testes)

**Status:**
ready-for-agent

**Files to modify:**
- `tests/test_renderer.py`

**Acceptance criteria:**
- [ ] Classe de asserção estrutural `XSSCanaryParser` implementada em `tests/test_renderer.py` herdando de `html.parser.HTMLParser`:
  - `PROHIBITED_TAGS`: conjunto contendo `{"script", "iframe", "object", "embed", "svg", "math", "base", "form", "button", "input", "link"}`.
  - `ALLOWED_TEMPLATE_TAGS`: conjunto estrito com as 21 tags legítimas do Bento Grid: `{"html", "head", "meta", "title", "style", "body", "table", "tr", "td", "div", "span", "h1", "h2", "p", "ul", "li", "strong", "em", "code", "a", "img"}`.
  - `EXPECTED_STATIC_METAS`: lista dos 4 dicionários exatos de meta esperados no template:
    1. `{"charset": "utf-8"}`
    2. `{"name": "viewport", "content": "width=device-width, initial-scale=1.0"}`
    3. `{"name": "color-scheme", "content": "light"}`
    4. `{"name": "supported-color-schemes", "content": "light"}`
- [ ] Máquina de estados estrita do ciclo de vida estrutural:
  - Controle explícito de flags de estado: `html_opened`, `html_closed`, `head_opened`, `head_closed`, `body_opened`, `body_closed`, `in_head`, `in_body`, `in_style_block`.
  - Rejeição de transições inválidas (tags `<html>`, `<head>` ou `<body>` duplicadas, aninhadas, reabertas ou fechadas prematuramente/fora de ordem), registrando a falha em `structure_anomalies` sem corromper as flags para um estado aparentemente válido.
  - Fechamento de `</head>` expressamente rejeitado enquanto `self.in_style_block` for `True`, registrando anomalia estrutural específica.
  - Rejeição de fechamento de `</style>` órfão ou duplicado.
  - Exigência de exatamente 1 bloco `<style>` estático no documento (`style_tags_count == 1`) e `in_style_block == False` ao final do parsing.
- [ ] Validação estática de tags `<meta>` e detecção prévia de duplicidade de atributos:
  - **Ressalva de Aceitação D1:** Antes de converter a lista de atributos da tag `<meta>` em dicionário, verificar se há nomes de atributos repetidos diretamente na lista `attrs: list[tuple[str, str | None]]` fornecida pelo `HTMLParser`. Registrar anomalia em `structure_anomalies` caso sejam encontrados atributos duplicados, prevenindo que a conversão silenciosa para `dict` produza um falso resultado válido.
  - Comparação dos atributos reais contra `EXPECTED_STATIC_METAS`: os atributos normalizados devem corresponder exatamente a uma das 4 entradas esperadas.
  - Rejeição de `<meta>` duplicada (já adicionada em `matched_metas`).
  - Rejeição de `<meta>` inesperada, modificada ou com atributos estranhos (como `http-equiv="refresh"`), registrando em `unexpected_tags_found`.
  - Exigência estrita de que `len(matched_metas) == 4` e `unexpected_tags_found == []`.
- [ ] Inspeção de Atributos e Proibições Estritas:
  - Rejeição de qualquer atributo iniciando com `on` (manipuladores inline de eventos) em qualquer elemento (`unsafe_attrs_found`).
  - Proibição expressa do atributo `srcset` (`unsafe_attrs_found`), confirmando que o template não o utiliza e evitando parsers frágeis.
  - Bloqueio de esquemas perigosos (`javascript:`, `data:`, `vbscript:`) nos atributos `href`, `src`, `action`, `formaction`, `poster` e `xlink:href` (`unsafe_attrs_found`).
  - Checagem heurística de construções ativas conhecidas (`expression`, `javascript:`, `behavior`, `@import`) em atributos `style` (`unsafe_attrs_found`).
- [ ] Rejeição Comprovada de URL com Userinfo:
  - O canário `CANARY_3_GH_REPO` com URL `https://evil.com@attacker.com` é submetido à renderização.
  - Asserção comprova que `https://evil.com@attacker.com` não aparece em nenhum atributo `href` de tag `<a>` no HTML gerado, sendo desarmado para texto inerte ou `<span>`, em conformidade estrita com o contrato de `_is_safe_url()`.
- [ ] Cobertura das 8 Superfícies de Entrada Canárias:
  1. Título de Seção Dinâmico: `## CANARY_1_TITLE <head><script>alert(1)</script></head>`
  2. Manchete Principal com Drop Cap: `- **CANARY_2_DROPCAP:** Manchete com payload <img src=x onerror=alert(2)>`
  3. Card GitHub Trending (Userinfo): `* **[CANARY_3_GH_REPO](https://evil.com@attacker.com)** ⭐ **1.200** (Python)`
  4. Card GitHub Trending (xlink / javascript): `  - CANARY_4_GH_DESC contendo <svg><a xlink:href="javascript:alert(4)">link</a></svg> e [Ataque](javascript:alert(4))`
  5. Card Papers ArXiv (data: URI): `* **[CANARY_5_PAPER_TITLE](data:text/html,<script>evil</script>)** 📄 **ArXiv: 2610.99999**`
  6. Card Papers ArXiv (iframe / action / formaction): `  - CANARY_6_PAPER_DESC contendo <iframe src='https://evil.com'></iframe> e <form action='javascript:alert(6)' formaction='javascript:alert(6)'>`
  7. Dica do Autor / Takeaway (CSS inline): `CANARY_7_TAKEAWAY <div style='behavior:url(x); background:url(javascript:alert(7))'>Dica</div>`
  8. Bullets Temáticos Padrão (vbscript / poster / srcset): `- **CANARY_8_BULLET:** Novidade com [Link](vbscript:msgbox(8)), <video poster='javascript:alert(8)'></video> e <img srcset='evil.jpg 1x'>`
- [ ] Asserção de Integridade dos Nós de Texto e Ausência de Vazamento:
  - Todos os 8 identificadores (`CANARY_1` a `CANARY_8`) são capturados como nós de texto em `handle_data()` (`parser.canary_data_chunks`).
  - Comprovação de que nenhum canário quebrou delimitadores para vazar como atributo HTML (`parser.canary_attrs_found == []`).
  - Comprovação de que nenhum canário vazou para o interior do bloco `<style>` (`parser.canary_in_style_found == []`).
- [ ] Validação Estrutural do Bento Grid (Sem Confusão com Inspeção Visual):
  - Presença confirmada das tags essenciais do template: `table`, `tr`, `td`, `div`, `span`, `h1`, `h2`, `p`, `ul`, `li`, `strong`, `em`, `code`, `a`, `img`.
  - Presença confirmada das classes essenciais do Bento Grid: `.main-container`, `.newspaper-section`, `.dropcap`, `.nav-pill`, `.footer-card`.
  - Presença confirmada das âncoras de navegação rápida: `#destaques`, `#github-trending`, `#papers`, `#takeaway`.
  - Distinção conceitual documentada: asserções automatizadas validam exclusivamente integridade estrutural e tipagem HTML; apelo visual e fidelidade estética continuam sob inspeção humana via `--preview`.
- [ ] Delimitação da Fronteira de CSS documentada no teste:
  - Documentado que `html.escape(..., quote=True)` atua em contextos de corpo e atributos HTML, e não como sanitizador de sintaxe interna CSS.
  - Template possui CSS estático de controle da aplicação; nenhum dado externo é interpolado em regras CSS; dispensado parser CSS próprio (KISS/YAGNI).
- [ ] Testes Herméticos e Desempenho:
  - Execução 100% determinística sem chamadas de rede reais, sob os guardrails de teste (`tests/guardrails.py`).
  - Execução da suíte completa de testes (`python -m unittest discover -s tests -t . -v`) com 100% de aprovação.

**TDD & Validation Commands:**
```bash
# Execução focada do novo teste de invariantes anti-XSS
python -m unittest tests.test_renderer.TestRendererCanaryInvariants -v

# Execução completa da suíte canônica sob guardrails de rede
python -m unittest discover -s tests -t . -v

# Verificação estrita de ausência de avisos de recursos
python -W error::ResourceWarning -m unittest discover -s tests -t .
```
