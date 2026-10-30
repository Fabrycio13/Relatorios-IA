# 11: Catálogo Rotativo sem Repetição, Persistência Atômica e Ciclo de Vida Pós-Envio

**What to build:**
Implementar o ciclo determinístico de exaustão sem repetição para os dias regulares e a máquina de estados em `data/historico_banners.json`. O seletor resolve a próxima imagem do catálogo geral não utilizada no ciclo corrente. Quando todas as imagens disponíveis forem exibidas, o ciclo é resetado automaticamente. Imagens adicionadas dinamicamente à pasta são absorvidas no ciclo em andamento antes do reset. A persistência do uso é realizada com gravação atômica (`.tmp` + `os.replace`) e disparada **exclusivamente após o envio de e-mail bem-sucedido** no pipeline diário (`main.py`). O modo `--preview` permanece estritamente read-only. Tratamento de falhas entre o envio SMTP e a escrita em disco com reconciliação segura via `ultimo_envio.txt`.

**Blocked by:**
10: Banner Comemorativo de Feriados, Fallback em 3 Tiers e Integração E2E no Renderer (Somente Leitura)

**Status:**
ready-for-agent

**Files to modify:**
- `src/delivery/banner_selector.py`
- `main.py`
- `tests/test_banner_selector.py`
- `tests/test_delivery_integration.py`

**Acceptance criteria:**
- [ ] Implementar a lógica de rotação por ciclo de exaustão em `src/delivery/banner_selector.py`: nenhuma imagem do pool geral é repetida até que todas as imagens físicas disponíveis em `assets/banners/` tenham sido exibidas.
- [ ] Suporte à adição dinâmica no meio do ciclo: novas imagens inseridas na pasta entram no conjunto de não consumidas e são exibidas antes que o ciclo reinicie.
- [ ] Persistência segura em `data/historico_banners.json` com gravação atômica via arquivo temporário intermediário (`historico_banners.json.tmp`) e substituição atômica (`os.replace`).
- [ ] Recuperação graciosa contra falhas: se `historico_banners.json` for corrompido, estiver vazio ou for deletado, o sistema reconstrói o estado em memória sem lançar exceções.
- [ ] Reconciliação e tolerância a falhas entre SMTP e disco: se o SMTP enviar com sucesso mas a escrita do histórico falhar, uma reexecução com `--force` no mesmo dia (já registrado em `ultimo_envio.txt`) reconcilia o estado sem queimar outro banner.
- [ ] Idempotência no mesmo dia: reexecuções na mesma data retornam exatamente o mesmo banner previamente atribuído.
- [ ] Ocorrência de feriado comemorativo não consome nem desalinha a sequência de banners do catálogo geral.
- [ ] O modo `--preview` (`python main.py --preview` ou `render_bento_email`) é estritamente somente leitura: nunca grava em disco, não altera `data/historico_banners.json` e não consome imagens do ciclo.
- [ ] Hook `confirmar_banner_utilizado()` integrado ao `main.py` invocado exclusivamente após o envio bem-sucedido via `EmailDeliveryChannel` (`args.step in ["all", "email"]` e `not args.preview`).
- [ ] Concorrência protegida: a trava diária existente (`data/ultimo_envio.txt`) impede corridas entre execuções concorrentes do pipeline.
- [ ] Testes unitários e de integração herméticos:
  - Ciclo de exaustão completo sobre pool de N imagens sem repetição.
  - Inserção dinâmica de nova imagem durante o ciclo e seu consumo antes do reset.
  - Idempotência de chamadas consecutivas para a mesma data de envio.
  - Garantia de que execução em `--preview` não cria nem altera `historico_banners.json`.
  - Simulação de corrupção do arquivo de histórico com recuperação automática.
  - Teste de integração do ciclo de vida: envio simulado com mock SMTP confirma o histórico; falha no envio não consome o histórico.
- [ ] Execução dos testes novos e da suíte completa de regressão (`python -m unittest discover tests -v`) com 100% de aprovação ao término do ticket.
- [ ] Demonstração: Teste simulando sequência de dias demonstra a rotação sem repetição das imagens do pool geral e o isolamento total do modo preview.
