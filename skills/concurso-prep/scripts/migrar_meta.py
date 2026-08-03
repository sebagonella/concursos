#!/usr/bin/env python3
"""
migrar_meta.py — completa o `.meta.json` de um concurso já gerado. (v1.0.0)

Os concursos do vault foram gerados antes do contrato da 1.6.0 e do diff por cargo
da 1.7.0. O que falta neles é quase todo **metadado** — e metadado se corrige
cirurgicamente, sem reexecutar a skill e sem tocar na prosa dos mapas, que é onde
mora o trabalho humano.

O que este script completa, e de onde tira cada coisa:

  cargos_validados[]        <- `cargos_multi` (SEDES) ou `cargos_gerados` (BB)
  estrutura_prova_por_cargo <- `cargos_multi[].titulos`/`.discursiva`
  edital_hash               <- recalculado do TEXTO, por edital_hash.py
  materias[].cargos_ids     <- `materias_por_cargo` (SEDES) ou
                               `cargos_gerados[].especificos` (BB)
  materias[] faltantes      <- Anexo III do edital, CONFERIDO contra os mapas

Disciplina, a mesma dos outros migradores do repo:
  - **dry-run é o padrão**; só escreve com `--aplicar`
  - backup `.meta.json.bak` antes de escrever
  - **nunca escolhe no palpite**: o que não for derivável com segurança vira
    pendência, e pendência sem `--forcar` impede a escrita
  - **duas fontes** para conteúdo programático: o edital e o mapa. Divergiram,
    é pendência — não se escolhe uma das duas no palpite
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import edital_hash as eh  # noqa: E402

PASTAS_MAPA = ("03-MAPAS-MATERIAS", "03-MAPAS-COMUNS")
# Marcador do escopo `_COMUM`: "mais de um cargo", sem dizer quais.
COMUM = "*"


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


# --------------------------------------------------------------------------- #
# cargos_validados
# --------------------------------------------------------------------------- #
def nomes_do_vault(pasta: Path) -> dict[str, str]:
    """Nome legível do cargo, garimpado no H1 do 99-Status.md — como PROPOSTA.

    Não é fonte confiável: no SEDES, o do AGENTE-SOCIAL nem nomeia o cargo. Serve
    para sugerir, nunca para decidir.
    """
    achados = {}
    for status in pasta.glob("*/99-Status.md"):
        m = re.search(r"^#\s+(.+)$", status.read_text(encoding="utf-8"), re.M)
        if not m:
            continue
        titulo = re.sub(r"^[^A-Za-zÀ-ÿ]+", "", m.group(1)).strip()
        titulo = re.sub(r"^Status(\s+da\s+Preparação)?\s*[—-]\s*", "", titulo).strip()
        if titulo and not re.match(r"^Sedes|^Status", titulo, re.I):
            achados[status.parent.name] = titulo
    return achados


def corr_cargos_validados(meta: dict, pasta: Path) -> tuple[list | None, list[str]]:
    if meta.get("cargos_validados"):
        return None, []
    pend, saida = [], []
    sugestoes = nomes_do_vault(pasta)

    for c in meta.get("cargos_multi") or []:
        sigla = c.get("sigla")
        nome = (meta.get("cargo", {}).get("nome_completo")
                if meta.get("cargo", {}).get("sigla") == sigla else None)
        if not nome:
            nome = sugestoes.get(sigla)
            if nome:
                pend.append(f"cargos_validados[{sigla}].nome_completo proposto a "
                            f"partir do 99-Status.md: {nome!r} — confirme")
            else:
                pend.append(f"cargos_validados[{sigla}].nome_completo NAO derivavel "
                            f"do meta nem do vault — preencha a mao")
                nome = ""
        saida.append({"nome_completo": nome, "sigla": sigla,
                      "codigo": c.get("codigo"),
                      "vagas_total": c.get("vagas_total"),
                      "salario": c.get("remuneracao")})

    for c in meta.get("cargos_gerados") or []:
        saida.append({"nome_completo": c.get("nome_completo", ""),
                      "sigla": c.get("slug"), "codigo": None,
                      "vagas_total": None, "salario": None})

    return (saida or None), pend


# --------------------------------------------------------------------------- #
# estrutura_prova_por_cargo
# --------------------------------------------------------------------------- #
def corr_estrutura_por_cargo(meta: dict) -> tuple[dict | None, list[str]]:
    """Títulos e discursiva variam POR CARGO — e o meta agregado mentia.

    No SEDES, `titulos.presente: false` com a ressalva em prosa era falso para o
    ASSISTENTE-SOCIAL, que é EDAS e tem títulos. O dado certo já estava em
    `cargos_multi[].titulos`; ninguém o consumia.
    """
    if meta.get("estrutura_prova_por_cargo"):
        return None, []
    multi = meta.get("cargos_multi") or []
    if not multi:
        return None, []
    saida = {}
    for c in multi:
        sigla = c.get("sigla")
        if not sigla:
            continue
        saida[sigla] = {
            "titulos": {"presente": bool(c.get("titulos"))},
            "discursiva": {"presente": bool(c.get("discursiva")),
                           "tipo": c.get("discursiva") or None},
        }
    divergem = len({json.dumps(v, sort_keys=True) for v in saida.values()}) > 1
    if not divergem:
        return None, []
    return saida, []


# --------------------------------------------------------------------------- #
# edital_hash
# --------------------------------------------------------------------------- #
def corr_edital_hash(meta: dict, pasta: Path) -> tuple[dict | None, list[str]]:
    editais = sorted((pasta / "_COMUM" / "01-EDITAL").glob("edital-*.pdf"))
    if not editais:
        return None, ["edital_hash: nenhum edital-*.pdf em _COMUM/01-EDITAL"]
    try:
        h = eh.hashes_do_edital(editais[0])
    except SystemExit:
        return None, [f"edital_hash: nao foi possivel extrair texto de {editais[0].name}"]
    atual = meta.get("edital_hash")
    if atual == h["edital_hash"]:
        return None, []
    novo = {"edital_hash": h["edital_hash"],
            "edital_pdf_sha256": h["edital_pdf_sha256"]}
    pend = []
    if atual and atual == h["edital_pdf_sha256"]:
        pend.append("edital_hash gravado era o hash dos BYTES do PDF (convencao "
                    "anterior a 1.7.0); sera trocado pelo hash do TEXTO")
    return novo, pend


# --------------------------------------------------------------------------- #
# materias[].cargos_ids
# --------------------------------------------------------------------------- #
def escopo_pelo_vault(pasta: Path) -> dict[str, set[str]]:
    """{materia_id_ou_slug: {cargos}} pelo LUGAR onde o mapa está.

    Não decide nada — serve de segunda fonte para conferir o que o meta diz.
    """
    cargos = {d.name for d in pasta.iterdir()
              if d.is_dir() and not d.name.startswith((".", "_"))}
    achado: dict[str, set[str]] = {}
    for sub in PASTAS_MAPA:
        for md in pasta.glob(f"*/{sub}/*.md"):
            if re.match(r"^(00-INDICE|99-Status)", md.stem, re.I):
                continue
            fm = re.match(r"^---\s*\n(.*?)\n---", md.read_text(encoding="utf-8"), re.S)
            mid = None
            if fm:
                m = re.search(r"^materia_id:\s*(\S+)", fm.group(1), re.M)
                mid = m.group(1).strip() if m else None
            mid = mid or re.sub(r"^\d{2}[-_ ]+", "", md.stem)
            escopo = md.relative_to(pasta).parts[0]
            # `_COMUM` significa "mais de um cargo", NÃO "todos": a etapa dos mapas manda
            # gravar ali também a matéria que vale para 2 de 3 cargos, declarando a
            # aplicabilidade no índice. Tratar como "todos" fazia o cross-check
            # acusar falso alarme no `fundamentos-suas` do SEDES, que é só do TDAS.
            achado.setdefault(mid, set()).update(
                {COMUM} if escopo == "_COMUM" else {escopo})
    return achado


def corr_cargos_ids(meta: dict, pasta: Path) -> tuple[list | None, list[str]]:
    materias = meta.get("materias") or []
    if not materias:
        return None, []
    falta = [m for m in materias
             if not m.get("cargos_ids")
             or m.get("tipo") not in ("gerais", "especificos_comuns", "especificos_cargo")]
    if not falta:
        return None, []

    todos = [c.get("sigla") or c.get("slug")
             for c in (meta.get("cargos_multi") or meta.get("cargos_gerados") or [])]
    todos = [c for c in todos if c]

    # De onde vem o escopo, por concurso
    por_nome: dict[str, set[str]] = {}
    for cargo, lista in (meta.get("materias_por_cargo") or {}).items():
        for m in lista or []:
            por_nome.setdefault(normalizar(m.get("nome")), set()).add(cargo)
    especificas: dict[str, set[str]] = {}
    for c in meta.get("cargos_gerados") or []:
        for e in c.get("especificos") or []:
            especificas.setdefault(normalizar(e.get("nome")), set()).add(c.get("slug"))

    vault = {normalizar(k): v for k, v in escopo_pelo_vault(pasta).items()}
    saida, pend = [], []
    for m in materias:
        novo = dict(m)
        chave = normalizar(m.get("nome"))
        if chave in por_nome:
            cargos = sorted(por_nome[chave])
        elif chave in especificas:
            cargos = sorted(especificas[chave])
        elif especificas:
            cargos = sorted(todos)          # básica: vale para todos os cargos
        else:
            pend.append(f"materia {m.get('nome')!r}: escopo nao derivavel do meta")
            saida.append(novo)
            continue

        # Segunda fonte: onde o mapa mora. Divergiu, é pendência.
        mid = normalizar(m.get("materia_id") or "")
        do_vault = vault.get(mid) or vault.get(chave)
        if do_vault:
            if COMUM in do_vault:
                # mapa em _COMUM: exige mais de um cargo, não um conjunto exato
                if len(cargos) < 2:
                    pend.append(f"materia {m.get('nome')!r}: o mapa esta em _COMUM "
                                f"mas o meta da so {cargos} — confira")
            elif set(cargos) != do_vault:
                pend.append(
                    f"materia {m.get('nome')!r}: meta diz {sorted(cargos)} e o mapa "
                    f"mora em {sorted(do_vault)} — confira antes de gravar")
        novo["cargos_ids"] = cargos
        novo["tipo"] = normalizar_tipo(novo.get("tipo", ""), len(cargos))
        saida.append(novo)
    return saida, pend


# --------------------------------------------------------------------------- #
# matérias que faltam no meta (existem como mapa, não existem no conteúdo)
# --------------------------------------------------------------------------- #
def limpar_texto_pdf(texto: str) -> str:
    """Tira o rodape de pagina do texto do pdftotext.

    O numero da pagina vem numa linha propria logo antes do form feed, e ao juntar
    as linhas ele entra NO MEIO do topico: o item 1 de Conhecimentos de Informatica
    saia com "ambiente Linux (SUSE 34 SLES 15 SP2)". Numero de pagina no meio do
    conteudo programatico e' lixo que ninguem revisa depois.
    """
    texto = re.sub(r"\n[ \t]*\d{1,3}[ \t]*\n*\f", "\n", texto)
    return texto.replace("\f", "\n")


def topicos_do_edital(texto: str, nome: str) -> list[str]:
    """Bloco `NOME: 1 - ... 2 - ...` do anexo de conteúdo programático."""
    texto = limpar_texto_pdf(texto)
    alvo = re.escape(nome.upper())
    # A secao termina na proxima materia (NOME:) OU num cabecalho de anexo. Sem o
    # segundo caso, o ultimo topico de "Vendas e Negociacao" engolia "ANEXO IV -
    # CRONOGRAMA", porque o anexo usa travessao e nao dois-pontos.
    fim = r"(?=^\s*[A-ZÀ-Ý][A-ZÀ-Ý \-]{6,}\s*:|^\s*ANEXO\s+[IVXLC]+\b|\Z)"
    m = re.search(rf"^\s*{alvo}\s*:\s*(.+?){fim}", texto, re.M | re.S)
    if not m:
        return []
    corpo = re.sub(r"\s+", " ", m.group(1)).strip()
    partes = re.split(r"(?:(?<=\.)|\s)\s*(\d{1,2})\s*[-–.]\s+", " " + corpo)
    itens = []
    for i in range(1, len(partes) - 1, 2):
        num, txt = partes[i], partes[i + 1].strip()
        if txt:
            itens.append(f"{num} - {txt}")
    return itens


def materia_id_do_mapa(pasta: Path, nome: str) -> str | None:
    """O `materia_id` da matéria, lido do mapa que já existe no vault.

    Matéria nova sem `materia_id` é matéria que não se liga a aprofundamento nem ao
    site — o campo é o vínculo. Derivar do nome seria re-derivar identidade, que é
    justamente o que o ADR proíbe; o mapa já declara a dela, então é de lá que sai.
    """
    alvo = normalizar(nome)
    for sub in PASTAS_MAPA:
        for md in pasta.glob(f"*/{sub}/*.md"):
            if alvo != normalizar(re.sub(r"^\d{2}[-_ ]+", "", md.stem)):
                continue
            fm = re.match(r"^---\s*\n(.*?)\n---", md.read_text(encoding="utf-8"), re.S)
            if fm:
                m = re.search(r"^materia_id:\s*(\S+)", fm.group(1), re.M)
                if m:
                    return m.group(1).strip()
            return re.sub(r"^\d{2}[-_ ]+", "", md.stem)
    return None


def normalizar_tipo(tipo: str, n_cargos: int) -> str:
    """`especificos` e vocabulario legado; o schema so conhece tres valores."""
    if tipo in ("gerais", "especificos_comuns", "especificos_cargo"):
        return tipo
    if tipo in ("especificos", "especifico", None, ""):
        return "especificos_comuns" if n_cargos > 1 else "especificos_cargo"
    return tipo


def topicos_do_mapa(pasta: Path, nome: str) -> list[str]:
    alvo = normalizar(nome)
    for md in list(pasta.glob(f"*/{PASTAS_MAPA[0]}/*.md")) + \
            list(pasta.glob(f"*/{PASTAS_MAPA[1]}/*.md")):
        if alvo not in normalizar(md.stem) and alvo not in normalizar(
                md.read_text(encoding="utf-8")[:400]):
            continue
        txt = md.read_text(encoding="utf-8")
        return [re.sub(r"\s+", " ", b).strip(" >")
                for b in re.findall(r"### Tópicos do edital \(literais\)\s*\n((?:>.*\n?)+)", txt)]
    return []


def corr_materias_faltantes(meta: dict, pasta: Path) -> tuple[list | None, list[str]]:
    materias = meta.get("materias") or []
    conhecidas = {normalizar(m.get("nome")) for m in materias}
    faltando: dict[str, set[str]] = {}
    for c in meta.get("cargos_gerados") or []:
        for e in c.get("especificos") or []:
            if normalizar(e.get("nome")) not in conhecidas:
                faltando.setdefault(e["nome"], set()).add(c.get("slug"))
    if not faltando:
        return None, []

    editais = sorted((pasta / "_COMUM" / "01-EDITAL").glob("edital-*.pdf"))
    if not editais:
        return None, [f"{len(faltando)} materia(s) fora do meta e nenhum edital para extrair"]
    try:
        texto = subprocess.run(["pdftotext", "-layout", str(editais[0]), "-"],
                               capture_output=True, text=True, check=True).stdout
    except Exception as e:
        return None, [f"nao foi possivel ler o edital: {e}"]

    novas, pend = [], []
    for nome, cargos in sorted(faltando.items()):
        do_edital = topicos_do_edital(texto, nome)
        do_mapa = topicos_do_mapa(pasta, nome)
        if not do_edital:
            pend.append(f"materia {nome!r}: nao encontrada no anexo do edital")
            continue
        # Duas fontes: o edital manda, o mapa confere a CONTAGEM. Divergiu, avisa.
        if not do_mapa:
            # Segunda fonte ausente NAO pode virar silencio: sem ela, ninguem
            # confere o que sai do PDF. E a mesma armadilha do check que "passava"
            # por nao encontrar nada.
            pend.append(f"materia {nome!r}: extraida do edital ({len(do_edital)} "
                        f"topicos) mas SEM mapa para conferir — revise a mao")
        elif len(do_mapa) != len(do_edital):
            pend.append(f"materia {nome!r}: o edital tem {len(do_edital)} topicos e o "
                        f"mapa lista {len(do_mapa)} — confira antes de gravar")
        mid = materia_id_do_mapa(pasta, nome)
        if not mid:
            pend.append(f"materia {nome!r}: sem mapa de onde tirar o materia_id — "
                        f"sem ele a materia nao se liga ao aprofundamento nem ao site")
            continue
        novas.append({"nome": nome, "materia_id": mid,
                      "tipo": "especificos_cargo",
                      "subitem_edital": "Anexo III", "topicos": do_edital,
                      "cargos_ids": sorted(cargos), "questoes": None,
                      "origem": "migrar_meta: extraido do anexo do edital"})
    return (novas or None), pend


# --------------------------------------------------------------------------- #
def analisar(pasta: Path) -> dict:
    meta = json.loads((pasta / ".meta.json").read_text(encoding="utf-8"))
    mudancas, pendencias = {}, []

    cv, p = corr_cargos_validados(meta, pasta)
    pendencias += p
    if cv:
        mudancas["cargos_validados"] = cv

    ec, p = corr_estrutura_por_cargo(meta)
    pendencias += p
    if ec:
        mudancas["estrutura_prova_por_cargo"] = ec

    hs, p = corr_edital_hash(meta, pasta)
    pendencias += p
    if hs:
        mudancas.update(hs)

    novas, p = corr_materias_faltantes(meta, pasta)
    pendencias += p
    if novas:
        meta = dict(meta, materias=(meta.get("materias") or []) + novas)
        mudancas["_materias_novas"] = [m["nome"] for m in novas]

    ids, p = corr_cargos_ids(meta, pasta)
    pendencias += p
    if ids:
        mudancas["materias"] = ids

    return {"meta": meta, "mudancas": mudancas, "pendencias": pendencias}


def main():
    ap = argparse.ArgumentParser(
        description="Completa o .meta.json de um concurso já gerado")
    ap.add_argument("pasta", type=Path)
    ap.add_argument("--aplicar", action="store_true",
                    help="escreve (o padrão é dry-run)")
    ap.add_argument("--forcar", action="store_true",
                    help="escreve mesmo havendo pendência — evite")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not (args.pasta / ".meta.json").exists():
        sys.stderr.write(f"ERRO: sem .meta.json em {args.pasta}\n")
        sys.exit(1)

    r = analisar(args.pasta)
    if args.json:
        print(json.dumps({"mudancas": {k: v for k, v in r["mudancas"].items()},
                          "pendencias": r["pendencias"]}, indent=2, ensure_ascii=False))
    else:
        print(f"=== {args.pasta.name} ===\n")
        if not r["mudancas"]:
            print("Nada a corrigir.")
        for k, v in r["mudancas"].items():
            if k == "materias":
                com = sum(1 for m in v if m.get("cargos_ids"))
                print(f"  materias[].cargos_ids: preenchido em {com}/{len(v)}")
            elif k == "_materias_novas":
                print(f"  materias[] novas: {', '.join(v)}")
            elif k == "cargos_validados":
                print(f"  cargos_validados: {len(v)} cargo(s) — "
                      f"{', '.join(c['sigla'] for c in v)}")
            elif k == "estrutura_prova_por_cargo":
                t = [s for s, e in v.items() if e['titulos']['presente']]
                print(f"  estrutura_prova_por_cargo: {len(v)} cargo(s); "
                      f"titulos para {t or 'nenhum'}")
            else:
                print(f"  {k}: {str(v)[:60]}")
        if r["pendencias"]:
            print(f"\n⚠️  {len(r['pendencias'])} pendencia(s):")
            for p in r["pendencias"]:
                print(f"  - {p}")

    if not args.aplicar:
        if not args.json:
            print("\n(dry-run — nada foi escrito; use --aplicar)")
        sys.exit(0)

    if r["pendencias"] and not args.forcar:
        sys.stderr.write("\nERRO: ha pendencia. Resolva ou use --forcar.\n")
        sys.exit(2)

    novo = dict(r["meta"])
    for k, v in r["mudancas"].items():
        if not k.startswith("_"):
            novo[k] = v
    destino = args.pasta / ".meta.json"
    (args.pasta / ".meta.json.bak").write_text(
        destino.read_text(encoding="utf-8"), encoding="utf-8")
    destino.write_text(json.dumps(novo, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(f"\n✅ Gravado. Backup em {destino.name}.bak")


if __name__ == "__main__":
    main()
