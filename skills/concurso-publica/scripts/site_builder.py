#!/usr/bin/env python3
"""
site_builder.py - Subsistema B da skill concurso-publica.

Consome o modelo produzido pelo site_collector.py e gera o site estático:
  - capa do concurso (ficha da prova + matérias)
  - índice por matéria (assuntos com selos de mídia e progresso)
  - página por assunto (resumo + mídias embutidas + quiz de flashcards)

Princípios (decisões aprovadas):
  - Site SÓ LEITURA: o progresso vem do vault e é exibido, nunca editado.
  - Mídia ausente = seção ausente, sem quebrar.
  - Assets locais (sem CDN): o site funciona offline / na rede doméstica.
  - Botão "Abrir no NotebookLM" só se notebooklm_url estiver preenchida.

Uso:
    python site_builder.py --concurso-dir <.../CONCURSOS/SEDES_2026> --out out/site
    python site_builder.py --modelo site-model.json --out out/site
"""
import argparse
import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import md2html  # noqa: E402
from site_collector import coletar_concurso, CATALOGO_MIDIAS, PRIORIDADES  # noqa: E402

ASSETS = AQUI.parent / "assets"


# --------------------------------------------------------------------------- #
# helpers de HTML
# --------------------------------------------------------------------------- #
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def nome_legivel(slug: str) -> str:
    """SEDES_2026 -> SEDES 2026 · BB_2027_PREVISTO -> BB 2027 (previsto)."""
    s = slug.replace("_", " ").strip()
    s = re.sub(r"\bPREVISTO\b", "(previsto)", s)
    s = re.sub(r"\bV(\d+)[- ]OFICIAL\b", r"— oficial (v\1)", s)
    s = re.sub(r"\bV(\d+)[- ]RETIFICADO\b", r"— retificado (v\1)", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def pagina(titulo: str, trilha_html: str, corpo: str, prefixo: str,
           descricao: str = "") -> str:
    """Esqueleto comum. `prefixo` é o caminho relativo até a raiz do site."""
    ano = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titulo)}</title>
{f'<meta name="description" content="{esc(descricao)}">' if descricao else ''}
<link rel="stylesheet" href="{prefixo}assets/site.css">
<script>
/* aplica o tema antes da pintura, para não piscar */
(function(){{try{{var t=localStorage.getItem("concursos:tema");
if(!t)t=(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches)?"escuro":"claro";
document.documentElement.setAttribute("data-tema",t);}}catch(e){{}}}})();
</script>
</head>
<body>
<header class="topo">
  <div class="topo-interno">
    <a class="marca" href="{prefixo}index.html">Estudo para concursos</a>
    <nav class="trilha">{trilha_html}</nav>
    <button class="tema-troca" type="button">☾ Escuro</button>
  </div>
</header>
<main class="folha">
{corpo}
</main>
<div class="lightbox" role="dialog" aria-label="Mapa mental ampliado"><img alt="Mapa mental ampliado"></div>
<footer class="rodape">
  Gerado a partir do vault em {ano}. Conteúdo de estudo — confira sempre o edital oficial.
