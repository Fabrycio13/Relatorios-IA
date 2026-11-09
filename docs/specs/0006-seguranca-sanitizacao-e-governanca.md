# Especificação Técnica 0006: Governança de Segurança, Invariantes Anti-XSS e Unificação SMTP

**Status:** Proposta para Aprovação Humana Final (Revisão 5.2)  
**Área:** Segurança de Aplicação (AppSec), Qualidade & Governança  
**Prerequisitos:** Consolidação da Retrospectiva de Segurança (Decisões D1 a D4 aprovadas)  
**Data:** 09/11/2026 (Revisão 5.2)  

---

## 1. Problem Statement

A auditoria de segurança e a retrospectiva operacional do projeto `Relatorios-IA` revelaram quatro oportunidades críticas de melhoria na robustez da aplicação e nas diretrizes de engenharia para agentes de IA:

1. **Fragilidade de Regressão em Interpolações HTML (Anti-XSS):**  
   O renderizador de e-mails (`src/delivery/renderer.py`) compõe o layout *The Engineering Gazette* interpolando strings formatadas com conteúdo curado por modelos de linguagem (LLM) a partir de fontes externas (X/Twitter, GitHub, ArXiv). Embora a rodada de segurança tenha sanitizado os campos existentes, a ausência de um teste de invariante estrutural permite que futuras adições de campos ou blocos editoriais introduzam injeção de HTML ou XSS caso o desenvolvedor esqueça de invocar `format_inline()` ou `html.escape()`.
2. **Ausência de Diretrizes de Segurança no `AGENTS.md`:**  
   O `AGENTS.md` possui foco estrito em isolamento de testes e automação CLI, mas omitia diretrizes mandatórias sobre a obrigatoriedade de sanitização contextual de dados externos e a configuração explícita de `SSLContext` com validação de certificados e hostname em conexões de rede.
3. **Lacuna Conceitual sobre Fronteiras de Confiança em `docs/ARCHITECTURE.md`:**  
   A documentação de arquitetura mapeava o fluxo sequencial de componentes, mas não formalizava as fronteiras de confiança entre fontes externas, síntese por IA, renderização determinística e canais de saída. Essa indefinição gerou dúvidas em auditorias sobre a relação entre *Prompt Injection*, renderização HTML, visualização local e canais de entrega.
4. **Duplicação da Lógica de Conexão SMTP Segura e Inversão de Camadas:**  
   Tanto o canal de envio oficial (`EmailDeliveryChannel.deliver` em `src/delivery/base.py`) quanto o diagnóstico de conectividade (`check_email` em `src/core/healthcheck.py`) inicializavam independentemente a conexão `smtplib.SMTP_SSL("smtp.gmail.com", 465)` com criação de contexto TLS e sanitização de credenciais, criando risco de divergência futura na política de segurança de transporte. Ademais, centralizar essa função dentro de `delivery.base` forçaria `src/core/healthcheck.py` a importar da camada de entrega, introduzindo uma inversão indesejada de dependência em camadas.

---

## 2. Solution Architecture & Escopo

### 2.1 Escopo Obrigatório (In-Scope)
* **D1 — Teste Canônico de Invariantes Anti-XSS (`tests/test_renderer.py`):**  
  Implementação de teste determinístico utilizando sentinelas canárias distintas injetadas em todas as 8 superfícies de entrada externas do Markdown, inspecionando a árvore resultante com `html.parser.HTMLParser` nativo como ferramenta de asserção estrutural nos testes (e não como sanitizador em tempo de execução nem parser de renderização de navegador). O teste emprega uma máquina de estados com controle estrito do ciclo de vida de `html`, `head` e `body` (rejeitando tags duplicadas, aninhadas ou fora de ordem tanto na abertura quanto no fechamento sem corromper o estado, e impedindo o fechamento de `</head>` com `<style>` ainda aberto), comparação efetiva das 4 tags `<meta>` estáticas contra `EXPECTED_STATIC_METAS` (rejeitando duplicatas ou substituições), exigência de exatamente 1 bloco `<style>` estático no documento, inspeção dedicada de `<style>` para verificação de canários (sem criar parser CSS próprio e reconhecendo a natureza heurística de substrings em `style`), proibição do atributo `srcset` (desnecessário ao template), rejeição de atributos inseguros (`on*`, `action`, `formaction`, `poster`, `xlink:href`), comprovação de ausência de canários em atributos HTML, além de demonstrar que URLs com userinfo (ex: `https://evil.com@attacker.com`) são rejeitadas e desarmadas para texto inerte conforme o contrato de `_is_safe_url()`. O teste valida a integridade estrutural e classes essenciais do Bento Grid (`.main-container`, `.newspaper-section`, `.dropcap`, `.nav-pill`, `.footer-card`), separando formalmente asserções estruturais automatizadas da inspeção visual humana.
* **D2 — Diretriz "Safe by Default" no `AGENTS.md` (§3):**  
  Inclusão de item conciso em `AGENTS.md` formalizando a exigência de sanitização contextual (`format_inline` / `html.escape`), validação própria de URLs antes de criar hyperlinks, TLS obrigatório com `ssl.create_default_context()` no SMTP e testes de regressão para novos campos, sem detalhes de implementação de baixo nível.
