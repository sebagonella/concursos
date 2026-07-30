#!/usr/bin/env python3
"""
md2html.py - Conversor Markdown -> HTML mínimo, sem dependências externas.

Cobre o subconjunto de Markdown que as skills deste projeto geram:
headings, negrito, itálico, código inline, listas, checkboxes, blockquote,
tabelas, links, wikilinks, separadores e parágrafos.

Não pretende ser um parser completo de CommonMark — pretende ser previsível,
testável e suficiente para o nosso conteúdo, sem trazer dependência para um
site que precisa funcionar offline.
"""
import html
import re
import unicodedata


# --------------------------------------------------------------------------- #
# âncoras e sumário
# --------------------------------------------------------------------------- #
def slug_ancora(texto: str) -> str:
    """Slug de heading, usado como `id` e como destino de `[[nota#seção]]`.

    Tem de ser a MESMA função nos dois lados: se o id do heading e a âncora do
    wikilink forem slugificados de formas diferentes, o link aponta para um id que
    não existe e o navegador não vai a lugar nenhum.
    """
    t = re.sub(r"<[^>]+>", "", texto or "")          # pode chegar já com <strong>
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s-]", "", t).strip().lower()
    return re.sub(r"[\s_]+", "-", t) or "secao"


_FRONTMATTER = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def _headings(md: str, pular_frontmatter=True,
              prefixo_id="") -> list[tuple[int, str, str]]:
    """Headings do documento, em ordem: (nível, texto, id).

    Ignora `#` dentro de bloco de código cercado — senão um comentário Python
    viraria heading. Desambigua ids repetidos com sufixo numérico, e é a **única**
    fonte de ids: `converter()` consome esta lista, para o sumário e o corpo nunca
    divergirem.

    `prefixo_id` existe porque a aba Plano converte vários trechos SOLTOS na mesma
    página — um por tópico do mapa. A desambiguação por sufixo só enxerga o trecho
    que está convertendo, então o `#### Proteção Social Básica (PSB)` de dois
    tópicos diferentes sairia com o mesmo `id`: HTML inválido e âncora que pula
    para o tópico errado. Quem converte trecho solto passa `t{n}-`.
    """
    if pular_frontmatter:
        md = _FRONTMATTER.sub("", md, count=1)
    achados: list[tuple[int, str, str]] = []
    vistos: dict[str, int] = {}
    dentro_de_codigo = False
    for linha in md.split("\n"):
        if linha.strip().startswith("```"):
            dentro_de_codigo = not dentro_de_codigo
            continue
        if dentro_de_codigo:
            continue
        m = _HEADING.match(linha.strip())
        if not m:
            continue
        texto = m.group(2).strip()
        base = slug_ancora(texto)
        vistos[base] = vistos.get(base, 0) + 1
        ident = base if vistos[base] == 1 else f"{base}-{vistos[base]}"
        achados.append((len(m.group(1)), texto, prefixo_id + ident))
    return achados


def sumario(md: str, niveis=(2, 3)) -> list[dict]:
    """Índice de seções para a lateral: `[{"nivel", "texto", "id"}]`."""
    return [{"nivel": n, "texto": t, "id": i}
            for n, t, i in _headings(md) if n in niveis]


# --------------------------------------------------------------------------- #
# inline
# --------------------------------------------------------------------------- #
# Wikilink com âncora e com pipe escapado. Em tabela markdown o pipe do wikilink
# vem como `\|`, e sem tratar isso o alvo capturado fica com a barra no fim — era
# a origem de 74 falsos positivos no validador da concurso-prep, e os índices do
# BB usam essa forma dentro de células. O `!?` inicial consome o embed `![[x]]`,
# que antes deixava um "!" solto na frente do link.
#   1 = alvo · 2 = âncora · 3 = rótulo
WIKILINK_RE = re.compile(r"!?\[\[([^\]|#]+?)(?:#([^\]|]*))?(?:\\?\|([^\]]*))?\]\]")

# O texto já vem escapado, então `&` da query string chega como `&amp;` — que é
# exatamente a forma correta dentro de um href.
_URL_NUA = re.compile(r"https?://[^\s<>\"'\]]+")


def _autolink(m) -> str:
    """URL nua -> <a>. A pontuação final fica FORA do link: no vault a URL costuma
    fechar a frase (`…/questoes.`) e engolir o ponto levaria a um 404."""
    url = m.group(0)
    cauda = ""
    while url and url[-1] in ".,;:!?)":
        cauda = url[-1] + cauda
        url = url[:-1]
    if not url or url.endswith("//"):
        return m.group(0)
    return f'<a href="{url}">{url}</a>{cauda}'


