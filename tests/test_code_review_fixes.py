"""Testes herméticos para validação dos achados do Code Review da Spec 0007 v4.3.

Cobre especificamente:
- B-01: Recuperação de execução interrompida (liveness, identidade de processo, recuperação sem dirty reads).
- B-03: Normalização de aliases legados no sintetizador ('github_trending', 'hf_papers').
- B-02: Garantia de timezone UTC em DailyIngestionBatch.from_dict() e suporte a offsets conhecidos.
"""

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.core.models import (
    DailyIngestionBatch,
    GitHubRepo,
    ResearchPaper,
    Tweet,
    SourceStatus,
    SourceCollectionResult,
    obter_metadados_fonte,
    SNAPSHOT_METADATA_FILE,
)
from src.core.manifest import (
    is_pid_alive,
    is_pid_recycled,
    is_execucao_em_andamento,
    is_source_fresh,
    _calcular_sha256_arquivo,
)
from src.collectors.pipeline import _marcar_inicio_execucao
from src.processors.ai_summarizer import _avaliar_frescor_e_qualidade


class TestCodeReviewFixes(unittest.TestCase):
    """Validação rigorosa dos achados confirmados do code-review da Spec 0007 v4.3."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp_dir.name)
        self.now_fixed = datetime(2026, 11, 13, 10, 0, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp_dir.cleanup()

    # -------------------------------------------------------------------------
    # B-01: Recuperação de Execução Interrompida
    # -------------------------------------------------------------------------

    def test_b01_liveness_e_identidade_de_processo(self):
        """Verifica detecção de liveness e reciclagem de PID."""
        # Processo atual deve ser detectado como vivo
        self.assertTrue(is_pid_alive(os.getpid()))

        # PID fictício/morto deve ser detectado como não-vivo
        self.assertFalse(is_pid_alive(99999999))
        self.assertFalse(is_pid_alive(0))
        self.assertFalse(is_pid_alive(-1))
        self.assertFalse(is_pid_alive(None))

        # is_execucao_em_andamento com check_liveness=True
        # Processo vivo e com started_at recente -> em andamento (True)
        running_alive = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "pid": os.getpid(),
        }
        self.assertTrue(is_execucao_em_andamento(running_alive, check_liveness=True))

        # Processo vivo mas com PID comprovadamente reciclado (started_at muito anterior ao nascimento) -> False
        # (se o SO suportar detecção de process creation time, avalia reciclagem; caso contrário, preserva True)
        if os.name == "nt":
            running_recycled = {
                "started_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                "status": "running",
                "pid": os.getpid(),
            }
            self.assertFalse(is_execucao_em_andamento(running_recycled, check_liveness=True))
            self.assertTrue(is_pid_recycled(os.getpid(), (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()))

        # Processo morto -> não está em andamento (False)
        running_dead = {
            "started_at": self.now_fixed.isoformat(),
            "status": "running",
            "pid": 99999999,
        }
        self.assertFalse(is_execucao_em_andamento(running_dead, check_liveness=True))

        # PID ausente -> incerteza preservada (True, proibindo dirty reads)
        running_uncertain = {
            "started_at": self.now_fixed.isoformat(),
            "status": "running",
            "pid": None,
        }
        self.assertTrue(is_execucao_em_andamento(running_uncertain, check_liveness=True))

    def test_b01_ordem_temporal_reciclagem_deterministica(self):
        """Verifica que a ordem temporal entre criação do processo e started_at é respeitada rigorosamente."""
        if os.name != "nt":
            self.skipTest("Inspeção de CreationTime via Win32 API aplicável no Windows")

        # Processo atual foi criado em algum momento no passado recente
        # Se started_at for posterior à criação do processo (ex: agora ou no futuro próximo):
        # O processo legítimo NÃO PODE ser considerado reciclado.
        started_at_futuro = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        self.assertFalse(
            is_pid_recycled(os.getpid(), started_at_futuro),
            "Processo criado antes de started_at não deve ser considerado reciclado",
        )

        started_at_recente = datetime.now(timezone.utc).isoformat()
        self.assertFalse(
            is_pid_recycled(os.getpid(), started_at_recente),
            "Processo legítimo em execução não deve ser considerado reciclado",
        )

        # Se started_at for muito anterior ao nascimento do processo atual (ex: 2 dias atrás):
        # Comprova que o PID foi reutilizado pelo SO muito depois do início da tentativa.
        started_at_antigo = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.assertTrue(
            is_pid_recycled(os.getpid(), started_at_antigo),
            "PID ativo cujo nascimento ocorreu após started_at deve ser identificado como reciclado",
        )

    def test_b01_erro_permissao_preserva_incerteza_sem_assumir_morte(self):
        """Verifica que erro de permissão (ex: processo de outro usuário) não é confundido com morte."""
        if os.name != "nt":
            self.skipTest("Teste de GetLastError() aplicável no Windows")

        # Mock de OpenProcess falhando com ERROR_ACCESS_DENIED (código 5)
        with patch("ctypes.windll.kernel32.OpenProcess", return_value=0), \
             patch("ctypes.windll.kernel32.GetLastError", return_value=5):
            # O processo deve ser considerado vivo (existe no SO)
            self.assertTrue(is_pid_alive(12345))

            # is_execucao_em_andamento deve preservar a condição de incerteza (retornando True)
            attempt = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "running",
                "pid": 12345,
            }
            self.assertTrue(
                is_execucao_em_andamento(attempt, check_liveness=True),
                "Erro de acesso deve preservar incerteza e bloquear dirty reads",
            )

    def test_b01_subprocesso_real_windows_crash_e_recuperacao(self):
        """Teste hermético com subprocesso real no Windows que registra running e é encerrado abruptamente."""
        import subprocess
        import sys
        import time

        sub_tmp = tempfile.TemporaryDirectory()
        try:
            sub_dir = Path(sub_tmp.name)
            ready_file = sub_dir / "ready.txt"

            # Script executado no subprocesso real
            script = f"""
