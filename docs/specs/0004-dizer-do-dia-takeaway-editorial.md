# Especificação Técnica 0004: Reformulação Editorial do Veredito da Redação (O Dizer do Dia)

**Status:** Aprovado para implementação  
**Área:** Síntese com IA & Renderização Bento Grid  
**Prerequisitos:** Specs 0001–0003 concluídas (PRs #1, #2 e #3 integradas na `main`)  

---

## 1. Problem Statement

Atualmente, o box final de fechamento do relatório diário — intitulado no HTML como *Veredito da Redação: Takeaway Prático de Engenharia do Dia* — apresenta duplicações de conteúdo e rigidez estrutural que prejudicam a fluidez editorial:

1. **Duplicação de Rótulos no Prompt:** A instrução em `get_prompt_takeaway()` solicita explicitamente à IA que *"sintetize de 2 a 3 conclusões e recomendações práticas... Formate EXATAMENTE assim: - **Padrão em Foco:** ... - **Recomendação Prática:** ..."*. Como consequência direta, o modelo `gpt-6-luna` gera dois ou três pares idênticos de marcadores com os mesmos títulos repetidos, criando uma experiência redundante de leitura.
2. **Formatação Fragmentada em Tópicos:** Em vez de oferecer um fechamento editorial conciso e fluido (a "Moral da História" ou a reflexão central do dia de IA), a seção força uma lista de marcadores (`<ul><li>`), distoando da estética tradicional de jornal impresso (*The Engineering Gazette*).

---

## 2. Solution

Reformular o prompt de síntese e o bloco correspondente no renderizador Bento Grid para transformar o antigo takeaway fragmentado em um **único texto corrido editorial fluido (O Dizer do Dia)**:

1. **Engenharia de Prompt (`prompts.py`):** Ajustar `get_prompt_takeaway()` para orientar a geração de um **único parágrafo conciso de 2 a 4 linhas**, eliminando a geração de múltiplos tópicos e proibindo expressamente o uso de marcadores (`-`, `*`) e prefixos rígidos (`Padrão em Foco:`, `Recomendação Prática:`).
2. **Padronização de Título (`ai_summarizer.py` & `renderer.py`):**
   - No Markdown: `## 💡 Veredito da Redação: O Dizer do Dia`.
   - No cabeçalho do box HTML: `VEREDITO DA REDAÇÃO: O DIZER DO DIA`.
3. **Renderização Visual Fluida (`renderer.py`):** Atualizar o renderizador para que, ao processar o box final, substitua a estrutura de lista (`<ul><li>`) por um parágrafo editorial justificado (`<p>`), tipografia serifada tradicional (`'Times New Roman', Georgia, serif`), entrelinha `1.65` e cor âmbar `#713f12`.
4. **Retrocompatibilidade de Âncoras:** Preservar a âncora `id="takeaway"` e `name="takeaway"` na barra de navegação rápida, garantindo que edições anteriores ou cliques de navegação continuem operando perfeitamente.

---

## 3. User Stories

1. **Como leitor do relatório diário**, quero ler um parágrafo editorial único e fluido no final do e-mail, para compreender a reflexão central do dia de IA sem marcadores repetitivos.
2. **Como leitor do relatório diário**, quero que a seção final não apresente repetições de rótulos como `Padrão em Foco:` e `Recomendação Prática:`, para que o texto soe como um veredito jornalístico autêntico e bem curado.
3. **Como leitor em clientes mobile e desktop**, quero que o "Dizer do Dia" seja formatado com tipografia serifada legível, fundo suave e alinhamento justificado, mantendo a identidade visual elegante do jornal impresso (*The Engineering Gazette*).
4. **Como leitor utilizando a navegação rápida no cabeçalho**, quero que o link de atalho para o fechamento continue funcionando normalmente.
5. **Como operador do sistema**, quero que a renderização de relatórios Markdown históricos (que porventura contenham o formato legado em bullets) continue funcionando sem quebras de layout.
6. **Como desenvolvedor**, quero que a montagem do prompt e a renderização do novo layout sejam verificadas por testes unitários rápidos e herméticos, garantindo zero regressões na suíte automatizada.

---

## 4. Implementation Decisions

### 4.1 Prompt do Dizer do Dia (`src/processors/prompts.py`)
* Manter a assinatura pública `get_prompt_takeaway(relatorio_completo_md: str) -> str`.
* Redefinir as instruções internas:
  * Papel: *Chief AI Architect e Editor Técnico*.
  * Objetivo: Produzir **um único parágrafo editorial contínuo (de 2 a 4 linhas)** que amarre o tema predominante do dia (convergência entre discussões do X, tendências do GitHub e avanços em papers).
  * Restrições estritas:
    - NUNCA usar marcadores de lista (`-`, `*`, `1.`).
    - NUNCA usar rótulos como `Padrão em Foco:` ou `Recomendação Prática:`.
    - NUNCA usar travessão longo (`—`).
    - Retornar apenas o texto corrido limpo, sem blocos de código markdown.

### 4.2 Anexação da Seção (`src/processors/ai_summarizer.py`)
* Manter a assinatura `_anexar_secao_takeaway(relatorio_md: str, openai_key: str) -> str`.
* Atualizar o cabeçalho gerado para:
  `## 💡 Veredito da Redação: O Dizer do Dia`

### 4.3 Renderização no Bento Grid (`src/delivery/renderer.py`)
* No seletor da seção editorial em `render_bento_email()`:
  * Reconhecer tanto o novo título quanto o legado: `if "Dizer do Dia" in title or "Takeaway" in title or "💡" in title:`.
  * Manter as âncoras HTML `<a name="takeaway" id="takeaway">` e adicionar `<a name="dizer-do-dia" id="dizer-do-dia">`.
  * Atualizar o título do cabeçalho do box para:
    `<h2 ...>VEREDITO DA REDAÇÃO: O DIZER DO DIA</h2>`
  * Processar as linhas de texto da seção:
    - Higienizar possíveis marcadores residuais se existirem (`- `, `* `).
    - Unificar as linhas em um texto corrido.
    - Renderizar em tag `<p>` estilizada:
      ```html
      <p style="margin: 0; font-size: 14.5px; line-height: 1.65; color: #713f12; font-family: 'Times New Roman', Georgia, serif; text-align: justify; font-weight: 400;">
          {texto_formatado}
      </p>
      ```
    - Eliminar o contêiner `<ul>` / `<li>`.

---

## 5. Testing Decisions & Acceptance Criteria

### 5.1 Critérios de Aceitação
- [ ] O prompt retornado por `get_prompt_takeaway()` exige 1 parágrafo corrido e veta explicitamente bullets e os prefixos `Padrão em Foco` / `Recomendação Prática`.
- [ ] A função `_anexar_secao_takeaway()` anexa o cabeçalho `## 💡 Veredito da Redação: O Dizer do Dia`.
- [ ] O renderizador `render_bento_email()` renderiza o box com o título `VEREDITO DA REDAÇÃO: O DIZER DO DIA` e tag `<p>` serifada justificada, sem tags `<ul>` ou `<li>`.
- [ ] A âncora `#takeaway` permanece presente e clicável.
- [ ] Relatórios em formato legado com bullets continuam sendo renderizados com elegância sem quebrar a pipeline.
- [ ] 100% da suíte de testes (95+ testes) passa sem erros ou chamadas externas.

### 5.2 Seams de Teste
* **Seam de Síntese (`tests/test_summarizer.py`):**
  - Teste unitário em `get_prompt_takeaway` verificando a presença das diretrizes de parágrafo único e proibição de rótulos repetidos.
  - Teste em `_anexar_secao_takeaway` (com mock da OpenAI) verificando o novo cabeçalho no Markdown.
* **Seam de Renderização (`tests/test_renderer.py`):**
  - Teste unitário em `render_bento_email` fornecendo Markdown com o novo formato e validando a ausência de `<ul>`/`<li>`, a presença do `<p>` formatado e a preservação das âncoras.
  - Teste de retrocompatibilidade com Markdown contendo bullets legados.

---

## 6. Out of Scope

* Alterar qualquer outra seção do relatório (Destaques, Ferramentas, Agentes, Radar VIP, Capacitação, Economia, GitHub Trending ou Papers).
* Modificar a lógica de coleta, scrapers Playwright ou transporte SMTP.
* Alterar o agendador de tarefas ou comandos operacionais CLI (`main.py`).

---

## 7. Further Notes

* Esta especificação resolve diretamente a queixa de redundância levantada no feedback visual, aplicando o princípio do menor delta suficiente (KISS/YAGNI) preconizado no `AGENTS.md`.