* **D3 — Fronteiras de Confiança em `docs/ARCHITECTURE.md` (§6):**  
  Inclusão de seção compacta documentando as zonas de confiança entre fontes externas, LLM configurada, Markdown gerado, renderer determinístico e canais de saída, formalizando as 4 ressalvas conceituais aprovadas na retrospectiva e os 3 princípios complementares derivados (risco de phishing em URLs válidas, relatividade da segurança do HTML gerado e prévia local no navegador distinguindo ausência de entrega SMTP da possibilidade de requisições externas para recursos remotos).
* **D4 — Unificação da Conexão SMTP Segura (`src/core/smtp.py`):**  
  Centralização da conexão SMTP TLS autenticada em função compartilhada (`conectar_smtp_ssl`) localizada na camada `src/core/`, preservando a hierarquia unidirecional de dependências (`delivery -> core` e `healthcheck -> core.smtp`), assinaturas públicas existentes, isolamento de testes e simplificação do ciclo de vida via context manager nativo de `smtplib` (cuja implementação na biblioteca padrão Python 3.12 e 3.13 garante envio de `QUIT` e execução de `close()` em bloco `finally`), com testes modelando os 4 cenários reais de encerramento do CPython e preservando rigorosamente o tratamento de exceções e logs de cada consumidor.

### 2.2 Não-Objetivos (Explicitamente Fora de Escopo / Rejeitados)
* **SAST com Bandit:** Adiado até eventual adoção de linter unificado (Ruff). Constatou-se na documentação oficial que o Bandit não detecta a ausência de contexto TLS no `smtplib.SMTP_SSL` nativamente e geraria ruído de falsos positivos em testes (`B101`) e banners (`B311`).
* **Fuzzing com Hypothesis:** Rejeitado para evitar dependências pesadas, testes não determinísticos e lentidão na suíte canônica.
* **Auditoria com Deptry / Testes AST Caseiros:** Adiado com base no princípio YAGNI. A base possui apenas duas dependências diretas de produção (`playwright` e `python-dotenv`), ambas em uso ativo comprovado.
* **Desacoplamento de URLs para `core/security.py`:** Rejeitado pelo princípio do Menor Delta. As funções `_is_safe_url` e `_is_valid_hostname` possuem consumidor único conhecido (`renderer.py`).
* **Modelagem STRIDE / Documento Extenso de AppSec:** Rejeitado por burocracia desproporcional.

### 2.3 Melhorias Futuras (Gatilhos de Reavaliação)
* Avaliar regras `S` do flake8-bandit caso o projeto adote o linter `ruff`.
* Avaliar `deptry` ou ferramentas de dependência caso o projeto atinja múltiplos grupos de dependências ou migre para empacotamento com `pyproject.toml` (`uv`/`poetry`).
* Avaliar extração de módulo utilitário de URLs caso surjam múltiplos consumidores fora do `renderer.py`.

---

## 3. Análise do Grafo de Dependências e Localização do SMTP

### 3.1 Grafo Atual de Pacotes
```
src/
├── core/
│   ├── config.py
│   ├── logger.py
│   ├── models.py
│   ├── retry.py
│   ├── notifier.py
│   └── healthcheck.py  --> consome core.config, core.logger
└── delivery/
    ├── base.py         --> consome core.config, core.logger
    ├── dispatcher.py   --> consome delivery.base, delivery.renderer
    ├── renderer.py     --> consome core.config, delivery.banner_selector
    └── sender.py       --> consome delivery.dispatcher
```

### 3.2 Avaliação Arquitetural da Localização da Conexão SMTP
Duas alternativas foram avaliadas para abrigar a função unificada `conectar_smtp_ssl`:

1. **Localização em `src/delivery/base.py` (Rejeitada):**  
   * Obriga `src/core/healthcheck.py` a importar `src.delivery.base`.  
   * *Problema:* Introduz acoplamento bidirecional entre pacotes (`delivery` já depende de `core`). Em termos de arquitetura em camadas, a camada central (`core`) passaria a depender de uma camada externa de entrega (`delivery`), que por sua vez importa submódulos pesados como `webbrowser`, `email.mime`, etc.

2. **Localização em `src/core/smtp.py` (Aprovada):**  
   * Cria um módulo coeso e mínimo (`src/core/smtp.py`, ~30 linhas) contendo estritamente a política de transporte SMTP seguro.
   * *Grafo de Dependências Resultante:*
     - `src/core/smtp.py` depende exclusivamente de bibliotecas padrão (`contextlib`, `smtplib`, `ssl`, `typing`).
     - `src/core/healthcheck.py` (core) consome `src.core.smtp` (intra-camada core).
     - `src/delivery/base.py` (delivery) consome `src.core.smtp` (camada superior dependendo da camada base core).
   * *Benefícios:* Dependência estritamente unidirecional e descendente; zero dependências circulares; zero inversões arquiteturais; testes de SMTP testáveis isoladamente.

---

## 4. Detalhamento Técnico das Implementações

### 4.1 Unificação da Conexão SMTP Segura (`src/core/smtp.py`)

