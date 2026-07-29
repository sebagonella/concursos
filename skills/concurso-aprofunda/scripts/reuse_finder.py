#!/usr/bin/env python3
"""
reuse_finder.py - Reaproveitamento entre concursos (skill concurso-aprofunda).

Antes de aprofundar um assunto a partir de um livro, percorre os concursos já
salvos no vault e verifica se AQUELE MESMO ASSUNTO já foi aprofundado com O MESMO
LIVRO em outro concurso. Se sim, reporta para reaproveitar em vez de refazer.

Princípio de identidade: um assunto de português ("Crase") estudado do mesmo livro
("Gramática do Pestana") é o mesmo trabalho, independente do edital. A chave é
(livro_normalizado, assunto_normalizado). As páginas servem para validar que é a
mesma edição — se divergirem muito, avisa (pode ser outra edição/numeração).

Como reconhece um assunto já aprofundado:
  - procura arquivos {vault}/**/03-MAPAS-MATERIAS/**/assuntos/<slug>/<slug>.md
  - lê o frontmatter YAML-like (title, materia, localizacao_livro, status)
  - considera "aproveitável" se status != nao-iniciado E o corpo não tem
    placeholders {XXX} pendentes (ou seja: foi realmente preenchido)

Uso:
    python reuse_finder.py --vault-concursos <dir CONCURSOS> \
        --livro "Gramatica-Pestana.pdf" --assuntos assuntos.json \
        [--concurso-atual SEDES_2026] [--json]

Saída: para cada assunto, se há fonte reaproveitável e onde.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aprofundamento_id import eh_pasta_aprofundamento  # noqa: E402


def norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(texto)).strip("-")


def ler_frontmatter(md: Path) -> dict:
    """Extrai o frontmatter YAML-like simples (chave: valor) do topo do arquivo."""
    try:
        txt = md.read_text(encoding="utf-8")
    except Exception:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    fm = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha:
                k, _, v = linha.partition(":")
                v = v.strip()
                # remover comentário inline do YAML ("padrao   # padrao | detalhado"),
                # preservando '#' dentro de valores entre aspas (ex.: URLs com fragmento)
                if not v.startswith(('"', "'")):
                    v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
                fm[k.strip()] = v.strip('"').strip("'")
    fm["_corpo"] = txt[m.end():] if m else txt
    return fm


def tem_placeholder_pendente(corpo: str) -> bool:
    return bool(re.search(r"\{[A-Z_]{3,}\}", corpo))


def extrair_paginas(localizacao: str) -> str | None:
    """De 'livro.pdf — págs. 1018–1045' extrai '1018-1045'."""
    m = re.search(r"(\d[\d,\s–\-]*\d)", localizacao or "")
    return m.group(1).replace("–", "-").strip() if m else None


def livro_bate(loc_livro: str, livro_alvo: str) -> bool:
    """Compara o livro do arquivo achado com o livro que estamos usando."""
    return norm(livro_alvo).split(".pdf")[0][:40] in norm(loc_livro) or \
           norm(loc_livro)[:40] in norm(livro_alvo)


def candidatos_assunto(vault: Path):
    """Todos os .md que são o arquivo principal de um aprofundamento.

    Formato atual:  .../assuntos/<assunto>/<nivel>--<N>f--f1-<fonte>/<assunto>--<id>.md
    Também lidos:   .../assuntos/<assunto>/aprofundamentos/<id>/<assunto>--<id>.md  (0.2.x)
                    .../assuntos/<assunto>/<assunto>.md                              (legado)
    """
    vistos = set()
    for md in sorted(vault.rglob("assuntos/*/*.md")):
        if md.stem == md.parent.name and md not in vistos:   # legado plano
            vistos.add(md)
            yield md
    for padrao in ("assuntos/*/*/*.md", "assuntos/*/aprofundamentos/*/*.md"):
        for md in sorted(vault.rglob(padrao)):
            if md.name.startswith(("flashcards-", "_", "00-")):
                continue
            pasta = md.parent
            if not (eh_pasta_aprofundamento(pasta.name)
                    or pasta.parent.name == "aprofundamentos"):
                continue
            if md not in vistos:
                vistos.add(md)
                yield md


def varrer_vault(vault: Path, livro: str) -> dict[str, list[dict]]:
    """Indexa todos os assuntos já aprofundados no vault com o livro dado.
    Retorna {assunto_norm: [ {arquivo, concurso, paginas, status, aproveitavel} ]}."""
    indice: dict[str, list[dict]] = {}
    for md in candidatos_assunto(vault):
        fm = ler_frontmatter(md)
        titulo = fm.get("title", md.stem)
        loc = fm.get("localizacao_livro", "")
        if not livro_bate(loc, livro):
            continue
        status = fm.get("status", "?")
        corpo = fm.get("_corpo", "")
        aproveitavel = status != "nao-iniciado" and not tem_placeholder_pendente(corpo)
        # concurso = pasta ancestral que contém CONCURSOS/<X>/...
        concurso = "?"
        for anc in md.parents:
            if anc.parent.name.upper() == "CONCURSOS":
                concurso = anc.name
                break
        indice.setdefault(norm(titulo), []).append({
            "arquivo": str(md),
            "concurso": concurso,
            "paginas": extrair_paginas(loc),
            "status": status,
            "aproveitavel": aproveitavel,
            "materia": fm.get("materia", ""),
        })
    return indice


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-concursos", type=Path, required=True,
                    help="diretório CONCURSOS do vault")
    ap.add_argument("--livro", required=True)
    ap.add_argument("--assuntos", type=Path, required=True)
    ap.add_argument("--concurso-atual", default=None,
                    help="para não reaproveitar de si mesmo")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    spec = json.loads(args.assuntos.read_text(encoding="utf-8"))
    assuntos = spec.get("assuntos", [])

    if not args.vault_concursos.exists():
        sys.stderr.write(f"AVISO: {args.vault_concursos} não existe; nada a reaproveitar.\n")
        print(json.dumps({"reaproveitaveis": {}, "resumo": {"encontrados": 0}}, indent=2))
        sys.exit(0)

    indice = varrer_vault(args.vault_concursos, args.livro)

    resultado = {"livro": args.livro, "reaproveitaveis": {}, "sem_fonte": [], "resumo": {}}
    for assunto in assuntos:
        fontes = indice.get(norm(assunto), [])
        # descartar o próprio concurso atual e manter só aproveitáveis
        fontes = [f for f in fontes
                  if f["aproveitavel"] and f["concurso"] != (args.concurso_atual or "")]
        if fontes:
            # preferir a fonte de status mais avançado; empate: a primeira
            melhor = sorted(fontes, key=lambda f: f["status"] != "concluido")[0]
            resultado["reaproveitaveis"][assunto] = melhor
        else:
            resultado["sem_fonte"].append(assunto)

    resultado["resumo"] = {
        "total_assuntos": len(assuntos),
        "reaproveitaveis": len(resultado["reaproveitaveis"]),
        "sem_fonte": len(resultado["sem_fonte"]),
    }

    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
