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
from pathlib import Path, PurePosixPath

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


# --------------------------------------------------------------------------- #
# rotas: onde cada página mora, decidido ANTES de renderizar
# --------------------------------------------------------------------------- #
# Toda rota é um caminho POSIX relativo à raiz do site, e todo link emitido é
# relativo — é o que permite servir o mesmo site na raiz ou num subpath.
def prefixo_de(rota: str) -> str:
    """Caminho da página até a raiz: `a/b/index.html` → `../../`."""
    return "../" * (len(PurePosixPath(rota).parts) - 1)


def relativo(destino: str, de_rota: str) -> str:
    """URL relativa da página em `de_rota` até `destino` (rota, âncora opcional).

    Substitui os prefixos literais (`"../"`, `"../../"`, `"../../../"`) que
    estavam espalhados pelos templates. Cada nível novo de pasta exigia acertar
    todos eles na mão, e prefixo errado é historicamente a regressão mais comum
    desta skill.
    """
    alvo, _, frag = destino.partition("#")
    partes = PurePosixPath(alvo).parts
    dir_alvo, nome_alvo = partes[:-1], partes[-1]
    dir_atual = PurePosixPath(de_rota).parts[:-1]
    i = 0
    while i < len(dir_atual) and i < len(dir_alvo) and dir_atual[i] == dir_alvo[i]:
        i += 1
    passos = [".."] * (len(dir_atual) - i) + list(dir_alvo[i:]) + [nome_alvo]
    return "/".join(passos) + (f"#{frag}" if frag else "")


class Rotas:
    """Índice `nome-de-arquivo-do-vault → rota no site`.

    Existe por causa do resolvedor de wikilinks: para virar `href`, `[[crase]]`
    precisa da URL de uma página que talvez ainda não tenha sido gerada. Num passo
    único isso é impossível — e era justamente por isso que o resolvedor anterior
    só conseguia ver assuntos irmãos da mesma matéria, deixando morto todo wikilink
    que atravessasse matéria ou apontasse para documento.

    Três classes de alvo, porque nem todo alvo é página:
      - **página**       → rota da página;
      - **artefato embutido** (flashcards) → rota da página que o hospeda + âncora;
      - **arquivo copiado** (mídia, anexo) → rota do arquivo dentro do site.
    Sem essa distinção, os 368 wikilinks de mídia dos pacotes NotebookLM viravam
    parede de link morto.
    """

    EXTENSOES = re.compile(
        r"\.(md|png|jpe?g|svg|webp|pdf|m4a|mp3|wav|ogg|mp4|webm|mov|csv|tsv|txt|pptx)$",
        re.IGNORECASE)

    def __init__(self) -> None:
        self._por_nome: dict[str, str] = {}

    @classmethod
    def chave(cls, nome: str) -> str:
        """Último segmento, sem extensão, minúsculo — como o Obsidian casa.

        Os wikilinks do SEDES usam caminho absoluto do vault
        (`[[_COMUM/03-APROFUNDAMENTO/…/crase]]`) e os do BB, nome nu (`[[crase]]`).
        Reduzir os dois ao basename faz as duas convenções caírem na mesma chave.
        """
        base = (nome or "").strip().rstrip("/").split("/")[-1]
        return cls.EXTENSOES.sub("", base).lower()

    def registrar(self, rota: str, *nomes: str, ancora: str = "") -> None:
        """Associa nomes do vault a uma rota. O primeiro registro vence, para uma
        página não ser sequestrada por um homônimo registrado depois."""
        destino = rota + (f"#{ancora}" if ancora else "")
        for nome in nomes:
            chave = self.chave(nome)
            if chave:
                self._por_nome.setdefault(chave, destino)

    def rota_de(self, nome: str) -> str | None:
        return self._por_nome.get(self.chave(nome))

    def resolvedor(self, rota_atual: str):
        """Closure no formato que o `md2html` espera: `alvo → href | None`."""
        def resolver(alvo: str) -> str | None:
            destino = self._por_nome.get(self.chave(alvo))
            return relativo(destino, rota_atual) if destino else None
        return resolver


def rota_irma(rota: str, *segmentos: str) -> str:
    """Rota de uma página vizinha, derivada da rota da página atual.

    A navegação interna do site NÃO pode passar pelo índice de nomes: ele resolve
    por basename e o primeiro registro vence, então com `lingua-portuguesa` no
    `_COMUM` e no cargo, o hub do cargo apontava para a matéria do comum e a sua
    própria ficava órfã. O índice existe para wikilink, onde a ambiguidade é
    inerente; link de navegação é sempre explícito.
    """
    return "/".join([str(PurePosixPath(rota).parent), *segmentos, "index.html"])


def rota_anexo(rota_secao: str, anexo: dict) -> str:
    """Rota de um anexo dentro da seção, preservando a subpasta do vault.

    Fonte única: o registro em `montar_rotas`, o link na página e a cópia do arquivo
    usam esta mesma função. Calcular em três lugares seria convite a divergir — e
    nomes de arquivo repetem entre cargos (`cronograma-macro.md` existe em três),
    então resolver por nome levaria ao arquivo do cargo errado.
    """
    sub = (anexo["subpasta"] + "/") if anexo["subpasta"] else ""
    return f'{PurePosixPath(rota_secao).parent}/arquivos/{sub}{anexo["arquivo"]}'


def ident_aprof(ap: dict, indice: int = 0) -> str:
    """Identificador do aprofundamento usado em pasta de mídia e em `data-aprof`.
    Vive numa função só porque o builder o calculava em dois lugares — e os dois
    tinham de continuar concordando, ou a mídia ia para uma pasta e o HTML
    apontava para outra."""
    return re.sub(r"[^A-Za-z0-9_+-]+", "-",
                  ap.get("aprofundamento") or f"a{indice}")


