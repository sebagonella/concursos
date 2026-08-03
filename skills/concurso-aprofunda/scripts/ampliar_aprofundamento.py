#!/usr/bin/env python3
"""
ampliar_aprofundamento.py — acrescenta fonte(s) a um aprofundamento existente.

A identidade de um aprofundamento É o conjunto de fontes, e o id É o path
(ver aprofundamento_id.py). Logo, acrescentar uma fonte é necessariamente
RENOMEAR: `padrao--pestana` -> `padrao--pestana+rosenthal`. Não existe
"adicionar sem mexer no nome".

Dois modos, que só diferem em mover vs. copiar:

  --modo ampliar (padrão)  MOVE. O id antigo deixa de existir; o texto já escrito
                           vira a semente da mescla. Use quando a fonte nova
                           completa/corrige o mesmo material.
  --modo derivar           COPIA. Os dois convivem; o novo nasce semeado. Use
                           quando quiser as duas versões lado a lado — ou quando
                           estiver em dúvida, porque copiar é reversível e mover
                           não é.

Uso:
    # uma pasta
    python ampliar_aprofundamento.py \
        --aprof-dir <.../assuntos/crase/padrao--pestana> \
        --fonte "Gramática para Concursos (Rosenthal)" --dry-run

    # a matéria inteira, todos os assuntos que tenham aquele id
    python ampliar_aprofundamento.py \
        --assuntos-dir <.../lingua-portuguesa/assuntos> \
        --aprofundamento padrao--pestana \
        --fonte "Gramática para Concursos (Rosenthal)" \
        --localizacao "Rosenthal — pp. 210 a 240" --aplicar

O modo em lote não é conveniência: o caso real é a matéria inteira recebendo a
mesma segunda fonte, e 22 invocações são 22 chances de errar um slug.

Segurança:
  - --dry-run é o PADRÃO; nada é escrito sem --aplicar.
  - Nunca sobrescreve pasta de destino existente (CONFLITO).
  - Conjunto de fontes igual em outra ordem é PENDÊNCIA (ver --permitir-permutacao):
    `a+b` e `b+a` seriam dois caminhos para a mesma coisa.
  - Não faz backup, de propósito: MOVE (não sobrescreve), e o único arquivo
    reescrito por cima é o pacote do NotebookLM, cujo backup é do notebooklm_pack
    e só acontece quando o conteúdo muda. Duplicar aqui repetiria o bug do
    fix_notebooklm_packs corrigido na 0.7.0.

Exit codes: 0 ok · 1 erro de uso ou nada encontrado · 2 pendência/conflito.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aprofundamento_id import (  # noqa: E402
    slug, slug_fonte, slug_suspeito, id_aprofundamento, nome_base, parse_id,
    chave_localizacao, localizacoes as aid_localizacoes,
)
from renomear_aprof import (  # noqa: E402
    ler_frontmatter, atualizar_frontmatter, planejar_movimentos, mapa_de_links,
    reescrever_referencias, reescrever_wikilinks_flashcards,
    concurso_do_path, raiz_dos_concursos,
)
from build_subject_md import fmt_paginas  # noqa: E402
import notebooklm_pack as nlp  # noqa: E402

# arquivos que NÃO são copiados numa derivação: apontariam a variante nova para o
# notebook do original, e `executor.garantir_fontes` só ADICIONA fonte — a nota da
# variante acabaria dentro do notebook alheio.
NAO_COPIA_EM_DERIVAR = ("_fonte-notebooklm.md", "_fonte-notebooklm.bak.md",
                        "_notebooklm-estado.json")
PREFIXOS_MIDIA = ("podcast-", "mapa-mental-", "video-", "report-")


def novos_slugs(atuais: list[str], novos: list[str], posicao: str) -> list[str]:
    """Onde a fonte nova entra na ordem — que é significativa e nunca canonicalizada.

    Padrão `fim`: mantém o PREFIXO do id estável (`padrao--a` -> `padrao--a+b`), o
    que deixa a linhagem adjacente numa listagem alfabética da pasta do assunto. E
    espelha a cronologia real: a fonte 1 é de onde o texto foi escrito, a nova
    completa.
    """
    if posicao == "fim":
        return atuais + novos
    if posicao == "inicio":
        return novos + atuais
    n = int(posicao)
    return atuais[:n] + novos + atuais[n:]


def _midias(origem: Path) -> list[str]:
    return sorted(p.name for p in origem.iterdir()
                  if p.is_file() and p.name.startswith(PREFIXOS_MIDIA))


def localizacao_do_mapa(assunto_slug: str, mapas: list[dict]) -> list[str]:
    """Ponteiro de cada fonte nova PARA ESTE ASSUNTO, no formato do frontmatter.

    Casa pelo slug do título, que é como `build_subject_md.py` nomeia a pasta.
    Assunto ausente do mapa devolve lista curta — e o chamador transforma isso em
    pendência, em vez de gravar a página de outro assunto.
    """
    out = []
    for m in mapas:
        alvo = next((loc for titulo, loc in (m.get("localizacoes") or {}).items()
                     if slug(titulo) == assunto_slug), None)
        if not alvo or alvo.get("confianca") in (None, "nao_encontrado"):
            break                      # contíguo: sem a fonte i não há como ter a i+1
        out.append(f'{m.get("livro", "")} — págs. {fmt_paginas(alvo)}')
    return out


def planejar(aprof_dir: Path, *, fontes: list[str], slugs: list[str],
             localizacoes: list[str], posicao: str, modo: str, concurso: str,
             permitir_permutacao: bool, copiar_midias: bool) -> dict:
    """Monta o item de relatório para UMA pasta de aprofundamento. Não escreve nada."""
    assunto_dir = aprof_dir.parent
    item = {"assunto": assunto_dir.name, "de": aprof_dir.name, "modo": modo.upper()}

    info = parse_id(aprof_dir.name)
    if not info:
        return {**item, "status": "PENDENCIA",
                "motivos": [f"{aprof_dir.name!r} não é uma pasta de aprofundamento"]}

    md = nlp.arquivo_principal(aprof_dir)
    if md is None:
        return {**item, "status": "PENDENCIA",
                "motivos": ["pasta sem .md principal — nada a ampliar"]}

    atuais = list(info["fontes"])
    ja_tem = [s for s in slugs if s in atuais]
    if ja_tem:
        return {**item, "status": "PENDENCIA",
                "motivos": [f"a(s) fonte(s) {ja_tem} já estão neste aprofundamento"]}

    alvo = novos_slugs(atuais, slugs, posicao)
    novo_id = id_aprofundamento(fontes, info["nivel"], fontes_slug=alvo)
    destino = assunto_dir / novo_id
    item.update(para=novo_id, fontes_id=alvo)

    if destino.exists():
        return {**item, "status": "CONFLITO",
                "motivos": [f"pasta de destino já existe: {novo_id}"]}

    # permutação: mesmo conjunto, outra ordem. Dois caminhos para a mesma coisa.
    if not permitir_permutacao:
        for irma in sorted(p for p in assunto_dir.iterdir() if p.is_dir()):
            outra = parse_id(irma.name)
            if (outra and outra["nivel"] == info["nivel"]
                    and set(outra["fontes"]) == set(alvo) and list(outra["fontes"]) != alvo):
                return {**item, "status": "PENDENCIA", "motivos": [
                    f"já existe aprofundamento com as mesmas fontes em outra ordem: "
                    f"{irma.name}; ampliar criaria dois caminhos para o mesmo conjunto "
                    f"(use --permitir-permutacao se for de propósito)"]}

    fm = ler_frontmatter(md)
    conc = concurso or fm.get("concurso", "") or concurso_do_path(aprof_dir)
    base_novo = nome_base(assunto_dir.name, novo_id, conc)
    idx = alvo.index(slugs[0])          # onde a primeira fonte nova ficou

    movimentos = planejar_movimentos(aprof_dir, md, base_novo)
    if modo == "derivar":
        movimentos = [(p, n) for p, n in movimentos
                      if p.name not in NAO_COPIA_EM_DERIVAR
                      and (copiar_midias or not p.name.startswith(PREFIXOS_MIDIA))]

    midias = _midias(aprof_dir)
    avisos, pendencias = [], []

    locs_atuais = aid_localizacoes(fm)
    if len(localizacoes) < len(fontes):
        pendencias.append(
            f"fonte(s) {slugs[len(localizacoes):]} sem --localizacao: entram sem "
            f"ponteiro de página. A Etapa 5 precisa localizá-las no livro ou "
            f"registrar a pendência — nunca inventar página.")
    # inserir no meio deslocaria as localizações já gravadas; sem os ponteiros das
    # fontes novas isso abriria um buraco que localizacoes() leria como fim da lista
    escreve_loc = bool(localizacoes)
    if escreve_loc and idx < len(locs_atuais):
        escreve_loc = False
        pendencias.append(
            f"a fonte nova entra na posição {idx}, antes de localizações já gravadas: "
            f"reordená-las automaticamente arriscaria perder ponteiro. As chaves "
            f"localizacao_* ficam como estão — ajuste à mão depois.")
    elif escreve_loc and idx > len(locs_atuais):
        escreve_loc = False
        pendencias.append(
            f"o aprofundamento tem {len(atuais)} fonte(s) no id mas só "
            f"{len(locs_atuais)} localização(ões); gravar na posição {idx} deixaria "
            f"buraco. Complete as localizações que faltam antes de ampliar.")

    if modo == "ampliar":
        pack = nlp.ler_frontmatter(aprof_dir / "_fonte-notebooklm.md") \
            if (aprof_dir / "_fonte-notebooklm.md").exists() else {}
        if pack.get("notebooklm_url") or pack.get("notebooklm_id"):
            pendencias.append(
                f"o notebook já criado ({pack.get('notebooklm_url') or pack.get('notebooklm_id')}) "
                f"contém a nota {md.name!r}, que deixa de existir. garantir_fontes() só "
                f"ADICIONA fonte, nunca remove — apague a nota antiga no NotebookLM antes "
                f"de gerar de novo, ou o modelo verá duas versões do mesmo assunto.")
        if midias:
            avisos.append(
                f"mídia gerada com o conjunto de fontes antigo: {midias}. Renomeada junto "
                f"(senão o pacote regeraria e queimaria quota), e marcada como obsoleta "
                f"no pacote.")

    return {**item, "status": "AMPLIAR" if modo == "ampliar" else "DERIVAR",
            "nivel": info["nivel"], "concurso": conc, "base_novo": base_novo,
            "indice_insercao": idx if escreve_loc else -1,
            "localizacoes": localizacoes if escreve_loc else [],
            "origem": str(aprof_dir), "destino": str(destino),
            "movimentos": [{"de": str(p), "para": n} for p, n in movimentos],
            "midias": midias,
            **({"avisos": avisos} if avisos else {}),
            **({"pendencias": pendencias} if pendencias else {})}


def executar(item: dict, *, fontes: list[str],
             manter_status: bool, materia: str, tpl: str) -> None:
    """Aplica UM item já planejado. Move/copia, corrige frontmatter, regenera o pack."""
    modo = item["modo"].lower()
    origem, destino = Path(item["origem"]), Path(item["destino"])
    assunto_dir = destino.parent
    destino.mkdir(parents=True, exist_ok=True)

    for mov in item["movimentos"]:
        de, para = Path(mov["de"]), destino / mov["para"]
        if modo == "ampliar":
            shutil.move(str(de), str(para))
        else:
            shutil.copy2(de, para)

    # Marca de obsolescência ANTES de regerar: herdar_campos() herda por prefixo
    # `notebooklm_`, então o aviso sobrevive a esta e a toda regeração futura.
    pack = destino / "_fonte-notebooklm.md"
    if modo == "ampliar" and pack.exists():
        marcas = {}
        # a nota antiga é a que virou `{base_novo}.md`, não a primeira em ordem
        # alfabética (que é sempre o próprio `_fonte-notebooklm.md`)
        antiga = next((Path(m["de"]).name for m in item["movimentos"]
                       if m["para"] == f"{item['base_novo']}.md"), "")
        for p in item.get("pendencias", []):
            if "notebook já criado" in p and antiga:
                marcas["notebooklm_fonte_obsoleta"] = antiga
        if item.get("midias"):
            marcas["notebooklm_midias_obsoletas"] = ", ".join(
                n.split("-")[0] for n in item["midias"])
        if marcas:
            pack.write_text(atualizar_frontmatter(pack.read_text(encoding="utf-8"), marcas),
                            encoding="utf-8")

    # frontmatter do .md principal ganha a identidade nova
    alvo = destino / f"{item['base_novo']}.md"
    txt = alvo.read_text(encoding="utf-8")
    fm = ler_frontmatter(alvo)
    fontes_antigas = [f.strip() for f in (fm.get("fontes") or "").split(",") if f.strip()]
    novos_campos = {
        "aprofundamento": item["para"],
        "fontes": ", ".join(fontes_antigas + fontes),
    }
    # Os ponteiros da fonte nova entram em localizacao_2..N; a fonte 1 continua em
    # `localizacao_livro`, para os leitores antigos não perderem nada.
    #
    # O índice sai do ID, nunca do campo `fontes:` — que no vault tem dois formatos
    # incompatíveis e às vezes conta errado. E só se escreve quando a inserção é no
    # FIM e não há buraco: inserir no meio deslocaria as localizações existentes, e
    # fazer isso sem os ponteiros das fontes novas criaria um buraco que
    # `localizacoes()` (que para no primeiro) leria como "acabou" — perdendo em
    # silêncio o ponteiro que já existia.
    if item["indice_insercao"] >= 0:
        for i, loc in enumerate(item["localizacoes"]):
            novos_campos[chave_localizacao(item["indice_insercao"] + i)] = loc
    if not manter_status:
        # declarar-se concluído antes da mescla é afirmação falsa que o site publica
        novos_campos["status"] = "revisar"
    if modo == "derivar":
        novos_campos["derivado_de"] = item["de"]
    txt = atualizar_frontmatter(txt, novos_campos)
    txt = reescrever_wikilinks_flashcards(txt, item["base_novo"])
    alvo.write_text(txt, encoding="utf-8")

    # o pacote inteiro (nome do notebook, arquivo_*, lista de fontes, prompts) sai do
    # GERADOR, com o nome-base novo. O ampliador nunca o escreve na mão.
    nlp.gerar_para_pasta(destino, assunto_dir, concurso=item["concurso"],
                         materia=materia, tpl=tpl)

    if modo == "ampliar" and origem.is_dir() and not any(origem.iterdir()):
        origem.rmdir()


def main():
    ap = argparse.ArgumentParser(
        description="Acrescenta fonte(s) a um aprofundamento existente (renomeia).")
    ap.add_argument("--aprof-dir", type=Path,
                    help="uma pasta de aprofundamento (.../assuntos/{assunto}/{nivel}--{f})")
    ap.add_argument("--assuntos-dir", type=Path,
                    help="a pasta 'assuntos/' da matéria, para o modo em lote")
    ap.add_argument("--aprofundamento", default="",
                    help="id de origem a procurar em cada assunto (ex.: padrao--pestana)")
    ap.add_argument("--fonte", action="append", default=[],
                    help="nome da fonte a acrescentar (repetível)")
    ap.add_argument("--fonte-slug", action="append", default=[],
                    help="slug explícito da fonte (repetível, casa em ordem com --fonte)")
    ap.add_argument("--localizacao", action="append", default=[],
                    help="ponteiro de página da fonte nova (repetível, casa em ordem). "
                         "MESMO valor para todos os alvos — no modo em lote prefira --mapa.")
    ap.add_argument("--mapa", type=Path, action="append", default=[],
                    help="mapa-localizacao.json da fonte nova (repetível, casa em ordem "
                         "com --fonte). No modo em lote é o caminho certo: o ponteiro é "
                         "POR ASSUNTO, e um --localizacao só gravaria a mesma página em "
                         "todos. Assunto ausente do mapa fica sem ponteiro e vira "
                         "pendência — nunca página inventada.")
    ap.add_argument("--posicao", default="fim",
                    help="onde a fonte entra na ordem: fim (padrão) | inicio | <n>")
    ap.add_argument("--modo", choices=("ampliar", "derivar"), default="ampliar")
    ap.add_argument("--concurso", default="", help="default: derivado do path")
    ap.add_argument("--materia", default="")
    ap.add_argument("--raiz-links", type=Path, default=None,
                    help="raiz para reescrever wikilink (default: a pasta CONCURSOS acima)")
    ap.add_argument("--copiar-midias", action="store_true",
                    help="no modo derivar, copia também as mídias já geradas")
    ap.add_argument("--manter-status", action="store_true",
                    help="não rebaixa `status` para 'revisar'")
    ap.add_argument("--permitir-permutacao", action="store_true")
    ap.add_argument("--template", type=Path,
                    default=Path(__file__).resolve().parents[1] / "assets/templates/fonte-notebooklm.md.tpl")
    ap.add_argument("--aplicar", action="store_true", help="executa (sem isto, é dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="(padrão) não escreve nada")
    args = ap.parse_args()

    if not args.aprof_dir and not args.assuntos_dir:
        sys.exit("erro: informe --aprof-dir ou --assuntos-dir")
    if args.assuntos_dir and not args.aprofundamento:
        sys.exit("erro: --assuntos-dir exige --aprofundamento (qual id ampliar)")
    if not args.fonte:
        sys.exit("erro: informe ao menos um --fonte")
    if args.fonte_slug and len(args.fonte_slug) != len(args.fonte):
        sys.exit(f"erro: --fonte-slug tem {len(args.fonte_slug)} item(ns) e --fonte tem "
                 f"{len(args.fonte)}; devem casar em número e ordem.")
    if args.mapa and len(args.mapa) != len(args.fonte):
        sys.exit(f"erro: --mapa foi passado {len(args.mapa)} vez(es) e --fonte tem "
                 f"{len(args.fonte)}; devem casar em número e ordem.")
    if args.mapa and args.localizacao:
        sys.exit("erro: use --mapa OU --localizacao, não os dois — teriam de concordar\n       e não há como saber qual vale.")
    if len(args.localizacao) > len(args.fonte):
        sys.exit(f"erro: --localizacao tem {len(args.localizacao)} item(ns), mais que os "
                 f"{len(args.fonte)} de --fonte.")
    aplicar = args.aplicar and not args.dry_run

    # Os slugs derivados são SEMPRE ecoados, não só quando suspeitos: um nome de
    # arquivo corrompido produz slug plausível e errado (`indleycintra` de um PDF do
    # Cunha & Cintra) que slug_suspeito() não acusa, e o erro só apareceria depois de
    # a pasta já existir.
    slugs, avisos_slug = [], []
    for i, f in enumerate(args.fonte):
        s = slug(args.fonte_slug[i]) if args.fonte_slug else slug_fonte(f)
        if slug_suspeito(s):
            sys.exit(f"erro: slug {s!r} derivado de {f!r} não identifica a fonte; "
                     f"passe --fonte-slug explicitamente.")
        slugs.append(s)
        avisos_slug.append(f"{f!r} -> {s!r}")

    if args.aprof_dir:
        alvos = [args.aprof_dir]
    else:
        alvos = sorted(
            p / args.aprofundamento
            for p in args.assuntos_dir.iterdir()
            if p.is_dir() and (p / args.aprofundamento).is_dir())

    if not alvos:
        # sair 0 sem achar nada foi o que escondeu a migração que não rodou
        print(json.dumps({"erro": "nenhum aprofundamento encontrado",
                          "procurado": args.aprofundamento or str(args.aprof_dir)},
                         indent=2, ensure_ascii=False))
        sys.exit(1)

    mapas = [json.loads(m.read_text(encoding='utf-8')) for m in args.mapa]
    itens = [planejar(a, fontes=args.fonte, slugs=slugs,
                      # o ponteiro é POR ASSUNTO: o mapa manda, --localizacao é o
                      # atalho de uma pasta só
                      localizacoes=(localizacao_do_mapa(a.parent.name, mapas)
                                    if mapas else args.localizacao),
                      posicao=args.posicao, modo=args.modo, concurso=args.concurso,
                      permitir_permutacao=args.permitir_permutacao,
                      copiar_midias=args.copiar_midias)
             for a in alvos]

    ok = [i for i in itens if i["status"] in ("AMPLIAR", "DERIVAR")]
    mapa_links = {}
    for i in ok:
        # numa derivação o original continua existindo: o wikilink de fora ainda
        # resolve, e reescrevê-lo mandaria o índice para a cópia
        if i["modo"] == "AMPLIAR":
            mapa_links.update(mapa_de_links(
                [(m["de"], m["para"]) for m in i["movimentos"]], i["para"]))

    if aplicar:
        tpl = args.template.read_text(encoding="utf-8")
        for i in ok:
            executar(i, fontes=args.fonte,
                     manter_status=args.manter_status, materia=args.materia, tpl=tpl)

    raiz = args.raiz_links or raiz_dos_concursos(alvos[0]) or alvos[0].parents[2]
    links = reescrever_referencias(raiz, mapa_links, aplicar) if mapa_links else []

    resumo = {}
    for i in itens:
        resumo[i["status"]] = resumo.get(i["status"], 0) + 1
    print(json.dumps({
        "modo": args.modo.upper(),
        "execucao": "APLICADO" if aplicar else "DRY-RUN (nada escrito)",
        "slugs_derivados": avisos_slug,
        "raiz_links": str(raiz),
        "resumo": resumo,
        "links_reescritos": {"arquivos": len(links), "detalhe": links},
        "itens": itens,
    }, indent=2, ensure_ascii=False))
    sys.exit(2 if any(i["status"] in ("PENDENCIA", "CONFLITO") or i.get("pendencias")
                      for i in itens) else 0)


if __name__ == "__main__":
    main()
