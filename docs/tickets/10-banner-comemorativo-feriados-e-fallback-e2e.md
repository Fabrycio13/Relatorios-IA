# 10: Banner Comemorativo de Feriados, Fallback em 3 Tiers e Integração E2E no Renderer (Somente Leitura)

**What to build:**
Implementar o fluxo vertical (*tracer bullet*) completo para banners comemorativos de feriados (fixos via `MM-DD` e móveis via `YYYY-MM-DD`) e a hierarquia estrita de fallback em 3 Tiers. O módulo `src/delivery/banner_selector.py` define o dataclass `BannerInfo` e a função de resolução em modo estritamente somente leitura `resolver_banner_do_dia()`. Se a data de envio coincide com feriado cadastrado em `assets/banners/manifesto.json` e o arquivo físico existe, o sistema seleciona a arte temática e sua legenda contextual (`is_special_date=True`). Se o feriado não tiver arquivo físico ou se for dia normal com catálogo vazio, aplica fallback gracioso para o castelo clássico (`castelo_panoramica_v2.jpg`). O renderizador `render_bento_email()` é conectado ao seletor, passando a renderizar dinamicamente o banner e a legenda sem quebrar assinaturas legadas.

**Blocked by:**
None (pode iniciar imediatamente)

**Status:**
ready-for-agent

**Files to modify:**
- `assets/banners/manifesto.json` *(novo)*
- `src/delivery/banner_selector.py` *(novo)*
- `src/delivery/renderer.py`
- `src/delivery/__init__.py`
- `tests/test_banner_selector.py` *(novo)*
- `tests/test_renderer.py`

**Acceptance criteria:**
- [ ] `assets/banners/manifesto.json` criado com suporte a feriados fixos (`MM-DD`), móveis (`YYYY-MM-DD`) e `legenda_padrao`.
- [ ] Módulo `src/delivery/banner_selector.py` implementado com dataclass `BannerInfo(banner_url, full_hd_url, caption, is_special_date, filename)` e função read-only `resolver_banner_do_dia(data_envio, banners_dir, manifesto_path)`.
- [ ] Hierarquia de 3 Tiers respeitada: Tier 1 (Feriado com arquivo físico) ➔ Tier 2 (Catálogo geral disponível) ➔ Tier 3 (Castelo clássico de segurança `castelo_panoramica_v2.jpg`).
- [ ] Suporte à absorção de arquivos físicos adicionais na pasta de banners aplicando a `legenda_padrao` quando não listados no manifesto.
- [ ] `render_bento_email(md_text, data_envio=None)` consome `resolver_banner_do_dia()` em modo somente leitura, preservando a assinatura e o comportamento das chamadas legadas sem argumentos.
- [ ] Testes unitários herméticos em `tests/test_banner_selector.py` cobrindo:
  - Seleção de feriado fixo (`10-31`) com arquivo físico presente.
  - Seleção de feriado móvel (`2026-02-17`) com arquivo físico presente.
  - Degradação de feriado sem arquivo físico para o castelo clássico.
  - Degradação de manifesto inválido/corrompido para o castelo clássico.
  - Degradação de pasta de banners ausente ou vazia para o castelo clássico.
- [ ] Teste em `tests/test_renderer.py` comprovando que o HTML renderiza a URL e legenda dinâmicas resolvidas para o dia.
- [ ] Execução dos novos testes e da suíte completa de regressão (`python -m unittest discover tests -v`) com 100% de aprovação ao término do ticket.
- [ ] Demonstração: Execução de teste gerando preview com data de Halloween exibe o banner de Halloween; execução com data regular em pasta vazia exibe o castelo clássico.
