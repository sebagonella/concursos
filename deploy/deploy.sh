#!/usr/bin/env bash
# deploy.sh - Publica o site de estudo no servidor (concursos.casa:8099).
#
# Roda na SUA máquina (onde está o vault). Faz:
#   1. gera o site a partir da pasta do concurso no vault
#   2. sincroniza os arquivos para o servidor via rsync sobre SSH
#   3. (opcional) sobe/reinicia o container, se ainda não estiver rodando
#
# Deploy é só sincronização de arquivos: o container usa bind mount, então
# NÃO há rebuild de imagem nem restart a cada atualização. O nginx passa a
# servir o conteúdo novo imediatamente.
#
# Uso:
#   ./deploy.sh --concurso-dir "~/vault/30_AREAS/CARREIRA/CONCURSOS/SEDES_2026"
#   ./deploy.sh --concurso-dir <...> --dry-run      # mostra o que mudaria
#   ./deploy.sh --concurso-dir <...> --so-build     # gera local, não envia
#   ./deploy.sh --setup                             # 1ª vez: sobe o container
#
# Configuração: edite as variáveis abaixo ou defina via ambiente/deploy.env

set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$AQUI/.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/concurso-publica"

# --- Configuração (sobrescreva em deploy.env ou por variável de ambiente) ---
# CONCURSOS_* são os nomes atuais; BEELINK_* continuam aceitos por compatibilidade
# com instalações antigas (o servidor mudou de beelink.casa para concursos.casa).
CONCURSOS_HOST="${CONCURSOS_HOST:-${BEELINK_HOST:-concursos.casa}}"
CONCURSOS_USER="${CONCURSOS_USER:-${BEELINK_USER:-${USER:-${LOGNAME:-$(id -un 2>/dev/null || echo root)}}}}"
CONCURSOS_DIR="${CONCURSOS_DIR:-${BEELINK_DIR:-/opt/concursos}}"   # onde vive o compose no servidor
CONCURSOS_PORTA="${CONCURSOS_PORTA:-8099}"                          # porta publicada no host
BUILD_DIR="${BUILD_DIR:-$REPO_ROOT/out/site}"        # saída local do gerador

[[ -f "$AQUI/deploy.env" ]] && source "$AQUI/deploy.env"

CONCURSO_DIR=""
DRY_RUN=0
SO_BUILD=0
SETUP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --concurso-dir) CONCURSO_DIR="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --so-build) SO_BUILD=1; shift ;;
    --setup) SETUP=1; shift ;;
    --help|-h) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opção desconhecida: $1"; exit 1 ;;
  esac
done

alvo="$CONCURSOS_USER@$CONCURSOS_HOST"

# ---------------------------------------------------------------------------
# --setup: primeira instalação no servidor (copia compose+nginx.conf e sobe)
# ---------------------------------------------------------------------------
if [[ $SETUP -eq 1 ]]; then
  echo "🔧 Preparando o servidor ($alvo:$CONCURSOS_DIR)..."

  # A porta é conferida ANTES de subir o container: o `docker compose up` falha com
  # "address already in use", mensagem que não diz quem está ocupando nem o que
  # fazer. Descobrir isso depois custa uma ida ao servidor.
  ocupada=$(ssh "$alvo" "(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) \
    | grep -E '[:.]${CONCURSOS_PORTA}[[:space:]]' || true")
  if [[ -n "$ocupada" ]]; then
    echo "❌ A porta $CONCURSOS_PORTA já está em uso em $CONCURSOS_HOST:" >&2
    echo "$ocupada" | sed 's/^/     /' >&2
    echo "" >&2
    echo "   Escolha outra porta e rode de novo:" >&2
    echo "     CONCURSOS_PORTA=8100 ./deploy/deploy.sh --setup" >&2
    echo "   (ou fixe em deploy/deploy.env). O mapeamento do docker-compose.yml" >&2
    echo "   acompanha a variável; a porta interna do nginx (80) não muda." >&2
    exit 1
  fi

  ssh "$alvo" "mkdir -p '$CONCURSOS_DIR/site'"
  scp "$AQUI/docker-compose.yml" "$AQUI/nginx.conf" "$alvo:$CONCURSOS_DIR/"
  # o compose lê este .env sozinho; é o que faz CONCURSOS_PORTA valer de fato
  ssh "$alvo" "printf 'CONCURSOS_PORTA=%s\n' '$CONCURSOS_PORTA' > '$CONCURSOS_DIR/.env'"
  echo "🐳 Subindo o container na porta $CONCURSOS_PORTA..."
  ssh "$alvo" "cd '$CONCURSOS_DIR' && docker compose up -d"
  echo ""
  ssh "$alvo" "cd '$CONCURSOS_DIR' && docker compose ps"
  echo ""
  echo "✅ Container no ar."
  echo "   Teste:  curl -I http://$CONCURSOS_HOST:$CONCURSOS_PORTA/healthz"
  echo "   Site:   http://$CONCURSOS_HOST:$CONCURSOS_PORTA/"
  echo ""
  echo "   Se ainda não resolver o nome, aponte concursos.casa para o IP do"
  echo "   servidor no seu DNS local (ou no /etc/hosts das máquinas da casa)."
  exit 0
