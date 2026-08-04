#!/usr/bin/env python3
"""gabarito.py — respostas oficiais da faixa de questões, do caderno CERTO.

O PDF de gabarito da CESGRANRIO traz uma tabela por caderno (GABARITO 1 a 4), cada
uma com as respostas embaralhadas de forma diferente. Ler a primeira tabela da
página é o erro mais fácil e o mais caro: no BB 2022/001, o caderno 1 e o caderno 4
divergem em 9 das 10 questões de Português.

    caderno 1: 1-B 2-B 3-E 4-C 5-A 6-D 7-B 8-E 9-D 10-C
    caderno 4: 1-D 2-D 3-A 4-C 5-E 6-B 7-A 8-D 9-B 10-E
                  ^   ^   ^       ^   ^   ^   ^   ^   ^
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prova_id import texto  # noqa: E402


class GabaritoErro(Exception):
    """Falha alto: gabarito ilegível é pior que gabarito ausente, porque o
    resultado parcial parece válido."""


def tabela_do_caderno(pdf: Path, caderno: str) -> str:
    """Recorta o bloco da tabela daquele caderno."""
    t = texto(pdf)
    marcas = [m.start() for m in re.finditer(rf"GABARITO\s+{re.escape(caderno)}\b", t)]
    if not marcas:
        disponiveis = sorted(set(re.findall(r"GABARITO\s+([1-4])\b", t)))
        raise GabaritoErro(
            f"não achei a tabela do caderno GABARITO {caderno} em {pdf.name}"
            + (f" (o arquivo tem: {', '.join(disponiveis)})" if disponiveis else ""))
    ini = marcas[0]
    # o bloco termina no próximo "GABARITO n" — ou no fim do arquivo
    prox = [m.start() for m in re.finditer(r"GABARITO\s+[1-4]\b", t) if m.start() > ini]
    return t[ini:prox[0]] if prox else t[ini:]


def respostas(pdf: Path, caderno: str, secao: str | None = None,
              questoes: range | None = None) -> dict[int, str]:
    """Respostas do caderno. `secao` recorta a matéria (ex.: "LÍNGUA PORTUGUESA").

    Quando `secao` é dada, o recorte vai do título dela até o título seguinte em
    CAIXA ALTA — é o que separa Português de Inglês na mesma tabela.
    """
    bloco = tabela_do_caderno(pdf, caderno)
    if secao:
        i = bloco.upper().find(secao.upper())
        if i < 0:
            raise GabaritoErro(f"seção '{secao}' não encontrada na tabela do caderno {caderno}")
        resto = bloco[i + len(secao):]
        # próximo cabeçalho de seção: linha em caixa alta com 8+ caracteres
        m = re.search(r"\n\s*[A-ZÁÂÃÉÊÍÓÔÕÚÇ][A-ZÁÂÃÉÊÍÓÔÕÚÇ \-]{7,}\s*\n", resto)
        bloco = resto[:m.start()] if m else resto

    achado = {int(q): r.upper() for q, r in re.findall(r"(\d{1,2})\s*-\s*([A-Ea-e])\b", bloco)}
    if not achado:
        raise GabaritoErro(f"nenhuma resposta legível no caderno {caderno}"
                           + (f", seção '{secao}'" if secao else ""))
    if questoes is not None:
        faltam = [q for q in questoes if q not in achado]
        if faltam:
            raise GabaritoErro(
                f"faltaram as questões {faltam} no caderno {caderno}"
                + (f", seção '{secao}'" if secao else "")
                + " — recorte de seção errado ou tabela em formato novo")
        return {q: achado[q] for q in questoes}
    return dict(sorted(achado.items()))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("gabarito", type=Path)
    ap.add_argument("--caderno", required=True, help="1 a 4")
    ap.add_argument("--secao", help='ex.: "LÍNGUA PORTUGUESA"')
    ap.add_argument("--de", type=int, help="primeira questão")
    ap.add_argument("--ate", type=int, help="última questão")
    a = ap.parse_args()
    faixa = range(a.de, a.ate + 1) if a.de and a.ate else None
    try:
        r = respostas(a.gabarito, a.caderno, a.secao, faixa)
    except GabaritoErro as e:
        sys.stderr.write(f"ERRO: {e}\n")
        return 1
    print(" ".join(f"{q}-{v}" for q, v in r.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
