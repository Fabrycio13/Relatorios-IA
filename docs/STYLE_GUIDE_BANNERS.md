# 🎨 Guia de Estilo & Prompt Playbook para Banners de IA (The Engineering Gazette)

Este documento define o **padrão estético visual, os parâmetros técnicos e o playbook de prompts** para geração do catálogo de imagens de cabeçalho do jornal *The Engineering Gazette*. Todas as artes (tanto de feriados comemorativos quanto do catálogo rotativo regular) devem seguir rigorosamente estas diretrizes para preservar a coerência visual de gravura clássica de época.

---

## 1. O DNA Visual da Imagem Âncora

A referência máxima de padrão estético do projeto é a arte clássica do castelo (`assets/castelo_panoramica_v2.jpg`). Qualquer nova imagem deve parecer ter sido desenhada pelo mesmo ilustrador e impressa na mesma prensa tipográfica do século XIX.

```
+-----------------------------------------------------------------------------------+
|  ESTILO: Gravura em placa de cobre (Copperplate Steel Engraving / Etching)        |
|  TRAÇO: Hachuras finas cruzadas (Cross-hatching), linhas limpas, alta densidade   |
|  ILUMINAÇÃO: Dramática clássica (Chiaroscuro), raios de luz suaves volumétricos   |
|  PALETA: Sépia envelhecido, pergaminho marfim, tinta ferrogálica preta/grafite    |
|  ATMOSFERA: Arquitetura monumental fantástica combinada a engenharia de software |
+-----------------------------------------------------------------------------------+
```

### Elementos Mandatórios (O que SEMPRE deve estar presente):
* **Textura de Prensa Impressa:** Sensação tátil de papel de algodão envelhecido, textura de matriz de metal ou xilogravura fina.
* **Monumentalidade e Perspectiva Panorâmica:** Planos amplos, estruturas arquitetônicas grandiosas (castelos, torres, forjas, aquedutos de dados, pontes gigantescas) que transmitam a escala da engenharia de IA.
* **Nitidez Extrema nas Linhas:** Cada detalhe estrutural (janelas, engrenagens, tijolos, cabos de cobre arcaicos, pergaminhos) deve ser nítido e bem definido, sem borrões ou gradientes plásticos modernos.

### Elementos Vetados (O que NUNCA deve aparecer):
* ❌ Renderização 3D moderna (CGI plástico, Unreal Engine 5 glossy, estilo videogame).
* ❌ Cores neon estridentes, brilhos holográficos ou cyberpunk moderno (magenta/ciano saturados).
* ❌ Fotorealismo fotográfico moderno (câmeras DSLR, bokeh excessivo, lentes contemporâneas).
* ❌ Textos ilegíveis, caracteres distorcidos ou pseudo-palavras geradas por IA.
* ❌ Bordas decorativas circulares ou molduras embutidas (a moldura de gravura é gerada pelo próprio CSS do e-mail).

---

## 2. Parâmetros Técnicos de Exportação

| Parâmetro | Requisito Obrigatório | Motivo / Impacto |
| :--- | :--- | :--- |
| **Dimensões Finais** | `1360 x 760 pixels` | Exata proporção ~16:9 panorâmica do layout com densidade **2x Retina** para e-mails |
| **Largura de Exibição no E-mail** | `680 pixels` (max-height: 380px) | Garantia de nitidez microscópica em telas 4K, iPhones e displays de alta densidade |
| **Formato de Arquivo** | `JPEG (.jpg)` | Máxima compatibilidade com Gmail, Outlook, Apple Mail e Thunderbird |
| **Compressão / Peso** | Entre `150 KB` e `280 KB` | Carregamento instantâneo no cliente de e-mail sem engasgar o leitor |
| **Espaço de Cor** | `sRGB` | Cores consistentes em navegadores e monitores de qualquer fabricante |
| **Localização dos Arquivos** | `assets/banners/<nome_arquivo>.jpg` | Servido via CDN do GitHub com anti-cache previsível |

---

## 3. Template do Prompt Mestre (Playbook de Geração)

Copie e cole a estrutura abaixo no gerador de sua preferência (**Midjourney v6**, **Flux.1 Schnell/Dev**, **DALL-E 3** ou **Recraft.ai**).

### 3.1 Prompt Estrutural Base (Inglês para Máxima Fidelidade na IA)

```text
A panoramic vintage newspaper steel engraving, classical 19th-century copperplate etching in the style of Albrecht Dürer and Gustave Doré. [SUA CENA / TEMA ESPECÍFICO AQUI]. Intricate ultra-fine cross-hatching, highly detailed architectural linework, antique ivory parchment paper texture, dark iron-gall ink monochrome with subtle warm sepia undertones. Grand monumental scale, dramatic chiaroscuro atmospheric lighting, clean etching details, sharp focus, museum archival quality, wide angle panoramic composition --ar 16:9 --style raw
```

