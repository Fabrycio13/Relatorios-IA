# Guia Operacional: Preflight Canônico (`scripts/preflight.py`)

Este guia orienta desenvolvedores e agentes de IA sobre a utilização, o contrato funcional e o diagnóstico de falhas do **Preflight Canônico** do repositório `Relatorios-IA`.

---

## 1. Visão Geral e Filosofia

O script [`scripts/preflight.py`](../../scripts/preflight.py) é o portão de qualidade mandatório da *Definition of Done* antes de propor commits locais ou publicações remotas (*push*).

### Princípios de Engenharia:
* **Estritamente Read-Only:** Não executa mutações no Git (`git add`, `git reset`, `git commit`) e não altera configurações ou arquivos.
* **Isolamento de Rede:** Opera de forma 100% hermética e local. **Não executa `git fetch` automaticamente**.
* **Zero Dependências:** Construído unicamente sobre a biblioteca padrão do Python (`sys`, `os`, `subprocess`, `pathlib`, `re`).
* **Higiene de Ambiente:** Utiliza `--no-ext-diff` e `--no-textconv` em invocações do Git e define `PYTHONDONTWRITEBYTECODE=1` para evitar poluição de cache `__pycache__`.

---

## 2. Invocação Canônica e Fluxo Operacional Obrigatório

A partir da raiz do repositório, o preflight canônico é executado via:

```bash
python scripts/preflight.py
```

O script utiliza internamente `sys.executable` para invocar a suíte de testes com o mesmo interpretador Python ativo no terminal.

### Ordem Operacional Mandatória (Ciclo de Vida de Commit e Push):

O preflight valida o snapshot em staging (`git diff --cached`) e os commits locais pendentes em relação à base remota. A sequência operacional obrigatória para desenvolvedores e agentes de IA é:

```mermaid
flowchart LR
    A["1. Preparar Alterações\n(Working tree)"] --> B["2. Staging Restrito\ngit add <arquivos>"]
    B --> C["3. Preflight no Staging\npython scripts/preflight.py"]
    C --> D["4. Criar Commit Local\ngit commit -m '...'"]
    D --> E["5. Preflight Pós-Commit\npython scripts/preflight.py"]
    E --> F["6. Publicação Remota\ngit push"]
```

1. **Preparar alterações:** Modifique apenas os arquivos pertencentes ao escopo da tarefa, mantendo a working tree limpa de artefatos indesejados.
2. **Fazer staging explícito e restrito:** Adicione exclusivamente os arquivos autorizados (`git add <arquivo1> <arquivo2>`).
3. **Executar o preflight sobre o snapshot staged:** Execute `python scripts/preflight.py`. O preflight inspeciona o diff staged em busca de segredos, caminhos proibidos e erros de whitespace.
4. **Criar o commit local:** Somente após a aprovação com **Código 0**, crie o commit local (`git commit`).
5. **Revalidar os commits locais pendentes (Pré-Push):** Execute novamente `python scripts/preflight.py`. O preflight agora validará cada commit local acumulado em relação à base de tracking (`@{upstream}` ou `origin/main`).
6. **Publicar no remoto:** Somente com o preflight aprovado e no estado `AHEAD` (`pronto_para_push = True`), execute `git push`.

---

## 3. O que é Verificado

O preflight executa um pipeline sequencial com interrupção imediata em falhas críticas (*fail-fast*):

```mermaid
flowchart TD
    S1["1. Ambiente Git\nValida repositório e executável"] --> S2["2. Staging (Pré-Commit)\nCaminhos sensíveis, Blobs de cópias/renomeações e Segredos no diff"]
    S2 --> S3["3. Resolução de Base e Histórico Local\nInspeciona individualmente cada commit pendente (Root, Normal ou Merge)"]
    S3 --> S4["4. Whitespace e Sintaxe de Diff\nStaged (Bloqueante) vs Working Tree (Informativo)"]
    S4 --> S5["5. Suíte Canônica de Testes\nDescoberta dinâmica via unittest"]
    S5 --> S6["Conclusão Determinística (Código 0 ou 1)"]
```

### Detalhamento das Etapas:

