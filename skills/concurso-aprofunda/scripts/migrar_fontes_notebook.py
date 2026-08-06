#!/usr/bin/env python3
"""
migrar_fontes_notebook.py — declara no vault as leis que sobem ao NotebookLM.

Até aqui a lista de fontes de cada notebook era **adivinhada** a cada geração do
pacote, por uma heurística que ninguém via decidir. Isso pôs leis não declaradas
em dezenas de aprofundamentos e deixou a pergunta "com que fontes este podcast
foi feito?" sem resposta possível sem abrir o notebook.

Este script grava a decisão em `fontes_notebook:` no `.md` do assunto. A partir
daí a heurística vira sugestão: quando o campo existe, ele manda.

Uso:
    python migrar_fontes_notebook.py --concurso-dir <.../CONCURSOS/SEDES_2026>
    python migrar_fontes_notebook.py --concurso-dir <...> --aplicar
    python migrar_fontes_notebook.py --materia-dir <.../03-APROFUNDAMENTO/{materia}>

`--dry-run` é o padrão: sem `--aplicar`, nada é escrito. Campo já declarado
**nunca** é sobrescrito — a segunda execução apagaria a decisão humana.

Sai 1 se houver o que migrar (útil em verificação); 0 quando não há.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notebooklm_pack as nlp  # noqa: E402

CAMPO = "fontes_notebook"


def leis_dir_do(pasta: Path) -> Path | None:
    """As leis ficam num lugar só por concurso: `{CONCURSO}/_COMUM/04-MATERIAIS/`.

    Vale também para aprofundamento de cargo — medido no vault, nenhum cargo tem
    `leis-baixadas` próprio, e duplicar por escopo criaria versões divergentes do
    mesmo PDF.
    """
    for pai in pasta.parents:
        cand = pai / "_COMUM/04-MATERIAIS/leis-baixadas"
        if cand.is_dir():
            return cand
    return None


def gravar_campo(md: Path, nomes: list[str]) -> None:
    """Acrescenta `fontes_notebook:` ao frontmatter, com backup `.md.bak`.

    O backup é `.md.bak`, **nunca** `.bak.md`: quem acha o arquivo principal do
    aprofundamento pega o primeiro `*.md` em ordem, e `….bak.md` ordenaria ANTES
    do `….md` — o backup viraria o aprofundamento.
    """
    txt = md.read_text(encoding="utf-8")
    m = re.match(r"(---\n)(.*?)(\n---\n)", txt, re.S)
    if not m:
        raise SystemExit(f"ERRO: {md.name} não tem frontmatter")
    valor = "[" + ", ".join(nomes) + "]"
    linha = re.compile(rf"^{CAMPO}:.*$", re.M)
    corpo_fm = (linha.sub(f"{CAMPO}: {valor}", m.group(2), count=1)
                if linha.search(m.group(2)) else m.group(2) + f"\n{CAMPO}: {valor}")
    md.with_name(md.name + ".bak").write_text(txt, encoding="utf-8")
    md.write_text(m.group(1) + corpo_fm + m.group(3) + txt[m.end():], encoding="utf-8")


def declaradas_em(fm: dict) -> list[str]:
    """As fontes já declaradas, na ordem em que estão gravadas."""
    bruto = str(fm.get(CAMPO) or "").strip()
    if bruto.startswith("[") and bruto.endswith("]"):
        bruto = bruto[1:-1]
    return [x.strip().strip('"').strip("'") for x in bruto.split(",") if x.strip()]


def varrer(raiz: Path, completar: bool = False) -> list[dict]:
    achados = []
    for assuntos_dir in sorted(raiz.rglob("assuntos")):
        if not assuntos_dir.is_dir():
            continue
        for assunto_dir in sorted(p for p in assuntos_dir.iterdir() if p.is_dir()):
            for pasta in nlp.pastas_de_aprofundamento(assunto_dir):
                md = nlp.arquivo_principal(pasta)
                if md is None:
                    continue
                fm = nlp.ler_frontmatter(md)
                ja = fm.get(CAMPO) is not None
                leis_dir = leis_dir_do(pasta)
                # `leis_relacionadas` respeita o campo declarado e devolve ele
                # mesmo — para SUGERIR de novo é preciso perguntar sem o fm.
                sugeridas = ([] if (ja and not completar)
                             else nlp.leis_relacionadas(fm.get("_corpo", ""), leis_dir))
                atuais = declaradas_em(fm) if ja else []
                # União preservando a ordem: o que já está declarado é decisão
                # tomada e nunca sai; o novo entra no fim.
                acrescentar = [n for n in sugeridas if n not in atuais]
                achados.append({
                    "assunto": assunto_dir.name, "aprofundamento": pasta.name,
                    "md": md, "ja_declarado": ja, "sugeridas": sugeridas,
                    "atuais": atuais, "acrescentar": acrescentar,
                })
    return achados


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--concurso-dir", type=Path)
    ap.add_argument("--materia-dir", type=Path)
    ap.add_argument("--aplicar", action="store_true",
                    help="escreve no vault (sem isto, só mostra)")
    ap.add_argument("--completar", action="store_true",
                    help="reexamina os já declarados e ACRESCENTA o que faltar "
                         "(nunca remove); use depois de melhorar a heurística")
    a = ap.parse_args()

    raiz = a.concurso_dir or a.materia_dir
    if not raiz or not raiz.is_dir():
        sys.stderr.write("ERRO: informe --concurso-dir ou --materia-dir\n")
        return 2

    achados = varrer(raiz, completar=a.completar)
    # Varrer e não achar nada FALHA ALTO — sair com sucesso sobre zero arquivos é
    # o defeito que fez o `fix_notebooklm_packs` achar 0 dos 158 pacotes e passar.
    if not achados:
        sys.stderr.write(f"ERRO: nenhum aprofundamento encontrado em {raiz}\n")
        return 2

    ja = [x for x in achados if x["ja_declarado"]]
    if a.completar:
        completar = [x for x in ja if x["acrescentar"]]
        for x in sorted(completar, key=lambda y: y["assunto"]):
            print(f"  {x['assunto'][:38]:<40} {x['aprofundamento'][:24]:<26} "
                  f"+{len(x['acrescentar'])}")
            for n in x["acrescentar"]:
                print(f"      + {n}")
            if a.aplicar:
                gravar_campo(x["md"], x["atuais"] + x["acrescentar"])
        print(json.dumps({
            "aprofundamentos": len(achados), "ja_declarados": len(ja),
            "completados": len(completar),
            "leis_acrescentadas": sum(len(x["acrescentar"]) for x in completar),
            "aplicado": bool(a.aplicar),
        }, indent=2, ensure_ascii=False))
        return 0 if a.aplicar or not completar else 1

    a_migrar = [x for x in achados if not x["ja_declarado"]]
    com_lei = [x for x in a_migrar if x["sugeridas"]]
    sem_lei = [x for x in a_migrar if not x["sugeridas"]]

    for x in sorted(com_lei, key=lambda y: (-len(y["sugeridas"]), y["assunto"])):
        print(f"  {x['assunto'][:38]:<40} {x['aprofundamento'][:24]:<26} "
              f"{len(x['sugeridas'])} lei(s)")
        for n in x["sugeridas"]:
            print(f"      · {n}")
        if a.aplicar:
            gravar_campo(x["md"], x["sugeridas"])

    # Sem lei é DECISÃO, não lacuna: grava `[]` para que o campo exista e a
    # heurística não volte a adivinhar na próxima geração do pacote.
    for x in sem_lei:
        if a.aplicar:
            gravar_campo(x["md"], [])

    print(json.dumps({
        "aprofundamentos": len(achados),
        "ja_declarados": len(ja),
        "migrados_com_lei": len(com_lei),
        "migrados_sem_lei": len(sem_lei),
        "leis_declaradas": sum(len(x["sugeridas"]) for x in com_lei),
        "aplicado": bool(a.aplicar),
    }, indent=2, ensure_ascii=False))

    if not a.aplicar and a_migrar:
        sys.stderr.write(f"\n{len(a_migrar)} aprofundamento(s) a migrar. "
                         "Rode de novo com --aplicar para gravar.\n")
    return 1 if (a_migrar and not a.aplicar) else 0


if __name__ == "__main__":
    raise SystemExit(main())