#### Contrato da Função Compartilhada (Context Manager Nativo)
```python
import smtplib
import ssl
from contextlib import contextmanager
from typing import Generator

@contextmanager
def conectar_smtp_ssl(
    remetente: str,
    senha_app: str,
    host: str = "smtp.gmail.com",
    port: int = 465,
    timeout: int = 20,
) -> Generator[smtplib.SMTP_SSL, None, None]:
    """Cria conexão SMTP SSL com validação de certificados, sanitiza credenciais e realiza autenticação.
    
    Ciclo de vida e encerramento:
    1. Fase de Conexão: Se smtplib.SMTP_SSL(...) falhar durante a resolução de DNS, conexão TCP ou handshake TLS,
       a exceção propaga diretamente ao chamador antes da ativação do bloco de contexto.
    2. Context Manager Nativo: O bloco 'with server:' gerencia o ciclo de vida. Conforme a implementação
       oficial da biblioteca padrão Python (verificada em Python 3.12 e 3.13), o método smtplib.SMTP.__exit__
       envia o comando protocolar QUIT (RFC 5321) e executa incondicionalmente self.close() dentro de uma
       cláusula 'finally', garantindo o fechamento determinístico do socket tanto em saídas bem-sucedidas quanto
       em caso de erro no login ou falha/timeout durante o comando QUIT.
    """
    if not remetente or not senha_app:
        raise ValueError("Remetente e senha de aplicativo são obrigatórios para conexão SMTP.")

    context = ssl.create_default_context()
    senha_limpa = senha_app.replace(" ", "")

    server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    with server:
        server.login(remetente, senha_limpa)
        yield server
```

#### Evidência Técnica e Mecânica Real do CPython (`smtplib.py`)
A inspeção do código-fonte do CPython nas versões Python 3.12.9 (ambiente local) e Python 3.13 (CI em `.github/workflows/ci.yml`) confirma a seguinte mecânica interna:

```python
def docmd(self, cmd, args=""):
    self.putcmd(cmd, args)
    return self.getreply()

def getreply(self):
    ...
    while 1:
        try:
            line = self.file.readline(_MAXLINE + 1)
        except OSError as e:
            self.close()
            raise SMTPServerDisconnected("Connection unexpectedly closed: " + str(e))
        if not line:
            self.close()
            raise SMTPServerDisconnected("Connection unexpectedly closed")
        ...
        return errcode, errmsg

def __exit__(self, *args):
    try:
        code, message = self.docmd("QUIT")
        if code != 221:
            raise SMTPResponseException(code, message)
    except SMTPServerDisconnected:
        pass
    finally:
        self.close()
```

*Constatações da Arquitetura do Runtime CPython:*
1. **Conversão de `OSError` para `SMTPServerDisconnected`:** Caso ocorra timeout de rede, encerramento abrupto pelo servidor ou quebra de pipe durante a leitura da resposta de `QUIT`, o método `getreply()` fecha o socket e levanta `SMTPServerDisconnected`.
2. **Supressão Controlada de Desconexão em `QUIT`:** O método `__exit__` captura expressamente `SMTPServerDisconnected` com `pass`, pois o socket já foi desconectado e fechado.
3. **Garantia Incondicional de `close()`:** A cláusula `finally: self.close()` é executada em 100% dos fluxos de saída do bloco `try`.
4. **Delimitação de Versões:** Essa constatação restringe-se formalmente à matriz suportada pelo projeto (**Python 3.12 e Python 3.13**).

#### Critérios de Testes Unitários de Ciclo de Vida SMTP (`tests/test_smtp.py`)
Para reproduzir com fidelidade o comportamento real do CPython (evitando mocks artificiais que não refletem a dinâmica de rede), os testes unitários cobrirão formalmente quatro cenários:
1. **Encerramento Normal:** Conclusão sem exceções do bloco `with`; verifica que `docmd("QUIT")` retornou 221 e `server.close()` foi executado.
2. **Falha de Autenticação (`login()`):** `server.login()` levanta `smtplib.SMTPAuthenticationError`; o context manager aciona `__exit__`, envia `QUIT`, executa `server.close()` e preserva a exceção original de autenticação para o chamador.
3. **Desconexão ou Timeout durante QUIT:** Simula a interrupção de rede na leitura de `QUIT`, onde o socket levanta `SMTPServerDisconnected`; o context manager captura a exceção em `__exit__`, executa `server.close()` e não vaza exceção espúria.
4. **Resposta SMTP Diferente de 221:** Simula resposta de erro do servidor ao `QUIT` (ex: 500); verifica que `server.close()` é executado via `finally` e `smtplib.SMTPResponseException` é propagada ao chamador.

#### Consumidores e Tratamento de Exceções
* **Consumidor 1 — `EmailDeliveryChannel.deliver` (`src/delivery/base.py`):**
  - Mantém a assinatura pública `deliver(self, subject: str, html_body: str, recipient: str, plain_text: str = "") -> bool`.
  - Executa `with conectar_smtp_ssl(remetente, senha_app, host=self.smtp_host, port=self.smtp_port, timeout=self.timeout) as server:`.
  - Dispara `server.sendmail(...)`, registra log de sucesso e retorna `True`.
  - Em caso de exceção (`Exception as e`), preserva rigorosamente o log e retorno originais:
    `logger.error(f"❌ Erro ao enviar e-mail via SMTP: {e}")` e retorna `False`.
* **Consumidor 2 — `check_email` (`src/core/healthcheck.py`):**
  - Mantém a assinatura pública `check_email() -> tuple[bool, str]`.
  - Valida credenciais no `.env`. Se incompletas, retorna imediatamente `(False, "Credenciais de e-mail incompletas no .env")`.
  - Executa `with conectar_smtp_ssl(remetente, senha_app, timeout=6): pass`.
  - Em caso de sucesso, retorna `(True, f"Login SMTP OK ({remetente} -> {destinatario})")`.
  - Em caso de exceção (`Exception as e`), preserva o retorno original `(False, f"Falha no login SMTP do Gmail: {e}")`, sem emitir log de erro fatal.

