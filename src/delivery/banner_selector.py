"""Seletor de Banners do Diário de IA (The Engineering Gazette).

Responsável por resolver o banner do cabeçalho da edição com base na
hierarquia estrita de 3 Tiers (Spec 0005) e ciclo de exaustão (Ticket 11):
  - Tier 1: Feriado comemorativo (fixo ou móvel) com arquivo físico presente.
  - Tier 2: Catálogo geral rotativo com ciclo de exaustão sem repetição até
            esgotar todas as imagens físicas, absorção dinâmica e persistência atômica.
  - Tier 3: Fallback de segurança para o Castelo Clássico (castelo_panoramica_v2.jpg).
"""

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path

from src.core.config import DATA_DIR, STATUS_FILE, BANNERS_DIR, HEADER_BANNER_URL, HEADER_FULL_HD_URL

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


@dataclass(frozen=True)
class StatusBannersInfo:
    """Painel de status e auditoria operacional do catálogo de banners."""
    total_geral: int
    consumidas_ciclo: int
    percentual_consumido: float
    consumidas_detalhes: list[dict]
    proximo_banner: dict | None
    restantes_no_ciclo: list[str]
    feriados_programados: list[dict]


def resolver_subcaminho_banner(banners_dir: Path, filename: str) -> tuple[Path, str]:
    """Retorna o caminho físico do arquivo e o subcaminho relativo para a URL pública.

    Verifica hierarquicamente:
      1. banners_dir / "festivos" / filename (se existir) -> subcaminho "festivos/{filename}"
      2. banners_dir / "geral" / filename (se existir) -> subcaminho "geral/{filename}"
      3. banners_dir / "padrao" / filename (se existir) -> subcaminho "padrao/{filename}"
      4. banners_dir / filename (raiz plana para compatibilidade) -> subcaminho filename
    """
    for sub in ["festivos", "geral", "padrao"]:
        sub_path = banners_dir / sub / filename
        if sub_path.is_file():
            return sub_path, f"{sub}/{filename}"
    return banners_dir / filename, filename


def _fallback_castelo_classico(banners_dir: Path | None = None) -> BannerInfo:
    """Retorna o banner do castelo clássico garantindo resiliência operacional absoluta."""
    url = HEADER_BANNER_URL
    full_url = HEADER_FULL_HD_URL
    if banners_dir is not None:
        caminho_padrao, subcaminho = resolver_subcaminho_banner(banners_dir, DEFAULT_BANNER_FILENAME)
        if caminho_padrao.is_file():
            url = f"{GITHUB_RAW_BANNERS_BASE}/{subcaminho}?v=20261021_v2"
            full_url = url

    return BannerInfo(
        banner_url=url,
        full_hd_url=full_url,
        caption=DEFAULT_BANNER_CAPTION,
        is_special_date=False,
        filename=DEFAULT_BANNER_FILENAME
    )


def _obter_arquivos_feriados(manifest_data: dict) -> set[str]:
    """Retorna o conjunto de nomes de arquivos associados a feriados cadastrados no manifesto."""
    feriados = manifest_data.get("feriados", {}) if isinstance(manifest_data, dict) else {}
    return {
        f_info.get("arquivo")
        for f_info in feriados.values()
        if isinstance(f_info, dict) and f_info.get("arquivo")
    }


def _resolver_legenda(
    nome_arquivo: str,
    manifest_data: dict,
    is_special: bool,
    data_envio: datetime
) -> str:
    """Obtém a legenda customizada do arquivo no manifesto ou retorna a legenda padrão."""
    legenda_padrao = manifest_data.get("legenda_padrao", DEFAULT_BANNER_CAPTION)
    if is_special:
        feriados = manifest_data.get("feriados", {})
        chave_movel = data_envio.strftime("%Y-%m-%d")
        chave_fixa = data_envio.strftime("%m-%d")
        feriado_entry = feriados.get(chave_movel) or feriados.get(chave_fixa)
        if isinstance(feriado_entry, dict) and feriado_entry.get("legenda"):
            return feriado_entry["legenda"]
        for f_entry in feriados.values():
            if isinstance(f_entry, dict) and f_entry.get("arquivo") == nome_arquivo and f_entry.get("legenda"):
                return f_entry["legenda"]
    else:
        for item in manifest_data.get("catalogo_geral", []):
            if isinstance(item, dict) and item.get("arquivo") == nome_arquivo and item.get("legenda"):
                return item["legenda"]
    return legenda_padrao