</footer>
<script src="{prefixo}assets/site.js"></script>
</body>
</html>
"""


def gabarito(progresso: dict, max_bolhas: int = 12) -> str:
    """Elemento-assinatura: as bolhas do cartão-resposta como barra de progresso."""
    total = progresso.get("total", 0)
    feitos = progresso.get("feitos", 0)
    if total <= 0:
        return ""
    mostrar = min(total, max_bolhas)
    cheias = round(feitos / total * mostrar) if total else 0
    bolhas = "".join(
        f'<span class="bolha{" cheia" if i < cheias else ""}"></span>'
        for i in range(mostrar)
    )
    return (f'<div class="gabarito"><span class="rotulo">Progresso</span>{bolhas}'
            f'<span class="contagem">{feitos} de {total}</span></div>')


def selos_midia(assunto: dict, so_presentes: bool = False) -> str:
    """Selos das mídias. Por padrão mostra também as ausentes (em cinza),
    o que ajuda a ver o que ainda falta gerar no NotebookLM."""
    partes = []
    for chave, (_pref, _ext, icone, rotulo) in CATALOGO_MIDIAS.items():
        tem = bool(assunto["midias"].get(chave))
        if so_presentes and not tem:
            continue
        cls = "selo" if tem else "selo ausente"
        partes.append(f'<span class="{cls}" title="{esc(rotulo)}">{icone}</span>')
    n = assunto["flashcards"].get("n_cards", 0)
    if n or not so_presentes:
        cls = "selo" if n else "selo ausente"
        partes.append(f'<span class="{cls}" title="Cartões didáticos">🃏 {n}</span>')
    return f'<div class="selos">{"".join(partes)}</div>' if partes else ""


# --------------------------------------------------------------------------- #
# flashcards -> JSON para o quiz
# --------------------------------------------------------------------------- #
def parsear_flashcards(caminho: Path) -> list[dict]:
    """Lê o .md de flashcards (multiline '??' ou singleline '::')."""
    try:
        txt = caminho.read_text(encoding="utf-8")
    except Exception:
        return []
    txt = re.sub(r"^---\s*\n.*?\n---\s*\n", "", txt, count=1, flags=re.DOTALL)
    txt = re.sub(r"<!--.*?-->", "", txt, flags=re.DOTALL)
    cards = []

    linhas = txt.split("\n")
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        # multiline: pergunta / ?? / resposta
        if linha == "??" and i > 0:
            frente = linhas[i - 1].strip()
            resposta = []
            j = i + 1
            while j < len(linhas) and linhas[j].strip() and linhas[j].strip() != "??":
                resposta.append(linhas[j].strip())
                j += 1
            if frente and resposta and not frente.startswith((">", "#")):
                cards.append({"f": frente, "v": " ".join(resposta)})
            i = j
            continue
        # singleline: pergunta::resposta
        if "::" in linha and not linha.startswith((">", "#", "-")):
            f, _, v = linha.partition("::")
            if f.strip() and v.strip():
                cards.append({"f": f.strip(), "v": v.strip()})
        i += 1
    return cards


def bloco_quiz(cards: list[dict], link_vault: str | None) -> str:
    if not cards:
        return ""
    dados = json.dumps(cards, ensure_ascii=False)
    return f"""<section class="cartao quiz">
  <h3>Flashcards ({len(cards)})</h3>
  <div class="carta" role="button" aria-label="Cartão — clique para virar">
    <span class="frente"></span><span class="verso"></span>
  </div>
  <div class="controles">
    <span class="posicao"></span>
    <span>
      <button class="botao secundario" data-acao="virar">Virar</button>
      <button class="botao" data-acao="proxima">Próximo</button>
    </span>
  </div>
  <div class="controles">
    <button class="botao secundario" data-acao="embaralhar">Embaralhar</button>
  </div>
  <p class="dica">Clique no cartão ou use espaço para virar, seta direita para avançar.
  Para revisão espaçada com agendamento, use o baralho no Obsidian.</p>
  <script type="application/json">{dados}</script>