def nome_escopo(nome: str) -> str:
    """Rótulo de exibição do escopo (`_COMUM` ou um cargo).

    O underscore de `_COMUM` é convenção de PASTA — existe para o Obsidian ordenar
    a pasta antes dos cargos. Numa página web ele lê como nome de arquivo vazado.
    O nome do cargo, ao contrário, fica como está: é o vocabulário que o usuário
    reconhece do edital e do vault.
    """
    if nome in ("_GERAL", ""):
        return ""                      # escopo implícito: não há o que rotular
    if nome == "_COMUM":
        return "Comum a todos os cargos"
    return nome


def pagina(titulo: str, trilha_html: str, corpo: str, rota: str,
           descricao: str = "") -> str:
    """Esqueleto comum. `rota` é o caminho da própria página relativo à raiz do
    site; o prefixo até os assets sai dela, em vez de ser contado à mão."""
    prefixo = prefixo_de(rota)
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
    # id âncora: os flashcards não são página própria, então os wikilinks que
    # apontam para o `.md` do baralho são resolvidos para cá (ver Rotas)
    return f"""<section class="cartao quiz" id="flashcards">
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
                         indice: int, ativo: bool,
                         rotas: "Rotas", rota: str) -> tuple[str, str]:
    """Renderiza UM aprofundamento: corpo (coluna esquerda) + cartões (lateral)."""
    origem_dir = Path(ap["resumo_md"]).parent

    corpo_md = Path(ap["resumo_md"]).read_text(encoding="utf-8")
    corpo_html = md2html.converter(corpo_md,
                                   wikilink_resolver=rotas.resolvedor(rota))

    # mídias deste aprofundamento vão para media/<id>/ (não colidem entre si)
    ident = ident_aprof(ap, indice)
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
            corpo_html += (f'\n<h2 id="relatorio">Relatório {baixar(src, "baixar")}</h2>\n'
                           + md2html.converter(
                               (origem_dir / rep).read_text(encoding="utf-8"),
                               wikilink_resolver=rotas.resolvedor(rota)))
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
                   destino_dir: Path, rotas: "Rotas", rota: str,
                   rota_materia: str, rota_capa: str,
                   rota_notebooklm: str | None = None) -> str:
    titulo = assunto["titulo"]
    aprofs = assunto.get("aprofundamentos") or []

    corpos, laterais, abas = [], [], []
    for i, ap in enumerate(aprofs):
        ativo = (i == 0)
        c, l = bloco_aprofundamento(ap, materia, assunto, destino_dir, i, ativo,
                                    rotas, rota)
        corpos.append(c)
        laterais.append(l)
        ident = ident_aprof(ap, i)
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
      {f'<a class="botao secundario" style="margin-top:.7rem" '
       f'href="{esc(relativo(rota_notebooklm, rota))}">Pacote NotebookLM</a>'
       if rota_notebooklm else ''}
    </section>
    {"".join(laterais)}
  </aside>
</div>"""

    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="{relativo(rota_materia, rota)}">{esc(materia["nome"])}</a> › '
              f'{esc(titulo)}')
    descricao = ""
    if aprofs:
        try:
            descricao = md2html.primeiro_paragrafo(
                Path(aprofs[0]["resumo_md"]).read_text(encoding="utf-8"), limite=180)
        except Exception:
            descricao = ""
    return pagina(f"{titulo} — {nome_legivel(concurso)}", trilha, corpo, rota,
                  descricao)


def bloco_pack(pack: dict, ap: dict, ativo: bool, ident: str) -> str:
    """Um pacote NotebookLM: as fontes a subir e os prompts a colar.

    Esta é a única página do site cuja razão de existir é uma **ação**, não leitura —
    daí o prompt vir com botão de copiar e o roteiro de cliques ao lado. O vault tem
    92 pacotes prontos e um único assunto com mídia de verdade: o gargalo não é ter o
    roteiro, é executá-lo 92 vezes.
    """
    fontes = "".join(
        f'<li>{md2html.converter(f, pular_frontmatter=False)}</li>'
        for f in pack["fontes"])

    prompts = []
    for p in pack["prompts"]:
        roteiro = "".join(f"<li>{esc(l)}</li>" for l in p["roteiro"])
        prompts.append(f"""<section class="cartao prompt">
  <div class="titulo-linha">
    <h3>{p["icone"]} {esc(p["rotulo"])}</h3>
    <button class="baixar copiar" type="button" data-copiar>⧉ Copiar</button>
  </div>
  <pre class="texto-prompt">{esc(p["prompt"])}</pre>
  {f'<ul class="roteiro">{roteiro}</ul>' if roteiro else ''}
</section>""")

    perguntas = "".join(f"<li>{esc(q)}</li>" for q in pack["perguntas"])
    checklist = "".join(
        f'<li class="tarefa {"feito" if c["feito"] else "aberto"}">'
        f'<span class="bolha" aria-hidden="true"></span><span>{esc(c["texto"])}</span></li>'
        for c in pack["checklist"])

    botao = ""
    if pack["url"]:
        botao = (f'<a class="botao" target="_blank" rel="noopener" '
                 f'href="{esc(pack["url"])}">Abrir no NotebookLM</a>')
    else:
        botao = ('<p class="meta">Sem link salvo. Depois de criar o notebook, '
                 'preencha <code>notebooklm_url:</code> no pacote, no vault.</p>')

    midias_prontas = [rot for chave, (_p, _e, ic, rot) in CATALOGO_MIDIAS.items()
                      if ap["midias"].get(chave)]
    estado = (f'<p class="meta">Já gerado: {esc(", ".join(midias_prontas))}.</p>'
              if midias_prontas
              else '<p class="meta">Nada gerado ainda para este aprofundamento.</p>')

    cls = "aprof" + (" ativo" if ativo else "")
    return f"""<div class="{cls}" data-aprof="{esc(ident)}">
  <section class="papel">
    <h2 id="fontes">1 · Fontes para subir no notebook</h2>
    <ol class="fontes-pack">{fontes}</ol>
    {estado}
    {botao}
  </section>
  <div class="grade-prompts">{"".join(prompts)}</div>
  <section class="papel" style="margin-top:1.25rem">
    <h2 id="perguntas">Perguntas úteis no chat</h2>
    <ul>{perguntas}</ul>
    <h2 id="checklist">Checklist</h2>
    <ul class="tarefas">{checklist}</ul>
    <p class="meta">O progresso vem do vault e é só leitura — marque no Obsidian.</p>
  </section>
</div>"""


