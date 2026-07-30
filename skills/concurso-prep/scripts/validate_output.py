#!/usr/bin/env python3
"""
validate_output.py - Valida a estrutura gerada pela skill concurso-prep. (v1.3.0)

Checks executados:
1. Estrutura de pastas esperada existe (convencao UPPERCASE: _COMUM/01-EDITAL etc.)
2. Nenhum arquivo .md tem placeholder nao preenchido ({XXX})
3. Links wikilink [[...]] resolvem, inclusive para pastas-irmas (V1-PREVISTO etc.)  [item 13]
4. Soma de questoes estimadas nos mapas bate com o total da prova (tolerancia %)  [item 2]
5. (modo oficial) Datas do cronograma nao ultrapassam a data da prova
6. (modo previsto) Banner PROVISORIO presente + cronograma relativo               [item 2]
7. PDFs baixados sao validos (header %PDF-)

Metadata lida de .meta.json (JSON nativo, preferido). Fallback legado: .meta.yml.  [item 11]

Uso:
    python validate_output.py <pasta-gerada> [--json] [--tolerancia 5] [--modo auto|oficial|previsto]
"""
import argparse
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path


PLACEHOLDER_RE = re.compile(r"\{[A-Z_][A-Z0-9_]{2,}\}")
# Em tabela markdown o pipe do wikilink vem escapado (\|); sem tratar isso o
# alvo capturado fica com a barra no fim e todo link em tabela vira falso positivo.
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]|]*)?(?:\\?\|[^\]]*)?\]\]")
# "Estimativa: 30" ou "Meta: 30 questoes" nos mapas / "questoes_total: N" no meta
# Casa a ESTIMATIVA DE QUESTOES NA PROVA declarada no mapa da materia.
# NAO pode casar as metas de estudo do checklist ("- [ ] 20 questoes de treino"):
# elas somavam milhares e faziam o check acusar divergencia em todo concurso.
ESTIMATIVA_RE = re.compile(
    r"estimativa[^\n:]{0,30}:?\s*\**\s*~?\s*(\d{1,3})\s*quest", re.IGNORECASE)
BANNER_RE = re.compile(r"CONTE[UÚ]DO PROVIS[OÓ]RIO", re.IGNORECASE)


def _read(md: Path) -> str:
    try:
        return md.read_text(encoding="utf-8")
    except Exception:
        return ""