### 3.2 Prompt Negativo (Evita desvios estéticos)

```text
photograph, 3d render, cgi, plastic, glossy, neon colors, digital painting blur, modern cyberpunk, oversaturated, text, watermark, signature, framing border, low resolution, noisy artifacts, deformed perspective
```

---

## 4. Mapeamento de Feriados & Datas Comemorativas (Fase 1)

Abaixo estão as datas mapeadas, os nomes de arquivo padronizados para o `manifesto.json`, a legenda sugerida e o prompt pronto para cada celebração:

---

### 🎃 1. Halloween / Dia das Bruxas (`10-31`)
* **Arquivo:** `assets/banners/halloween.jpg`
* **Legenda:** *"Edição Especial de Halloween: Os fantasmas dos bugs esquecidos em produção e os cemitérios de dependências obsoletas."*
* **Prompt Específico:**
  ```text
  A panoramic vintage newspaper steel engraving of a grand gothic stone castle shrouded in dense twilight mist and autumn fog, twisted ancient bare oak trees with subtle spiderwebs, carved jack-o'-lanterns softly illuminating old cobblestone castle ramparts, miniature clockwork mechanical bats flying near tall spires, eerie atmospheric chiaroscuro lighting, intricate 19th-century cross-hatching, sepia and antique ivory etching, sharp linework, wide panoramic composition --ar 16:9
  ```

---

### 🎄 2. Véspera e Dia de Natal (`12-24` e `12-25`)
* **Arquivo:** `assets/banners/natal.jpg`
* **Legenda:** *"Edição Especial de Natal: A grande oficina dos agentes em recesso, arquiteturas de IA em repouso e paz na branch main."*
* **Prompt Específico:**
  ```text
  A panoramic vintage newspaper steel engraving of a monumental snow-covered stone citadel and clocktower in mid-winter, delicate architectural snow on slate roofs and castle battlements, warm glowing lantern light emanating from large arched library windows, festive evergreen pine garlands hung on stone balustrades, gentle falling snowflakes, intricate Victorian cross-hatching, warm antique sepia ink, sharp detailed etching --ar 16:9
  ```

---

### 🎆 3. Véspera e Ano Novo (`12-31` e `01-01`)
* **Arquivo:** `assets/banners/ano_novo.jpg`
* **Legenda:** *"Edição Especial de Ano Novo: Novos paradigmas, arquiteturas limpas e a celebração dos marcos alcançados na engenharia de agentes."*
* **Prompt Específico:**
  ```text
  A panoramic vintage newspaper steel engraving of a majestic grand observatory and cathedral of engineering at midnight, magnificent celestial vintage fireworks illuminating the night sky above monumental domes and stone arches, intricate astronomical brass astrolabes, clean fine cross-hatching, deep ink tones with luminous parchment contrasts, dramatic festive historical composition --ar 16:9
  ```

---

### 🎭 4. Carnaval (`02-17` - Móvel)
* **Arquivo:** `assets/banners/carnaval.jpg`
* **Legenda:** *"Edição Especial de Carnaval: A folia dos dados sintéticos e a dança sincronizada de múltiplos agentes em produção."*
* **Prompt Específico:**
  ```text
  A panoramic vintage 19th-century newspaper copperplate engraving of a grand festive Venetian masquerade ball inside a colossal stone amphitheater and palace, baroque automata and ornate brass mechanical figures wearing elaborate historical carnival masks, flowing festive banners and ribbons draped from marble columns, intricate etching linework, sepia and ivory tones --ar 16:9
  ```

---

### 🇧🇷 5. Tiradentes (`04-21`)
* **Arquivo:** `assets/banners/tiradentes.jpg`
* **Legenda:** *"Edição Especial de Tiradentes: A liberdade do código open-source e a coragem de quebrar os monopólios proprietários de IA."*
* **Prompt Específico:**
  ```text
  A panoramic vintage historical engraving of colonial Brazilian baroque architecture, grand stone mansions and stone churches with bell towers in 18th-century Ouro Preto, dramatic mountainous landscape in the background, morning sunlight cutting through misty valleys, antique archival etching, deep ink cross-hatching, noble historical tone --ar 16:9
  ```

---