1. **Inspeção de Staging (Pré-Commit):**
   - Utiliza `git diff --cached --name-status -C --find-copies-harder --no-ext-diff -z`.
   - Bloqueia adições (`A`), modificações (`M`), trocas de tipo (`T`), renomeações (`R`) e cópias (`C`) envolvendo arquivos proibidos.
   - Para cópias (`C`), lê o conteúdo integral do blob de destino (`git show --no-ext-diff --no-textconv :<path>`) para detectar segredos copiados para nomes inofensivos.
   - Permite deleções isoladas (`D`) como saneamento seguro.
2. **Inspeção de Commits Locais (Pré-Push):**
   - Determina a lista de commits pendentes de envio em relação à base remota.
   - Inspeciona cada commit atomicamente:
     - *Root Commits:* `git diff-tree --no-commit-id --root ...`
     - *Commits Normais:* `git diff-tree --no-commit-id <sha>~1 <sha>`
     - *Commits de Merge:* `git diff-tree --no-commit-id <sha>^1 <sha>`
   - Garante que segredos adicionados em um commit e removidos em outro sejam flagrados no commit de origem.
3. **Detecção de Segredos por Regex Estrito:**
   - Detecta chaves privadas PEM, tokens GitHub (`ghp_`, `github_pat_`), chaves de API Google (`AIza`) e senhas de app Gmail.
   - **Masking Obrigatório:** Nunca imprime valores reais de tokens no terminal ou logs (`ghp_****...****`).
4. **Validação de Whitespace:**
   - `git diff --cached --check`: Erros de whitespace ou marcadores de conflito (`<<<<<<<`) no staging **bloqueiam** a execução.
   - `git diff --check`: Erros na working tree não-staged emitem **aviso amarelo informativo**, sem bloquear.
5. **Execução Dinâmica de Testes:**
   - Executa `python -m unittest discover -s tests -t . -v`.
   - Valida `returncode == 0` e confirma dinamicamente que a contagem de testes foi maior que zero (`Ran N tests`).
   - Se zero testes forem descobertos, encerra com erro.

---

## 4. Códigos de Saída, Prontidão para Publicação e Semântica Git

| Código | Significado | Prontidão para Push | Próxima Ação |
| :---: | :--- | :---: | :--- |
| **`0`** | **Verificações Locais Aprovadas.** Staging e commits locais seguros; suíte de testes 100% verde. | Condicional ao estado Git | Consultar o estado da branch antes de publicar. |
| **`1`** | **Falha de Validação.** Segredos detectados, conflito não resolvido, whitespace corrompido no index ou testes quebrados. | **NÃO** | Corrigir as violações apontadas e reexecutar o preflight. |

### Diferenciação entre Aprovação Local e Prontidão para Publicação:

* **Aprovação Local (Código 0):** Certifica estritamente que o staging, os commits locais pendentes e a suíte de testes estão seguros e sem violações.
* **Prontidão para Publicação (`pronto_para_push = True`):** Exclusiva do estado `AHEAD`. Indica que há commits locais validados e a branch está em condições de envio imediato via `git push`.
* **Necessidade de Reconciliação com o Remoto:** Nos estados `BEHIND` e `DIVERGED`, as verificações locais são aprovadas (código 0), mas a publicação **não é autorizada** até que o desenvolvedor execute a sincronização remota.

### Estados de Relacionamento Git:

* **`SYNCED`:** A branch local possui o mesmo commit do remoto (`HEAD == origin/main`). 0 commits a enviar (`pronto_para_push = False`).
* **`AHEAD`:** A branch local possui commits exclusivos à frente do remoto prontos para publicação via `git push` (`pronto_para_push = True`).
* **`BEHIND`:** O remoto avançou. As validações locais passaram, mas é obrigatório executar `git pull` antes de publicar (`pronto_para_push = False`).
* **`DIVERGED`:** Houve divergência entre local e remoto. Os commits locais foram validados, mas exigem reconciliação (`git merge` ou `git rebase`) antes do push (`pronto_para_push = False`).
* **`AHEAD_LOCAL`:** Commits validados contra uma branch local (ex: `main`), sem remoto configurado. Não confere prontidão de push (`pronto_para_push = False`).
* **`UNRELATED` / `UNKNOWN`:** Árvores sem ancestral comum ou sem base confiável. O preflight **rejeita com código 1**.

---

## 5. Regras de Segurança e Fixtures de Teste

