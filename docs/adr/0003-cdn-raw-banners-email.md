# 3. CDN Raw Serving para Banners de E-mail via Repositório Público no GitHub

## Contexto
O layout Bento Grid utiliza banners visuais estáticos no cabeçalho e rodapé do e-mail. A anexação direta de imagens como partes MIME multipart (com referências `cid:`) aumenta o tamanho da mensagem para mais de 10 MB, aciona filtros de spam corporativos e faz com que clientes como o Gmail exibam botões de anexo e avisos de download de mídia.

## Decisão
Hospedamos os arquivos de imagem na pasta `assets/` do próprio repositório público do GitHub e os referenciamos no HTML via URL direta do CDN Raw (`raw.githubusercontent.com/...`), adicionando parâmetros de query string para invalidação de cache (`?v=YYYYMMDD`).

## Consequências
- **Positivas**: Mensagem de e-mail ultra leve (~15 KB de payload HTML); zero anexos aparentes na interface do Gmail e Outlook; renderização imediata com carregamento assíncrono pelo cliente de e-mail.
- **Trade-offs**: Exige que as imagens estejam publicadas no repositório público do GitHub no branch principal; clientes de e-mail com bloqueio agressivo de imagens externas exigem que o usuário autorize a exibição na primeira leitura.