def pagina_notebooklm(assunto: dict, materia: dict, concurso: str, rotas: "Rotas",
                      rota: str, rota_assunto: str, rota_capa: str) -> str:
    """Uma página por ASSUNTO, com abas por aprofundamento.

    Não uma por pacote: entre `padrao--X` e `detalhado--X` só o prompt de áudio
    difere — o resto é nome de arquivo. Página por aprofundamento daria 92 páginas com
    ~95% de conteúdo repetido, e o seletor em abas já existe.
    """
    packs = [(ap, ap.get("pack_notebooklm")) for ap in assunto["aprofundamentos"]]
    packs = [(ap, p) for ap, p in packs if p]
    if not packs:
        return ""

    corpos, abas = [], []
    for i, (ap, p) in enumerate(packs):
        ident = ident_aprof(ap, i)
        corpos.append(bloco_pack(p, ap, i == 0, ident))
        abas.append(f'<button class="aba{" ativa" if i == 0 else ""}" '
                    f'data-alvo="{esc(ident)}" type="button">'
                    f'{esc(rotulo_aprof(ap))}</button>')

    seletor = ""
    if len(packs) > 1:
        seletor = (f'<div class="seletor-aprof" role="tablist" '
                   f'aria-label="Aprofundamentos"><span class="rotulo">Pacote de</span>'
                   f'{"".join(abas)}</div>')

    corpo = f"""<div class="papel cabecalho-assunto">
  <div class="sobrancelha">NotebookLM · {esc(materia["nome"])}</div>
  <h1>{esc(assunto["titulo"])}</h1>
  <p class="meta">Roteiro e prompts para gerar as mídias no Estúdio do NotebookLM.</p>
  {seletor}
</div>
{"".join(corpos)}"""
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="{relativo(rota_assunto, rota)}">{esc(assunto["titulo"])}</a> › '
              f'NotebookLM')
    return pagina(f'NotebookLM: {assunto["titulo"]} — {nome_legivel(concurso)}',
                  trilha, corpo, rota)


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


def card_assunto(a: dict, href: str) -> str:
    pag = (f'<span class="meta">págs. {esc(a["paginas_livro"])}</span>'
           if a.get("paginas_livro") else "")
    return f"""<a class="item" href="{esc(href)}">
  <h3>{esc(a["titulo"])}</h3>
  {pag}
  {selos_aprofundamento(a)}
  {selos_midia(a)}
  {gabarito(a["progresso"], max_bolhas=8)}
</a>"""


def assuntos_do_topico(topico: dict, materia: dict) -> list[str]:
    """Assuntos aprofundados que correspondem a um tópico do mapa.

    **Só casamento exato**, e é uma decisão, não uma limitação de tempo. Derivar por
    slugificação daria link errado na maior parte: dos 203 tópicos dos 24 mapas do
    vault, só ~18% casam por slug. No SEDES o tópico "Domínio da estrutura
    morfossintática do período" explode em 7 assuntos; nas matérias de "lei como
    fonte" o assunto É uma norma, e a relação é N:M; e 9 assuntos de Português do
    SEDES foram reaproveitados do BB, então os slugs seguem o edital do outro
    concurso.

    O risco não é a ausência de link — é o falso negativo: tópico sem link lido como
    "não tem aprofundamento" quando ele existe com outro nome, escondendo trabalho
    já feito. Por isso, sem casamento, a página **não afirma nada**. Quem quiser o
    link fino preenche `mapa-aliases.json`.
    """
    slugs = {a["slug"] for a in materia["assuntos"]}
    aliases = materia.get("aliases_mapa") or {}
    alvo = aliases.get(_norm_txt(topico["titulo"]))
    if alvo:
        return [s for s in alvo if s in slugs]
    return [topico["slug"]] if topico["slug"] in slugs else []