</section>"""


# --------------------------------------------------------------------------- #
# páginas
# --------------------------------------------------------------------------- #
ROTULO_NIVEL = {"detalhado": "Detalhado", "padrao": "Padrão"}


def rotulo_aprof(ap: dict) -> str:
    """Rótulo legível de um aprofundamento: fonte + nível."""
    nivel = ROTULO_NIVEL.get(ap.get("nivel", ""), ap.get("nivel", ""))
    fontes = (ap.get("fontes") or "").strip()
    if fontes:
        curto = fontes if len(fontes) <= 42 else fontes[:40] + "…"
        return f"{curto} · {nivel}"
    ident = ap.get("aprofundamento", "")
    if ident in ("unico", "original", ""):
        return f"Material original · {nivel}"
    return f"{ident} · {nivel}"


def bloco_aprofundamento(ap: dict, materia: dict, assunto: dict, destino_dir: Path,
                         indice: int, ativo: bool) -> tuple[str, str]:
    """Renderiza UM aprofundamento: corpo (coluna esquerda) + cartões (lateral)."""
    origem_dir = Path(ap["resumo_md"]).parent
    irmaos = {a["slug"] for a in materia["assuntos"]}

    def resolver(alvo: str) -> str | None:
        base = alvo.split("/")[-1].replace(".md", "")
        base = base.split("--")[0]
        if base in irmaos and base != assunto["slug"]:
            return f"../{base}/index.html"
        return None

    corpo_md = Path(ap["resumo_md"]).read_text(encoding="utf-8")
    corpo_html = md2html.converter(corpo_md, wikilink_resolver=resolver)

    # mídias deste aprofundamento vão para media/<id>/ (não colidem entre si)
    ident = re.sub(r"[^A-Za-z0-9_+-]+", "-", ap.get("aprofundamento") or f"a{indice}")
    midia_dir = destino_dir / "media" / ident
    blocos = []

    def copiar(nome: str) -> str:
        midia_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem_dir / nome, midia_dir / nome)
        return f"media/{ident}/{nome}"

    def baixar(src: str, rotulo: str = "Baixar") -> str:
        nome = src.split("/")[-1]
        return (f'<a class="baixar" href="{esc(src)}" download="{esc(nome)}">'
                f'⤓ {esc(rotulo)}</a>')

    def cabecalho(rotulo: str, src: str) -> str:
        return f'<div class="titulo-linha"><h3>{esc(rotulo)}</h3>{baixar(src)}</div>'

    m = ap["midias"]
    if m.get("podcast"):
        src = copiar(m["podcast"])
        blocos.append(f'<section class="cartao">{cabecalho("Resumo em áudio", src)}'
                      f'<audio controls preload="none" src="{esc(src)}"></audio></section>')
    if m.get("video"):
        src = copiar(m["video"])
        blocos.append(f'<section class="cartao">{cabecalho("Resumo em vídeo", src)}'
                      f'<video controls preload="none" src="{esc(src)}"></video></section>')
    if m.get("mapa_mental"):
        src = copiar(m["mapa_mental"])
        blocos.append(f'<section class="cartao mapa-mental">{cabecalho("Mapa mental", src)}'
                      f'<img src="{esc(src)}" alt="Mapa mental" loading="lazy"></section>')
    if m.get("infografico"):
        src = copiar(m["infografico"])
        if src.lower().endswith(".pdf"):
            blocos.append(f'<section class="cartao">{cabecalho("Infográfico", src)}'
                          f'<a class="botao secundario" href="{esc(src)}" target="_blank" '
                          f'rel="noopener">Abrir infográfico</a></section>')
        else:
            blocos.append(f'<section class="cartao mapa-mental">{cabecalho("Infográfico", src)}'
                          f'<img src="{esc(src)}" alt="Infográfico" loading="lazy"></section>')
    if m.get("slides"):
        src = copiar(m["slides"])
        blocos.append(f'<section class="cartao">{cabecalho("Apresentação de slides", src)}'
                      f'<a class="botao secundario" href="{esc(src)}" target="_blank" '
                      f'rel="noopener">Abrir slides</a></section>')

    extras = []
    for chave in ("teste", "tabela"):
        if m.get(chave):
            src = copiar(m[chave])
            _p, _e, icone, rotulo = CATALOGO_MIDIAS[chave]
            extras.append(f'<li><span class="rot">{icone} {esc(rotulo)}</span>{baixar(src)}</li>')
    if extras:
        blocos.append(f'<section class="cartao"><h3>Outros materiais</h3>'
                      f'<ul class="midias-extra">{"".join(extras)}</ul></section>')

    fc = ap["flashcards"].get("obsidian")
    if fc:
        cards = parsear_flashcards(origem_dir / fc)
        b = bloco_quiz(cards, None)
        if b:
            blocos.append(b)

    if ap.get("notebooklm_url"):
        blocos.append(f'<section class="cartao"><h3>NotebookLM</h3>'
                      f'<p style="font-size:.88rem;margin:0 0 .6rem">Mapa interativo e chat com as fontes.</p>'
                      f'<a class="botao secundario" target="_blank" rel="noopener" '
                      f'href="{esc(ap["notebooklm_url"])}">Abrir no NotebookLM</a></section>')

    if m.get("report"):
        rep = m["report"]
        if rep.lower().endswith((".md", ".txt")):
            src = copiar(rep)
            corpo_html += (f'\n<h2>Relatório {baixar(src, "baixar")}</h2>\n'
                           + md2html.converter((origem_dir / rep).read_text(encoding="utf-8")))
        else:
            src = copiar(rep)
            blocos.append(f'<section class="cartao">{cabecalho("Relatório", src)}'
                          f'<a class="botao secundario" href="{esc(src)}" target="_blank" '
                          f'rel="noopener">Abrir relatório</a></section>')

    cls = "aprof" + (" ativo" if ativo else "")
    pag = ap.get("paginas_livro")
    ficha = []
    if ap.get("fontes"):
        ficha.append(f'<div><dt>Fonte</dt><dd style="font-size:.92rem">{esc(ap["fontes"])}</dd></div>')
    if pag:
        ficha.append(f'<div><dt>No livro</dt><dd style="font-size:.92rem">págs. {esc(pag)}</dd></div>')
    ficha.append(f'<div><dt>Nível</dt><dd style="font-size:.92rem">'
                 f'{esc(ROTULO_NIVEL.get(ap.get("nivel",""), ap.get("nivel","")))}</dd></div>')

    corpo = (f'<article class="papel {cls}" data-aprof="{esc(ident)}">'
             f'<dl class="ficha">{"".join(ficha)}</dl>'
             f'{corpo_html}</article>')
    lateral = (f'<div class="{cls}" data-aprof="{esc(ident)}">'
               f'{gabarito(ap["progresso"])}{"".join(blocos)}</div>')
    return corpo, lateral


def pagina_assunto(assunto: dict, materia: dict, concurso: str,
                   origem_dir: Path, destino_dir: Path) -> str:
    titulo = assunto["titulo"]
    aprofs = assunto.get("aprofundamentos") or []

    corpos, laterais, abas = [], [], []
    for i, ap in enumerate(aprofs):
        ativo = (i == 0)
        c, l = bloco_aprofundamento(ap, materia, assunto, destino_dir, i, ativo)
        corpos.append(c)
        laterais.append(l)
        ident = re.sub(r"[^A-Za-z0-9_+-]+", "-", ap.get("aprofundamento") or f"a{i}")
        abas.append(f'<button class="aba{" ativa" if ativo else ""}" '
                    f'data-alvo="{esc(ident)}" type="button">{esc(rotulo_aprof(ap))}</button>')

    seletor = ""
    if len(aprofs) > 1:
        seletor = (f'<div class="seletor-aprof" role="tablist" '
                   f'aria-label="Versões deste assunto">'
                   f'<span class="rotulo">Aprofundamentos</span>{"".join(abas)}</div>')

    corpo = f"""<div class="papel cabecalho-assunto">
  <div class="sobrancelha">{esc(materia["nome"])}</div>
  <h1>{esc(titulo)}</h1>
  {selos_aprofundamento(assunto)}
  {seletor}
