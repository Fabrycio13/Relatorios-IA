# Especificação Técnica 0001: DailyIngestionBatch

**Status:** Aprovado para detalhamento de tickets  
**Área:** Ingestão & Processamento de Dados  
**Prerequisitos:** Nenhum (Primeiro passo da migração)  

---

## 1. Problem Statement
Atualmente, cada módulo coletor (`src/collectors/`) salva seus dados de forma descentralizada diretamente em arquivos JSON em `data/` (`tweets_coletados.json`, `github_trending.json`, `hf_papers.json`), e a função `gerar_resumo_ia()` em `src/processors/ai_summarizer.py` relê esses arquivos individualmente do disco. 

Essa dependência de I/O em disco no caminho crítico:
* Impede que o pipeline de síntese seja testado em memória (< 10ms) sem criar e limpar arquivos temporários.
* Oculta os contratos de tipo e o esquema de dados trafegado entre coleta e síntese.
* Pode ocasionar leitura de dados residuais ou desatualizados de execuções anteriores caso um dos coletores falhe silenciosamente sem limpar o arquivo em disco.

---

## 2. Solution
Introduzir o modelo de dados tipado `DailyIngestionBatch` como um dataclass nativo em `src/core/models.py`. O pipeline em memória passa a transportar o lote consolidado diretamente dos coletores para a função `gerar_resumo_ia(batch)`.

Para preservar a resiliência e a compatibilidade operacional:
* O lote mantém um método de persistência atômica (`batch.save_snapshot()`) que grava/sobrescreve os arquivos JSON em `data/` com timestamp explícito (`collected_at`), garantindo que dados de execuções distintas nunca se misturem.
* Caso `gerar_resumo_ia()` seja chamado sem argumentos (como no comando `python main.py --step summarize`), ele utiliza o método `DailyIngestionBatch.load_snapshot()` como salvaguarda para carregar os dados em disco.

---

## 3. User Stories
1. **Como desenvolvedor**, quero que a função de síntese (`gerar_resumo_ia`) receba um objeto em memória `DailyIngestionBatch`, para que eu possa testá-la unitariamente com dados mockados em milissegundos sem tocar o disco.
2. **Como mantenedor**, quero que o lote carregue modelos fortemente tipados (`Tweet`, `GitHubRepo`, `ResearchPaper`), para que erros de digitação de chaves em dicionários sejam eliminados em tempo de compilação/análise estática.
3. **Como operador**, quero que uma cópia dos dados brutos continue sendo gravada atomicamente em `data/` a cada execução, para que em caso de queda na OpenAI os dados coletados do X e do GitHub não sejam perdidos.
4. **Como operador**, quero que o comando `python main.py --step summarize` continue funcionando isoladamente, carregando automaticamente o snapshot de dados existente em disco.
5. **Como operador**, quero que o snapshot sobrescreva os dados da execução anterior de forma atômica e registre o timestamp ISO de coleta, para evitar a contaminação cruzada de dados residuais de dias anteriores.

---

## 4. Implementation Decisions

### 4.1 Estrutura do Modelo (`src/core/models.py`)
* Criar o dataclass `DailyIngestionBatch`:
  * `tweets: list[Tweet] = field(default_factory=list)`
  * `repos: list[GitHubRepo] = field(default_factory=list)`
  * `papers: list[ResearchPaper] = field(default_factory=list)`
  * `collected_at: str = field(default_factory=...)`
* Métodos essenciais:
  * `is_empty() -> bool`: indica se nenhuma fonte obteve dados.
  * `to_dict() -> dict[str, Any]` e `from_dict(data) -> DailyIngestionBatch`: serialização limpa.
  * `save_snapshot(data_dir: Path) -> None`: grava atomicamente os 3 arquivos JSON correspondentes em `data/`.
  * `load_snapshot(data_dir: Path) -> DailyIngestionBatch`: reconstitui o lote tipado a partir dos arquivos JSON.

### 4.2 Adaptação da Síntese (`src/processors/ai_summarizer.py`)
* Atualizar a assinatura da função:
  `def gerar_resumo_ia(batch: DailyIngestionBatch | None = None) -> Path | None:`
* Se `batch` for fornecido, utiliza diretamente `batch.tweets`, `batch.repos` e `batch.papers`.
* Se `batch is None`, executa `DailyIngestionBatch.load_snapshot(DATA_DIR)`. Se nenhum dado for encontrado, emite erro claro e aborta.
* As funções auxiliares internas (`_anexar_secao_github`, `_anexar_secao_papers`) passam a receber diretamente as listas de objetos em memória (`list[GitHubRepo]`, `list[ResearchPaper]`).

### 4.3 Política de Falhas e Degradação Graciosa
* **Preservação da política atual:** Se um coletor não conseguir dados (ex: Twitter sem posts novos ou timeout de scraping), a lista correspondente em `batch.tweets` será vazia (`[]`). A síntese continua normalmente processando as fontes que obtiveram sucesso, sem abortar o pipeline.

---

## 5. Testing Decisions & Acceptance Criteria

### 5.1 Critérios de Aceitação
- [ ] O modelo `DailyIngestionBatch` valida e tipa coleções de `Tweet`, `GitHubRepo` e `ResearchPaper`.
- [ ] Chamar `gerar_resumo_ia(batch)` em memória não realiza leitura dos arquivos `data/*.json`.
- [ ] O comando `python main.py --step summarize` continua operando com sucesso ao ler o snapshot do disco.
- [ ] A execução completa `--step all` atualiza os snapshots em disco com dados novos e timestamp da execução.
- [ ] A trava antirrepetição em `data/ultimo_envio.txt` permanece inalterada e funcional.

### 5.2 Testes de Regressão Automatizados
- **Teste Unitário de Modelo:** Validar serialização/desserialização de `DailyIngestionBatch` em memória.
- **Teste Unitário de Snapshot:** Validar que `save_snapshot` e `load_snapshot` preservam 100% dos campos de cada entidade em diretório temporário.
- **Teste Unitário de Síntese:** Executar `gerar_resumo_ia` com um lote falso e mock da OpenAI, verificando a geração do arquivo Markdown sem ler a pasta `data/`.

---

## 6. Out of Scope
* Alterar o formato do relatório final em Markdown (`reports/Resumo_IA_YYYY-MM-DD.md`).
* Modificar a lógica de scraping do Playwright ou as consultas de API do GitHub e Hugging Face.
