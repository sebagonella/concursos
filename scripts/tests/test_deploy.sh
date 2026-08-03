#!/usr/bin/env bash
# test_deploy.sh - Testes do deploy. Roda standalone:
#     bash scripts/tests/test_deploy.sh
#
# Existe porque o `deploy.sh` publicava conteúdo velho sem avisar: ele CONSTRÓI
# só o concurso de `--concurso-dir`, mas ENVIA o `out/site/` inteiro com
# `rsync --delete` — e esse diretório acumula. Publicando o SEDES_2026, o
# BB_2027_PREVISTO foi para o servidor com um build de véspera, sem erro nenhum
# na saída. Falha silenciosa, a classe que este repositório trata como a pior.
#
# Nada aqui toca a rede: `ssh`, `scp`, `rsync` e `docker` são substituídos por
# stubs no início do PATH, que registram o argv num log. O vault de teste sai da
# fixture da `concurso-publica` — a mesma que a suíte dela usa, para o deploy não
# testar contra um concurso que o gerador nunca produz.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY="$REPO_ROOT/deploy/deploy.sh"
FIXTURE="$REPO_ROOT/skills/concurso-publica/scripts/tests"
FALHAS=0
PASSES=0

ok()   { echo "  PASS  $1"; PASSES=$((PASSES + 1)); }
fail() { echo "  FAIL  $1: $2"; FALHAS=$((FALHAS + 1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- stubs ------------------------------------------------------------------
# Cada um grava a linha de comando no seu log e sai com STUB_RC. O `ssh` também
# imprime STUB_SSH_SAIDA, que é como se simula "porta ocupada" e "container
# rodando" sem servidor nenhum.
mkdir -p "$TMP/bin" "$TMP/log"
for prog in ssh scp rsync docker; do
  cat > "$TMP/bin/$prog" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "\$STUB_LOG/$prog.log"
printf '%s\n' "$prog \$*" >> "\$STUB_LOG/ordem.log"
[[ "$prog" == "ssh" ]] && printf '%s' "\${STUB_SSH_SAIDA:-}"
exit \${STUB_RC:-0}
STUB
  chmod +x "$TMP/bin/$prog"
done
export STUB_LOG="$TMP/log"
export PATH="$TMP/bin:$PATH"

# --- vault de teste ---------------------------------------------------------
VAULT="$TMP/vault/CONCURSOS"
mkdir -p "$VAULT"
if ! python3 - "$FIXTURE" "$VAULT" <<'PY' > "$TMP/fixture.log" 2>&1
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from fixture_concurso import montar_concurso
for nome in ("ALFA_2026", "BETA_2027_PREVISTO"):
    montar_concurso(Path(sys.argv[2]) / nome)
PY
then
  echo "  FAIL  montar_vault_de_teste: veja $TMP/fixture.log"
  cat "$TMP/fixture.log"
  exit 1
fi
ALFA="$VAULT/ALFA_2026"
BETA="$VAULT/BETA_2027_PREVISTO"

# --- helpers ----------------------------------------------------------------
# O deploy roda sempre com destino falso e build próprio. `DEPLOY_ENV=/dev/null`
# neutraliza o deploy.env real da máquina de quem roda os testes.
BUILD="$TMP/out"
rodar_deploy() {
  rm -f "$STUB_LOG"/*.log
  env DEPLOY_ENV=/dev/null \
      CONCURSOS_HOST="host-de-teste" CONCURSOS_USER="u" \
      CONCURSOS_DIR="/destino" CONCURSOS_PORTA="9999" \
      BUILD_DIR="$BUILD" \
      bash "$DEPLOY" "$@" > "$TMP/saida.log" 2>&1
}
# Lê um campo do manifesto. Falha alto: um helper que devolve "" quando não
# consegue ler faz o teste passar por acidente — foi o que aconteceu aqui
# enquanto ele engolia o próprio IndexError em 2>/dev/null.
manifesto() { # $1 = slug ; $2 = campo
  python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or "")' \
    "$BUILD/$1/.concurso.json" "$2"
}
log_de()   { cat "$STUB_LOG/$1.log" 2>/dev/null; }
chamou()   { [[ -s "$STUB_LOG/$1.log" ]]; }

# ===========================================================================
# O DEFEITO: reconstruir todos os concursos do build antes de enviar
# ===========================================================================
rodar_deploy --concurso-dir "$ALFA" --so-build
rodar_deploy --concurso-dir "$BETA" --so-build     # agora o build tem os dois

# Envelhece o manifesto do BETA, como se tivesse sido construído noutro dia.
python3 - "$BUILD/beta_2027_previsto/.concurso.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["gerado_em"] = "2020-01-01T00:00:00"
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False)
PY

rodar_deploy --concurso-dir "$ALFA"
beta_depois="$(manifesto beta_2027_previsto gerado_em)"
if [[ -n "$beta_depois" && "$beta_depois" != "2020-01-01T00:00:00" ]]; then
  ok "reconstroi_todos_os_concursos_do_build"
else
  fail "reconstroi_todos_os_concursos_do_build" \
       "o BETA foi enviado com o build velho — o defeito original"
fi

n_rsync=$(log_de rsync | grep -c . || true)
if [[ "$n_rsync" -eq 1 ]]; then
  ok "rsync_roda_uma_vez_so"
else
  fail "rsync_roda_uma_vez_so" "rsync chamado $n_rsync vez(es)"
fi

# o envio tem de ser a ÚLTIMA coisa: enviar no meio publicaria build parcial
if [[ "$(grep -c . "$STUB_LOG/ordem.log")" -gt 0 ]] \
   && grep -q '^rsync' <<< "$(grep -m1 rsync "$STUB_LOG/ordem.log")"; then
  primeira_rsync=$(grep -n '^rsync' "$STUB_LOG/ordem.log" | head -1 | cut -d: -f1)
  ultima_ssh=$(grep -n '^ssh' "$STUB_LOG/ordem.log" | tail -1 | cut -d: -f1 || echo 0)
  if [[ "$primeira_rsync" -lt "${ultima_ssh:-999}" || "${ultima_ssh:-0}" -eq 0 ]]; then
    ok "rsync_vem_depois_dos_builds"
  else
    fail "rsync_vem_depois_dos_builds" "ordem inesperada em ordem.log"
  fi
fi

if log_de rsync | grep -q -- "--delete" && log_de rsync | grep -q "u@host-de-teste:/destino/site/"; then
  ok "rsync_leva_delete_e_o_destino_certo"
else
  fail "rsync_leva_delete_e_o_destino_certo" "$(log_de rsync)"
fi

if grep -q "ALFA_2026" "$TMP/saida.log" && grep -q "BETA_2027_PREVISTO" "$TMP/saida.log"; then
  ok "resumo_final_nomeia_os_concursos_publicados"
else
  fail "resumo_final_nomeia_os_concursos_publicados" "$(tail -5 "$TMP/saida.log")"
fi

# ===========================================================================
# --so-este: o escape hatch não pode ser silencioso
# ===========================================================================
rodar_deploy --concurso-dir "$ALFA" --so-este
if grep -q -- "--so-este" "$TMP/saida.log" \
   && grep -q "BETA_2027_PREVISTO" "$TMP/saida.log" \
   && chamou rsync; then
  ok "so_este_avisa_nomeando_os_que_vao_como_estao"
else
  fail "so_este_avisa_nomeando_os_que_vao_como_estao" "$(cat "$TMP/saida.log")"
fi

# ===========================================================================
# origem: campo ausente (manifesto legado) → dedução pela pasta irmã, ECOADA
# ===========================================================================
python3 - "$BUILD/beta_2027_previsto/.concurso.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d.pop("origem", None)
d["gerado_em"] = "2020-01-01T00:00:00"
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False)
PY
rodar_deploy --concurso-dir "$ALFA" --so-build
if grep -q "origem deduzida da pasta irmã" "$TMP/saida.log" \
   && grep -q "$BETA" "$TMP/saida.log"; then
  ok "origem_deduzida_de_manifesto_legado_e_ecoada"
else
  fail "origem_deduzida_de_manifesto_legado_e_ecoada" "$(cat "$TMP/saida.log")"
fi
beta_depois="$(manifesto beta_2027_previsto gerado_em)"
if [[ -n "$beta_depois" && "$beta_depois" != "2020-01-01T00:00:00" ]]; then
  ok "manifesto_legado_e_reconstruido_apos_a_deducao"
else
  fail "manifesto_legado_e_reconstruido_apos_a_deducao" "seguiu com a data velha"
fi
if [[ "$(manifesto beta_2027_previsto origem)" == "$BETA" ]]; then
  ok "reconstrucao_grava_a_origem_no_manifesto"
else
  fail "reconstrucao_grava_a_origem_no_manifesto" "origem=$(manifesto beta_2027_previsto origem)"
fi

# ===========================================================================
# órfão: origem sumiu e não há irmã → avisa DUAS vezes e não bloqueia
# ===========================================================================
GAMA_BUILD="$BUILD/gama_2028"
mkdir -p "$GAMA_BUILD"
cat > "$GAMA_BUILD/.concurso.json" <<JSON
{"concurso": "GAMA_2028", "slug": "gama_2028",
 "origem": "$TMP/vault/CONCURSOS-QUE-SUMIU/GAMA_2028",
 "gerado_em": "2019-05-05T00:00:00"}
JSON
rodar_deploy --concurso-dir "$ALFA"
rc=$?
n_avisos=$(grep -c "não puderam ser reconstruídos" "$TMP/saida.log" || true)
if [[ "$rc" -eq 0 ]] && chamou rsync; then
  ok "orfao_nao_bloqueia_o_deploy"
else
  fail "orfao_nao_bloqueia_o_deploy" "rc=$rc, rsync=$(chamou rsync && echo sim || echo nao)"
fi
if [[ "$n_avisos" -eq 2 ]]; then
  ok "orfao_avisa_duas_vezes"
else
  fail "orfao_avisa_duas_vezes" "aviso apareceu $n_avisos vez(es), esperado 2"
fi
if grep -q "GAMA_2028" "$TMP/saida.log" && grep -q "2019-05-05" "$TMP/saida.log"; then
  ok "aviso_de_orfao_nomeia_o_concurso_e_a_data"
else
  fail "aviso_de_orfao_nomeia_o_concurso_e_a_data" "$(cat "$TMP/saida.log")"
fi
rm -rf "$GAMA_BUILD"

# ===========================================================================
# flags
# ===========================================================================
alfa_antes="$(manifesto alfa_2026 gerado_em)"
sleep 1                     # o carimbo do manifesto tem resolução de segundo
rodar_deploy --concurso-dir "$ALFA" --dry-run
if log_de rsync | grep -q -- "--dry-run" && ! log_de docker | grep -q "up -d"; then
  ok "dry_run_envia_com_dry_run_e_nao_sobe_container"
else
  fail "dry_run_envia_com_dry_run_e_nao_sobe_container" "$(log_de rsync)"
fi
if [[ "$(manifesto alfa_2026 gerado_em)" != "$alfa_antes" ]]; then
  ok "dry_run_reconstroi_o_build"
else
  fail "dry_run_reconstroi_o_build" "não reconstruiu — o diff mostrado seria mentira"
fi

rodar_deploy --concurso-dir "$ALFA" --so-build
if ! chamou rsync && ! chamou ssh; then
  ok "so_build_nao_chama_ssh_nem_rsync"
else
  fail "so_build_nao_chama_ssh_nem_rsync" "rsync=$(log_de rsync) ssh=$(log_de ssh)"
fi

rodar_deploy
if [[ $? -ne 0 ]] && grep -q -- "--concurso-dir" "$TMP/saida.log"; then
  ok "sem_concurso_dir_falha_claro"
else
  fail "sem_concurso_dir_falha_claro" "$(cat "$TMP/saida.log")"
fi

rodar_deploy --concurso-dir "$TMP/nao-existe"
if [[ $? -ne 0 ]] && grep -q "não encontrada" "$TMP/saida.log"; then
  ok "concurso_dir_inexistente_falha_claro"
else
  fail "concurso_dir_inexistente_falha_claro" "$(cat "$TMP/saida.log")"
fi

# ===========================================================================
# configuração: ambiente vence o deploy.env
# ===========================================================================
cat > "$TMP/deploy.env" <<'ENV'
# comentário no arquivo de config
CONCURSOS_HOST=host-do-arquivo
CONCURSOS_USER="usuario-do-arquivo"
ENV
rm -f "$STUB_LOG"/*.log
env DEPLOY_ENV="$TMP/deploy.env" \
    CONCURSOS_HOST="host-do-ambiente" CONCURSOS_DIR="/destino" \
    BUILD_DIR="$BUILD" \
    bash "$DEPLOY" --concurso-dir "$ALFA" > "$TMP/saida.log" 2>&1
if log_de rsync | grep -q "host-do-ambiente"; then
  ok "ambiente_vence_o_deploy_env"
else
  fail "ambiente_vence_o_deploy_env" "$(log_de rsync)"
fi
if log_de rsync | grep -q "usuario-do-arquivo@"; then
  ok "deploy_env_vale_quando_o_ambiente_cala"
else
  fail "deploy_env_vale_quando_o_ambiente_cala" "$(log_de rsync)"
fi

# ===========================================================================
# --setup
# ===========================================================================
rm -f "$STUB_LOG"/*.log
env DEPLOY_ENV=/dev/null CONCURSOS_HOST="h" CONCURSOS_USER="u" CONCURSOS_DIR="/destino" \
    CONCURSOS_PORTA="9999" BUILD_DIR="$BUILD" \
    STUB_SSH_SAIDA=$'LISTEN 0 4096 *:9999 users:(("nginx",pid=1))\n' \
    bash "$DEPLOY" --setup > "$TMP/saida.log" 2>&1
rc=$?
if [[ "$rc" -ne 0 ]] && ! chamou scp; then
  ok "setup_aborta_quando_a_porta_esta_ocupada"
else
  fail "setup_aborta_quando_a_porta_esta_ocupada" "rc=$rc, scp=$(log_de scp)"
fi

rm -f "$STUB_LOG"/*.log
env DEPLOY_ENV=/dev/null CONCURSOS_HOST="h" CONCURSOS_USER="u" CONCURSOS_DIR="/destino" \
    CONCURSOS_PORTA="9999" BUILD_DIR="$BUILD" STUB_SSH_SAIDA="" \
    bash "$DEPLOY" --setup > "$TMP/saida.log" 2>&1
if log_de scp | grep -q "docker-compose.yml" && log_de scp | grep -q "nginx.conf"; then
  ok "setup_copia_compose_e_nginx"
else
  fail "setup_copia_compose_e_nginx" "$(log_de scp)"
fi
if log_de ssh | grep -q "docker compose up -d" && log_de ssh | grep -q "CONCURSOS_PORTA=%s"; then
  ok "setup_sobe_o_container_e_grava_a_porta"
else
  fail "setup_sobe_o_container_e_grava_a_porta" "$(log_de ssh)"
fi

echo ""
TOTAL=$((PASSES + FALHAS))
if [[ "$FALHAS" -eq 0 ]]; then
  echo "$PASSES/$TOTAL testes passaram."
else
  echo "$PASSES/$TOTAL testes passaram — $FALHAS falha(s)."
fi
exit $((FALHAS > 0 ? 1 : 0))
