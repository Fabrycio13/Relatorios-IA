#!/usr/bin/env python3
"""
Preflight Canônico do Relatórios-IA (Especificação Técnica v8.1.1).

Ferramenta autônoma, estritamente de leitura (read-only), multiplataforma e
construída exclusivamente com a biblioteca padrão do Python.

Executa:
1. Validação de ambiente Git.
2. Inspeção de segurança de staging (caminhos, blobs de cópias/renomeações e segredos no diff).
3. Resolução determinística de base de comparação e integridade do histórico local.
4. Inspeção individual atômica de cada commit pendente (root, normal ou merge).
5. Verificação de erros de whitespace no staging (bloqueante) e working tree (informativo).
6. Execução canônica e dinâmica da suíte de testes herméticos via unittest.
"""

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ==============================================================================
# 1. Configuração e Constantes de Segurança
# ==============================================================================

EXTENSOES_CHAVES_PRIVADAS = {".pem", ".key", ".pfx", ".pkcs12"}

ARQUIVOS_EXATOS_PROIBIDOS = {
    "auth.json",
    "email_config.json",
    "data/ultimo_envio.txt",
    "data/ultimo_envio.lock",
    "data/snapshot.lock",
    "ultimo_envio.txt",
    "ultimo_envio.lock",
}

PREFIXOS_DIRETORIOS_PROIBIDOS = (
    ".session/",
    "data/quarantine/",
)

CAMINHOS_PROIBIDOS = list(ARQUIVOS_EXATOS_PROIBIDOS) + list(PREFIXOS_DIRETORIOS_PROIBIDOS)

REGEX_SEGREDOS = [
    (
        "Chave Privada PEM",
        re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"),
    ),
    (
        "GitHub Personal Access Token (Classic)",
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}"),
    ),
    (
        "GitHub Fine-Grained Token",
        re.compile(r"github_pat_[A-Za-z0-9_]{82}"),
    ),
    (
        "Google API Key",
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    ),
    (
        "Senha de Aplicativo Gmail",
        re.compile(r"(?i)GMAIL_APP_PASSWORD\s*[:=]\s*['\"][a-z ]{16,20}['\"]"),
    ),
]


# ==============================================================================
# 2. Estruturas de Dados de Resultado
# ==============================================================================

@dataclass
class ResultadoInspecaoGit:
    sucesso: bool = True
    estado_sincronizacao: str = "UNKNOWN"
    pronto_para_push: bool = False
    mensagem_base: str = ""
    commits_pendentes: list[str] = field(default_factory=list)
    erros_seguranca: list[str] = field(default_factory=list)
    erro_whitespace_staged: bool = False
    detalhes_whitespace_staged: str = ""
    aviso_whitespace_working_tree: bool = False
    detalhes_whitespace_working_tree: str = ""
    mensagem_erro: str = ""


@dataclass
class ResultadoSuiteTestes:
    sucesso: bool = True
    quantidade_testes: int = 0
    mensagem: str = ""
    saida_completa: str = ""


# ==============================================================================
# 3. Funções Auxiliares de Git e Segurança
# ==============================================================================

def mascarar_segredo(segredo: str) -> str:
    """Mascara o valor de um segredo preservando apenas o prefixo identificador."""
    if not segredo:
        return "****"
    if segredo.startswith("-----BEGIN"):
        return "-----BEGIN PRIVATE KEY [MASCARADO]-----"
    prefixo_len = min(4, len(segredo))
    return f"{segredo[:prefixo_len]}****...****"


def _eh_caminho_proibido(caminho: str) -> bool:
    """Valida se um caminho normalizado viola as regras de caminhos sensíveis."""
    if not caminho:
        return False
    norm = caminho.replace("\\", "/").strip().lstrip("/")
    norm_lower = norm.lower()

    # Exceção autorizada: .env.example
    if norm_lower == ".env.example" or norm_lower.endswith("/.env.example"):
        return False

    # Regra .env e variantes (.env.*, .env_*, .env-*)
    partes = norm_lower.split("/")
    nome_arquivo = partes[-1]
    if (
        nome_arquivo == ".env"
        or nome_arquivo.startswith(".env.")
        or nome_arquivo.startswith(".env_")
        or nome_arquivo.startswith(".env-")
    ):
        return True

    # Arquivos exatos proibidos
    if norm_lower in ARQUIVOS_EXATOS_PROIBIDOS or any(norm_lower.endswith("/" + a) for a in ARQUIVOS_EXATOS_PROIBIDOS):
        return True

    # Extensões de chaves criptográficas
    for ext in EXTENSOES_CHAVES_PRIVADAS:
        if norm_lower.endswith(ext):
            return True

    # Prefixos de diretórios operacionais ou sensíveis
    for prefixo in PREFIXOS_DIRETORIOS_PROIBIDOS:
        if norm_lower.startswith(prefixo) or f"/{prefixo}" in norm_lower:
            return True

    # Padrões operacionais em data/
    if norm_lower.startswith("data/") or "/data/" in norm_lower:
        if norm_lower.endswith(".lock") or norm_lower.endswith(".tmp"):
            return True

    if norm_lower.endswith(".lock"):
        return True

    return False


