#!/usr/bin/env bash
# test-all.sh - Roda os smoke tests de todas as skills do repositório.
#
# Uso:
#   bash scripts/test-all.sh
#   bash scripts/test-all.sh --only concurso-prep

set -uo pipefail   # sem -e: queremos rodar TODAS as suítes mesmo se uma falhar

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"
ONLY="${2:-}"

[[ "${1:-}" == "--only" ]] && ONLY="${2:-}"

falhas=0
total=0

echo "🧪 Rodando testes das skills"
echo ""

for d in "$SKILLS_DIR"/*/; do
  skill="$(basename "$d")"
  [[ -f "${d}SKILL.md" ]] || continue
  [[ -n "$ONLY" && "$skill" != "$ONLY" ]] && continue

  # Toda suíte da skill, não só a `test_smoke.py`: quando a convenção de
  # material ganhou arquivo próprio (`test_material_id.py`), 65 testes ficaram
  # invisíveis para o CI porque o runner procurava um nome fixo.
  achou=0
  for suite in "${d}scripts/tests/"test_*.py; do
    [[ -f "$suite" ]] || continue
    achou=1
    nome="$(basename "$suite" .py)"
    total=$((total + 1))
    if [[ "$nome" == "test_smoke" ]]; then
      echo "▶️  $skill"
    else
      echo "▶️  $skill · $nome"
    fi
    if saida=$(python3 "$suite" 2>&1); then
      echo "$saida" | tail -1 | sed 's/^/   /'
    else
      echo "$saida" | sed 's/^/   /'
      falhas=$((falhas + 1))
    fi
    echo ""
  done
  [[ $achou -eq 0 ]] && echo "⏭️  $skill — sem suíte de testes"
done

# Suites de shell: os scripts que mexem no ambiente do usuario (install/deploy)
# nao eram cobertos por nada, e foi ai que passou o defeito do --uninstall
# deixando subagents orfaos.
for suite_sh in "$REPO_ROOT"/scripts/tests/test_*.sh; do
  [[ -f "$suite_sh" ]] || continue
  nome_sh="$(basename "$suite_sh" .sh)"
  echo "▶️  $nome_sh"
  total=$((total + 1))
  if saida=$(bash "$suite_sh" 2>&1); then
    echo "$saida" | tail -1 | sed 's/^/   /'
  else
    echo "$saida" | sed 's/^/   /'
    falhas=$((falhas + 1))
  fi
  echo ""
done

# Limpar caches gerados pelos testes
find "$SKILLS_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

if [[ $falhas -eq 0 ]]; then
  echo "✅ Todas as $total suíte(s) passaram."
  exit 0
else
  echo "❌ $falhas de $total suíte(s) falharam."
  exit 1
fi