fi

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
if [[ -z "$CONCURSO_DIR" ]]; then
  echo "❌ Faltou --concurso-dir (a pasta do concurso no vault)."
  echo "   Ex: ./deploy.sh --concurso-dir ~/vault/30_AREAS/CARREIRA/CONCURSOS/SEDES_2026"
  exit 1
fi

CONCURSO_DIR="${CONCURSO_DIR/#\~/$HOME}"
if [[ ! -d "$CONCURSO_DIR" ]]; then
  echo "❌ Pasta do concurso não encontrada: $CONCURSO_DIR"
  exit 1
fi

CONCURSO_NOME="$(basename "$CONCURSO_DIR")"
echo "📚 Concurso: $CONCURSO_NOME"

if ! command -v python3 &> /dev/null; then
  echo "❌ python3 não encontrado."; exit 1
fi

echo "🏗️  Gerando o site..."
mkdir -p "$BUILD_DIR"

if [[ ! -f "$SKILL_DIR/scripts/site_builder.py" ]]; then
  echo "❌ site_builder.py não encontrado em $SKILL_DIR/scripts/."
  echo "   O repositório parece incompleto — confira a instalação das skills."
  exit 1
fi

python3 "$SKILL_DIR/scripts/site_builder.py" \
  --concurso-dir "$CONCURSO_DIR" --out "$BUILD_DIR"

TAM="$(du -sh "$BUILD_DIR" 2>/dev/null | cut -f1)"
echo "   ✓ site em $BUILD_DIR ($TAM)"

if [[ $SO_BUILD -eq 1 ]]; then
  echo "✅ Build local concluído (--so-build: nada foi enviado)."
  exit 0
fi

# ---------------------------------------------------------------------------
# Deploy (rsync)
# ---------------------------------------------------------------------------
if ! command -v rsync &> /dev/null; then
  echo "❌ rsync não encontrado. Instale: sudo apt install rsync"
  exit 1
fi

RSYNC_OPTS=(-az --delete --human-readable --info=stats1)
[[ $DRY_RUN -eq 1 ]] && RSYNC_OPTS+=(--dry-run --itemize-changes)

echo "🚀 Enviando para $alvo:$CONCURSOS_DIR/site/ ..."
# a barra final em "$BUILD_DIR/" é essencial: envia o CONTEÚDO, não a pasta
rsync "${RSYNC_OPTS[@]}" "$BUILD_DIR/" "$alvo:$CONCURSOS_DIR/site/"

if [[ $DRY_RUN -eq 1 ]]; then
  echo ""
  echo "✅ Dry-run concluído — nada foi alterado no servidor."
  exit 0
fi

# Container roda? (bind mount: não precisa restart, mas avisa se estiver parado)
if ssh "$alvo" "cd '$CONCURSOS_DIR' && docker compose ps --status running -q" | grep -q .; then
  echo "   ✓ container rodando — conteúdo novo já está sendo servido"
else
  echo "   ⚠️  container parado. Subindo..."
  ssh "$alvo" "cd '$CONCURSOS_DIR' && docker compose up -d"
fi

echo ""
echo "✅ Deploy concluído."
echo "   http://$CONCURSOS_HOST:$CONCURSOS_PORTA/"
