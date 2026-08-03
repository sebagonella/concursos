#!/usr/bin/env bash
# deploy.sh - Publica o site de estudo no servidor (concursos.casa:8099).
#
# Roda na SUA máquina (onde está o vault). Faz:
#   1. reconstrói TODOS os concursos presentes no build, a partir do vault
#   2. sincroniza os arquivos para o servidor via rsync sobre SSH
#   3. (opcional) sobe/reinicia o container, se ainda não estiver rodando
#
# Deploy é só sincronização de arquivos: o container usa bind mount, então
# NÃO há rebuild de imagem nem restart a cada atualização. O nginx passa a
# servir o conteúdo novo imediatamente.
#
# Por que reconstrói todos: o envio é `rsync --delete` do build INTEIRO, mas o
# `--concurso-dir` nomeia um só. Construir apenas ele republicava os demais com
# o conteúdo da sessão em que foram gerados — sem erro nenhum na saída. Cada
# concurso do build guarda no seu `.concurso.json` a pasta de origem no vault,
# que é o que torna a reconstrução possível.
#
# Uso:
#   ./deploy.sh --concurso-dir "~/vault/30_AREAS/CARREIRA/CONCURSOS/SEDES_2026"
#   ./deploy.sh --concurso-dir <...> --dry-run      # mostra o que mudaria
#   ./deploy.sh --concurso-dir <...> --so-build     # gera local, não envia
#   ./deploy.sh --concurso-dir <...> --so-este      # constrói SÓ este (avisa)
#   ./deploy.sh --setup                             # 1ª vez: sobe o container
#
# Configuração: precedência ambiente > deploy.env > padrões deste arquivo.

set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$AQUI/.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/concurso-publica"

