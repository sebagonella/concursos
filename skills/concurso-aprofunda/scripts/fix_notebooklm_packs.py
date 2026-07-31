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
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import notebooklm_pack as nlp  # noqa: E402  (a regra de layout mora lá, não aqui)


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

    # Inventário: UM pacote por aprofundamento, no layout que o gerador realmente
    # emite. Antes esta função reimplementava a regra de layout procurando
    # `subdir/{subdir.name}.md` — o formato plano legado. Como o padrão desde a
    # 0.5.0 é `{assunto}/{nivel}--{fonte}/`, o inventário achava ZERO alvos nos 158
    # pacotes do vault e o script saía com sucesso sem escrever nada: migração que
    # não migra e não reclama. Agora a regra vem do próprio gerador.
    alvos = []
    for subdir in sorted(args.assuntos_dir.iterdir()):
        if not subdir.is_dir():
            continue
        for pasta in nlp.pastas_de_aprofundamento(subdir):
            if nlp.arquivo_principal(pasta) is None:
                continue
            pack = pasta / "_fonte-notebooklm.md"
            rotulo = subdir.name if pasta == subdir else f"{subdir.name}/{pasta.name}"
            alvos.append((rotulo, pack, pack.exists()))

    if not alvos:
        sys.stderr.write("Nenhum assunto encontrado para atualizar.\n")
        sys.exit(1)          # falhar alto: sair 0 escondia a migração que não rodou

    print(f"Aprofundamentos encontrados: {len(alvos)}")
    for rotulo, pack, existe in alvos:
        print(f"  - {rotulo}: pack {'existe (será atualizado)' if existe else 'novo'}")

    if args.dry_run:
        print("\n[dry-run] Nada foi escrito.")
        sys.exit(0)

    if args.no_backup:
        print("\n⚠️  --no-backup: o gerador não guardará o pack antigo em .bak.md")

    # O backup é do próprio `notebooklm_pack.py` (só copia quando o conteúdo mudou,
    # ver a regra de preservar trabalho do usuário). Este script já duplicou esse
    # backup, incondicionalmente — o que gerava .bak.md inútil em todo pacote
    # inalterado e ainda era sobrescrito pelo backup do gerador logo em seguida.

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
