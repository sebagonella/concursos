#!/usr/bin/env python3
"""
book_coverage.py - Relatório de cobertura do livro vs. edital.

A partir do mapa de localização (book_index.py), calcula quais faixas de páginas
do livro NÃO correspondem a nenhum assunto do edital — ou seja, o que pode ser
pulado no estudo. Também resume quanto do livro é efetivamente coberto.

Uso:
    python book_coverage.py --mapa mapa-localizacao.json [--out cobertura.md] [--min-gap 15]

--min-gap: tamanho mínimo (em páginas) de um vão para reportá-lo (default 15;
           vãos menores costumam ser só transições de capítulo, não conteúdo pulável).
"""
import argparse
import json
import sys
from pathlib import Path


def coletar_intervalos(mapa: dict) -> list[tuple[int, int, str]]:
    """Retorna [(inicio, fim, assunto)] ordenados, ignorando não-localizados."""
    ivs = []
    for assunto, loc in mapa.get("localizacoes", {}).items():
        p = loc.get("paginas")
        if p and isinstance(p, list) and len(p) == 2:
            ivs.append((p[0], p[1], assunto))
    return sorted(ivs)


def fundir_intervalos(ivs: list[tuple[int, int, str]]) -> list[tuple[int, int]]:
    """Funde intervalos sobrepostos/contíguos para medir cobertura real."""
    if not ivs:
        return []
    fundidos = [(ivs[0][0], ivs[0][1])]
    for ini, fim, _ in ivs[1:]:
        ult_ini, ult_fim = fundidos[-1]
        if ini <= ult_fim + 1:
            fundidos[-1] = (ult_ini, max(ult_fim, fim))
        else:
            fundidos.append((ini, fim))
    return fundidos


def achar_gaps(fundidos: list[tuple[int, int]], total: int, min_gap: int) -> list[tuple[int, int]]:
    """Faixas não cobertas, considerando início do livro, vãos e fim."""
    gaps = []
    # os capítulos iniciais (capa, sumário, prefácio) até o 1º assunto — reportar se grande
    if fundidos and fundidos[0][0] - 1 >= min_gap:
        gaps.append((1, fundidos[0][0] - 1))
    for i in range(len(fundidos) - 1):
        fim_atual = fundidos[i][1]
        ini_prox = fundidos[i + 1][0]
        if ini_prox - fim_atual - 1 >= min_gap:
            gaps.append((fim_atual + 1, ini_prox - 1))
    # do último assunto ao fim do livro
    if fundidos and total and total - fundidos[-1][1] >= min_gap:
        gaps.append((fundidos[-1][1] + 1, total))
    return gaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapa", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--min-gap", type=int, default=15)
    args = ap.parse_args()

    mapa = json.loads(args.mapa.read_text(encoding="utf-8"))
    total = mapa.get("total_paginas", 0)
    livro = mapa.get("livro", "?")

    ivs = coletar_intervalos(mapa)
    fundidos = fundir_intervalos(ivs)
    cobertas = sum(f - i + 1 for i, f in fundidos)
    gaps = achar_gaps(fundidos, total, args.min_gap)
    puláveis = sum(f - i + 1 for i, f in gaps)

    pct_cob = (cobertas / total * 100) if total else 0

    linhas = [
        f"# Cobertura do livro vs. edital — {mapa.get('materia','')}",
        "",
        f"**Livro:** {livro}  ",
        f"**Total de páginas:** {total}  ",
        f"**Páginas cobertas pelo edital:** {cobertas} ({pct_cob:.0f}%)  ",
        f"**Páginas potencialmente puláveis:** {puláveis} ({100-pct_cob:.0f}%)",
        "",
        "## 📉 Faixas que você provavelmente pode pular",
        "",
        "> Páginas do livro que não correspondem a nenhum assunto do seu edital.",
        "> Confira antes de pular em definitivo — pode haver conteúdo de base útil.",
        "",
    ]
    if gaps:
        linhas.append("| Faixa | Páginas | Observação |")
        linhas.append("|---|---|---|")
        for ini, fim in gaps:
            tam = fim - ini + 1
            obs = "pré-textual (capa/sumário/prefácio)" if ini == 1 else "capítulos fora do edital"
            linhas.append(f"| pp. {ini}–{fim} | {tam} | {obs} |")
    else:
        linhas.append("_Nenhuma faixa grande fora do edital — o livro é bem aderente._")

    linhas += [
        "",
        "## 📗 Faixas cobertas (o que estudar)",
        "",
        "| Assunto | Páginas |",
        "|---|---|",
    ]
    for ini, fim, assunto in ivs:
        linhas.append(f"| {assunto} | {ini}–{fim} |")

    saida = "\n".join(linhas) + "\n"
    if args.out:
        args.out.write_text(saida, encoding="utf-8")
        sys.stderr.write(f"OK: relatório salvo em {args.out}\n")
    else:
        print(saida)

    # resumo em stderr para o agente
    sys.stderr.write(f"Cobertura: {pct_cob:.0f}% | puláveis: {puláveis} págs em {len(gaps)} faixas\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
