# 5. Isolamento de Preview e Ciclo de Vida do Número de Edição

**Status:** Aprovado
**Data:** 16/11/2026
**Contexto Técnico:** Entrega e Apresentação / Persistência de Publicação

---

## Contexto e Problema

O cabeçalho do Diário de Engenharia exibe a numeração sequencial da publicação no padrão `ANO I - Nº XXX`. Historicamente, a função `obter_numero_edicao()` persistia o incremento diretamente no arquivo físico `data/edicoes.json` durante a renderização do HTML pelo `render_bento_email`.

Esse comportamento gerava efeitos colaterais indesejados:
1. **Mutação de estado em pré-visualização e testes:** Execuções do comando local `python main.py --preview` (e execuções de testes unitários que invocavam o renderer) incrementavam e gravavam o número da edição em disco, poluindo o histórico de produção sem que houvesse qualquer envio real por e-mail.
2. **Risco de sobrescrita destrutiva:** Se `data/edicoes.json` sofresse corrupção de formatação ou falha transitória de leitura, o bloco de captura genérica de exceções reiniciava o dicionário como vazio (`{}`), sobrescrevendo o arquivo com a edição atual como `001` e descartando o histórico pregresso (violação da invariante DEF-01).
3. **Potencial divergência entre número renderizado e persistido:** Não havia garantia estrutural de que o número renderizado no HTML enviado corresponderia ao valor gravado após o envio em caso de concorrência ou reexecuções.

---

## Decisão

1. **Desacoplamento entre Projeção e Persistência:**
   - A função `obter_numero_edicao(data_str, persist=False)` opera puramente em memória por padrão (`persist=False`). A visualização local (`--preview`) e a suíte de testes projetam a numeração sem realizar qualquer I/O de escrita em disco.
   - O renderer `render_bento_email` foi tornado livre de efeitos colaterais de persistência durante a renderização, recebendo opcionalmente o `numero_edicao` já resolvido.

2. **Invariante de Correspondência Exata da Edição:**
   - Em execuções reais de envio (`main.py`), o número é projetado previamente (`numero_edicao_envio`), injetado no renderer e repassado a `confirmar_edicao_utilizada(data_envio, numero_edicao)`. O número persistido em disco corresponde exatamente ao valor impresso no cabeçalho do e-mail.

3. **Confirmação Estritamente Pós-SMTP:**
   - A chamada a `confirmar_edicao_utilizada()` é realizada exclusivamente em `main.py` após o retorno bem-sucedido do transporte SMTP (`EmailDeliveryChannel`).

4. **Proteção Anti-Sobrescrita Destrutiva (Invariante DEF-01):**
   - A função `_carregar_edicoes()` valida a existência e a integridade sintática do JSON (exigindo `isinstance(data, dict)`). Se o arquivo existir mas a leitura ou decodificação falhar, retorna `None`.
   - Diante de `None`, `confirmar_edicao_utilizada()` e `obter_numero_edicao(persist=True)` abortam imediatamente a gravação, preservando integralmente os bytes originais em disco e emitindo aviso em log.

5. **Validação de Consistência e Rejeição de Conflitos:**
   - Se a data já estiver registrada com o mesmo número, a operação é idempotente (`return True`).
   - Se a data já possuir outro número atribuído, ou se o número solicitado já pertencer a outra data histórica (duplicação de edição), a confirmação é rejeitada explicitamente (`return False`) com alerta em log.

6. **Limpeza Defensiva em Escritas Atômicas:**
   - A gravação atômica (`_salvar_edicoes_atomico` e `registrar_envio_sucesso`) remove defensivamente arquivos temporários `.tmp` em caso de falha antes ou durante `os.replace`.

---

## Alternativas Consideradas

* **Reconciliação Automática Cega baseada no Relatório Markdown:**
  *Descartada.* A existência de um arquivo Markdown em `reports/` não comprova que houve despacho e aceitação pelo servidor SMTP, podendo induzir falsas confirmações de envio.
* **Persistência Prévia ao Envio SMTP com Rollback Local:**
  *Descartada.* Complexidade acidental desnecessária. Se o processo abortasse ou perdesse energia durante a conexão SMTP, o rollback nunca seria executado, deixando edições "queimadas" no disco.
* **Transação Distribuída de Duas Fases (2PC):**
  *Descartada.* Inaplicável entre o protocolo SMTP padrão (que não suporta commit em duas fases) e o sistema de arquivos local.

---

## Consequências

### Positivas
- **Isolamento de Preview:** `python main.py --preview` e a suíte de testes tornam-se rigorosamente livres de efeitos colaterais em `data/edicoes.json`.
- **Integridade Histórica:** Arquivos corrompidos ou com falhas de leitura não são reiniciados destrutivamente.
- **Rastreabilidade e Determinismo:** O número persistido em disco é garantidamente idêntico ao entregue na caixa de entrada dos destinatários.

### Trade-offs e Riscos Residuais
- **Ausência de Garantia Exactly-Once e Risco de Reutilização Pós-Crash:**
  Não há garantia de entrega exatamente uma vez (*exactly-once*) entre SMTP e disco. Caso ocorra um encerramento abrupto do processo (queda de energia, crash de SO ou finalização forçada de processo) imediatamente após o servidor SMTP aceitar a mensagem, mas antes de `confirmar_edicao_utilizada()` concluir a escrita atômica, o e-mail terá sido entregue com sucesso, mas a edição não constará em `edicoes.json`.
  *Consequência:* Na publicação seguinte, o sistema projetará e utilizará o mesmo número sequencial. Esse comportamento é um trade-off consciente e documentado: prioriza a não-duplicação de mensagens aos destinatários (evita reenvio cego de e-mail), aceitando como risco residual menor a possibilidade de reutilização do número sequencial em caso de crash pós-SMTP.
- **Degradação Graciosa Pós-SMTP:**
  Se a confirmação em disco falhar pós-SMTP (ex: disco cheio), o pipeline registra aviso em log sem abortar com erro fatal (`sys.exit(1)`), pois a entrega principal da automação já foi concluída com êxito.

---

## Rastreabilidade e Evidências

- **Commit de Implementação:** [`d2bab62`](https://github.com/Fabrycio13/Relatorios-IA/commit/d2bab62) (*fix(delivery): isolate edition preview and harden publication state*).
- **Módulos Afetados:** [`main.py`](../../main.py), [`src/delivery/renderer.py`](../../src/delivery/renderer.py), [`src/delivery/dispatcher.py`](../../src/delivery/dispatcher.py), [`src/delivery/__init__.py`](../../src/delivery/__init__.py).
- **Testes Relacionados:** [`tests/test_renderer.py`](../../tests/test_renderer.py) e [`tests/test_delivery_integration.py`](../../tests/test_delivery_integration.py).
- **Resultados Reportados:** 387 testes herméticos aprovados sem falhas na suíte canônica de testes automatizados (`python -m unittest discover -s tests -t .`).
