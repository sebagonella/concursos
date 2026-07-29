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

  suite="${d}scripts/tests/test_smoke.py"
  if [[ ! -f "$suite" ]]; then
    echo "⏭️  $skill — sem suíte de testes"
    continue
  fi

  total=$((total + 1))
  echo "▶️  $skill"
  if saida=$(python3 "$suite" 2>&1); then
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
