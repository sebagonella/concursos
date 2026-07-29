#!/usr/bin/env python3
"""
book_index.py - Subsistema A da skill concurso-aprofunda.

Dado um livro (PDF com texto, PDF escaneado, ou EPUB) e a lista de assuntos já
mapeados de uma matéria, produz um "mapa de localização": para cada assunto,
onde ele é tratado no livro (intervalo de páginas), com um score de confiança.

Estratégia:
  1. Detectar o tipo do arquivo e extrair texto por página.
     - PDF com texto -> pdftotext (rápido, preciso)
     - PDF escaneado -> OCR via tesseract (lento; só se detectar ausência de texto)
     - EPUB -> desempacota e extrai texto dos XHTML (estrutura semântica nativa)
  2. Tentar localizar via SUMÁRIO (TOC): casar títulos do sumário com os assuntos.
  3. Onde o sumário não cobre, cair para BUSCA POR DENSIDADE de termos do assunto.
  4. Emitir JSON com {assunto: {paginas, confianca, metodo}}.

Uso:
    python book_index.py --livro <arquivo> --assuntos <assuntos.json> \
        [--out mapa-localizacao.json] [--ocr auto|forcar|nunca] [--json]

<assuntos.json> = {"materia": "Língua Portuguesa",
                   "assuntos": ["Concordância verbal", "Regência", ...]}

Exit: 0 ok · 1 erro de leitura · 2 nenhum texto extraído (livro é imagem e OCR off)
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textmatch import normalizar, score_match, densidade_termos, tokens_significativos  # noqa: E402


CONF_ALTA, CONF_MEDIA, CONF_BAIXA = "alta", "media", "baixa"
LIMIAR_TOC = 0.62      # score mínimo p/ aceitar um match de sumário
LIMIAR_DENSIDADE = 0.15  # densidade mínima p/ considerar uma página relevante


# --------------------------------------------------------------------------- #
# 1. Extração de texto por página
# --------------------------------------------------------------------------- #
def detectar_tipo(livro: Path) -> str:
    ext = livro.suffix.lower()
    if ext == ".epub":
        return "epub"
    if ext == ".pdf":
        return "pdf"
    if ext in (".txt", ".md"):
        return "texto"
    return "desconhecido"


def extrair_pdf_texto(livro: Path) -> list[str]:
    """Retorna lista de páginas (texto). Usa pdftotext com separador de página."""
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", str(livro), "-"],
            capture_output=True, text=True, timeout=300,
        )
    except FileNotFoundError:
        sys.stderr.write("ERRO: pdftotext não encontrado (instale poppler-utils).\n")
        return []
    except subprocess.TimeoutExpired:
        sys.stderr.write("ERRO: pdftotext expirou (livro muito grande).\n")
        return []
    # pdftotext separa páginas com \f (form feed)
    paginas = out.stdout.split("\f")
    return paginas


def extrair_pdf_ocr(livro: Path) -> list[str]:
    """OCR página a página via pdftoppm + tesseract. Lento; usado só em fallback."""
    paginas = []
    with tempfile.TemporaryDirectory() as td:
        try:
            subprocess.run(["pdftoppm", "-r", "200", "-png", str(livro),
                            str(Path(td) / "pg")], check=True, timeout=600)
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            sys.stderr.write(f"ERRO no OCR (pdftoppm): {e}\n")
            return []
        imgs = sorted(Path(td).glob("pg*.png"))
        for img in imgs:
            try:
                r = subprocess.run(["tesseract", str(img), "-", "-l", "por"],
                                   capture_output=True, text=True, timeout=120)
                paginas.append(r.stdout)
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                sys.stderr.write(f"AVISO: tesseract falhou em {img.name}: {e}\n")
                paginas.append("")
    return paginas


def extrair_epub(livro: Path) -> list[str]:
    """Extrai texto dos documentos XHTML do EPUB, na ordem da spine se possível."""
    from html.parser import HTMLParser

    class _Strip(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.buf = []
            self._skip = 0

        def handle_starttag(self, t, a):
            if t in ("script", "style"):
                self._skip += 1

        def handle_endtag(self, t):
            if t in ("script", "style") and self._skip:
                self._skip -= 1

        def handle_data(self, d):
            if not self._skip and d.strip():
                self.buf.append(d)

    paginas = []
    try:
        with zipfile.ZipFile(livro) as z:
            nomes = [n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
            nomes.sort()
            for n in nomes:
                p = _Strip()
                try:
                    p.feed(z.read(n).decode("utf-8", errors="replace"))
                except Exception:
                    continue
                txt = re.sub(r"\s+", " ", " ".join(p.buf)).strip()
                if txt:
                    paginas.append(txt)
    except zipfile.BadZipFile:
        sys.stderr.write("ERRO: EPUB inválido.\n")
        return []
    return paginas


def extrair_paginas(livro: Path, modo_ocr: str) -> tuple[list[str], str]:
    """Retorna (paginas, metodo_extracao)."""
    tipo = detectar_tipo(livro)
    if tipo == "epub":
        return extrair_epub(livro), "epub"
    if tipo == "texto":
        return livro.read_text(encoding="utf-8", errors="replace").split("\f"), "texto"
    if tipo == "pdf":
        if modo_ocr == "forcar":
            return extrair_pdf_ocr(livro), "ocr"
        paginas = extrair_pdf_texto(livro)
        texto_total = "".join(paginas).strip()
        # Heurística: se quase não há texto, o PDF é imagem -> OCR (se permitido)
        if len(texto_total) < 200 and modo_ocr != "nunca":
            sys.stderr.write("INFO: PDF parece escaneado; acionando OCR (mais lento)...\n")
            return extrair_pdf_ocr(livro), "ocr"
        return paginas, "pdf-texto"
    sys.stderr.write(f"ERRO: tipo de arquivo não suportado: {livro.suffix}\n")
    return [], "desconhecido"


# --------------------------------------------------------------------------- #
# 2. Sumário (TOC)
# --------------------------------------------------------------------------- #
TOC_MARCADORES = re.compile(r"^\s*(sum[aá]rio|[ií]ndice|conte[uú]do)\s*$", re.IGNORECASE)
# linha de sumário: "Título ......... 42" ou "Título   42"
LINHA_TOC = re.compile(r"^(.{4,120}?)[\.\s]{2,}(\d{1,4})\s*$")


def extrair_toc(paginas: list[str]) -> list[tuple[str, int]]:
    """Procura páginas de sumário e extrai (título, página). Heurística tolerante."""
    entradas = []
    # olhar nas primeiras ~15 páginas por um bloco de sumário
    for pg in paginas[:15]:
        linhas = pg.split("\n")
        tem_marcador = any(TOC_MARCADORES.match(l) for l in linhas)
        candidatos = []
        for l in linhas:
            m = LINHA_TOC.match(l.rstrip())
            if m:
                titulo = m.group(1).strip(" .-")
                num = int(m.group(2))
                if titulo and len(titulo) > 3:
                    candidatos.append((titulo, num))
        # aceitar o bloco se tem marcador OU se há muitos candidatos juntos
        if tem_marcador or len(candidatos) >= 5:
            entradas.extend(candidatos)
    # dedup preservando ordem
    visto = set()
    out = []
    for t, n in entradas:
        chave = (normalizar(t), n)
        if chave not in visto:
            visto.add(chave)
            out.append((t, n))
    return out


def localizar_por_toc(assunto: str, toc: list[tuple[str, int]],
                      total_paginas: int) -> dict | None:
    """Casa o assunto com a melhor entrada de sumário. Página final = início da
    próxima entrada - 1 (aproximação do intervalo do capítulo)."""
    if not toc:
        return None
    scored = sorted(
        ((score_match(assunto, titulo), titulo, pg) for titulo, pg in toc),
        reverse=True,
    )
    melhor_score, melhor_titulo, melhor_pg = scored[0]
    if melhor_score < LIMIAR_TOC:
        return None
    # achar a próxima página de TOC maior que a nossa (fim do intervalo)
    paginas_toc = sorted({pg for _, pg in toc})
    fim = total_paginas
    for pg in paginas_toc:
        if pg > melhor_pg:
            fim = pg - 1
            break
    conf = CONF_ALTA if melhor_score >= 0.80 else CONF_MEDIA
    return {
        "paginas": [melhor_pg, fim],
        "confianca": conf,
        "metodo": "toc",
        "titulo_no_livro": melhor_titulo,
        "score": melhor_score,
    }


# --------------------------------------------------------------------------- #
# 3. Busca por densidade (fallback sem TOC)
# --------------------------------------------------------------------------- #
def localizar_por_densidade(assunto: str, paginas: list[str]) -> dict | None:
    termos = tokens_significativos(assunto)
    if not termos:
        return None
    scores = []
    for i, pg in enumerate(paginas):
        d = densidade_termos(pg, termos)
        if d >= LIMIAR_DENSIDADE:
            scores.append((d, i + 1))  # páginas 1-indexed
    if not scores:
        return None
    scores.sort(reverse=True)
    top = [pg for _, pg in scores[:8]]
    top.sort()
    # agrupar em intervalo contíguo dominante
    inicio, fim = top[0], top[-1]
    melhor_d = scores[0][0]
    conf = CONF_MEDIA if melhor_d >= 0.35 else CONF_BAIXA
    return {
        "paginas": [inicio, fim],
        "paginas_relevantes": top,
        "confianca": conf,
        "metodo": "densidade",
        "score": melhor_d,
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Localiza assuntos dentro de um livro")
    ap.add_argument("--livro", type=Path, required=True)
    ap.add_argument("--assuntos", type=Path, required=True, help="JSON com materia+assuntos")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--ocr", choices=["auto", "forcar", "nunca"], default="auto")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.livro.exists():
        sys.stderr.write(f"ERRO: livro não encontrado: {args.livro}\n")
        sys.exit(1)

    spec = json.loads(args.assuntos.read_text(encoding="utf-8"))
    materia = spec.get("materia", "?")
    assuntos = spec.get("assuntos", [])

    modo_ocr = {"auto": "auto", "forcar": "forcar", "nunca": "nunca"}[args.ocr]
    paginas, metodo_extr = extrair_paginas(args.livro, modo_ocr)
    if not paginas or not "".join(paginas).strip():
        sys.stderr.write("ERRO: nenhum texto extraído do livro.\n")
        sys.exit(2)

    toc = extrair_toc(paginas)
    total = len(paginas)

    resultado = {
        "livro": str(args.livro.name),
        "materia": materia,
        "extracao": metodo_extr,
        "total_paginas": total,
        "toc_entradas": len(toc),
        "localizacoes": {},
        "pendencias": [],
    }

    for assunto in assuntos:
        loc = localizar_por_toc(assunto, toc, total)
        if loc is None:
            loc = localizar_por_densidade(assunto, paginas)
        if loc is None:
            resultado["localizacoes"][assunto] = {"confianca": "nao_encontrado", "metodo": None}
            resultado["pendencias"].append(f"NÃO LOCALIZADO: {assunto}")
        else:
            resultado["localizacoes"][assunto] = loc
            if loc["confianca"] in (CONF_BAIXA,):
                resultado["pendencias"].append(
                    f"CONFERIR (confiança baixa): {assunto} -> págs {loc['paginas']}")

    saida = json.dumps(resultado, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(saida, encoding="utf-8")
        sys.stderr.write(f"OK: mapa salvo em {args.out}\n")
    if args.json or not args.out:
        print(saida)

    sys.exit(0)


if __name__ == "__main__":
    main()