def _norm_txt(s: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def bloco_plano(materia: dict, rotas: "Rotas", rota: str) -> str:
    """A aba **Plano**: o que o edital exige, tópico por tópico.

    O progresso do mapa é exibido separado do aprofundamento. Os 24 mapas do vault
    somam 2.220 checkboxes, nenhum marcado — jogá-los na mesma barra faria o
    progresso do aprofundamento desaparecer num denominador de milhares que ninguém
    pretende marcar pela web.
    """
    mapa = materia.get("mapa")
    if not mapa:
        return ""
    itens = []
    for t in mapa["topicos"]:
        alvos = assuntos_do_topico(t, materia)
        link = ""
        if alvos:
            hrefs = []
            for slug in alvos:
                hrefs.append(f'<a href="{esc(relativo(rota_irma(rota, slug), rota))}"'
                             f'>estudar</a>')
            link = f'<span class="ir">{" · ".join(hrefs)}</span>' if hrefs else ""
        subs = "".join(f"<li>{esc(s)}</li>" for s in t["subtopicos"])
        prio = (f'<span class="selo-aprof nivel-{t["prioridade"]}">'
                f'{esc(ROTULOS_PRIORIDADE[t["prioridade"]][0])}</span>'
                if t.get("prioridade") in ROTULOS_PRIORIDADE else "")
        pg = t["progresso"]
        itens.append(f"""<li class="topico">
  <div class="linha">
    <span class="num">{t["numero"]}</span>
    <h3 id="t{t["numero"]}">{esc(t["titulo"])}</h3>
    {prio}{link}
  </div>
  {f'<ul class="subtopicos">{subs}</ul>' if subs else ''}
  {f'<span class="meta">{pg["feitos"]}/{pg["total"]} itens do plano</span>' if pg["total"] else ''}
</li>""")

    aux = "".join(
        f'<section class="papel" style="margin-top:1rem">'
        f'<h2 id="{esc(md2html.slug_ancora(a["titulo"]))}">{esc(a["titulo"])}</h2>'
        f'{md2html.converter(a["corpo"], wikilink_resolver=rotas.resolvedor(rota))}'
        f'</section>'
        for a in mapa["auxiliares"] if a["corpo"].strip())

    prog = mapa["progresso"]
    resumo = (f'{mapa["n_topicos"]} tópicos do edital · '
              f'{prog["feitos"]}/{prog["total"]} itens do plano')
    return f"""<div class="visao plano ativo" data-visao="plano">
  <section class="papel">
    <p class="meta">{esc(resumo)}</p>
    <ol class="lista-topicos">{"".join(itens)}</ol>
  </section>
  {aux}
</div>"""


def bloco_cobertura(materia: dict, rotas: "Rotas", rota: str) -> str:
    """O que o vault AFIRMA sobre a cobertura, em vez de adivinhação.

    Existe porque o link fino tópico→assunto não é derivável (ver
    `assuntos_do_topico`). Em vez de inferir, mostra o que já está escrito: a lista
    real de assuntos aprofundados (varredura de pasta, a verdade do disco) e, quando
    a matéria tem, os documentos de cobertura e pendências que a Etapa 2 gerou.
    """
    partes = []
    if materia["assuntos"]:
        partes.append(f'<p>{materia["n_assuntos"]} assunto(s) aprofundado(s) — '
                      f'a lista completa está na visão <strong>Estudo</strong>.</p>')
    externo = materia.get("aprofundamento_em")
    if externo:
        conc = PurePosixPath(rota).parts[0]
        destino = (f'{conc}/{externo["escopo_slug"]}/materias/'
                   f'{externo["materia_slug"]}/index.html')
        if destino:
            partes.append(
                f'<p>O aprofundamento desta matéria fica em '
                f'<a href="{esc(relativo(destino, rota))}">'
                f'{esc(nome_escopo(externo["escopo_nome"]))}</a> — '
                f'{externo["n_assuntos"]} assunto(s), aproveitados por este cargo.</p>')
    for nome, rotulo in (("00-COBERTURA-LIVRO.md", "Cobertura do livro"),
                         ("00-PENDENCIAS-FORA-DO-LIVRO.md", "Fora do livro")):
        alvo = Path(materia["dir"]) / nome
        if alvo.exists():
            partes.append(f'<h3>{esc(rotulo)}</h3>'
                          + md2html.converter(alvo.read_text(encoding="utf-8"),
                                              wikilink_resolver=rotas.resolvedor(rota)))
    if not partes:
        return ""
    return (f'<section class="papel cobertura" style="margin-top:1.25rem">'
            f'<h2 id="cobertura">Cobertura desta matéria</h2>'
            f'{"".join(partes)}</section>')


def pagina_materia(materia: dict, concurso: str, materia_dir: Path,
                   rotas: "Rotas", rota: str, rota_capa: str) -> str:
    def href_de(a: dict) -> str:
        return relativo(rota_irma(rota, a["slug"]), rota)

    # agrupar por prioridade, na ordem alta -> média -> base -> sem classificação
    grupos = []
    for prio in PRIORIDADES:
        doss = [a for a in materia["assuntos"] if a.get("prioridade") == prio]
        if not doss:
            continue
        titulo, explica = ROTULOS_PRIORIDADE[prio]
        cards = "".join(card_assunto(a, href_de(a)) for a in doss)
        grupos.append(f"""<section class="grupo-prioridade" data-prio="{prio}">
  <header><h2>{esc(titulo)}</h2><span class="quantos">{len(doss)} assuntos</span></header>
  <p class="explica">{esc(explica)}</p>
  <div class="grade">{cards}</div>
</section>""")

    sem_prio = [a for a in materia["assuntos"] if not a.get("prioridade")]
    if sem_prio:
        cards = "".join(card_assunto(a, href_de(a)) for a in sem_prio)
        grupos.append(f"""<section class="grupo-prioridade" data-prio="sem">
  <header><h2>Demais assuntos</h2><span class="quantos">{len(sem_prio)} assuntos</span></header>
  <div class="grade">{cards}</div>
</section>""")

    # "Como a banca cobra esta matéria" — antes dos assuntos
    bloco_banca = ""
    if materia.get("doc_banca"):
        try:
            texto = (materia_dir / materia["doc_banca"]).read_text(encoding="utf-8")
            bloco_banca = (
                f'<section class="papel" style="margin-top:1.25rem">'
                f'{md2html.converter(texto, wikilink_resolver=rotas.resolvedor(rota))}'
                f'</section>')
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

    plano = bloco_plano(materia, rotas, rota)
    cobertura = bloco_cobertura(materia, rotas, rota)

    # Uma matéria, duas visões: Plano (o mapa do edital) e Estudo (os assuntos
    # aprofundados). São ângulos diferentes do MESMO recorte — separá-los em duas
    # páginas obrigaria a saber em qual procurar. Reusa o seletor em abas que já
    # existe na página de assunto, em vez de inventar componente.
    tem_estudo = bool(materia["assuntos"])
    seletor = ""
    if plano and tem_estudo:
        seletor = ('<div class="seletor-aprof" role="tablist" aria-label="Visões">'
                   '<span class="rotulo">Visão</span>'
                   '<button class="aba ativa" data-visao-alvo="plano" type="button">'
                   'Plano</button>'
                   '<button class="aba" data-visao-alvo="estudo" type="button">'
                   'Estudo</button></div>')

    estudo = ""
    if tem_estudo:
        ativo = " ativo" if not plano else ""
        estudo = (f'<div class="visao{ativo}" data-visao="estudo">'
                  f'{bloco_banca}{"".join(grupos)}{docs}{cobertura}</div>')
    elif cobertura:
        estudo = cobertura

    linha_resumo = []
    if tem_estudo:
        linha_resumo.append(f'{materia["n_assuntos"]} assuntos aprofundados')
        if materia["n_com_podcast"]:
            linha_resumo.append(f'{materia["n_com_podcast"]} com áudio')
        if materia["n_com_flashcards"]:
            linha_resumo.append(f'{materia["n_com_flashcards"]} com flashcards')

    corpo = f"""<div class="papel">
  <div class="sobrancelha">{esc(nome_legivel(concurso))}</div>
  <h1>{esc(materia["nome"])}</h1>
  {f'<p>{esc(" · ".join(linha_resumo))}</p>' if linha_resumo else ''}
  {f'<p class="meta">{esc(resumo_prio)}</p>' if resumo_prio else ''}
  {seletor}
</div>
{plano}
{estudo if (plano and tem_estudo) else (estudo or bloco_banca + "".join(grupos) + docs)}"""
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a>'
              f' › {esc(materia["nome"])}')
    return pagina(f'{materia["nome"]} — {nome_legivel(concurso)}', trilha, corpo, rota)


