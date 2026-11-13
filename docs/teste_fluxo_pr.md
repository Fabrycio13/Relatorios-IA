# Teste de Aprendizado: Fluxo de Criação e Exclusão de Pull Requests

Este arquivo é um documento temporário criado exclusivamente para testar e praticar o fluxo completo de ciclo de vida de uma branch e Pull Request no GitHub.

---

## 🎯 Objetivo do Teste

Praticar manualmente as seguintes etapas:
1. Publicar esta branch local (`test/pr-exclusao`) para o repositório remoto (`origin`).
2. Abrir um Pull Request (PR) no GitHub comparando `test/pr-exclusao` com a branch base `main`.
3. Inspecionar as abas do PR:
   - **Conversation:** comentários e status de verificações.
   - **Commits:** histórico do commit isolado deste teste.
   - **Files changed:** visualização do diff (adição deste arquivo).
4. Fechar ou mesclar o Pull Request:
   - **Cenário A (Fechamento/Descarte):** Clicar em *Close pull request* sem merge (para simular uma branch descartada).
   - **Cenário B (Merge e Exclusão):** Fazer *Squash and merge* ou *Rebase and merge*.
5. Excluir a branch remota no GitHub (*Delete branch*).
6. Limpar a branch localmente e remover o worktree de teste.

---

## 📋 Comandos de Referência para as Próximas Etapas

### 1. Enviar a branch para o GitHub (Push)
> *Execute somente quando estiver pronto para iniciar o teste no GitHub:*
```bash
git push -u origin test/pr-exclusao
```

### 2. Abrir o PR no GitHub
- Acesse: https://github.com/Fabrycio13/Relatorios-IA
- Clique no botão **Compare & pull request** que aparecerá na barra amarela superior.
- Garanta que a base seja `main` e a compare seja `test/pr-exclusao`.
- Preencha título e descrição e clique em **Create pull request**.

### 3. Exclusão da Branch após o Teste
- No GitHub: clique em **Delete branch** na página do PR fechado/mesclado.
- Localmente (após concluir o teste):
```bash
# Para remover a branch remota via terminal (caso não tenha clicado no botão do GitHub):
git push origin --delete test/pr-exclusao

# Para retornar à branch principal ou original e deletar a branch local de teste:
git branch -D test/pr-exclusao

# Para limpar a referência do worktree temporário (executado da pasta principal):
git worktree remove "d:\Projetos\Relatorios-IA-test-pr"
```

---
*Nota: Este arquivo não altera código funcional e pode ser descartado a qualquer momento.*
