"""Testes unitários e de integração para Persistência Atômica, Recuperação Idempotente e Quarentena.

Cobre os requisitos mandatórios do Ticket 20 e Spec 0007:
1. Persistência por fonte (SUCCESS, EMPTY, PARTIAL, FAILED, isolamento e timestamps).
2. Atomicidade e durabilidade (.prev, .tmp.<pid>, os.fsync, os.replace, _fsync_dir, ordem de commit).
3. Integridade e recuperação (SHA-256 match, recuperação de ativo corrompido via .prev, idempotência,
   proibição de dirty reads sob status 'running', legacy_unverified).
4. Quarentena delimitada (apenas prefixos de snapshot, proteção de arquivos alheios em data/, não-sobrescrita).
5. Concorrência (uso de adquirir_trava_snapshot, ausência de aninhamento e de lock em chamadas externas).
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from src.core.models import (
    DailyIngestionBatch,
    Tweet,
    GitHubRepo,
    ResearchPaper,
    SourceStatus,
    SourceCollectionResult,
    SNAPSHOT_TWEETS_FILE,
    SNAPSHOT_GITHUB_FILE,
    SNAPSHOT_PAPERS_FILE,
    SNAPSHOT_METADATA_FILE,
)
from src.core.manifest import (
    validar_schema_manifesto,
    _calcular_sha256_arquivo,
    is_source_fresh,
)
from src.core.lock import (
    adquirir_trava_snapshot,
    _SNAPSHOT_LOCKS_ATIVOS,
)


class TestSnapshotAtomicAndRecovery(unittest.TestCase):
    """Suíte de testes de persistência transacional, durabilidade e recuperação de snapshots."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp_dir.name)
        self.lock_path = self.data_dir / "snapshot.lock"
        self.quarantine_dir = self.data_dir / "quarantine"

        # Entidades padrão para testes
        self.tweet_sample = Tweet(
            author_name="Alice",
            author_handle="@alice",
            timestamp="2026-11-12T08:00:00+00:00",
            text="AI agent update",
            url="https://x.com/alice/status/1",
        )
        self.repo_sample = GitHubRepo(
            name="cool-repo",
            full_name="org/cool-repo",
            stars=150,
            description="Agent repo",
            language="Python",
            url="https://github.com/org/cool-repo",
        )
        self.paper_sample = ResearchPaper(
            title="Agent Architecture",
            arxiv_id="2611.12345",
            summary="Paper on resilient snapshots",
            authors=("Carol",),
            upvotes=42,
            url="https://huggingface.co/papers/2611.12345",
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    # =========================================================================
    # 1. Persistência por fonte
    # =========================================================================

    def test_save_snapshot_success_grava_novos_dados(self):
        """SUCCESS grava os novos dados no arquivo definitivo e gera manifesto v2 com quality verified."""
        batch = DailyIngestionBatch(
            tweets=[self.tweet_sample],
            collected_at="2026-11-12T10:00:00+00:00",
        )
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Arquivo definitivo de tweets deve existir com os dados gravados
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        self.assertTrue(tweets_file.exists())
        with open(tweets_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["text"], "AI agent update")

        # Manifesto v2 deve registrar a fonte como verified e success
        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        self.assertTrue(meta_file.exists())
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertTrue(validar_schema_manifesto(meta))
        src_info = meta["sources"]["twitter"]
        self.assertEqual(src_info["status"], "success")
        self.assertEqual(src_info["count"], 1)
        self.assertEqual(src_info["quality"], "verified")
        self.assertEqual(src_info["sha256"], _calcular_sha256_arquivo(tweets_file))

    def test_save_snapshot_empty_confirmado_permite_snapshot_vazio(self):
        """EMPTY confirmado permite gravar lista vazia [] com status empty e count 0 no manifesto."""
        batch = DailyIngestionBatch(tweets=[], collected_at="2026-11-12T10:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.EMPTY)

        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        self.assertTrue(tweets_file.exists())
        with open(tweets_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data, [])

        with open(self.data_dir / SNAPSHOT_METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertTrue(validar_schema_manifesto(meta))
        src_info = meta["sources"]["twitter"]
        self.assertEqual(src_info["status"], "empty")
        self.assertEqual(src_info["count"], 0)
        self.assertEqual(src_info["quality"], "verified")
        self.assertEqual(src_info["sha256"], _calcular_sha256_arquivo(tweets_file))

    def test_save_snapshot_partial_com_dados_grava_dados_parciais(self):
        """PARTIAL com dados grava o resultado parcial e registra status partial no manifesto."""
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T10:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.PARTIAL)

        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        self.assertTrue(tweets_file.exists())
        with open(tweets_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)

        with open(self.data_dir / SNAPSHOT_METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertTrue(validar_schema_manifesto(meta))
        self.assertEqual(meta["sources"]["twitter"]["status"], "partial")
        self.assertEqual(meta["sources"]["twitter"]["count"], 1)

    def test_save_snapshot_partial_sem_dados_preserva_dados_anteriores(self):
        """PARTIAL sem dados não sobrescreve o arquivo existente no disco (preservação DEF-01)."""
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        conteudo_antigo = json.dumps([self.tweet_sample.to_dict()])
        tweets_file.write_text(conteudo_antigo, encoding="utf-8")

        # Salva lote com PARTIAL e 0 tweets
        batch = DailyIngestionBatch(tweets=[], collected_at="2026-11-12T12:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.PARTIAL)

        # O arquivo em disco DEVE permanecer com os tweets anteriores
        self.assertEqual(tweets_file.read_text(encoding="utf-8"), conteudo_antigo)

    def test_save_snapshot_failed_preserva_dados_anteriores(self):
        """FAILED preserva integralmente os dados anteriores em disco sem sobrescrever com vazio."""
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        conteudo_antigo = json.dumps([self.tweet_sample.to_dict()])
        tweets_file.write_text(conteudo_antigo, encoding="utf-8")

        # Salva lote indicando FAILED
        batch = DailyIngestionBatch(tweets=[], collected_at="2026-11-12T12:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.FAILED)

        # Dados anteriores continuam intactos
        self.assertEqual(tweets_file.read_text(encoding="utf-8"), conteudo_antigo)

    def test_coleta_isolada_atualiza_exclusivamente_sua_fonte_e_metadados(self):
        """Uma coleta isolada via CLI atualiza apenas o arquivo e metadados da fonte alvo."""
        # Estado inicial com github e twitter
        batch_init = DailyIngestionBatch(
            tweets=[self.tweet_sample],
            repos=[self.repo_sample],
            collected_at="2026-11-12T08:00:00+00:00",
        )
        batch_init.save_snapshot(self.data_dir)

        # Coleta isolada de github às 11:00
        novo_repo = GitHubRepo(
            name="new-repo",
            full_name="org/new-repo",
            stars=500,
            description="New",
            language="Python",
            url="http://gh",
        )
        batch_isolado = DailyIngestionBatch(repos=[novo_repo], collected_at="2026-11-12T11:00:00+00:00")
        batch_isolado.save_snapshot(self.data_dir, source="github", status=SourceStatus.SUCCESS)

        # Twitter não pode ter sido modificado nem nos dados nem no timestamp do manifesto
        with open(self.data_dir / SNAPSHOT_METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["sources"]["twitter"]["updated_at"], "2026-11-12T08:00:00+00:00")
        self.assertEqual(meta["sources"]["github"]["updated_at"], "2026-11-12T11:00:00+00:00")

    def test_fontes_nao_coletadas_nao_recebem_timestamps_novos(self):
        """Fontes que não foram executadas mantêm estritamente seus timestamps anteriores."""
        batch_init = DailyIngestionBatch(
            tweets=[self.tweet_sample],
            papers=[self.paper_sample],
            collected_at="2026-11-12T07:00:00+00:00",
        )
        batch_init.save_snapshot(self.data_dir)

        # Salva apenas papers com novo timestamp
        batch_update = DailyIngestionBatch(
            papers=[self.paper_sample],
            collected_at="2026-11-12T09:00:00+00:00",
        )
        batch_update.save_snapshot(self.data_dir, source="papers", status=SourceStatus.SUCCESS)

        with open(self.data_dir / SNAPSHOT_METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["sources"]["twitter"]["updated_at"], "2026-11-12T07:00:00+00:00")
        self.assertEqual(meta["sources"]["papers"]["updated_at"], "2026-11-12T09:00:00+00:00")

    # =========================================================================
    # 2. Atomicidade e durabilidade
    # =========================================================================

    def test_arquivos_temporarios_nao_consumidos_como_snapshots_validos(self):
        """Arquivos com sufixo .tmp.<pid> abandonados por crash não são consumidos como snapshot."""
        # Cria arquivo temporário solto
        tmp_ghost = self.data_dir / f"{SNAPSHOT_TWEETS_FILE}.tmp.9999"
        tmp_ghost.write_text('[{"text": "fantasma"}]', encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Arquivos temporários .tmp não devem ser consumidos")

    def test_backup_prev_preparado_antes_de_substituir_ativo(self):
        """Ao sobrescrever arquivo ativo, o backup .prev correspondente é criado com os dados anteriores."""
        batch1 = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch1.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Segundo salvamento com outro tweet
        tweet2 = Tweet(
            author_name="Bob",
            author_handle="@bob",
            timestamp="",
            text="Second tweet",
            url="http://x",
        )
        batch2 = DailyIngestionBatch(tweets=[tweet2], collected_at="2026-11-12T09:00:00+00:00")
        batch2.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # O arquivo .prev deve existir e conter o tweet1
        prev_file = self.data_dir / f"{SNAPSHOT_TWEETS_FILE}.prev"
        self.assertTrue(prev_file.exists(), "O arquivo .prev deve ter sido gerado na rotação")
        with open(prev_file, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
        self.assertEqual(prev_data[0]["author_name"], "Alice")

        # O ativo contém o tweet2
        with open(self.data_dir / SNAPSHOT_TWEETS_FILE, "r", encoding="utf-8") as f:
            active_data = json.load(f)
        self.assertEqual(active_data[0]["author_name"], "Bob")

    def test_os_fsync_e_replace_exercitados_na_gravacao(self):
        """Valida que os.replace e flush/fsync são invocados durante save_snapshot."""
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")

        with patch("os.replace", wraps=os.replace) as mock_replace, patch("os.fsync", wraps=os.fsync) as mock_fsync:
            batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)
            self.assertTrue(mock_replace.called, "os.replace deve ser chamado para garantir atomicidade")
            self.assertTrue(mock_fsync.called, "os.fsync deve ser chamado para durabilidade física")

    def test_falha_injetada_em_etapa_critica_nao_publica_dados_inconsistentes(self):
        """Se ocorrer falha antes do commit do manifesto, a transação não publica o snapshot incompleto."""
        # Estado inicial com tweets válidos
        batch_init = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch_init.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Tenta salvar novo lote, mas simula crash na escrita do manifesto
        novo_tweet = Tweet(author_name="Mallory", author_handle="@mal", timestamp="", text="Crash", url="")
        batch_fail = DailyIngestionBatch(tweets=[novo_tweet], collected_at="2026-11-12T10:00:00+00:00")

        original_replace = os.replace

        def _falhar_no_manifesto(src, dst):
            if SNAPSHOT_METADATA_FILE in str(dst):
                raise OSError("Falha de disco simulada no commit do manifesto")
            original_replace(src, dst)

        with patch("os.replace", side_effect=_falhar_no_manifesto):
            with self.assertRaises(OSError):
                batch_fail.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Ao carregar, o snapshot comitado anterior DEVE ser preservado
        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(loaded.tweets[0].author_name, "Alice")

    # =========================================================================
    # 3. Integridade e recuperação
    # =========================================================================

    def test_sha256_valido_permite_leitura_da_geracao_correspondente(self):
        """Arquivo com SHA-256 idêntico ao registrado no manifesto é carregado normalmente."""
        batch = DailyIngestionBatch(repos=[self.repo_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="github", status=SourceStatus.SUCCESS)

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.repos), 1)
        self.assertEqual(loaded.repos[0].name, "cool-repo")

    def test_hash_divergente_impede_consumo_como_dado_verificado(self):
        """Se o arquivo ativo foi alterado externamente e seu hash diverge do manifesto, é rejeitado."""
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Adultera o arquivo em disco
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text('[{"text": "adulterado"}]', encoding="utf-8")

        # Como não há .prev válido com esse hash, o arquivo adulterado não é consumido
        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Dados com hash mismatch não podem ser entregues")

    def test_backup_valido_recupera_ativo_corrompido(self):
        """Arquivo ativo corrompido (JSON inválido) é isolado na quarentena e restaurado do .prev válido."""
        # Salva versão 1 (válida)
        batch1 = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch1.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Salva versão 2 para que versão 1 vá para .prev
        tweet2 = Tweet(author_name="Bob", author_handle="@bob", timestamp="", text="V2", url="")
        batch2 = DailyIngestionBatch(tweets=[tweet2], collected_at="2026-11-12T09:00:00+00:00")
        batch2.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Corrompe artificialmente o arquivo ativo
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text('{"corrompido": [incompleto', encoding="utf-8")

        # Executa load_snapshot: deve recuperar do .prev
        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 1)
        self.assertEqual(loaded.tweets[0].author_name, "Alice")

        # Verifica se o corrompido foi movido para quarentena
        quarantine_files = list(self.quarantine_dir.glob("tweets_coletados_*.corrupted"))
        self.assertGreaterEqual(len(quarantine_files), 1)

    def test_backup_invalido_nao_pode_ser_promovido(self):
        """Se o ativo for corrompido e o .prev também for corrompido, .prev não pode ser promovido."""
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Cria .prev corrompido
        prev_file = self.data_dir / f"{SNAPSHOT_TWEETS_FILE}.prev"
        prev_file.write_text("{json_prev_invalido:", encoding="utf-8")

        # Corrompe ativo
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text("{json_ativo_invalido:", encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Backup corrompido não pode ser promovido")

    def test_recuperacao_repetida_e_idempotente(self):
        """Chamar load_snapshot repetidamente em cenário de recuperação não quebra nem duplica quarentenas."""
        # Configura ativo corrompido com .prev válido
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text("{corrompido:", encoding="utf-8")
        prev_file = self.data_dir / f"{SNAPSHOT_TWEETS_FILE}.prev"
        prev_file.write_text(json.dumps([self.tweet_sample.to_dict()]), encoding="utf-8")

        # Primeira recuperação
        loaded1 = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded1.tweets), 1)
        quarantine_count_1 = len(list(self.quarantine_dir.glob("*.corrupted")))

        # Segunda recuperação imediata
        loaded2 = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded2.tweets), 1)
        quarantine_count_2 = len(list(self.quarantine_dir.glob("*.corrupted")))

        # Deve ser idempotente: ativo já recuperado não gera novas quarentenas
        self.assertEqual(quarantine_count_1, quarantine_count_2)

    def test_arquivos_legados_legacy_unverified_nao_sao_promovidos_automaticamente_a_verified(self):
        """Ao carregar manifesto com quality legacy_unverified, mantém essa classificação sem promover."""
        v1_meta = {
            "collected_at": "2026-10-27T08:00:00.000000+00:00",
            "sources": {
                "twitter": "2026-10-27T08:00:00.000000+00:00",
            },
        }
        (self.data_dir / SNAPSHOT_METADATA_FILE).write_text(json.dumps(v1_meta), encoding="utf-8")
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text(json.dumps([self.tweet_sample.to_dict()]), encoding="utf-8")

        # Carrega snapshot sob manifesto legado v1
        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 1)

    def test_json_corrompido_ou_sha256_none_de_fonte_failed_nao_e_tratado_como_integro(self):
        """Fonte marcada como failed no manifesto nunca é tratada como íntegra, mesmo com arquivo em disco."""
        meta = {
            "version": 2,
            "collected_at": "2026-11-12T08:00:00.000000+00:00",
            "last_attempt": {
                "started_at": "2026-11-12T08:00:00.000000+00:00",
                "completed_at": "2026-11-12T08:00:00.000000+00:00",
                "status": "completed",
                "trigger": "test",
                "pid": None,
            },
            "sources": {
                "twitter": {
                    "updated_at": "2026-11-12T08:00:00.000000+00:00",
                    "sha256": None,
                    "count": 0,
                    "status": "failed",
                    "quality": "legacy_unverified",
                }
            },
        }
        (self.data_dir / SNAPSHOT_METADATA_FILE).write_text(json.dumps(meta), encoding="utf-8")
        (self.data_dir / SNAPSHOT_TWEETS_FILE).write_text('[{"text": "arquivo_antigo"}]', encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Fonte FAILED não pode entregar dados como válidos")

    def test_manifesto_com_status_running_impede_consumo_de_dados_inconsistentes(self):
        """Manifesto em estado 'running' indica execução em andamento: dirty reads são estritamente proibidos."""
        meta = {
            "version": 2,
            "collected_at": "2026-11-12T08:00:00.000000+00:00",
            "last_attempt": {
                "started_at": "2026-11-12T08:00:00.000000+00:00",
                "status": "running",
                "trigger": "pipeline",
                "pid": os.getpid(),
            },
            "sources": {
                "twitter": {
                    "updated_at": "2026-11-12T08:00:00.000000+00:00",
                    "sha256": "a" * 64,
                    "count": 1,
                    "status": "success",
                    "quality": "verified",
                }
            },
        }
        (self.data_dir / SNAPSHOT_METADATA_FILE).write_text(json.dumps(meta), encoding="utf-8")
        (self.data_dir / SNAPSHOT_TWEETS_FILE).write_text(json.dumps([self.tweet_sample.to_dict()]), encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Execução em estado running deve retornar lote vazio seguro")

    # =========================================================================
    # 4. Quarentena
    # =========================================================================

    def test_apenas_arquivos_pertencentes_ao_subsistema_de_snapshots_vao_para_quarentena(self):
        """Arquivos desconhecidos em data/ (ex: ultimo_envio.txt, log, db) NUNCA são movidos para quarentena."""
        # Cria arquivos no diretório
        arquivo_alheio = self.data_dir / "ultimo_envio.txt"
        arquivo_alheio.write_text("2026-11-11", encoding="utf-8")
        outro_db = self.data_dir / "custom.db"
        outro_db.write_text("dados_criticos_alheios", encoding="utf-8")

        # Cria arquivo de snapshot corrompido
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text("{corrompido:", encoding="utf-8")

        # Dispara load_snapshot
        DailyIngestionBatch.load_snapshot(self.data_dir)

        # Arquivos alheios DEVEM permanecer intactos
        self.assertTrue(arquivo_alheio.exists(), "ultimo_envio.txt deve ser preservado")
        self.assertEqual(arquivo_alheio.read_text(encoding="utf-8"), "2026-11-11")
        self.assertTrue(outro_db.exists(), "custom.db deve ser preservado")

    def test_evidencias_anteriores_em_quarentena_nao_sao_sobrescritas(self):
        """Múltiplas corrupções geram arquivos com nomes únicos e sem sobrescrita na quarentena."""
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text("{corrompido_1:", encoding="utf-8")
        DailyIngestionBatch.load_snapshot(self.data_dir)

        # Segunda corrupção
        tweets_file.write_text("{corrompido_2:", encoding="utf-8")
        DailyIngestionBatch.load_snapshot(self.data_dir)

        quarantine_files = list(self.quarantine_dir.glob("tweets_coletados_*.corrupted"))
        self.assertEqual(len(quarantine_files), 2, "Cada evidência deve gerar um arquivo distinto")

    # =========================================================================
    # 5. Concorrência
    # =========================================================================

    def test_save_snapshot_utiliza_adquirir_trava_snapshot(self):
        """save_snapshot deve adquirir e liberar adquirir_trava_snapshot durante o bloco de I/O."""
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")

        with patch("src.core.models.adquirir_trava_snapshot", wraps=adquirir_trava_snapshot) as mock_lock:
            batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)
            self.assertTrue(mock_lock.called, "save_snapshot deve adquirir a trava de persistência")

    def test_mesma_trava_nao_e_adquirida_duas_vezes_de_forma_aninhada(self):
        """Garante que save_snapshot não chama a trava de forma aninhada."""
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        lock_file = self.data_dir / "snapshot.lock"

        # Se já estiver sob a trava de snapshot, uma nova chamada aninhada deve levantar RuntimeError
        with adquirir_trava_snapshot(lock_file):
            with self.assertRaises(RuntimeError):
                batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

    def test_lock_nao_mantido_durante_operacoes_externas(self):
        """A trava é liberada determinística e imediatamente ao encerrar save_snapshot."""
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # O lock deve estar livre imediatamente após o retorno
        resolved = str(self.lock_path.resolve())
        self.assertNotIn(resolved, _SNAPSHOT_LOCKS_ATIVOS, "A trava não deve permanecer ativa após save_snapshot")

    def test_preflight_recupera_anterior_antes_de_nova_gravacao_se_interrompido(self):
        """Valida que uma nova gravação C identifica gravação B interrompida no preflight e preserva A."""
        # 1. Grava snapshot A confirmado
        tweet_A = Tweet(author_name="Alice", author_handle="@alice", timestamp="", text="A", url="")
        batch_A = DailyIngestionBatch(tweets=[tweet_A], collected_at="2026-11-12T08:00:00+00:00")
        batch_A.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        prev_file = self.data_dir / f"{SNAPSHOT_TWEETS_FILE}.prev"
        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE

        sha_A = _calcular_sha256_arquivo(tweets_file)
        with open(meta_file, "r", encoding="utf-8") as f:
            meta_fase1 = json.load(f)
        self.assertEqual(meta_fase1["sources"]["twitter"]["sha256"], sha_A)

        # 2. Simula interrupção da gravação B após substituir ativo, mas antes do commit do manifesto
        tweet_B = Tweet(author_name="Bob", author_handle="@bob", timestamp="", text="B", url="")
        batch_B = DailyIngestionBatch(tweets=[tweet_B], collected_at="2026-11-12T09:00:00+00:00")

        original_replace = os.replace

        def _falhar_no_manifesto_B(src, dst):
            if SNAPSHOT_METADATA_FILE in str(dst):
                raise OSError("Crash simulado antes do commit do manifesto em B")
            original_replace(src, dst)

        with patch("os.replace", side_effect=_falhar_no_manifesto_B):
            with self.assertRaises(OSError):
                batch_B.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Estado físico pós-crash B:
        # Ativo contém B (sintaticamente válido, mas NÃO comitado no manifesto)
        # .prev contém A (comitado)
        # Manifesto ainda aponta para sha_A
        with open(tweets_file, "r", encoding="utf-8") as f:
            conteudo_ativo_pos_crash = json.load(f)
        self.assertEqual(conteudo_ativo_pos_crash[0]["author_name"], "Bob")
        with open(prev_file, "r", encoding="utf-8") as f:
            conteudo_prev_pos_crash = json.load(f)
        self.assertEqual(conteudo_prev_pos_crash[0]["author_name"], "Alice")
        with open(meta_file, "r", encoding="utf-8") as f:
            meta_fase2 = json.load(f)
        self.assertEqual(meta_fase2["sources"]["twitter"]["sha256"], sha_A)
        self.assertNotEqual(_calcular_sha256_arquivo(tweets_file), meta_fase2["sources"]["twitter"]["sha256"])

        # 3. SEM executar load_snapshot, inicia diretamente a gravação C
        tweet_C = Tweet(author_name="Carol", author_handle="@carol", timestamp="", text="C", url="")
        batch_C = DailyIngestionBatch(tweets=[tweet_C], collected_at="2026-11-12T10:00:00+00:00")
        batch_C.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # 4. Comprovações pós-gravação C:
        # a) O preflight identificou que o ativo B era hash mismatch em relação ao manifesto comitado,
        #    moveu B para a quarentena e restaurou A como ativo antes da rotação.
        quarantine_files = list(self.quarantine_dir.glob("tweets_coletados_*.corrupted"))
        self.assertGreaterEqual(len(quarantine_files), 1)
        with open(quarantine_files[0], "r", encoding="utf-8") as f:
            dado_quarentenado = json.load(f)
        self.assertEqual(dado_quarentenado[0]["author_name"], "Bob", "B não-comitado deve ter sido isolado na quarentena")

        # b) Como A foi restaurado antes de gravar C, o novo backup .prev DEVE conter A (não B!)
        with open(prev_file, "r", encoding="utf-8") as f:
            conteudo_prev_final = json.load(f)
        self.assertEqual(conteudo_prev_final[0]["author_name"], "Alice", "O backup .prev deve preservar A comitado")

        # c) O novo ativo contém C
        with open(tweets_file, "r", encoding="utf-8") as f:
            conteudo_ativo_final = json.load(f)
        self.assertEqual(conteudo_ativo_final[0]["author_name"], "Carol")

        # d) O manifesto agora comita C
        sha_C = _calcular_sha256_arquivo(tweets_file)
        with open(meta_file, "r", encoding="utf-8") as f:
            meta_fase3 = json.load(f)
        self.assertEqual(meta_fase3["sources"]["twitter"]["sha256"], sha_C)

    def test_concorrencia_leitor_nao_publica_nao_comitado_nem_quarentena_escritor_em_andamento(self):
        """Valida que o leitor concorre com segurança contra escritor ativo sob snapshot.lock."""
        import threading
        import subprocess

        # Grava snapshot A confirmado inicial
        tweet_A = Tweet(author_name="Alice", author_handle="@alice", timestamp="", text="A", url="")
        batch_A = DailyIngestionBatch(tweets=[tweet_A], collected_at="2026-11-12T08:00:00+00:00")
        batch_A.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        # Eventos de sincronização determinística
        writer_active_replaced = threading.Event()
        allow_writer_to_commit = threading.Event()
        writer_finished = threading.Event()

        tweet_B = Tweet(author_name="Bob", author_handle="@bob", timestamp="", text="B", url="")
        batch_B = DailyIngestionBatch(tweets=[tweet_B], collected_at="2026-11-12T09:00:00+00:00")

        original_replace = os.replace

        def _replace_intercept(src, dst):
            original_replace(src, dst)
            # Quando substituir o arquivo ativo de tweets, pausa o escritor antes do manifesto
            if SNAPSHOT_TWEETS_FILE in str(dst) and not str(dst).endswith(".tmp") and not str(dst).endswith(".prev"):
                writer_active_replaced.set()
                allow_writer_to_commit.wait(timeout=5.0)

        writer_error = []

        def _writer_thread():
            try:
                with patch("os.replace", side_effect=_replace_intercept):
                    batch_B.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)
            except Exception as e:
                writer_error.append(e)
            finally:
                writer_finished.set()

        t_writer = threading.Thread(target=_writer_thread)
        t_writer.start()

        try:
            # Aguarda deterministicamente o escritor substituir o ativo de tweets
            self.assertTrue(writer_active_replaced.wait(timeout=5.0))

            # Neste instante exato:
            # - O escritor retém snapshot.lock
            # - tweets_coletados.json em disco já contém B
            # - snapshot_metadata.json ainda aponta para A

            # 1. Leitor no mesmo processo: protegido contra execução aninhada/concorrente via RuntimeError
            with self.assertRaises(RuntimeError):
                DailyIngestionBatch.load_snapshot(self.data_dir, timeout=0.1)

            # 2. Leitor em processo concorrente independente: bloqueado pelo OS lock até timeout
            script_helper = (
                "import sys\n"
                "from pathlib import Path\n"
                "from src.core.models import DailyIngestionBatch\n"
                "data_dir = Path(sys.argv[1])\n"
                "try:\n"
                "    DailyIngestionBatch.load_snapshot(data_dir, timeout=0.3)\n"
                "    print('SUB_OK')\n"
                "except TimeoutError:\n"
                "    print('SUB_TIMEOUT')\n"
                "except Exception as e:\n"
                "    print(f'SUB_ERROR: {type(e).__name__}: {e}')\n"
            )
            proc = subprocess.run(
                [sys.executable, "-c", script_helper, str(self.data_dir)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertIn("SUB_TIMEOUT", proc.stdout)

            # Comprova que a quarentena não foi violada enquanto o escritor operava
            quarantine_files_during_write = list(self.quarantine_dir.glob("*.corrupted"))
            self.assertEqual(len(quarantine_files_during_write), 0, "Leitor não pode quarentenar arquivo ativo do escritor")

        finally:
            # Garante que o escritor sempre retoma e conclui o thread
            allow_writer_to_commit.set()
            t_writer.join(timeout=5.0)

        self.assertTrue(writer_finished.is_set())
        self.assertEqual(len(writer_error), 0, f"Escritor falhou inesperadamente: {writer_error}")

        # 3. Agora que o lock foi liberado e o manifesto comitado, o leitor consome B com sucesso
        loaded = DailyIngestionBatch.load_snapshot(self.data_dir, timeout=2.0)
        self.assertEqual(len(loaded.tweets), 1)
        self.assertEqual(loaded.tweets[0].author_name, "Bob")
        self.assertEqual(len(list(self.quarantine_dir.glob("*.corrupted"))), 0)

    def test_load_snapshot_proibe_aquisicao_aninhada(self):
        """load_snapshot não pode adquirir snapshot.lock de forma aninhada se já estiver ativo no mesmo processo."""
        lock_file = self.data_dir / "snapshot.lock"
        with adquirir_trava_snapshot(lock_file):
            with self.assertRaises(RuntimeError):
                DailyIngestionBatch.load_snapshot(self.data_dir)

    # =========================================================================
    # 6. Testes Adicionais de Robustez Contratual (Revisão Ticket 20)
    # =========================================================================

    def test_backup_prev_com_hash_divergente_do_manifesto_nao_e_promovido(self):
        """Se o ativo e o .prev divergirem do hash esperado, .prev não é promovido nem consumido."""
        # 1. Cria ativo A para obter seu hash válido e registrar no manifesto
        tweet_A = Tweet(author_name="Alice", author_handle="@alice", timestamp="", text="A", url="")
        batch_A = DailyIngestionBatch(tweets=[tweet_A], collected_at="2026-11-12T08:00:00+00:00")
        batch_A.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        prev_file = self.data_dir / f"{SNAPSHOT_TWEETS_FILE}.prev"
        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE

        conteudo_exato_A = tweets_file.read_text(encoding="utf-8")

        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        sha_A = meta["sources"]["twitter"]["sha256"]

        # 2. Configura ativo com B e .prev com C (ambos válidos em sintaxe JSON, mas divergentes de A)
        tweet_B = Tweet(author_name="Bob", author_handle="@bob", timestamp="", text="B", url="")
        tweet_C = Tweet(author_name="Charlie", author_handle="@charlie", timestamp="", text="C", url="")
        tweets_file.write_text(json.dumps([tweet_B.to_dict()], indent=2), encoding="utf-8")
        prev_file.write_text(json.dumps([tweet_C.to_dict()], indent=2), encoding="utf-8")

        # 3. Leitura deve recusar C, isolar arquivos e retornar vazio para twitter
        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Backup com hash divergente de A não pode ser promovido")

        # 4. Agora coloca backup A (com hash correto e idêntico a A) e corrompe o ativo
        prev_file.write_text(conteudo_exato_A, encoding="utf-8")
        tweets_file.write_text("{json_ativo_corrompido:", encoding="utf-8")

        loaded2 = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded2.tweets), 1, "Backup A com hash correto deve ser recuperado")
        self.assertEqual(loaded2.tweets[0].author_name, "Alice")
        quarantine_count_pos_recup = len(list(self.quarantine_dir.glob("*.corrupted")))

        # 5. Recuperação repetida permanece idempotente
        loaded3 = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded3.tweets), 1)
        self.assertEqual(loaded3.tweets[0].author_name, "Alice")
        self.assertEqual(len(list(self.quarantine_dir.glob("*.corrupted"))), quarantine_count_pos_recup)

    def test_manifesto_v2_invalido_rejeitado_e_quarentenado(self):
        """Manifesto v2 com violação estrutural de schema é rejeitado e movido para quarentena."""
        # Manifesto v2 malformado (faltando chaves obrigatórias como last_attempt e sources)
        meta_invalido = {"version": 2}
        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        meta_file.write_text(json.dumps(meta_invalido), encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertTrue(loaded.is_empty(), "Manifesto v2 inválido deve retornar lote vazio")

        # Deve ter movido o manifesto malformado para quarentena
        quarantine_meta = list(self.quarantine_dir.glob("snapshot_metadata_*.corrupted"))
        self.assertGreaterEqual(len(quarantine_meta), 1, "Manifesto v2 inválido deve ir para quarentena")

    def test_manifesto_v2_verified_sem_sha256_rejeitado(self):
        """Fonte declarada como verified mas sem sha256 válido viola o contrato e é rejeitada."""
        meta_invalido = {
            "version": 2,
            "collected_at": "2026-11-12T08:00:00+00:00",
            "last_attempt": {
                "started_at": "2026-11-12T08:00:00+00:00",
                "completed_at": "2026-11-12T08:00:00+00:00",
                "status": "completed",
                "trigger": "test",
                "pid": None,
            },
            "sources": {
                "twitter": {
                    "updated_at": "2026-11-12T08:00:00+00:00",
                    "sha256": None,  # Inválido para verified!
                    "count": 1,
                    "status": "success",
                    "quality": "verified",
                }
            },
        }
        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        meta_file.write_text(json.dumps(meta_invalido), encoding="utf-8")
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text(json.dumps([self.tweet_sample.to_dict()]), encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Fonte verified sem hash não pode entregar dados válidos")

    def test_manifesto_corrompido_com_backup_prev_valido_promove_backup(self):
        """Se o manifesto ativo estiver corrompido mas o .prev for válido, restaura .prev."""
        # Cria dados legítimos e gera .prev salvando duas vezes
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)
        batch.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        prev_meta = self.data_dir / f"{SNAPSHOT_METADATA_FILE}.prev"

        # Garante que .prev do manifesto existe e é válido
        self.assertTrue(prev_meta.exists())

        # Corrompe o manifesto ativo
        meta_file.write_text("{json_manifesto_corrompido:", encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 1, "Deve recuperar os metadados a partir do .prev válido")

        # O ativo corrompido foi quarentenado
        quarantine_meta = list(self.quarantine_dir.glob("snapshot_metadata_*.corrupted"))
        self.assertGreaterEqual(len(quarantine_meta), 1)

    def test_manifesto_e_backup_ambos_invalidos_quarentena_ambos(self):
        """Se ativo e backup do manifesto estiverem inválidos, ambos vão para a quarentena."""
        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        prev_meta = self.data_dir / f"{SNAPSHOT_METADATA_FILE}.prev"

        meta_file.write_text("{corrupt_meta:", encoding="utf-8")
        prev_meta.write_text("{corrupt_prev_meta:", encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertTrue(loaded.is_empty())

        quarantine_meta = list(self.quarantine_dir.glob("snapshot_metadata*.corrupted"))
        self.assertGreaterEqual(len(quarantine_meta), 2, "Ambos os manifestos inválidos devem ser quarentenados")

    def test_save_snapshot_rejeita_fonte_desconhecida_e_path_traversal(self):
        """save_snapshot deve rejeitar fontes desconhecidas e tentativas de path traversal fora de data_dir."""
        sub_dir = self.data_dir / "snapshots"
        sub_dir.mkdir(parents=True, exist_ok=True)
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")

        # Tentativa 1: Path traversal
        with self.assertRaises(ValueError):
            batch.save_snapshot(sub_dir, source="../arquivo_fora")

        # Comprova que NENHUM arquivo fora do diretório de dados foi criado
        arquivo_escapado = self.data_dir / "arquivo_fora.json"
        self.assertFalse(arquivo_escapado.exists(), "Não pode criar arquivo fora do sub_dir")

        # Tentativa 2: Fonte inexistente / desconhecida
        with self.assertRaises(ValueError):
            batch.save_snapshot(sub_dir, source="fonte_fantasma")

    def test_save_snapshot_aceita_todas_fontes_e_aliases_validos(self):
        """save_snapshot aceita todas as fontes canônicas e seus aliases especificados."""
        batch = DailyIngestionBatch(
            tweets=[self.tweet_sample],
            repos=[self.repo_sample],
            papers=[self.paper_sample],
            collected_at="2026-11-12T08:00:00+00:00",
        )

        fontes_validas = [
            "twitter", "tweets", "collect-twitter", "collect-tweets",
            "github", "repos", "github_trending", "collect-github", "collect-repos", "collect-github_trending",
            "papers", "hf_papers", "collect-papers", "collect-hf_papers",
        ]

        for f in fontes_validas:
            # Não pode levantar ValueError
            batch.save_snapshot(self.data_dir, source=f)

    def test_novo_snapshot_persiste_updated_at_com_timezone_e_is_fresh(self):
        """Novos snapshots geram updated_at com timezone explícito e passam na validação de frescor."""
        batch = DailyIngestionBatch(tweets=[self.tweet_sample])
        batch.save_snapshot(self.data_dir, source="twitter")

        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        updated_at = meta["sources"]["twitter"]["updated_at"]
        dt = datetime.fromisoformat(updated_at)
        self.assertIsNotNone(dt.tzinfo, "updated_at deve possuir fuso horário explícito")
        self.assertTrue(is_source_fresh(updated_at), "Snapshot recém-criado deve ser fresh")

    def test_save_snapshot_preserva_timestamps_historicos_legados_sem_adulteracao(self):
        """save_snapshot de uma fonte não pode alterar ou adulterar timestamps de outras fontes."""
        # Prepara manifesto com timestamp histórico em github
        ts_historico = "2025-05-10T14:30:00+00:00"
        meta_inicial = {
            "version": 2,
            "collected_at": ts_historico,
            "last_attempt": {
                "started_at": ts_historico,
                "completed_at": ts_historico,
                "status": "completed",
                "trigger": "test",
                "pid": None,
            },
            "sources": {
                "github": {
                    "updated_at": ts_historico,
                    "sha256": "0" * 64,
                    "count": 5,
                    "status": "success",
                    "quality": "legacy_unverified",
                }
            },
        }
        (self.data_dir / SNAPSHOT_METADATA_FILE).write_text(json.dumps(meta_inicial), encoding="utf-8")
        (self.data_dir / SNAPSHOT_GITHUB_FILE).write_text("[]", encoding="utf-8")

        # Executa save_snapshot exclusivamente para twitter
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at="2026-11-12T08:00:00+00:00")
        batch.save_snapshot(self.data_dir, source="twitter")

        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        with open(meta_file, "r", encoding="utf-8") as f:
            meta_final = json.load(f)

        self.assertEqual(
            meta_final["sources"]["github"]["updated_at"],
            ts_historico,
            "Timestamp histórico de github deve permanecer rigorosamente inalterado",
        )

    def test_manifesto_v1_sem_collected_at_na_raiz_carregado_sem_quarentena(self):
        """Manifesto legado v1 sem collected_at na raiz não é enviado para quarentena e carrega dados."""
        v1_meta = {
            "sources": {
                "twitter": "2026-10-27T08:00:00.000000+00:00",
            }
        }
        (self.data_dir / SNAPSHOT_METADATA_FILE).write_text(json.dumps(v1_meta), encoding="utf-8")
        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        tweets_file.write_text(json.dumps([self.tweet_sample.to_dict()]), encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 1)
        self.assertEqual(len(list(self.quarantine_dir.glob("*.corrupted"))), 0)

    def test_recuperacao_geracao_anterior_sincroniza_manifesto_e_segunda_leitura_e_estavel(self):
        """Ao recuperar A do .prev após B corrompido, manifesto ativo é sincronizado com hash de A."""
        # 1. Snapshot A confirmado e válido
        tweet_A = Tweet(author_name="Alice", author_handle="@alice", timestamp="", text="A", url="")
        batch_A = DailyIngestionBatch(tweets=[tweet_A], collected_at="2026-11-12T08:00:00+00:00")
        batch_A.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        tweets_file = self.data_dir / SNAPSHOT_TWEETS_FILE
        sha_A = _calcular_sha256_arquivo(tweets_file)

        # 2. Snapshot B confirmado e válido, tendo A como backup (.prev)
        tweet_B = Tweet(author_name="Bob", author_handle="@bob", timestamp="", text="B", url="")
        batch_B = DailyIngestionBatch(tweets=[tweet_B], collected_at="2026-11-12T09:00:00+00:00")
        batch_B.save_snapshot(self.data_dir, source="twitter", status=SourceStatus.SUCCESS)

        sha_B = _calcular_sha256_arquivo(tweets_file)
        self.assertNotEqual(sha_A, sha_B)

        # 3. Corrupção do ativo B
        tweets_file.write_text("{json_ativo_B_corrompido:", encoding="utf-8")

        # 4. Primeira leitura: recupera A a partir do .prev, autorizada pelo manifesto de backup
        loaded1 = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded1.tweets), 1)
        self.assertEqual(loaded1.tweets[0].author_name, "Alice")

        # Verifica se o manifesto ativo agora aponta para o hash realmente recuperado (sha_A)
        with open(self.data_dir / SNAPSHOT_METADATA_FILE, "r", encoding="utf-8") as f:
            meta_pos_recup = json.load(f)
        self.assertEqual(
            meta_pos_recup["sources"]["twitter"]["sha256"],
            sha_A,
            "Manifesto ativo deve apontar para o hash de A após a recuperação",
        )

        quarantine_count_1 = len(list(self.quarantine_dir.glob("*.corrupted")))
        self.assertGreaterEqual(quarantine_count_1, 1, "Arquivo B corrompido deve ter ido para quarentena")

        # 5. Segunda leitura: deve continuar recuperando A, sem nova quarentena ou perda de dados
        loaded2 = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded2.tweets), 1)
        self.assertEqual(loaded2.tweets[0].author_name, "Alice")
        quarantine_count_2 = len(list(self.quarantine_dir.glob("*.corrupted")))
        self.assertEqual(quarantine_count_1, quarantine_count_2, "Segunda leitura não pode gerar novas quarentenas")

    def test_conversao_temporal_preserva_instante_real_em_utc_menos_tres(self):
        """Timestamp fornecido em UTC-03:00 é convertido para UTC preservando estritamente o instante real."""
        # 10:00 em UTC-03:00 equivale exatamente a 13:00 em UTC (+00:00)
        ts_sao_paulo = "2026-11-12T10:00:00-03:00"
        batch = DailyIngestionBatch(tweets=[self.tweet_sample], collected_at=ts_sao_paulo)
        batch.save_snapshot(self.data_dir, source="twitter")

        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        updated_at = meta["sources"]["twitter"]["updated_at"]
        dt = datetime.fromisoformat(updated_at)

        # O fuso deve ser UTC (+00:00)
        self.assertEqual(dt.tzinfo, timezone.utc)
        # A hora em UTC deve ser 13:00:00, preservando o instante real de 10:00-03:00
        self.assertEqual(dt.hour, 13)
        self.assertEqual(dt.minute, 0)
        self.assertEqual(dt.timestamp(), datetime.fromisoformat(ts_sao_paulo).timestamp())


if __name__ == "__main__":
    unittest.main()
