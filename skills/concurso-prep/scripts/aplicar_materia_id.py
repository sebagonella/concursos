#!/usr/bin/env python3
"""
aplicar_materia_id.py — grava `materia_id` no frontmatter dos mapas de matéria.

É a outra metade do vínculo. O `aplicar_vinculos.py` grava o id no lado do
ASSUNTO; sem o mesmo id no lado do MAPA, os dois continuam sem se encontrar e a
matéria segue sem aba Plano — o join volta a ser por nome de pasta, que diverge
em boa parte dos casos reais (`direitos-violacoes` no aprofundamento contra
`direitos-violacoes-vulnerabilidades` no mapa).

Consome o mesmo JSON revisado do `propor_vinculos.py`: dele vem o `materia_id`
escolhido e qual mapa é o dono daquele id.

Disciplina: dry-run por padrão, backup `.md.bak`, só mexe no frontmatter,
pendência ruidosa com exit code 2.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PASTAS_MAPA = ("03-MAPAS-MATERIAS", "03-MAPAS-COMUNS")


def achar_mapa(base: Path, arquivo: str) -> list[Path]:
    """Procura o mapa pelo NOME em qualquer escopo.

    Por nome, e não pelo escopo declarado no JSON, porque a consolidação de
    mapas comuns pode tê-lo movido de `{CARGO}/03-MAPAS-MATERIAS/` para
    `_COMUM/03-MAPAS-COMUNS/` entre a proposta e a aplicação.
    """
    return [p for pasta in PASTAS_MAPA for p in base.glob(f"*/{pasta}/{arquivo}")]


def gravar(md: Path, materia_id: str, aplicar: bool) -> str | None:
    txt = md.read_text(encoding="utf-8")
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", txt, re.DOTALL)
    if not m:
        # mapa sem frontmatter: cria um mínimo, senão não há onde gravar o id
        novo = f"---\nmateria_id: {materia_id}\n---\n\n{txt}"
    else:
        linhas = [l for l in m.group(2).split("\n")
                  if not l.strip().startswith("materia_id:")]
        atual = re.search(r"^materia_id:\s*(\S+)", m.group(2), re.MULTILINE)
        if atual and atual.group(1) == materia_id:
            return None                      # já está lá, nada a fazer
        novo = (m.group(1) + "\n".join([f"materia_id: {materia_id}"] + linhas)
                + m.group(3) + txt[m.end():])
    if novo == txt:
        return None
    if aplicar:
        md.with_suffix(".md.bak").write_text(txt, encoding="utf-8")
        md.write_text(novo, encoding="utf-8")
    return materia_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vinculos", type=Path, required=True)
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    dados = json.loads(args.vinculos.read_text(encoding="utf-8"))
    base = args.concurso_dir
    tocados, pendencias = [], []

    for mat in dados.get("materias", []):
        materia_id = (mat.get("materia_id") or "").strip()
        if not materia_id:
            pendencias.append(f"{mat['pasta_aprofundamento']}: sem `materia_id`")
            continue
        donos = [c for c in mat.get("mapas_candidatos", [])
                 if c.get("slug") == materia_id]
        if not donos:
            pendencias.append(
                f"{mat['pasta_aprofundamento']}: nenhum mapa candidato tem slug "
                f"{materia_id!r} — o id escolhido não corresponde a mapa nenhum")
            continue
        for dono in donos:      # a mesma matéria pode ter mapa em mais de um cargo
            achados = achar_mapa(base, dono["arquivo"])
            if not achados:
                pendencias.append(f"mapa {dono['arquivo']!r} não encontrado")
                continue
            for md in achados:
                r = gravar(md, materia_id, args.aplicar)
                if r:
                    tocados.append((md, r))

    modo = "APLICADO" if args.aplicar else "DRY-RUN (nada foi escrito)"
    print(f"{modo}: {len(tocados)} mapa(s)")
    for md, mid in tocados:
        print(f"  {md.parent.parent.name}/{md.name}  ->  materia_id: {mid}")
    if pendencias:
        sys.stderr.write("\nPENDÊNCIAS:\n")
        for p in pendencias:
            sys.stderr.write(f"  - {p}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
