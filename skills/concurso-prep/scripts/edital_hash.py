#!/usr/bin/env python3
"""
edital_hash.py — calcula o `edital_hash`, num lugar só. (v1.0.0)

O `SKILL.md` define, desde a 1.3.0, que `edital_hash` é o SHA-256 do **texto
extraído** do edital, e que o R.0.2 compara esse hash com o gravado no
`.meta.json` para decidir se há o que reconciliar. A regra existia; o executor,
não. Resultado medido no vault:

    SEDES  ->  edital_hash == SHA-256 dos BYTES DO PDF   (fora da regra)
    BB     ->  edital_hash == SHA-256 do TEXTO           (dentro da regra)
               + um campo `edital_pdf_sha256` que o SKILL nunca definiu

Duas execuções, duas convenções, porque quem calculava era o modelo. A
consequência prática: no SEDES o R.0.2 nunca reconhece "edital idêntico", e um
mesmo edital salvo de novo (bytes diferentes, texto igual) vira `V3-RETIFICADO`
espúrio.

## Canonicalização (é o que torna o hash reproduzível)

Antes de hashear o texto:
  1. normaliza fim de linha (CRLF/CR -> LF)
  2. remove espaço/tab no fim de cada linha
  3. remove linhas em branco do fim do arquivo
  4. codifica em UTF-8

Sem isso o hash muda com detalhe irrelevante — e hash que muda à toa acusa
retificação onde não houve.

Os dois hashes são gravados, com nomes distintos e significados distintos:
  `edital_hash`       -> texto canonicalizado (é o que decide reconciliação)
  `edital_pdf_sha256` -> bytes do arquivo (rastreabilidade do arquivo exato)
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def canonicalizar(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    linhas = [ln.rstrip(" \t") for ln in texto.split("\n")]
    while linhas and not linhas[-1]:
        linhas.pop()
    return "\n".join(linhas)


def hash_texto(texto: str) -> str:
    return hashlib.sha256(canonicalizar(texto).encode("utf-8")).hexdigest()


def hash_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def extrair_texto(path: Path) -> str:
    """Mesma extração da Etapa 1 — o hash tem de ser do texto que a skill lê."""
    if path.suffix.lower() == ".pdf":
        try:
            r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                               capture_output=True, text=True, check=True)
            return r.stdout
        except FileNotFoundError:
            sys.stderr.write("ERRO: pdftotext nao encontrado (poppler-utils).\n")
            sys.exit(3)
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"ERRO: pdftotext falhou: {e}\n")
            sys.exit(3)
    return path.read_text(encoding="utf-8", errors="replace")


def hashes_do_edital(path: Path) -> dict:
    texto = extrair_texto(path)
    if not canonicalizar(texto).strip():
        # Texto vazio hasheia igual para qualquer PDF-imagem: dois editais
        # diferentes sairiam "idênticos". Isso é pendência de OCR, não hash.
        sys.stderr.write(
            f"ERRO: nao foi possivel extrair texto de {path.name} — provavelmente "
            f"PDF-imagem. Sem texto nao ha hash confiavel (todos os vazios "
            f"colidem). Registre pendencia de OCR.\n")
        sys.exit(4)
    return {"edital_hash": hash_texto(texto),
            "edital_pdf_sha256": hash_bytes(path) if path.suffix.lower() == ".pdf" else None,
            "chars_extraidos": len(texto)}


def main():
    ap = argparse.ArgumentParser(
        description="Calcula edital_hash (texto canonicalizado) e edital_pdf_sha256")
    ap.add_argument("edital", type=Path)
    ap.add_argument("--comparar", type=Path, default=None,
                    help="pasta do concurso ou .meta.json com o hash já gravado")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.edital.exists():
        sys.stderr.write(f"ERRO: nao existe: {args.edital}\n")
        sys.exit(1)

    res = hashes_do_edital(args.edital)

    if args.comparar:
        p = args.comparar / ".meta.json" if args.comparar.is_dir() else args.comparar
        gravado = {}
        if p.exists():
            try:
                gravado = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                gravado = {}
        antigo = gravado.get("edital_hash")
        res["hash_gravado"] = antigo
        if antigo is None:
            res["veredito"] = "sem hash gravado — tratar como edital novo"
        elif antigo == res["edital_hash"]:
            res["veredito"] = "IDENTICO — nada a reconciliar"
        elif antigo == res["edital_pdf_sha256"]:
            # O SEDES está exatamente aqui.
            res["veredito"] = ("hash gravado é do PDF, não do texto (convenção "
                               "anterior à 1.7.0) — regravar antes de comparar")
        else:
            res["veredito"] = "DIFERENTE — seguir com a reconciliação"

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        for k, v in res.items():
            print(f"{k}: {v}")

    sys.exit(0 if res.get("veredito", "").startswith("IDENTICO") or not args.comparar
             else 1)


if __name__ == "__main__":
    main()