def carregar_meta(root: Path) -> dict:
    """Le .meta.json (preferido) ou .meta.yml (legado). Retorna {} se ausente."""
    j = root / ".meta.json"
    if j.exists():
        try:
            return json.loads(j.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {"_erro": f".meta.json malformado: {e}"}
    y = root / ".meta.yml"
    if y.exists():
        try:
            import yaml  # opcional
            return yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        except ImportError:
            return {"_erro": ".meta.yml presente mas PyYAML ausente (prefira .meta.json)"}
        except Exception as e:
            return {"_erro": f".meta.yml malformado: {e}"}
    return {}


def detectar_modo(root: Path, meta: dict, forcado: str) -> str:
    if forcado != "auto":
        return forcado
    if str(meta.get("modo", "")).lower() == "previsto":
        return "previsto"
    if root.name.upper().endswith(("_PREVISTO", "_V1-PREVISTO")):
        return "previsto"
    return "oficial"


def check_structure(root: Path) -> list[str]:
    required = [
        "00-INDICE.md",
        "_COMUM/01-EDITAL",
        "_COMUM/04-MATERIAIS",
        "_COMUM/05-HISTORICO-CONCURSO",
        "_COMUM/06-SINERGIA",
    ]
    issues = []
    # aceitar .meta.json OU .meta.yml
    if not (root / ".meta.json").exists() and not (root / ".meta.yml").exists():
        issues.append("FALTA: .meta.json (ou .meta.yml)")
    for path in required:
        if not (root / path).exists():
            issues.append(f"FALTA: {path}")
    return issues


def materias_do_meta(meta: dict) -> list[dict]:
    """Todas as matérias do concurso, de `materias[]` e de `materias_por_cargo`.

    Os dois lugares existem e nenhum é completo sozinho: no SEDES, `materias[]`
    só traz as do AGENTE-SOCIAL e o resto vive em `materias_por_cargo`; no BB
    não há `materias_por_cargo` e faltam 3 matérias inteiras. Ler só um dos dois
    é o que fazia a checagem passar por cima do buraco.
    """
    achadas, vistos = [], set()
    fontes = list(meta.get("materias") or [])
    for lista in (meta.get("materias_por_cargo") or {}).values():
        fontes.extend(lista or [])
    for m in fontes:
        if not isinstance(m, dict):
            continue
        nome = (m.get("nome") or "").strip()
        chave = (m.get("materia_id") or slug_simples(nome))
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        achadas.append({"nome": nome, "materia_id": chave})
    return achadas


def slug_simples(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


# palavras que não distinguem uma matéria de outra
_VAZIAS = {"de", "do", "da", "dos", "das", "e", "em", "no", "na", "para", "a", "o",
           "conhecimentos", "especificos", "fundamentos", "nocoes", "geral", "gerais"}


def tokens_uteis(slug: str) -> set[str]:
    return {t for t in slug.split("-") if len(t) > 2 and t not in _VAZIAS}


def check_cobertura_mapas(root: Path, meta: dict) -> list[str]:
    """Toda matéria do edital tem mapa de estudo?

    Este check não existia, e é por isso que o buraco passou: a Etapa 5 gera um
    mapa por matéria, mas se um subagent falha (2 retries e segue) nada depois
    confere. Pior: `check_soma_questoes` é estruturalmente cego a isso — ele
    soma os mapas que EXISTEM, e aborta com INFO quando não acha nenhum, de modo
    que zero mapas gerados passava como OK.
    """
    materias = materias_do_meta(meta)
    if not materias:
        return ["INFO: .meta.json sem materias[]; pulando cobertura de mapas"]

    achados = {}
    for pasta in ("03-MAPAS-MATERIAS", "03-MAPAS-COMUNS"):
        for md in root.glob(f"*/{pasta}/*.md"):
            if re.match(r"^(00-INDICE|99-Status)", md.stem, re.IGNORECASE):
                continue
            fm = {}
            try:
                txt = md.read_text(encoding="utf-8")
                m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
                if m:
                    for linha in m.group(1).split("\n"):
                        if ":" in linha:
                            k, _, v = linha.partition(":")
                            fm[k.strip()] = v.strip().strip('"').strip("'")
            except OSError:
                pass
            mid = fm.get("materia_id") or slug_simples(
                re.sub(r"^\d{2}[-_ ]+", "", md.stem))
            achados[mid] = md

    issues = []
    for mat in materias:
        if mat["materia_id"] in achados:
            continue
        # Candidato por sobreposição de PALAVRAS, não por prefixo: o nome do
        # edital é longo ("Conhecimentos Específicos — Agente Social") e o do
        # arquivo é curto, então prefixo casava lixo — sugeria
        # `conhecimentos-df-legislacao-primeiros-socorros` para "Conhecimentos
        # Específicos", só porque os dois começam com "conhecimentos".
        # Duas palavras em comum, OU o nome curto do arquivo inteiramente contido
        # no nome longo do edital — `fundamentos-suas` compartilha só "suas" com
        # "Fundamentos, Organização, Gestão e Marcos Operacionais do SUAS", e é
        # o mapa certo.
        alvo = tokens_uteis(mat["materia_id"])
        parecidos = [k for k in achados
                     if len(alvo & tokens_uteis(k)) >= 2
                     or (tokens_uteis(k) and tokens_uteis(k) <= alvo)]
        if parecidos:
            issues.append(f"AVISO: matéria {mat['nome']!r} não tem mapa com "
                          f"`materia_id: {mat['materia_id']}` — há candidato por "
                          f"nome parecido ({', '.join(parecidos)}); grave o "
                          f"`materia_id` no frontmatter do mapa")
        else:
            issues.append(f"FALTA: matéria {mat['nome']!r} do edital não tem mapa "
                          f"de estudo em nenhum escopo")

    orfaos = [k for k in achados if k not in {m["materia_id"] for m in materias}]
    for o in sorted(orfaos):
        issues.append(f"INFO: mapa {achados[o].name!r} não corresponde a nenhuma "
                      f"matéria do .meta.json")
    return issues


def check_placeholders(root: Path) -> list[str]:
    issues = []
    for md in root.rglob("*.md"):
        content = _read(md)
        for match in PLACEHOLDER_RE.finditer(content):
            line_start = content.rfind("\n", 0, match.start()) + 1
            nl = content.find("\n", match.start())
            line = content[line_start:nl if nl != -1 else len(content)]
            if line.lstrip().startswith(("- [ ]", "- [x]", "#", "//", "```")):
                continue
            issues.append(f"PLACEHOLDER em {md.relative_to(root)}: {match.group()}")
    return issues


def check_wikilinks(root: Path) -> list[str]:
    """Resolve links dentro da raiz E em pastas-irmas (item 13)."""
    issues = []
    search_roots = [root]
    parent = root.parent
    # pastas-irmas do mesmo concurso (ex: SEDES_2026_V1-PREVISTO ao lado da V2-OFICIAL)
    base = re.sub(r"_(V\d+-[A-Z]+|PREVISTO|OFICIAL)$", "", root.name)
    if parent.exists():
        for sib in parent.iterdir():
            if sib.is_dir() and sib != root and sib.name.startswith(base):
                search_roots.append(sib)
    all_stems, all_paths, all_names = {}, set(), set()
    for sr in search_roots:
        for p in sr.rglob("*"):
            if not p.is_file():
                continue
            all_names.add(p.name)                 # midias sao referenciadas com extensao
            if p.suffix == ".md":
                all_stems[p.stem] = p
                all_paths.add(str(p.relative_to(sr.parent)).replace(".md", ""))
    for md in root.rglob("*.md"):
        if md.name.endswith(".bak.md"):           # backup nao e conteudo vivo
            continue
        content = _read(md)
        for match in WIKILINK_RE.finditer(content):
            target = match.group(1).strip()
            stem = target.split("/")[-1]
            if stem in all_stems or stem in all_names:
                continue
            # Midia planejada pelo pacote NotebookLM e gerada FORA daqui (o usuario
            # sobe as fontes e baixa os artefatos). Ate baixar, o link aponta para
            # um arquivo que ainda nao existe — e isso e esperado, nao defeito.
            if (md.name.startswith("_fonte-notebooklm")
                    and stem.startswith(("podcast-", "video-", "mapa-mental-",
                                         "report-", "slides-", "infografico-",
                                         "teste-", "tabela-"))):
                continue
            if target in all_paths:
                continue
            if (root / f"{target}.md").exists() or (root / target).exists():
                continue
            issues.append(f"LINK QUEBRADO em {md.relative_to(root)}: [[{target}]]")
    return issues


def check_pdfs(root: Path) -> list[str]:
    issues = []
    for pdf in root.rglob("*.pdf"):
        if pdf.stat().st_size < 100:
            issues.append(f"PDF VAZIO/PEQUENO: {pdf.relative_to(root)}")
            continue
        with open(pdf, "rb") as f:
            if not f.read(5).startswith(b"%PDF-"):
                issues.append(f"PDF INVALIDO: {pdf.relative_to(root)}")
    return issues


def check_soma_questoes(root: Path, meta: dict, tol_pct: float) -> list[str]:
    """Item 2: soma das estimativas dos mapas ~= total da prova."""
    total_prova = None
    est = meta.get("estrutura_prova", {})
    if isinstance(est, dict):
        obj = est.get("objetiva", {})
        total_prova = obj.get("total_questoes") or meta.get("questoes_total")
    if not total_prova:
        return ["INFO: total de questoes ausente no meta; pulando soma"]
    # Num concurso MULTI-CARGO cada candidato faz UMA prova: as materias comuns
    # (_COMUM) valem para todos, e as especificas so para o cargo dele. Somar os
    # mapas de todos os cargos de uma vez acusa divergencia em todo concurso
    # multi-cargo — a soma tem de ser feita por cargo.
    por_cargo: dict[str, int] = {}
    comum = 0
    achou = False
    for md in root.rglob("*.md"):
        partes = md.relative_to(root).parts
        if not any("03-MAPAS-MATERIAS" in p.upper() or "03-MAPAS-COMUNS" in p.upper()
                   for p in partes):
            continue
        n = sum(int(m.group(1)) for m in ESTIMATIVA_RE.finditer(_read(md)))
        if not n:
            continue
        achou = True
        cargo = partes[0]
        if cargo.upper() == "_COMUM":
            comum += n
        else:
            por_cargo[cargo] = por_cargo.get(cargo, 0) + n
    if not achou:
        return ["INFO: nenhuma estimativa de questoes encontrada nos mapas"]

    tol = total_prova * tol_pct / 100
    alvos = {c: v + comum for c, v in por_cargo.items()} or {"(cargo unico)": comum}
    issues = []
    for cargo, soma in sorted(alvos.items()):
        if abs(soma - total_prova) > tol:
            issues.append(f"SOMA DIVERGENTE [{cargo}]: mapas somam {soma}, prova tem "
                          f"{total_prova} (tolerancia {tol_pct}% = {tol:.0f})")
    return issues


def check_cronograma_oficial(root: Path, meta: dict) -> list[str]:
    dk = meta.get("datas_chave", {})
    data_prova = dk.get("prova_data") if isinstance(dk, dict) else None
    if not data_prova:
        return ["INFO: prova_data ausente; pulando check de data"]
    # O .meta.yml (legado) e lido pelo YAML, que converte "2026-05-10" em
    # datetime.date automaticamente; o .meta.json mantem string. Aceita os dois.
    if isinstance(data_prova, datetime):
        prova = data_prova
    elif isinstance(data_prova, date):
        prova = datetime.combine(data_prova, datetime.min.time())
    else:
        try:
            prova = datetime.strptime(str(data_prova), "%Y-%m-%d")
        except ValueError:
            return [f"AVISO: prova_data invalida: {data_prova}"]
    if prova < datetime.now():
        return [f"AVISO: data da prova ({data_prova}) ja passou"]
    return []


def check_previsto(root: Path) -> list[str]:
    """Item 2/6: no modo previsto exige banner e cronograma relativo."""
    issues = []
    crono_dir = None
    for d in root.rglob("02-CRONOGRAMA"):
        crono_dir = d
        break
    if crono_dir:
        if (crono_dir / "cronograma-oficial.md").exists():
            issues.append("MODO PREVISTO: cronograma-oficial.md nao deveria existir")
        if not (crono_dir / "cronograma-relativo.md").exists():
            issues.append("MODO PREVISTO: falta cronograma-relativo.md")
    # banner em ao menos os arquivos de cronograma/mapas
    faltando_banner = []
    for md in root.rglob("*.md"):
        up = str(md).upper()
        if "02-CRONOGRAMA" in up or "03-MAPAS-MATERIAS" in up:
            if not BANNER_RE.search(_read(md)):
                faltando_banner.append(str(md.relative_to(root)))
    if faltando_banner:
        issues.append(f"MODO PREVISTO: banner PROVISORIO ausente em {len(faltando_banner)} arquivo(s): "
                      + ", ".join(faltando_banner[:5]) + ("..." if len(faltando_banner) > 5 else ""))
    return issues


def main():
    ap = argparse.ArgumentParser(description="Valida output da skill concurso-prep")
    ap.add_argument("path", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tolerancia", type=float, default=5.0, help="tolerancia %% da soma de questoes")
    ap.add_argument("--modo", choices=["auto", "oficial", "previsto"], default="auto")
    args = ap.parse_args()

    if not args.path.is_dir():
        sys.stderr.write(f"ERRO: nao e diretorio: {args.path}\n")
        sys.exit(1)

    meta = carregar_meta(args.path)
    modo = detectar_modo(args.path, meta, args.modo)

    results = {
        "estrutura": check_structure(args.path),
        "placeholders": check_placeholders(args.path),
        "wikilinks": check_wikilinks(args.path),
        "soma_questoes": check_soma_questoes(args.path, meta, args.tolerancia),
        "cobertura_mapas": check_cobertura_mapas(args.path, meta),
        "pdfs": check_pdfs(args.path),
    }
    if meta.get("_erro"):
        results["meta"] = [f"ERRO: {meta['_erro']}"]
    if modo == "previsto":
        results["previsto"] = check_previsto(args.path)
    else:
        results["cronograma"] = check_cronograma_oficial(args.path, meta)

    def reais(issues):
        return [i for i in issues if not i.startswith("INFO:")]

    total_issues = sum(len(reais(v)) for v in results.values())

    if args.json:
        print(json.dumps({"modo": modo, "resultados": results,
                          "total_problemas": total_issues}, indent=2, ensure_ascii=False))
    else:
        print(f"=== Validacao ({modo}): {args.path} ===\n")
        for check, issues in results.items():
            r = reais(issues)
            print(f"[{check}] {'OK' if not r else f'{len(r)} issue(s)'}")
            for issue in issues[:10]:
                print(f"  - {issue}")
            if len(issues) > 10:
                print(f"  ... e mais {len(issues) - 10}")
            print()
        print(f"Total: {total_issues} problema(s) real(is) encontrado(s)")

    logs_dir = args.path.parent / ".logs"
    if logs_dir.exists():
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        (logs_dir / f"validacao-{ts}.json").write_text(
            json.dumps({"modo": modo, "resultados": results}, indent=2, ensure_ascii=False),
            encoding="utf-8")

    sys.exit(0 if total_issues == 0 else 1)


if __name__ == "__main__":
    main()