</div>
<div class="colunas" style="margin-top:1.25rem">
  <div>{"".join(corpos)}</div>
  <aside class="lateral">
    <section class="cartao">
      <h3>Este assunto</h3>
      {selos_midia(assunto)}
    </section>
    {"".join(laterais)}
  </aside>
</div>"""

    trilha = (f'<a href="../../index.html">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="../index.html">{esc(materia["nome"])}</a> › {esc(titulo)}')
    descricao = ""
    if aprofs:
        try:
            descricao = md2html.primeiro_paragrafo(
                Path(aprofs[0]["resumo_md"]).read_text(encoding="utf-8"), limite=180)
        except Exception:
            descricao = ""
    return pagina(f"{titulo} — {nome_legivel(concurso)}", trilha, corpo, "../../../",
                  descricao)


ROTULOS_PRIORIDADE = {
    "alta":  ("Prioridade alta", "Os que mais derrubam candidato — comece por aqui."),
    "media": ("Prioridade média", "Importantes, mas depois de dominar os de alta."),
    "base":  ("Base e leitura", "Fundamentos e assuntos de leitura; reforçam o resto."),
}


def selos_aprofundamento(assunto: dict) -> str:
    """Sinaliza no card: quantas fontes e quais níveis de aprofundamento existem.

    Usa a bolha do cartão-resposta (assinatura visual do site) para comunicar
    profundidade: bolha PELA METADE = padrão, bolha CHEIA = detalhado.
    """
    niveis = assunto.get("niveis") or []
    n_fontes = assunto.get("n_fontes") or 0
    n_aprof = assunto.get("n_aprofundamentos") or 0
    if not niveis and n_fontes <= 1 and n_aprof <= 1:
        return ""   # caso simples: não poluir o card

    partes = []

    # fontes
    if n_fontes >= 1:
        titulo = "; ".join(assunto.get("fontes") or [])
        rot = "1 fonte" if n_fontes == 1 else f"{n_fontes} fontes"
        partes.append(f'<span class="selo-aprof" title="{esc(titulo)}">📚 {rot}</span>')

    # níveis — meia bolha (padrão) e/ou bolha cheia (detalhado)
    tem_padrao = "padrao" in niveis
    tem_detalhado = "detalhado" in niveis
    if tem_padrao and tem_detalhado:
        rot, cls, titulo = "Padrão + Detalhado", "ambos", "Há versão padrão e detalhada"
    elif tem_detalhado:
        rot, cls, titulo = "Detalhado", "detalhado", "Aprofundamento detalhado"
    elif tem_padrao:
        rot, cls, titulo = "Padrão", "padrao", "Aprofundamento padrão (revisão)"
    else:
        rot = cls = titulo = ""
    if rot:
        bolhas = ('<span class="bolha meia"></span><span class="bolha cheia"></span>'
                  if cls == "ambos" else
                  f'<span class="bolha {"cheia" if cls == "detalhado" else "meia"}"></span>')
        partes.append(f'<span class="selo-aprof nivel-{cls}" title="{esc(titulo)}">'
                      f'{bolhas}{esc(rot)}</span>')

    # mais de um aprofundamento no mesmo assunto
    if n_aprof > 1:
        partes.append(f'<span class="selo-aprof" title="Versões deste assunto">'
                      f'⇄ {n_aprof} versões</span>')

    return f'<div class="selos-aprof">{"".join(partes)}</div>'


def card_assunto(a: dict) -> str:
    pag = (f'<span class="meta">págs. {esc(a["paginas_livro"])}</span>'
           if a.get("paginas_livro") else "")
    return f"""<a class="item" href="{esc(a["slug"])}/index.html">
  <h3>{esc(a["titulo"])}</h3>
  {pag}
  {selos_aprofundamento(a)}
  {selos_midia(a)}
  {gabarito(a["progresso"], max_bolhas=8)}
