#!/usr/bin/env python3
"""
flashcards_gen.py - Geração NATIVA de flashcards por assunto (sem NotebookLM).

Recebe um JSON de cards (que o agente Claude produz a partir do resumo do assunto)
e emite:
  - flashcards-{slug}.md   -> formato Obsidian (compatível com plugin Spaced Repetition:
                              "Pergunta ?? Resposta" ou blocos #flashcards)
  - flashcards-{slug}.csv  -> importável no Anki (Front;Back;Tags)

Entrada JSON:
{
  "assunto": "Concordância verbal",
  "materia": "Língua Portuguesa",
  "cards": [
    {"front": "...", "back": "...", "tag": "regra"},
    ...
  ]
}

Uso:
    python flashcards_gen.py --cards cards.json --out-dir <pasta-do-assunto> \
        [--formato obsidian,anki]

O script valida os cards (não vazios, tamanho sensato) e recusa gerar cards
duplicados. Não inventa conteúdo — só formata o que recebe.
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path


def slug(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")


def validar_cards(cards: list[dict]) -> tuple[list[dict], list[str]]:
    validos, avisos = [], []
    vistos = set()
    for i, c in enumerate(cards):
        front = (c.get("front") or "").strip()
        back = (c.get("back") or "").strip()
        if not front or not back:
            avisos.append(f"card {i}: frente ou verso vazio — descartado")
            continue
        if len(front) > 300:
            avisos.append(f"card {i}: frente muito longa ({len(front)} chars) — revise")
        chave = slug(front)
        if chave in vistos:
            avisos.append(f"card {i}: duplicado ('{front[:40]}...') — descartado")
            continue
        vistos.add(chave)
        validos.append({"front": front, "back": back, "tag": (c.get("tag") or "").strip()})
    return validos, avisos


def gerar_obsidian(cards: list[dict], assunto: str, materia: str, estilo: str = "multiline") -> str:
    """Gera flashcards no formato do plugin Spaced Repetition.

    estilo='multiline' (default): pergunta, depois '??' sozinho numa linha, depois
      resposta. Gera cartão reverso (frente<->verso). É o formato mais legível para
      respostas longas.
    estilo='singleline': 'Pergunta::Resposta' numa linha só (mais compacto).
      Use ':::' para também gerar o cartão reverso.
    """
    linhas = [
        "---",
        f'title: "Flashcards — {assunto}"',
        "tipo: flashcards",
        f'materia: "{materia}"',
        "tags: [flashcards, concurso/aprofundamento]",
        "---",
        "",
        f"# Flashcards — {assunto}",
        "",
        "> Baralho do plugin **Spaced Repetition** do Obsidian.",
        "> Para revisar: instale o plugin, abra a paleta de comandos e rode",
        '> "Spaced Repetition: Review flashcards", ou clique no baralho na barra lateral.',
        "",
        "#flashcards",
        "",
    ]
    for c in cards:
        tag = f"  <!-- {c['tag']} -->" if c["tag"] else ""
        if estilo == "singleline":
            # escapar :: que porventura exista no texto
            front = c["front"].replace("::", ":\u200b:")
            back = c["back"].replace("::", ":\u200b:")
            linhas.append(f"{front}::{back}{tag}")
            linhas.append("")
        else:
            # multi-linha: '??' PRECISA estar sozinho numa linha entre P e R
            linhas.append(c["front"])
            linhas.append("??")
            linhas.append(f"{c['back']}{tag}")
            linhas.append("")
    return "\n".join(linhas).strip() + "\n"


def gerar_anki_csv(cards: list[dict], destino: Path, assunto: str):
    with destino.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        for c in cards:
            tags = f"{slug(assunto)} {slug(c['tag'])}".strip()
            w.writerow([c["front"], c["back"], tags])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--formato", default="obsidian,anki")
    ap.add_argument("--estilo", default="multiline", choices=["multiline", "singleline"],
                    help="formato Obsidian: multiline (?? em linha própria) ou singleline (::)")
    ap.add_argument("--nome-base", default="",
                    help="nome-base dos arquivos, SEM o prefixo 'flashcards-' e sem "
                         "extensão. Deve ser o mesmo nome-base do .md do aprofundamento "
                         "(ex.: 'crase--detalhado--1f--f1-pestana'), senão o wikilink "
                         "gerado pelo build_subject_md.py não resolve e dois "
                         "aprofundamentos do mesmo assunto viram arquivos homônimos. "
                         "Padrão: slug do assunto (formato legado).")
    ap.add_argument("--aprofundamento", default="",
                    help="atalho para --nome-base: id do aprofundamento "
                         "(ex.: 'detalhado--pestana'); o nome-base vira "
                         "'{slug-assunto}--{id}[--{CONCURSO}]'.")
    ap.add_argument("--concurso", default="",
                    help="slug do concurso (ex.: SEDES_2026); entra no fim do "
                         "nome-base para o arquivo ser único no vault.")
    args = ap.parse_args()

    spec = json.loads(args.cards.read_text(encoding="utf-8"))
    assunto = spec.get("assunto", "assunto")
    materia = spec.get("materia", "")
    cards_raw = spec.get("cards", [])

    cards, avisos = validar_cards(cards_raw)
    if not cards:
        sys.stderr.write("ERRO: nenhum card válido.\n")
        for a in avisos:
            sys.stderr.write(f"  - {a}\n")
        sys.exit(1)

    formatos = {f.strip() for f in args.formato.split(",")}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    # o nome-base precisa casar com o do .md do aprofundamento: o Obsidian resolve
    # wikilinks pelo NOME do arquivo, então dois aprofundamentos do mesmo assunto
    # não podem gerar 'flashcards-{assunto}.md' os dois.
    if args.nome_base:
        s = args.nome_base
    elif args.aprofundamento:
        s = f"{slug(assunto)}--{args.aprofundamento}"
        if args.concurso:
            s = f"{s}--{args.concurso}"
    else:
        s = slug(assunto)
    gerados = []

    if "obsidian" in formatos:
        p = args.out_dir / f"flashcards-{s}.md"
        p.write_text(gerar_obsidian(cards, assunto, materia, args.estilo), encoding="utf-8")
        gerados.append(str(p))
    if "anki" in formatos:
        p = args.out_dir / f"flashcards-{s}.csv"
        gerar_anki_csv(cards, p, assunto)
        gerados.append(str(p))

    print(json.dumps({
        "assunto": assunto, "cards_validos": len(cards),
        "cards_descartados": len(cards_raw) - len(cards),
        "avisos": avisos, "gerados": gerados,
    }, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
