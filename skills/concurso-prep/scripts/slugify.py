#!/usr/bin/env python3
"""
slugify.py - Converte nome de cargo/órgão em slug UPPERCASE para nome de pasta.

Regras:
1. Remove acentos (Administração -> Administracao)
2. Substitui espaços e separadores por hífen
3. Converte para UPPERCASE
4. Remove caracteres não-alfanuméricos (exceto hífen e underscore)
5. Colapsa hífens repetidos

Uso:
    python slugify.py "EDAS Administração"        -> EDAS-ADMINISTRACAO
    python slugify.py "Técnico Judiciário - Área" -> TECNICO-JUDICIARIO-AREA
    python slugify.py --org "Sedes/DF" 2026       -> SEDES_2026 (modo órgão)
"""
import argparse
import re
import sys
import unicodedata


def remove_acentos(texto: str) -> str:
    """Remove acentos via normalização NFKD."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def slugify_cargo(nome: str) -> str:
    """Converte nome de cargo em slug UPPERCASE com hifens."""
    texto = remove_acentos(nome)
    texto = texto.upper()
    # Substituir separadores comuns por hífen
    texto = re.sub(r"[\s/\\_.,:;|]+", "-", texto)
    # Remover qualquer caractere que não seja A-Z, 0-9 ou hífen
    texto = re.sub(r"[^A-Z0-9-]", "", texto)
    # Colapsar hifens repetidos
    texto = re.sub(r"-{2,}", "-", texto)
    # Remover hifens das pontas
    return texto.strip("-")


def slugify_orgao(orgao: str, ano: int | str) -> str:
    """Gera nome de pasta do concurso: ORGAO_ANO em uppercase."""
    texto = remove_acentos(orgao)
    texto = texto.upper()
    # Pegar só a parte antes de barra (ex: Sedes/DF -> SEDES)
    texto = texto.split("/")[0]
    texto = re.sub(r"[\s\\_.,:;|]+", "-", texto)
    texto = re.sub(r"[^A-Z0-9-]", "", texto)
    texto = re.sub(r"-{2,}", "-", texto).strip("-")
    return f"{texto}_{ano}"


def main():
    parser = argparse.ArgumentParser(description="Slugify para nomes de pasta uppercase")
    parser.add_argument("texto", help="Nome do cargo (ou órgão se --org)")
    parser.add_argument("ano", nargs="?", help="Ano (apenas no modo --org)")
    parser.add_argument("--org", action="store_true",
                        help="Modo órgão: gera ORGAO_ANO")
    args = parser.parse_args()

    if args.org:
        if not args.ano:
            sys.stderr.write("ERRO: modo --org exige o ano como segundo argumento\n")
            sys.exit(1)
        print(slugify_orgao(args.texto, args.ano))
    else:
        print(slugify_cargo(args.texto))


if __name__ == "__main__":
    main()
