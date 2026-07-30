#!/usr/bin/env python3
"""
assuntos_do_topico.py — seleciona UM tópico do mapa e extrai seus assuntos.

Existe para aprofundar um pedaço da matéria de cada vez, em vez da matéria
inteira: escolhe-se o tópico do edital e saem dele os assuntos derivados, já com
o `topico_id` que amarra tudo ao plano.

Saída (JSON) no MESMO formato que o `book_index.py` consome, mais o vínculo:

    {"materia": "...", "materia_id": "...",
     "topico_id": "...", "topico": "4. Orçamento Público",
     "assuntos": ["...", "..."]}

Assim a saída serve de entrada direta para `book_index.py --assuntos` (com livro)
ou para `build_subject_md.py --assuntos --proprio` (sem fonte externa).

De onde saem os assuntos: dos itens de `### Subtópicos derivados` daquele tópico
— que é o que o `materia-mapper` escreve como desdobramento do item do edital.
Um tópico pode ter vários blocos de subtópicos (com sufixo temático); todos
entram, na ordem do documento.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aprofundamento_id import slug  # noqa: E402

PASTAS_MAPA = ("03-MAPAS-MATERIAS", "03-MAPAS-COMUNS")
NAO_PUBLICAVEL = re.compile(r"^(00-INDICE|99-Status)", re.IGNORECASE)
TOPICO_NUMERADO = re.compile(r"^(\d+)\.\s*(.+)$")
SUBTOPICOS_H3 = re.compile(r"^subt[oó]picos derivados", re.IGNORECASE)
ITEM = re.compile(r"^\s*[-*]\s*(?:\[[ xX]\]\s*)?(.+)$")
H4 = re.compile(r"^\s*####\s+")
PRIORIDADE_EMOJI = ("🔴", "🟠", "🟡", "🟢")


def ler_frontmatter(md: Path) -> tuple[dict, str]:
    txt = md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    fm = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha:
                k, _, v = linha.partition(":")
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, (txt[m.end():] if m else txt)


def limpar_titulo(t: str) -> str:
    for e in PRIORIDADE_EMOJI:
        t = t.replace(e, "")
    t = re.sub(r"\s*\((BLOCO [^)]+)\)\s*$", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", t).strip(" —-·")


def nome_do_h1(md: Path) -> str:
    """Nome da matéria a partir do H1, sem o rótulo do documento.

    Só 9 dos 19 mapas do vault trazem `materia:` no frontmatter; sem isto o nome
    caía no nome do arquivo (`06-conhecimentos-bancarios`).
    """
    _, corpo = ler_frontmatter(md)
    m = re.search(r"^#\s+(.+)$", corpo, re.MULTILINE)
    if not m:
        return ""
    t = re.sub(r"^[^\w(]*", "", m.group(1).strip())
    return re.sub(r"^mapa\s+de\s+estudo\s*[—–:-]\s*", "", t, flags=re.IGNORECASE).strip()


def achar_mapa(base: Path, materia_id: str) -> Path | None:
    """Acha o mapa pelo `materia_id` do frontmatter; cai no slug do arquivo."""
    reserva = None
    for pasta in PASTAS_MAPA:
        for md in sorted(base.glob(f"*/{pasta}/*.md")):
            if NAO_PUBLICAVEL.match(md.stem):
                continue
            fm, _ = ler_frontmatter(md)
            if (fm.get("materia_id") or "").strip() == materia_id:
                return md
            if slug(re.sub(r"^\d{2}[-_ ]+", "", md.stem)) == materia_id:
                reserva = reserva or md
    return reserva


def topicos_do_mapa(md: Path) -> list[dict]:
    """Cada `## N. Título` com os assuntos dos seus `### Subtópicos derivados`."""
    _, corpo = ler_frontmatter(md)
    achados = []
    for bloco in re.split(r"^##\s+", corpo, flags=re.MULTILINE)[1:]:
        linhas = bloco.split("\n")
        m = TOPICO_NUMERADO.match(linhas[0].strip())
        if not m:
            continue
        titulo = limpar_titulo(m.group(2))
        assuntos, dentro = [], False
        for sub in re.split(r"^###\s+", "\n".join(linhas[1:]), flags=re.MULTILINE)[1:]:
            slinhas = sub.split("\n")
            dentro = bool(SUBTOPICOS_H3.match(slinhas[0].strip()))
            if not dentro:
                continue
            for linha in slinhas[1:]:
                if H4.match(linha):
                    continue          # subdivisão do bloco, não é assunto
                mi = ITEM.match(linha)
                if mi:
                    texto = re.sub(r"\*\*", "", mi.group(1)).strip()
                    # o item costuma ser "Tema: explicação"; o assunto é o tema
                    assuntos.append(texto.split(":")[0].strip() if ":" in texto[:80]
                                    else texto)
        achados.append({"numero": int(m.group(1)), "titulo": titulo,
                        "id": slug(titulo), "assuntos": assuntos})
    return achados


def escolher(topicos: list[dict], alvo: str) -> dict | None:
    """Aceita número (`4`), slug (`orcamento-publico…`) ou trecho do título."""
    alvo = (alvo or "").strip()
    if alvo.isdigit():
        return next((t for t in topicos if t["numero"] == int(alvo)), None)
    s = slug(alvo)
    exatos = [t for t in topicos if t["id"] == s]
    if exatos:
        return exatos[0]
    parciais = [t for t in topicos if s and s in t["id"]]
    return parciais[0] if len(parciais) == 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--materia-id", required=True)
    ap.add_argument("--topico", required=True,
                    help="número, slug ou trecho do título do tópico")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--listar", action="store_true",
                    help="só lista os tópicos da matéria e sai")
    args = ap.parse_args()

    md = achar_mapa(args.concurso_dir, args.materia_id)
    if not md:
        sys.exit(f"erro: nenhum mapa com materia_id {args.materia_id!r} em "
                 f"{args.concurso_dir}")
    fm, _ = ler_frontmatter(md)
    topicos = topicos_do_mapa(md)

    if args.listar:
        for t in topicos:
            print(f"{t['numero']:>3}. {t['titulo']}  ({len(t['assuntos'])} assuntos) "
                  f"[{t['id']}]")
        sys.exit(0)

    alvo = escolher(topicos, args.topico)
    if not alvo:
        # falhar alto: devolver lista vazia faria a etapa seguinte gerar nada e
        # parecer que o tópico simplesmente não tem assunto
        sys.stderr.write(f"erro: tópico {args.topico!r} não encontrado em {md.name}. "
                         f"Disponíveis:\n")
        for t in topicos:
            sys.stderr.write(f"  {t['numero']:>3}. {t['titulo']} [{t['id']}]\n")
        sys.exit(2)

    saida = {
        "materia": fm.get("materia", "") or nome_do_h1(md) or md.stem,
        "materia_id": args.materia_id,
        "topico_id": alvo["id"],
        "topico": f'{alvo["numero"]}. {alvo["titulo"]}',
        "assuntos": alvo["assuntos"],
        "mapa": str(md),
    }
    txt = json.dumps(saida, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(txt, encoding="utf-8")
        sys.stderr.write(f"OK: {len(alvo['assuntos'])} assunto(s) em {args.out}\n")
    else:
        print(txt)
    if not alvo["assuntos"]:
        sys.stderr.write("AVISO: o tópico não tem `### Subtópicos derivados` — "
                         "nada a aprofundar a partir dele.\n")


if __name__ == "__main__":
    main()