def _inline(texto: str, wikilink_resolver=None) -> str:
    """Aplica formatação inline. O texto JÁ deve estar escapado."""
    # código inline primeiro (protege o conteúdo do resto)
    fragmentos: list[str] = []

    def _guardar(m):
        fragmentos.append(f"<code>{m.group(1)}</code>")
        return f"\x00{len(fragmentos) - 1}\x00"

    texto = re.sub(r"`([^`]+)`", _guardar, texto)

    # wikilinks [[alvo]], [[alvo|rotulo]], [[alvo#secao]], [[alvo#secao|rotulo]]
    def _wiki(m):
        alvo = m.group(1).strip()
        ancora = (m.group(2) or "").strip()
        # sem rótulo explícito, exibir só o último segmento: os wikilinks do SEDES
        # usam caminho absoluto do vault (`[[_COMUM/03-APROFUNDAMENTO/…/crase]]`) e
        # o caminho inteiro como texto visível é ruído — e vaza convenção de pasta
        rotulo = (m.group(3) or "").strip() or alvo.rstrip("/").split("/")[-1]
        if wikilink_resolver:
            href = wikilink_resolver(alvo)
            if href:
                if ancora:
                    href = f"{href}#{slug_ancora(ancora)}"
                return f'<a href="{href}">{rotulo}</a>'
        return f'<span class="wikilink-morto" title="não publicado">{rotulo}</span>'

    texto = WIKILINK_RE.sub(_wiki, texto)

    # imagens ANTES dos links: a regex de link casa o mesmo texto e deixaria o "!"
    # solto na frente de um <a> — era assim que toda imagem markdown saía quebrada
    texto = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                   r'<img src="\2" alt="\1" loading="lazy">', texto)

    # links markdown [texto](url)
    texto = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', texto)

    # negrito e itálico
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", texto)

    # URL nua vira link. O "Material recomendado" dos mapas escreve
    # `- Questões: https://qconcursos.com/…` sem sintaxe de link, e sem isto a
    # linha chega na web como texto morto — justamente na seção cuja razão de
    # existir é levar o estudante ao material. Os <a>/<img> montados acima são
    # guardados antes, senão a URL do próprio href viraria link dentro de link.
    # Marcador próprio (\x01): o do código só é restaurado no fim, e restaurar
    # aninhado num único passe de re.sub deixaria placeholder cru na página.
    tags: list[str] = []

    def _guardar_tag(m):
        tags.append(m.group(0))
        return f"\x01{len(tags) - 1}\x01"

    texto = re.sub(r"<a\b[^>]*>.*?</a>|<img\b[^>]*>", _guardar_tag, texto)
    texto = _URL_NUA.sub(_autolink, texto)
    texto = re.sub(r"\x01(\d+)\x01", lambda m: tags[int(m.group(1))], texto)

    # restaurar código
    def _restaurar(m):
        return fragmentos[int(m.group(1))]

    return re.sub(r"\x00(\d+)\x00", _restaurar, texto)


