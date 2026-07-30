#!/usr/bin/env python3
"""
propor_vinculos.py — extrai o material cru para vincular ASSUNTO -> TÓPICO do edital.

Este script NÃO decide nada. Ele lê o vault e monta um JSON com, de um lado, os
tópicos de cada mapa e, de outro, os assuntos já aprofundados — para que a
classificação seja feita por leitura (pelo agente ou pelo humano) e depois
aplicada por `aplicar_vinculos.py`.

A separação é o ponto. Vincular assunto a tópico não é problema de regex: dos
203 tópicos dos 24 mapas do vault, só ~18% casam por slug com algum assunto. Um
tópico do edital pode cobrir vários assuntos, aprofundamento por legislação é
N:M, e assunto reaproveitado de outro concurso mantém o slug do edital de
origem. Derivar automaticamente produziria vínculo errado na maior parte — e
vínculo errado é pior que vínculo ausente, porque some da vista.

Saída (JSON):
{
  "concurso": "SEDES_2026",
  "materias": [
    {
      "materia_id": "...",            # proposto: slug do mapa (revisar!)
      "escopo_aprofundamento": "_COMUM",
      "pasta_aprofundamento": "direitos-violacoes",
      "nome_no_aprofundamento": "Direitos e Violações (EDAS)",
      "mapas": [ {"escopo": "ASSISTENTE-SOCIAL", "arquivo": "04-....md",
                   "nome": "...", "topicos": [{"id","numero","titulo"}]} ],
      "assuntos": [ {"slug","titulo","arquivos":[...],"topico_id":[]} ]
    }
  ]
}

Preencher `topico_id` de cada assunto (lista — um assunto pode servir a mais de
um tópico) e conferir `materia_id`. Deixar `[]` é legítimo: significa "não
consegui dizer", e o site mostra esses assuntos num balde próprio.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aprofundamento_id import eh_pasta_aprofundamento, slug  # noqa: E402

PASTAS_MAPA = ("03-MAPAS-MATERIAS", "03-MAPAS-COMUNS")
NAO_PUBLICAVEL = re.compile(r"^(00-INDICE|99-Status)", re.IGNORECASE)
TOPICO_NUMERADO = re.compile(r"^(\d+)\.\s*(.+)$")
PRIORIDADE_EMOJI = ("🔴", "🟠", "🟡", "🟢")


def ler_frontmatter(md: Path) -> dict:
    try:
        txt = md.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    fm = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha:
                k, _, v = linha.partition(":")
                fm[k.strip()] = v.strip().strip('"').strip("'")
    fm["_corpo"] = txt[m.end():] if m else txt
    return fm


def slug_doc(nome: str) -> str:
    return slug(re.sub(r"^\d{2}[-_ ]+", "", nome.removesuffix(".md")))


def limpar_titulo(t: str) -> str:
    for e in PRIORIDADE_EMOJI:
        t = t.replace(e, "")
    t = re.sub(r"\s*\((BLOCO [^)]+)\)\s*$", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", t).strip(" —-·")


def topicos_do_mapa(md: Path) -> list[dict]:
    """Os `## N. Título` do mapa. O `id` é o slug do título — e não o número —
    porque numeração muda quando um tópico é inserido, e aí todo vínculo
    gravado apontaria para o tópico errado em silêncio."""
    corpo = ler_frontmatter(md).get("_corpo", "")
    achados = []
    for bloco in re.split(r"^##\s+", corpo, flags=re.MULTILINE)[1:]:
        m = TOPICO_NUMERADO.match(bloco.split("\n")[0].strip())
        if not m:
            continue
        titulo = limpar_titulo(m.group(2))
        achados.append({"id": slug(titulo), "numero": int(m.group(1)),
                        "titulo": titulo})
    return achados


def escopos(base: Path) -> list[Path]:
    return [d for d in sorted(base.iterdir())
            if d.is_dir() and not d.name.startswith(".")]


def mapas_do_concurso(base: Path) -> list[dict]:
    achados = []
    for esc in escopos(base):
        for nome in PASTAS_MAPA:
            for md in sorted((esc / nome).glob("*.md")) if (esc / nome).is_dir() else []:
                if NAO_PUBLICAVEL.match(md.stem):
                    continue
                tops = topicos_do_mapa(md)
                if not tops:
                    continue
                fm = ler_frontmatter(md)
                achados.append({
                    "escopo": esc.name, "arquivo": md.name,
                    "slug": slug_doc(md.name),
                    "materia_id_atual": fm.get("materia_id", ""),
                    "nome": fm.get("materia", "") or md.stem,
                    "topicos": tops,
                })
    return achados


def assuntos_da_materia(materia_dir: Path) -> list[dict]:
    achados = []
    for pasta in sorted((materia_dir / "assuntos").iterdir()):
        if not pasta.is_dir():
            continue
        arquivos, titulo, topico_atual = [], "", []
        for sub in sorted(pasta.iterdir()):
            if not (sub.is_dir() and eh_pasta_aprofundamento(sub.name)):
                continue
            for md in sorted(sub.glob("*.md")):
                if md.name.startswith(("flashcards-", "_", "00-")):
                    continue
                fm = ler_frontmatter(md)
                titulo = titulo or fm.get("title", "")
                if fm.get("topico_id"):
                    topico_atual = [t.strip() for t in
                                    fm["topico_id"].strip("[]").split(",") if t.strip()]
                arquivos.append(str(md))
        if arquivos:
            achados.append({"slug": pasta.name, "titulo": titulo or pasta.name,
                            "arquivos": arquivos, "topico_id": topico_atual})
    return achados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    base = args.concurso_dir
    if not base.is_dir():
        sys.exit(f"erro: não é diretório: {base}")

    mapas = mapas_do_concurso(base)
    materias = []
    for esc in escopos(base):
        aprof = esc / "03-APROFUNDAMENTO"
        if not aprof.is_dir():
            continue
        for mdir in sorted(aprof.iterdir()):
            if not (mdir / "assuntos").is_dir():
                continue
            assuntos = assuntos_da_materia(mdir)
            if not assuntos:
                continue
            nome = ""
            for idx in mdir.glob("00-INDICE*.md"):
                nome = ler_frontmatter(idx).get("materia", "")
                break
            # candidatos: mapas cujo slug ou nome se parecem com o da matéria.
            # É PISTA para quem revisa, não decisão — por isso vão todos os
            # candidatos, e a escolha fica explícita no campo `materia_id`.
            cands = [m for m in mapas
                     if m["slug"].startswith(mdir.name[:12])
                     or mdir.name.startswith(m["slug"][:12])]
            materias.append({
                "materia_id": (cands[0]["slug"] if len(cands) == 1 else ""),
                "escopo_aprofundamento": esc.name,
                "pasta_aprofundamento": mdir.name,
                "nome_no_aprofundamento": nome or mdir.name,
                "mapas_candidatos": cands or mapas,
                "assuntos": assuntos,
            })

    saida = {"concurso": base.name, "dir": str(base), "materias": materias}
    txt = json.dumps(saida, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(txt, encoding="utf-8")
        sys.stderr.write(f"OK: proposta em {args.out}\n")
    else:
        print(txt)

    sem_mapa = [m["pasta_aprofundamento"] for m in materias if not m["materia_id"]]
    if sem_mapa:
        sys.stderr.write(f"ATENÇÃO: {len(sem_mapa)} matéria(s) sem `materia_id` "
                         f"resolvido — preencher à mão: {', '.join(sem_mapa)}\n")
    n_ass = sum(len(m["assuntos"]) for m in materias)
    n_sem = sum(1 for m in materias for a in m["assuntos"] if not a["topico_id"])
    sys.stderr.write(f"{len(materias)} matéria(s), {n_ass} assunto(s), "
                     f"{n_sem} sem vínculo com tópico.\n")


if __name__ == "__main__":
    main()