### 🛠️ 6. Dia do Trabalho (`05-01`)
* **Arquivo:** `assets/banners/trabalho.jpg`
* **Legenda:** *"Edição Especial do Dia do Trabalhador: Homenagem aos engenheiros de software, compiladores e agentes que mantêm o mundo funcionando."*
* **Prompt Específico:**
  ```text
  A panoramic vintage newspaper steel engraving of a colossal 19th-century industrial forge and engineering workshop, heroic craftsmen and monumental waterwheels, giant brass gears, architectural iron arches, steam rising softly towards grand vaulted glass ceilings, Gustave Doré industrial etching style, intricate linework, antique sepia --ar 16:9
  ```

---

### 🇧🇷 7. Independência do Brasil (`09-07`)
* **Arquivo:** `assets/banners/independencia.jpg`
* **Legenda:** *"Edição Especial da Independência: A soberania de construir e hospedar nossa própria inteligência computacional."*
* **Prompt Específico:**
  ```text
  A panoramic historical steel engraving depicting a monumental colonial palace and expansive river valley under a radiant sunrise, fluttering historical banners, majestic palm trees framing neoclassical stone facades, intricate cross-hatching, noble and triumphant composition, 19th-century Brazilian empire architectural engraving --ar 16:9
  ```

---

### 👑 8. Proclamação da República (`11-15`)
* **Arquivo:** `assets/banners/republica.jpg`
* **Legenda:** *"Edição Especial da República: O poder distribuído da comunidade e o avanço da computação pública e auditável."*
* **Prompt Específico:**
  ```text
  A panoramic vintage newspaper engraving of a classical neoclassical civic square with grand columned parliament palaces, statues of wisdom and science, antique streetlamps and wide stone promenades, crisp architectural linework, formal 19th-century gazette illustration, sharp etching details --ar 16:9
  ```

---

### ✊ 9. Dia da Consciência Negra (`11-20`)
* **Arquivo:** `assets/banners/consciencia_negra.jpg`
* **Legenda:** *"Edição Especial da Consciência Negra: Resiliência, diversidade e a força das ideias que transformam a tecnologia e a história."*
* **Prompt Específico:**
  ```text
  A panoramic historical engraving of a proud mountainous quilombo and majestic ancient baobab tree overlooking an expansive valley at dawn, grand natural stone bastions, powerful atmospheric sunbeams, intricate organic and architectural linework in antique steel engraving style, noble and resilient aesthetic --ar 16:9
  ```

---

## 5. Catálogo de Ideias de IA para o Pool Rotativo Geral (Fase 2)

Para alimentar as 100 a 200 imagens do ciclo regular, utilize temas inspirados na metáfora arquitetônica da Engenharia de Software e IA:

1. **A Torre do Contexto Infinito:** Uma colossal torre espiral de pedra e pergaminhos que toca as nuvens.
2. **A Grande Forja dos Compiladores:** Oficinas mecânicas gigantes com engrenagens forjando código determinístico.
3. **O Aqueduto dos Vetores:** Pontes de pedra monumentais canalizando rios de dados luminosos.
4. **O Arquivo de Alexandria Digital:** Uma biblioteca infinita com arcos góticos e escadas rolantes mecânicas de livros técnicos.
5. **A Cidadela dos Agentes Autônomos:** Uma cidade fortificada com múltiplos observatórios cooperando em rede.
6. **O Laboratório de Avaliações (Evals):** Balanças gigantescas de latão pesando precisão e latência sob a luz de vitrais.
7. **A Ponte do Desacoplamento:** Uma monumental ponte pênsil de pedra e cabos conectando duas montanhas de código.
8. **O Relógio do Determinismo:** Uma torre de relógio astronômico do século XIX com milhares de pêndulos e engrenagens perfeitas.
9. **A Mina de Pesquisa:** Engenheiros em cavernas gigantescas extraindo blocos de cristal de conhecimento científico.
10. **A Oficina de Sandboxing:** Uma câmara de ferro reforçada com escotilhas e válvulas contendo experimentos seguros de agentes.

---

## 6. Checklist de Curadoria e Aprovação Humana

Antes de adicionar qualquer imagem gerada ao diretório `assets/banners/`, confira os 5 critérios eliminatórios:

* [ ] **1. Textura:** O estilo parece com uma gravura impressa em papel antigo de jornal (sem traços plásticos 3D)?
* [ ] **2. Proporção:** A imagem está estritamente em `1360 x 760 pixels` (proporção panorâmica ~16:9)?
* [ ] **3. Nitidez:** Em zoom de 100%, os traços finos estão nítidos e bem definidos?
* [ ] **4. Ausência de Letras:** Não há palavras falsas, letras ilegíveis ou assinaturas da IA no rodapé?
* [ ] **5. Manifesto Atualizado:** A imagem foi registrada no `assets/banners/manifesto.json` com sua legenda correspondente?