def _carregar_historico(historico_path: Path) -> dict:
    """Carrega o histórico de banners garantindo reconstrução graciosa em memória se corrompido."""
    default_hist = {
        "versao": "1.0",
        "imagens_consumidas_no_ciclo": [],
        "ultimo_envio_por_data": {}
    }
    if not historico_path.exists() or not historico_path.is_file():
        return default_hist
    try:
        conteudo = historico_path.read_text(encoding="utf-8").strip()
        if not conteudo:
            return default_hist
        dados = json.loads(conteudo)
        if not isinstance(dados, dict):
            logger.warning(f"Aviso: Histórico ({historico_path}) não é um objeto JSON válido. Reconstruindo.")
            return default_hist
        if "imagens_consumidas_no_ciclo" not in dados or not isinstance(dados["imagens_consumidas_no_ciclo"], list):
            dados["imagens_consumidas_no_ciclo"] = []
        if "ultimo_envio_por_data" not in dados or not isinstance(dados["ultimo_envio_por_data"], dict):
            dados["ultimo_envio_por_data"] = {}
        return dados
    except Exception as e:
        logger.warning(f"Aviso ao ler histórico ({historico_path}): {e}. Reconstruindo em memória.")
        return default_hist


def _listar_arquivos_catalogo_geral(banners_dir: Path, arquivos_feriados: set[str]) -> list[str]:
    """Lista nomes de arquivos JPG/JPEG do diretório ordenados alfabeticamente, excluindo feriados.

    Varre prioritariamente a subpasta 'geral/'. Caso não exista, varre a raiz de banners_dir.
    """
    if not banners_dir.exists() or not banners_dir.is_dir():
        return []

    dir_varredura = banners_dir / "geral"
    if not (dir_varredura.exists() and dir_varredura.is_dir()):
        dir_varredura = banners_dir

    try:
        return sorted([
            f.name for f in dir_varredura.iterdir()
            if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg"] and f.name not in arquivos_feriados
        ])
    except Exception as e:
        logger.warning(f"Aviso ao escanear imagens gerais em {dir_varredura}: {e}")
        return []


def _salvar_historico_atomico(historico_path: Path, dados: dict) -> bool:
    """Salva o dicionário de histórico atomicamente via arquivo temporário intermediário e os.replace."""
    tmp_path = None
    try:
        historico_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = historico_path.with_name(f"{historico_path.name}.tmp")
        conteudo = json.dumps(dados, indent=2, ensure_ascii=False)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(conteudo)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, historico_path)
        return True
    except Exception as e:
        logger.warning(f"Aviso ao salvar histórico de banners atomicamente ({historico_path}): {e}")
        try:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
        except OSError as cleanup_err:
            logger.debug(f"Aviso ao remover arquivo temporário {tmp_path}: {cleanup_err}")
        return False