### Arquivos Proibidos por Caminho:
* `.env`, `.env.*`, `.env_*`, `.env-*` (exceção explícita autorizada: `.env.example` em qualquer nível de pasta).
* `auth.json`, `email_config.json`.
* `.session/` (todo o diretório).
* `*.pem`, `*.key`, `*.pfx`, `*.pkcs12`.
* `data/ultimo_envio.txt`, `data/*.lock`, `data/*.tmp`, `data/quarantine/*`, `*.lock`.

### Política Estrita de Fixtures em Testes Automatizados:

O preflight **não possui exceções genéricas** para arquivos de teste (como diretórios `tests/`). Qualquer arquivo staged que contenha um padrão de credencial real ou token sintético completo será bloqueado. Para evitar falsos positivos nos testes preservando a capacidade de validação dos scanners, adote estritamente as duas estratégias abaixo:

#### Estratégia 1: Placeholders Sintaticamente Inválidos (Testes Neutros / Negativos)
Quando o teste precisa simular valores de configuração, chaves ou tokens, mas **não tem o propósito de acionar o scanner de segurança**, utilize placeholders que violam intencionalmente a especificação sintática das credenciais oficiais:
* **GitHub Token Inválido:** `"ghp_TEST_PLACEHOLDER"` (tamanho e caracteres fora da especificação).
* **Google API Key Inválida:** `"AIza_MOCK_INVALID_KEY"` (tamanho e caracteres fora da especificação).
* **Chave PEM Fictícia:** `"-----BEGIN DUMMY TEST KEY-----"`.
* **Senha Gmail Fictícia:** `"GMAIL_APP_PASSWORD = 'curta'"` (tamanho menor que 16 caracteres).

#### Estratégia 2: Construção Dinâmica em Runtime (Testes Positivos de Detecção e Masking)
Quando o teste precisa validar que o scanner detecta e mascara padrões reais de segredos, o token **nunca deve ser escrito literalmente no código-fonte versionado**. Em vez disso, monte o padrão em tempo de execução via concatenação ou multiplicação de strings:
* **GitHub Token Sintético:** `"ghp_" + ("1" * 36)`
* **Google API Key Sintética:** `"AIza" + "SyD-" + ("a" * 31)`
* **Chave PEM Sintética:** `"-----BEGIN " + "RSA " + "PRIVATE " + "KEY-----"`
* **Senha Gmail Sintética:** `"GMAIL_" + "APP_PASSWORD = '" + ("abcd " * 4) + "'"`

*Mecanismo de Isolamento:* No disco e no repositório versionado, o código-fonte contém apenas chamadas de concatenação em Python, que passam limpas pelo scanner de staging. Durante a execução da suíte, o token completo é sintetizado na memória volátil e gravado em repositórios Git temporários isolados (`tempfile.TemporaryDirectory`), permitindo validar com 100% de fidelidade a detecção, a rejeição e o mascaramento.

#### Meta-teste de Prevenção de Regressão:
A suíte `tests/test_preflight.py` conta com um meta-teste hermético determinístico (`test_meta_proprio_arquivo_test_preflight_livre_de_segredos_literais`). Ele lê o próprio arquivo de testes e o submete ao scanner do preflight. Qualquer token sintético válido escrito literalmente provocará falha imediata na suíte de testes antes que o staging seja aprovado.

---

## 6. Troubleshooting de Falhas Comuns

### "Arquivo proibido detectado no commit local X"
* **Causa:** Um arquivo sensível (como `.env` ou `auth.json`) foi incluído em um commit local pendente, mesmo que já tenha sido deletado em commit posterior.
* **Solução:** Remova o arquivo do histórico local utilizando `git rebase -i` ou `git reset` para desfazê-lo antes de tentar publicar.

### "Conflito de merge não resolvido (status 'U')"
* **Causa:** Há marcadores de conflito ou arquivos em estado unmerged no staging.
* **Solução:** Resolva os conflitos no arquivo, adicione com `git add <arquivo>` e complete o merge antes do preflight.

### "Base de publicação indeterminada"
* **Causa:** A branch atual não possui upstream configurado e não foi encontrada a referência `origin/main`.
* **Solução:** Configure o upstream da branch (`git branch --set-upstream-to=origin/<branch>`) ou atualize as referências locais via `git fetch origin`.
