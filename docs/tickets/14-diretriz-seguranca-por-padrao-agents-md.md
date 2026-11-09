# 14: Governança "Safe by Default" para Agentes de IA em AGENTS.md

**What to build:**
Formalizar as diretrizes mandatórias de segurança de aplicação ("Safe by Default") no arquivo de governança central do repositório (`AGENTS.md`), na seção `## 3. Princípios de Engenharia e Padrões de Código`. A cláusula estabelece regras claras e acionáveis para futuros agentes de IA e desenvolvedores sobre sanitização contextual obrigatória de dados externos (`format_inline` e `html.escape(..., quote=True)`), validação estrita de URLs antes de criar hyperlinks (`_is_safe_url()`), configuração imperativa de contexto TLS seguro (`ssl.create_default_context()`) com validação de certificados e hostname em conexões SMTP, e a obrigatoriedade de cobertura de testes de regressão para qualquer novo campo alimentado por dados externos.

A redação deve manter estrita concisão, sem inflar o documento com detalhes efêmeros ou de baixo nível (como especificações de regexes, RFCs ou detalhes de IPv6), preservando o princípio do Menor Delta e a manutenibilidade do guia de agentes.

**Blocked by:**
None (pode iniciar imediatamente; tarefa autônoma de governança)

**Status:**
ready-for-agent

**Files to modify:**
- `AGENTS.md`

**Acceptance criteria:**
- [ ] Inclusão do item `Segurança por Padrão (Sanitização e TLS)` na seção `## 3. Princípios de Engenharia e Padrões de Código` de `AGENTS.md`.
- [ ] Redação alinhada estritamente com a especificação técnica aprovada:
  ```markdown
  * **Segurança por Padrão (Sanitização e TLS):** Dados externos (Markdown, feeds, redes sociais, IA) nunca devem ser interpolados diretamente no HTML sem tratamento contextual: utilize `format_inline()` para Markdown suportado e `html.escape(..., quote=True)` para atributos e textos puros. URLs devem ser validadas com `_is_safe_url()` antes da criação de hyperlinks (`<a>`); o escape isolado de caracteres não torna uma URL segura. Conexões de rede criptografadas via `smtplib.SMTP_SSL` devem obrigatoriamente fornecer `context=ssl.create_default_context()`, preservando verificação ativa de certificados e hostname. Novos campos alimentados por dados externos exigem testes de regressão correspondentes.
  ```
- [ ] Princípio da Concisão Preservado: nenhum detalhe efêmero ou de baixo nível de implementação (como expressões regulares de RFC 1123, validações manuais de IP ou regexes de parsing) é inserido no documento.
- [ ] Preservação Integral das Demais Diretrizes: as regras existentes de isolamento de testes, contratos CLI, higiene da raiz e padrões de banners permanecem intocadas.
- [ ] Validação de Formatação e Rastreabilidade:
  - Formatação Markdown limpa, sem caracteres corrompidos e sem espaços em branco residuais (`git diff --check`).
  - Execução canônica da suíte de testes do repositório permanece 100% verde (`python -m unittest discover -s tests -t . -v`).

**TDD & Validation Commands:**
```bash
# Verificação de formatação e ausência de trailing whitespace
git diff --check AGENTS.md

# Verificação da suíte canônica de testes (garantia de não-regressão)
python -m unittest discover -s tests -t . -v
```
