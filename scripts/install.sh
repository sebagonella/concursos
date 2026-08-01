#!/usr/bin/env bash
# install.sh - Instalador único do projeto concursos-vault-skills
#
# Descobre automaticamente todas as skills em skills/ e as instala no Claude Code.
# Skills novas não exigem edição deste script.
#
# Uso:
#   bash scripts/install.sh                        # todas, global (~/.claude/)
#   bash scripts/install.sh --local                # todas, local (.claude/)
#   bash scripts/install.sh --only concurso-prep   # apenas uma skill
#   bash scripts/install.sh --uninstall            # remove as skills E os subagents
#   bash scripts/install.sh --list                 # lista as skills disponíveis

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"

MODE="global"
ACTION="install"
ONLY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local) MODE="local"; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    --list) ACTION="list"; shift ;;
    --only) ONLY="${2:-}"; shift 2 ;;
    --help|-h)
      sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Opção desconhecida: $1 (use --help)"; exit 1 ;;
  esac
done

# Descobrir skills: toda subpasta de skills/ que tenha SKILL.md
descobrir_skills() {
  local encontradas=()
  for d in "$SKILLS_DIR"/*/; do
    [[ -f "${d}SKILL.md" ]] || continue
    encontradas+=("$(basename "$d")")
  done
  printf '%s\n' "${encontradas[@]}"
}

mapfile -t SKILLS < <(descobrir_skills)

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  echo "❌ Nenhuma skill encontrada em $SKILLS_DIR"
  exit 1
fi

if [[ -n "$ONLY" ]]; then
  if [[ ! " ${SKILLS[*]} " =~ " ${ONLY} " ]]; then
    echo "❌ Skill '$ONLY' não encontrada. Disponíveis: ${SKILLS[*]}"
    exit 1
  fi
  SKILLS=("$ONLY")
fi

# --list
if [[ "$ACTION" == "list" ]]; then
  echo "Skills disponíveis neste repositório:"
  for s in "${SKILLS[@]}"; do
    ver=$(grep -m1 '^version:' "$SKILLS_DIR/$s/SKILL.md" 2>/dev/null | sed 's/version: *//' || echo "?")
    echo "  - $s (v$ver)"
  done
  exit 0
fi

# Destino
if [[ "$MODE" == "local" ]]; then
  CLAUDE_DIR=".claude"
else
  CLAUDE_DIR="$HOME/.claude"
fi

# --uninstall
if [[ "$ACTION" == "uninstall" ]]; then
  for s in "${SKILLS[@]}"; do
    alvo="$CLAUDE_DIR/skills/$s"
    if [[ -d "$alvo" ]]; then
      rm -rf "$alvo"
      echo "🗑️  Removida: $s"
    fi
  done

  # Os subagents são instalados em $CLAUDE_DIR/agents/ (fora de skills/), e o
  # uninstall não os removia: sobravam 5 arquivos apontando para skills que não
  # existiam mais. Remove APENAS os que este repositório instala — comparando
  # pelo nome com skills/*/agents/ — para nunca apagar agent de outro projeto
  # que divida o mesmo diretório.
  n_agents=0
  for origem_agent in "$SKILLS_DIR"/*/agents/*.md; do
    [[ -f "$origem_agent" ]] || continue
    alvo_agent="$CLAUDE_DIR/agents/$(basename "$origem_agent")"
    if [[ -f "$alvo_agent" ]]; then
      rm -f "$alvo_agent"
      n_agents=$((n_agents + 1))
    fi
  done
  [[ $n_agents -gt 0 ]] && echo "🗑️  $n_agents subagent(s) removido(s) de $CLAUDE_DIR/agents/"

  echo "✅ Desinstalação concluída."
  exit 0
fi

# ---------------------------------------------------------------------------
# Instalação
# ---------------------------------------------------------------------------
echo "📦 Instalando skills do projeto ($MODE)..."
echo ""

# Pré-requisitos comuns
echo "🔍 Verificando pré-requisitos..."
if ! command -v python3 &> /dev/null; then
  echo "❌ python3 não encontrado. Instale Python 3.10+."
  exit 1
fi
PYV=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "   python3 $PYV ✓"

if ! command -v pdftotext &> /dev/null; then
  echo "   ⚠️  pdftotext ausente (necessário para ler editais e livros em PDF)"
  echo "      Linux: sudo apt install poppler-utils | macOS: brew install poppler"
else
  echo "   pdftotext ✓"
fi

if ! python3 -c "import reportlab" &> /dev/null; then
  echo "   ℹ️  reportlab ausente (usado para gerar leis em PDF; o .md continua funcionando)"
  echo "      Instale com: pip install -r skills/concurso-prep/requirements.txt"
else
  echo "   reportlab ✓"
fi

if ! command -v tesseract &> /dev/null; then
  echo "   ℹ️  tesseract ausente (opcional — só para livros em PDF escaneado)"
fi
echo ""

mkdir -p "$CLAUDE_DIR/skills"

for s in "${SKILLS[@]}"; do
  origem="$SKILLS_DIR/$s"
  destino="$CLAUDE_DIR/skills/$s"
  ver=$(grep -m1 '^version:' "$origem/SKILL.md" 2>/dev/null | sed 's/version: *//' || echo "?")

  echo "📋 $s (v$ver)"
  rm -rf "$destino"
  mkdir -p "$destino"

  cp "$origem/SKILL.md" "$destino/"
  [[ -f "$origem/README.md" ]] && cp "$origem/README.md" "$destino/"
  [[ -f "$origem/CHANGELOG.md" ]] && cp "$origem/CHANGELOG.md" "$destino/"
  [[ -f "$origem/requirements.txt" ]] && cp "$origem/requirements.txt" "$destino/"
  [[ -d "$origem/assets" ]] && cp -r "$origem/assets" "$destino/"
  [[ -d "$origem/scripts" ]] && cp -r "$origem/scripts" "$destino/"
  [[ -d "$origem/examples" ]] && cp -r "$origem/examples" "$destino/"

  # Subagents (a concurso-prep tem 5) vão para o diretório de agents do Claude Code
  if [[ -d "$origem/agents" ]]; then
    mkdir -p "$CLAUDE_DIR/agents"
    cp "$origem/agents"/*.md "$CLAUDE_DIR/agents/" 2>/dev/null || true
    n_agents=$(ls -1 "$origem/agents"/*.md 2>/dev/null | wc -l | tr -d ' ')
    echo "   ↳ $n_agents subagent(s) instalado(s) em $CLAUDE_DIR/agents/"
  fi

  chmod +x "$destino/scripts/"*.py 2>/dev/null || true
  chmod +x "$destino/scripts/tests/"*.py 2>/dev/null || true

  # Smoke test da skill recém-instalada
  if [[ -f "$destino/scripts/tests/test_smoke.py" ]]; then
    if python3 "$destino/scripts/tests/test_smoke.py" > /dev/null 2>&1; then
      echo "   ↳ smoke tests ✓"
    else
      echo "   ↳ ⚠️  smoke tests falharam — verifique o Python e a cópia dos arquivos"
    fi
  fi

  # Limpar caches gerados pelos testes
  find "$destino" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  echo ""
done

echo "✅ Instalação concluída em $CLAUDE_DIR/skills/"
echo ""
echo "⚠️  Reinicie a sessão do Claude Code para carregar as versões novas."
echo "   (As skills são lidas no início da sessão; uma sessão aberta pode manter cache.)"
echo ""
echo "Skills instaladas: ${SKILLS[*]}"