</a>"""


def pagina_materia(materia: dict, concurso: str, materia_dir: Path) -> str:
    # agrupar por prioridade, na ordem alta -> média -> base -> sem classificação
    grupos = []
    for prio in PRIORIDADES:
        doss = [a for a in materia["assuntos"] if a.get("prioridade") == prio]
        if not doss:
            continue
        titulo, explica = ROTULOS_PRIORIDADE[prio]
        cards = "".join(card_assunto(a) for a in doss)
        grupos.append(f"""<section class="grupo-prioridade" data-prio="{prio}">
  <header><h2>{esc(titulo)}</h2><span class="quantos">{len(doss)} assuntos</span></header>
  <p class="explica">{esc(explica)}</p>
  <div class="grade">{cards}</div>
</section>""")

    sem_prio = [a for a in materia["assuntos"] if not a.get("prioridade")]
    if sem_prio:
        cards = "".join(card_assunto(a) for a in sem_prio)
        grupos.append(f"""<section class="grupo-prioridade" data-prio="sem">
  <header><h2>Demais assuntos</h2><span class="quantos">{len(sem_prio)} assuntos</span></header>
  <div class="grade">{cards}</div>
</section>""")

    # "Como a banca cobra esta matéria" — antes dos assuntos
    bloco_banca = ""
    if materia.get("doc_banca"):
        try:
            texto = (materia_dir / materia["doc_banca"]).read_text(encoding="utf-8")
            bloco_banca = (f'<section class="papel" style="margin-top:1.25rem">'
                           f'{md2html.converter(texto)}</section>')
        except Exception:
            bloco_banca = ""

    docs = ""
    outros = [d for d in materia.get("docs_apoio", []) if d != materia.get("doc_banca")]
    if outros:
        lista = "".join(f"<li>{esc(d)}</li>" for d in outros)
        docs = (f'<section class="papel" style="margin-top:1.5rem">'
                f'<h2>Documentos de apoio (no vault)</h2><ul>{lista}</ul></section>')

    pp = materia.get("por_prioridade", {})
    resumo_prio = " · ".join(
        f"{pp.get(k, 0)} {ROTULOS_PRIORIDADE[k][0].lower()}"
        for k in PRIORIDADES if pp.get(k))

    corpo = f"""<div class="papel">
  <div class="sobrancelha">{esc(nome_legivel(concurso))}</div>
  <h1>{esc(materia["nome"])}</h1>
  <p>{materia["n_assuntos"]} assuntos · {materia["n_com_podcast"]} com áudio ·
     {materia["n_com_flashcards"]} com flashcards</p>
  {f'<p class="meta">{esc(resumo_prio)}</p>' if resumo_prio else ''}
