#!/usr/bin/env python3
"""
build_subject_md.py - Subsistema B da skill concurso-aprofunda.

A partir do mapa de localização (saída do book_index.py) e do template de
assunto, gera o ARCABOUÇO de um arquivo .md por assunto no vault, no Modelo 2:
  - ponteiros de página (localização no livro)
  - seções para resumo completo, subtópicos, trechos-âncora (citações curtas),
    pegadinhas e conexões

IMPORTANTE (direitos autorais): este script NÃO extrai o texto integral do livro.
Ele cria a estrutura com placeholders {RESUMO_COMPLETO}, {CITACOES} etc. que o
AGENTE (Claude) preenche — o resumo é redigido do zero e as citações são trechos
curtos com atribuição de página. Assim o material fica original e didático.

Uso:
    python build_subject_md.py --mapa mapa-localizacao.json \
        --out-dir <pasta-assuntos> --concurso "SEDES_2026" \
        [--template <assunto.md.tpl>] [--so-encontrados]

Emite um .md por assunto (arcabouço) + um relatório do que precisa ser preenchido.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from aprofundamento_id import (  # noqa: E402
    slug, slug_fonte, slug_suspeito, id_aprofundamento, nome_base,
    chave_localizacao, parse_id, fontes_legiveis,
)

PADRAO_TEMPLATE = Path(__file__).resolve().parents[1] / "assets/templates/assunto.md.tpl"


def fmt_paginas(loc: dict) -> str:
    """Formata as páginas para exibição. Se o assunto está embutido num capítulo
    maior (tem paginas_relevantes), prefere listar as páginas específicas, que
    são mais úteis que o intervalo cheio do capítulo."""
    rel = loc.get("paginas_relevantes")
    conf = loc.get("confianca")
    p = loc.get("paginas")
    # embutido: confiança média + páginas relevantes disponíveis -> usar as específicas
    if rel and conf != "alta":
        faixa = f" (dentro de {p[0]}–{p[1]})" if p else ""
        return "pp. " + ", ".join(map(str, rel)) + faixa
    if not p:
        return ", ".join(map(str, rel)) if rel else "?"
    return f"{p[0]}–{p[1]}" if p[0] != p[1] else str(p[0])


def localizacao_das_extras(assunto: str, extras_mapa: list, marcador: str) -> tuple:
    """Os três trechos que as fontes 2..N acrescentam ao template.

    Devolve (frontmatter, callout, checklist). Todos os três são placeholders de
    FIM DE LINHA e vêm com o `\\n` na frente: com uma fonte só eles são strings
    vazias e o arquivo gerado sai byte a byte igual ao de antes — por construção,
    sem depender de limpar linha em branco depois.

    Fonte em que o assunto NÃO foi localizado aparece como "não localizado" em vez
    de sumir: omitir seria o falso negativo que este repo proíbe — o leitor não
    saberia se a fonte não cobre o assunto ou se ninguém procurou.
    """
    fm, callout, checklist = [], [], []
    for i, m in enumerate(extras_mapa):
        nome = m.get("livro", "") or f"fonte {i + 2}"
        loc = (m.get("localizacoes") or {}).get(assunto)
        if loc and loc.get("confianca") not in (None, "nao_encontrado"):
            pgs = fmt_paginas(loc)
            fm.append(f'{chave_localizacao(i + 1)}: "{nome} — págs. {pgs}"')
            callout.append(f"> {marcador} **Também em:** *{nome}* — páginas **{pgs}** "
                           f"({loc.get('metodo', '?')}, confiança {loc.get('confianca')}).")
            checklist.append(f"- [ ] Ler as páginas {pgs} de *{nome}*")
        else:
            fm.append(f'{chave_localizacao(i + 1)}: "{nome} — não localizado"')
            callout.append(f"> ⚠️ **Não localizado em** *{nome}* — confirme à mão "
                           f"se a fonte cobre este assunto.")
    def junta(linhas):
        return ("\n" + "\n".join(linhas)) if linhas else ""
    return junta(fm), junta(callout), junta(checklist)


def preencher_template(tpl: str, ctx: dict) -> str:
    out = tpl
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapa", type=Path, action="append", default=None,
                    help="mapa-localizacao.json do book_index. Dispensável com "
                         "--proprio, que não tem livro para localizar. REPETÍVEL: um "
                         "mapa por fonte, na MESMA ordem de --fontes. O book_index "
                         "indexa um livro por execução, então N fontes já são N "
                         "execuções; juntá-los num arquivo só seria um quarto formato "
                         "e um lugar novo onde 'de qual livro é esta página' se perde.")
    ap.add_argument("--assuntos", type=Path, default=None,
                    help="arquivo com um assunto por linha. Entrada de --proprio, "
                         "que não passa por localização em livro.")
    ap.add_argument("--proprio", action="store_true",
                    help="material escrito do zero, sem fonte externa. Gera "
                         "{nivel}--proprio e usa o template sem páginas/citações.")
    ap.add_argument("--materia", default="",
                    help="nome da matéria. Vem do mapa quando há --mapa; com "
                         "--assuntos precisa ser informado.")
    ap.add_argument("--materia-id", default="",
                    help="slug estável da matéria, o join com o mapa do edital")
    ap.add_argument("--topico-id", default="",
                    help="slug do tópico do mapa a que estes assuntos pertencem")
    ap.add_argument("--topico", default="",
                    help="título legível do tópico, para conferência humana")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--concurso", default="")
    ap.add_argument("--template", type=Path, default=PADRAO_TEMPLATE)
    ap.add_argument("--fontes", default="",
                    help="nome(s) da(s) fonte(s), separados por vírgula. Ex: "
                         "'A Gramática para Concursos (Pestana)'. Várias fontes numa "
                         "mesma execução geram UM aprofundamento combinado.")
    ap.add_argument("--fontes-slug", default="",
                    help="slugs das fontes, separados por vírgula, na MESMA ordem de "
                         "--fontes. Sobrepõe a derivação automática. Use quando o nome "
                         "da fonte não permite deduzir o autor/norma "
                         "(ex.: --fontes-slug 'kotler').")
    ap.add_argument("--nivel", default="padrao", choices=["padrao", "detalhado"],
                    help="padrao = resumo de revisão; detalhado = tratamento exaustivo")
    ap.add_argument("--legado-plano", action="store_true",
                    help="gerar no formato antigo (arquivo direto na pasta do assunto)")
    ap.add_argument("--prioridades", type=Path, default=None,
                    help='JSON {"Assunto": "alta|media|base"} para classificar os assuntos')
    ap.add_argument("--prioridade-default", default="media",
                    choices=["alta", "media", "base"])
    ap.add_argument("--forcar", action="store_true",
                    help="regerar por cima de arcabouço já existente. Faz backup\n"
                         ".md.bak antes — o .md guarda o resumo escrito à mão.")
    ap.add_argument("--so-encontrados", action="store_true",
                    help="não gerar arcabouço para assuntos não localizados")
    args = ap.parse_args()

    if not args.mapa and not args.assuntos:
        sys.exit("erro: informe --mapa (localização em livro) ou --assuntos "
                 "(lista direta, usada com --proprio).")

    extras_mapa = []
    if args.mapa:
        mapas = [json.loads(m.read_text(encoding="utf-8")) for m in args.mapa]
        mapa, extras_mapa = mapas[0], mapas[1:]
    else:
        # Sem livro não há localização. O mapa sintético traz confiança
        # "sem_fonte" — e NÃO "nao_encontrado": um material deliberadamente sem
        # livro não pode se disfarçar de falha de localização, que é o que a
        # regra de honestidade proíbe.
        # Aceita TXT (um assunto por linha) e o MESMO JSON que o book_index.py
        # consome (`{"materia", "assuntos": [...]}`). Os dois scripts liam
        # formatos diferentes para a mesma lista, o que obrigava a converter à
        # mão entre uma etapa e a seguinte.
        bruto = args.assuntos.read_text(encoding="utf-8").strip()
        materia_json = ""
        if bruto.startswith("{"):
            spec = json.loads(bruto)
            assuntos = spec.get("assuntos", [])
            materia_json = spec.get("materia", "")
        else:
            assuntos = [l.strip() for l in bruto.split("\n") if l.strip()]
        mapa = {"materia": materia_json, "livro": "",
                "localizacoes": {a: {"confianca": "sem_fonte"} for a in assuntos}}

    prioridades = {}
    if args.prioridades and args.prioridades.exists():
        prioridades = json.loads(args.prioridades.read_text(encoding="utf-8"))

    tpl_path = args.template
    if args.template == PADRAO_TEMPLATE:
        nome = {(False, "padrao"):    "assunto.md.tpl",
                (False, "detalhado"): "assunto-detalhado.md.tpl",
                (True,  "padrao"):    "assunto-proprio.md.tpl",
                (True,  "detalhado"): "assunto-proprio-detalhado.md.tpl"}[
                    (bool(args.proprio), args.nivel)]
        alt = PADRAO_TEMPLATE.parent / nome
        if alt.exists():
            tpl_path = alt
    tpl = tpl_path.read_text(encoding="utf-8")
    materia = args.materia or mapa.get("materia", "")
    livro = mapa.get("livro", "")

    avisos = []
    if args.proprio:
        fontes, fontes_slug = [], []
        aprof_id = id_aprofundamento([], args.nivel, proprio=True)
    else:
        fontes = [f.strip() for f in args.fontes.split(",") if f.strip()]
        if not fontes:
            fontes = [livro] if livro else ["fonte"]
        fontes_slug = [s.strip() for s in args.fontes_slug.split(",") if s.strip()]
        if fontes_slug and len(fontes_slug) != len(fontes):
            sys.exit(f"erro: --fontes-slug tem {len(fontes_slug)} item(ns) e --fontes tem "
                     f"{len(fontes)}; devem casar em número e ordem.")
        aprof_id = id_aprofundamento(fontes, args.nivel, fontes_slug or None)
        # mesmo guard de --fontes-slug: pareamento posicional só é confiável se os
        # comprimentos casam. Um mapa a mais/menos gravaria a página do livro errado.
        if args.mapa and len(args.mapa) not in (1, len(fontes)):
            sys.exit(f"erro: --mapa foi passado {len(args.mapa)} vez(es) e --fontes tem "
                     f"{len(fontes)} fonte(s); use 1 mapa (só a fonte 1 localizada) ou "
                     f"um por fonte, na mesma ordem.")

        # não gravar path ruim no vault: avisa e pede slug explícito
        if not fontes_slug:
            for f in fontes:
                s = slug_fonte(f)
                if slug_suspeito(s):
                    avisos.append(
                        f"slug '{s}' derivado de {f!r} não identifica a fonte — "
                        f"rode de novo com --fontes-slug")

    if not args.topico_id:
        avisos.append("sem --topico-id: o assunto nasce sem vínculo com o tópico do "
                      "edital, e o site não vai conseguir agrupá-lo por tópico")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    gerados, pulados, a_preencher = [], [], []
    ja_existiam, forcados = [], []

    # a lista de assuntos é a UNIÃO das chaves: um assunto pode estar só no livro 2
    todos_assuntos = dict(mapa.get("localizacoes", {}))
    for m in extras_mapa:
        for a, loc in m.get("localizacoes", {}).items():
            todos_assuntos.setdefault(a, {"confianca": "nao_encontrado"})

    for assunto, loc in todos_assuntos.items():
        conf = loc.get("confianca", "nao_encontrado")
        if conf == "sem_fonte":
            paginas, metodo, aviso = "", "", ""
        elif conf == "nao_encontrado":
            if args.so_encontrados:
                pulados.append(assunto)
                continue
            paginas = "??? (não localizado — buscar manualmente)"
            metodo = "não localizado"
            aviso = "> ⚠️ **Localização não encontrada automaticamente.** Confirme a página no livro."
        else:
            paginas = fmt_paginas(loc)
            metodo = loc.get("metodo", "?")
            aviso = ("> ⚠️ **Confira a localização** — confiança baixa/média."
                     if conf in ("baixa", "media") else "")

        sassunto = slug(assunto)
        if args.legado_plano:
            subdir = args.out_dir / sassunto
            base = sassunto
        else:
            # cada aprofundamento vive na sua própria pasta, identificada por
            # nível + fontes — permite vários aprofundamentos do mesmo assunto
            subdir = args.out_dir / sassunto / aprof_id
            base = nome_base(sassunto, aprof_id, args.concurso)
        subdir.mkdir(parents=True, exist_ok=True)

        # o marcador do callout difere entre os templates (📍 no padrão, 📖 no
        # detalhado); seguir o do template evita duas fontes com ícones diferentes
        marcador = "📖" if args.nivel == "detalhado" else "📍"
        loc_fm, loc_callout, loc_check = localizacao_das_extras(
            assunto, extras_mapa, marcador)

        ctx = {
            "ASSUNTO": assunto,
            "MATERIA": materia,
            "CONCURSO": args.concurso,
            "LIVRO": livro,
            "PAGINAS": paginas,
            "CONFIANCA": conf,
            # vazios com uma fonte só: o arquivo sai idêntico ao de antes
            "LOCALIZACAO_EXTRA_FM": loc_fm,
            "LOCALIZACOES_EXTRA": loc_callout,
            "CHECKLIST_LEITURA_EXTRA": loc_check,
            "PRIORIDADE": prioridades.get(assunto, args.prioridade_default),
            "METODO_LOCALIZACAO": metodo,
            "AVISO_CONFERIR": aviso,
            # tag da matéria some quando não há matéria, em vez de deixar um item
            # vazio no meio da lista YAML (`[a, , b]`)
            "TAG_MATERIA": f", {slug(materia)}" if slug(materia) else "",
            "TAG_ASSUNTO": sassunto,
            "SLUG_ASSUNTO": base,
            "APROFUNDAMENTO": aprof_id,
            "NIVEL": args.nivel,
            # O texto informado VENCE quando é consistente com o id (mesma
            # contagem); só se não houver é que se deriva do id.
            #
            # Derivar sempre degradaria o dado: medido no vault, 53 dos 55 slugs
            # têm um único nome, e esse nome carrega precisão que o slug não tem
            # — `lei-8742` deriva "Lei 8.742", mas o texto diz "Lei nº 8.742/1993".
            # Trocar 53 nomes bons para consertar 2 divergentes seria piorar.
            # A consistência é garantida pelo validador, não por sobrescrita.
            "FONTES": (", ".join(fontes)
                       if len(fontes) == len(parse_id(aprof_id)["fontes"])
                       else ", ".join(fontes_legiveis(aprof_id))) or livro,
            # O vínculo com o plano do edital, montado como YAML aqui e não no
            # template: sem tópico o campo tem de sair `[]`, não `[""]` — lista
            # vazia é "ainda não vinculado", e uma lista com string vazia é lixo
            # que o leitor teria de aprender a ignorar.
            "MATERIA_ID": args.materia_id or slug(materia),
            "TOPICO_ID": f"[{args.topico_id}]" if args.topico_id else "[]",
            "TOPICO": f'["{args.topico}"]' if args.topico else "[]",
            # placeholders que o AGENTE preenche (Modelo 2):
            "RELEVANCIA_CONCURSO": "{RELEVANCIA_CONCURSO}",
            "RESUMO": "{RESUMO}",
            "VISAO_GERAL": "{VISAO_GERAL}",
            "DESENVOLVIMENTO": "{DESENVOLVIMENTO}",
            "QUADRO_CASOS": "{QUADRO_CASOS}",
            "EXEMPLOS_RESOLVIDOS": "{EXEMPLOS_RESOLVIDOS}",
            "QUESTOES_COMENTADAS": "{QUESTOES_COMENTADAS}",
            "DIVERGENCIAS": "{DIVERGENCIAS}",
            "SUBTOPICOS": "{SUBTOPICOS}",
            "CITACOES": "{CITACOES}",
            "ONDE_CONFERIR": "{ONDE_CONFERIR}",
            "PEGADINHAS": "{PEGADINHAS}",
            "RELACIONADOS": "{RELACIONADOS}",
            "NORMA": "{NORMA}",
        }
        conteudo = preencher_template(tpl, ctx)
        destino = subdir / f"{base}.md"

        # NÃO sobrescrever conteúdo já preenchido.
        #
        # Este arquivo é onde mora o resumo escrito à mão — o ativo mais caro do
        # vault. Até aqui o script gravava por cima sem perguntar, então rodar a
        # matéria de novo trocava o texto pronto por um arcabouço com os
        # {PLACEHOLDER} de volta. O risco explode no modo seletivo (aprofundar um
        # tópico por vez), que é justamente reexecutar a mesma matéria várias
        # vezes. Regenerar de propósito exige --forcar, e mesmo assim com backup.
        if destino.exists() and not args.forcar:
            ja_existiam.append(str(destino))
            continue
        if destino.exists():
            destino.with_suffix(".md.bak").write_text(
                destino.read_text(encoding="utf-8"), encoding="utf-8")
            forcados.append(str(destino))
        destino.write_text(conteudo, encoding="utf-8")
        gerados.append(str(destino))

        # quais placeholders sobraram para o agente preencher
        faltando = sorted(set(re.findall(r"\{([A-Z_]+)\}", conteudo)))
        if faltando:
            a_preencher.append({"assunto": assunto, "arquivo": str(destino),
                                "campos": faltando, "paginas": paginas})

    relatorio = {
        "materia": materia, "livro": livro,
        "aprofundamento": aprof_id, "nivel": args.nivel, "fontes": fontes,
        "gerados": len(gerados), "pulados": pulados,
        # separados de propósito: "pulado" é assunto sem localização no livro;
        # "ja_existia" é arcabouço preservado — dizer só "pulou" confundiria os dois
        "ja_existiam": ja_existiam, "forcados": forcados,
        "avisos": avisos,
        "a_preencher": a_preencher,
    }
    print(json.dumps(relatorio, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