import json, os, pathlib, sys, time
from datetime import datetime, timezone

data_dir = pathlib.Path(sys.argv[1])
ready_flag = pathlib.Path(sys.argv[2])

meta = {{
    "version": 2,
    "collected_at": datetime.now(timezone.utc).isoformat(),
    "last_attempt": {{
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "trigger": "subproc_test",
        "pid": os.getpid(),
    }},
    "sources": {{}},
}}
(data_dir / "snapshot_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
ready_flag.write_text("ready", encoding="utf-8")

# Permanece ativo aguardando encerramento abrupto
while True:
    time.sleep(0.1)
"""
            subproc = subprocess.Popen(
                [sys.executable, "-c", script, str(sub_dir), str(ready_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            try:
                # Aguarda até 5 segundos para o subprocesso escrever o manifesto
                deadline = time.monotonic() + 5.0
                while not ready_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)

                self.assertTrue(ready_file.exists(), "Subprocesso real deve ter gravado o manifesto")
                subproc_pid = subproc.pid

                # Verifica que enquanto o subprocesso está ativo, is_pid_alive é True
                self.assertTrue(is_pid_alive(subproc_pid), "Subprocesso ativo deve ter liveness=True")

                # Encerra abruptamente o subprocesso simulando crash (SIGKILL / TerminateProcess)
                subproc.kill()
                subproc.wait(timeout=5.0)

                # Comprova que o SO reporta que o PID está morto
                self.assertFalse(is_pid_alive(subproc_pid), "Após kill(), o PID deve estar morto")

                # Executa DailyIngestionBatch.load_snapshot() no diretório temporário
                # O sistema deve identificar o término abrupto e transicionar para 'interrupted' sob a trava
                loaded = DailyIngestionBatch.load_snapshot(sub_dir)
                self.assertIsNotNone(loaded)

                # Verifica que o manifesto foi atualizado deterministicamente para 'interrupted'
                with open(sub_dir / SNAPSHOT_METADATA_FILE, "r", encoding="utf-8") as f:
                    meta_atualizado = json.load(f)

                self.assertEqual(meta_atualizado["last_attempt"]["status"], "interrupted")
                self.assertEqual(meta_atualizado["last_attempt"]["pid"], subproc_pid)
                self.assertIn("completed_at", meta_atualizado["last_attempt"])
            finally:
                if subproc.poll() is None:
                    subproc.kill()
                    subproc.wait()
        finally:
            sub_tmp.cleanup()

    def test_b01_recuperacao_apos_crash_em_load_snapshot(self):
        """Comprova recuperação de snapshot confirmado após interrupção abrupta da execução seguinte.
        
        Cenário:
        1. Snapshot A confirmado existe em disco (Twitter, GitHub, Papers) com manifesto válido.
        2. Execução B inicia, grava last_attempt.status='running' com PID morto, e morre antes de finalizar.
        3. Arquivo transitório não comitado (.tmp.99999) é deixado no disco.
        4. load_snapshot() é executado:
           - Não deve permanecer bloqueado indefinidamente.
           - Deve transicionar o manifesto para 'interrupted' sob a trava com backup .prev.
           - Não deve consumir o arquivo não comitado.
           - Deve retornar os dados íntegros de A.
        """
        # 1. Cria snapshot A confirmado
        tweets_a = [
            Tweet(
                author_name="dev",
                author_handle="@dev",
                timestamp=self.now_fixed.isoformat(),
                text="Tweet A",
                url="https://x.com/dev/1",
            )
        ]
        batch_a = DailyIngestionBatch(
            collected_at=self.now_fixed.isoformat(),
            tweets=tweets_a,
        )
        batch_a.save_snapshot(
            self.data_dir,
            result=SourceCollectionResult(
                source_name="twitter",
                status=SourceStatus.SUCCESS,
                items=tuple(tweets_a),
                successful_operations=("scrape_feed",),
            ),
            source="twitter",
        )

        # Verifica que o snapshot A foi salvo
        carregado_a = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(carregado_a.tweets), 1)
        self.assertEqual(carregado_a.tweets[0].text, "Tweet A")

        # 2. Simula crash abrupto da Execução B
        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        meta["last_attempt"] = {
            "started_at": (self.now_fixed + timedelta(minutes=10)).isoformat(),
            "status": "running",
            "trigger": "pipeline",
            "pid": 99999999,  # Processo comprovadamente morto
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        # Cria arquivo não comitado deixado pelo processo que crashou
        arquivo_transitorio = self.data_dir / "tweets_coletados.tmp.99999999"
        arquivo_transitorio.write_text(json.dumps([{"id": "2", "text": "Dirty Data"}]), encoding="utf-8")

        # 3. Executa load_snapshot()
        recuperado = DailyIngestionBatch.load_snapshot(self.data_dir)

        # 4. Validações estritas de recuperação
        # - Snapshot A íntegro foi retornado
        self.assertEqual(len(recuperado.tweets), 1)
        self.assertEqual(recuperado.tweets[0].text, "Tweet A")

        # - Arquivo não comitado não foi consumido
        self.assertTrue(arquivo_transitorio.exists())  # Permanece como lixo ou não ingerido

        # - Manifesto foi atualizado para 'interrupted'
        with open(meta_file, "r", encoding="utf-8") as f:
            meta_atualizado = json.load(f)
        self.assertEqual(meta_atualizado["last_attempt"]["status"], "interrupted")
        self.assertIn("completed_at", meta_atualizado["last_attempt"])

        # - Backup .prev do manifesto foi gerado
        prev_meta_file = self.data_dir / f"{SNAPSHOT_METADATA_FILE}.prev"
        self.assertTrue(prev_meta_file.exists())

        # - Segunda leitura continua idempotente
        recuperado_2 = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(recuperado_2.tweets), 1)

    def test_b01_exclusividade_de_processo_em_marcar_inicio(self):
        """Verifica que nova execução recusa concorrência se houver processo ativo, mas assume se estiver morto."""
        meta_file = self.data_dir / SNAPSHOT_METADATA_FILE

        # Cenário 1: Processo ativo (PID vivo) já executando
        meta_com_processo_vivo = {
            "version": 2,
            "collected_at": self.now_fixed.isoformat(),
            "last_attempt": {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "running",
                "trigger": "pipeline",
                "pid": os.getpid(),  # Processo atual está VIVO
            },
            "sources": {},
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_com_processo_vivo, f)

        # Tentativa concorrente deve ser bloqueada para exclusividade
        with self.assertRaises(RuntimeError) as ctx:
            _marcar_inicio_execucao(self.data_dir, trigger="pipeline")
        self.assertIn("em andamento", str(ctx.exception).lower())

        # Cenário 2: Processo anterior crashou (PID morto)
        meta_com_processo_morto = {
            "version": 2,
            "collected_at": self.now_fixed.isoformat(),
            "last_attempt": {
                "started_at": self.now_fixed.isoformat(),
                "status": "running",
                "trigger": "pipeline",
                "pid": 99999999,  # Processo MORTO
            },
            "sources": {},
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_com_processo_morto, f)

        # Nova execução deve identificar que o anterior morreu e iniciar com sucesso
        _marcar_inicio_execucao(self.data_dir, trigger="pipeline")

        with open(meta_file, "r", encoding="utf-8") as f:
            meta_novo = json.load(f)
        self.assertEqual(meta_novo["last_attempt"]["status"], "running")
        self.assertEqual(meta_novo["last_attempt"]["pid"], os.getpid())

    # -------------------------------------------------------------------------
    # B-03: Aliases Legados no Sintetizador
    # -------------------------------------------------------------------------

    def test_b03_obter_metadados_fonte_resolve_canonicos_e_aliases(self):
        """Testa a resolução centralizada de chaves canônicas e aliases em sources_metadata."""
        sources_meta = {
            "github_trending": {
                "quality": "legacy_unverified",
                "updated_at": self.now_fixed.isoformat(),
                "sha256": "abc1",
            },
            "hf_papers": {
                "quality": "verified",
                "updated_at": self.now_fixed.isoformat(),
                "sha256": "abc2",
            },
            "twitter": {
                "quality": "verified",
                "updated_at": self.now_fixed.isoformat(),
                "sha256": "abc3",
            },
        }

        # Busca pelo canônico 'github' deve encontrar metadados de 'github_trending'
        meta_gh = obter_metadados_fonte(sources_meta, "github")
        self.assertEqual(meta_gh.get("quality"), "legacy_unverified")
        self.assertEqual(meta_gh.get("sha256"), "abc1")

        # Busca pelo alias 'github_trending' direto
        self.assertEqual(obter_metadados_fonte(sources_meta, "github_trending").get("sha256"), "abc1")

        # Busca pelo canônico 'papers' deve encontrar 'hf_papers'
        meta_papers = obter_metadados_fonte(sources_meta, "papers")
        self.assertEqual(meta_papers.get("sha256"), "abc2")

        # Busca pelo alias 'hf_papers' direto
        self.assertEqual(obter_metadados_fonte(sources_meta, "hf_papers").get("sha256"), "abc2")

        # Inverso: se o dict tiver chaves canônicas 'github' e 'papers'
        meta_canonico = {
            "github": {"quality": "verified", "sha256": "gh_can"},
            "papers": {"quality": "verified", "sha256": "pa_can"},
        }
        self.assertEqual(obter_metadados_fonte(meta_canonico, "github_trending").get("sha256"), "gh_can")
        self.assertEqual(obter_metadados_fonte(meta_canonico, "hf_papers").get("sha256"), "pa_can")

    def test_b03_sintetizador_resolve_aliases_legados_e_aplica_aviso_editorial(self):
        """Comprova que o sintetizador avalia corretamente 'github_trending' e 'hf_papers' em manifestos migrados."""
        repos = [GitHubRepo(name="repo1", full_name="org/repo1", description="desc", stars=100, language="Python", url="http://gh")]
        papers = [ResearchPaper(title="paper1", arxiv_id="2401.12345", summary="sum", authors=("aut",), url="http://hf")]

        # Manifesto legado com chaves 'github_trending' e 'hf_papers'
        sources_meta = {
            "github_trending": {
                "quality": "legacy_unverified",
                "updated_at": self.now_fixed.isoformat(),
            },
            "hf_papers": {
                "quality": "verified",
                "updated_at": (self.now_fixed - timedelta(hours=40)).isoformat(),  # Stale (> 36h)
            },
        }

        # Avaliação de 'github': deve detectar 'legacy_unverified' e marcar is_historical=True, is_usable=True
        is_usable, is_historical, is_stale = _avaliar_frescor_e_qualidade(
            "github", repos, sources_meta, collection_status=None
        )
        self.assertTrue(is_usable)
        self.assertTrue(is_historical, "Deve reconhecer quality='legacy_unverified' via alias github_trending")
        self.assertFalse(is_stale)

        # Avaliação de 'papers': deve detectar updated_at obsoleto (>36h) e marcar is_stale=True, is_usable=False
        is_usable_p, is_historical_p, is_stale_p = _avaliar_frescor_e_qualidade(
            "papers", papers, sources_meta, collection_status=None
        )
        self.assertFalse(is_usable_p, "Dados obsoletos de papers não devem ser utilizáveis")
        self.assertTrue(is_stale_p, "Deve reconhecer timestamp de hf_papers como stale (>36h)")

    # -------------------------------------------------------------------------
    # B-02: Garantia de Timezone em from_dict e Offsets Conhecidos
    # -------------------------------------------------------------------------

    def test_b02_batch_from_dict_garante_timezone_utc_quando_ausente(self):
        """Verifica que DailyIngestionBatch.from_dict({}) não gera timestamp ingênuo sem timezone."""
        batch = DailyIngestionBatch.from_dict({})
        self.assertTrue(batch.collected_at)
        dt = datetime.fromisoformat(batch.collected_at)
        self.assertIsNotNone(dt.tzinfo, "collected_at gerado em from_dict deve ser timezone-aware")
        self.assertEqual(dt.utcoffset(), timedelta(0), "Offset deve ser estritamente UTC")

    def test_b02_is_source_fresh_suporta_offsets_conhecidos(self):
        """Verifica que timestamps com fuso explícito (-03:00, +02:00, Z) são avaliados com precisão em UTC."""
        now = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)

        # 1 hora no passado em Brasília (-03:00) -> 12:00 UTC corresponde a 09:00 em -03:00
        # Logo, 08:00 em -03:00 é 11:00 UTC (1 hora atrás)
        ts_bsb_1h_atras = "2026-11-13T08:00:00-03:00"
        self.assertTrue(is_source_fresh(ts_bsb_1h_atras, max_hours=36.0, now=now))

        # 37 horas no passado em Berlim (+01:00)
        # 12:00 UTC de hoje corresponde a 13:00 em +01:00.
        # 37h atrás em +01:00 = anteontem às 00:00 (+01:00)
        ts_berlim_37h_atras = "2026-11-11T23:00:00+01:00"
        self.assertFalse(is_source_fresh(ts_berlim_37h_atras, max_hours=36.0, now=now))

        # Rejeição de timestamp sem fuso (ingênuo) permanece inalterada
        self.assertFalse(is_source_fresh("2026-11-13T11:00:00", max_hours=36.0, now=now))