---

### 4.2 Teste Canônico de Invariantes Anti-XSS (`tests/test_renderer.py`)

#### Papel do `HTMLParser` como Ferramenta de Asserção Estrutural
O `html.parser.HTMLParser` da biblioteca padrão é adotado **exclusivamente como ferramenta de inspeção e asserção estrutural nos testes determinísticos**, e **não** como sanitizador em tempo de execução nem como emulador completo do algoritmo de parsing de navegadores reais (WHATWG HTML5). A blindagem em produção é de responsabilidade estrita das rotinas do renderizador (`format_inline()`, `html.escape(..., quote=True)` e `_is_safe_url()`).

#### Contrato Completo da Máquina de Estados e Inspeção Estrutural
A classe de teste `XSSCanaryParser` implementa transições estritas de abertura e fechamento para `html`, `head` e `body`. Uma transição inválida registra uma anomalia em `structure_anomalies` e **não** atualiza o estado interno para uma posição aparentemente válida. O fechamento de `</head>` é expressamente impedido se o bloco `<style>` ainda estiver aberto:

```python
class XSSCanaryParser(html.parser.HTMLParser):
    """Parser de teste para inspeção estrutural do HTML gerado pelo renderizador."""
    
    # Tags intrinsecamente perigosas que NUNCA devem aparecer no documento
    PROHIBITED_TAGS = {
        "script", "iframe", "object", "embed", "svg", "math",
        "base", "form", "button", "input", "link"
    }

    # Tags legítimas esperadas no layout Bento Grid (The Engineering Gazette)
    ALLOWED_TEMPLATE_TAGS = {
        "html", "head", "meta", "title", "style", "body",
        "table", "tr", "td", "div", "span", "h1", "h2", "p",
        "ul", "li", "strong", "em", "code", "a", "img"
    }

    # As 4 tags <meta> estáticas exatamente esperadas no cabeçalho do template
    EXPECTED_STATIC_METAS = [
        {"charset": "utf-8"},
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"},
        {"name": "color-scheme", "content": "light"},
        {"name": "supported-color-schemes", "content": "light"},
    ]

    def __init__(self):
        super().__init__()
        # Máquina de estados explícita do ciclo de vida estrutural
        self.html_opened: bool = False
        self.html_closed: bool = False
        self.head_opened: bool = False
        self.head_closed: bool = False
        self.body_opened: bool = False
        self.body_closed: bool = False
        self.in_head: bool = False
        self.in_body: bool = False
        self.in_style_block: bool = False

        # Validação estática efetiva de elementos do cabeçalho
        self.matched_metas: list[dict[str, str]] = []
        self.style_tags_count: int = 0

        # Registros de anomalias e achados
        self.structure_anomalies: list[str] = []
        self.active_tags_found: list[str] = []
        self.unexpected_tags_found: list[str] = []
        self.unsafe_attrs_found: list[tuple[str, str, str]] = []
        self.canary_attrs_found: list[tuple[str, str, str]] = []
        self.canary_in_style_found: list[str] = []
        self.canary_data_chunks: list[str] = []
        self.legitimate_tags_found: set[str] = set()
        self.essential_classes_found: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()

        # 1. Transições de abertura da máquina de estados
        if tag_lower == "html":
            if self.html_opened or self.head_opened or self.body_opened or self.html_closed:
                self.structure_anomalies.append("Tag <html> duplicada, aninhada ou reaberta")
            else:
                self.html_opened = True
        elif tag_lower == "head":
            if not self.html_opened or self.head_opened or self.head_closed or self.body_opened or self.html_closed:
                self.structure_anomalies.append("Tag <head> duplicada, aninhada ou iniciada fora de ordem")
            else:
                self.head_opened = True
                self.in_head = True
        elif tag_lower == "body":
            if not self.html_opened or not self.head_closed or self.body_opened or self.body_closed or self.html_closed:
                self.structure_anomalies.append("Tag <body> duplicada, iniciada antes do fechamento de <head> ou fora de ordem")
            else:
                self.body_opened = True
                self.in_body = True
        elif tag_lower == "meta":
            if not self.in_head or self.head_closed:
                self.active_tags_found.append("meta_outside_head")
            else:
                # Normalização e comparação efetiva contra EXPECTED_STATIC_METAS
                current_meta = {k.lower(): (v or "").strip().lower() for k, v in attrs}
                if current_meta in self.EXPECTED_STATIC_METAS:
                    if current_meta in self.matched_metas:
                        self.structure_anomalies.append(f"Tag <meta> duplicada: {current_meta}")
                    else:
                        self.matched_metas.append(current_meta)
                else:
                    self.unexpected_tags_found.append(f"meta_inesperada_ou_modificada: {current_meta}")
        elif tag_lower == "style":
            if not self.in_head or self.head_closed:
                self.active_tags_found.append("style_outside_head")
            else:
                self.style_tags_count += 1
                if self.style_tags_count > 1:
                    self.structure_anomalies.append(f"Tag <style> duplicada ou excedente (count={self.style_tags_count})")
                self.in_style_block = True

        # 2. Categorização de tags
        if tag_lower in self.PROHIBITED_TAGS:
            self.active_tags_found.append(tag_lower)
        elif tag_lower not in self.ALLOWED_TEMPLATE_TAGS:
            self.unexpected_tags_found.append(tag_lower)
        else:
            self.legitimate_tags_found.add(tag_lower)

        # 3. Inspeção de atributos
        for attr_name, attr_val in attrs:
            attr_name_lower = attr_name.lower()
            val_clean = (attr_val or "").lower().strip()

            # Comprova ausência total de canários em atributos HTML
            if attr_val and "CANARY" in attr_val:
                self.canary_attrs_found.append((tag_lower, attr_name, attr_val))

            # Classes essenciais do Bento Grid
            if attr_name_lower == "class" and attr_val:
                for cls in attr_val.split():
                    self.essential_classes_found.add(cls.strip())

            # Manipuladores inline de eventos (on*)
            if attr_name_lower.startswith("on"):
                self.unsafe_attrs_found.append((tag_lower, attr_name, val_clean))

            # Proibição explícita do atributo srcset (desnecessário ao template)
            if attr_name_lower == "srcset":
                self.unsafe_attrs_found.append((tag_lower, attr_name, val_clean))

            # Bloqueio de esquemas perigosos em URLs
            if attr_name_lower in ("href", "src", "action", "formaction", "poster", "xlink:href"):
                if val_clean.startswith(("javascript:", "data:", "vbscript:")):
                    self.unsafe_attrs_found.append((tag_lower, attr_name, val_clean))

            # Checagem heurística contra construções ativas conhecidas em style inline
            if attr_name_lower == "style":
                if any(kw in val_clean for kw in ("expression", "javascript:", "behavior", "@import")):
                    self.unsafe_attrs_found.append((tag_lower, attr_name, val_clean))

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()

        # Transições de fechamento com validação estrita
        if tag_lower == "head":
            if not self.head_opened or self.head_closed or not self.in_head or self.body_opened:
                self.structure_anomalies.append("Fechamento de </head> duplicado, órfão ou fora de ordem")
            elif self.in_style_block:
                self.structure_anomalies.append("Tentativa de fechar </head> com bloco <style> ainda aberto")
            else:
                self.head_closed = True
                self.in_head = False
        elif tag_lower == "body":
            if not self.body_opened or self.body_closed or not self.in_body or self.html_closed:
                self.structure_anomalies.append("Fechamento de </body> duplicado, órfão ou fora de ordem")
            else:
                self.body_closed = True
                self.in_body = False
        elif tag_lower == "html":
            if not self.html_opened or self.html_closed or not self.body_closed:
                self.structure_anomalies.append("Fechamento de </html> prematuro, duplicado ou fora de ordem")
            else:
                self.html_closed = True
        elif tag_lower == "style":
            if not self.in_style_block:
                self.structure_anomalies.append("Fechamento de </style> órfão ou duplicado")
            else:
                self.in_style_block = False

    def handle_data(self, data: str):
        # Inspeção dedicada do bloco <style> do cabeçalho
        if self.in_style_block:
            if "CANARY" in data:
                self.canary_in_style_found.append(data)
            return

        # Nós textuais de conteúdo editorial
        if "CANARY" in data:
            self.canary_data_chunks.append(data)
```

