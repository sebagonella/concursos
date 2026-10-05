#!/usr/bin/env python3
"""comparar_gabaritos.py — do gabarito preliminar ao definitivo: o que rejulgar.

Entre o preliminar e o definitivo a banca julga os recursos: troca a resposta de umas
questões e anula outras. Uma aferição feita sobre o preliminar continua quase toda
válida — o veredicto "o material responde?" depende do conteúdo da questão, não da
letra —, mas cada questão alterada precisa de nova leitura, e cada anulada sai do
denominador.

O script só APONTA. Não reescreve a aferição: ela guarda o julgamento do agente, e
trocar a letra na tabela sem reler a questão seria fingir que o veredicto continua
certo. Mesma regra do `build_afericao.py`: o determinístico é do script, o juízo é do
agente.

    comparar_gabaritos.py --antes PRELIMINAR.pdf --depois DEFINITIVO.pdf \\
        --afericao .../00-AFERICAO-LINGUA-PORTUGUESA--...md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gabarito import GabaritoErro, respostas  # noqa: E402
from quadrix import SecaoGabarito, banca_do_pdf, ler_gabarito, tokens  # noqa: E402


def frontmatter(md: Path) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", md.read_text(encoding="utf-8"), re.S)
    out = {}
    for linha in (m.group(1).split("\n") if m else []):
        if ":" in linha:
            k, v = linha.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def questoes_da_afericao(md: Path) -> list[int]:
    """Os números da tabela "Questão a questão" — as questões que o documento julgou."""
    t = md.read_text(encoding="utf-8")
    # `[^\n]*`, não `.*`: com DOTALL o `.*` do cabeçalho engolia o documento inteiro
    m = re.search(r"^## [^\n]*Quest[ãa]o a quest[ãa]o[^\n]*\n(.*?)(?=^## |\Z)", t,
                  re.M | re.S)
    if not m:
        raise SystemExit(f"ERRO: {md.name} não tem a seção 'Questão a questão'")
    return sorted({int(n) for n in re.findall(r"^\|\s*(\d{1,3})\s*\|", m.group(1), re.M)})


def secao_quadrix(pdf: Path, cargo: str, tipo: str | None) -> SecaoGabarito:
    gab = ler_gabarito(pdf)
    alvo = tokens(cargo)
    achadas = [s for s in gab.secoes if tokens(s.cargo) == alvo and s.tipo == tipo]
    if len(achadas) != 1:
        raise SystemExit(
            f"ERRO: {pdf.name} tem {len(achadas)} seção(ões) para '{cargo}' tipo "
            f"{tipo or '—'} — esperava 1. Seções: "
            + ", ".join(s.rotulo for s in gab.secoes))
    return achadas[0]


def diferencas(antes: dict[int, str], anul_antes: set[int], depois: dict[int, str],
               anul_depois: set[int], questoes: list[int] | None = None) -> dict:
    universo = sorted((set(antes) | anul_antes | set(depois) | anul_depois)
                      if questoes is None else set(questoes))
    alteradas, anuladas_novas, desanuladas, sumidas = [], [], [], []
    for q in universo:
        a_anul, d_anul = q in anul_antes, q in anul_depois
        if d_anul and not a_anul:
            anuladas_novas.append(q)
        elif a_anul and not d_anul:
            desanuladas.append(q)
        elif not d_anul and q not in depois:
            sumidas.append(q)
        elif not a_anul and antes.get(q) != depois.get(q):
            alteradas.append({"questao": q, "antes": antes.get(q), "depois": depois[q]})
    return {"alteradas": alteradas, "anuladas_novas": anuladas_novas,
            "desanuladas": desanuladas, "ausentes_no_depois": sumidas,
            "rejulgar": sorted({x["questao"] for x in alteradas}
                               | set(anuladas_novas) | set(desanuladas))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--antes", type=Path, required=True, help="gabarito anterior (preliminar)")
    ap.add_argument("--depois", type=Path, required=True, help="gabarito novo (definitivo)")
    ap.add_argument("--afericao", type=Path, action="append",
                    help="aferição a conferir (repetível). Na Quadrix, cargo e tipo vêm "
                         "do frontmatter dela")
    ap.add_argument("--cargo-prova", help="Quadrix, sem --afericao: a seção do gabarito")
    ap.add_argument("--tipo", help="Quadrix, sem --afericao: o tipo do caderno")
    ap.add_argument("--caderno", help="CESGRANRIO: o número do caderno (GABARITO N)")
    a = ap.parse_args()

    quadrix = banca_do_pdf(a.antes) == "quadrix"
    alvos: list[tuple[Path | None, str | None, str | None, list[int] | None]] = []
    for md in a.afericao or []:
        fm = frontmatter(md)
        tipo = fm.get("tipo_caderno")
        alvos.append((md, fm.get("cargo_prova") or a.cargo_prova,
                      None if tipo in (None, "unico") else tipo, questoes_da_afericao(md)))
    if not alvos:
        alvos.append((None, a.cargo_prova, a.tipo, None))

    saida = {"antes": a.antes.name, "depois": a.depois.name, "comparacoes": []}
    for md, cargo, tipo, qs in alvos:
        if quadrix:
            if not cargo:
                raise SystemExit("ERRO: diga o cargo com --cargo-prova (ou passe uma "
                                 "aferição Quadrix, que o traz no frontmatter)")
            sa, sd = secao_quadrix(a.antes, cargo, tipo), secao_quadrix(a.depois, cargo, tipo)
            dif = diferencas(sa.respostas, sa.anuladas, sd.respostas, sd.anuladas, qs)
            rotulo = sa.rotulo
            fontes = (ler_gabarito(a.antes).fonte, ler_gabarito(a.depois).fonte)
        else:
            if not a.caderno:
                raise SystemExit("ERRO: na CESGRANRIO diga o caderno com --caderno")
            try:
                ra, rd = respostas(a.antes, a.caderno), respostas(a.depois, a.caderno)
            except GabaritoErro as e:
                raise SystemExit(f"ERRO: {e}")
            dif = diferencas(ra, set(), rd, set(), qs)
            rotulo, fontes = f"caderno {a.caderno}", (None, None)
        if fontes[1] == "preliminar":
            sys.stderr.write(f"AVISO: {a.depois.name} ainda é um gabarito PRELIMINAR\n")
        saida["comparacoes"].append({
            "afericao": str(md) if md else None, "secao": rotulo,
            "fonte_antes": fontes[0], "fonte_depois": fontes[1], **dif})
    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
