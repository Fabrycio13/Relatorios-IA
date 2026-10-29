import unittest
from datetime import datetime
import json
import tempfile
from pathlib import Path

from src.delivery.banner_selector import (
    BannerInfo,
    resolver_banner_do_dia,
    confirmar_banner_utilizado,
    reconciliar_historico_se_necessario
)
from src.core.config import HEADER_BANNER_URL, HEADER_FULL_HD_URL


class TestBannerSelector(unittest.TestCase):
    """Testes unitários herméticos para o módulo BannerSelector (Ticket 10)."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.banners_dir = Path(self.tmp_dir.name)
        self.manifesto_path = self.banners_dir / "manifesto.json"

        # Manifesto de teste canônico
        self.sample_manifest = {
            "versao": "1.0",
            "legenda_padrao": "Legenda Padrão de Teste para o Diário de IA.",
            "feriados": {
                "10-31": {
                    "arquivo": "halloween.jpg",
                    "legenda": "Edição de Halloween: Bugs assombrados em produção."
                },
                "12-25": {
                    "arquivo": "natal.jpg",
                    "legenda": "Edição de Natal: Paz na branch main."
                },
                "2026-02-17": {
                    "arquivo": "carnaval.jpg",
                    "legenda": "Edição de Carnaval: Folia de múltiplos agentes."
                }
            },
            "catalogo_geral": [
                {
                    "arquivo": "banner_001.jpg",
                    "legenda": "A Forja dos Compiladores: Código determinístico."
                }
            ]
        }
        self.manifesto_path.write_text(json.dumps(self.sample_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_feriado_fixo_com_arquivo_fisico_seleciona_tier_1(self):
        """Valida seleção prioritária de feriado anual fixo (10-31) quando o arquivo físico existe."""
        halloween_file = self.banners_dir / "halloween.jpg"
        halloween_file.write_bytes(b"dummy_image_data")

        data_teste = datetime(2026, 10, 31, 8, 0, 0)
        info = resolver_banner_do_dia(
            data_envio=data_teste,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        self.assertTrue(info.is_special_date)
        self.assertEqual(info.filename, "halloween.jpg")
        self.assertIn("halloween.jpg", info.banner_url)
        self.assertEqual(info.caption, "Edição de Halloween: Bugs assombrados em produção.")

    def test_feriado_movel_com_arquivo_fisico_seleciona_tier_1(self):
        """Valida seleção de feriado móvel com data específica (YYYY-MM-DD) quando o arquivo existe."""
        carnaval_file = self.banners_dir / "carnaval.jpg"
        carnaval_file.write_bytes(b"dummy_image_data")

        data_teste = datetime(2026, 2, 17, 8, 0, 0)
        info = resolver_banner_do_dia(
            data_envio=data_teste,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        self.assertTrue(info.is_special_date)
        self.assertEqual(info.filename, "carnaval.jpg")
        self.assertIn("carnaval.jpg", info.banner_url)
        self.assertEqual(info.caption, "Edição de Carnaval: Folia de múltiplos agentes.")

    def test_feriado_sem_arquivo_fisico_degrada_para_catalogo_geral_tier_2(self):
        """Valida que quando a data coincide com feriado mas o .jpg inexiste, degrada para o Tier 2 se houver imagem geral."""
        # NÃO cria halloween.jpg, mas cria banner_001.jpg
        geral_file = self.banners_dir / "banner_001.jpg"
        geral_file.write_bytes(b"dummy_image_data")

        data_teste = datetime(2026, 10, 31, 8, 0, 0)
        info = resolver_banner_do_dia(
            data_envio=data_teste,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        # Deve degradar para Tier 2 (banner_001.jpg)
        self.assertFalse(info.is_special_date)
        self.assertEqual(info.filename, "banner_001.jpg")
        self.assertEqual(info.caption, "A Forja dos Compiladores: Código determinístico.")

    def test_feriado_sem_arquivo_fisico_e_sem_catalogo_geral_degrada_para_castelo_classico_tier_3(self):
        """Valida que quando feriado e catálogo geral estão sem arquivos, degrada para o castelo clássico."""
        # Pasta sem nenhum arquivo de imagem
        data_teste = datetime(2026, 10, 31, 8, 0, 0)
        info = resolver_banner_do_dia(
            data_envio=data_teste,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        self.assertFalse(info.is_special_date)
        self.assertEqual(info.filename, "castelo_panoramica_v2.jpg")
        self.assertEqual(info.banner_url, HEADER_BANNER_URL)
        self.assertEqual(info.full_hd_url, HEADER_FULL_HD_URL)
        self.assertIn("Castelo da Engenharia de Agentes", info.caption)

    def test_diretorio_banners_inexistente_faz_fallback_seguro_tier_3(self):
        """Valida fallback gracioso para o castelo clássico se o diretório não existir fisicamente."""
        caminho_inexistente = Path(tempfile.gettempdir()) / "diretorio_inexistente_banners_12345"
        info = resolver_banner_do_dia(
            data_envio=datetime(2026, 10, 29),
            banners_dir=caminho_inexistente,
            manifesto_path=caminho_inexistente / "manifesto.json"
        )

        self.assertFalse(info.is_special_date)
        self.assertEqual(info.filename, "castelo_panoramica_v2.jpg")
        self.assertEqual(info.banner_url, HEADER_BANNER_URL)

    def test_manifesto_corrompido_faz_fallback_seguro_tier_3(self):
        """Valida que JSON corrompido ou inválido não lança exceção e faz fallback silencioso."""
        self.manifesto_path.write_text("{ json invalido: sem aspas e quebrado... ", encoding="utf-8")

        info = resolver_banner_do_dia(
            data_envio=datetime(2026, 10, 31),
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        self.assertFalse(info.is_special_date)
        self.assertEqual(info.filename, "castelo_panoramica_v2.jpg")

    def test_descoberta_automatica_de_arquivo_sem_cadastro_aplica_legenda_padrao(self):
        """Valida que imagem física na pasta não listada no manifesto é absorvida com a legenda_padrao."""
        nova_imagem = self.banners_dir / "imagem_nao_cadastrada.jpg"
        nova_imagem.write_bytes(b"dummy_image_data")

        # Data sem feriado
        data_teste = datetime(2026, 10, 29)
        info = resolver_banner_do_dia(
            data_envio=data_teste,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        self.assertFalse(info.is_special_date)
        self.assertEqual(info.filename, "imagem_nao_cadastrada.jpg")
        self.assertEqual(info.caption, "Legenda Padrão de Teste para o Diário de IA.")


    def test_imagem_de_feriado_nao_vaza_para_catalogo_geral_em_dia_normal(self):
        """Valida que imagens comemorativas de feriados NUNCA entram no catálogo geral em datas comuns,
        mesmo quando são os únicos arquivos presentes no diretório."""
        # Cria apenas o arquivo de feriado 'halloween.jpg' (mapeado para 10-31)
        halloween_file = self.banners_dir / "halloween.jpg"
        halloween_file.write_bytes(b"dummy_image_data")

        # Consulta em uma data comum regular (29 de Outubro)
        data_comum = datetime(2026, 10, 29, 8, 0, 0)
        info = resolver_banner_do_dia(
            data_envio=data_comum,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        # Não deve usar halloween.jpg no dia comum; como não há fotos gerais, deve cair no Tier 3
        self.assertFalse(info.is_special_date)
        self.assertNotEqual(info.filename, "halloween.jpg")
        self.assertEqual(info.filename, "castelo_panoramica_v2.jpg")
        self.assertEqual(info.banner_url, HEADER_BANNER_URL)

    def test_manifesto_com_raiz_nao_objeto_faz_fallback_seguro_tier_3(self):
        """Valida que manifesto com raiz que não seja dicionário (ex: lista []) não lança exceção e faz fallback."""
        # Grava JSON sintaticamente válido, porém raiz do tipo lista []
        self.manifesto_path.write_text(json.dumps(["item_invalido_1", "item_invalido_2"]), encoding="utf-8")

        info = resolver_banner_do_dia(
            data_envio=datetime(2026, 10, 31),
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        self.assertFalse(info.is_special_date)
        self.assertEqual(info.filename, "castelo_panoramica_v2.jpg")
        self.assertEqual(info.banner_url, HEADER_BANNER_URL)



    def test_ciclo_exaustao_catalogo_geral_sem_repeticao_ate_esgotar(self):
        """Valida que o catálogo geral rotaciona sem repetição até que todas as fotos físicas
        tenham sido exibidas, reiniciando o ciclo automaticamente no dia N+1."""
        historico_path = self.banners_dir / "historico_banners.json"

        # Cria 3 imagens gerais físicas
        (self.banners_dir / "banner_001.jpg").write_bytes(b"img1")
        (self.banners_dir / "banner_002.jpg").write_bytes(b"img2")
        (self.banners_dir / "banner_003.jpg").write_bytes(b"img3")

        # Dia 1 (2026-10-21): Deve resolver banner_001.jpg
        d1 = datetime(2026, 10, 21, 8, 0, 0)
        info1 = resolver_banner_do_dia(data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info1.filename, "banner_001.jpg")
        confirmar_banner_utilizado(banner_info=info1, data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Dia 2 (2026-10-22): Deve resolver banner_002.jpg (sem repetir 001)
        d2 = datetime(2026, 10, 22, 8, 0, 0)
        info2 = resolver_banner_do_dia(data_envio=d2, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info2.filename, "banner_002.jpg")
        confirmar_banner_utilizado(banner_info=info2, data_envio=d2, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Dia 3 (2026-10-23): Deve resolver banner_003.jpg (sem repetir 001 nem 002)
        d3 = datetime(2026, 10, 23, 8, 0, 0)
        info3 = resolver_banner_do_dia(data_envio=d3, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info3.filename, "banner_003.jpg")
        confirmar_banner_utilizado(banner_info=info3, data_envio=d3, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Dia 4 (2026-10-24): Todas foram consumidas! Ciclo reinicia e escolhe banner_001.jpg
        d4 = datetime(2026, 10, 24, 8, 0, 0)
        info4 = resolver_banner_do_dia(data_envio=d4, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info4.filename, "banner_001.jpg")

    def test_adicao_dinamica_de_imagem_no_meio_do_ciclo_consome_antes_do_reset(self):
        """Valida que nova imagem física adicionada na pasta durante um ciclo é absorvida
        no conjunto de não consumidas e exibida antes do reinício do ciclo."""
        historico_path = self.banners_dir / "historico_banners.json"

        # Começa com 2 imagens
        (self.banners_dir / "banner_001.jpg").write_bytes(b"img1")
        (self.banners_dir / "banner_002.jpg").write_bytes(b"img2")

        # Dia 1: Consome banner_001.jpg
        d1 = datetime(2026, 10, 21)
        info1 = resolver_banner_do_dia(data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info1.filename, "banner_001.jpg")
        confirmar_banner_utilizado(banner_info=info1, data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Inserção dinâmica: usuário adiciona banner_003.jpg
        (self.banners_dir / "banner_003.jpg").write_bytes(b"img3")

        # Dia 2: Consome banner_002.jpg
        d2 = datetime(2026, 10, 22)
        info2 = resolver_banner_do_dia(data_envio=d2, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info2.filename, "banner_002.jpg")
        confirmar_banner_utilizado(banner_info=info2, data_envio=d2, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Dia 3: NÃO deve reiniciar ainda! Deve consumir a nova imagem adicionada (banner_003.jpg)
        d3 = datetime(2026, 10, 23)
        info3 = resolver_banner_do_dia(data_envio=d3, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info3.filename, "banner_003.jpg")
        confirmar_banner_utilizado(banner_info=info3, data_envio=d3, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Dia 4: Agora sim, com todas as 3 consumidas, reinicia o ciclo
        d4 = datetime(2026, 10, 24)
        info4 = resolver_banner_do_dia(data_envio=d4, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info4.filename, "banner_001.jpg")

    def test_idempotencia_reexecucoes_na_mesma_data_retornam_mesmo_banner(self):
        """Valida que reexecuções na mesma data de envio retornam exatamente a mesma imagem
        anteriormente atribuída e confirmada."""
        historico_path = self.banners_dir / "historico_banners.json"

        (self.banners_dir / "banner_001.jpg").write_bytes(b"img1")
        (self.banners_dir / "banner_002.jpg").write_bytes(b"img2")

        data_hoje = datetime(2026, 10, 29, 8, 0, 0)
        info_primeira = resolver_banner_do_dia(data_envio=data_hoje, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        confirmar_banner_utilizado(banner_info=info_primeira, data_envio=data_hoje, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Reexecução mais tarde no mesmo dia
        data_reexecucao = datetime(2026, 10, 29, 14, 30, 0)
        info_segunda = resolver_banner_do_dia(data_envio=data_reexecucao, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        self.assertEqual(info_segunda.filename, info_primeira.filename)
        self.assertEqual(info_segunda.caption, info_primeira.caption)

    def test_modo_preview_estritamente_read_only_nao_cria_nem_altera_historico(self):
        """Valida que resolver_banner_do_dia é estritamente somente leitura e nunca grava em disco."""
        historico_path = self.banners_dir / "historico_banners.json"

        (self.banners_dir / "banner_001.jpg").write_bytes(b"img1")
        (self.banners_dir / "banner_002.jpg").write_bytes(b"img2")

        self.assertFalse(historico_path.exists())

        # Múltiplas resoluções simulando chamadas de preview
        for dia in range(20, 25):
            info = resolver_banner_do_dia(
                data_envio=datetime(2026, 10, dia),
                banners_dir=self.banners_dir,
                manifesto_path=self.manifesto_path,
                historico_path=historico_path
            )
            self.assertIsNotNone(info)

        # O arquivo de histórico NÃO pode ter sido criado
        self.assertFalse(historico_path.exists())

    def test_feriado_comemorativo_nao_consome_catalogo_geral(self):
        """Valida que a ocorrência de feriado comemorativo não consome nem desalinha a rotação geral."""
        historico_path = self.banners_dir / "historico_banners.json"

        (self.banners_dir / "banner_001.jpg").write_bytes(b"img1")
        (self.banners_dir / "banner_002.jpg").write_bytes(b"img2")
        (self.banners_dir / "halloween.jpg").write_bytes(b"halloween")

        # Dia 1 (10-30): Regular -> consome banner_001.jpg
        d1 = datetime(2026, 10, 30)
        info1 = resolver_banner_do_dia(data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info1.filename, "banner_001.jpg")
        confirmar_banner_utilizado(banner_info=info1, data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Dia 2 (10-31, Halloween): Feriado -> exibe halloween.jpg
        d2 = datetime(2026, 10, 31)
        info2 = resolver_banner_do_dia(data_envio=d2, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertTrue(info2.is_special_date)
        self.assertEqual(info2.filename, "halloween.jpg")
        confirmar_banner_utilizado(banner_info=info2, data_envio=d2, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # Dia 3 (11-01): Regular -> Deve consumir banner_002.jpg (não repete banner_001!)
        d3 = datetime(2026, 11, 1)
        info3 = resolver_banner_do_dia(data_envio=d3, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info3.filename, "banner_002.jpg")

    def test_recuperacao_graciosa_historico_corrompido_ou_vazio(self):
        """Valida que histórico corrompido, vazio ou inválido não lança exceção e é reconstruído."""
        historico_path = self.banners_dir / "historico_banners.json"

        (self.banners_dir / "banner_001.jpg").write_bytes(b"img1")

        # Cenário 1: Arquivo vazio
        historico_path.write_text("", encoding="utf-8")
        info = resolver_banner_do_dia(data_envio=datetime(2026, 10, 29), banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info.filename, "banner_001.jpg")

        # Cenário 2: JSON corrompido
        historico_path.write_text("{ json quebrado...", encoding="utf-8")
        info = resolver_banner_do_dia(data_envio=datetime(2026, 10, 29), banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info.filename, "banner_001.jpg")

        # Cenário 3: JSON não-dicionário (ex: lista)
        historico_path.write_text(json.dumps(["item1", "item2"]), encoding="utf-8")
        info = resolver_banner_do_dia(data_envio=datetime(2026, 10, 29), banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(info.filename, "banner_001.jpg")

    def test_persistencia_atomica_usa_arquivo_tmp_e_os_replace(self):
        """Valida gravação atômica via arquivo .tmp e os.replace."""
        from unittest.mock import patch
        historico_path = self.banners_dir / "historico_banners.json"
        (self.banners_dir / "banner_001.jpg").write_bytes(b"img1")

        d1 = datetime(2026, 10, 29)
        info = resolver_banner_do_dia(data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        with patch("os.replace") as mock_replace:
            confirmar_banner_utilizado(banner_info=info, data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
            mock_replace.assert_called_once()
            src, dst = mock_replace.call_args[0]
            self.assertTrue(str(src).endswith(".tmp"))
            self.assertEqual(dst, historico_path)

    def test_reconciliacao_quando_smtp_sucesso_mas_historico_falhou(self):
        """Valida que quando status_file (ultimo_envio.txt) registra envio mas historico_banners.json
        não registrou, a reconciliação associa o banner sem queimar imagem adicional."""
        historico_path = self.banners_dir / "historico_banners.json"
        status_file = self.banners_dir / "ultimo_envio.txt"

        (self.banners_dir / "banner_001.jpg").write_bytes(b"img1")
        (self.banners_dir / "banner_002.jpg").write_bytes(b"img2")

        # Simula que o envio de hoje foi concluído no status_file
        data_hoje = datetime(2026, 10, 29)
        status_file.write_text("2026-10-29", encoding="utf-8")

        # Mas historico_banners.json está vazio (falha de gravação anterior)
        reconciliar_historico_se_necessario(
            data_envio=data_hoje,
            status_file=status_file,
            historico_path=historico_path,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        # O histórico deve ter sido reconciliado com banner_001.jpg
        hist_data = json.loads(historico_path.read_text(encoding="utf-8"))
        self.assertEqual(hist_data["ultimo_envio_por_data"]["2026-10-29"], "banner_001.jpg")
        self.assertEqual(hist_data["imagens_consumidas_no_ciclo"], ["banner_001.jpg"])



    def test_salvar_historico_atomico_limpa_tmp_em_caso_de_falha(self):
        """Valida que se a gravação atômica falhar no os.replace, o arquivo .tmp é excluído defensivamente."""
        from src.delivery.banner_selector import _salvar_historico_atomico
        from unittest.mock import patch

        historico_path = self.banners_dir / "historico_banners.json"
        tmp_path = self.banners_dir / "historico_banners.json.tmp"

        with patch("os.replace", side_effect=PermissionError("Simulated disk error")):
            sucesso = _salvar_historico_atomico(historico_path, {"teste": 1})
            self.assertFalse(sucesso)
            self.assertFalse(tmp_path.exists())

    def test_reconciliacao_limite_quando_novo_arquivo_alfabeticamente_anterior_inserido(self):
        """Demonstra o limite técnico documentado da reconciliação: se um arquivo alfabeticamente
        anterior for adicionado entre a falha e a reexecução, a reconciliação associa a imagem determinística
        atualmente disponível na pasta (limite de não termos o nome do arquivo persistido em ultimo_envio.txt)."""
        historico_path = self.banners_dir / "historico_banners.json"
        status_file = self.banners_dir / "ultimo_envio.txt"

        (self.banners_dir / "banner_002.jpg").write_bytes(b"img2")
        (self.banners_dir / "banner_003.jpg").write_bytes(b"img3")

        # Simula falha: ultimo_envio.txt registrou a data de hoje, mas historico falhou
        data_hoje = datetime(2026, 10, 29)
        status_file.write_text("2026-10-29", encoding="utf-8")

        # Intervenção externa antes da reexecução: novo arquivo inserido antes de banner_002.jpg
        (self.banners_dir / "banner_001_novo.jpg").write_bytes(b"img1_novo")

        reconciliar_historico_se_necessario(
            data_envio=data_hoje,
            status_file=status_file,
            historico_path=historico_path,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )

        # Demonstra que o reconciliador atribui a nova imagem determinística disponível
        hist_data = json.loads(historico_path.read_text(encoding="utf-8"))
        self.assertEqual(hist_data["ultimo_envio_por_data"]["2026-10-29"], "banner_001_novo.jpg")


    def test_reconciliacao_quando_execucao_ocorre_no_dia_seguinte_a_falha_de_persistencia(self):
        """Valida a simulação do Cenário 1:
        - Dia 1: Banner A enviado e registrado.
        - Dia 2: Banner B enviado e registrado.
        - Dia 3: Banner C enviado via SMTP, mas gravação de histórico falha; ultimo_envio.txt tem Dia 3.
        - Dia 4: Agendador executa normalmente sem --force.
        Garante que o Banner C NÃO é repetido no Dia 4, sendo selecionado o Banner D."""
        historico_path = self.banners_dir / "historico_banners.json"
        status_file = self.banners_dir / "ultimo_envio.txt"

        (self.banners_dir / "banner_01.jpg").write_bytes(b"A")
        (self.banners_dir / "banner_02.jpg").write_bytes(b"B")
        (self.banners_dir / "banner_03.jpg").write_bytes(b"C")
        (self.banners_dir / "banner_04.jpg").write_bytes(b"D")

        # Dia 1 (10-26): Banner A
        d1 = datetime(2026, 10, 26)
        b1 = resolver_banner_do_dia(data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        confirmar_banner_utilizado(banner_info=b1, data_envio=d1, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        status_file.write_text("2026-10-26", encoding="utf-8")
        self.assertEqual(b1.filename, "banner_01.jpg")

        # Dia 2 (10-27): Banner B
        d2 = datetime(2026, 10, 27)
        b2 = resolver_banner_do_dia(data_envio=d2, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        confirmar_banner_utilizado(banner_info=b2, data_envio=d2, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        status_file.write_text("2026-10-27", encoding="utf-8")
        self.assertEqual(b2.filename, "banner_02.jpg")

        # Dia 3 (10-28): Banner C enviado via SMTP, mas salvar_historico falhou (simulado por não chamar confirmar)
        d3 = datetime(2026, 10, 28)
        b3 = resolver_banner_do_dia(data_envio=d3, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)
        self.assertEqual(b3.filename, "banner_03.jpg")
        # Simula SMTP OK e gravação de ultimo_envio.txt com Dia 3
        status_file.write_text("2026-10-28", encoding="utf-8")

        # Dia 4 (10-29): Agendador aciona o pipeline normalmente
        d4 = datetime(2026, 10, 29)
        # 1. Pipeline aciona reconciliação
        reconciliar_historico_se_necessario(
            data_envio=d4,
            status_file=status_file,
            historico_path=historico_path,
            banners_dir=self.banners_dir,
            manifesto_path=self.manifesto_path
        )
        # 2. Pipeline resolve o banner do Dia 4
        b4 = resolver_banner_do_dia(data_envio=d4, banners_dir=self.banners_dir, manifesto_path=self.manifesto_path, historico_path=historico_path)

        # O Banner C NÃO pode se repetir no Dia 4! O sistema deve selecionar Banner D!
        self.assertNotEqual(b4.filename, "banner_03.jpg")
        self.assertEqual(b4.filename, "banner_04.jpg")

        # Valida que o histórico agora possui os registros corretos de ambos os dias
        hist_data = json.loads(historico_path.read_text(encoding="utf-8"))
        self.assertEqual(hist_data["ultimo_envio_por_data"]["2026-10-28"], "banner_03.jpg")
        self.assertIn("banner_03.jpg", hist_data["imagens_consumidas_no_ciclo"])


if __name__ == "__main__":
    unittest.main()