def resolver_banner_do_dia(
    data_envio: datetime | None = None,
    banners_dir: Path | None = None,
    manifesto_path: Path | None = None,
    historico_path: Path | None = None
) -> BannerInfo:
    """Resolve o banner correspondente à data de envio respeitando a hierarquia de 3 Tiers.

    Executa em modo estritamente somente leitura (read-only), sem alterar estado ou arquivos em disco.
    """
    if data_envio is None:
        data_envio = datetime.now()

    if banners_dir is None:
        banners_dir = BANNERS_DIR

    if manifesto_path is None:
        manifesto_path = banners_dir / "manifesto.json"

    if historico_path is None:
        historico_path = DATA_DIR / "historico_banners.json"

    # Se o diretório base não existir, faz fallback imediato para o Tier 3
    if not banners_dir.exists() or not banners_dir.is_dir():
        return _fallback_castelo_classico(banners_dir)

    # Leitura segura do manifesto
    manifest_data = {}
    if manifesto_path.exists() and manifesto_path.is_file():
        try:
            manifest_data = json.loads(manifesto_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Aviso ao ler manifesto de banners ({manifesto_path}): {e}. Prosseguindo com fallback.")
            return _fallback_castelo_classico(banners_dir)

    # Valida defensivamente que a raiz do JSON é um objeto (dicionário)
    if not isinstance(manifest_data, dict):
        logger.warning(f"Aviso: Manifesto de banners ({manifesto_path}) não é um objeto JSON válido. Prosseguindo com fallback.")
        return _fallback_castelo_classico(banners_dir)

    legenda_padrao = manifest_data.get("legenda_padrao", DEFAULT_BANNER_CAPTION)
    feriados = manifest_data.get("feriados", {})
    arquivos_feriados = _obter_arquivos_feriados(manifest_data)

    data_str = data_envio.strftime("%Y-%m-%d")

    # Carrega histórico em modo estritamente somente leitura
    historico = _carregar_historico(historico_path)
    ultimo_envio_por_data = historico.get("ultimo_envio_por_data", {})

    # =========================================================================
    # RECONCILIAÇÃO / IDEMPOTÊNCIA: Verifica se a data já foi enviada previamente
    # =========================================================================
    arquivo_ja_enviado = ultimo_envio_por_data.get(data_str)
    if arquivo_ja_enviado:
        caminho_ja_enviado, subcaminho = resolver_subcaminho_banner(banners_dir, arquivo_ja_enviado)
        if caminho_ja_enviado.is_file():
            is_special = arquivo_ja_enviado in arquivos_feriados
            caption = _resolver_legenda(arquivo_ja_enviado, manifest_data, is_special, data_envio)
            url = f"{GITHUB_RAW_BANNERS_BASE}/{subcaminho}?v=20261021_v2"
            return BannerInfo(
                banner_url=url,
                full_hd_url=url,
                caption=caption,
                is_special_date=is_special,
                filename=arquivo_ja_enviado
            )

    # =========================================================================
    # TIER 1: Verificação de Feriado Comemorativo (Fixo ou Móvel)
    # =========================================================================
    chave_movel = data_envio.strftime("%Y-%m-%d")
    chave_fixa = data_envio.strftime("%m-%d")

    feriado_entry = feriados.get(chave_movel) or feriados.get(chave_fixa)
    if feriado_entry and isinstance(feriado_entry, dict):
        arquivo_feriado = feriado_entry.get("arquivo")
        if arquivo_feriado:
            caminho_feriado, subcaminho = resolver_subcaminho_banner(banners_dir, arquivo_feriado)
            if caminho_feriado.is_file():
                caption = feriado_entry.get("legenda") or legenda_padrao
                url = f"{GITHUB_RAW_BANNERS_BASE}/{subcaminho}?v=20261021_v2"
                return BannerInfo(
                    banner_url=url,
                    full_hd_url=url,
                    caption=caption,
                    is_special_date=True,
                    filename=arquivo_feriado
                )

    # =========================================================================
    # TIER 2: Catálogo Geral Rotativo (Ciclo de Exaustão sem Repetição)
    # =========================================================================
    nomes_gerais = _listar_arquivos_catalogo_geral(banners_dir, arquivos_feriados)
    if nomes_gerais:
        consumidas = [nome for nome in historico.get("imagens_consumidas_no_ciclo", []) if nome in nomes_gerais]
        nao_consumidas = [nome for nome in nomes_gerais if nome not in consumidas]

        # Se todas as imagens físicas disponíveis já foram consumidas, reinicia o ciclo
        if not nao_consumidas:
            nao_consumidas = list(nomes_gerais)

        escolhido_nome = nao_consumidas[0]
        caminho_escolhido, subcaminho = resolver_subcaminho_banner(banners_dir, escolhido_nome)
        caption_geral = _resolver_legenda(escolhido_nome, manifest_data, is_special=False, data_envio=data_envio)
        url_geral = f"{GITHUB_RAW_BANNERS_BASE}/{subcaminho}?v=20261021_v2"
        return BannerInfo(
            banner_url=url_geral,
            full_hd_url=url_geral,
            caption=caption_geral,
            is_special_date=False,
            filename=escolhido_nome
        )

    # =========================================================================
    # TIER 3: Fallback de Segurança Global (Castelo Clássico)
    # =========================================================================
    return _fallback_castelo_classico(banners_dir)


def confirmar_banner_utilizado(
    banner_info: BannerInfo | None = None,
    data_envio: datetime | None = None,
    banners_dir: Path | None = None,
    manifesto_path: Path | None = None,
    historico_path: Path | None = None
) -> BannerInfo | None:
    """Executado exclusivamente após envio SMTP com sucesso para persistir atomicamente o uso."""
    if data_envio is None:
        data_envio = datetime.now()

    if banners_dir is None:
        banners_dir = BANNERS_DIR

    if manifesto_path is None:
        manifesto_path = banners_dir / "manifesto.json"

    if historico_path is None:
        historico_path = DATA_DIR / "historico_banners.json"

    if banner_info is None:
        banner_info = resolver_banner_do_dia(
            data_envio=data_envio,
            banners_dir=banners_dir,
            manifesto_path=manifesto_path,
            historico_path=historico_path
        )

    data_str = data_envio.strftime("%Y-%m-%d")
    historico = _carregar_historico(historico_path)

    ja_registrado = historico.get("ultimo_envio_por_data", {}).get(data_str)
    historico["ultimo_envio_por_data"][data_str] = banner_info.filename

    # Se for catálogo geral (não é feriado e não é o castelo clássico)
    if not banner_info.is_special_date and banner_info.filename != DEFAULT_BANNER_FILENAME:
        manifest_data = {}
        if manifesto_path.exists() and manifesto_path.is_file():
            try:
                manifest_data = json.loads(manifesto_path.read_text(encoding="utf-8"))
            except Exception:
                manifest_data = {}

        arquivos_feriados = _obter_arquivos_feriados(manifest_data)
        nomes_gerais = _listar_arquivos_catalogo_geral(banners_dir, arquivos_feriados)

        consumidas = [nome for nome in historico.get("imagens_consumidas_no_ciclo", []) if nome in nomes_gerais]

        if not ja_registrado:
            if set(consumidas) >= set(nomes_gerais):
                consumidas = [banner_info.filename]
            elif banner_info.filename not in consumidas:
                consumidas.append(banner_info.filename)
        historico["imagens_consumidas_no_ciclo"] = consumidas

    _salvar_historico_atomico(historico_path, historico)
    return banner_info


def reconciliar_historico_se_necessario(
    data_envio: datetime | None = None,
    status_file: Path | None = None,
    historico_path: Path | None = None,
    banners_dir: Path | None = None,
    manifesto_path: Path | None = None
) -> None:
    """Reconcilia falhas entre SMTP e disco.

    Se a data registrada em status_file (ultimo_envio.txt) não consta em historico_banners.json,
    confirma deterministicamente o banner para aquela data sem queimar outro banner.
    Cobre tanto reexecuções no mesmo dia quanto execuções subsequentes em dias posteriores.
    """
    if data_envio is None:
        data_envio = datetime.now()

    if status_file is None:
        status_file = STATUS_FILE

    if historico_path is None:
        historico_path = DATA_DIR / "historico_banners.json"

    status_registrado = None
    if status_file.exists() and status_file.is_file():
        try:
            status_registrado = status_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    if status_registrado:
        historico = _carregar_historico(historico_path)
        if status_registrado not in historico.get("ultimo_envio_por_data", {}):
            try:
                data_status = datetime.strptime(status_registrado, "%Y-%m-%d")
                logger.info(
                    f"Reconciliando histórico de banners para a data {status_registrado} a partir de {status_file.name}..."
                )
                confirmar_banner_utilizado(
                    data_envio=data_status,
                    banners_dir=banners_dir,
                    manifesto_path=manifesto_path,
                    historico_path=historico_path
                )
            except ValueError:
                logger.warning(f"Data inválida em {status_file.name}: {status_registrado}")


def obter_status_banners(
    data_consulta: datetime | None = None,
    banners_dir: Path | None = None,
    manifesto_path: Path | None = None,
    historico_path: Path | None = None
) -> StatusBannersInfo:
    """Calcula estatísticas e previsões do ciclo de banners de forma estritamente somente-leitura."""
    if data_consulta is None:
        data_consulta = datetime.now()
    if banners_dir is None:
        banners_dir = BANNERS_DIR
    if manifesto_path is None:
        manifesto_path = banners_dir / "manifesto.json"
    if historico_path is None:
        historico_path = DATA_DIR / "historico_banners.json"

    manifest_data = {}
    if manifesto_path.exists() and manifesto_path.is_file():
        try:
            manifest_data = json.loads(manifesto_path.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = {}

    arquivos_feriados = _obter_arquivos_feriados(manifest_data)
    nomes_gerais = _listar_arquivos_catalogo_geral(banners_dir, arquivos_feriados)
    historico = _carregar_historico(historico_path)

    consumidas = [nome for nome in historico.get("imagens_consumidas_no_ciclo", []) if nome in nomes_gerais]
    nao_consumidas = [nome for nome in nomes_gerais if nome not in consumidas]

    total_geral = len(nomes_gerais)
    total_consumidas = len(consumidas)
    percentual = (total_consumidas / total_geral * 100.0) if total_geral > 0 else 0.0

    proximo_nome = nao_consumidas[0] if nao_consumidas else (nomes_gerais[0] if nomes_gerais else None)
    proximo_banner = None
    if proximo_nome:
        caminho_fisico, subcaminho = resolver_subcaminho_banner(banners_dir, proximo_nome)
        legenda = _resolver_legenda(proximo_nome, manifest_data, is_special=False, data_envio=data_consulta)
        titulo = ""
        for item in manifest_data.get("catalogo_geral", []):
            if isinstance(item, dict) and item.get("arquivo") == proximo_nome:
                titulo = item.get("titulo", "")
                break
        proximo_banner = {
            "arquivo": proximo_nome,
            "titulo": titulo or proximo_nome,
            "legenda": legenda,
            "caminho_fisico": caminho_fisico,
            "subcaminho": subcaminho
        }

    ultimo_envio_por_data = historico.get("ultimo_envio_por_data", {})
    datas_por_arquivo = {}
    for dt_str, arq in ultimo_envio_por_data.items():
        datas_por_arquivo.setdefault(arq, []).append(dt_str)

    consumidas_detalhes = []
    for nome in consumidas:
        datas = datas_por_arquivo.get(nome, [])
        consumidas_detalhes.append({
            "arquivo": nome,
            "datas_envio": datas
        })

    feriados_info = []
    feriados = manifest_data.get("feriados", {})
    if isinstance(feriados, dict):
        for chave, entry in sorted(feriados.items(), key=lambda x: str(x[0])):
            if isinstance(entry, dict):
                arq = entry.get("arquivo", "")
                caminho_f, _ = resolver_subcaminho_banner(banners_dir, arq) if arq else (Path(), "")
                feriados_info.append({
                    "data": chave,
                    "titulo": entry.get("titulo", chave),
                    "arquivo": arq,
                    "presente": caminho_f.is_file() if arq else False,
                    "legenda": entry.get("legenda", "")
                })

    return StatusBannersInfo(
        total_geral=total_geral,
        consumidas_ciclo=total_consumidas,
        percentual_consumido=percentual,
        consumidas_detalhes=consumidas_detalhes,
        proximo_banner=proximo_banner,
        restantes_no_ciclo=nao_consumidas,
        feriados_programados=feriados_info
    )


def exibir_status_banners(
    preview: bool = False,
    banners_dir: Path | None = None,
    manifesto_path: Path | None = None,
    historico_path: Path | None = None
) -> int:
    """Exibe painel de status formatado no terminal e opcionalmente abre preview no navegador."""
    import webbrowser

    status = obter_status_banners(
        banners_dir=banners_dir,
        manifesto_path=manifesto_path,
        historico_path=historico_path
    )

    print("=" * 65)
    print("           STATUS DO CATÁLOGO DE BANNERS - GAZETA DE IA")
    print("=" * 65)
    print(f"Total no Catálogo Geral: {status.total_geral} imagens")
    print(f"Progresso do Ciclo:      {status.consumidas_ciclo}/{status.total_geral} ({status.percentual_consumido:.1f}% consumido)")
    print("-" * 65)

    print(f"\n[USADAS NO CICLO ATUAL ({len(status.consumidas_detalhes)})]")
    if not status.consumidas_detalhes:
        print("  (Nenhuma imagem consumida ainda no ciclo corrente)")
    else:
        for item in status.consumidas_detalhes:
            datas = ", ".join(item["datas_envio"]) if item["datas_envio"] else "em ciclo"
            print(f"  ✓ {item['arquivo']:<28} (enviado em: {datas})")

    print("\n[PRÓXIMO BANNER DA FILA]")
    if status.proximo_banner:
        prox = status.proximo_banner
        print(f"  ▶ Arquivo: {prox['arquivo']}")
        if prox.get("titulo"):
            print(f"    Tema:    {prox['titulo']}")
        print(f"    Legenda: \"{prox['legenda']}\"")
    else:
        print("  (Nenhum banner disponível no catálogo geral)")

    print(f"\n[NÃO UTILIZADAS NO CICLO ({len(status.restantes_no_ciclo)} restantes)]")
    if not status.restantes_no_ciclo:
        print("  (Ciclo completo! A próxima execução reiniciará a rotação)")
    else:
        chunk_size = 4
        chunks = [status.restantes_no_ciclo[i:i + chunk_size] for i in range(0, len(status.restantes_no_ciclo), chunk_size)]
        for chunk in chunks:
            print("  • " + "   • ".join(chunk))

    print(f"\n[DATAS FESTIVAS PROGRAMADAS ({len(status.feriados_programados)})]")
    for f in status.feriados_programados:
        status_ico = "🟢 Presente" if f["presente"] else "🟡 Pendente"
        print(f"  ★ {f['data']:<10} | {f['arquivo']:<24} | {status_ico} | {f['titulo']}")

    print("=" * 65)

    if preview:
        if status.proximo_banner and status.proximo_banner.get("caminho_fisico") and status.proximo_banner["caminho_fisico"].is_file():
            caminho = status.proximo_banner["caminho_fisico"].resolve()
            print(f"\n🌐 Abrindo visualização no navegador: {caminho.name} ...")
            webbrowser.open(caminho.as_uri())
        else:
            print("\n⚠️ Não foi possível abrir o preview: arquivo físico do próximo banner não encontrado.")

    return 0
