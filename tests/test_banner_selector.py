import unittest
from datetime import datetime
import json
import tempfile
from pathlib import Path

from src.delivery.banner_selector import BannerInfo, resolver_banner_do_dia
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


if __name__ == "__main__":
    unittest.main()