#### Fronteira de Segurança CSS e Delimitação da Inspeção (Transparência Técnica)
* **Arquitetura Estática do CSS:** O CSS do layout Bento Grid é 100% estático e controlado pela aplicação (residente no bloco `<style>` estático do cabeçalho e nos atributos `style` pré-definidos das seções e tabelas).
* **Proibição de Interpolação Direta:** Dados externos (Markdown, feeds, IA) **nunca** devem ser interpolados diretamente dentro de blocos `<style>` nem em valores de propriedades CSS (`style="..."`).
* **Delimitação do Escopo de `html.escape()`:** O uso de `html.escape(..., quote=True)` neutraliza a quebra de tags HTML e delimitadores de atributos nos contextos apropriados (corpo HTML e valores de atributos entre aspas), mas **não** sanitiza nem valida regras de sintaxe CSS interna.
* **Governança para Necessidades Futuras:** Caso surja necessidade futura de propriedades CSS dinâmicas baseadas em dados externos, ela deverá adotar validação restritiva por allowlist (ex: mapeamento fechado para tokens/cores previamente homologados), e nunca interpolação crua de CSS.
* **Sem Parser CSS Caseiro (KISS/YAGNI):** A especificação rejeita a criação de um parser ou sanitizador CSS próprio. A inspeção de atributos `style` e do bloco `<style>` no `XSSCanaryParser` é expressamente declarada como uma **asserção heurística de integridade do template** (verificando a ausência de canários e substrings ativas conhecidas como `expression`, `javascript:`, `behavior`, `@import`), e não como uma garantia universal contra ataques avançados em CSS.

#### As 8 Superfícies de Entrada Externas e Payloads Canários
Cada superfície externa é desafiada com canários específicos, incluindo teste de injeção de `<head>` anômalo e atributos perigosos:
1. **Título de Seção Dinâmico (`<script>` e `<head>` duplicado):**  
   `## CANARY_1_TITLE <head><script>alert(1)</script></head>`
2. **Manchete Principal com Drop Cap (Manipulador `onerror`):**  
   `- **CANARY_2_DROPCAP:** Manchete com payload <img src=x onerror=alert(2)>`
3. **Card GitHub Trending — URL com Userinfo (`@` no netloc):**  
   `* **[CANARY_3_GH_REPO](https://evil.com@attacker.com)** ⭐ **1.200** (Python)`
