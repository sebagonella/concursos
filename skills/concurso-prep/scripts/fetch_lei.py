#!/usr/bin/env python3
"""
fetch_lei.py - Baixa uma lei/decreto/resolucao de fonte oficial e gera DOIS formatos:
    - Markdown (.md)  -> ideal para o vault Obsidian (linkavel, pesquisavel, leve)
    - PDF (.pdf)      -> arquivo fiel para leitura/impressao/anexo

Motivacao (item 9 da revisao): o Planalto e a maioria dos portais oficiais servem
as leis em HTML, nao em PDF. O fluxo antigo (fetch_pdf.py --require-pdf) rejeitava
esses downloads. Este script resolve convertendo HTML -> MD e HTML -> PDF.

Uso:
    python fetch_lei.py <url> --slug lei-8742-1993-loas --out-dir <pasta> \
        [--titulo "LOAS - Lei 8.742/1993"] [--formatos md,pdf] [--timeout 30]

Estrategia de conversao PDF (tenta em ordem, usa o primeiro disponivel):
    1. weasyprint            (HTML -> PDF, melhor fidelidade tipografica)
    2. reportlab             (a partir do texto/MD extraido; sempre disponivel aqui)
Se nenhum produtor de PDF estiver disponivel, gera so o MD e avisa (exit 2).

Exit codes:
    0 = sucesso (todos os formatos pedidos gerados)
    1 = erro de rede / URL
    2 = baixou e gerou MD, mas nao conseguiu gerar PDF
    3 = argumentos invalidos
    4 = fonte fora da whitelist (quando --whitelist e passada)
"""
import argparse
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 ConcursoPrepBot/1.3"
)


# --------------------------------------------------------------------------- #
# 1. Download
# --------------------------------------------------------------------------- #
def baixar_html(url: str, timeout: int = 30) -> str | None:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset()
    except (URLError, HTTPError, TimeoutError) as e:
        sys.stderr.write(f"  Falha ao baixar: {type(e).__name__}: {e}\n")
        return None
    # Planalto usa latin-1 com frequencia; tentar declarado -> utf-8 -> latin-1
    for enc in filter(None, [charset, "utf-8", "latin-1"]):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# 2. HTML -> texto estruturado (paragrafos)
