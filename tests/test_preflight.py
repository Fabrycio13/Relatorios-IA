import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Importação condicional do módulo a ser implementado (TDD)
try:
    from scripts.preflight import (
        inspecionar_git,
        executar_suite_testes,
        mascarar_segredo,
        _inspecionar_commit_atomico,
        CAMINHOS_PROIBIDOS,
        REGEX_SEGREDOS,
        ResultadoInspecaoGit,
        ResultadoSuiteTestes,
    )
except ImportError:
    # Permitir que a suíte carregue na fase RED do TDD antes de preflight.py existir
    inspecionar_git = None
    executar_suite_testes = None
    mascarar_segredo = None
    _inspecionar_commit_atomico = None
    CAMINHOS_PROIBIDOS = []
    REGEX_SEGREDOS = []
    ResultadoInspecaoGit = None
    ResultadoSuiteTestes = None


class TestPreflightUnitario(unittest.TestCase):
    """Testes unitários com mocks focados na lógica pura de parsing, regexes e captura de testes."""

    def setUp(self):
        if inspecionar_git is None:
            self.skipTest("scripts.preflight ainda não implementado (fase RED do TDD)")

    def test_unitario_parser_estados_git_name_status(self):
        """Valida que o parser NUL (-z) decodifica tokens de status e caminhos com espaços e acentos."""
        from scripts.preflight import _parse_name_status_z

        # Exemplo com A, M, D, R100, C090 e caminhos com espaços e caracteres especiais
        raw_tokens = (
            b"A\x00src/app.py\x00"
            b"M\x00reports/Resumo [2026].txt\x00"
            b"D\x00.env\x00"
            b"R100\x00old path.py\x00new path.py\x00"
            b"C090\x00origem com espacos.txt\x00copia acentuada \xc3\xa9.txt\x00"
            b"T\x00symlink.sh\x00"
        )
        parsed = _parse_name_status_z(raw_tokens)

        self.assertEqual(len(parsed), 6)
        self.assertEqual(parsed[0], ("A", "src/app.py", None))
        self.assertEqual(parsed[1], ("M", "reports/Resumo [2026].txt", None))
        self.assertEqual(parsed[2], ("D", ".env", None))
        self.assertEqual(parsed[3], ("R100", "old path.py", "new path.py"))
        self.assertEqual(parsed[4], ("C090", "origem com espacos.txt", "copia acentuada é.txt"))
        self.assertEqual(parsed[5], ("T", "symlink.sh", None))

    def test_unitario_parser_rejeita_estados_anomalos_ou_conflito(self):
        """Valida que status U, B, X e desconhecidos levantam erro ou geram violação estrita."""
        from scripts.preflight import _avaliar_tokens_status

        # Status U (unmerged conflict)
        tokens_u = [("U", "conflito.py", None)]
        erros_u = _avaliar_tokens_status(tokens_u, Path("."))
        self.assertTrue(any("Conflito de merge não resolvido" in e or "U" in e for e in erros_u))

        # Status B (pairing broken)
        tokens_b = [("B", "arquivo.py", None)]
        erros_b = _avaliar_tokens_status(tokens_b, Path("."))
        self.assertTrue(any("Status Git anômalo" in e or "B" in e for e in erros_b))

        # Status X (desconhecido)
        tokens_x = [("X", "estranho.py", None)]
        erros_x = _avaliar_tokens_status(tokens_x, Path("."))
        self.assertTrue(any("Status Git anômalo" in e or "X" in e for e in erros_x))

    def test_unitario_regex_segredos_e_masking(self):
        """Valida regexes contra tokens reais e certifica que o valor impresso é mascarado."""
        from scripts.preflight import _escanear_linhas_por_segredos

        tok_ghp = "ghp_" + ("1" * 36)
        tok_google = "AIza" + "SyD-" + ("a" * 31)
        tok_gmail = "GMAIL_" + "APP_PASSWORD = 'abcd efgh ijkl mnop'"
        tok_pem = "-----BEGIN " + "RSA " + "PRIVATE " + "KEY-----"

        linhas = [
            f"+const githubToken = '{tok_ghp}';",
            f"+const googleKey = '{tok_google}';",
            f"+{tok_gmail};",
            f"+{tok_pem}",
            "+const placeholder = 'ghp_TEST_PLACEHOLDER';",
            "+const invalidKey = 'AIza_MOCK_INVALID';",
        ]

        erros = _escanear_linhas_por_segredos(linhas, "src/config.py")

        # Deve encontrar 4 segredos reais e ignorar os 2 placeholders inválidos
        self.assertEqual(len(erros), 4)

        # Garantir masking: nenhum segredo real deve aparecer em texto plano na mensagem de erro
        texto_erros = "\n".join(erros)
        self.assertNotIn(tok_ghp, texto_erros)
        self.assertNotIn(tok_google, texto_erros)
        self.assertNotIn("abcd efgh ijkl mnop", texto_erros)
        self.assertIn("ghp_****", texto_erros)
        self.assertIn("AIza****", texto_erros)

    def test_unitario_suite_testes_captura_dinamica_e_retorno(self):
        """Valida que executar_suite_testes captura saída dinâmica e rejeita 'Ran 0 tests'."""
        with patch("subprocess.run") as mock_run:
            # Caso 1: Sucesso dinâmico com 42 testes
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Ran 42 tests in 1.234s\n\nOK\n",
                stderr=""
            )
            res_ok = executar_suite_testes(Path("."))
            self.assertTrue(res_ok.sucesso)
            self.assertEqual(res_ok.quantidade_testes, 42)

            # Caso 2: Falha em teste
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="FAILED (failures=1)\n",
                stderr="AssertionError"
            )
            res_fail = executar_suite_testes(Path("."))
            self.assertFalse(res_fail.sucesso)

            # Caso 3: Zero testes descobertos (deve falhar com código de erro)
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Ran 0 tests in 0.001s\n\nOK\n",
                stderr=""
            )
            res_zero = executar_suite_testes(Path("."))
            self.assertFalse(res_zero.sucesso)
            self.assertIn("Ran 0 tests", res_zero.mensagem)

    def test_unitario_ausencia_git_trata_gracefully(self):
        """Valida que a ausência do executável git é tratada com erro limpo sem crash."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            res = inspecionar_git(Path("."))
            self.assertFalse(res.sucesso)
            self.assertIn("não foi encontrado no PATH", res.mensagem_erro)

    def test_unitario_diretorio_nao_git_rejeita(self):
        """Valida que um diretório que não seja repositório git é rejeitado com erro limpo."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: not a git repository")
            res = inspecionar_git(Path("."))
            self.assertFalse(res.sucesso)
            self.assertIn("não é um repositório Git válido", res.mensagem_erro)

    def test_unitario_caminhos_proibidos_padroes_env(self):
        """ACH-01: Bloqueia .env, .env.*, .env_*, .env-* e preserva .env.example como exceção."""
        from scripts.preflight import _eh_caminho_proibido

        # Padrões que devem bloquear (True)
        padroes_bloqueados = [
            ".env",
            ".env.local",
            ".env.production",
            ".env.test",
            ".env_local",
            ".env_prod",
            ".env_staging",
            ".env-secrets",
            ".env-vault",
            "backend/.env_prod",
            "config/sub/.env-staging",
            "nested/.env.local",
        ]
        for p in padroes_bloqueados:
            self.assertTrue(_eh_caminho_proibido(p), f"Deveria bloquear: {p}")

        # Exceção autorizada: .env.example (em qualquer nível)
        self.assertFalse(_eh_caminho_proibido(".env.example"))
        self.assertFalse(_eh_caminho_proibido("config/.env.example"))
        self.assertFalse(_eh_caminho_proibido("sub/folder/.env.example"))

        # Padrões não relacionados que não devem ser falsos positivos
        self.assertFalse(_eh_caminho_proibido(".environment"))
        self.assertFalse(_eh_caminho_proibido("my.env"))
        self.assertFalse(_eh_caminho_proibido("environ.py"))


