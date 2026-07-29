#!/usr/bin/env python3
"""
fix_notebooklm_packs.py - Atualiza os _fonte-notebooklm.md de um concurso JÁ
aprofundado, aplicando a versão atual do template (extensão .m4a, prompts finos
para os 4 geráveis, seção de links) SEM regenerar resumos, flashcards ou progresso.

Uso típico: você aprofundou uma matéria num concurso antes de ajustes no template
e quer só atualizar os pacotes NotebookLM, mantendo todo o resto intacto.

O que faz:
  - Para cada assunto (subpasta com .md preenchido), regenera _fonte-notebooklm.md.
  - Antes de sobrescrever, faz BACKUP do arquivo antigo como
    _fonte-notebooklm.bak.md (a menos de --no-backup), para você não perder links
    que já tenha preenchido manualmente.
  - NÃO toca em: {assunto}.md, flashcards-*, nem em qualquer .m4a/.mp3/.png já salvo.

Uso:
    python fix_notebooklm_packs.py --assuntos-dir <.../assuntos> \
        --concurso "BB_2027_PREVISTO" --materia "Língua Portuguesa" \
        [--leis-dir <...>] [--no-backup] [--dry-run]

Este script é um WRAPPER fino sobre notebooklm_pack.py: mesma geração, mais backup
e relatório do que mudou. Use-o quando a pasta do concurso JÁ existe.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assuntos-dir", type=Path, required=True)
    ap.add_argument("--concurso", default="")
    ap.add_argument("--materia", default="")
    ap.add_argument("--leis-dir", type=Path, default=None)
    ap.add_argument("--no-backup", action="store_true",
                    help="não criar _fonte-notebooklm.bak.md antes de sobrescrever")
    ap.add_argument("--dry-run", action="store_true",
                    help="apenas listar o que seria atualizado, sem escrever")
    args = ap.parse_args()

    if not args.assuntos_dir.is_dir():
        sys.stderr.write(f"ERRO: não é diretório: {args.assuntos_dir}\n")
        sys.exit(1)

    # inventário do que existe hoje
    alvos = []
    for subdir in sorted(args.assuntos_dir.iterdir()):
        if not subdir.is_dir():
            continue
        assunto_md = subdir / f"{subdir.name}.md"
        pack = subdir / "_fonte-notebooklm.md"
        if assunto_md.exists():
            alvos.append((subdir, pack, pack.exists()))

    if not alvos:
        sys.stderr.write("Nenhum assunto encontrado para atualizar.\n")
        sys.exit(0)

    print(f"Assuntos encontrados: {len(alvos)}")
    for subdir, pack, existe in alvos:
        print(f"  - {subdir.name}: pack {'existe (será atualizado)' if existe else 'novo'}")

    if args.dry_run:
        print("\n[dry-run] Nada foi escrito.")
        sys.exit(0)

    # backup dos packs existentes
    if not args.no_backup:
        n_bak = 0
        for subdir, pack, existe in alvos:
            if existe:
                bak = subdir / "_fonte-notebooklm.bak.md"
                shutil.copy2(pack, bak)
                n_bak += 1
        print(f"\nBackup: {n_bak} arquivo(s) salvos como _fonte-notebooklm.bak.md")

    # delega a geração ao notebooklm_pack.py (fonte única de verdade do formato)
    cmd = [sys.executable, str(AQUI / "notebooklm_pack.py"),
           "--assuntos-dir", str(args.assuntos_dir),
           "--concurso", args.concurso, "--materia", args.materia]
    if args.leis_dir:
        cmd += ["--leis-dir", str(args.leis_dir)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        sys.exit(r.returncode)

    print("\n✅ Pacotes NotebookLM atualizados (resumos, flashcards e progresso intactos).")
    if not args.no_backup:
        print("   Versões antigas preservadas em _fonte-notebooklm.bak.md — apague quando quiser.")
        print("   Se você já tinha links preenchidos no pack antigo, confira o .bak.md para recuperá-los.")


if __name__ == "__main__":
    main()
