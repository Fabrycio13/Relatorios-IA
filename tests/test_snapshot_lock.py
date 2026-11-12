import errno
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.lock import (
    adquirir_trava_pipeline,
    adquirir_trava_snapshot,
    _fsync_dir,
    mover_para_quarentena,
    ConcorrenciaDetectadaError,
)


class TestSnapshotLockAndDurability(unittest.TestCase):
    """Suíte de testes de travamento exclusivo de snapshot e primitivas de durabilidade."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.lock_path = self.base_dir / "snapshot.lock"
        self.pipeline_lock_path = self.base_dir / "pipeline.lock"
        self.quarantine_dir = self.base_dir / "quarantine"

    def tearDown(self):
        self.tmp_dir.cleanup()

    # 1. Aquisição e liberação normal do lock
    def test_aquisicao_e_liberacao_normal(self):
        self.assertFalse(self.lock_path.exists())
        with adquirir_trava_snapshot(self.lock_path):
            self.assertTrue(self.lock_path.exists())
        # Após a saída, o arquivo ainda existe, mas o handle está liberado
        self.assertTrue(self.lock_path.exists())
        # Deve ser possível readquirir imediatamente
        with adquirir_trava_snapshot(self.lock_path):
            pass

    # 2. Exclusividade real entre dois subprocessos e 3. Timeout quando ocupado
    def test_exclusividade_real_entre_dois_subprocessos(self):
        script_helper = (
            "import sys, time\n"
            "from pathlib import Path\n"
            "from src.core.lock import adquirir_trava_snapshot\n"
            "lock_path = Path(sys.argv[1])\n"
            "try:\n"
            "    with adquirir_trava_snapshot(lock_path, timeout=0.3, retry_delay=0.05):\n"
            "        print('SUB_OK')\n"
            "except TimeoutError:\n"
            "    print('SUB_TIMEOUT')\n"
            "except Exception as e:\n"
            "    print(f'SUB_ERROR: {e}')\n"
        )

        with adquirir_trava_snapshot(self.lock_path):
            proc = subprocess.run(
                [sys.executable, "-c", script_helper, str(self.lock_path)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertIn("SUB_TIMEOUT", proc.stdout)

    # 4. Aquisição bem-sucedida após liberação
    def test_aquisicao_bem_sucedida_apos_liberacao(self):
        script_helper = (
            "import sys\n"
            "from pathlib import Path\n"
            "from src.core.lock import adquirir_trava_snapshot\n"
            "lock_path = Path(sys.argv[1])\n"
            "with adquirir_trava_snapshot(lock_path, timeout=1.0):\n"
            "    print('SUB_OK')\n"
        )
        with adquirir_trava_snapshot(self.lock_path):
            pass

        proc = subprocess.run(
            [sys.executable, "-c", script_helper, str(self.lock_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertIn("SUB_OK", proc.stdout)

    # 5. Exceção dentro do bloco protegido propagada sem alteração
    def test_excecao_dentro_do_bloco_protegido_propagada_sem_alteracao(self):
        with self.assertRaises(ValueError) as ctx:
            with adquirir_trava_snapshot(self.lock_path):
                raise ValueError("falha de teste customizada")
        self.assertEqual(str(ctx.exception), "falha de teste customizada")

    # 6. Liberação após exceção
    def test_liberacao_apos_excecao(self):
        try:
            with adquirir_trava_snapshot(self.lock_path):
                raise RuntimeError("erro forçado")
        except RuntimeError:
            pass

        adquiriu = False
        with adquirir_trava_snapshot(self.lock_path, timeout=0.5):
            adquiriu = True
        self.assertTrue(adquiriu)

    # 7. Ausência de reexecução do bloco protegido após erro do chamador
    def test_ausencia_de_reexecucao_do_bloco_protegido(self):
        execucoes = 0
        try:
            with adquirir_trava_snapshot(self.lock_path, timeout=1.0, retry_delay=0.1):
                execucoes += 1
                raise KeyError("erro do chamador")
        except KeyError:
            pass

        self.assertEqual(execucoes, 1, "O bloco do chamador não pode ser reexecutado em caso de exceção!")

    # 8. Proibição de aquisição aninhada no mesmo processo
    def test_proibicao_de_aquisicao_aninhada(self):
        with adquirir_trava_snapshot(self.lock_path):
            with self.assertRaises(RuntimeError) as ctx:
                with adquirir_trava_snapshot(self.lock_path, timeout=0.2):
                    pass
            self.assertIn("aninhada", str(ctx.exception).lower())

    # 9. Separação entre lock de pipeline e lock de snapshot
    def test_separacao_entre_lock_de_pipeline_e_lock_de_snapshot(self):
        with adquirir_trava_pipeline(self.pipeline_lock_path):
            with adquirir_trava_snapshot(self.lock_path):
                self.assertTrue(self.pipeline_lock_path.exists())
                self.assertTrue(self.lock_path.exists())
                self.assertNotEqual(self.pipeline_lock_path.resolve(), self.lock_path.resolve())

    # 10. Comportamento documentado de _fsync_dir no Windows (no-op seguro)
    def test_fsync_dir_no_windows_e_no_op_documentado(self):
        if sys.platform == "win32":
            # No Windows nativo, _fsync_dir executa sem erro
            _fsync_dir(self.base_dir)

    # 11. Comportamento de _fsync_dir no POSIX e propagação estrita de falha
    @patch("sys.platform", "linux")
    @patch("os.open")
    @patch("os.fsync")
    @patch("os.close")
    def test_fsync_dir_no_posix_chama_open_e_fsync(self, mock_close, mock_fsync, mock_open):
        mock_open.return_value = 99
        _fsync_dir(self.base_dir)
        mock_open.assert_called_once_with(str(self.base_dir), os.O_RDONLY)
        mock_fsync.assert_called_once_with(99)
        mock_close.assert_called_once_with(99)

    @patch("sys.platform", "linux")
    @patch("os.open", side_effect=OSError("Disco não suporta sync"))
    def test_fsync_dir_no_posix_propaga_erro(self, mock_open):
        with self.assertRaises(OSError):
            _fsync_dir(self.base_dir)

    # 12. Prevenção de Deadlock em aquisições sucessivas rápidas
    def test_sucessivas_aquisicoes_rapidas_sem_deadlock(self):
        for _ in range(30):
            with adquirir_trava_snapshot(self.lock_path, timeout=1.0, retry_delay=0.01):
                pass

    # 13. Timeout quando ocupado por outro processo
    def test_timeout_quando_ocupado_por_outro_processo(self):
        script_helper = (
            "import sys, time\n"
            "from pathlib import Path\n"
            "from src.core.lock import adquirir_trava_snapshot\n"
            "lock_path = Path(sys.argv[1])\n"
            "with adquirir_trava_snapshot(lock_path, timeout=2.0):\n"
            "    print('LOCKED', flush=True)\n"
            "    time.sleep(1.2)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script_helper, str(self.lock_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            linha = proc.stdout.readline()
            self.assertIn("LOCKED", linha)
            with self.assertRaises(TimeoutError):
                with adquirir_trava_snapshot(self.lock_path, timeout=0.2, retry_delay=0.05):
                    pass
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            proc.terminate()
            proc.wait(timeout=3)

    # 14. Classificação de erros na aquisição do lock
    def test_aquisicao_erro_permissao_ao_abrir_propaga_imediatamente_sem_timeout(self):
        with patch("builtins.open", side_effect=PermissionError("Acesso negado")):
            inicio = time.monotonic()
            with self.assertRaises(PermissionError):
                with adquirir_trava_snapshot(self.lock_path, timeout=5.0, retry_delay=0.5):
                    pass
            duracao = time.monotonic() - inicio
            self.assertLess(duracao, 1.0, "Erro de permissão deve propagar imediatamente sem esperar o timeout!")

    def test_aquisicao_erro_io_filesystem_ao_abrir_propaga_imediatamente_sem_timeout(self):
        with patch("builtins.open", side_effect=OSError(errno.EIO, "Falha de I/O no disco")):
            inicio = time.monotonic()
            with self.assertRaises(OSError):
                with adquirir_trava_snapshot(self.lock_path, timeout=5.0, retry_delay=0.5):
                    pass
            duracao = time.monotonic() - inicio
            self.assertLess(duracao, 1.0, "Erro de I/O deve propagar imediatamente sem esperar o timeout!")

    def test_aquisicao_erro_inesperado_no_locking_fecha_handle_e_propaga_imediatamente_windows(self):
        if sys.platform == "win32":
            import msvcrt
            with patch("msvcrt.locking", side_effect=OSError(errno.EBADF, "Bad file descriptor")):
                inicio = time.monotonic()
                with self.assertRaises(OSError) as ctx:
                    with adquirir_trava_snapshot(self.lock_path, timeout=5.0, retry_delay=0.5):
                        pass
                self.assertEqual(ctx.exception.errno, errno.EBADF)
                self.assertLess(time.monotonic() - inicio, 1.0, "Erro não-contencioso deve propagar imediatamente!")

    @patch("sys.platform", "linux")
    def test_aquisicao_erro_inesperado_no_locking_fecha_handle_e_propaga_imediatamente_posix(self):
        mock_fcntl = MagicMock()
        mock_fcntl.LOCK_EX = 2
        mock_fcntl.LOCK_NB = 4
        mock_fcntl.flock.side_effect = OSError(errno.EBADF, "Bad file descriptor")
        with patch.dict("sys.modules", {"fcntl": mock_fcntl}):
            inicio = time.monotonic()
            with self.assertRaises(OSError) as ctx:
                with adquirir_trava_snapshot(self.lock_path, timeout=5.0, retry_delay=0.5):
                    pass
            self.assertEqual(ctx.exception.errno, errno.EBADF)
            self.assertLess(time.monotonic() - inicio, 1.0, "Erro não-contencioso deve propagar imediatamente!")

    # 15. Durabilidade da quarentena e propagação de falhas de fsync
    @patch("src.core.lock._fsync_dir")
    def test_mover_para_quarentena_falha_fsync_origem_apos_replace_propaga_erro_e_mantem_movimentacao(self, mock_fsync):
        arquivo = self.base_dir / "tweets_coletados.json"
        arquivo.write_text("conteudo corrompido", encoding="utf-8")

        chamadas = []

        def side_effect(path, *args, **kwargs):
            chamadas.append(path)
            # Chamada 1: sync de quarantine_dir.parent (pré-replace)
            # Chamada 2: sync de file_path.parent (pós-replace)
            if len(chamadas) == 2:
                raise OSError("Falha ao sincronizar diretório de origem")

        mock_fsync.side_effect = side_effect

        with self.assertRaises(OSError) as ctx:
            mover_para_quarentena(arquivo, self.quarantine_dir)

        self.assertIn("Falha ao sincronizar diretório de origem", str(ctx.exception))
        # O arquivo físico já foi movido pelo os.replace antes da falha no fsync
        self.assertFalse(arquivo.exists(), "Após os.replace, o arquivo não está mais na origem")
        arquivos_quarentena = list(self.quarantine_dir.glob("*.corrupted"))
        self.assertEqual(len(arquivos_quarentena), 1, "Arquivo movido está presente na quarentena (sem rollback)")

    @patch("src.core.lock._fsync_dir")
    def test_mover_para_quarentena_falha_fsync_destino_apos_replace_propaga_erro_e_mantem_movimentacao(self, mock_fsync):
        arquivo = self.base_dir / "tweets_coletados.json"
        arquivo.write_text("conteudo corrompido", encoding="utf-8")

        chamadas = []

        def side_effect(path, *args, **kwargs):
            chamadas.append(path)
            # Chamada 3: sync de quarantine_dir (pós-replace)
            if len(chamadas) == 3:
                raise OSError("Falha ao sincronizar diretório de destino")

        mock_fsync.side_effect = side_effect

        with self.assertRaises(OSError) as ctx:
            mover_para_quarentena(arquivo, self.quarantine_dir)

        self.assertIn("Falha ao sincronizar diretório de destino", str(ctx.exception))
        self.assertFalse(arquivo.exists())
        arquivos_quarentena = list(self.quarantine_dir.glob("*.corrupted"))
        self.assertEqual(len(arquivos_quarentena), 1)

    @patch("src.core.lock._fsync_dir")
    def test_mover_para_quarentena_falha_fsync_criacao_quarentena_propaga_erro_antes_de_mover(self, mock_fsync):
        arquivo = self.base_dir / "tweets_coletados.json"
        arquivo.write_text("conteudo integro original", encoding="utf-8")

        def side_effect(path, *args, **kwargs):
            if path == self.quarantine_dir.parent:
                raise OSError("Falha de sync ao criar quarentena")

        mock_fsync.side_effect = side_effect

        with self.assertRaises(OSError):
            mover_para_quarentena(arquivo, self.quarantine_dir)

        # Falha ocorreu antes do replace; arquivo permanece intacto na origem
        self.assertTrue(arquivo.exists())
        self.assertEqual(arquivo.read_text(encoding="utf-8"), "conteudo integro original")

    # 16. Quarentena com UUID4 completo e preservação contra sobrescrita
    def test_quarentena_usa_uuid4_completo_e_nomes_unicos(self):
        arquivo1 = self.base_dir / "tweets_coletados.json"
        arquivo1.write_text("conteudo 1", encoding="utf-8")

        dest1 = mover_para_quarentena(arquivo1, self.quarantine_dir)
        self.assertTrue(dest1.exists())
        self.assertFalse(arquivo1.exists())
        # Formato: <stem>_<YYYYmmddTHHMMSS_microseconds>_<uuid4_32hex><suffix>.corrupted
        partes = dest1.name.split("_")
        self.assertTrue(dest1.name.startswith("tweets_coletados_"))
        self.assertTrue(dest1.name.endswith(".json.corrupted"))
        # Verifica que o trecho de uuid tem 32 caracteres hexadecimais
        # Nome ex: tweets_coletados_20261112T120000_123456_a1b2c3d4...json.corrupted
        raw_uuid_suffix = partes[-1].replace(".json.corrupted", "")
        self.assertEqual(len(raw_uuid_suffix), 32, "UUID4 na quarentena deve ter 32 hexadecimais completos")

    def test_quarentena_colisao_induzida_preserva_evidencia_preexistente(self):
        arquivo = self.base_dir / "tweets_coletados.json"
        arquivo.write_text("conteudo novo corrompido", encoding="utf-8")

        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        # Cria evidência prévia com nome fixo
        fixed_time = datetime(2026, 11, 12, 12, 0, 0, 123456, tzinfo=timezone.utc)
        fixed_time_str = fixed_time.strftime("%Y%m%dT%H%M%S_%f")
        uuid_colidente = "11111111111111111111111111111111"
        uuid_livre = "22222222222222222222222222222222"

        evidencia_preexistente = self.quarantine_dir / f"tweets_coletados_{fixed_time_str}_{uuid_colidente}.json.corrupted"
        evidencia_preexistente.write_text("EVIDENCIA_HISTORICA_PREEXISTENTE", encoding="utf-8")

        mock_uuid1 = MagicMock()
        mock_uuid1.hex = uuid_colidente
        mock_uuid2 = MagicMock()
        mock_uuid2.hex = uuid_livre

        with patch("src.core.lock.datetime") as mock_dt, patch("src.core.lock.uuid.uuid4") as mock_uuid:
            mock_dt.now.return_value = fixed_time
            mock_uuid.side_effect = [mock_uuid1, mock_uuid2]

            dest = mover_para_quarentena(arquivo, self.quarantine_dir)

        # Evidência pré-existente NÃO foi sobrescrita
        self.assertEqual(evidencia_preexistente.read_text(encoding="utf-8"), "EVIDENCIA_HISTORICA_PREEXISTENTE")
        # Novo destino utilizou o UUID alternativo
        self.assertEqual(dest.name, f"tweets_coletados_{fixed_time_str}_{uuid_livre}.json.corrupted")
        self.assertEqual(dest.read_text(encoding="utf-8"), "conteudo novo corrompido")

    def test_quarentena_colisao_persistente_levanta_file_exists_error_sem_sobrescrever(self):
        arquivo = self.base_dir / "tweets_coletados.json"
        arquivo.write_text("conteudo novo", encoding="utf-8")

        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        fixed_time = datetime(2026, 11, 12, 12, 0, 0, 123456, tzinfo=timezone.utc)
        fixed_time_str = fixed_time.strftime("%Y%m%dT%H%M%S_%f")
        uuid_colidente = "33333333333333333333333333333333"

        evidencia_preexistente = self.quarantine_dir / f"tweets_coletados_{fixed_time_str}_{uuid_colidente}.json.corrupted"
        evidencia_preexistente.write_text("EVIDENCIA_HISTORICA_PREEXISTENTE", encoding="utf-8")

        mock_uuid_forever = MagicMock()
        mock_uuid_forever.hex = uuid_colidente

        with patch("src.core.lock.datetime") as mock_dt, patch("src.core.lock.uuid.uuid4") as mock_uuid:
            mock_dt.now.return_value = fixed_time
            mock_uuid.return_value = mock_uuid_forever

            with self.assertRaises(FileExistsError):
                mover_para_quarentena(arquivo, self.quarantine_dir)

        # Evidência permanece intacta
        self.assertEqual(evidencia_preexistente.read_text(encoding="utf-8"), "EVIDENCIA_HISTORICA_PREEXISTENTE")
        # Arquivo original NÃO foi removido
        self.assertTrue(arquivo.exists())
        self.assertEqual(arquivo.read_text(encoding="utf-8"), "conteudo novo")

    def test_quarentena_arquivo_inexistente_levanta_file_not_found(self):
        arquivo_fantasma = self.base_dir / "inexistente.json"
        with self.assertRaises(FileNotFoundError):
            mover_para_quarentena(arquivo_fantasma, self.quarantine_dir)


if __name__ == "__main__":
    unittest.main()