# --------------------------------------------------------------------------- #
class _TextExtractor(HTMLParser):
    """Extrai texto visivel preservando quebras de paragrafo. Sem dependencias."""

    _SKIP = {"script", "style", "head", "meta", "link", "noscript"}
    _BLOCK = {"p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skipping += 1
        if tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skipping:
            self._skipping -= 1
        if tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skipping:
            return
        if data.strip():
            self.parts.append(data)

    def get_text(self) -> str:
        txt = "".join(self.parts)
        txt = re.sub(r"[ \t]+", " ", txt)
        txt = re.sub(r"\n[ \t]+", "\n", txt)
        txt = re.sub(r"\n{3,}", "\n\n", txt)
        return txt.strip()


def html_para_texto(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


# --------------------------------------------------------------------------- #
# 3. texto -> Markdown (com leve realce de estrutura juridica)
# --------------------------------------------------------------------------- #
ART_RE = re.compile(r"^\s*(Art\.?\s*\d+[ºo\-A-Z]*)", re.IGNORECASE)
PARAG_RE = re.compile(r"^\s*(§\s*\d+[ºo]?|Par[aá]grafo [uú]nico)", re.IGNORECASE)
CAPITULO_RE = re.compile(r"^\s*(T[IÍ]TULO|CAP[IÍ]TULO|SE[ÇC][AÃ]O|LIVRO)\b", re.IGNORECASE)


def texto_para_markdown(texto: str, titulo: str, url: str) -> str:
    linhas_out = [
        "---",
        f'title: "{titulo}"',
        "tipo: legislacao",
        f"fonte: {url}",
        f"baixado_em: {datetime.now().strftime('%Y-%m-%d')}",
        "tags: [legislacao, concurso/material]",
        "---",
        "",
        f"# {titulo}",
        "",
        f"> Fonte oficial: {url}  ",
        f"> Baixado automaticamente em {datetime.now().strftime('%d/%m/%Y')}. "
        "Texto de domínio público. Confira sempre a versão vigente na fonte.",
        "",
    ]
    for linha in texto.split("\n"):
        l = linha.strip()
        if not l:
            linhas_out.append("")
            continue
        if CAPITULO_RE.match(l):
            linhas_out.append(f"## {l}")
        elif ART_RE.match(l):
            m = ART_RE.match(l)
            linhas_out.append(f"**{m.group(1)}**{l[m.end():]}")
        elif PARAG_RE.match(l):
            linhas_out.append(f"- {l}")
        else:
            linhas_out.append(l)
    md = "\n".join(linhas_out)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


# --------------------------------------------------------------------------- #
# 4. Geradores de PDF
# --------------------------------------------------------------------------- #
def pdf_via_weasyprint(html: str, dest: Path) -> bool:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return False
    try:
        HTML(string=html).write_pdf(str(dest))
        return dest.exists() and dest.stat().st_size > 100
    except Exception as e:
        sys.stderr.write(f"  weasyprint falhou: {e}\n")
        return False


def pdf_via_reportlab(texto: str, titulo: str, dest: Path) -> bool:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_JUSTIFY
    except Exception:
        return False
    try:
        doc = SimpleDocTemplate(
            str(dest), pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=1.8 * cm, bottomMargin=1.8 * cm, title=titulo,
        )
        styles = getSampleStyleSheet()
        body = ParagraphStyle(
            "corpo", parent=styles["Normal"], fontSize=9.5,
            leading=13, alignment=TA_JUSTIFY, spaceAfter=4,
        )
        h = ParagraphStyle("h", parent=styles["Title"], fontSize=15, spaceAfter=10)
        story = [Paragraph(_xml_escape(titulo), h), Spacer(1, 6)]
        for par in texto.split("\n"):
            par = par.strip()
            if par:
                story.append(Paragraph(_xml_escape(par), body))
            else:
                story.append(Spacer(1, 4))
        doc.build(story)
        return dest.exists() and dest.stat().st_size > 100
    except Exception as e:
        sys.stderr.write(f"  reportlab falhou: {e}\n")
        return False


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------- #
# 5. Whitelist de dominio (integra com item 12)
# --------------------------------------------------------------------------- #
def dominio_permitido(url: str, whitelist: list[str]) -> bool:
    if not whitelist:
        return True
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in whitelist)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Baixa lei e gera MD + PDF")
    ap.add_argument("url")
    ap.add_argument("--slug", required=True, help="nome base do arquivo (sem extensao)")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--titulo", default=None, help="titulo legivel; default = slug")
    ap.add_argument("--formatos", default="md,pdf", help="csv: md,pdf (default ambos)")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--whitelist", default="", help="csv de dominios confiaveis (item 12)")
    args = ap.parse_args()

    formatos = {f.strip().lower() for f in args.formatos.split(",") if f.strip()}
    if not formatos <= {"md", "pdf"}:
        sys.stderr.write("ERRO: --formatos aceita apenas md,pdf\n")
        sys.exit(3)

    whitelist = [d.strip().lower() for d in args.whitelist.split(",") if d.strip()]
    if not dominio_permitido(args.url, whitelist):
        sys.stderr.write(f"BLOQUEADO: {args.url} fora da whitelist {whitelist}\n")
        sys.exit(4)

    titulo = args.titulo or args.slug
    args.out_dir.mkdir(parents=True, exist_ok=True)

    html = baixar_html(args.url, args.timeout)
    if html is None:
        sys.exit(1)

    texto = html_para_texto(html)
    if len(texto) < 200:
        sys.stderr.write("AVISO: texto extraido muito curto; a pagina pode nao ser a lei.\n")

    resultados = {}

    # --- Markdown ---
    if "md" in formatos:
        md = texto_para_markdown(texto, titulo, args.url)
        md_path = args.out_dir / f"{args.slug}.md"
        md_path.write_text(md, encoding="utf-8")
        resultados["md"] = str(md_path)
        sys.stderr.write(f"OK md:  {md_path} ({len(md)} chars)\n")

    # --- PDF ---
    pdf_ok = True
    if "pdf" in formatos:
        pdf_path = args.out_dir / f"{args.slug}.pdf"
        ok = pdf_via_weasyprint(html, pdf_path) or pdf_via_reportlab(texto, titulo, pdf_path)
        if ok:
            resultados["pdf"] = str(pdf_path)
            sys.stderr.write(f"OK pdf: {pdf_path} ({pdf_path.stat().st_size} bytes)\n")
        else:
            pdf_ok = False
            sys.stderr.write("ERRO: nenhum gerador de PDF disponivel (weasyprint/reportlab).\n")

    print(",".join(f"{k}={v}" for k, v in resultados.items()))
    if "pdf" in formatos and not pdf_ok:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