4. **Card GitHub Trending — Atributos `xlink:href` e Esquema `javascript:`:**  
   `  - CANARY_4_GH_DESC contendo <svg><a xlink:href="javascript:alert(4)">link</a></svg> e [Ataque](javascript:alert(4))`
5. **Card Papers ArXiv — Esquema `data:` em Hyperlink:**  
   `* **[CANARY_5_PAPER_TITLE](data:text/html,<script>evil</script>)** 📄 **ArXiv: 2610.99999**`
6. **Card Papers ArXiv — `<iframe>` e Atributos `action` / `formaction`:**  
   `  - CANARY_6_PAPER_DESC contendo <iframe src='https://evil.com'></iframe> e <form action='javascript:alert(6)' formaction='javascript:alert(6)'>`
7. **Dica do Autor / Takeaway — Construções Heurísticas de CSS em `style`:**  
   `CANARY_7_TAKEAWAY <div style='behavior:url(x); background:url(javascript:alert(7))'>Dica</div>`
8. **Bullets Temáticos Padrão — Esquema `vbscript:`, Atributo `poster` e Tentativa de `srcset`:**  
   `- **CANARY_8_BULLET:** Novidade com [Link](vbscript:msgbox(8)), <video poster='javascript:alert(8)'></video> e <img srcset='evil.jpg 1x'>`

#### Asserções do Teste Canônico
1. `self.assertEqual(parser.structure_anomalies, [])`: Nenhuma anomalia de abertura ou fechamento de `html`, `head`, `body` ou `style` é gerada.
2. `self.assertEqual(len(parser.matched_metas), 4)` e `self.assertEqual(parser.unexpected_tags_found, [])`: As 4 tags `<meta>` estáticas foram comparadas e validadas com sucesso contra `EXPECTED_STATIC_METAS`, sem duplicatas ou substituições.
3. `self.assertEqual(parser.style_tags_count, 1)` e `self.assertFalse(parser.in_style_block)`: Exatamente um bloco `<style>` estático foi encontrado e devidamente fechado antes de `</head>`.
4. `self.assertEqual(parser.active_tags_found, [])`: Nenhuma tag proibida é criada e nenhuma tag `<meta>` ou `<style>` é injetada fora do `<head>` estático.
5. `self.assertEqual(parser.unsafe_attrs_found, [])`: Nenhum atributo malicioso (`on*`, `action`, `formaction`, `poster`, `srcset` proibido, `xlink:href`, ou `style` com construções proibidas) é emitido.
6. **Rejeição Comprovada de URL com Userinfo:** O teste verifica especificamente que `https://evil.com@attacker.com` não aparece como atributo `href` de tag `<a>`. O canário `CANARY_3_GH_REPO` é desarmado e renderizado apenas como texto seguro ou `<span>` inofensivo, em conformidade com o contrato de `_is_safe_url()`.
7. **Comprovação de Nós Textuais e Ausência de Canários em Atributos e `<style>`:**  
   - Todos os 8 identificadores canários (`CANARY_1` a `CANARY_8`) são capturados em `parser.canary_data_chunks` em nós de texto (`handle_data`).
   - A inspeção comprova `self.assertEqual(parser.canary_attrs_found, [])`, garantindo que nenhum canário quebrou a estrutura para vazar como atributo HTML.
   - A inspeção comprova `self.assertEqual(parser.canary_in_style_found, [])`, assegurando que o bloco `<style>` estático não sofreu injeção de conteúdo externo.
8. **Integridade Estrutural do Bento Grid (Sem Confusão com Inspeção Visual):**
   - O teste automatizado valida a presença de tags e classes essenciais do layout:
     * Tags: `table`, `tr`, `td`, `div`, `span`, `h1`, `h2`, `p`, `ul`, `li`, `strong`, `em`, `code`, `a`, `img`.
     * Classes essenciais: `.main-container`, `.newspaper-section`, `.dropcap`, `.nav-pill`, `.footer-card`.
     * Âncoras de navegação rápida: `#destaques`, `#github-trending`, `#papers`, `#takeaway`.
   - *Separação Conceitual:* A asserção automatizada garante exclusivamente a integridade estrutural e a ausência de corrupção de tags/classes no HTML. A fidelidade tipográfica e o apelo visual (proporções, cores de contraste, renderização de fontes) são validados via inspeção visual humana no navegador através do comando operacional seguro `python main.py --preview`.

---

### 4.3 Governança "Safe by Default" no `AGENTS.md`

Inclusão de item conciso na seção `## 3. Princípios de Engenharia e Padrões de Código`:

```markdown
* **Segurança por Padrão (Sanitização e TLS):** Dados externos (Markdown, feeds, redes sociais, IA) nunca devem ser interpolados diretamente no HTML sem tratamento contextual: utilize `format_inline()` para Markdown suportado e `html.escape(..., quote=True)` para atributos e textos puros. URLs devem ser validadas com `_is_safe_url()` antes da criação de hyperlinks (`<a>`); o escape isolado de caracteres não torna uma URL segura. Conexões de rede criptografadas via `smtplib.SMTP_SSL` devem obrigatoriamente fornecer `context=ssl.create_default_context()`, preservando verificação ativa de certificados e hostname. Novos campos alimentados por dados externos exigem testes de regressão correspondentes.
```

---

### 4.4 Fronteiras de Confiança em `docs/ARCHITECTURE.md`

