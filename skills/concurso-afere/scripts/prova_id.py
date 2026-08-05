#!/usr/bin/env python3
"""prova_id.py — identifica prova, caderno e cargo pelo CONTEÚDO do PDF.

Por que pelo conteúdo e não pelo nome do arquivo: no vault chegou um PDF chamado
"PROVA B - ESCRITURÁRIO - AGENTE COMERCIAL.pdf" que era o **gabarito** da prova B,
não o caderno. Nome de arquivo é palpite; o cabeçalho da página é fato.

Três eixos, e confundir qualquer um invalida a aferição inteira:

- **Prova A/B/C** — cadernos com QUESTÕES DIFERENTES, aplicados a grupos distintos.
- **Gabarito 1/2/3/4** — a mesma prova com as ALTERNATIVAS EMBARALHADAS. Usar a
  tabela do caderno errado troca 9 das 10 respostas de Português.
- **Cargo** — Agente Comercial e Agente de Tecnologia dividem a mesma seleção e o
  mesmo "GABARITO 4". Medido: cruzar a prova de um com o gabarito do outro devolve
  10 respostas plausíveis e completamente erradas, sem erro nenhum na saída.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 180


def texto(pdf: Path, layout: bool = True, ini: int | None = None,
          fim: int | None = None) -> str:
    """Texto do PDF via pdftotext.

    `layout=False` respeita a ordem de leitura em duas colunas; `layout=True`
    preserva a geometria (útil para tabela de gabarito).
    """
    cmd = ["pdftotext"]
    if ini:
        cmd += ["-f", str(ini)]
    if fim:
        cmd += ["-l", str(fim)]
    if layout:
        cmd += ["-layout"]
    cmd += [str(pdf), "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except FileNotFoundError:
        sys.stderr.write("ERRO: pdftotext não encontrado (instale poppler-utils).\n")
        raise SystemExit(1)
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"ERRO: pdftotext expirou em {pdf.name}.\n")
        raise SystemExit(1)
    return r.stdout


# Cargos conhecidos. A lista é aberta de propósito: cargo não reconhecido vira
# None e a comparação simplesmente não acusa — melhor não afirmar do que afirmar
# errado. O que NÃO pode é reconhecer dois cargos diferentes e deixar passar.
CARGOS = [
    (r"AGENTE\s+COMERCIAL", "agente-comercial"),
    (r"AGENTE\s+DE\s+TECNOLOGIA", "agente-de-tecnologia"),
    (r"ESCRITUR[ÁA]RIO", "escriturario"),
]


@dataclass
class ProvaID:
    versao: str | None       # A, B, C
    caderno: str | None      # 1..4 — do CADERNO; None em gabarito
    cadernos: list[str]      # 1..4 — os que o GABARITO contém
    cargo: str | None        # slug
    e_gabarito: bool
    arquivo: Path

    def descricao(self) -> str:
        if self.e_gabarito:
            quais = ", ".join(self.cadernos) if self.cadernos else "?"
            return (f"gabarito · versão {self.versao or '?'}"
                    f" · cadernos {quais} · {self.cargo or 'cargo?'}")
        return (f"prova · versão {self.versao or '?'} · caderno {self.caderno or '?'}"
                f" · {self.cargo or 'cargo?'}")


def identificar(pdf: Path) -> ProvaID:
    t = texto(pdf, ini=1, fim=3)
    versao = re.search(r"PROVA\s+([ABC])\b", t, re.I)

    cargo = None
    for pat, nome in CARGOS:
        if re.search(pat, t, re.I):
            cargo = nome
            # 'escriturario' é genérico: só vale se nenhum específico casar
            if nome != "escriturario":
                break

    # O gabarito oficial abre com "BANCO DO BRASIL - Prova X - <cargo>" seguido da
    # tabela; o caderno abre com o cabeçalho de instruções. O marcador confiável é
    # a tabela de respostas ("1 - B" e afins) logo nas primeiras páginas.
    e_gab = bool(re.search(r"\b\d{1,2}\s*-\s*[A-E]\b.*\b\d{1,2}\s*-\s*[A-E]\b", t, re.S))

    # No CADERNO, "GABARITO n" no cabeçalho é a versão daquele exemplar — informação
    # decisiva, é ela que escolhe a tabela. No PDF de GABARITO, o mesmo texto aparece
    # 4 vezes, uma por tabela: reportar só a primeira faria o operador crer que o
    # arquivo serve a um caderno só. São coisas diferentes e ficam em campos diferentes.
    if e_gab:
        todos = texto(pdf)
        cadernos = sorted(set(re.findall(r"GABARITO\s+([1-4])\b", todos, re.I)))
        caderno_do_exemplar = None
    else:
        cadernos = []
        m = re.search(r"GABARITO\s+([1-4])\b", t, re.I)
        caderno_do_exemplar = m.group(1) if m else None

    return ProvaID(versao=versao.group(1).upper() if versao else None,
                   caderno=caderno_do_exemplar, cadernos=cadernos,
                   cargo=cargo, e_gabarito=e_gab, arquivo=pdf)


def conferir_par(prova: ProvaID, gabarito: ProvaID) -> list[str]:
    """Divergências entre caderno e gabarito. Lista vazia = par confiável.

    Não devolve bool: a mensagem precisa NOMEAR o que divergiu. "Não use" sem
    dizer por quê faz o operador tentar de novo com o mesmo par.
    """
    problemas = []
    if prova.e_gabarito:
        problemas.append(f"{prova.arquivo.name} parece ser um GABARITO, não um caderno")
    if not gabarito.e_gabarito:
        problemas.append(f"{gabarito.arquivo.name} não parece ser um gabarito")
    if prova.versao and gabarito.versao and prova.versao != gabarito.versao:
        problemas.append(f"prova é versão {prova.versao}, gabarito é versão {gabarito.versao}")
    if prova.cargo and gabarito.cargo and prova.cargo != gabarito.cargo:
        problemas.append(f"cargo da prova é {prova.cargo}, do gabarito é {gabarito.cargo}")
    if not prova.caderno:
        problemas.append(f"não achei o número do caderno (GABARITO N) em {prova.arquivo.name}")
    elif gabarito.cadernos and prova.caderno not in gabarito.cadernos:
        problemas.append(
            f"o caderno da prova é {prova.caderno}, mas {gabarito.arquivo.name} só tem "
            f"as tabelas {', '.join(gabarito.cadernos)}")
    return problemas


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prova", type=Path)
    ap.add_argument("gabarito", type=Path, nargs="?")
    a = ap.parse_args()

    p = identificar(a.prova)
    print(f"prova    : {a.prova.name}\n  {p.descricao()}")
    if not a.gabarito:
        return 0
    g = identificar(a.gabarito)
    print(f"gabarito : {a.gabarito.name}\n  {g.descricao()}")
    problemas = conferir_par(p, g)
    if problemas:
        print("  ⚠️  DIVERGÊNCIA — NÃO use este par: " + " · ".join(problemas))
        return 2
    print("  ✓ par confiável")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
