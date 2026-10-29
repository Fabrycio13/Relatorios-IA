# Especificação Técnica 0005: Sistema de Banners Rotativos e Comemorativos

**Status:** Aprovado para implementação  
**Área:** Entrega, Identidade Visual & Renderização Bento Grid  
**Prerequisitos:** Specs 0001–0004 concluídas (PRs #1 a #5 integradas na `main`)  
**Documento Complementar:** [`docs/STYLE_GUIDE_BANNERS.md`](../STYLE_GUIDE_BANNERS.md)

---

## 1. Problem Statement

Atualmente, o e-mail diário (*The Engineering Gazette*) utiliza uma única imagem estática fixa no topo da edição (`assets/castelo_panoramica_v2.jpg`) acompanhada da mesma legenda em todas as edições:
> *"O Castelo da Engenharia de Agentes: Panorama da fronteira de desenvolvimento em IA contemporânea."*

Embora a imagem original tenha estabelecido com sucesso a estética e o padrão de gravura clássica de jornal, a sua repetição diária contínua traz limitações para a experiência do leitor:

1. **Monotonia Visual:** Leitores diários deixam de notar a área principal de imagem devido à repetição estática da mesma arte todos os dias.
2. **Ausência de Contexto Sazonal/Comemorativo:** Em feriados ou datas de alta relevância (ex: Halloween, Natal, Ano Novo, Carnaval, datas históricas nacionais), o cabeçalho não celebra nem reflete a ocasião com uma releitura temática alinhada ao universo de IA e engenharia.
3. **Inviabilidade Operacional de Geração em Tempo Real:** Tentar gerar uma nova imagem via API (DALL-E, Midjourney, Flux) todo dia às 08:00 no horário de disparo acarretaria riscos severos de confiabilidade: latência adicional imprevisível (30-60s), custos contínuos de chamada, falhas de conectividade e o perigo iminente de quebra de nitidez e textura (alucinação de estilos fora do padrão de gravura).

---

## 2. Solution

Implementar um **Sistema de Banners Rotativos e Comemorativos Pré-curados**, com seleção determinística inteligente, suporte a datas comemorativas prioritárias via manifesto leve, máquina de estados de ciclo sem repetição e fallback de segurança 100% resiliente:

1. **Hierarquia de Seleção em 3 Tiers (Precedência Estrita):**
   - **Tier 1 (Comemorativo):** Se a data coincidir com um feriado mapeado (fixo `"MM-DD"` ou móvel `"YYYY-MM-DD"`) E o arquivo físico existir em `assets/banners/`, seleciona prioritariamente a arte temática e sua legenda contextual (`is_special_date=True`).
   - **Tier 2 (Catálogo Geral por Exaustão):** Se não for feriado (ou se a imagem do feriado não existir), seleciona a próxima imagem não consumida do catálogo rotativo regular.
   - **Tier 3 (Castelo Clássico de Segurança):** Se a pasta estiver vazia, faltarem imagens ou ocorrer erro catastrófico de I/O, utiliza o castelo atual (`castelo_panoramica_v2.jpg`) e a legenda institucional clássica.
2. **Máquina de Estados de Rotação sem Repetição (`data/historico_banners.json`):**
   - Controla o conjunto de imagens consumidas no ciclo corrente. Nenhuma imagem é repetida até que todas as imagens físicas disponíveis em `assets/banners/` tenham sido exibidas.
   - **Inserção dinâmica no meio do ciclo:** Imagens adicionadas a qualquer momento entram no conjunto de não consumidas e são exibidas antes que o ciclo resete.
   - **Gravação atômica:** Persistência segura em arquivo temporário (`historico_banners.json.tmp`) seguido de substituição atômica (`os.replace`).
3. **Ciclo de Vida do Envio e Modo `--preview` Read-Only:**
   - O modo `--preview` (e qualquer renderização local) é **estritamente somente leitura**: resolve a imagem do dia para exibição, mas **nunca grava** em disco nem consome itens da fila do ciclo.
   - O avanço do ciclo e registro da imagem no histórico ocorrem **exclusivamente após o despacho de e-mail bem-sucedido** no `main.py` (`args.step in ["all", "email"]` e `not args.preview`).
   - Se o envio SMTP falhar, o histórico não é consumido. Reexecuções no mesmo dia com `--force` reutilizam a mesma imagem já atribuída àquela data.
4. **Descoberta Automática de Arquivos + Manifesto de Legendas (`manifesto.json`):**
   - O seletor escaneia os arquivos físicos `.jpg` em `assets/banners/`.
   - Se a imagem estiver listada em `catalogo_geral` no `manifesto.json`, usa sua legenda contextual personalizada.
   - Se a imagem for um arquivo novo colocado na pasta sem cadastro no manifesto, ela é absorvida no pool rotativo recebendo a `legenda_padrao` do manifesto (crescimento incremental zero-config).
5. **Portão de Ativação de Produção (Style Guide):**
   - A capacidade de descoberta automática de arquivos **não contorna** o controle de qualidade: somente imagens previamente validadas pelo checklist de 5 critérios do [`docs/STYLE_GUIDE_BANNERS.md`](../STYLE_GUIDE_BANNERS.md) (1360x760, traço nítido, gravura de jornal, sem textos corrompidos) têm permissão de entrar na pasta `assets/banners/` de produção.
6. **Alta Resolução Interativa:**
   - O clique no banner do e-mail abre diretamente a URL em alta resolução (1360x760) daquela imagem específica do dia hospedada no repositório GitHub (`assets/banners/<arquivo>.jpg`), preservando a interatividade.

---

## 3. User Stories

1. **Como leitor do diário de IA**, quero ver uma imagem comemorativa temática no topo do e-mail em datas especiais (como Halloween, Natal, Ano Novo ou Carnaval), para que a edição pareça viva, contextual e comemorativa.
2. **Como leitor do diário de IA**, quero que cada arte especial possua uma legenda contextual criativa, para compreender a narrativa técnica ou satírica por trás da ilustração daquele dia.
3. **Como leitor assíduo**, quero ver ilustrações diferentes a cada dia regular sem repetições da mesma imagem até que todas tenham sido utilizadas, tornando a abertura do e-mail uma experiência visual renovada.
4. **Como leitor em telas Retina e mobile de alta densidade**, quero que todas as imagens apresentem traços finos, textura nítida de gravura e resolução 1360x760 (Retina 2x), para que a leitura seja elegante e sem borrões visuais.
5. **Como leitor que clica na imagem para ver detalhes**, quero abrir a versão de alta resolução daquela arte específica do dia, para inspecionar os detalhes arquitetônicos e elementos visuais da gravura.
6. **Como curador do jornal**, quero poder adicionar novas imagens aprovadas à pasta `assets/banners/` a qualquer momento, sabendo que o sistema as absorverá no ciclo corrente sem duplicar imagens recém-vistas.
7. **Como desenvolvedor executando `--preview`**, quero visualizar a prévia do e-mail localmente sem que isso avance a fila de banners nem altere o histórico de produção.
8. **Como engenheiro de operação**, quero que o pipeline matinal continue rodando em menos de 5 segundos na etapa de renderização, sem depender de chamadas síncronas a APIs externas de geração de imagem.
9. **Como operador do sistema**, quero que qualquer erro de I/O, arquivo corrompido ou manifesto faltante acione um fallback silencioso para o castelo clássico, garantindo que o relatório seja entregue sem exceções no agendador.
10. **Como desenvolvedor**, quero testar hermeticamente a seleção de feriados, a rotação sequencial, a gravação atômica e os cenários de fallback sem tocar em arquivos de produção nem conectar à internet.

---

## 4. Implementation Decisions

### 4.1 Módulo Seletor de Banners (`src/delivery/banner_selector.py`)

Criar o módulo desacoplado dedicado à resolução do banner do dia:

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass(frozen=True)
class BannerInfo:
    """Metadados do banner selecionado para renderização no e-mail."""
    banner_url: str
    full_hd_url: str
    caption: str
    is_special_date: bool
    filename: str

def resolver_banner_do_dia(
    data_envio: datetime | None = None,
    banners_dir: Path | None = None,
    manifesto_path: Path | None = None,
    historico_path: Path | None = None,
    commit_historico: bool = False
) -> BannerInfo:
    """Resolve o banner correspondente à data de envio respeitando a hierarquia de 3 Tiers.
    Por padrão opera em modo somente leitura (commit_historico=False).
    """
    ...

def confirmar_banner_utilizado(
    data_envio: datetime | None = None,
    banners_dir: Path | None = None,
    manifesto_path: Path | None = None,
    historico_path: Path | None = None
) -> None:
    """Executado exclusivamente após envio SMTP com sucesso para persistir atomicamente o uso."""
    ...
```

### 4.2 Estrutura do Manifesto (`assets/banners/manifesto.json`)

Suporta feriados anuais fixos (`MM-DD`) e feriados móveis específicos de cada ano (`YYYY-MM-DD`):

```json
{
  "versao": "1.0",
  "legenda_padrao": "Crônicas da Engenharia de Agentes: Panorama diário da fronteira de desenvolvimento em IA contemporânea.",
  "feriados": {
    "10-31": {
      "arquivo": "halloween.jpg",
      "legenda": "Edição Especial de Halloween: Os fantasmas dos bugs em produção e os cemitérios de dependências abandonadas."
    },
    "12-25": {
      "arquivo": "natal.jpg",
      "legenda": "Edição Especial de Natal: A oficina dos agentes em recesso e a paz na branch main."
    },
    "01-01": {
      "arquivo": "ano_novo.jpg",
      "legenda": "Edição Especial de Ano Novo: Novos paradigmas, refatorações ambiciosas e o futuro da inteligência artificial."
    },
    "2026-02-17": {
      "arquivo": "carnaval.jpg",
      "legenda": "Edição Especial de Carnaval: A folia dos dados sintéticos e a dança de múltiplos agentes em produção."
    }
  },
  "catalogo_geral": [
    {
      "arquivo": "banner_001.jpg",
      "legenda": "O Castelo da Engenharia de Agentes: Panorama da fronteira de desenvolvimento em IA contemporânea."
    },
    {
      "arquivo": "banner_002.jpg",
      "legenda": "A Forja dos Compiladores: Onde modelos fundacionais encontram a rigidez de execução determinística."
    }
  ]
}
```

### 4.3 Estrutura do Histórico Atômico (`data/historico_banners.json`)

```json
{
  "versao": "1.0",
  "imagens_consumidas_no_ciclo": [
    "banner_001.jpg",
    "banner_002.jpg"
  ],
  "ultimo_envio_por_data": {
    "2026-10-28": "banner_001.jpg",
    "2026-10-29": "banner_002.jpg"
  }
}
```

### 4.4 Política de Falha e Reconciliação com `ultimo_envio.txt`
* Não se promete transação distribuída de duas fases (2PC) entre servidor SMTP remoto e sistema de arquivos local.
* Se o envio SMTP for concluído com sucesso, mas a gravação de `historico_banners.json` falhar (ex: disco cheio), o sistema registrará um aviso em log. Em uma reexecução posterior na mesma data (detectada via `ultimo_envio.txt`), o reconciliador reatribui com segurança o mesmo banner sem corromper o ciclo.
* A trava diária de envio (`data/ultimo_envio.txt`) continua sendo a guardiã única contra envios duplicados por concorrência de processos.

### 4.5 Integração no Renderizador Bento Grid (`src/delivery/renderer.py`)
* Atualizar a função `render_bento_email`:
  ```python
  def render_bento_email(
      md_text: str,
      data_envio: datetime | None = None
  ) -> str:
  ```
* Se `data_envio` não for informado, assume `datetime.now()`.
* Chama `resolver_banner_do_dia(data_envio=data_envio, commit_historico=False)` garantindo renderização estritamente read-only.
* Substitui os placeholders fixos `{HEADER_BANNER_URL}`, `{HEADER_FULL_HD_URL}` e a legenda estática pelos valores dinâmicos de `BannerInfo`.

---

## 5. Testing Decisions

* **Isolamento Total:** Os testes **nunca** farão conexões de rede para o GitHub nem dependerão de credenciais reais ou arquivos de produção.
* **Uso Obrigatório de `tempfile.TemporaryDirectory`:** Todas as fixtures de teste (arquivos `.jpg` simulados, manifestos de teste e arquivos de histórico) são instanciadas em pastas temporárias descartáveis.
* **Cenários Obrigatórios de Teste:**
  1. *Feriado Mapeado:* Data coincide com chave de feriado fixo (`MM-DD`) ou móvel (`YYYY-MM-DD`) -> retorna o banner comemorativo com `is_special_date=True`.
  2. *Feriado sem arquivo físico:* Feriado mapeado no JSON, mas o `.jpg` não existe em disco -> degrada graciosamente para o catálogo geral (Tier 2) ou castelo (Tier 3).
  3. *Rotação e Exaustão do Pool:* Catálogo de N fotos -> consome sequencialmente sem repetição; no dia N+1 o ciclo é resetado.
  4. *Adição Dinâmica no Meio do Ciclo:* Nova foto adicionada após consumo parcial -> nova foto é consumida no ciclo corrente antes do reset.
  5. *Idempotência com `--force`:* Execuções múltiplas para a mesma data retornam exatamente a mesma imagem.
  6. *Isolamento de `--preview`:* Execução de preview não cria nem altera `historico_banners.json`.
  7. *Gravação Atômica e Recuperação de Corrupção:* JSON de histórico inválido ou ausente -> recupera em memória sem lançar exceções.
  8. *Integração no Layout HTML:* `render_bento_email` renderiza a URL do banner dinâmico e a legenda correspondente no HTML final.
* **Execução Obrigatória por Ticket:** A suíte de testes de regressão (`python -m unittest discover tests -v`) deve ser executada e aprovada com 100% de sucesso ao término de cada ticket.

---

## 6. Out of Scope

* Geração síncrona ou em tempo real de imagens via API da OpenAI/Midjourney durante o pipeline das 08:00.
* Download automático de imagens da internet durante o envio de e-mail.
* Edição binária ou redimensionamento de imagens em tempo de execução via Pillow/OpenCV (todas as imagens devem ser pré-processadas e otimizadas em 1360x760 antes de serem commitadas).

---

## 7. Further Notes

* Rastreabilidade formal:
  - **Spec 0005** ➔ **Ticket 10** ➔ `tests/test_banner_selector.py` (Feriados, 3 Tiers, Fallback & Renderer Read-Only)
  - **Spec 0005** ➔ **Ticket 11** ➔ `tests/test_banner_rotation.py` (Ciclo sem Repetição, Gravação Atômica, Ciclo de Vida Pós-Envio)
  - **Spec 0005** ➔ **Ticket 12** ➔ `tests/test_delivery_integration.py` & Suíte Geral (Links HD, CLI Preview, Style Guide Gate)