def _exec_git(args: list[str], repo_root: Path, check: bool = False) -> tuple[int, bytes, bytes]:
    """Executa um comando Git estritamente de leitura com isolamento de ambiente."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        ["git"] + args,
        cwd=repo_root,
        capture_output=True,
        env=env
    )
    if check and proc.returncode != 0:
        err_msg = proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"Comando Git falhou: git {' '.join(args)}\n{err_msg}")
    return proc.returncode, proc.stdout, proc.stderr


def _parse_name_status_z(raw_bytes: bytes) -> list[tuple[str, str, str | None]]:
    """
    Decodifica a saída NUL (-z) de git diff --name-status ou git diff-tree.
    Retorna lista de tuplas: (status, path, new_path_or_none).
    """
    if not raw_bytes:
        return []

    tokens = raw_bytes.split(b"\x00")
    if tokens and not tokens[-1]:
        tokens.pop()  # Remove trailing empty token

    resultado: list[tuple[str, str, str | None]] = []
    i = 0
    total = len(tokens)
    while i < total:
        status_token = tokens[i].decode("utf-8", errors="replace").strip()
        i += 1
        if not status_token:
            continue

        if status_token.startswith(("R", "C")):
            if i + 1 < total:
                old_path = tokens[i].decode("utf-8", errors="replace")
                new_path = tokens[i + 1].decode("utf-8", errors="replace")
                i += 2
                resultado.append((status_token, old_path, new_path))
            else:
                break
        else:
            if i < total:
                path = tokens[i].decode("utf-8", errors="replace")
                i += 1
                resultado.append((status_token, path, None))
            else:
                break

    return resultado


def _escanear_linhas_por_segredos(linhas: list[str], contexto_arquivo: str) -> list[str]:
    """Escaneia linhas adicionadas buscando por padrões de segredos com masking de saída."""
    erros: list[str] = []
    for num_linha, linha in enumerate(linhas, start=1):
        if not linha.startswith("+") or linha.startswith("+++"):
            continue
        conteudo = linha[1:]  # remove o prefixo '+'
        for nome_segredo, padrao in REGEX_SEGREDOS:
            match = padrao.search(conteudo)
            if match:
                segredo_real = match.group(0)
                segredo_mascarado = mascarar_segredo(segredo_real)
                erros.append(
                    f"Padrão de segredo '{nome_segredo}' detectado em '{contexto_arquivo}' "
                    f"(linha {num_linha}): '{segredo_mascarado}'."
                )
    return erros


def _inspecionar_blob(repo_root: Path, ref_blob: str, caminho_para_contexto: str) -> list[str]:
    """Lê o conteúdo integral de um blob no index ou commit e escaneia contra padrões de segredos."""
    code, out, _ = _exec_git(["show", "--no-ext-diff", "--no-textconv", ref_blob], repo_root)
    if code != 0 or not out:
        return []

    try:
        texto = out.decode("utf-8", errors="replace")
    except Exception:
        return []

    erros: list[str] = []
    for nome_segredo, padrao in REGEX_SEGREDOS:
        match = padrao.search(texto)
        if match:
            segredo_real = match.group(0)
            segredo_mascarado = mascarar_segredo(segredo_real)
            erros.append(
                f"Padrão de segredo '{nome_segredo}' detectado no conteúdo do arquivo "
                f"'{caminho_para_contexto}' via inspeção de blob: '{segredo_mascarado}'."
            )
    return erros


def _avaliar_tokens_status(
    tokens: list[tuple[str, str, str | None]],
    repo_root: Path,
    commit_sha: str | None = None
) -> list[str]:
    """Avalia cada status e caminho decodificado pelo parser Git."""
    erros: list[str] = []
    prefixo_contexto = f"no commit {commit_sha[:8]}" if commit_sha else "no staging"

    for status_token, path, new_path in tokens:
        status_code = status_token[0].upper() if status_token else ""

        # Status U: Unmerged (conflito)
        if status_code == "U":
            erros.append(f"Conflito de merge não resolvido (status 'U') detectado em '{path}' {prefixo_contexto}.")
            continue

        # Status B, X ou desconhecido: Bloqueia de forma fail-safe
        if status_code in ("B", "X") or status_code not in ("A", "M", "D", "R", "C", "T"):
            erros.append(f"Status Git anômalo ou não resolvido ('{status_token}') detectado em '{path}' {prefixo_contexto}.")
            continue

        # Status D: Exclusão é permitida (saneamento seguro)
        if status_code == "D":
            continue

        # Status R ou C: Renomeação ou Cópia
        if status_code in ("R", "C"):
            if _eh_caminho_proibido(path):
                erros.append(f"Operação '{status_token}' com caminho de origem proibido '{path}' {prefixo_contexto}.")
            if new_path and _eh_caminho_proibido(new_path):
                erros.append(f"Operação '{status_token}' com caminho de destino proibido '{new_path}' {prefixo_contexto}.")

            # Para cópias (C), inspeciona o blob de destino integralmente
            if status_code == "C" and new_path:
                ref_blob = f"{commit_sha}:{new_path}" if commit_sha else f":{new_path}"
                erros_blob = _inspecionar_blob(repo_root, ref_blob, new_path)
                erros.extend(erros_blob)
            continue

        # Status A, M, T: Adição, Modificação ou Troca de Tipo
        if _eh_caminho_proibido(path):
            erros.append(f"Arquivo sensível/operacional proibido '{path}' (status '{status_token}') detectado {prefixo_contexto}.")

    return erros


def _inspecionar_commit_atomico(commit_sha: str, repo_root: Path) -> list[str]:
    """Inspeciona caminhos, status e conteúdo de um único commit (root, normal ou merge)."""
    erros: list[str] = []

    # Identificar quantidade de pais do commit
    _, parents_out, _ = _exec_git(["rev-list", "--parents", "-n", "1", commit_sha], repo_root)
    partes_parents = parents_out.decode("utf-8", errors="replace").strip().split()
    # partes_parents[0] é o próprio commit_sha; os subsequentes são os pais
    num_pais = len(partes_parents) - 1

    if num_pais <= 0:
        # Root commit (0 pais): usa --root e --no-commit-id
        cmd_status = ["diff-tree", "--no-commit-id", "--root", "-r", "-z", "--name-status", "-C", "--find-copies-harder", "--no-ext-diff", commit_sha]
        cmd_patch = ["diff-tree", "--no-commit-id", "--root", "-p", "-U0", "--no-ext-diff", "--no-textconv", commit_sha]
    elif num_pais == 1:
        # Commit normal (1 pai): compara contra <commit>~1
        cmd_status = ["diff-tree", "--no-commit-id", "-r", "-z", "--name-status", "-C", "--find-copies-harder", "--no-ext-diff", f"{commit_sha}~1", commit_sha]
        cmd_patch = ["diff-tree", "--no-commit-id", "-p", "-U0", "--no-ext-diff", "--no-textconv", f"{commit_sha}~1", commit_sha]
    else:
        # Commit de merge (>= 2 pais): compara deterministicamente contra o primeiro pai <commit>^1
        cmd_status = ["diff-tree", "--no-commit-id", "-r", "-z", "--name-status", "-C", "--find-copies-harder", "--no-ext-diff", f"{commit_sha}^1", commit_sha]
        cmd_patch = ["diff-tree", "--no-commit-id", "-p", "-U0", "--no-ext-diff", "--no-textconv", f"{commit_sha}^1", commit_sha]

    # 1. Inspeção de caminhos e status
    code_s, out_s, _ = _exec_git(cmd_status, repo_root)
    if code_s == 0 and out_s:
        tokens = _parse_name_status_z(out_s)
        erros_status = _avaliar_tokens_status(tokens, repo_root, commit_sha=commit_sha)
        erros.extend(erros_status)

    # 2. Inspeção de conteúdo adicionado
    code_p, out_p, _ = _exec_git(cmd_patch, repo_root)
    if code_p == 0 and out_p:
        linhas = out_p.decode("utf-8", errors="replace").splitlines()
        erros_conteudo = _escanear_linhas_por_segredos(linhas, f"commit {commit_sha[:8]}")
        erros.extend(erros_conteudo)

    return erros


# ==============================================================================
# 4. Inspeção Git Principal (inspecionar_git)
# ==============================================================================

def inspecionar_git(repo_root: Path) -> ResultadoInspecaoGit:
    """Executa a inspeção estrita de segurança e integridade Git sobre o repositório."""
    res = ResultadoInspecaoGit()

    # Passo 1: Verificar se o executável Git existe e se é repositório Git válido
    try:
        code_wt, out_wt, err_wt = _exec_git(["rev-parse", "--is-inside-work-tree"], repo_root)
    except FileNotFoundError:
        res.sucesso = False
        res.mensagem_erro = "O comando 'git' não foi encontrado no PATH do sistema operacional."
        return res

    if code_wt != 0 or out_wt.strip() != b"true":
        res.sucesso = False
        res.mensagem_erro = f"O diretório '{repo_root}' não é um repositório Git válido."
        return res

    # Passo 2: Inspecionar staging (caminhos, blobs de cópias/renomeações e segredos)
    cmd_staged_status = ["diff", "--cached", "--name-status", "-C", "--find-copies-harder", "--no-ext-diff", "-z"]
    _, out_staged_s, _ = _exec_git(cmd_staged_status, repo_root)
    if out_staged_s:
        tokens_staged = _parse_name_status_z(out_staged_s)
        erros_staged = _avaliar_tokens_status(tokens_staged, repo_root, commit_sha=None)
        res.erros_seguranca.extend(erros_staged)

    cmd_staged_patch = ["diff", "--cached", "-U0", "--no-ext-diff", "--no-textconv"]
    _, out_staged_p, _ = _exec_git(cmd_staged_patch, repo_root)
    if out_staged_p:
        linhas_staged = out_staged_p.decode("utf-8", errors="replace").splitlines()
        erros_staged_conteudo = _escanear_linhas_por_segredos(linhas_staged, "staging")
        res.erros_seguranca.extend(erros_staged_conteudo)

    # Passo 3: Whitespace check no staging (bloqueante)
    code_ws_staged, out_ws_staged, err_ws_staged = _exec_git(["diff", "--cached", "--check"], repo_root)
    if code_ws_staged != 0:
        res.erro_whitespace_staged = True
        res.detalhes_whitespace_staged = (out_ws_staged + err_ws_staged).decode("utf-8", errors="replace").strip()

    # Passo 4: Whitespace check na working tree (informativo)
    code_ws_wt, out_ws_wt, err_ws_wt = _exec_git(["diff", "--check"], repo_root)
    if code_ws_wt != 0:
        res.aviso_whitespace_working_tree = True
        res.detalhes_whitespace_working_tree = (out_ws_wt + err_ws_wt).decode("utf-8", errors="replace").strip()

    # Passo 5: Resolução determinística de base e relacionamento Git
    branch_atual_code, branch_atual_out, _ = _exec_git(["branch", "--show-current"], repo_root)
    branch_atual = branch_atual_out.decode("utf-8", errors="replace").strip()

    head_code, head_out, _ = _exec_git(["rev-parse", "HEAD"], repo_root)
    sha_head = head_out.decode("utf-8", errors="replace").strip() if head_code == 0 else ""

    base_ref: str | None = None
    tipo_base: str = "UNKNOWN"

    # Precedência 1: Upstream configurado
    up_code, up_out, _ = _exec_git(["rev-parse", "--verify", "@{upstream}"], repo_root)
    if up_code == 0 and up_out.strip():
        base_ref = "@{upstream}"
        tipo_base = "REMOTA"

    # Precedência 2: Referência remota local origin/main
    if not base_ref:
        for ref_remota in ["origin/main", "origin/master"]:
            c_rem, out_rem, _ = _exec_git(["rev-parse", "--verify", ref_remota], repo_root)
            if c_rem == 0 and out_rem.strip():
                base_ref = ref_remota
                tipo_base = "REMOTA"
                break

    # Precedência 3: Branch principal local main (válida somente se branch atual não for ela mesma)
    if not base_ref and branch_atual not in ("main", "master"):
        for ref_local in ["main", "master"]:
            c_loc, out_loc, _ = _exec_git(["rev-parse", "--verify", ref_local], repo_root)
            if c_loc == 0 and out_loc.strip():
                base_ref = ref_local
                tipo_base = "LOCAL"
                break

    if not base_ref:
        res.estado_sincronizacao = "UNKNOWN"
        res.mensagem_base = "Não foi possível determinar uma base confiável (upstream ou origin/main)."
        res.sucesso = False
        return res

    # Obter SHA da base
    _, base_sha_out, _ = _exec_git(["rev-parse", base_ref], repo_root)
    sha_base = base_sha_out.decode("utf-8", errors="replace").strip()

    if tipo_base == "REMOTA":
        if sha_head == sha_base:
            res.estado_sincronizacao = "SYNCED"
            res.pronto_para_push = False
            res.mensagem_base = f"Sincronizada com {base_ref} (0 commits pendentes)."
        else:
            mb_code, mb_out, _ = _exec_git(["merge-base", sha_base, sha_head], repo_root)
            sha_mb = mb_out.decode("utf-8", errors="replace").strip() if mb_code == 0 else ""

            if not sha_mb:
                res.estado_sincronizacao = "UNRELATED"
                res.pronto_para_push = False
                res.mensagem_base = f"Históricos sem ancestral comum com {base_ref}."
                res.sucesso = False
                return res
            elif sha_mb == sha_head:
                res.estado_sincronizacao = "BEHIND"
                res.pronto_para_push = False
                res.mensagem_base = f"Branch local atrasada em relação a {base_ref} (reconciliação necessária: git pull antes de publicar)."
            elif sha_mb == sha_base:
                res.estado_sincronizacao = "AHEAD"
                # Obter commits pendentes base..HEAD
                _, rev_out, _ = _exec_git(["rev-list", f"{sha_base}..{sha_head}"], repo_root)
                res.commits_pendentes = [c.strip() for c in rev_out.decode("utf-8", errors="replace").splitlines() if c.strip()]
                res.pronto_para_push = True
                res.mensagem_base = f"Branch à frente de {base_ref} ({len(res.commits_pendentes)} commits locais prontos para envio)."
            else:
                res.estado_sincronizacao = "DIVERGED"
                res.pronto_para_push = False
                _, rev_out, _ = _exec_git(["rev-list", f"{sha_mb}..{sha_head}"], repo_root)
                res.commits_pendentes = [c.strip() for c in rev_out.decode("utf-8", errors="replace").splitlines() if c.strip()]
                res.mensagem_base = f"Branch divergida de {base_ref} ({len(res.commits_pendentes)} commits locais; reconciliação necessária: git merge/rebase antes de publicar)."
    else:
        # Base local (Precedência 3)
        mb_code, mb_out, _ = _exec_git(["merge-base", sha_base, sha_head], repo_root)
        sha_mb = mb_out.decode("utf-8", errors="replace").strip() if mb_code == 0 else ""
        if sha_mb:
            _, rev_out, _ = _exec_git(["rev-list", f"{sha_mb}..{sha_head}"], repo_root)
            res.commits_pendentes = [c.strip() for c in rev_out.decode("utf-8", errors="replace").splitlines() if c.strip()]
            res.estado_sincronizacao = "AHEAD_LOCAL"
            res.pronto_para_push = False
            res.mensagem_base = f"Commits validados contra a referência local '{base_ref}' (sem base remota; não confere prontidão para push)."
        else:
            res.estado_sincronizacao = "UNRELATED"
            res.pronto_para_push = False
            res.sucesso = False
            return res

    # Passo 6: Inspecionar commits pendentes individualmente
    for commit_sha in res.commits_pendentes:
        erros_commit = _inspecionar_commit_atomico(commit_sha, repo_root)
        res.erros_seguranca.extend(erros_commit)

    # Avaliar sucesso final da inspeção Git
    if res.erros_seguranca or res.erro_whitespace_staged or not res.sucesso:
        res.sucesso = False

    return res


# ==============================================================================
# 5. Execução da Suíte Canônica de Testes (executar_suite_testes)
# ==============================================================================

def executar_suite_testes(repo_root: Path, python_bin: str = sys.executable) -> ResultadoSuiteTestes:
    """Executa a suíte canônica hermética de testes via unittest com descoberta dinâmica."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    cmd = [python_bin, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env
    )

    saida = (proc.stdout or "") + "\n" + (proc.stderr or "")
    matches_ran = re.findall(r"Ran (\d+) tests", saida)
    qtd_testes = int(matches_ran[-1]) if matches_ran else 0

    sucesso_testes = (proc.returncode == 0 and qtd_testes > 0 and "\nOK" in saida)

    res = ResultadoSuiteTestes(
        sucesso=sucesso_testes,
        quantidade_testes=qtd_testes,
        saida_completa=saida
    )

    if qtd_testes == 0:
        res.sucesso = False
        res.mensagem = "Nenhum teste automatizado foi executado (Ran 0 tests). A suíte deve localizar e executar testes válidos."
    elif proc.returncode != 0:
        res.sucesso = False
        res.mensagem = f"A suíte de testes falhou (código de saída: {proc.returncode})."
    else:
        res.mensagem = f"Todos os {qtd_testes} testes foram executados com sucesso (OK)."

    return res