</div>
{bloco_banca}
{"".join(grupos)}
{docs}"""
    trilha = f'<a href="../index.html">{esc(nome_legivel(concurso))}</a> › {esc(materia["nome"])}'
    return pagina(f'{materia["nome"]} — {nome_legivel(concurso)}', trilha, corpo, "../../")


def pagina_capa(modelo: dict) -> str:
    meta = modelo.get("meta", {})
    campos = []
    if meta.get("banca"):
        campos.append(("Banca", meta["banca"]))
    dk = meta.get("datas_chave") or {}
    if dk.get("prova_data"):
        try:
            d = datetime.strptime(dk["prova_data"], "%Y-%m-%d")
            faltam = (d - datetime.now()).days
            campos.append(("Prova", d.strftime("%d/%m/%Y") +
                           (f" · faltam {faltam} dias" if faltam > 0 else "")))
        except ValueError:
            campos.append(("Prova", dk["prova_data"]))
    if meta.get("vagas_ac"):
        campos.append(("Vagas (AC)", meta["vagas_ac"]))
    if meta.get("salario"):
        campos.append(("Salário", meta["salario"]))
    ep = meta.get("estrutura_prova") or {}
    if isinstance(ep, dict) and (ep.get("objetiva") or {}).get("total_questoes"):
        campos.append(("Questões", ep["objetiva"]["total_questoes"]))

    ficha = ""
    if campos:
        ficha = ('<dl class="ficha">' + "".join(
            f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in campos)
            + "</dl>")

    blocos = []
    for cargo in modelo["cargos"]:
        itens = []
        for mat in cargo["materias"]:
            itens.append(f"""<a class="item" href="{esc(mat["slug"])}/index.html">
  <h3>{esc(mat["nome"])}</h3>
  <div class="meta">{mat["n_assuntos"]} assuntos · {mat["n_com_podcast"]} com podcast</div>
