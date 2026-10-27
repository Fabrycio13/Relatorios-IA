# 2. Coleta no X (Twitter) via Playwright Headless com Sessão Persistente

## Contexto
O monitoramento de perfis de referência (Radar VIP) e do feed no X é essencial para a curadoria técnica diária. A API oficial do X (v2) possui planos pagos com custos elevados para projetos individuais/pequenos times e restrições severas de endpoints para leitura de feeds cronológicos de contas seguidas.

## Decisão
Implementamos a ingestão do X através de um robô **Playwright** rodando Chromium em modo headless com injeção de cookies de autenticação (`auth_token` e `ct0`) e armazenamento de contexto persistente em diretório local (`.session/`), com script auxiliar de renovação interativa (`scripts/login_x.py`).

## Consequências
- **Positivas**: Custo zero de API para coleta de dados públicos de perfis e timeline; acesso direto ao feed completo em linguagem natural; scraping rápido e resiliente.
- **Trade-offs**: Fragilidade diante de mudanças no DOM ou alterações nos seletores HTML do X; necessidade de renovar cookies periodicamente caso a sessão expire; necessidade de gerenciar o ciclo de vida do processo Chromium headless.