def tamanho_legivel(n: int) -> str:
    for unidade, limite in (("GB", 1 << 30), ("MB", 1 << 20), ("kB", 1 << 10)):
        if n >= limite:
            return f"{n / limite:.1f} {unidade}".replace(".0 ", " ")
    return f"{n} B"


def lista_documentos(secao: dict, rotas: "Rotas", rota: str) -> str:
    """As seções de CONSULTA num registro tipográfico, sem card.

    Card com sombra e progresso é para o que se estuda; transformar "Sinergia" em
    peer visual de "Crase" faria a página competir consigo mesma. Aqui a hierarquia
    é só tipográfica.
    """
    itens = []
    for doc in secao["documentos"]:
        href = rota_irma(rota, doc["slug"])
        meta = []
        if doc["n_secoes"]:
            meta.append(f'{doc["n_secoes"]} seções')
        if doc["progresso"]["total"]:
            meta.append(f'{doc["progresso"]["feitos"]}/{doc["progresso"]["total"]} itens')
        itens.append(
            f'<li><a href="{esc(relativo(href, rota))}">{esc(doc["titulo"])}</a>'
            + (f'<span class="meta">{esc(" · ".join(meta))}</span>' if meta else "")
            + (f'<p class="resumo">{esc(doc["resumo"])}</p>' if doc["resumo"] else "")
            + "</li>")
    return f'<ul class="lista-docs">{"".join(itens)}</ul>' if itens else ""


def lista_anexos(secao: dict, rotas: "Rotas", rota: str) -> str:
    """Anexos com tamanho, para o peso ser visível ANTES do clique — há PDF de
    quase 10 MB, e quem abre no celular na rede doméstica agradece o aviso."""
    if not secao["anexos"]:
        return ""
    itens = []
    for a in secao["anexos"]:
        rel = relativo(rota_anexo(rota, a), rota)
        itens.append(
            f'<li><span class="rot">{esc(a["arquivo"])}</span>'
            f'<span class="meta">{esc(tamanho_legivel(a["bytes"]))}</span>'
            f'<a class="baixar" href="{esc(rel)}" download="{esc(a["arquivo"])}">'
            f'⤓ Baixar</a></li>')
    total = tamanho_legivel(secao["bytes_anexos"])
    return (f'<section class="papel" style="margin-top:1.5rem">'
            f'<h2 id="arquivos">Arquivos ({secao["n_anexos"]} · {esc(total)})</h2>'
            f'<ul class="midias-extra">{"".join(itens)}</ul></section>')


def pagina_escopo(escopo: dict, concurso: str, rotas: "Rotas", rota: str,
                  rota_capa: str) -> str:
    """Hub de um escopo (`_COMUM` ou um cargo).

    Focal: as matérias, que é onde se estuda. Depois as seções de estudo, e por
    último as de consulta, num registro visivelmente mais quieto.
    """
    rotulo = nome_escopo(escopo["nome"]) or nome_legivel(concurso)

    grupos = []
    if escopo["materias"]:
        cards = []
        for mat in escopo["materias"]:
            href = relativo(rota_irma(rota, "materias", mat["slug"]), rota)
            cards.append(f"""<a class="item" href="{esc(href)}">
  <h3>{esc(mat["nome"])}</h3>
  <div class="meta">{mat["n_assuntos"]} assuntos · {mat["n_com_podcast"]} com áudio</div>
</a>""")
        grupos.append(f"""<section class="grupo grupo-escopo">
  <header><h2>Matérias</h2>
  <span class="quantos">{len(escopo["materias"])} matérias ·
  {escopo["n_assuntos"]} assuntos</span></header>
  <div class="grade">{"".join(cards)}</div>
</section>""")

    for registro, titulo, explica in (
            ("estudo", "Estudo e planejamento",
             "O que fazer e como treinar."),
            ("consulta", "Consulta",
             "As regras, as fontes e o histórico — para conferir quando precisar.")):
        secoes = [s for s in escopo["secoes"] if s["registro"] == registro]
        if not secoes:
            continue
        blocos = []
        for s in secoes:
            # a rota da seção é sempre `{escopo}/{slug}/index.html`, mesmo quando ela
            # foi colapsada no documento único — o caminho é o mesmo, muda o conteúdo
            href = relativo(f'{PurePosixPath(rota).parent}/{s["slug"]}/index.html', rota)
            n = []
            if s["n_documentos"] > 1:
                n.append(f'{s["n_documentos"]} documentos')
            if s["n_anexos"]:
                n.append(f'{s["n_anexos"]} arquivo(s) · {tamanho_legivel(s["bytes_anexos"])}')
            blocos.append(
                f'<li><span class="ordinal">{esc(s["ordinal"])}</span>'
                f'<a href="{esc(href)}">{esc(s["rotulo"])}</a>'
                f'<span class="meta">{esc(" · ".join(n))}</span></li>')
        grupos.append(f"""<section class="grupo grupo-escopo" data-registro="{registro}">
  <header><h2>{esc(titulo)}</h2><span class="quantos">{len(secoes)} seções</span></header>
  <p class="explica">{esc(explica)}</p>
  <ul class="lista-secoes">{"".join(blocos)}</ul>
</section>""")

    prog = escopo.get("progresso") or {}
    corpo = f"""<div class="papel">
  <div class="sobrancelha">{esc(nome_legivel(concurso))}</div>
  <h1>{esc(rotulo)}</h1>
  {gabarito(prog) if prog.get("total") else ""}
</div>
<div style="margin-top:1.25rem">{"".join(grupos)}</div>"""
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a>'
              f' › {esc(rotulo)}')
    return pagina(f"{rotulo} — {nome_legivel(concurso)}", trilha, corpo, rota)


