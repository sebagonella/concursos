#!/usr/bin/env bash
# test_install.sh - Testes do instalador. Roda standalone:
#     bash scripts/tests/test_install.sh
#
# Existe porque o `--uninstall` removia as skills e DEIXAVA os subagents para
# trás: sobravam 5 arquivos em ~/.claude/agents/ apontando para skills que não
# existiam mais. O defeito passou despercebido porque o test-all.sh só roda as
# suítes Python — nada cobria os scripts de shell, que são justamente os que
# mexem no ambiente do usuário.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FALHAS=0
PASSES=0

# O contador do rodape TEM de bater com a lista exibida: contradicao entre os dois
# foi o que denunciou um defeito real no gerador do site ("1 item listado sob 0/22").
ok()   { echo "  PASS  $1"; PASSES=$((PASSES + 1)); }
fail() { echo "  FAIL  $1: $2"; FALHAS=$((FALHAS + 1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# O modo --local instala em ./.claude relativo ao CWD, então basta rodar de
# dentro de um diretório temporário para não tocar no ambiente real.
cd "$TMP"
if bash "$REPO_ROOT/scripts/install.sh" --local > "$TMP/install.log" 2>&1; then
  ok "install_local_roda_sem_erro"
else
  fail "install_local_roda_sem_erro" "saiu com erro; veja $TMP/install.log"
fi

# --- instalação -------------------------------------------------------------
n_skills=$(find "$TMP/.claude/skills" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
esperado_skills=$(find "$REPO_ROOT/skills" -maxdepth 1 -mindepth 1 -type d | wc -l)
if [[ "$n_skills" -eq "$esperado_skills" && "$n_skills" -gt 0 ]]; then
  ok "install_instala_todas_as_skills ($n_skills)"
else
  fail "install_instala_todas_as_skills" "instalou $n_skills, esperado $esperado_skills"
fi

n_agents=$(find "$TMP/.claude/agents" -name "*.md" 2>/dev/null | wc -l)
esperado_agents=$(find "$REPO_ROOT/skills" -path "*/agents/*.md" | wc -l)
if [[ "$n_agents" -eq "$esperado_agents" && "$n_agents" -gt 0 ]]; then
  ok "install_instala_os_subagents ($n_agents)"
else
  fail "install_instala_os_subagents" "instalou $n_agents, esperado $esperado_agents"
fi

# --- agent de terceiro: o uninstall NÃO pode encostar ------------------------
mkdir -p "$TMP/.claude/agents"
echo "# agent de outro projeto" > "$TMP/.claude/agents/zz-agent-de-terceiro.md"

# --- desinstalação ----------------------------------------------------------
if bash "$REPO_ROOT/scripts/install.sh" --local --uninstall > "$TMP/uninstall.log" 2>&1; then
  ok "uninstall_roda_sem_erro"
else
  fail "uninstall_roda_sem_erro" "saiu com erro; veja $TMP/uninstall.log"
fi

restantes_skills=$(find "$TMP/.claude/skills" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
if [[ "$restantes_skills" -eq 0 ]]; then
  ok "uninstall_remove_as_skills"
else
  fail "uninstall_remove_as_skills" "sobraram $restantes_skills"
fi

# O defeito que este arquivo existe para travar.
orfaos=0
for origem in "$REPO_ROOT"/skills/*/agents/*.md; do
  [[ -f "$origem" ]] || continue
  [[ -f "$TMP/.claude/agents/$(basename "$origem")" ]] && orfaos=$((orfaos + 1))
done
if [[ "$orfaos" -eq 0 ]]; then
  ok "uninstall_remove_tambem_os_subagents"
else
  fail "uninstall_remove_tambem_os_subagents" "$orfaos subagent(s) orfao(s)"
fi

if [[ -f "$TMP/.claude/agents/zz-agent-de-terceiro.md" ]]; then
  ok "uninstall_preserva_agent_de_outro_projeto"
else
  fail "uninstall_preserva_agent_de_outro_projeto" "apagou agent que nao e deste repo"
fi

echo ""
TOTAL=$((PASSES + FALHAS))
if [[ "$FALHAS" -eq 0 ]]; then
  echo "$PASSES/$TOTAL testes passaram."
else
  echo "$PASSES/$TOTAL testes passaram — $FALHAS falha(s)."
fi
exit $((FALHAS > 0 ? 1 : 0))