# --- Configuração ------------------------------------------------------------
# Precedência: ambiente > deploy.env > padrões abaixo.
#
# O `deploy.env` era lido com `source` DEPOIS dos padrões, então
# `CONCURSOS_HOST=x ./deploy.sh` era silenciosamente ignorado sempre que a mesma
# chave estivesse no arquivo — o contrário do que o cabeçalho promete, e sem
# nenhum sinal de que a variável fora descartada. Lendo CHAVE=VALOR e definindo
# só o que ainda não veio do ambiente, a promessa passa a valer; de quebra, o
# arquivo de configuração deixa de poder executar shell.
if [[ -f "${DEPLOY_ENV:-$AQUI/deploy.env}" ]]; then
  while IFS= read -r linha || [[ -n "$linha" ]]; do
    linha="${linha%%#*}"
    linha="${linha#"${linha%%[![:space:]]*}"}"
    [[ "$linha" == *=* ]] || continue
    chave="${linha%%=*}"
    chave="${chave%"${chave##*[![:space:]]}"}"
    [[ "$chave" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ -z "${!chave-}" ]]; then
      valor="${linha#*=}"
      valor="${valor#"${valor%%[![:space:]]*}"}"
      valor="${valor%"${valor##*[![:space:]]}"}"
      if [[ ${#valor} -ge 2 && ( "$valor" == \"*\" || "$valor" == \'*\' ) ]]; then
        valor="${valor:1:${#valor}-2}"
      fi
      printf -v "$chave" '%s' "$valor"
    fi
  done < "${DEPLOY_ENV:-$AQUI/deploy.env}"
fi

# CONCURSOS_* são os nomes atuais; BEELINK_* continuam aceitos por compatibilidade
# com instalações antigas (o servidor mudou de beelink.casa para concursos.casa).
CONCURSOS_HOST="${CONCURSOS_HOST:-${BEELINK_HOST:-concursos.casa}}"
CONCURSOS_USER="${CONCURSOS_USER:-${BEELINK_USER:-${USER:-${LOGNAME:-$(id -un 2>/dev/null || echo root)}}}}"
CONCURSOS_DIR="${CONCURSOS_DIR:-${BEELINK_DIR:-/opt/concursos}}"   # onde vive o compose no servidor
CONCURSOS_PORTA="${CONCURSOS_PORTA:-8099}"                          # porta publicada no host
BUILD_DIR="${BUILD_DIR:-$REPO_ROOT/out/site}"        # saída local do gerador

CONCURSO_DIR=""
DRY_RUN=0
SO_BUILD=0
SO_ESTE=0
SETUP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --concurso-dir) CONCURSO_DIR="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --so-build) SO_BUILD=1; shift ;;
    --so-este) SO_ESTE=1; shift ;;
    --setup) SETUP=1; shift ;;
    # o bloco de ajuda é o cabeçalho até a primeira linha que não é comentário,
    # para não quebrar toda vez que o cabeçalho crescer
    --help|-h) awk 'NR>1 && /^#/{sub(/^# ?/,""); print; next} NR>1{exit}' "${BASH_SOURCE[0]}"; exit 0 ;;
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

  # Placeholder enquanto não houver conteúdo. Sem ele, quem abre o navegador entre o
  # --setup e o primeiro deploy leva um "403 Forbidden" cru do nginx: `site/` está
  # vazio, não há index.html e o autoindex é desligado. O 403 não diz nada sobre o
  # que fazer, e parece container quebrado quando o container está perfeito.
  # O `rsync --delete` do deploy remove este arquivo sozinho — ele não existe na
  # origem, e o gerador escreve seu próprio index.html na raiz.
  ssh "$alvo" "cat > '$CONCURSOS_DIR/site/index.html'" <<'PLACEHOLDER'
<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Site ainda não publicado</title>
<style>
  body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
       background:#EDEDE8;color:#23262E;line-height:1.65;margin:0;
       display:grid;place-items:center;min-height:100vh;padding:1.5rem}
  main{background:#F7F7F4;border:1px solid #DFDFD8;border-radius:3px;
       padding:2rem 2.25rem;max-width:34rem}
  h1{font-family:Palatino,Georgia,serif;font-size:1.6rem;margin:0 0 .5rem}
  code{background:#E8ECF8;padding:.15em .4em;border-radius:2px;font-size:.9em}
  pre{background:#101425;color:#E7ECFA;padding:1rem;border-radius:3px;
      overflow-x:auto;font-size:.82rem}
  p{margin:0 0 1rem}
  @media (prefers-color-scheme: dark){
    body{background:#14161C;color:#E4E7EE}
    main{background:#1B1E26;border-color:#2E323D}
    code{background:#232838}
  }
</style></head><body><main>
<h1>Site ainda não publicado</h1>
<p>O container está no ar — este arquivo é a prova. Só falta o conteúdo:
o <code>--setup</code> cria a pasta vazia, e o material vem do deploy.</p>
<pre>./deploy/deploy.sh --concurso-dir &lt;vault&gt;/30_AREAS/CARREIRA/CONCURSOS/SEDES_2026</pre>
<p>Rode na máquina que tem o vault. Esta página desaparece no primeiro deploy.</p>
</main></body></html>
PLACEHOLDER
  # o compose lê este .env sozinho; é o que faz CONCURSOS_PORTA valer de fato
  ssh "$alvo" "printf 'CONCURSOS_PORTA=%s\n' '$CONCURSOS_PORTA' > '$CONCURSOS_DIR/.env'"
  echo "🐳 Subindo o container na porta $CONCURSOS_PORTA..."
  ssh "$alvo" "cd '$CONCURSOS_DIR' && docker compose up -d"
  echo ""
  ssh "$alvo" "cd '$CONCURSOS_DIR' && docker compose ps"
  echo ""
  echo "✅ Container no ar em http://$CONCURSOS_HOST:$CONCURSOS_PORTA/"
  echo "   Teste:  curl -I http://$CONCURSOS_HOST:$CONCURSOS_PORTA/healthz"
  echo ""
  echo "👉 Falta publicar o conteúdo — o setup criou a pasta vazia:"
  echo "     ./deploy/deploy.sh --concurso-dir <vault>/30_AREAS/CARREIRA/CONCURSOS/SEDES_2026"
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

# path absoluto: a origem vai gravada no manifesto e será relida noutro momento,
# possivelmente de outro diretório de trabalho
CONCURSO_DIR="$(cd "$CONCURSO_DIR" && pwd)"
CONCURSO_NOME="$(basename "$CONCURSO_DIR")"
CONCURSOS_PAI="$(dirname "$CONCURSO_DIR")"
echo "📚 Concurso: $CONCURSO_NOME"

if ! command -v python3 &> /dev/null; then
  echo "❌ python3 não encontrado."; exit 1
fi

mkdir -p "$BUILD_DIR"

if [[ ! -f "$SKILL_DIR/scripts/site_builder.py" ]]; then
  echo "❌ site_builder.py não encontrado em $SKILL_DIR/scripts/."
  echo "   O repositório parece incompleto — confira a instalação das skills."
  exit 1
fi

# ---------------------------------------------------------------------------
# Plano de builds
#
# O envio é `rsync --delete` do BUILD INTEIRO, então tudo que está em
# $BUILD_DIR vai para o servidor — inclusive concurso construído semanas atrás.
# Aqui se descobre o que existe no build e de onde cada um veio, para
# reconstruir todos antes de enviar.
# ---------------------------------------------------------------------------
NOMES=("$CONCURSO_NOME")          # o alvo primeiro: falha rápido no que se veio fazer
ORIGENS=("$CONCURSO_DIR")
DEDUZIDAS=("")
DATAS=("")                         # data do build anterior, para o aviso do --so-este
ORFAOS=()                          # "nome<TAB>data do build" — republicados como estão

while IFS=$'\t' read -r m_nome m_origem m_data; do
  [[ -n "$m_nome" ]] || continue
  [[ "$m_nome" == "$CONCURSO_NOME" ]] && continue

  origem="$m_origem"
  deduzida=""
  if [[ -z "$origem" || ! -d "$origem" ]]; then
    # Manifesto antigo (gerado antes de o campo existir) ou pasta que mudou de
    # lugar. Os concursos moram todos lado a lado, então a irmã é um palpite
    # bom — mas palpite ECOADO, nunca silencioso: é a mesma razão pela qual o
    # repo ecoa slug derivado sempre, e não só quando parece suspeito.
    if [[ -d "$CONCURSOS_PAI/$m_nome" ]]; then
      origem="$CONCURSOS_PAI/$m_nome"
      deduzida="sim"
    else
      origem=""
    fi
  fi

  if [[ -n "$origem" ]]; then
    NOMES+=("$m_nome"); ORIGENS+=("$origem"); DEDUZIDAS+=("$deduzida")
    DATAS+=("${m_data:-?}")
  else
    ORFAOS+=("$m_nome"$'\t'"${m_data:-?}")
  fi
done < <(python3 - "$BUILD_DIR" <<'PY'
import json, sys
from pathlib import Path

for man in sorted(Path(sys.argv[1]).glob("*/.concurso.json")):
    try:
        d = json.loads(man.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        continue
    print("\t".join(str(d.get(c) or "") for c in ("concurso", "origem", "gerado_em")))
PY
)

# O aviso dos órfãos é montado uma vez e impresso DUAS: aqui e no bloco final.
# Órfão não bloqueia o deploy (é republicado como está), e aviso que aparece só
# no meio de uma saída longa é aviso que não se lê.
AVISO_ORFAOS=""
if [[ ${#ORFAOS[@]} -gt 0 ]]; then
  AVISO_ORFAOS="⚠️  ${#ORFAOS[@]} concurso(s) do build não puderam ser reconstruídos e vão"$'\n'
  AVISO_ORFAOS+="   para o servidor COMO ESTÃO — a pasta de origem no vault não foi encontrada:"$'\n'
  for o in "${ORFAOS[@]}"; do
    IFS=$'\t' read -r o_nome o_data <<< "$o"
    AVISO_ORFAOS+="     • $o_nome — build de $o_data"$'\n'
  done
  AVISO_ORFAOS+="   Procurei em $CONCURSOS_PAI/<nome>. Se a pasta foi renomeada, publique-a"$'\n'
  AVISO_ORFAOS+="   com --concurso-dir para o build voltar a acompanhar o vault."
  echo ""
  echo "$AVISO_ORFAOS"
fi

if [[ $SO_ESTE -eq 1 && ${#NOMES[@]} -gt 1 ]]; then
  echo ""
  echo "⚠️  --so-este: construindo apenas $CONCURSO_NOME. Os demais serão enviados"
  echo "   com o conteúdo que já está no build:"
  for i in "${!NOMES[@]}"; do
    [[ $i -eq 0 ]] && continue
    echo "     • ${NOMES[$i]} — build de ${DATAS[$i]}"
  done
  NOMES=("${NOMES[0]}"); ORIGENS=("${ORIGENS[0]}"); DEDUZIDAS=("${DEDUZIDAS[0]}")
fi

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
echo ""
if [[ ${#NOMES[@]} -gt 1 ]]; then
  echo "🏗️  Gerando o site — ${#NOMES[@]} concursos no build:"
else
  echo "🏗️  Gerando o site..."
fi

for i in "${!NOMES[@]}"; do
  nome="${NOMES[$i]}"
  origem="${ORIGENS[$i]}"
  rotulo="   [$((i + 1))/${#NOMES[@]}] $nome"
  [[ -n "${DEDUZIDAS[$i]}" ]] && rotulo+=" (origem deduzida da pasta irmã: $origem)"
  echo "$rotulo"

  # stdout capturado (é o JSON do gerador); stderr segue para o terminal, porque
  # é por ali que saem os avisos de rótulo fora do template — que não podem se
  # perder em silêncio
  if ! saida="$(python3 "$SKILL_DIR/scripts/site_builder.py" \
        --concurso-dir "$origem" --out "$BUILD_DIR")"; then
    echo "❌ Falhou ao construir $nome (origem: $origem)." >&2
    exit 1
  fi
  paginas="$(printf '%s' "$saida" | grep -o '"paginas": *[0-9]*' | grep -o '[0-9]*' || true)"
  echo "         ✓ ${paginas:-?} páginas"
done

TAM="$(du -sh "$BUILD_DIR" 2>/dev/null | cut -f1)"
echo "   ✓ site em $BUILD_DIR ($TAM)"

if [[ $SO_BUILD -eq 1 ]]; then
  echo "✅ Build local concluído (--so-build: nada foi enviado)."
  [[ -n "$AVISO_ORFAOS" ]] && { echo ""; echo "$AVISO_ORFAOS"; }
  exit 0
fi

# ---------------------------------------------------------------------------
# Deploy (rsync)
# ---------------------------------------------------------------------------
if ! command -v rsync &> /dev/null; then
  echo "❌ rsync não encontrado. Instale: sudo apt install rsync"
  exit 1
fi

# --chmod normaliza a permissao NO DESTINO. Sem ele, o `-a` preserva a permissao
# da origem, e arquivo que esta 0600 no vault chega 0600 no servidor — o nginx do
# container roda com outro usuario e devolve 403. Aconteceu de verdade: um podcast
# de 41 MB do SEDES ficou inacessivel no site enquanto as outras 85 midias abriam,
# porque so aquele arquivo estava 0600 na origem.
# O site e artefato DERIVADO: a permissao dele nao deve depender de como o arquivo
# acabou salvo no vault.
RSYNC_OPTS=(-az --delete --chmod=D755,F644 --human-readable --info=stats1)
[[ $DRY_RUN -eq 1 ]] && RSYNC_OPTS+=(--dry-run --itemize-changes)

echo "🚀 Enviando para $alvo:$CONCURSOS_DIR/site/ ..."
# a barra final em "$BUILD_DIR/" é essencial: envia o CONTEÚDO, não a pasta
rsync "${RSYNC_OPTS[@]}" "$BUILD_DIR/" "$alvo:$CONCURSOS_DIR/site/"

if [[ $DRY_RUN -eq 1 ]]; then
  echo ""
  echo "✅ Dry-run concluído — nada foi alterado no servidor."
  [[ -n "$AVISO_ORFAOS" ]] && { echo ""; echo "$AVISO_ORFAOS"; }
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
echo "✅ Deploy concluído — ${#NOMES[@]} concurso(s) reconstruído(s) e publicado(s):"
for nome in "${NOMES[@]}"; do
  echo "     • $nome"
done
echo "   http://$CONCURSOS_HOST:$CONCURSOS_PORTA/"

# repetido de propósito: no meio de uma saída longa, o aviso do começo já rolou
# para fora da tela quando o deploy termina
[[ -n "$AVISO_ORFAOS" ]] && { echo ""; echo "$AVISO_ORFAOS"; }
exit 0