# ==============================================================================
# 6. Ponto de Entrada Operacional (main)
# ==============================================================================

def main() -> int:
    """Orquestra a verificação completa de preflight e retorna código 0 ou 1."""
    repo_root = Path(__file__).resolve().parent.parent

    print("\n" + "=" * 70)
    print("🚀 INICIANDO PREFLIGHT CANÔNICO (Relatórios-IA)")
    print("=" * 70)

    # 1. Inspeção Git
    print("▶️  [1/2] Inspecionando integridade Git, staging e commits locais...")
    res_git = inspecionar_git(repo_root)

    if not res_git.sucesso:
        print("\n❌ FALHA DE SEGURANÇA OU INTEGRIDADE GIT:")
        if res_git.mensagem_erro:
            print(f"   • {res_git.mensagem_erro}")
        for erro in res_git.erros_seguranca:
            print(f"   • {erro}")
        if res_git.erro_whitespace_staged:
            print("   • Erros de whitespace ou marcadores de merge detectados no staging:")
            for l in res_git.detalhes_whitespace_staged.splitlines():
                print(f"     {l}")
        print("\nO preflight foi abortado. Corrija as violações acima antes de continuar.\n")
        return 1

    print("   ✓ Staging limpo de segredos e arquivos proibidos.")
    if res_git.commits_pendentes:
        print(f"   ✓ {len(res_git.commits_pendentes)} commit(s) local(is) pendente(s) inspecionado(s) individualmente sem violações.")
    print(f"   ✓ Estado de sincronização: {res_git.estado_sincronizacao} ({res_git.mensagem_base})")

    if res_git.aviso_whitespace_working_tree:
        print("\n⚠️  [DIAGNÓSTICO INFORMATIVO] Avisos de whitespace na working tree não-staged:")
        for l in res_git.detalhes_whitespace_working_tree.splitlines():
            print(f"   {l}")
        print("   (Como essas alterações não estão staged, a execução prosseguirá normalmente.)\n")

    # 2. Execução da Suíte de Testes
    print("\n▶️  [2/2] Executando suíte canônica completa de testes herméticos...")
    res_testes = executar_suite_testes(repo_root)

    if not res_testes.sucesso:
        print("\n❌ FALHA NA SUÍTE DE TESTES:")
        print(f"   • {res_testes.mensagem}")
        print("\nSaída dos testes:")
        print(res_testes.saida_completa[-2000:])  # Exibe os últimos 2000 caracteres
        return 1

    print(f"   ✓ {res_testes.mensagem}")

    # Conclusão Aprovada
    print("\n" + "=" * 70)
    print("✅ PREFLIGHT APROVADO COM SUCESSO (Validações locais concluídas)!")
    print(f"   Status da base: {res_git.mensagem_base}")
    if res_git.pronto_para_push:
        print("   🚀 PRONTIDÃO PARA PUBLICAÇÃO: SIM (commits locais validados e prontos para git push).")
    elif res_git.estado_sincronizacao == "SYNCED":
        print("   ℹ️  PRONTIDÃO PARA PUBLICAÇÃO: NENHUM COMMIT PENDENTE (sincronizada com o remoto).")
    elif res_git.estado_sincronizacao in ("BEHIND", "DIVERGED"):
        print("   ⚠️  PRONTIDÃO PARA PUBLICAÇÃO: NÃO (Reconciliação com o remoto necessária antes do push).")
    elif res_git.estado_sincronizacao == "AHEAD_LOCAL":
        print("   ⚠️  PRONTIDÃO PARA PUBLICAÇÃO: NÃO (Sem referência remota configurada).")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