</a>""")
        titulo_cargo = "" if cargo["nome"] == "_GERAL" else f'<h2>{esc(cargo["nome"])}</h2>'
        blocos.append(titulo_cargo + f'<div class="grade">{"".join(itens)}</div>')

    r = modelo["resumo"]
    corpo = f"""<div class="papel">
  <div class="sobrancelha">Preparação</div>
  <h1>{esc(nome_legivel(modelo["concurso"]))}</h1>
  {ficha}
  {gabarito({"total": r["n_assuntos"], "feitos": 0}) if False else ""}
  <p>{r["n_materias"]} matéria(s) · {r["n_assuntos"]} assuntos aprofundados</p>
</div>
<div style="margin-top:1.25rem">{"".join(blocos)}</div>"""
    return pagina(nome_legivel(modelo["concurso"]), '<a href="../index.html">Concursos</a>', corpo, "../")


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def pagina_raiz(concursos: list[dict]) -> str:
    """Índice de TODOS os concursos publicados (a porta de entrada do site)."""
    if not concursos:
        corpo = ('<div class="papel"><h1>Nenhum concurso publicado</h1>'
                 '<p>Gere um concurso com a skill <code>concurso-publica</code>.</p></div>')
        return pagina("Estudo para concursos", "", corpo, "")

    def cartao(c: dict) -> str:
        etiquetas = []
        if c.get("banca"):
            etiquetas.append(esc(c["banca"]))
        if c.get("prova_data"):
            try:
                d = datetime.strptime(c["prova_data"], "%Y-%m-%d")
                faltam = (d - datetime.now()).days
                etiquetas.append(d.strftime("%d/%m/%Y") +
                                 (f" · faltam {faltam} dias" if faltam > 0 else " · realizada"))
            except ValueError:
                etiquetas.append(esc(c["prova_data"]))
        nome = c["concurso"]
        tag = ""
        if "PREVISTO" in nome.upper():
            tag = '<span class="tag">previsto</span>'
        elif "RETIFICADO" in nome.upper():
            tag = '<span class="tag">retificado</span>'
        return f"""<a class="item concurso-item" href="{esc(c["slug"])}/index.html">
  <h3>{esc(nome_legivel(nome))}{tag}</h3>
  <div class="meta">{" · ".join(etiquetas)}</div>
  <div class="resumo">{c.get("n_materias", 0)} matéria(s) · {c.get("n_assuntos", 0)} assuntos aprofundados</div>
</a>"""

    # agrupar por órgão
    por_orgao: dict[str, list[dict]] = {}
    for c in concursos:
        orgao = (c.get("orgao") or re.split(r"[_-]", c["concurso"])[0] or "Outros").upper()
        por_orgao.setdefault(orgao, []).append(c)

    def chave_data(c):
        return c.get("prova_data") or "9999"

    blocos = []
    for orgao in sorted(por_orgao):
        lista = sorted(por_orgao[orgao], key=chave_data)
        cartoes = "".join(cartao(c) for c in lista)
        plural = "concurso" if len(lista) == 1 else "concursos"
        blocos.append(f"""<section class="grupo-orgao">
  <header><h2>{esc(orgao)}</h2><span class="quantos">{len(lista)} {plural}</span></header>
  <div class="grade">{cartoes}</div>
</section>""")
    itens = blocos

    corpo = f"""<div class="papel">
  <div class="sobrancelha">Vault de estudos</div>
  <h1>Concursos</h1>
  <p>{len(concursos)} concurso(s) em {len(por_orgao)} órgão(s), publicados a partir do vault.</p>
