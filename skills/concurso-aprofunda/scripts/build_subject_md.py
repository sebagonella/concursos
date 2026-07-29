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


def preencher_template(tpl: str, ctx: dict) -> str:
    out = tpl
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapa", type=Path, required=True)
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
    ap.add_argument("--so-encontrados", action="store_true",
                    help="não gerar arcabouço para assuntos não localizados")
    args = ap.parse_args()

    mapa = json.loads(args.mapa.read_text(encoding="utf-8"))
    prioridades = {}
    if args.prioridades and args.prioridades.exists():
        prioridades = json.loads(args.prioridades.read_text(encoding="utf-8"))
    tpl_path = args.template
    if args.nivel == "detalhado" and args.template == PADRAO_TEMPLATE:
        alt = PADRAO_TEMPLATE.parent / "assunto-detalhado.md.tpl"
        if alt.exists():
            tpl_path = alt
    tpl = tpl_path.read_text(encoding="utf-8")
    materia = mapa.get("materia", "")
    livro = mapa.get("livro", "")

    fontes = [f.strip() for f in args.fontes.split(",") if f.strip()]
    if not fontes:
        fontes = [livro] if livro else ["fonte"]
    fontes_slug = [s.strip() for s in args.fontes_slug.split(",") if s.strip()]
    if fontes_slug and len(fontes_slug) != len(fontes):
        sys.exit(f"erro: --fontes-slug tem {len(fontes_slug)} item(ns) e --fontes tem "
                 f"{len(fontes)}; devem casar em número e ordem.")
    aprof_id = id_aprofundamento(fontes, args.nivel, fontes_slug or None)

    # não gravar path ruim no vault: avisa e pede slug explícito
    avisos = []
    if not fontes_slug:
        for f in fontes:
            s = slug_fonte(f)
            if slug_suspeito(s):
                avisos.append(
                    f"slug '{s}' derivado de {f!r} não identifica a fonte — "
                    f"rode de novo com --fontes-slug")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    gerados, pulados, a_preencher = [], [], []

    for assunto, loc in mapa.get("localizacoes", {}).items():
        conf = loc.get("confianca", "nao_encontrado")
        if conf == "nao_encontrado":
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

        ctx = {
            "ASSUNTO": assunto,
            "MATERIA": materia,
            "CONCURSO": args.concurso,
            "LIVRO": livro,
            "PAGINAS": paginas,
            "CONFIANCA": conf,
            "PRIORIDADE": prioridades.get(assunto, args.prioridade_default),
            "METODO_LOCALIZACAO": metodo,
            "AVISO_CONFERIR": aviso,
            "TAG_MATERIA": slug(materia),
            "TAG_ASSUNTO": sassunto,
            "SLUG_ASSUNTO": base,
            "APROFUNDAMENTO": aprof_id,
            "NIVEL": args.nivel,
            "FONTES": ", ".join(fontes) if fontes else livro,
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
            "PEGADINHAS": "{PEGADINHAS}",
            "RELACIONADOS": "{RELACIONADOS}",
            "NORMA": "{NORMA}",
        }
        conteudo = preencher_template(tpl, ctx)
        destino = subdir / f"{base}.md"
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
        "avisos": avisos,
        "a_preencher": a_preencher,
    }
    print(json.dumps(relatorio, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
