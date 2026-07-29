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


# --------------------------------------------------------------------------- #
# inline
# --------------------------------------------------------------------------- #
def _inline(texto: str, wikilink_resolver=None) -> str:
    """Aplica formatação inline. O texto JÁ deve estar escapado."""
    # código inline primeiro (protege o conteúdo do resto)
    fragmentos: list[str] = []

    def _guardar(m):
        fragmentos.append(f"<code>{m.group(1)}</code>")
        return f"\x00{len(fragmentos) - 1}\x00"

    texto = re.sub(r"`([^`]+)`", _guardar, texto)

    # wikilinks [[alvo|rotulo]] ou [[alvo]]
    def _wiki(m):
        alvo = m.group(1).strip()
        rotulo = (m.group(2) or alvo).strip()
        if wikilink_resolver:
            href = wikilink_resolver(alvo)
            if href:
                return f'<a href="{href}">{rotulo}</a>'
        return f'<span class="wikilink-morto" title="não publicado">{rotulo}</span>'

    texto = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", _wiki, texto)

    # links markdown [texto](url)
    texto = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', texto)

    # negrito e itálico
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", texto)

    # restaurar código
    def _restaurar(m):
        return fragmentos[int(m.group(1))]

    return re.sub(r"\x00(\d+)\x00", _restaurar, texto)


# --------------------------------------------------------------------------- #
# blocos
# --------------------------------------------------------------------------- #
def converter(md: str, wikilink_resolver=None, pular_frontmatter=True) -> str:
    if pular_frontmatter:
        md = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md, count=1, flags=re.DOTALL)

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
            out.append(f"<h{nivel}>{conteudo}</h{nivel}>")
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
                return [c.strip() for c in l.split("|")]
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
