"""Suíte de testes de validação de schema do manifesto, migração legada e frescor temporal.

Implementa a validação estrita dos contratos do Ticket 19 (Spec 0007 v4.3).
"""

from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import tempfile
import unittest

from src.core.manifest import (
    validar_schema_manifesto,
    is_manifesto_v1,
    migrar_manifesto_v1_para_v2,
    is_source_fresh,
    avaliar_estado_execucao,
    is_execucao_em_andamento,
    is_execucao_finalizada,
    criar_manifesto_v2_vazio,
)
from src.core.models import SourceStatus


class TestManifestSchemaAndFreshness(unittest.TestCase):
    """Testes de schema v2, migração legada v1 e política de frescor temporal."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        # Horário de referência fixo para os testes
        self.now_fixed = datetime(2026, 11, 12, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _criar_manifesto_v2_valido(self) -> dict:
        return {
            "version": 2,
            "collected_at": "2026-11-12T12:00:00.000000+00:00",
            "last_attempt": {
                "started_at": "2026-11-12T11:59:00.000000+00:00",
                "completed_at": "2026-11-12T12:00:00.000000+00:00",
                "status": "completed",
                "trigger": "scheduled",
                "pid": 12345,
            },
            "sources": {
                "twitter": {
                    "updated_at": "2026-11-12T12:00:00.000000+00:00",
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "count": 42,
                    "status": "success",
                    "quality": "verified",
                },
                "github": {
                    "updated_at": "2026-11-12T12:00:00.000000+00:00",
                    "sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
                    "count": 15,
                    "status": "success",
                    "quality": "verified",
                },
                "papers": {
                    "updated_at": "2026-11-12T12:00:00.000000+00:00",
                    "sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
                    "count": 10,
                    "status": "success",
                    "quality": "verified",
                },
            },
        }

    # 1. Manifesto v2 válido e estruturalmente inválido
    def test_manifesto_v2_valido_retorna_true(self):
        manifesto = self._criar_manifesto_v2_valido()
        self.assertTrue(validar_schema_manifesto(manifesto))

    def test_manifesto_v2_chaves_raiz_ausentes_retorna_false(self):
        for chave in ("version", "collected_at", "last_attempt", "sources"):
            manifesto = self._criar_manifesto_v2_valido()
            del manifesto[chave]
            self.assertFalse(validar_schema_manifesto(manifesto), f"Deveria falhar sem chave {chave}")

    def test_manifesto_v2_versao_diferente_de_2_retorna_false(self):
        manifesto = self._criar_manifesto_v2_valido()
        manifesto["version"] = 1
        self.assertFalse(validar_schema_manifesto(manifesto))
        manifesto["version"] = 3
        self.assertFalse(validar_schema_manifesto(manifesto))

    # 2. Campos obrigatórios, tipos, identificadores canônicos, status e hash SHA-256
    def test_last_attempt_status_invalido_retorna_false(self):
        manifesto = self._criar_manifesto_v2_valido()
        manifesto["last_attempt"]["status"] = "invalido"
        self.assertFalse(validar_schema_manifesto(manifesto))

    def test_sha256_invalido_rejeitado(self):
        manifesto = self._criar_manifesto_v2_valido()
        # Não hexadecimal
        manifesto["sources"]["twitter"]["sha256"] = "z" * 64
        self.assertFalse(validar_schema_manifesto(manifesto))
        # Tamanho diferente de 64
        manifesto["sources"]["twitter"]["sha256"] = "a" * 63
        self.assertFalse(validar_schema_manifesto(manifesto))
        # Maiúsculas (deve ser estritamente minúsculo)
        manifesto["sources"]["twitter"]["sha256"] = ("A" * 64)
        self.assertFalse(validar_schema_manifesto(manifesto))

    def test_source_status_invalido_rejeitado(self):
        manifesto = self._criar_manifesto_v2_valido()
        manifesto["sources"]["twitter"]["status"] = "unknown_status"
        self.assertFalse(validar_schema_manifesto(manifesto))

    def test_source_quality_aceita_apenas_valores_canônicos(self):
        manifesto = self._criar_manifesto_v2_valido()
        for q in ("verified", "legacy_unverified", "recovered"):
            manifesto["sources"]["twitter"]["quality"] = q
            self.assertTrue(validar_schema_manifesto(manifesto), f"Deveria aceitar quality={q}")

        manifesto["sources"]["twitter"]["quality"] = "invented_quality"
        self.assertFalse(validar_schema_manifesto(manifesto))

    # 3. Rejeição de booleanos onde números inteiros são obrigatórios
    def test_rejeicao_de_booleanos_em_campos_inteiros(self):
        manifesto = self._criar_manifesto_v2_valido()
        manifesto["version"] = True  # bool é subclasse de int em Python
        self.assertFalse(validar_schema_manifesto(manifesto), "version não pode ser booleano")

        manifesto = self._criar_manifesto_v2_valido()
        manifesto["last_attempt"]["pid"] = False
        self.assertFalse(validar_schema_manifesto(manifesto), "pid não pode ser booleano")

        manifesto = self._criar_manifesto_v2_valido()
        manifesto["sources"]["twitter"]["count"] = True
        self.assertFalse(validar_schema_manifesto(manifesto), "count não pode ser booleano")

        manifesto = self._criar_manifesto_v2_valido()
        manifesto["sources"]["twitter"]["count"] = 10.5
        self.assertFalse(validar_schema_manifesto(manifesto), "count não pode ser float")

    def test_count_negativo_rejeitado(self):
        manifesto = self._criar_manifesto_v2_valido()
        manifesto["sources"]["twitter"]["count"] = -1
        self.assertFalse(validar_schema_manifesto(manifesto))

    def test_count_zero_valido(self):
        manifesto = self._criar_manifesto_v2_valido()
        manifesto["sources"]["twitter"]["count"] = 0
        self.assertTrue(validar_schema_manifesto(manifesto))

    def test_aceita_items_count_como_alias(self):
        manifesto = self._criar_manifesto_v2_valido()
        del manifesto["sources"]["twitter"]["count"]
        manifesto["sources"]["twitter"]["items_count"] = 12
        self.assertTrue(validar_schema_manifesto(manifesto))

    # 4. Compatibilidade com metadados v1 reais do projeto
    def test_identificacao_de_manifesto_v1(self):
        v1_real = {
            "collected_at": "2026-10-27T08:00:00",
            "sources": {
                "twitter": "2026-10-27T08:00:00",
                "github": "2026-10-27T08:00:00",
                "papers": "2026-10-27T08:00:00",
            },
        }
        self.assertTrue(is_manifesto_v1(v1_real))
        self.assertFalse(validar_schema_manifesto(v1_real))

        manifesto_v2 = self._criar_manifesto_v2_valido()
        self.assertFalse(is_manifesto_v1(manifesto_v2))

    # 5. Migração não destrutiva e classificação legacy_unverified
    def test_migracao_v1_para_v2_produz_manifesto_valido_com_legacy_unverified(self):
        v1_data = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "twitter": "2026-10-27T08:00:00.000000+00:00",
                "github": "2026-10-27T08:00:00.000000+00:00",
                "papers": "2026-10-27T08:00:00.000000+00:00",
            },
        }

        v2_migrado = migrar_manifesto_v1_para_v2(v1_data)
        self.assertTrue(validar_schema_manifesto(v2_migrado))
        self.assertEqual(v2_migrado["version"], 2)

        for src_name in ("twitter", "github", "papers"):
            src_info = v2_migrado["sources"][src_name]
            self.assertEqual(src_info["quality"], "legacy_unverified")
            self.assertEqual(src_info["status"], "failed")
            self.assertIsNone(src_info["sha256"])
            self.assertEqual(src_info["count"], 0)

    # 6. Garantia de que calcular SHA-256 durante migração não transforma dados em verified
    def test_migracao_com_arquivos_existentes_em_disco_preserva_legacy_unverified(self):
        tweets_file = self.base_dir / "tweets_coletados.json"
        tweets_file.write_text('[{"text": "legado"}]', encoding="utf-8")

        v1_data = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "twitter": "2026-10-27T08:00:00.000000+00:00",
            },
        }

        v2_migrado = migrar_manifesto_v1_para_v2(v1_data, data_dir=self.base_dir)
        self.assertTrue(validar_schema_manifesto(v2_migrado))
        self.assertEqual(v2_migrado["sources"]["twitter"]["quality"], "legacy_unverified")
        self.assertEqual(v2_migrado["sources"]["twitter"]["status"], "success")
        self.assertEqual(v2_migrado["sources"]["twitter"]["count"], 1)
        self.assertEqual(len(v2_migrado["sources"]["twitter"]["sha256"]), 64)
        self.assertNotEqual(
            v2_migrado["sources"]["twitter"]["quality"],
            "verified",
            "Cálculo de SHA-256 no legado NÃO pode declarar integridade retrospectiva!",
        )

    # 7. is_source_fresh com fronteiras exatas de 36 horas
    def test_frescor_fronteira_exata_36_horas(self):
        # 36 horas exatas atrás -> True
        dt_36h = self.now_fixed - timedelta(hours=36)
        self.assertTrue(is_source_fresh(dt_36h, max_hours=36.0, now=self.now_fixed))

        # 36 horas e 1 segundo atrás -> False (stale)
        dt_36h_mais_1s = self.now_fixed - timedelta(hours=36, seconds=1)
        self.assertFalse(is_source_fresh(dt_36h_mais_1s, max_hours=36.0, now=self.now_fixed))

        # 0 segundos de diferença -> True
        self.assertTrue(is_source_fresh(self.now_fixed, max_hours=36.0, now=self.now_fixed))

    # 8. Tolerância de até 300 segundos para timestamps futuros
    def test_tolerancia_futuro_ate_300_segundos(self):
        # 300 segundos no futuro -> True
        dt_futuro_300s = self.now_fixed + timedelta(seconds=300)
        self.assertTrue(is_source_fresh(dt_futuro_300s, max_hours=36.0, now=self.now_fixed))

        # 301 segundos no futuro -> False (anomalia de relógio)
        dt_futuro_301s = self.now_fixed + timedelta(seconds=301)
        self.assertFalse(is_source_fresh(dt_futuro_301s, max_hours=36.0, now=self.now_fixed))

        # 600 segundos no futuro -> False
        dt_futuro_600s = self.now_fixed + timedelta(seconds=600)
        self.assertFalse(is_source_fresh(dt_futuro_600s, max_hours=36.0, now=self.now_fixed))

    # 9. Timestamps ingênuos sem fuso conhecido classificados como temporalmente não confiáveis
    def test_timestamp_ingenuo_classificado_como_nao_confiavel(self):
        # datetime ingênuo (tzinfo=None)
        dt_ingenuo = datetime(2026, 11, 12, 11, 30, 0)
        self.assertFalse(
            is_source_fresh(dt_ingenuo, max_hours=36.0, now=self.now_fixed),
            "Timestamp ingênuo sem fuso deve ser classificado como não confiável (False)",
        )

        # String ISO ingênua sem offset
        iso_ingenuo = "2026-11-12T11:30:00"
        self.assertFalse(
            is_source_fresh(iso_ingenuo, max_hours=36.0, now=self.now_fixed),
            "String ISO sem offset de fuso deve ser classificada como não confiável (False)",
        )

        # String ISO com fuso UTC válido (+00:00) -> True
        iso_aware = "2026-11-12T11:30:00+00:00"
        self.assertTrue(is_source_fresh(iso_aware, max_hours=36.0, now=self.now_fixed))

    # 10. Governança do ciclo de vida em last_attempt e distinção entre execução e publicação
    def test_execucao_em_andamento_e_finalizada_identificadas_corretamente(self):
        running_attempt = {
            "started_at": "2026-11-12T11:50:00.000000+00:00",
            "status": "running",
            "trigger": "scheduled",
            "pid": 99999,
        }
        self.assertTrue(is_execucao_em_andamento(running_attempt))
        self.assertFalse(is_execucao_finalizada(running_attempt))

        completed_attempt = {
            "started_at": "2026-11-12T11:50:00.000000+00:00",
            "completed_at": "2026-11-12T12:00:00.000000+00:00",
            "status": "completed",
            "trigger": "scheduled",
            "pid": 99999,
        }
        self.assertFalse(is_execucao_em_andamento(completed_attempt))
        self.assertTrue(is_execucao_finalizada(completed_attempt))

    def test_distincao_entre_execucao_finalizada_e_sucesso_de_fontes(self):
        # Manifesto com ciclo de execução 'completed', mas onde uma fonte falhou
        manifesto = self._criar_manifesto_v2_valido()
        manifesto["last_attempt"]["status"] = "completed"
        manifesto["sources"]["twitter"]["status"] = "failed"

        # A execução finalizou, mas isso NÃO significa que todas as fontes foram bem-sucedidas
        self.assertTrue(is_execucao_finalizada(manifesto["last_attempt"]))
        self.assertEqual(manifesto["sources"]["twitter"]["status"], "failed")

    def test_estado_running_com_pid_ausente_ou_tempo_longo_nao_assume_crash(self):
        # Tentativa iniciada há mais de 30 minutos sem PID
        last_attempt_longo = {
            "started_at": "2026-11-12T10:00:00.000000+00:00",
            "status": "running",
            "trigger": "scheduled",
            "pid": None,
        }
        status, msg = avaliar_estado_execucao(last_attempt_longo)
        self.assertEqual(status, "running")
        self.assertTrue(is_execucao_em_andamento(last_attempt_longo))
        self.assertFalse(is_execucao_finalizada(last_attempt_longo))

    def test_migracao_em_memoria_nao_modifica_arquivos_reais(self):
        prod_data_dir = Path("data")
        arquivos_antes = {}
        if prod_data_dir.exists():
            arquivos_antes = {p: p.stat().st_mtime for p in prod_data_dir.iterdir() if p.is_file()}

        # Executa migração em memória
        v1_data = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {"twitter": "2026-10-27T08:00:00.000000+00:00"},
        }
        _ = migrar_manifesto_v1_para_v2(v1_data)

        if prod_data_dir.exists():
            arquivos_depois = {p: p.stat().st_mtime for p in prod_data_dir.iterdir() if p.is_file()}
            self.assertEqual(
                arquivos_antes,
                arquivos_depois,
                "A migração em memória jamais deve alterar arquivos em data/!",
            )

    # 11. Entradas malformadas rejeitadas sem exceções inesperadas
    def test_entradas_malformadas_rejeitadas_graciosamente(self):
        self.assertFalse(validar_schema_manifesto(None))
        self.assertFalse(validar_schema_manifesto("string_invalida"))
        self.assertFalse(validar_schema_manifesto([]))
        self.assertFalse(validar_schema_manifesto({}))
        self.assertFalse(validar_schema_manifesto({"sources": "nao_e_dict"}))

        self.assertFalse(is_source_fresh(None))
        self.assertFalse(is_source_fresh("data_invalida_nao_iso"))
        self.assertFalse(is_source_fresh(12345))

    # 12. Primeiro uso limpo de v2 (sem manifesto prévio)
    def test_primeiro_uso_v2_sem_manifesto_previo(self):
        manifesto_novo = criar_manifesto_v2_vazio(now=self.now_fixed)
        self.assertTrue(validar_schema_manifesto(manifesto_novo))
        self.assertEqual(manifesto_novo["version"], 2)
        self.assertEqual(manifesto_novo["collected_at"], self.now_fixed.isoformat())
        self.assertEqual(manifesto_novo["last_attempt"]["status"], "completed")

    # 13. Testes RED: Hash em falha de leitura (Item 1)
    def test_calcular_sha256_arquivo_inexistente_levanta_file_not_found(self):
        from src.core.manifest import _calcular_sha256_arquivo
        arquivo_fantasma = self.base_dir / "inexistente.json"
        with self.assertRaises(FileNotFoundError):
            _calcular_sha256_arquivo(arquivo_fantasma)

    def test_calcular_sha256_arquivo_com_erro_io_levanta_os_error(self):
        import errno
        from unittest.mock import patch
        from src.core.manifest import _calcular_sha256_arquivo
        arquivo = self.base_dir / "arquivo_io.json"
        arquivo.write_text("{}", encoding="utf-8")
        with patch("builtins.open", side_effect=OSError(errno.EIO, "Falha de I/O no disco")):
            with self.assertRaises(OSError):
                _calcular_sha256_arquivo(arquivo)

    # 14. Testes RED: Migração legada diferencia sucesso, vazio e falha (Item 2)
    def test_migracao_legada_diferencia_sucesso_vazio_e_falha(self):
        # 1. Arquivo com itens -> success
        tweets_file = self.base_dir / "tweets_coletados.json"
        tweets_file.write_text('[{"text": "tweet real"}]', encoding="utf-8")

        # 2. Arquivo com lista vazia -> empty
        github_file = self.base_dir / "github_trending.json"
        github_file.write_text("[]", encoding="utf-8")

        # 3. Arquivo com JSON corrompido / sintaxe inválida -> failed
        papers_file = self.base_dir / "hf_papers.json"
        papers_file.write_text('{"corrompido": ', encoding="utf-8")

        v1_data = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "twitter": "2026-10-27T08:00:00.000000+00:00",
                "github": "2026-10-27T08:00:00.000000+00:00",
                "papers": "2026-10-27T08:00:00.000000+00:00",
                "fonte_fantasma": "2026-10-27T08:00:00.000000+00:00",
            },
        }

        v2_migrado = migrar_manifesto_v1_para_v2(v1_data, data_dir=self.base_dir)

        # Twitter: arquivo válido com itens -> status=success, count=1
        self.assertEqual(v2_migrado["sources"]["twitter"]["status"], "success")
        self.assertEqual(v2_migrado["sources"]["twitter"]["count"], 1)
        self.assertIsNotNone(v2_migrado["sources"]["twitter"]["sha256"])

        # GitHub: arquivo válido com lista vazia -> status=empty, count=0
        self.assertEqual(v2_migrado["sources"]["github"]["status"], "empty")
        self.assertEqual(v2_migrado["sources"]["github"]["count"], 0)
        self.assertIsNotNone(v2_migrado["sources"]["github"]["sha256"])

        # Papers: arquivo com JSON inválido -> status=failed, count=0 (NÃO declara success!)
        self.assertEqual(v2_migrado["sources"]["papers"]["status"], "failed")
        self.assertEqual(v2_migrado["sources"]["papers"]["count"], 0)

        # Fonte fantasma: arquivo inexistente -> status=failed, sha256=None (NÃO inventa hash fictício!)
        self.assertEqual(v2_migrado["sources"]["fonte_fantasma"]["status"], "failed")
        self.assertIsNone(v2_migrado["sources"]["fonte_fantasma"]["sha256"])

    def test_migracao_legada_nao_inventa_timestamps_atuais_para_datas_invalidas(self):
        v1_data = {
            "collected_at": "data_coleta_invalida",
            "sources": {
                "twitter": "timestamp_corrompido_legado",
            },
        }
        v2_migrado = migrar_manifesto_v1_para_v2(v1_data, data_dir=self.base_dir)

        # Não pode substituir por datetime.now()!
        self.assertEqual(v2_migrado["sources"]["twitter"]["updated_at"], "timestamp_corrompido_legado")
        self.assertEqual(v2_migrado["collected_at"], "data_coleta_invalida")
        # Avaliação de frescor deve falhar normalmente
        self.assertFalse(is_source_fresh(v2_migrado["sources"]["twitter"]["updated_at"]))

    # 15. Testes RED: Validação defensiva contra tipos não-hashables e is_manifesto_v1 (Item 3)
    def test_validacao_defensiva_rejeita_list_e_dict_em_status_e_quality_sem_typeerror(self):
        manifesto = self._criar_manifesto_v2_valido()

        # status como list ou dict
        manifesto["sources"]["twitter"]["status"] = ["success"]
        self.assertFalse(validar_schema_manifesto(manifesto), "status como list deve retornar False sem TypeError")

        manifesto["sources"]["twitter"]["status"] = {"valor": "success"}
        self.assertFalse(validar_schema_manifesto(manifesto), "status como dict deve retornar False sem TypeError")

        # quality como list ou dict
        manifesto["sources"]["twitter"]["status"] = "success"
        manifesto["sources"]["twitter"]["quality"] = ["verified"]
        self.assertFalse(validar_schema_manifesto(manifesto), "quality como list deve retornar False sem TypeError")

        manifesto["sources"]["twitter"]["quality"] = {"q": "verified"}
        self.assertFalse(validar_schema_manifesto(manifesto), "quality como dict deve retornar False sem TypeError")

        # last_attempt.status como list ou dict
        manifesto = self._criar_manifesto_v2_valido()
        manifesto["last_attempt"]["status"] = ["running"]
        self.assertFalse(validar_schema_manifesto(manifesto), "last_attempt.status como list deve retornar False sem TypeError")

    def test_is_manifesto_v1_rejeita_versoes_desconhecidas_e_estruturas_invalidas(self):
        # Versão desconhecida (ex: 3) não pode ser classificada como v1
        self.assertFalse(is_manifesto_v1({
            "version": 3,
            "collected_at": "2026-10-27T08:00:00",
            "sources": {"twitter": "2026-10-27T08:00:00"}
        }))

        # Versão 2 não é v1
        self.assertFalse(is_manifesto_v1(self._criar_manifesto_v2_valido()))

        # sources com objetos aninhados não é v1
        self.assertFalse(is_manifesto_v1({
            "collected_at": "2026-10-27T08:00:00",
            "sources": {"twitter": {"count": 10}}
        }))

        # sem collected_at não é v1
        self.assertFalse(is_manifesto_v1({
            "sources": {"twitter": "2026-10-27T08:00:00"}
        }))

        # sources vazio não é v1
        self.assertFalse(is_manifesto_v1({
            "collected_at": "2026-10-27T08:00:00",
            "sources": {}
        }))

    # 16. Testes de Integração de Migração v1 -> v2 e Contrato de Validação (5 Cenários)
    def test_integracao_migracao_v1_com_arquivo_json_valido(self):
        """Cenário 1: Manifesto v1 com arquivo JSON válido contendo itens."""
        tweets_file = self.base_dir / "tweets_coletados.json"
        tweets_file.write_text('[{"text": "tweet_1"}, {"text": "tweet_2"}]', encoding="utf-8")

        v1_data = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "twitter": "2026-10-27T08:00:00.000000+00:00",
            },
        }

        v2_migrado = migrar_manifesto_v1_para_v2(v1_data, data_dir=self.base_dir)

        # Verificação das propriedades migradas
        src_info = v2_migrado["sources"]["twitter"]
        self.assertEqual(src_info["status"], "success")
        self.assertEqual(src_info["count"], 2)
        self.assertEqual(src_info["quality"], "legacy_unverified")
        self.assertEqual(len(src_info["sha256"]), 64)

        # Validação de conformidade com o contrato de schema v2
        self.assertTrue(
            validar_schema_manifesto(v2_migrado),
            "Manifesto v1 migrado com arquivo válido deve ser aceito pelo schema v2",
        )

    def test_integracao_migracao_v1_com_arquivo_json_vazio(self):
        """Cenário 2: Manifesto v1 com arquivo JSON válido contendo lista vazia."""
        github_file = self.base_dir / "github_trending.json"
        github_file.write_text("[]", encoding="utf-8")

        v1_data = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "github": "2026-10-27T08:00:00.000000+00:00",
            },
        }

        v2_migrado = migrar_manifesto_v1_para_v2(v1_data, data_dir=self.base_dir)

        # Verificação das propriedades migradas
        src_info = v2_migrado["sources"]["github"]
        self.assertEqual(src_info["status"], "empty")
        self.assertEqual(src_info["count"], 0)
        self.assertEqual(src_info["quality"], "legacy_unverified")
        self.assertEqual(len(src_info["sha256"]), 64)

        # Validação de conformidade com o contrato de schema v2
        self.assertTrue(
            validar_schema_manifesto(v2_migrado),
            "Manifesto v1 migrado com lista vazia deve ser aceito pelo schema v2",
        )

    def test_integracao_migracao_v1_com_arquivo_inexistente(self):
        """Cenário 3: Manifesto v1 com arquivo inexistente em disco."""
        # Não cria o arquivo hf_papers.json no disco
        v1_data = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "papers": "2026-10-27T08:00:00.000000+00:00",
            },
        }

        v2_migrado = migrar_manifesto_v1_para_v2(v1_data, data_dir=self.base_dir)

        # Verificação: arquivo ausente NÃO declara sucesso nem gera hash fictício
        src_info = v2_migrado["sources"]["papers"]
        self.assertEqual(src_info["status"], "failed")
        self.assertEqual(src_info["count"], 0)
        self.assertEqual(src_info["quality"], "legacy_unverified")
        self.assertIsNone(src_info["sha256"], "Arquivo ausente não deve ter sha256 gerado")

        # Validação de conformidade com o contrato de schema v2:
        # Schema v2 aceita status 'failed' com sha256=None para registrar explicitamente a falha da fonte
        self.assertTrue(
            validar_schema_manifesto(v2_migrado),
            "Manifesto v1 migrado com fonte inexistente (status=failed, sha256=None) é aceito pelo schema v2",
        )

    def test_integracao_migracao_v1_com_json_corrompido(self):
        """Cenário 4: Manifesto v1 com arquivo contendo JSON corrompido/inválido."""
        papers_file = self.base_dir / "hf_papers.json"
        papers_file.write_text('{"syntax_error": [corrompido', encoding="utf-8")

        v1_data = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "papers": "2026-10-27T08:00:00.000000+00:00",
            },
        }

        v2_migrado = migrar_manifesto_v1_para_v2(v1_data, data_dir=self.base_dir)

        # Verificação: JSON corrompido é classificado como falha, registrando o hash físico dos bytes
        src_info = v2_migrado["sources"]["papers"]
        self.assertEqual(src_info["status"], "failed", "JSON corrompido NÃO pode ser declarado como sucesso")
        self.assertEqual(src_info["count"], 0)
        self.assertEqual(src_info["quality"], "legacy_unverified")
        self.assertEqual(len(src_info["sha256"]), 64, "Hash dos bytes físicos corrompidos deve ser registrado")

        # Validação de conformidade com o contrato de schema v2:
        # É aceito pelo schema v2 como registro de fonte em falha
        self.assertTrue(
            validar_schema_manifesto(v2_migrado),
            "Manifesto v1 migrado com JSON corrompido (status=failed) é aceito pelo schema v2",
        )

    def test_integracao_migracao_v1_com_timestamp_invalido_rejeitado_pelo_contrato_v2(self):
        """Cenário 5: Manifesto v1 com timestamp inválido é rejeitado pelo contrato v2."""
        # Caso 5A: timestamp de fonte corrompido
        v1_com_fonte_invalida = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "twitter": "timestamp_corrompido_legado",
            },
        }

        v2_migrado_5a = migrar_manifesto_v1_para_v2(v1_com_fonte_invalida, data_dir=self.base_dir)

        # Preserva o valor histórico cru sem inventar datetime.now()
        self.assertEqual(v2_migrado_5a["sources"]["twitter"]["updated_at"], "timestamp_corrompido_legado")

        # Explicitamente REJEITADO pelo validador de schema v2 da Spec 0007 (exige ISO 8601)
        self.assertFalse(
            validar_schema_manifesto(v2_migrado_5a),
            "Manifesto migrado com timestamp de fonte inválido deve ser REJEITADO pelo schema v2",
        )
        self.assertFalse(is_source_fresh(v2_migrado_5a["sources"]["twitter"]["updated_at"]))

        # Caso 5B: collected_at raiz corrompido
        v1_com_collected_at_invalido = {
            "collected_at": "data_coleta_invalida",
            "sources": {
                "twitter": "2026-10-27T08:00:00.000000+00:00",
            },
        }

        v2_migrado_5b = migrar_manifesto_v1_para_v2(v1_com_collected_at_invalido, data_dir=self.base_dir)

        # Preserva o valor histórico cru sem inventar datetime.now()
        self.assertEqual(v2_migrado_5b["collected_at"], "data_coleta_invalida")

        # Explicitamente REJEITADO pelo validador de schema v2
        self.assertFalse(
            validar_schema_manifesto(v2_migrado_5b),
            "Manifesto migrado com collected_at raiz inválido deve ser REJEITADO pelo schema v2",
        )


if __name__ == "__main__":
    unittest.main()
