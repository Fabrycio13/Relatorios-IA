# Retrospectiva: Banners Rotativos, Concorrência e Ciclo de Vida E2E (Spec 0005)

**Data:** 29 de Outubro de 2026
**Status do Projeto:** 134/134 testes automatizados aprovados | CI no GitHub Actions 100% verde
**Escopo Analisado:** Implementação completa da Spec 0005 (Tickets 10, 11 e 12 / PR #7), abrangendo: seletor de feriados e 3 Tiers, catálogo rotativo por exaustão sem repetição, persistência atômica, exclusão mútua por lock de SO (Windows/Linux), links em alta resolução, modo preview isolado e formalização do Style Guide Gate.

---

## 1. O que Funcionou Bem

1. **Protocolos Pragmáticos e Dataclasses Congeladas (`BannerInfo`):**
   O uso de `@dataclass(frozen=True)` para `BannerInfo` impediu mutações acidentais de estado durante o pipeline de renderização e facilitou a injeção em mocks e testes unitários.
2. **Separação Estrita de Fases: Red-Green-Refactor e Duplo Code Review:**
   A revisão independente por dois subagentes especializados (Standards e Spec) detectou com precisão dois riscos sutis antes da consolidação do Ticket 12: a criação desnecessária de diretórios no *import time* e a fragilidade do patch de `DATA_DIR` nos testes de preview.
3. **Persistência Atômica com Substituição do SO (`.tmp` + `os.replace`):**
   A gravação de `historico_banners.json` mostrou-se 100% resiliente a corrupções de processo e simulações de disco cheio, garantindo idempotência e preservando o catálogo.
4. **Exclusão Mútua Cross-Platform Funcional:**
   A abstração de trava (`src/core/lock.py`) operou com precisão tanto sob Windows (`msvcrt`) quanto sob Ubuntu no CI (`fcntl`), garantindo o contrato operacional do Windows Task Scheduler (`sys.exit(0)` em caso de colisão de processos).

---

## 2. Padrões de Falha Observados e Oportunidades de Melhoria

### Candidato 1 (Severidade Alta): Falta de Bloqueador Hermético de Rede nos Testes
* **Categoria:** Automated checks / Guardrail
* **O que ocorreu:** Ao elaborar um teste para `python main.py --preview`, o agente chamou `main.main()` sem mockar `IngestionPipeline.run`. Como o step padrão é `all`, o pipeline disparou a coleta real do Twitter via Playwright em segundo plano (`task-3365`), precisando ser cancelada manualmente.
* **Causa Raiz:** A suíte de testes não possui um bloqueador global de socket ou trava padrão de rede que force falha imediata caso qualquer teste tente abrir conexão externa não mockada.
* **Melhoria Proposta:** Adicionar fixture de bloqueio de rede global nos testes (ou no `conftest.py` / `unittest` runner base) que intercepte chamadas de `socket.connect` e Playwright sem mock prévio, tornando o teste hermético por construção.

### Candidato 2 (Severidade Alta): Normalização de Line Endings no Windows (`.gitattributes`)
* **Categoria:** Automated checks / Tooling
* **O que ocorreu:** O `git diff --check` acusou quebras de linha corrompidas (`\r\r\n`) devido à escrita de arquivos de texto no Windows misturando substituições manuais de string com escrita em modo texto padrão.
* **Causa Raiz:** Ausência de arquivo `.gitattributes` no repositório configurando `* text=auto eol=lf`.
* **Melhoria Proposta:** Criar `.gitattributes` na raiz do projeto com regra explícita de `eol=lf` para arquivos Python, Markdown e JSON, garantindo que o Git converta e valide automaticamente as quebras de linha em qualquer SO.

### Candidato 3 (Severidade Média): Criação de Diretórios no *Import Time* em `config.py`
* **Categoria:** Coding standards / Mechanical check
* **O que ocorreu:** O laço `d.mkdir(parents=True, exist_ok=True)` em `src/core/config.py` criava `assets/banners/` no momento em que o módulo era importado. Isso gerava efeito colateral no sistema de arquivos e mascarava a verificação de fallback do Tier 3 para pastas inexistentes.
* **Melhoria Proposta:** Adicionar regra explícita nas diretrizes (ou linter): constantes de configuração devem apenas resolver e expor caminhos (`Path`). Mutações no disco (`mkdir`) devem ser lazy ou restritas estritamente a diretórios efêmeros de runtime (`reports/`, `logs/`, `data/`).

### Candidato 4 (Severidade Média): Mapeamento e Localização de Módulos de Teste
* **Categoria:** Navigation & Information access
* **O que ocorreu:** O agente tentou executar `tests/test_banner_rotation.py` e encontrou `ModuleNotFoundError`, pois os testes de rotação do Ticket 11 foram consolidados dentro de `tests/test_banner_selector.py`.
* **Melhoria Proposta:** Atualizar a seção de rastreabilidade da documentação e/ou manter equivalência estrita 1:1 entre nomes de funcionalidades e arquivos de teste, ou adicionar um ponteiro no topo de `tests/test_banner_selector.py` indicando que ele cobre tanto o Seletor (Ticket 10) quanto a Rotação (Ticket 11).

### Candidato 5 (Severidade Baixa): Limpeza de Descritores de Arquivo em Subprocessos (`ResourceWarning`)
* **Categoria:** Automated checks / Cleanup
* **O que ocorreu:** O teste de concorrência multiprocesso emitiu `ResourceWarning: unclosed file` sob Python 3.13 porque os descritores de pipe (`proc1.stdout`, `proc1.stderr`) não foram explicitamente fechados no bloco `finally:`.
* **Melhoria Proposta:** Adicionar `proc1.stdout.close()` e `proc1.stderr.close()` no cleanup do teste em `test_delivery_integration.py`.

---

## 3. Próximas Ações Prioritárias Recomendadas

1. **Criar `.gitattributes`:** Configurar normalização estrita de LF (`* text=auto eol=lf`) para eliminar avisos e riscos de `\r\r\n` no Windows. *(Custo: Mínimo | Benefício: Alto)*
2. **Sanitizar pipes do teste multiprocesso:** Fechar `proc1.stdout` e `proc1.stderr` explicitamente no `test_delivery_integration.py` para zerar `ResourceWarning` sob Python 3.13. *(Custo: Trivial | Benefício: Médio)*
3. **Bloqueador de Socket para Testes:** Investigar integração de um guardrail hermético que impeça chamadas reais de rede durante a execução de testes automatizados. *(Custo: Baixo | Benefício: Alto)*