</div>
<div style="margin-top:1.25rem">{"".join(itens)}</div>"""
    return pagina("Estudo para concursos", "", corpo, "")


def ler_manifestos(raiz: Path) -> list[dict]:
    """Lê os manifestos de todos os concursos já publicados nesta pasta.
    Permite deploy incremental: publicar um concurso não apaga os outros do índice."""
    achados = []
    for man in sorted(raiz.glob("*/.concurso.json")):
        try:
            achados.append(json.loads(man.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return achados


def construir(modelo: dict, destino: Path, com_raiz: bool = True) -> dict:
    """Gera o site de UM concurso em destino/<slug-do-concurso>/ e (re)gera o
    índice raiz listando todos os concursos publicados em destino/."""
    destino.mkdir(parents=True, exist_ok=True)

    concurso = modelo["concurso"]
    slug_conc = re.sub(r"[^A-Za-z0-9_-]+", "-", concurso).strip("-").lower()
    base = destino / slug_conc
    base.mkdir(parents=True, exist_ok=True)

    # assets ficam na raiz e são compartilhados por todos os concursos
    dest_assets = destino / "assets"
    dest_assets.mkdir(exist_ok=True)
    for nome in ("site.css", "site.js"):
        origem = ASSETS / nome
        if origem.exists():
            shutil.copy2(origem, dest_assets / nome)

    n_paginas = 0
    (base / "index.html").write_text(pagina_capa(modelo), encoding="utf-8")
    n_paginas += 1

    for cargo in modelo["cargos"]:
        for materia in cargo["materias"]:
            mat_dir = base / materia["slug"]
            mat_dir.mkdir(parents=True, exist_ok=True)
            (mat_dir / "index.html").write_text(
                pagina_materia(materia, concurso, Path(materia["dir"])), encoding="utf-8")
            n_paginas += 1

            for assunto in materia["assuntos"]:
                origem_dir = Path(assunto["resumo_md"]).parent
                a_dir = mat_dir / assunto["slug"]
                a_dir.mkdir(parents=True, exist_ok=True)
                (a_dir / "index.html").write_text(
                    pagina_assunto(assunto, materia, concurso, origem_dir, a_dir),
                    encoding="utf-8")
                n_paginas += 1

    # manifesto deste concurso (alimenta o índice raiz)
    meta = modelo.get("meta", {})
    (base / ".concurso.json").write_text(json.dumps({
        "concurso": concurso,
        "slug": slug_conc,
        "orgao": meta.get("orgao") or re.split(r"[_-]", concurso)[0],
        "banca": meta.get("banca"),
        "prova_data": (meta.get("datas_chave") or {}).get("prova_data"),
        "n_materias": modelo["resumo"]["n_materias"],
        "n_assuntos": modelo["resumo"]["n_assuntos"],
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    n_concursos = 0
    if com_raiz:
        manifestos = ler_manifestos(destino)
        (destino / "index.html").write_text(pagina_raiz(manifestos), encoding="utf-8")
        n_paginas += 1
        n_concursos = len(manifestos)

    return {"paginas": n_paginas, "concurso": concurso,
            "destino": str(base), "concursos_no_indice": n_concursos}


def main():
    ap = argparse.ArgumentParser(description="Gera o site estático de um concurso")
    ap.add_argument("--concurso-dir", type=Path, default=None)
    ap.add_argument("--modelo", type=Path, default=None,
                    help="usar um site-model.json já coletado")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if args.modelo:
        modelo = json.loads(args.modelo.read_text(encoding="utf-8"))
    elif args.concurso_dir:
        if not args.concurso_dir.is_dir():
            sys.stderr.write(f"ERRO: não é diretório: {args.concurso_dir}\n")
            sys.exit(1)
        modelo = coletar_concurso(args.concurso_dir)
    else:
        sys.stderr.write("ERRO: informe --concurso-dir ou --modelo\n")
        sys.exit(1)

    if modelo["resumo"]["n_assuntos"] == 0:
        sys.stderr.write("AVISO: nenhum assunto aprofundado — o site sairá vazio.\n")

    r = construir(modelo, args.out)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
