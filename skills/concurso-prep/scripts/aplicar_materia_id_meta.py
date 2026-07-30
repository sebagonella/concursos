#!/usr/bin/env python3
"""
aplicar_materia_id_meta.py — grava `materia_id` nas matérias do `.meta.json`.

É a terceira e última perna do vínculo. O id já está no assunto e no mapa; sem
ele também no `.meta.json`, o validador continua derivando o id do NOME COMPLETO
do edital ("Conhecimentos do DF, Política para Mulheres, Legislação e Primeiros
Socorros") e comparando com o slug curto do arquivo
(`conhecimentos-df-legislacao-primeiros-socorros`) — o que nunca casa e produz
um aviso por matéria, para sempre.

Como decide: usa o MESMO casamento por palavras do `validate_output.py`
(`check_cobertura_mapas`), e só grava quando há **exatamente um** mapa candidato.
Ambiguidade vira pendência para decisão humana — escolher no palpite gravaria um
id errado no lugar mais central do concurso.

Disciplina: dry-run por padrão, backup `.meta.json.bak`, pendência com exit 2.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_output import slug_simples, tokens_uteis  # noqa: E402

PASTAS_MAPA = ("03-MAPAS-MATERIAS", "03-MAPAS-COMUNS")


def mapas_do_concurso(base: Path) -> dict[str, Path]:
    achados = {}
    for pasta in PASTAS_MAPA:
        for md in sorted(base.glob(f"*/{pasta}/*.md")):
            if re.match(r"^(00-INDICE|99-Status)", md.stem, re.IGNORECASE):
                continue
            fm = re.match(r"^---\s*\n(.*?)\n---\s*\n", md.read_text(encoding="utf-8"),
                          re.DOTALL)
            mid = ""
            if fm:
                m = re.search(r"^materia_id:\s*(\S+)", fm.group(1), re.MULTILINE)
                mid = m.group(1) if m else ""
            achados[mid or slug_simples(re.sub(r"^\d{2}[-_ ]+", "", md.stem))] = md
    return achados


def candidatos(nome: str, mapas: dict[str, Path]) -> list[str]:
    alvo = tokens_uteis(slug_simples(nome))
    return [k for k in mapas
            if len(alvo & tokens_uteis(k)) >= 2
            or (tokens_uteis(k) and tokens_uteis(k) <= alvo)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    base = args.concurso_dir
    meta_p = base / ".meta.json"
    if not meta_p.exists():
        sys.exit(f"erro: {meta_p} não existe")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    mapas = mapas_do_concurso(base)

    tocados, pendencias = [], []

    def resolver(m: dict) -> bool:
        """Grava o id na matéria. Devolve True se mudou."""
        if not isinstance(m, dict) or not (m.get("nome") or "").strip():
            return False
        nome = m["nome"].strip()
        if m.get("materia_id"):
            return False                       # já resolvido, não mexer
        cands = candidatos(nome, mapas)
        if len(cands) == 1:
            m["materia_id"] = cands[0]
            tocados.append((nome, cands[0]))
            return True
        if not cands:
            pendencias.append(f"{nome!r}: nenhum mapa candidato")
        else:
            pendencias.append(f"{nome!r}: {len(cands)} candidatos "
                              f"({', '.join(sorted(cands))}) — escolha à mão")
        return False

    mudou = False
    for m in meta.get("materias") or []:
        mudou |= resolver(m)
    for lista in (meta.get("materias_por_cargo") or {}).values():
        for m in lista or []:
            mudou |= resolver(m)

    modo = "APLICADO" if args.aplicar else "DRY-RUN (nada foi escrito)"
    print(f"{modo}: {len(tocados)} matéria(s) do .meta.json")
    for nome, mid in tocados:
        print(f"  {nome[:58]:60} -> {mid}")
    if mudou and args.aplicar:
        meta_p.with_suffix(".json.bak").write_text(
            meta_p.read_text(encoding="utf-8"), encoding="utf-8")
        meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")

    if pendencias:
        sys.stderr.write("\nPENDÊNCIAS (não gravadas):\n")
        for p in pendencias:
            sys.stderr.write(f"  - {p}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