def pagina_secao(secao: dict, escopo: dict, concurso: str, rotas: "Rotas",
                 rota: str, rota_escopo: str, rota_capa: str) -> str:
    """Índice de uma seção: seus documentos e seus anexos."""
    rotulo_esc = nome_escopo(escopo["nome"]) or nome_legivel(concurso)
    corpo = f"""<div class="papel">
  <div class="sobrancelha">{esc(secao["ordinal"])} · {esc(rotulo_esc)}</div>
  <h1>{esc(secao["rotulo"])}</h1>
  {lista_documentos(secao, rotas, rota)}
</div>
{lista_anexos(secao, rotas, rota)}"""
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="{relativo(rota_escopo, rota)}">{esc(rotulo_esc)}</a> › '
              f'{esc(secao["rotulo"])}')
    return pagina(f'{secao["rotulo"]} — {nome_legivel(concurso)}', trilha, corpo, rota)


def bloco_sumario(md: str, rota_atual: str) -> str:
    """Índice de seções na lateral, quando o documento é longo o bastante.

    Reusa `.colunas`/`.lateral` da página de assunto em vez de inventar layout: os
    documentos do vault têm de 50 a 2.400 linhas, e rolar 600 linhas sem índice é o
    que faz a pessoa desistir e voltar ao Obsidian.
    """
    itens = md2html.sumario(md)
    if len(itens) < 4:
        return ""
    links = "".join(
        f'<li class="n{x["nivel"]}"><a href="#{esc(x["id"])}">{esc(x["texto"])}</a></li>'
        for x in itens)
    return (f'<section class="cartao sumario"><h3>Nesta página</h3>'
            f'<ul>{links}</ul></section>')


def pagina_documento(doc: dict, secao: dict, escopo: dict, concurso: str,
                     rotas: "Rotas", rota: str, trilha_meio: tuple,
                     rota_capa: str) -> str:
    md = Path(doc["caminho"]).read_text(encoding="utf-8")
    corpo_html = md2html.converter(md, wikilink_resolver=rotas.resolvedor(rota))
    sumario = bloco_sumario(md, rota)

    if sumario:
        corpo = (f'<div class="colunas">'
                 f'<article class="papel">{corpo_html}</article>'
                 f'<aside class="lateral">{sumario}</aside></div>')
    else:
        corpo = f'<article class="papel">{corpo_html}</article>'

    # o nível do meio da trilha é a seção quando ela tem índice próprio, e o escopo
    # quando a seção É este documento
    rota_meio, rotulo_meio = trilha_meio
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="{relativo(rota_meio, rota)}">{esc(rotulo_meio)}</a> › '
              f'{esc(doc["titulo"])}')
    return pagina(f'{doc["titulo"]} — {nome_legivel(concurso)}', trilha, corpo, rota,
                  doc.get("resumo", ""))


def pagina_capa(modelo: dict, rotas: "Rotas", rota: str) -> str:
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

    # Um card por escopo — o galho, não a matéria. A grade de matérias, que ficava
    # aqui, desceu para o hub do escopo: na capa o que importa é escolher o cargo.
    cards = []
    for escopo in modelo.get("escopos") or modelo["cargos"]:
        href = relativo(rota_irma(rota, escopo["slug"]), rota)
        n = [f'{escopo["n_materias"]} matéria(s)',
             f'{escopo["n_assuntos"]} assunto(s)']
        n_docs = sum(s["n_documentos"] for s in escopo.get("secoes") or [])
        if n_docs:
            n.append(f"{n_docs} documento(s)")
        prog = escopo.get("progresso") or {}
        cards.append(f"""<a class="item concurso-item" href="{esc(href)}">
  <h3>{esc(nome_escopo(escopo["nome"]) or "Material")}
  {'<span class="tag">comum</span>' if escopo["tipo"] == "comum" else ""}</h3>
  <div class="meta">{esc(" · ".join(n))}</div>
  {gabarito(prog, max_bolhas=8) if prog.get("total") else ""}
</a>""")

    r = modelo["resumo"]
    resumo_txt = (f'{r["n_materias"]} matéria(s) · {r["n_assuntos"]} assuntos '
                  f'aprofundados · {r.get("n_documentos", 0)} documento(s)')
    corpo = f"""<div class="papel">
  <div class="sobrancelha">Preparação</div>
  <h1>{esc(nome_legivel(modelo["concurso"]))}</h1>
  {ficha}
  <p>{esc(resumo_txt)}</p>
</div>
<div class="grade" style="margin-top:1.25rem">{"".join(cards)}</div>"""
    trilha = f'<a href="{relativo("index.html", rota)}">Concursos</a>'
    return pagina(nome_legivel(modelo["concurso"]), trilha, corpo, rota)


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def pagina_raiz(concursos: list[dict]) -> str:
    """Índice de TODOS os concursos publicados (a porta de entrada do site)."""
    if not concursos:
        corpo = ('<div class="papel"><h1>Nenhum concurso publicado</h1>'
                 '<p>Gere um concurso com a skill <code>concurso-publica</code>.</p></div>')
        return pagina("Estudo para concursos", "", corpo, "index.html")

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
    return pagina("Estudo para concursos", "", corpo, "index.html")


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


