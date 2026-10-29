"""Seletor de Banners do Diário de IA (The Engineering Gazette).

Responsável por resolver o banner do cabeçalho da edição com base na
hierarquia estrita de 3 Tiers (Spec 0005):
  - Tier 1: Feriado comemorativo (fixo ou móvel) com arquivo físico presente.
  - Tier 2: Catálogo geral rotativo disponível (com legendas do manifesto ou padrão).
  - Tier 3: Fallback de segurança para o Castelo Clássico (castelo_panoramica_v2.jpg).
"""

from dataclasses import dataclass
from datetime import datetime
import json
import logging
from pathlib import Path

from src.core.config import HEADER_BANNER_URL, HEADER_FULL_HD_URL

logger = logging.getLogger(__name__)

DEFAULT_BANNER_FILENAME = "castelo_panoramica_v2.jpg"
DEFAULT_BANNER_CAPTION = (
    "O Castelo da Engenharia de Agentes: Panorama da fronteira de desenvolvimento em IA contemporânea."
)
GITHUB_RAW_BANNERS_BASE = (
    "https://raw.githubusercontent.com/Fabrycio13/Relatorios-IA/main/assets/banners"
)


@dataclass(frozen=True)
class BannerInfo:
    """Metadados do banner selecionado para renderização no e-mail."""
    banner_url: str
    full_hd_url: str
    caption: str
    is_special_date: bool
    filename: str


def _fallback_castelo_classico() -> BannerInfo:
    """Retorna o banner do castelo clássico garantindo resiliência operacional absoluta."""
    return BannerInfo(
        banner_url=HEADER_BANNER_URL,
        full_hd_url=HEADER_FULL_HD_URL,
        caption=DEFAULT_BANNER_CAPTION,
        is_special_date=False,
        filename=DEFAULT_BANNER_FILENAME
    )


def resolver_banner_do_dia(
    data_envio: datetime | None = None,
    banners_dir: Path | None = None,
    manifesto_path: Path | None = None
) -> BannerInfo:
    """Resolve o banner correspondente à data de envio respeitando a hierarquia de 3 Tiers.

    Executa em modo estritamente somente leitura (read-only), sem alterar estado ou arquivos.
    """
    if data_envio is None:
        data_envio = datetime.now()

    if banners_dir is None:
        banners_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "banners"

    if manifesto_path is None:
        manifesto_path = banners_dir / "manifesto.json"

    # Se o diretório base não existir, faz fallback imediato para o Tier 3
    if not banners_dir.exists() or not banners_dir.is_dir():
        return _fallback_castelo_classico()

    # Leitura segura do manifesto
    manifest_data = {}
    if manifesto_path.exists() and manifesto_path.is_file():
        try:
            manifest_data = json.loads(manifesto_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Aviso ao ler manifesto de banners ({manifesto_path}): {e}. Prosseguindo com fallback.")
            return _fallback_castelo_classico()

    # Valida defensivamente que a raiz do JSON é um objeto (dicionário)
    if not isinstance(manifest_data, dict):
        logger.warning(f"Aviso: Manifesto de banners ({manifesto_path}) não é um objeto JSON válido. Prosseguindo com fallback.")
        return _fallback_castelo_classico()

    legenda_padrao = manifest_data.get("legenda_padrao", DEFAULT_BANNER_CAPTION)
    feriados = manifest_data.get("feriados", {})

    # =========================================================================
    # TIER 1: Verificação de Feriado Comemorativo (Fixo ou Móvel)
    # =========================================================================
    chave_movel = data_envio.strftime("%Y-%m-%d")
    chave_fixa = data_envio.strftime("%m-%d")

    # Precedência: busca primeiro feriado móvel (ano específico), depois anual fixo
    feriado_entry = feriados.get(chave_movel) or feriados.get(chave_fixa)

    if feriado_entry and isinstance(feriado_entry, dict):
        arquivo_feriado = feriado_entry.get("arquivo")
        if arquivo_feriado:
            caminho_feriado = banners_dir / arquivo_feriado
            if caminho_feriado.is_file():
                caption = feriado_entry.get("legenda") or legenda_padrao
                url = f"{GITHUB_RAW_BANNERS_BASE}/{arquivo_feriado}?v=20261021_v2"
                return BannerInfo(
                    banner_url=url,
                    full_hd_url=url,
                    caption=caption,
                    is_special_date=True,
                    filename=arquivo_feriado
                )

    # =========================================================================
    # TIER 2: Catálogo Geral (Imagens gerais disponíveis no diretório)
    # =========================================================================
    arquivos_feriados = {
        f_info.get("arquivo")
        for f_info in feriados.values()
        if isinstance(f_info, dict) and f_info.get("arquivo")
    }

    # Escaneia arquivos físicos .jpg e .jpeg na pasta excluindo os de feriados
    candidatos_gerais = []
    try:
        for f in sorted(banners_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg"] and f.name not in arquivos_feriados:
                candidatos_gerais.append(f)
    except Exception as e:
        logger.warning(f"Aviso ao escanear imagens gerais em {banners_dir}: {e}")

    if candidatos_gerais:
        # Para o Ticket 10, seleciona o primeiro candidato disponível
        # (O ciclo de exaustão sem repetição será incorporado no Ticket 11)
        escolhido = candidatos_gerais[0]

        # Busca legenda personalizada no catalogo_geral do manifesto se existir
        caption_geral = legenda_padrao
        for item in manifest_data.get("catalogo_geral", []):
            if isinstance(item, dict) and item.get("arquivo") == escolhido.name:
                caption_geral = item.get("legenda", legenda_padrao)
                break

        url_geral = f"{GITHUB_RAW_BANNERS_BASE}/{escolhido.name}?v=20261021_v2"
        return BannerInfo(
            banner_url=url_geral,
            full_hd_url=url_geral,
            caption=caption_geral,
            is_special_date=False,
            filename=escolhido.name
        )

    # =========================================================================
    # TIER 3: Fallback de Segurança Global (Castelo Clássico)
    # =========================================================================
    return _fallback_castelo_classico()
