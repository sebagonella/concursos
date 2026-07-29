#!/usr/bin/env python3
"""
fetch_pdf.py - Download robusto de PDFs com retry, validação e User-Agent.

Uso:
    python fetch_pdf.py <url> --out <caminho-destino> [--retries 3] [--timeout 30]

Exit codes:
    0 = sucesso, arquivo válido
    1 = erro de rede / URL
    2 = arquivo baixado mas não é PDF válido
    3 = argumentos inválidos
"""
import argparse
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


USER_AGENT = "Mozilla/5.0 (compatible; ConcursoPrepBot/1.0; +https://example.com/bot)"


def is_valid_pdf(path: Path) -> bool:
    """Verifica se o arquivo começa com header %PDF."""
    if not path.exists() or path.stat().st_size < 100:
        return False
    with open(path, "rb") as f:
        header = f.read(5)
    return header.startswith(b"%PDF-")


def download(url: str, dest: Path, timeout: int = 30) -> bool:
    """Tenta baixar uma vez. Retorna True se sucesso."""
    req = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,*/*",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except (URLError, HTTPError, TimeoutError) as e:
        sys.stderr.write(f"  Falha: {type(e).__name__}: {e}\n")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download robusto de PDF")
    parser.add_argument("url", help="URL do PDF a baixar")
    parser.add_argument("--out", type=Path, required=True, help="Caminho de destino")
    parser.add_argument("--retries", type=int, default=3, help="Tentativas (default 3)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout em segundos")
    parser.add_argument("--require-pdf", action="store_true",
                        help="Exigir que o arquivo seja PDF válido")
    args = parser.parse_args()

    for attempt in range(1, args.retries + 1):
        sys.stderr.write(f"Tentativa {attempt}/{args.retries}: {args.url}\n")
        if download(args.url, args.out, args.timeout):
            if args.require_pdf and not is_valid_pdf(args.out):
                sys.stderr.write("  Arquivo baixado nao e um PDF valido.\n")
                args.out.unlink(missing_ok=True)
                sys.exit(2)
            sys.stderr.write(f"OK: salvo em {args.out} ({args.out.stat().st_size} bytes)\n")
            sys.exit(0)
        if attempt < args.retries:
            wait = 2 ** attempt
            sys.stderr.write(f"  Aguardando {wait}s antes da proxima tentativa...\n")
            time.sleep(wait)

    sys.stderr.write("ERRO: todas as tentativas falharam.\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