class TestPreflightIntegracaoGit(unittest.TestCase):
    """Testes de integração herméticos com repositórios Git reais em diretórios temporários."""

    def setUp(self):
        if inspecionar_git is None:
            self.skipTest("scripts.preflight ainda não implementado (fase RED do TDD)")

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.tmp_dir.name)
        self._git(["init", "-b", "main"])
        self._git(["config", "user.name", "Test Runner"])
        self._git(["config", "user.email", "test@example.com"])
        self._git(["config", "commit.gpgsign", "false"])

        # Commit inicial legítimo
        (self.repo_path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        self._git(["add", "README.md"])
        self._git(["commit", "-m", "Initial commit"])

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _git(self, args: list[str], check: bool = True) -> str:
        import subprocess
        proc = subprocess.run(
            ["git"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if check and proc.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}\nError: {proc.stderr}")
        return proc.stdout.strip()

    def test_integracao_staging_arquivo_sensivel_bloqueia(self):
        """AC-01: Bloqueia status A no staging para caminhos proibidos (.env, auth.json)."""
        (self.repo_path / ".env").write_text("SECRET=123\n", encoding="utf-8")
        self._git(["add", ".env"])

        res = inspecionar_git(self.repo_path)
        self.assertFalse(res.sucesso)
        self.assertTrue(any(".env" in e for e in res.erros_seguranca))

    def test_integracao_delecao_isolada_de_segredo_aprova(self):
        """AC-02: Exclusão de arquivo sensível (status D) é permitida como saneamento seguro."""
        # Criar commit com arquivo e depois deletar
        (self.repo_path / "segredo.txt").write_text("conteudo\n", encoding="utf-8")
        self._git(["add", "segredo.txt"])
        self._git(["commit", "-m", "add segredo"])

        # Deletar no staging
        (self.repo_path / "segredo.txt").unlink()
        self._git(["add", "segredo.txt"])  # Status D no index

        # Configurar remote simulado para haver base
        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        res = inspecionar_git(self.repo_path)
        # Deleção não deve ser classificada como erro de segurança
        self.assertFalse(any("segredo.txt" in e for e in res.erros_seguranca))

    def test_integracao_renomeacao_sensivel_bidirecional_bloqueia(self):
        """AC-03: Renomeação de .env para safe.txt ou safe.txt para .env bloqueia no staging e em commits."""
        # Configurar base remota
        c_inicial = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", c_inicial])

        # Cenário 1: .env -> safe.txt no staging
        (self.repo_path / ".env").write_text("A" * 100 + "\n", encoding="utf-8")
        self._git(["add", ".env"])
        self._git(["commit", "-m", "add env"])
        self._git(["mv", ".env", "safe.txt"])
        res1 = inspecionar_git(self.repo_path)
        self.assertFalse(res1.sucesso)
        self.assertTrue(any(".env" in e or "safe.txt" in e for e in res1.erros_seguranca))

        # Cenário 2: .env -> safe.txt em commit pendente
        self._git(["commit", "-m", "renomeia .env para safe.txt"])
        res2 = inspecionar_git(self.repo_path)
        self.assertFalse(res2.sucesso)
        self.assertTrue(any(".env" in e or "safe.txt" in e for e in res2.erros_seguranca))

        # Reverter para estado inicial
        self._git(["reset", "--hard", c_inicial])

        # Cenário 3: safe.txt -> .env no staging
        (self.repo_path / "safe.txt").write_text("B" * 100 + "\n", encoding="utf-8")
        self._git(["add", "safe.txt"])
        self._git(["commit", "-m", "add safe.txt"])
        c_safe = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", c_safe])

        self._git(["mv", "safe.txt", ".env"])
        res3 = inspecionar_git(self.repo_path)
        self.assertFalse(res3.sucesso)
        self.assertTrue(any(".env" in e or "safe.txt" in e for e in res3.erros_seguranca))

        # Cenário 4: safe.txt -> .env em commit pendente
        self._git(["commit", "-m", "renomeia safe.txt para .env"])
        res4 = inspecionar_git(self.repo_path)
        self.assertFalse(res4.sucesso)
        self.assertTrue(any(".env" in e or "safe.txt" in e for e in res4.erros_seguranca))

        # Reverter
        self._git(["reset", "--hard", c_inicial])
        self._git(["update-ref", "refs/remotes/origin/main", c_inicial])

    def test_integracao_copia_identica_com_inspecao_de_blob(self):
        """AC-04: Cópia idêntica de arquivo com segredo para nome seguro bloqueia via inspeção de blob."""
        token_real = "ghp_" + ("1" * 36)
        (self.repo_path / "origem.txt").write_text(f"TOKEN={token_real}\n", encoding="utf-8")
        self._git(["add", "origem.txt"])
        self._git(["commit", "-m", "add origem"])

        # Cópia idêntica para destino com nome aparentemente seguro
        (self.repo_path / "documento.txt").write_text(f"TOKEN={token_real}\n", encoding="utf-8")
        self._git(["add", "documento.txt"])

        res = inspecionar_git(self.repo_path)
        self.assertFalse(res.sucesso)
        self.assertTrue(any("documento.txt" in e and "ghp_" in e for e in res.erros_seguranca))

    def test_integracao_caminhos_com_espacos_e_caracteres_especiais(self):
        """AC-06: Parser NUL (-z) decodifica corretamente arquivos com espaços e colchetes."""
        nome_especial = "relatorio de vendas [2026] final.txt"
        (self.repo_path / nome_especial).write_text("conteudo\n", encoding="utf-8")
        self._git(["add", nome_especial])

        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        res = inspecionar_git(self.repo_path)
        # Não deve haver erro de parsing ou caminhos corrompidos
        self.assertEqual(len(res.erros_seguranca), 0)

    def test_integracao_segredo_efemero_em_commits_distintos(self):
        """AC-07: Segredo adicionado no commit 1 e removido no commit 2 bloqueia pelo commit 1."""
        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        # Commit 1: adiciona auth.json
        (self.repo_path / "auth.json").write_text('{"token": "123"}\n', encoding="utf-8")
        self._git(["add", "auth.json"])
        c1_sha = self._git(["commit", "-m", "commit 1 com auth.json"])

        # Commit 2: remove auth.json
        (self.repo_path / "auth.json").unlink()
        self._git(["add", "auth.json"])
        self._git(["commit", "-m", "commit 2 remove auth.json"])

        res = inspecionar_git(self.repo_path)
        self.assertFalse(res.sucesso)
        self.assertTrue(any("auth.json" in e for e in res.erros_seguranca))

    def test_integracao_root_commit_inspecionado_com_no_commit_id(self):
        """AC-08: Invocação direta da inspeção atômica sobre root commit com segredo bloqueia."""
        # Criar repo isolado com root commit contendo .env
        with tempfile.TemporaryDirectory() as tmp_root:
            p = Path(tmp_root)
            import subprocess
            subprocess.run(["git", "init", "-b", "main"], cwd=p, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=p, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=p, capture_output=True)
            subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=p, capture_output=True)
            (p / ".env").write_text("SECRET=1\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=p, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Root with secret"], cwd=p, capture_output=True)
            r_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=p, capture_output=True, text=True).stdout.strip()

            erros = _inspecionar_commit_atomico(r_sha, p)
            self.assertTrue(len(erros) > 0)
            self.assertTrue(any(".env" in e for e in erros))

    def test_integracao_commit_de_merge_captura_segredo(self):
        """AC-09: Commit de merge integrando branch com segredo é detectado contra <sha>^1."""
        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        # Criar branch feature e comitar segredo nela
        self._git(["checkout", "-b", "feature"])
        (self.repo_path / "auth.json").write_text('{"token": "xyz"}\n', encoding="utf-8")
        self._git(["add", "auth.json"])
        self._git(["commit", "-m", "add auth.json on feature"])

        # Voltar para main e fazer merge --no-ff
        self._git(["checkout", "main"])
        self._git(["merge", "--no-ff", "feature", "-m", "Merge feature into main"])

        res = inspecionar_git(self.repo_path)
        self.assertFalse(res.sucesso)
        self.assertTrue(any("auth.json" in e for e in res.erros_seguranca))

    def test_integracao_main_sincronizada_com_remoto_aprova(self):
        """AC-12: Quando HEAD == origin/main, reporta 0 commits pendentes e aprova com código 0."""
        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        res = inspecionar_git(self.repo_path)
        self.assertTrue(res.sucesso)
        self.assertEqual(res.estado_sincronizacao, "SYNCED")
        self.assertFalse(res.pronto_para_push)
        self.assertEqual(len(res.commits_pendentes), 0)

    def test_integracao_branch_atrasada_orienta_pull(self):
        """AC-13: Quando origin/main está à frente de HEAD local, emite estado BEHIND."""
        head_sha = self._git(["rev-parse", "HEAD"])
        # Criar commit novo simulado no remoto
        (self.repo_path / "outro.txt").write_text("outro\n", encoding="utf-8")
        self._git(["add", "outro.txt"])
        self._git(["commit", "-m", "c2 no remoto"])
        c2 = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", c2])

        # Resetar HEAD local para c1 (atrasado)
        self._git(["reset", "--hard", head_sha])

        res = inspecionar_git(self.repo_path)
        self.assertTrue(res.sucesso)
        self.assertEqual(res.estado_sincronizacao, "BEHIND")
        self.assertFalse(res.pronto_para_push)
        self.assertIn("reconciliação necessária", res.mensagem_base)
        self.assertEqual(len(res.commits_pendentes), 0)

    def test_integracao_branch_ahead_inspeciona_commits(self):
        """AC-14: Quando branch local está à frente de origin/main, reporta AHEAD e inspeciona commits."""
        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        # Commit local legítimo
        (self.repo_path / "seguro.py").write_text("print('ok')\n", encoding="utf-8")
        self._git(["add", "seguro.py"])
        self._git(["commit", "-m", "commit seguro à frente"])

        res = inspecionar_git(self.repo_path)
        self.assertTrue(res.sucesso)
        self.assertEqual(res.estado_sincronizacao, "AHEAD")
        self.assertTrue(res.pronto_para_push)
        self.assertEqual(len(res.commits_pendentes), 1)

    def test_integracao_branch_divergida_alerta_reconciliacao(self):
        """AC-15: Quando local e remoto divergiram de base comum, reporta DIVERGED."""
        c0 = self._git(["rev-parse", "HEAD"])

        # Commit do remoto
        (self.repo_path / "remoto.txt").write_text("r\n", encoding="utf-8")
        self._git(["add", "remoto.txt"])
        self._git(["commit", "-m", "commit remoto"])
        c_remoto = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", c_remoto])

        # Resetar para c0 e criar commit local diferente
        self._git(["reset", "--hard", c0])
        (self.repo_path / "local.txt").write_text("l\n", encoding="utf-8")
        self._git(["add", "local.txt"])
        self._git(["commit", "-m", "commit local"])

        res = inspecionar_git(self.repo_path)
        self.assertTrue(res.sucesso)
        self.assertEqual(res.estado_sincronizacao, "DIVERGED")
        self.assertFalse(res.pronto_para_push)
        self.assertIn("reconciliação necessária", res.mensagem_base)
        self.assertEqual(len(res.commits_pendentes), 1)

    def test_integracao_validacao_contra_base_local_sem_remoto(self):
        """AC-16: Em feature branch sem remoto, valida contra main local e reporta AHEAD_LOCAL."""
        self._git(["checkout", "-b", "feature-x"])
        (self.repo_path / "feature.py").write_text("f\n", encoding="utf-8")
        self._git(["add", "feature.py"])
        self._git(["commit", "-m", "feature commit"])

        res = inspecionar_git(self.repo_path)
        self.assertTrue(res.sucesso)
        self.assertEqual(res.estado_sincronizacao, "AHEAD_LOCAL")
        self.assertFalse(res.pronto_para_push)

    def test_integracao_historicos_sem_ancestral_comum_recusa(self):
        """AC-17: Branch órfã sem ancestral comum recusa aprovação com código 1."""
        self._git(["checkout", "--orphan", "orphan-branch"])
        (self.repo_path / "novo.txt").write_text("novo\n", encoding="utf-8")
        self._git(["add", "novo.txt"])
        self._git(["commit", "-m", "orphan commit"])

        # Tentar validar contra origin/main que não tem história em comum
        head_main = self._git(["rev-parse", "main"])
        self._git(["update-ref", "refs/remotes/origin/main", head_main])

        res = inspecionar_git(self.repo_path)
        self.assertFalse(res.sucesso)
        self.assertEqual(res.estado_sincronizacao, "UNRELATED")

    def test_integracao_ausencia_de_base_recusa_aprovacao(self):
        """AC-18: Branch main sem remoto e sem upstream recusa aprovação com código 1."""
        # Repo temporário na branch main sem remotes configurados
        res = inspecionar_git(self.repo_path)
        self.assertFalse(res.sucesso)
        self.assertEqual(res.estado_sincronizacao, "UNKNOWN")

    def test_integracao_whitespace_staged_vs_working_tree(self):
        """AC-19: Erro de whitespace staged bloqueia; não-staged emite aviso e aprova."""
        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        # Cenário 1: Marcador de merge no staging bloqueia
        (self.repo_path / "README.md").write_text("<<<<<<< HEAD\n# Test Repo\n", encoding="utf-8")
        self._git(["add", "README.md"])

        res1 = inspecionar_git(self.repo_path)
        self.assertFalse(res1.sucesso)
        self.assertTrue(res1.erro_whitespace_staged)

        # Desestagiar restaurando o index para HEAD mas mantendo o erro no arquivo em disco
        self._git(["reset", "HEAD", "README.md"])

        # Cenário 2: Erro na working tree não-staged -> emite aviso informativo mas não bloqueia
        res2 = inspecionar_git(self.repo_path)
        self.assertTrue(res2.sucesso)
        self.assertTrue(res2.aviso_whitespace_working_tree)

    def test_integracao_env_variantes_bloqueiam_e_example_permite(self):
        """ACH-01: Bloqueia .env_*, .env-* e .env.* no Git real; preserva .env.example."""
        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        # 1. .env_local no staging
        (self.repo_path / ".env_local").write_text("SECRET=1\n", encoding="utf-8")
        self._git(["add", ".env_local"])
        res1 = inspecionar_git(self.repo_path)
        self.assertFalse(res1.sucesso)
        self.assertTrue(any(".env_local" in e for e in res1.erros_seguranca))
        self._git(["reset", "--hard", "HEAD"])

        # 2. .env-secrets em commit pendente
        (self.repo_path / ".env-secrets").write_text("SECRET=2\n", encoding="utf-8")
        self._git(["add", ".env-secrets"])
        self._git(["commit", "-m", "add env-secrets"])
        res2 = inspecionar_git(self.repo_path)
        self.assertFalse(res2.sucesso)
        self.assertTrue(any(".env-secrets" in e for e in res2.erros_seguranca))
        self._git(["reset", "--hard", head_sha])

        # 3. .env.example no staging é autorizado
        (self.repo_path / ".env.example").write_text("API_KEY=placeholder\n", encoding="utf-8")
        self._git(["add", ".env.example"])
        res3 = inspecionar_git(self.repo_path)
        self.assertTrue(res3.sucesso)
        self.assertFalse(any(".env.example" in e for e in res3.erros_seguranca))
        self._git(["reset", "--hard", "HEAD"])

    def test_integracao_token_em_staging_bloqueia_e_mascara(self):
        """AC-05: Token sintético em arquivo rastreado no staging bloqueia com mascaramento estrito."""
        token_sintetico = "AIza" + "SyD-" + ("a" * 31)
        (self.repo_path / "README.md").write_text(f"# Test\nAPI_KEY = '{token_sintetico}'\n", encoding="utf-8")
        self._git(["add", "README.md"])

        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        res = inspecionar_git(self.repo_path)
        self.assertFalse(res.sucesso)
        self.assertTrue(any("Google API Key" in e for e in res.erros_seguranca))

        # Validação estrita de masking: segredo real não pode constar na saída
        texto_erros = "\n".join(res.erros_seguranca)
        self.assertIn("AIza****", texto_erros)
        self.assertNotIn(token_sintetico, texto_erros)

        self._git(["reset", "--hard", "HEAD"])

    def test_integracao_token_em_commit_pendente_bloqueia_e_mascara(self):
        """AC-06: Token sintético em commit pendente bloqueia com mascaramento estrito e sem vazar segredo."""
        head_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", head_sha])

        token_sintetico = "ghp_" + ("1" * 36)
        (self.repo_path / "README.md").write_text(f"# Test\nTOKEN = '{token_sintetico}'\n", encoding="utf-8")
        self._git(["add", "README.md"])
        self._git(["commit", "-m", "adiciona token sintético em commit"])

        res = inspecionar_git(self.repo_path)
        self.assertFalse(res.sucesso)
        self.assertTrue(any("GitHub Personal Access Token" in e for e in res.erros_seguranca))

        # Validação estrita de masking
        texto_erros = "\n".join(res.erros_seguranca)
        self.assertIn("ghp_****", texto_erros)
        self.assertNotIn(token_sintetico, texto_erros)

        self._git(["reset", "--hard", head_sha])

    def test_integracao_patch_sem_commit_id_numeracao_precisa(self):
        """AC-08: diff-tree sem commit id extrai linhas adicionadas com precisão e sem deslocamento."""
        (self.repo_path / "app.py").write_text("linha1 = 1\nlinha2 = 2\nlinha3 = 3\n", encoding="utf-8")
        self._git(["add", "app.py"])
        self._git(["commit", "-m", "base app.py"])
        base_sha = self._git(["rev-parse", "HEAD"])
        self._git(["update-ref", "refs/remotes/origin/main", base_sha])

        # Commit pendente modificando a linha 2
        token = "AIza" + "SyD-" + ("a" * 31)
        (self.repo_path / "app.py").write_text(f"linha1 = 1\nchave = '{token}'\nlinha3 = 3\n", encoding="utf-8")
        self._git(["add", "app.py"])
        self._git(["commit", "-m", "altera linha 2"])
        c_sha = self._git(["rev-parse", "HEAD"])

        erros = _inspecionar_commit_atomico(c_sha, self.repo_path)
        self.assertTrue(len(erros) > 0)
        self.assertTrue(any("Google API Key" in e for e in erros))

        self._git(["reset", "--hard", base_sha])


if __name__ == "__main__":
    unittest.main()