def copiar_anexos(secao: dict, destino: Path, rota_secao: str) -> None:
    """Copia os anexos da seção para dentro do site, na rota já registrada.

    O site precisa ser autossuficiente: servido pelo nginx a partir de `/srv/site`,
    nada que esteja fora dessa pasta é alcançável pelo navegador. Sem a cópia, o
    link da lei funcionaria só na máquina do vault.
    """
    for a in secao["anexos"]:
        alvo = destino / rota_anexo(rota_secao, a)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        origem = Path(a["caminho"])
        # o rmtree do concurso já limpou; a checagem cobre anexo homônimo em duas
        # subpastas da mesma seção, que resolveria para a mesma rota
        if not alvo.exists():
            shutil.copy2(origem, alvo)


def montar_rotas(modelo: dict, slug_conc: str) -> tuple[Rotas, list[dict]]:
    """Passo 1 do build: decide onde cada página mora e indexa os nomes do vault.

    Roda ANTES de qualquer renderização, porque o resolvedor de wikilinks precisa
    conhecer a URL de páginas que ainda não existem. Devolve o índice de rotas e o
    plano de renderização (a lista do que gerar, na ordem).
    """
    rotas = Rotas()
    plano: list[dict] = []

    rota_capa = f"{slug_conc}/index.html"
    # o 00-INDICE do vault é o índice do concurso: quem aponta para ele vai à capa
    rotas.registrar(rota_capa, modelo["concurso"], "00-INDICE")
    plano.append({"rota": rota_capa, "tipo": "capa"})

    for escopo in modelo.get("escopos") or modelo["cargos"]:
        esc_slug = escopo.get("slug") or "geral"
        rota_esc = f"{slug_conc}/{esc_slug}/index.html"
        # o `99-Status` não vira página (a navegação do site é o índice), mas quem
        # aponta para ele quer o progresso — que é justamente o que o hub mostra
        rotas.registrar(rota_esc, escopo["nome"], "99-Status")
        plano.append({"rota": rota_esc, "tipo": "escopo", "escopo": escopo,
                      "rota_capa": rota_capa})

        for secao in escopo.get("secoes") or []:
            rota_sec = f'{slug_conc}/{esc_slug}/{secao["slug"]}/index.html'
            rotulo_esc = nome_escopo(escopo["nome"])

            # Seção com um documento só e sem anexo É o documento. Um índice que
            # lista um único item é página inútil, e gerava caminho redundante
            # (`titulos/titulos/`, `cronograma/cronograma-macro/`).
            if len(secao["documentos"]) == 1 and not secao["anexos"]:
                doc = secao["documentos"][0]
                rotas.registrar(rota_sec, doc["arquivo"], doc["slug"], secao["slug"])
                plano.append({"rota": rota_sec, "tipo": "documento", "doc": doc,
                              "secao": secao, "escopo": escopo,
                              "trilha_meio": (rota_esc, rotulo_esc),
                              "rota_capa": rota_capa})
                continue

            plano.append({"rota": rota_sec, "tipo": "secao", "secao": secao,
                          "escopo": escopo, "rota_escopo": rota_esc,
                          "rota_capa": rota_capa})

            for doc in secao["documentos"]:
                rota_doc = (f'{slug_conc}/{esc_slug}/{secao["slug"]}'
                            f'/{doc["slug"]}/index.html')
                # o documento é citado pelo nome do arquivo (com e sem prefixo
                # numérico) — as duas formas aparecem nos wikilinks do vault
                rotas.registrar(rota_doc, doc["arquivo"], doc["slug"])
                plano.append({"rota": rota_doc, "tipo": "documento", "doc": doc,
                              "secao": secao, "escopo": escopo,
                              "trilha_meio": (rota_sec, secao["rotulo"]),
                              "rota_capa": rota_capa})

            # anexos: rota determinística, registrada antes da cópia, para que os
            # wikilinks que apontam direto para o PDF da lei resolvam
            for anexo in secao["anexos"]:
                rotas.registrar(rota_anexo(rota_sec, anexo), anexo["arquivo"])

        for materia in escopo["materias"]:
            rota_mat = f'{slug_conc}/{esc_slug}/materias/{materia["slug"]}/index.html'
            rotas.registrar(rota_mat, materia["slug"],
                            f'00-INDICE-{materia["slug"]}')
            plano.append({"rota": rota_mat, "tipo": "materia", "materia": materia,
                          "escopo": escopo, "rota_escopo": rota_esc,
                          "rota_capa": rota_capa})

            for assunto in materia["assuntos"]:
                rota_a = (f'{slug_conc}/{esc_slug}/materias/{materia["slug"]}'
                          f'/{assunto["slug"]}/index.html')
                aprofs = assunto.get("aprofundamentos") or []
                # 1ª classe — página: o slug da pasta e o nome de cada .md de
                # aprofundamento (o Obsidian resolve por nome de arquivo, e o nome
                # completo é `{assunto}--{nivel}--{fonte}--{CONCURSO}`)
                nomes = [assunto["slug"]] + [Path(a["resumo_md"]).stem for a in aprofs]
                rotas.registrar(rota_a, *nomes)

                for i, ap in enumerate(aprofs):
                    ident = ident_aprof(ap, i)
                    # 2ª classe — artefato embutido: flashcards não são página,
                    # então o wikilink do baralho vai para a âncora do quiz
                    for chave in ("obsidian", "anki"):
                        fc = (ap.get("flashcards") or {}).get(chave)
                        if fc:
                            rotas.registrar(rota_a, fc, ancora="flashcards")
                    # 3ª classe — arquivo copiado: mídia vive em media/<ident>/.
                    # A rota é determinística, então dá para registrar aqui, antes
                    # da cópia — e é o que impede os 368 wikilinks de mídia dos
                    # pacotes NotebookLM de virarem parede de link morto.
                    for nome in (ap.get("midias") or {}).values():
                        if nome:
                            rotas.registrar(
                                f'{slug_conc}/{esc_slug}/materias/{materia["slug"]}'
                                f'/{assunto["slug"]}/media/{ident}/{nome}', nome)

                rota_nb = (f'{slug_conc}/{esc_slug}/materias/{materia["slug"]}'
                           f'/{assunto["slug"]}/notebooklm/index.html')
                tem_pack = any(ap.get("pack_notebooklm") for ap in aprofs)
                plano.append({"rota": rota_a, "tipo": "assunto", "assunto": assunto,
                              "materia": materia, "escopo": escopo,
                              "rota_materia": rota_mat, "rota_capa": rota_capa,
                              "rota_notebooklm": rota_nb if tem_pack else None})
                if tem_pack:
                    rotas.registrar(rota_nb, f'_fonte-notebooklm-{assunto["slug"]}')
                    plano.append({"rota": rota_nb, "tipo": "notebooklm",
                                  "assunto": assunto, "materia": materia,
                                  "rota_assunto": rota_a, "rota_capa": rota_capa})
    return rotas, plano


