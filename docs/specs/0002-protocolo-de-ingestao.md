# Especificação Técnica 0002: Protocolo de Ingestão Desacoplado

**Status:** Aprovado para detalhamento de tickets  
**Área:** Ingestão de Dados & Orquestração  
**Prerequisitos:** Especificação 0001 (`DailyIngestionBatch`)  

---

## 1. Problem Statement
Atualmente, o arquivo `main.py` contém lógica procedural acoplada para importar e invocar individualmente três coletores com interfaces distintas:
* `coletar_tweets_vip(max_scrolls, headless)` (Playwright)
* `coletar_github_trending(dias_atras, limite_top)` (GitHub API)
* `coletar_papers_huggingface(limite_top)` (Hugging Face API)

Além disso, `main.py` trata flags CLI individuais (`--step collect-twitter`, `--step collect-github`, etc.) misturando regras de negócio de ingestão com a interface de linha de comando. Isso dificulta plugar novas fontes (como ArXiv, Bluesky ou Reddit) sem modificar o orquestrador principal.

---

## 2. Solution
Definir uma interface simples baseada em `typing.Protocol` chamada `IngestionSource` e um orquestrador de ingestão profundo chamado `IngestionPipeline` no pacote `src/collectors/`.

O `IngestionPipeline`:
* Registra os adaptadores de cada fonte (`TwitterSource`, `GitHubSource`, `HuggingFaceSource`).
* Expõe um método único e simples: `IngestionPipeline.run(sources=None) -> DailyIngestionBatch`.
* Centraliza os logs de início/término de cada fonte e garante o preenchimento consolidado do `DailyIngestionBatch`.
* Mantém suporte completo a execuções isoladas via CLI (`--step collect-twitter`, `--step collect-github`, `--step collect-papers`).

---

## 3. User Stories
1. **Como desenvolvedor**, quero que cada coletor obedeça à interface `IngestionSource`, para que eu possa adicionar uma nova fonte criando apenas um novo arquivo em `src/collectors/` sem alterar o código de `main.py`.
2. **Como mantenedor**, quero que o `IngestionPipeline` execute as fontes e encapsule o tratamento de logs e timeouts, para que `main.py` fique limpo e foque apenas no fluxo macro do diário.
3. **Como operador**, quero que a política de falhas permaneça graciosa: se uma fonte falhar ou der timeout (ex: Twitter), ela retorna lista vazia com log de aviso, sem impedir a coleta das demais fontes nem abortar o pipeline.
4. **Como operador**, quero continuar executando comandos como `python main.py --step collect-github` sem qualquer alteração na interface de linha de comando.

---

## 4. Implementation Decisions

### 4.1 Interface `IngestionSource` (`src/collectors/base.py`)
Utilizando `typing.Protocol` nativo da biblioteca padrão:
```python
from typing import Protocol, Any

class IngestionSource(Protocol):
    name: str  # "twitter", "github", "papers"
    
    def collect(self) -> list[Any]:
        """Executa a coleta da fonte e retorna a lista de entidades de domínio correspondente."""
        ...
```

### 4.2 Adaptadores de Fontes
Classes leves que encapsulam as chamadas existentes sem modificar a lógica interna de scraping ou HTTP:
* `TwitterSource`: chama `coletar_tweets_vip(headless=True)`.
* `GitHubSource`: chama `coletar_github_trending()`.
* `HuggingFaceSource`: chama `coletar_papers_huggingface()`.

### 4.3 Orquestrador de Ingestão (`IngestionPipeline`)
* Centraliza a lista de fontes ativas padrão.
* Método `run(target_source: str | None = None) -> DailyIngestionBatch`:
  * Se `target_source` for informado (ex: via `--step collect-github`), executa apenas a fonte solicitada.
  * Se `target_source` for `None` (ou `"all"` / `"collect"`), executa todas as fontes registradas.
  * Monta e retorna o `DailyIngestionBatch`.
  * Invoca `batch.save_snapshot()` para manter o disco atualizado como salvaguarda.

### 4.4 Política de Falha Estável
* **Sem alterações na política de falha:** O pipeline mantém exatamente o comportamento atual:
  * Timeout ou erro de rede em uma fonte = warning nos logs + lista vazia no lote.
  * O pipeline só aborta se todas as fontes falharem criticamente E o usuário estiver rodando um step exclusivo daquela fonte.

---

## 5. Testing Decisions & Acceptance Criteria

### 5.1 Critérios de Aceitação
- [ ] `main.py` não importa mais funções individuais de coletores (`coletar_tweets_vip`, etc.), delegando toda a coleta ao `IngestionPipeline`.
- [ ] Todos os 3 coletores existentes implementam `IngestionSource`.
- [ ] O comando `python main.py --step collect` executa todas as fontes e retorna o lote consolidado.
- [ ] O comando `python main.py --step collect-github` executa apenas a fonte do GitHub e atualiza seu snapshot.
- [ ] Se o Twitter falhar, o pipeline avisa no log e prossegue com a coleta do GitHub e Hugging Face.

### 5.2 Testes de Regressão Automatizados
- **Teste de Protocolo:** Teste unitário verificando que `TwitterSource`, `GitHubSource` e `HuggingFaceSource` cumprem o protocolo `IngestionSource`.
- **Teste de IngestionPipeline com Mock:** Injetar uma fonte falsa no pipeline e validar a composição correta do `DailyIngestionBatch`.
- **Teste de Tolerância a Falhas:** Injetar uma fonte que levanta exceção (`RuntimeError`) e certificar que o pipeline captura o erro, emite warning e retorna as demais fontes intactas.

---

## 6. Out of Scope
* Concorrência paralela assíncrona (manter execução síncrona e sequencial).
* Adição de novas fontes nesta etapa (o foco é aprofundar o módulo existente).
