#!/usr/bin/env python3
"""
consolidar_mapas_comuns.py — junta em `_COMUM/03-MAPAS-COMUNS/` os mapas de matéria
que estão duplicados dentro de cada cargo.

O problema que resolve: até a 1.4.0 a `concurso-prep` gravava o mapa SEMPRE em
`{CARGO}/03-MAPAS-MATERIAS/`. Num concurso multi-cargo, a mesma matéria comum
era mapeada uma vez por cargo — no BB são 5 matérias × 2 cargos = 10 arquivos
quase idênticos, onde deviam existir 5. Editar um mapa exigia lembrar de editar
o gêmeo, e o `_COMUM/03-MAPAS-COMUNS/` que o site lê nunca era escrito.

Disciplina (a mesma do `migrar_aprofundamentos.py`):
  - **dry-run é o padrão**; só mexe com `--aplicar`
  - **MOVE, não copia**: o conteúdo é do usuário e não se duplica de novo
  - **nunca sobrescreve** destino existente — conflito vira pendência
  - **reescreve os wikilinks** que apontavam para o caminho antigo; sem isso a
    consolidação deixa o vault cheio de link quebrado, que foi exatamente o que
    aconteceu na migração de aprofundamentos
  - divergência de conteúdo entre os gêmeos **não** é resolvida no palpite: vira
    pendência, para o humano escolher qual fica

O que NÃO faz: decidir que uma matéria é comum. Isso vem do `cargos[]` do
frontmatter ou da igualdade de conteúdo entre os cargos — nunca de heurística
sobre o nome.
"""
import argparse
import difflib
import hashlib
import re
import shutil
import sys
from pathlib import Path

PASTA_CARGO = "03-MAPAS-MATERIAS"
PASTA_COMUM = "03-MAPAS-COMUNS"
NAO_PUBLICAVEL = re.compile(r"^(00-INDICE|99-Status)", re.IGNORECASE)


def ler_frontmatter(md: Path) -> dict:
    txt = md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    fm = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha:
                k, _, v = linha.partition(":")
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def digest(md: Path) -> str:
    return hashlib.sha256(md.read_bytes()).hexdigest()


def escopos_de_cargo(base: Path) -> list[Path]:
    return [d for d in sorted(base.iterdir())
            if d.is_dir() and d.name != "_COMUM" and not d.name.startswith(".")]


def semelhanca(a: Path, b: Path) -> float:
    ta = a.read_text(encoding="utf-8").split("\n")
    tb = b.read_text(encoding="utf-8").split("\n")
    return difflib.SequenceMatcher(None, ta, tb).ratio()


def reescrever_wikilinks(base: Path, de_para: dict[str, str], aplicar: bool) -> int:
    """Troca o caminho antigo pelo novo em todo `.md` do concurso.

    Os índices referenciam o mapa pelo caminho completo (`[[CARGO/03-MAPAS-MATERIAS/…]]`),
    então mover sem isto quebra todos eles.
    """
    n = 0
    for md in base.rglob("*.md"):
        try:
            txt = md.read_text(encoding="utf-8")
        except OSError:
            continue
        novo = txt
        for antigo, atual in de_para.items():
            novo = novo.replace(antigo, atual)
        if novo != txt:
            n += 1
            if aplicar:
                md.write_text(novo, encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--limiar", type=float, default=0.90,
                    help="semelhança mínima entre os gêmeos para consolidar sem "
                         "pendência (0-1). Abaixo disso, o humano decide.")
    args = ap.parse_args()
    base = args.concurso_dir
    if not base.is_dir():
        sys.exit(f"erro: não é diretório: {base}")

    # agrupar mapas por slug de arquivo, entre os cargos
    por_slug: dict[str, list[Path]] = {}
    for cargo in escopos_de_cargo(base):
        pasta = cargo / PASTA_CARGO
        if not pasta.is_dir():
            continue
        for md in sorted(pasta.glob("*.md")):
            if NAO_PUBLICAVEL.match(md.stem):
                continue
            por_slug.setdefault(md.name, []).append(md)

    destino_dir = base / "_COMUM" / PASTA_COMUM
    mover, pendencias, de_para = [], [], {}

    for nome, arquivos in sorted(por_slug.items()):
        if len(arquivos) < 2:
            continue        # só um cargo cobra: o mapa fica onde está
        destino = destino_dir / nome
        if destino.exists():
            pendencias.append(f"{nome}: já existe em {PASTA_COMUM}; nada movido")
            continue
        digests = {digest(a) for a in arquivos}
        if len(digests) > 1:
            pares = [(a, b) for i, a in enumerate(arquivos) for b in arquivos[i + 1:]]
            pior = min(semelhanca(a, b) for a, b in pares)
            if pior < args.limiar:
                pendencias.append(
                    f"{nome}: os {len(arquivos)} mapas divergem (semelhança "
                    f"{pior:.0%} < {args.limiar:.0%}) — escolha qual fica antes de "
                    f"consolidar; podem ser matérias diferentes com o mesmo nome")
                continue
        # o primeiro (ordem alfabética de cargo) é o que fica; os demais somem
        fica, somem = arquivos[0], arquivos[1:]
        mover.append((fica, destino, somem))
        for a in arquivos:
            de_para[f"{a.parent.parent.name}/{PASTA_CARGO}/{a.stem}"] = \
                f"_COMUM/{PASTA_COMUM}/{a.stem}"

    modo = "APLICADO" if args.aplicar else "DRY-RUN (nada foi movido)"
    print(f"{modo}: {len(mover)} matéria(s) a consolidar em {PASTA_COMUM}/")
    for fica, destino, somem in mover:
        print(f"  {fica.parent.parent.name}/{fica.name}  ->  _COMUM/{PASTA_COMUM}/")
        for s in somem:
            print(f"      remove duplicata: {s.parent.parent.name}/{s.name}")
        if args.aplicar:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(fica), str(destino))
            for s in somem:
                s.unlink()

    n = reescrever_wikilinks(base, de_para, args.aplicar)
    print(f"\n{n} arquivo(s) com wikilink reescrito"
          f"{'' if args.aplicar else ' (seriam)'}")

    if pendencias:
        sys.stderr.write("\nPENDÊNCIAS (nada movido para estes):\n")
        for p in pendencias:
            sys.stderr.write(f"  - {p}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