def construir(modelo: dict, destino: Path, com_raiz: bool = True) -> dict:
    """Gera o site de UM concurso em destino/<slug-do-concurso>/ e (re)gera o
    índice raiz listando todos os concursos publicados em destino/."""
    destino.mkdir(parents=True, exist_ok=True)

    concurso = modelo["concurso"]
    slug_conc = re.sub(r"[^A-Za-z0-9_-]+", "-", concurso).strip("-").lower()
    base = destino / slug_conc

    # Limpar SÓ a pasta deste concurso antes de gerar. Sem isso, quando a
    # estrutura de pastas muda, o layout antigo sobrevive em out/ — e o
    # `rsync --delete` do deploy NÃO o remove, porque ele existe na origem.
    # O escopo é deliberado: apagar `destino` mataria os concursos irmãos e o
    # assets/ compartilhado, e o índice raiz é remontado dos manifestos.
    #
    # Custo conhecido: a mídia é recopiada a cada build (um podcast passa de
    # 70 MB). O deploy não sofre — `copy2` preserva o mtime, então o rsync
    # continua incremental — mas o disco local reescreve tudo. A correção certa é
    # varrer por diferença contra o conjunto de arquivos efetivamente escritos, o
    # que fica natural quando a tabela de rotas existir; guarda de mtime aqui não
    # resolveria nada, porque o rmtree apaga a mídia antes da comparação.
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)

    # assets ficam na raiz e são compartilhados por todos os concursos
    dest_assets = destino / "assets"
    dest_assets.mkdir(exist_ok=True)
    for nome in ("site.css", "site.js"):
        origem = ASSETS / nome
        if origem.exists():
            shutil.copy2(origem, dest_assets / nome)

    # ---- passo 1: decidir as rotas ----------------------------------------- #
    rotas, plano = montar_rotas(modelo, slug_conc)

    # ---- passo 2: renderizar ---------------------------------------------- #
    n_paginas = 0
    rota_capa = f"{slug_conc}/index.html"
    for item in plano:
        rota = item["rota"]
        alvo = destino / rota
        alvo.parent.mkdir(parents=True, exist_ok=True)
        tipo = item["tipo"]
        if tipo == "capa":
            html_pag = pagina_capa(modelo, rotas, rota)
        elif tipo == "escopo":
            html_pag = pagina_escopo(item["escopo"], concurso, rotas, rota, rota_capa)
        elif tipo == "secao":
            html_pag = pagina_secao(item["secao"], item["escopo"], concurso, rotas,
                                    rota, item["rota_escopo"], rota_capa)
            copiar_anexos(item["secao"], destino, rota)
        elif tipo == "documento":
            html_pag = pagina_documento(item["doc"], item["secao"], item["escopo"],
                                        concurso, rotas, rota, item["trilha_meio"],
                                        rota_capa)
            # seção de documento único não tem página de índice, então é aqui que
            # os anexos dela (se houver) seriam copiados — hoje não há, por
            # construção, mas manter a chamada evita anexo órfão se a regra mudar
            copiar_anexos(item["secao"], destino, rota)
        elif tipo == "materia":
            html_pag = pagina_materia(item["materia"], concurso,
                                      Path(item["materia"]["dir"]),
                                      rotas, rota, item["rota_escopo"])
        elif tipo == "notebooklm":
            html_pag = pagina_notebooklm(item["assunto"], item["materia"], concurso,
                                         rotas, rota, item["rota_assunto"], rota_capa)
        else:
            html_pag = pagina_assunto(item["assunto"], item["materia"], concurso,
                                      alvo.parent, rotas, rota,
                                      item["rota_materia"], rota_capa,
                                      item.get("rota_notebooklm"))
        alvo.write_text(html_pag, encoding="utf-8")
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