Inclusão da seção `## 6. Fronteiras de Confiança e Modelo de Blindagem`:

#### Mapeamento de Zonas de Confiança
| Zona | Componentes | Nível de Confiança | Mecanismos de Blindagem |
| :--- | :--- | :--- | :--- |
| **Z1: Fontes Externas** | APIs públicas, Feeds, X/Twitter, ArXiv, GitHub | **Não Confiável** | Timeout estrito, cabeçalhos de User-Agent, parsing resiliente. |
| **Z2: Síntese de Conteúdo** | LLM configurada (processamento de texto e geração) | **Não Determinística** | Prompts estruturados; o Markdown gerado é considerado **não confiável** para inserção em HTML. |
| **Z3: Renderização Determinística** | `src/delivery/renderer.py` | **Fronteira de Blindagem** | `format_inline()`, `html.escape(..., quote=True)`, validação de RFC/Userinfo em `_is_safe_url()`, teste canônico de invariantes. |
| **Z4: Canais de Entrega e Apresentação** | `src/delivery/base.py`, SMTP Gmail, Preview no Navegador | **Transporte & Exibição** | Conexão SMTP com TLS estrito (`ssl.create_default_context()`) para entrega de e-mail; gravação local em arquivo para preview (o navegador pode realizar requisições de rede para carregar recursos remotos referenciados no HTML, como imagens externas). A segurança do conteúdo continua sob responsabilidade do renderizador. |

#### A. As 4 Ressalvas Conceituais Formalmente Aprovadas na Retrospectiva
1. **Fronteiras Independentes e Conteúdo Não Confiável por Definição:** Mapeamento explícito e separado das fronteiras entre fontes externas, síntese pela LLM configurada, Markdown gerado, renderer determinístico e canais de entrega. Todo conteúdo externo e todo Markdown da LLM devem ser tratados como não confiáveis até passarem pelo tratamento contextual do renderizador.
2. **Blindagem Determinística no Renderer:** A proteção contra XSS e HTML Injection depende exclusivamente da implementação determinística do renderizador (escape contextual, validação de URLs e cobertura exaustiva de campos dinâmicos).
3. **Desvinculação entre Sanitização HTML e Prompt Injection:** A sanitização e neutralização de tags HTML no renderizador **não resolve nem mitiga Prompt Injection**; Prompt Injection é um vetor de manipulação semântica da LLM pertencente à fronteira da IA, demandando defesas próprias de prompt e curadoria.
4. **Separação Rigorosa entre Segurança de Transporte e de Conteúdo:** O transporte via SMTP com TLS protege a confidencialidade e integridade do canal de conexão, mas não garante que o conteúdo, as afirmações editoriais ou os links incluídos sejam idôneos ou seguros.

#### B. Os 3 Princípios Complementares Derivados (Propostos nesta Especificação)
5. **Risco Residual de Phishing em URLs Sintaticamente Válidas:** A validação sintática estrita de URLs (`_is_safe_url()`) garante conformidade com RFC 1123, hostname válido e ausência de userinfo, mas não verifica a reputação do domínio de destino; URLs sintaticamente perfeitas ainda podem direcionar para destinos maliciosos.
6. **Segurança Relativa do HTML Gerado:** O documento HTML final não é rotulado como "universalmente seguro"; sua segurança é relativa e estritamente delimitada pelas regras de sanitização implementadas e cobertas pela suíte canônica de testes de invariantes.
7. **Preview Local no Navegador como Superfície Ativa:** A prévia local (`--preview`) não realiza envio SMTP (grava o relatório em `reports/preview.html` e aciona o navegador padrão). Contudo, o navegador pode realizar requisições de rede para carregar recursos remotos (como imagens e fontes externas) e interpreta ativamente o HTML renderizado. Portanto, o preview local exige as mesmas garantias de blindagem contra injeção e execução de scripts que o relatório transmitido por e-mail, sendo a segurança do conteúdo de inteira responsabilidade do renderizador determinístico. Não se deve assumir que o preview bloqueia tráfego externo.

---

## 5. Rastreabilidade Bidirecional

| Decisão | Requisito da Spec | Componente Afetado | Artefato de Verificação / Teste | Status de Governança |
| :---: | :--- | :--- | :--- | :--- |
| **D1** | Invariante Anti-XSS estrutural em 8 superfícies, máquina de estados, validação estática de metas/style, proibição de srcset, URLs com userinfo e Bento Grid | `src/delivery/renderer.py` | `tests/test_renderer.py` (`TestRendererCanaryInvariants`) | Aprovado na Retrospectiva (Refinado na Revisão 5.2) |
| **D2** | Cláusula "Safe by Default" para agentes de IA no `AGENTS.md §3` | `AGENTS.md` | Inspeção documental e Code Review (Standards) | Aprovado na Retrospectiva |
| **D3** | Registro de Fronteiras de Confiança, 4 ressalvas aprovadas e 3 princípios derivados | `docs/ARCHITECTURE.md §6` | Inspeção documental e Code Review (Spec) | 4 Ressalvas Aprovadas; 3 Princípios Derivados Sujeitos a Aprovação |
| **D4** | Unificação da conexão SMTP SSL em `src/core/smtp.py` via context manager nativo e 4 cenários de teste | `src/core/smtp.py`<br>`src/delivery/base.py`<br>`src/core/healthcheck.py` | `tests/test_smtp.py`<br>`tests/test_delivery_channels.py`<br>`tests/test_healthcheck.py`<br>`tests/test_delivery_integration.py` | Aprovado na Retrospectiva; Simplificação Nativa Sujeita a Aprovação |

