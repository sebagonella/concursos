#!/usr/bin/env python3
"""
migrar_aprofundamentos.py — move aprofundamentos para a convenção de pastas atual.

Convenção de destino (ver aprofundamento_id.py, fonte de verdade):

    assuntos/{slug-assunto}/{nivel}--{N}f--f1-{fonte1}[--f2-{fonte2}]/
        {slug-assunto}--{nivel}--{N}f--f1-{fonte1}[...].md
        flashcards-{slug-assunto}--{nivel}--{N}f--f1-{fonte1}[...].md/.csv
        cards.json, _fonte-notebooklm.md, mídias...

Formatos de ORIGEM reconhecidos:
    a) legado plano   assuntos/crase/crase.md
    b) 0.2.x          assuntos/crase/aprofundamentos/pestana--padrao/crase--pestana--padrao.md
    c) já convertido  assuntos/crase/padrao--1f--f1-pestana/...        (ignorado)

A fonte de cada assunto é lida do frontmatter:
    localizacao_livro:  "<livro>.pdf — págs. 10–20"   -> livro  (autor)
    fonte_norma:        "Lei nº 8.742/1993"           -> norma  (identificador)
Normas separadas por ';' contam como fontes distintas (f1, f2, ...); alteração
posterior da MESMA norma NÃO conta como fonte extra.

O nível vem do frontmatter (`nivel:`) ou, se ausente, é inferido pelas seções do
documento (o template detalhado tem "Desenvolvimento completo"/"Exemplos
resolvidos"). Na dúvida assume `padrao` e REGISTRA no relatório.

Uso:
    python migrar_aprofundamentos.py --raiz <.../CONCURSOS> --dry-run
    python migrar_aprofundamentos.py --raiz <.../CONCURSOS> --overrides ov.json --aplicar

Segurança:
  - --dry-run é o padrão; nada é escrito sem --aplicar.
  - MOVE (não copia): o conteúdo do usuário é preservado, nunca reescrito.
  - Nunca sobrescreve uma pasta de destino existente — reporta conflito e pula.
  - Um slug de fonte "suspeito" vira PENDÊNCIA: o script recusa migrar e pede
    override explícito, em vez de gravar um path ruim no vault.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aprofundamento_id import (  # noqa: E402
    slug, slug_fonte, slug_suspeito, id_aprofundamento, nome_base,
    eh_pasta_aprofundamento, parse_id,
)

# arquivos que acompanham o aprofundamento e devem migrar junto
PREFIXOS_RENOMEAR = ("flashcards-", "podcast-", "mapa-mental-", "video-", "report-")
ACOMPANHAM = ("cards.json", "_fonte-notebooklm.md", "_fonte-notebooklm.bak.md")

MARCAS_DETALHADO = (
    "Desenvolvimento completo",
    "Exemplos resolvidos",
    "Questões comentadas",
    "Divergências entre autores",
)


def ler_frontmatter(md: Path) -> dict:
    try:
        txt = md.read_text(encoding="utf-8")
    except Exception:
        return {"_corpo": ""}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    fm = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha and not linha.lstrip().startswith("-"):
                k, _, v = linha.partition(":")
                v = v.strip()
                if not v.startswith(('"', "'")):
                    v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
                fm[k.strip()] = v.strip('"').strip("'")
    fm["_corpo"] = txt[m.end():] if m else txt
    fm["_texto"] = txt
    fm["_fm_bruto"] = m.group(1) if m else ""
    return fm


def separar_normas(valor: str) -> list[str]:
    """Divide 'Lei A; Decreto B' em fontes distintas.

    Um parêntese de alteração ('com alterações da Lei X') pertence à norma
    anterior e NÃO vira fonte nova.
    """
    valor = re.sub(r"\((?:com\s+)?altera[cç][oõ]es[^)]*\)", "", valor, flags=re.IGNORECASE)
    partes = [p.strip(" .;") for p in re.split(r"[;]", valor) if p.strip(" .;")]
    return partes or [valor.strip()]


def fontes_do_assunto(fm: dict) -> tuple[list[str], str]:
    """Devolve (lista de nomes de fonte, tipo) — tipo em {'livro','norma','?'}."""
    loc = (fm.get("localizacao_livro") or "").strip()
    if loc:
        livro = re.split(r"\s+—\s+|\s+-\s+p[áa]gs?\.", loc)[0].strip()
        return ([livro] if livro else []), "livro"
    norma = (fm.get("fonte_norma") or "").strip()
    if norma:
        return separar_normas(norma), "norma"
    fontes = (fm.get("fontes") or "").strip()
    if fontes:
        return [f.strip() for f in fontes.split(",") if f.strip()], "?"
    return [], "?"


def nivel_do_assunto(fm: dict) -> tuple[str, bool]:
    """(nivel, inferido) — inferido=True quando não veio do frontmatter."""
    n = (fm.get("nivel") or "").strip().lower()
    if n in ("padrao", "detalhado"):
        return n, False
    corpo = fm.get("_corpo", "")
    achados = sum(1 for marca in MARCAS_DETALHADO if marca in corpo)
    return ("detalhado" if achados >= 2 else "padrao"), True


def _mds_principais(d: Path) -> list[Path]:
    return [p for p in sorted(d.glob("*.md"))
            if not p.name.startswith(("flashcards-", "_", "00-"))]


def _md_principal(d: Path):
    mds = _mds_principais(d)
    return mds[0] if mds else None


def origem_dos_aprofundamentos(assunto_dir: Path):
    """Cede (pasta_origem, md_principal, formato) para cada aprofundamento do assunto."""
    plano = assunto_dir / f"{assunto_dir.name}.md"
    if plano.exists():
        yield assunto_dir, plano, "legado-plano"
    antiga = assunto_dir / "aprofundamentos"
    if antiga.is_dir():
        for d in sorted(antiga.iterdir()):
            if d.is_dir() and (md := _md_principal(d)):
                yield d, md, "aprofundamentos-0.2"
    # pastas já em formato de aprofundamento: só migram se forem do formato 0.3.x
    for d in sorted(p for p in assunto_dir.iterdir() if p.is_dir()):
        info = parse_id(d.name)
        if info and info.get("formato") == "0.3" and (md := _md_principal(d)):
            yield d, md, "pasta-0.3"


def atualizar_frontmatter(texto: str, novos: dict) -> str:
    """Insere/atualiza chaves no frontmatter, preservando o resto."""
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", texto, re.DOTALL)
    if not m:
        return texto
    corpo_fm = m.group(2)
    for k, v in novos.items():
        linha = f'{k}: "{v}"' if not str(v).startswith('[') else f"{k}: {v}"
        if re.search(rf"^{re.escape(k)}:", corpo_fm, re.M):
            corpo_fm = re.sub(rf"^{re.escape(k)}:.*$", linha, corpo_fm, count=1, flags=re.M)
        else:
            corpo_fm += f"\n{linha}"
    return m.group(1) + corpo_fm + m.group(3) + texto[m.end():]


def migrar_assunto(assunto_dir: Path, overrides: dict, aplicar: bool,
                   concurso: str = "") -> list[dict]:
    resultados = []
    sassunto = assunto_dir.name
    for origem, md, formato in origem_dos_aprofundamentos(assunto_dir):
        fm = ler_frontmatter(md)
        fontes, tipo = fontes_do_assunto(fm)
        nivel, inferido = nivel_do_assunto(fm)
        conc = concurso or fm.get("concurso", "")
        # pasta 0.3.x já traz nível e slugs de fonte resolvidos: reusa em vez de rederivar
        info30 = parse_id(origem.name) if formato == "pasta-0.3" else None

        slugs, pendencias = [], []
        if info30:
            slugs, nivel, inferido = list(info30["fontes"]), info30["nivel"], False
            fontes = fontes or slugs
        else:
          for f in fontes:
            s = overrides.get(f) or overrides.get(f.strip())
            if not s:
                s = slug_fonte(f)
                if slug_suspeito(s):
                    pendencias.append(
                        f"slug '{s}' derivado de {f!r} não identifica a fonte")
            slugs.append(slug(s))

        if not fontes:
            pendencias.append("assunto sem fonte no frontmatter "
                              "(nem localizacao_livro, nem fonte_norma)")

        # Guarda: pasta com mais de um .md principal é ambígua — qual deles é o
        # conteúdo e qual é arcabouço órfão? Migrar escolhendo "o primeiro em ordem
        # alfabética" já trocou conteúdo preenchido por arcabouço vazio. Reporta.
        extras = [m.name for m in _mds_principais(origem) if m != md]
        if extras:
            pendencias.append(
                f"pasta com mais de um .md principal ({[md.name] + extras}) — "
                f"consolide manualmente antes de migrar")

        item = {
            "assunto": sassunto, "origem": str(origem), "formato_origem": formato,
            "tipo_fonte": tipo, "fontes": fontes, "nivel": nivel,
            "nivel_inferido": inferido,
        }
        if pendencias:
            item.update(status="PENDENCIA", motivos=pendencias)
            resultados.append(item)
            continue

        aprof_id = id_aprofundamento(fontes, nivel, slugs)
        base_novo = nome_base(sassunto, aprof_id, conc)
        destino = assunto_dir / aprof_id
        item.update(aprofundamento=aprof_id, destino=str(destino))

        if destino.exists() and destino != origem:
            item.update(status="CONFLITO",
                        motivos=[f"pasta de destino já existe: {destino.name}"])
            resultados.append(item)
            continue
        if origem == destino:
            item.update(status="JA-OK")
            resultados.append(item)
            continue

        # o que move e como se chama no destino
        movimentos = []
        for p in sorted(origem.iterdir()):
            if p.is_dir():
                continue
            nome = p.name
            if p == md:
                novo = f"{base_novo}.md"
            elif nome.startswith(PREFIXOS_RENOMEAR):
                prefixo = next(x for x in PREFIXOS_RENOMEAR if nome.startswith(x))
                novo = f"{prefixo}{base_novo}{p.suffix}"
            elif nome in ACOMPANHAM:
                novo = nome
            elif formato == "legado-plano":
                continue        # arquivo alheio ao aprofundamento: não mexe
            else:
                novo = nome
            movimentos.append((str(p), novo))
        item["movimentos"] = [{"de": d, "para": n} for d, n in movimentos]
        item["status"] = "MIGRAR"

        if aplicar:
            destino.mkdir(parents=True, exist_ok=True)
            for de, novo_nome in movimentos:
                shutil.move(de, str(destino / novo_nome))
            # frontmatter do .md principal ganha a identidade do aprofundamento
            alvo = destino / f"{base_novo}.md"
            txt = alvo.read_text(encoding="utf-8")
            txt = atualizar_frontmatter(txt, {
                "nivel": nivel,
                "aprofundamento": aprof_id,
                "fontes": ", ".join(fontes),
            })
            # wikilinks de flashcards passam a apontar para o novo nome
            txt = re.sub(r"\[\[flashcards-[^\]|]*?(\|[^\]]*)?\]\]",
                         lambda m: f"[[flashcards-{base_novo}{m.group(1) or ''}]]", txt)
            alvo.write_text(txt, encoding="utf-8")
            # limpa as pastas de origem que ficaram vazias (a do id e a 'aprofundamentos')
            if origem != assunto_dir and origem.is_dir() and not any(origem.iterdir()):
                origem.rmdir()
            antiga = assunto_dir / "aprofundamentos"
            if antiga.is_dir() and not any(antiga.iterdir()):
                antiga.rmdir()
        resultados.append(item)
    return resultados


def reescrever_referencias(raiz: Path, mapa: dict, aplicar: bool) -> list[dict]:
    """Atualiza wikilinks que apontam para os paths/nomes antigos.

    Os índices de matéria (00-INDICE-*.md) vivem FORA de assuntos/ e referenciam
    cada assunto pelo path completo — sem esta etapa, a migração deixa o vault
    cheio de link quebrado.

    `mapa` leva 'trecho antigo' -> 'trecho novo', do mais longo para o mais curto
    (para o path completo casar antes do nome solto).
    """
    tocados = []
    chaves = sorted(mapa, key=len, reverse=True)
    for md in sorted(raiz.rglob("*.md")):
        try:
            txt = md.read_text(encoding="utf-8")
        except Exception:
            continue
        novo, trocas = txt, 0
        for antigo in chaves:
            if antigo in novo:
                trocas += novo.count(antigo)
                novo = novo.replace(antigo, mapa[antigo])
        if trocas:
            tocados.append({"arquivo": str(md), "trocas": trocas})
            if aplicar:
                md.write_text(novo, encoding="utf-8")
    return tocados


def _concurso_do_path(p: Path) -> str:
    """Sobe o path até achar .../CONCURSOS/<CONCURSO>/..."""
    for anc in p.parents:
        if anc.parent.name.upper() == "CONCURSOS":
            return anc.name
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", type=Path,
                    help="raiz a varrer (ex.: .../30_AREAS/CARREIRA/CONCURSOS)")
    ap.add_argument("--assuntos-dir", type=Path,
                    help="migrar só uma pasta 'assuntos/' específica")
    ap.add_argument("--overrides", type=Path,
                    help='JSON {"<nome da fonte>": "<slug>"} para fontes que a '
                         'derivação automática não acerta')
    ap.add_argument("--aplicar", action="store_true",
                    help="executa de fato (sem esta flag, é dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="(padrão) não escreve nada")
    args = ap.parse_args()

    if not args.raiz and not args.assuntos_dir:
        sys.exit("erro: informe --raiz ou --assuntos-dir")
    overrides = {}
    if args.overrides and args.overrides.exists():
        overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    aplicar = args.aplicar and not args.dry_run

    if args.assuntos_dir:
        pastas_assuntos = [args.assuntos_dir]
    else:
        pastas_assuntos = sorted(p for p in args.raiz.rglob("assuntos") if p.is_dir())

    todos = []
    for pa in pastas_assuntos:
        for assunto_dir in sorted(p for p in pa.iterdir() if p.is_dir()):
            todos += migrar_assunto(assunto_dir, overrides, aplicar, _concurso_do_path(assunto_dir))

    # links que precisam ser reescritos por causa dos arquivos movidos/renomeados
    mapa_links = {}
    for r in todos:
        if r["status"] != "MIGRAR":
            continue
        aprof_id = r["aprofundamento"]
        for mov in r.get("movimentos", []):
            p_antigo = Path(mov["de"])
            stem_antigo, stem_novo = p_antigo.stem, Path(mov["para"]).stem
            # path relativo a partir de 'assuntos/', sem extensão (formato do índice)
            partes = p_antigo.parts
            if "assuntos" in partes:
                i = len(partes) - 1 - partes[::-1].index("assuntos")
                rel_antigo = "/".join(partes[i:])[: -len(p_antigo.suffix)]
                rel_novo = "/".join(partes[i:i + 2] + (aprof_id, Path(mov["para"]).stem))
                # o pipe do wikilink aparece cru (|) e escapado (\|, dentro de tabela)
                for fim in ("|", "\\|", "]]"):
                    mapa_links[rel_antigo + fim] = rel_novo + fim
            if stem_antigo != stem_novo:
                for fim in ("|", "\\|", "]]"):
                    mapa_links["[[" + stem_antigo + fim] = "[[" + stem_novo + fim

    raiz_links = args.raiz or args.assuntos_dir
    links = reescrever_referencias(raiz_links, mapa_links, aplicar) if mapa_links else []

    resumo = {}
    for r in todos:
        resumo[r["status"]] = resumo.get(r["status"], 0) + 1
    print(json.dumps({
        "modo": "APLICADO" if aplicar else "DRY-RUN (nada escrito)",
        "pastas_assuntos": len(pastas_assuntos),
        "resumo": resumo,
        "links_reescritos": {"arquivos": len(links), "detalhe": links},
        "itens": todos,
    }, indent=2, ensure_ascii=False))
    sys.exit(0 if not any(r["status"] == "PENDENCIA" for r in todos) else 2)


if __name__ == "__main__":
    main()