# --------------------------------------------------------------------------- #
# blocos
# --------------------------------------------------------------------------- #
def converter(md: str, wikilink_resolver=None, pular_frontmatter=True,
              prefixo_id="") -> str:
    if pular_frontmatter:
        md = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md, count=1, flags=re.DOTALL)

    # ids dos headings vêm de _headings(), a mesma função que alimenta sumario():
    # calcular aqui de novo abriria espaço para o índice apontar para id inexistente
    ids = [ident for _n, _t, ident in _headings(md, pular_frontmatter=False,
                                                prefixo_id=prefixo_id)]
    prox_id = 0

    linhas = md.split("\n")
    out: list[str] = []
    i = 0
    lista_aberta: str | None = None   # 'ul' | 'ol' | None

    def fechar_lista():
        nonlocal lista_aberta
        if lista_aberta:
            out.append(f"</{lista_aberta}>")
            lista_aberta = None

    while i < len(linhas):
        linha = linhas[i]
        strip = linha.strip()

        # linha em branco
        if not strip:
            fechar_lista()
            i += 1
            continue

        # comentário HTML: ignorar
        if strip.startswith("<!--"):
            while i < len(linhas) and "-->" not in linhas[i]:
                i += 1
            i += 1
            continue

        # bloco de código cercado
        if strip.startswith("```"):
            fechar_lista()
            i += 1
            buf = []
            while i < len(linhas) and not linhas[i].strip().startswith("```"):
                buf.append(html.escape(linhas[i]))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue

        # separador
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", strip):
            fechar_lista()
            out.append("<hr>")
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", strip)
        if m:
            fechar_lista()
            nivel = len(m.group(1))
            conteudo = _inline(html.escape(m.group(2)), wikilink_resolver)
            ident = (ids[prox_id] if prox_id < len(ids)
                     else prefixo_id + slug_ancora(m.group(2)))
            prox_id += 1
            out.append(f'<h{nivel} id="{ident}">{conteudo}</h{nivel}>')
            i += 1
            continue

        # blockquote (agrupa linhas consecutivas)
        if strip.startswith(">"):
            fechar_lista()
            buf = []
            while i < len(linhas) and linhas[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", linhas[i]))
                i += 1
            corpo = _inline(html.escape("\n".join(buf)), wikilink_resolver)
            corpo = corpo.replace("\n", "<br>")
            out.append(f"<blockquote>{corpo}</blockquote>")
            continue

        # tabela (linha com | e próxima linha de separação)
        if "|" in strip and i + 1 < len(linhas) and re.match(
                r"^\s*\|?[\s:|-]+\|[\s:|-]*$", linhas[i + 1]):
            fechar_lista()
            def celulas(l):
                l = l.strip().strip("|")
                # dividir só em pipe NÃO escapado: dentro de tabela o wikilink vem
                # como `[[alvo\|rotulo]]`, e dividir nele partia o link em duas
                # células. Depois de dividir, o `\|` volta a ser `|` para o
                # wikilink ser reconhecido normalmente.
                return [c.strip().replace("\\|", "|")
                        for c in re.split(r"(?<!\\)\|", l)]
            cabecalho = celulas(linhas[i])
            i += 2
            corpo_linhas = []
            while i < len(linhas) and "|" in linhas[i] and linhas[i].strip():
                corpo_linhas.append(celulas(linhas[i]))
                i += 1
            th = "".join(f"<th>{_inline(html.escape(c), wikilink_resolver)}</th>"
                         for c in cabecalho)
            trs = []
            for row in corpo_linhas:
                tds = "".join(f"<td>{_inline(html.escape(c), wikilink_resolver)}</td>"
                              for c in row)
                trs.append(f"<tr>{tds}</tr>")
            out.append(f"<table><thead><tr>{th}</tr></thead>"
                       f"<tbody>{''.join(trs)}</tbody></table>")
            continue

        # checkbox (é um item de lista especial — vira lista de tarefas)
        m = re.match(r"^\s*[-*]\s+\[([ xX])\]\s+(.*)$", linha)
        if m:
            if lista_aberta != "ul":
                fechar_lista()
                out.append('<ul class="tarefas">')
                lista_aberta = "ul"
            feito = m.group(1).lower() == "x"
            marca = "feito" if feito else "aberto"
            conteudo = _inline(html.escape(m.group(2)), wikilink_resolver)
            out.append(f'<li class="tarefa {marca}">'
                       f'<span class="bolha" aria-hidden="true"></span>'
                       f'<span>{conteudo}</span></li>')
            i += 1
            continue

        # lista não ordenada
        m = re.match(r"^\s*[-*]\s+(.*)$", linha)
        if m:
            if lista_aberta != "ul":
                fechar_lista()
                out.append("<ul>")
                lista_aberta = "ul"
            out.append(f"<li>{_inline(html.escape(m.group(1)), wikilink_resolver)}</li>")
            i += 1
            continue

        # lista ordenada
        m = re.match(r"^\s*\d+[.)]\s+(.*)$", linha)
        if m:
            if lista_aberta != "ol":
                fechar_lista()
                out.append("<ol>")
                lista_aberta = "ol"
            out.append(f"<li>{_inline(html.escape(m.group(1)), wikilink_resolver)}</li>")
            i += 1
            continue

        # parágrafo (agrupa linhas até em branco)
        fechar_lista()
        buf = [linha]
        i += 1
        while i < len(linhas) and linhas[i].strip() and not re.match(
                r"^\s*(#{1,6}\s|[-*]\s|\d+[.)]\s|>|```|\|)", linhas[i]):
            buf.append(linhas[i])
            i += 1
        texto = _inline(html.escape(" ".join(b.strip() for b in buf)), wikilink_resolver)
        out.append(f"<p>{texto}</p>")

    fechar_lista()
    return "\n".join(out)


def primeiro_paragrafo(md: str, limite: int = 200) -> str:
    """Extrai um resumo curto (texto puro) do markdown, para cards/índices."""
    md = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md, count=1, flags=re.DOTALL)
    for linha in md.split("\n"):
        s = linha.strip()
        if not s or s.startswith(("#", ">", "-", "*", "|", "```", "<!--")):
            continue
        s = re.sub(r"[*`\[\]]", "", s)
        return (s[:limite] + "…") if len(s) > limite else s
    return ""
