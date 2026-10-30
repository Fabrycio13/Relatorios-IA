# 12: Links em Alta Resolução, Integração CLI, Style Guide Gate e Checkpoint de Regressão

**What to build:**
Concluir a experiência do usuário integrando o link interativo de alta resolução (1360x760) no HTML do e-mail Bento Grid, apontando diretamente para o arquivo público da imagem do dia no GitHub. Integrar formalmente a resolução de banners no pipeline CLI oficial (`main.py --preview` e `main.py --step email --preview`), assegurando conformidade estrita com o contrato operacional do Windows Task Scheduler (`sys.exit(0/1/2)`) e zero alterações na trava diária. Formalizar o portão de qualidade do Style Guide como requisito de ativação para a inclusão de imagens reais na pasta de produção `assets/banners/`.

**Blocked by:**
11: Catálogo Rotativo sem Repetição, Persistência Atômica e Ciclo de Vida Pós-Envio

**Status:**
ready-for-agent

**Files to modify:**
- `src/delivery/renderer.py`
- `src/core/config.py`
- `tests/test_delivery_integration.py`
- `tests/test_renderer.py`

**Acceptance criteria:**
- [ ] A tag `<a>` que envolve o banner no layout Bento Grid aponta dinamicamente para a URL em alta resolução (1360x760) da imagem específica do dia no repositório GitHub.
- [ ] O atributo `title` do link e o `alt` da imagem refletem dinamicamente o tema do banner selecionado (comemorativo ou geral).
- [ ] A execução de `python main.py --preview` (e `python main.py --step email --preview`) renderiza o layout com o banner dinâmico do dia em `reports/preview.html` e dispara o navegador sem conectar à rede SMTP e sem tocar em `data/ultimo_envio.txt`.
- [ ] Portão de Ativação de Produção (Style Guide Gate): Fica estabelecido como critério de aceitação de produto que nenhuma imagem real entra na pasta de produção `assets/banners/` sem validação prévia humana contra o checklist de 5 critérios do `docs/STYLE_GUIDE_BANNERS.md` (textura de gravura clássica, 1360x760, proporção 16:9, nitidez e ausência de textos corrompidos).
- [ ] Distinção formal de validação: os testes automatizados utilizam fixtures temporárias herméticas; a validação da beleza artística e conformidade visual das imagens reais de feriados/catálogo é auditada pelo Style Guide antes do commit.
- [ ] Contratos operacionais CLI preservados:
  - `sys.exit(0)` em caso de preview ou sucesso.
  - `sys.exit(1)` em caso de falha crítica de execução.
  - `sys.exit(2)` em caso de timeout de rede (se aplicável).
- [ ] Preservação de compatibilidade retroativa: todas as assinaturas públicas de `render_bento_email()`, `despachar_relatorio()` e `EmailDeliveryChannel` continuam 100% compatíveis com o código existente.
- [ ] Execução da suíte completa de testes de regressão do repositório (`python -m unittest discover tests -v`) com 100% de aprovação (todos os 99+ testes legados + todos os novos testes de banners).
- [ ] Demonstração: Execução de `python main.py --preview` na CLI gera `reports/preview.html` com o banner dinâmico e o link de alta resolução operando visualmente.