---

## 6. Critérios de Aceitação (Definition of Done)

### CA-D1: Invariantes Anti-XSS no Renderizador
* **CA-D1.1:** O teste canônico em `tests/test_renderer.py` cobre formalmente todas as 8 superfícies de entrada externas identificadas, executando de forma determinística sob os guardrails de rede sem bloqueios ou sleeps.
* **CA-D1.2:** A classe `XSSCanaryParser` implementa máquina de estados estrita com controle de abertura e fechamento de `html`, `head` e `body` (rejeitando transições anômalas sem corromper o estado), audita a presença exata das 4 tags `<meta>` comparando seus atributos reais com `EXPECTED_STATIC_METAS` (`len(matched_metas) == 4`, sem duplicatas ou substituições), impede o fechamento de `</head>` com `<style>` ainda aberto, exige exatamente 1 bloco `<style>` no documento (`style_tags_count == 1`), comprova ausência de canários em atributos HTML (`canary_attrs_found == []`), ausência de canários no bloco `<style>` (`canary_in_style_found == []`), proíbe expressamente o atributo `srcset` (`unsafe_attrs_found == []`) e documenta a inspeção de atributos `style` como heurística de integridade.
* **CA-D1.3:** O teste canônico comprova que a URL com userinfo (`https://evil.com@attacker.com`) é rejeitada por `_is_safe_url()`, não gerando elemento `<a href="...">` e sendo neutralizada como texto/`<span>`.
* **CA-D1.4:** Todos os 8 identificadores canários são capturados como nós de texto inertes em `handle_data()`, e a inspeção confirma ausência total de canários em atributos HTML e dentro do bloco `<style>`.
* **CA-D1.5:** A asserção automatizada verifica a integridade de tags estruturais e classes essenciais do Bento Grid (`.main-container`, `.newspaper-section`, `.dropcap`, `.nav-pill`, `.footer-card`), mantendo a distinção formal de que fidelidade visual/tipográfica é responsabilidade de inspeção humana via `--preview`.

### CA-D2: Diretriz "Safe by Default" no AGENTS.md
* **CA-D2.1:** `AGENTS.md §3` contém o item compacto de segurança por padrão com redação alinhada à decisão aprovada.
* **CA-D2.2:** O texto prescreve o tratamento contextual (`format_inline` e `html.escape(..., quote=True)`), validação de URLs antes de `<a>`, `context=ssl.create_default_context()` no SMTP e exigência de testes para novos campos externos.
* **CA-D2.3:** Nenhum detalhe efêmero ou de baixo nível de implementação (regexes, RFC 1123, IPv6) é adicionado ao `AGENTS.md`.

### CA-D3: Fronteiras de Confiança no ARCHITECTURE.md
* **CA-D3.1:** `docs/ARCHITECTURE.md §6` documenta a tabela mapeando as 4 zonas de confiança, utilizando referência genérica à LLM configurada e descrevendo com precisão que a prévia local não faz entrega SMTP mas pode carregar recursos remotos no navegador.
* **CA-D3.2:** As 4 ressalvas conceituais aprovadas na retrospectiva e os 3 princípios complementares derivados constam formalmente descritos no texto da seção §6.

### CA-D4: Unificação da Conexão SMTP Segura
* **CA-D4.1:** O módulo `src/core/smtp.py` implementa `conectar_smtp_ssl` como context manager, centralizando host, porta 465, timeout configurável, `ssl.create_default_context()`, normalização de senha de aplicativo e autenticação.
* **CA-D4.2:** O contrato da função apoia-se exclusivamente no context manager nativo `with server:`, com cobertura de testes unitários para fechamento determinístico nos 4 cenários reais de protocolo do CPython: (1) saída normal com `QUIT` (221); (2) falha no `login()` com preservação do `SMTPAuthenticationError`; (3) desconexão/timeout durante `QUIT` convertida para `SMTPServerDisconnected` e tratada sem vazamento de erro espúrio; e (4) resposta com código != 221 levantando `SMTPResponseException` com fechamento garantido do socket.
* **CA-D4.3:** `EmailDeliveryChannel.deliver()` consome `conectar_smtp_ssl` preservando sua assinatura pública, retorno booleano e registro exato do log original `logger.error(f"❌ Erro ao enviar e-mail via SMTP: {e}")`.
* **CA-D4.4:** `check_email()` consome `conectar_smtp_ssl` preservando sua assinatura pública, retorno exato `(False, f"Falha no login SMTP do Gmail: {e}")` e sem emissão de log de erro fatal.
* **CA-D4.5:** O grafo de dependências permanece estritamente unidirecional e descendente (`delivery -> core` e `healthcheck -> core.smtp`), sem importação reversa de `delivery` em `core`.

### Critérios Gerais de Conclusão (CG)
* **CG.1:** 100% dos testes da suíte canônica executam e passam sob os guardrails de rede:  
  `python -m unittest discover -s tests -t . -v`
* **CG.2:** Zero avisos de recursos em execução estrita:  
  `python -W error::ResourceWarning -m unittest discover -s tests -t . -v`
* **CG.3:** Formatação git limpa e sem espaços residuais:  
  `git diff --check`
* **CG.4:** Nenhuma dependência externa adicionada a `requirements.txt`.
