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
# `^id` sozinho na linha: block id do Obsidian, alvo de `[[nota#^id]]`
_BLOCO_ID = re.compile(r"^\s*\^([A-Za-z0-9][A-Za-z0-9-]*)\s*$")


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
            try:
                href = wikilink_resolver(alvo, ancora)
            except TypeError:            # resolvedor antigo, de um argumento só
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

    # negrito e itálico, nesta ordem — e a ordem é o que faz funcionar.
    #
    # `***x***` vem primeiro porque o passo do negrito, sendo preguiçoso, casaria
    # `**` + `*x` + `**` e deixaria um `*` solto na página.
    #
    # O negrito aceita `*` DENTRO (`[\s\S]+?` no lugar do antigo `[^*]+`): o vault
    # escreve `**​*Cujo* não admite artigo**` — negrito contendo itálico — em 139
    # linhas de 20 arquivos, e com a classe negada a linha inteira chegava ao site
    # com os asteriscos crus. A forma inversa (`*Fui eu **que fiz***`) já funcionava
    # e continua funcionando.
    #
    # `[\s\S]` e não `.`: o negrito PRECISA cruzar linha. O texto que chega aqui é um
    # bloco inteiro — parágrafo ou blockquote, com as linhas ainda separadas por
    # `\n` —, e o vault quebra linha no meio de negrito o tempo todo. Usar `.` fecha
    # o casamento na quebra e devolve 1.406 asteriscos crus ao site; foi medido.
    texto = re.sub(r"\*\*\*([\s\S]+?)\*\*\*", r"<strong><em>\1</em></strong>", texto)
    texto = re.sub(r"\*\*([\s\S]+?)\*\*", r"<strong>\1</strong>", texto)
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
    # Pilha de listas abertas, uma entrada por nível de indentação. Era um único
    # `lista_aberta`, e por isso toda lista aninhada chegava ACHATADA ao site: os
    # subitens viravam irmãos dos pais e a hierarquia — que é a informação — sumia.
    # Eram 408 linhas em 51 arquivos do vault.
    #
    # Cada nível guarda se o seu `<li>` está aberto, porque a sublista tem de ficar
    # DENTRO dele: `<ul>` como filho direto de `<ul>` é HTML inválido, e fechar o
    # `<li>` antes da sublista era o jeito errado de fazer parecer certo.
    pilha: list = []      # [{"tag", "classe", "indent", "li"}]

    def _fechar_nivel():
        n = pilha.pop()
        if n["li"]:
            out.append("</li>")
        out.append(f"</{n['tag']}>")

    def fechar_lista(ate: int | None = None):
        """Fecha tudo (ate=None) ou só os níveis mais fundos que `ate`."""
        while pilha and (ate is None or pilha[-1]["indent"] > ate):
            _fechar_nivel()
        if ate is None and pilha:
            pass

    def abrir_item(indent: int, tag: str, classe: str, corpo: str):
        """Emite um `<li>` no nível certo, abrindo e fechando o que for preciso."""
        fechar_lista(ate=indent)
        if pilha and pilha[-1]["indent"] == indent:
            if pilha[-1]["tag"] != tag or pilha[-1]["classe"] != classe:
                _fechar_nivel()
            elif pilha[-1]["li"]:
                out.append("</li>")
                pilha[-1]["li"] = False
        if not pilha or pilha[-1]["indent"] < indent:
            # aninhada: o `<li>` do pai continua ABERTO e recebe esta sublista
            out.append(f'<{tag} class="{classe}">' if classe else f"<{tag}>")
            pilha.append({"tag": tag, "classe": classe, "indent": indent, "li": False})
        out.append(corpo)
        pilha[-1]["li"] = True

    def _indent(l: str) -> int:
        expandida = l.expandtabs(4)
        return len(expandida) - len(expandida.lstrip())

    def _corpo_do_item(j: int, texto: str) -> tuple:
        """Junta as linhas de continuação ao texto do item, e devolve `(texto, j)`.

        As linhas têm de ser juntadas ANTES de ir para o conversor inline: o vault
        quebra a linha no meio de negrito, e convertendo linha a linha as duas
        metades caem em chamadas diferentes — o `**` fica órfão dos dois lados e os
        asteriscos chegam crus à página. Linha indentada que TEM marcador de lista
        não é continuação: é sublista, e quem trata é o laço principal.
        """
        j += 1
        while j < len(linhas):
            seguinte = linhas[j]
            if not seguinte.strip():
                break
            if not seguinte[:1].isspace():
                break
            if re.match(r"^\s*(?:[-*]|\d+[.)])\s+", seguinte):
                break
            texto += "\n" + seguinte.strip()
            j += 1
        return texto, j

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
                # O pipe do wikilink não é separador de célula. Escapado (`\|`) o
                # `(?<!\\)` já dava conta, mas o vault também escreve `[[alvo|rótulo]]`
                # CRU dentro de tabela — e aí a célula virava quatro, com o link
                # aparecendo em texto puro na página. Mascarar o miolo de `[[…]]`
                # antes de dividir resolve as duas formas de uma vez.
                l = re.sub(r"\[\[[^\]]*\]\]",
                           lambda m: m.group(0).replace("\\|", "\x02").replace("|", "\x02"),
                           l)
                return [c.strip().replace("\x02", "|")
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
            marca = "feito" if m.group(1).lower() == "x" else "aberto"
            texto, i = _corpo_do_item(i, m.group(2))
            conteudo = _inline(html.escape(texto), wikilink_resolver)
            abrir_item(_indent(linha), "ul", "tarefas",
                       f'<li class="tarefa {marca}">'
                       f'<span class="bolha" aria-hidden="true"></span>'
                       f'<span>{conteudo}</span>')
            continue

        # lista não ordenada
        m = re.match(r"^\s*[-*]\s+(.*)$", linha)
        if m:
            texto, i = _corpo_do_item(i, m.group(1))
            abrir_item(_indent(linha), "ul", "",
                       f"<li>{_inline(html.escape(texto), wikilink_resolver)}")
            continue

        # lista ordenada
        m = re.match(r"^\s*\d+[.)]\s+(.*)$", linha)
        if m:
            texto, i = _corpo_do_item(i, m.group(1))
            abrir_item(_indent(linha), "ol", "",
                       f"<li>{_inline(html.escape(texto), wikilink_resolver)}")
            continue

        # block id do Obsidian (`^mat-pestana-gramatica`), sozinho na linha.
        # É METADADO, não conteúdo: no Obsidian ele fica invisível no modo
        # leitura, e é o alvo de `[[nota#^id]]`. Sem este ramo ele saía como
        # texto visível na página E o wikilink de âncora resolvia para um id
        # que não existia — o link levava à página certa e não pulava a lugar
        # nenhum, que é o pior dos dois mundos: parece funcionar.
        m = _BLOCO_ID.match(linha)
        if m:
            fechar_lista()
            out.append(f'<span class="ancora-bloco" id="{html.escape(m.group(1))}"></span>')
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
