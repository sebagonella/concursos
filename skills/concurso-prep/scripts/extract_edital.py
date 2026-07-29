#!/usr/bin/env python3
"""
extract_edital.py - Extrai texto de edital em PDF/DOCX/MD para parse posterior.

Uso:
    python extract_edital.py <caminho-edital> [--out <arquivo-saida>]

Saída padrão: stdout (ou arquivo se --out fornecido).
"""
import argparse
import subprocess
import sys
from pathlib import Path


def extract_pdf(path: Path) -> str:
    """Extrai texto de PDF usando pdftotext (poppler)."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True, text=True, check=True, timeout=120
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        # Fallback sem layout
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            capture_output=True, text=True, check=True, timeout=120
        )
        return result.stdout
    except FileNotFoundError:
        sys.stderr.write("ERRO: pdftotext nao encontrado. Instale poppler-utils.\n")
        sys.exit(1)


def extract_docx(path: Path) -> str:
    """Extrai texto de DOCX usando python-docx."""
    try:
        from docx import Document
    except ImportError:
        sys.stderr.write("ERRO: python-docx nao instalado. Rode: pip install python-docx\n")
        sys.exit(1)
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_md(path: Path) -> str:
    """Lê arquivo Markdown diretamente."""
    return path.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Extrai texto de edital")
    parser.add_argument("path", type=Path, help="Caminho do edital")
    parser.add_argument("--out", type=Path, help="Arquivo de saída (default: stdout)")
    args = parser.parse_args()

    if not args.path.exists():
        sys.stderr.write(f"ERRO: arquivo nao encontrado: {args.path}\n")
        sys.exit(1)

    ext = args.path.suffix.lower()
    if ext == ".pdf":
        text = extract_pdf(args.path)
    elif ext in (".docx", ".doc"):
        text = extract_docx(args.path)
    elif ext in (".md", ".txt"):
        text = extract_md(args.path)
    else:
        sys.stderr.write(f"ERRO: formato nao suportado: {ext}\n")
        sys.exit(1)

    if args.out:
        args.out.write_text(text, encoding="utf-8")
        sys.stderr.write(f"OK: {len(text)} chars escritos em {args.out}\n")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
