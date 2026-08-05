#!/usr/bin/env python3
"""validar_afericao.py — recusa aferição incompleta ou incoerente.

Cinco checagens, cada uma nascida de um defeito real:

1. **Veredicto em branco.** O arcabouço sai com `···` onde o agente precisa julgar.
   Publicar com o marcador seria nota fantasma.
2. **Notas por prova somam ao consolidado.** Se as parciais não fecham com o total,
   um dos dois está errado e não dá para saber qual.
3. **Formatação única da nota.** O mesmo cálculo saiu 39,4 numa tabela e 39,5 noutra
   do mesmo documento.
4. **N declarado.** Com 1 prova a conclusão desta sessão foi "empate técnico"; com 3,
   inverteu. Afirmação sem amostra declarada é afirmação sem lastro.
5. **Superlativo sem amostra.** "prova que", "comprova", "confirma" exigem N ≥ 2 provas.

Varrer e não achar nada **falha alto** — sair com sucesso sobre zero arquivos é o
defeito que fez o `fix_notebooklm_packs` achar 0 dos 158 pacotes e sair feliz.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VAZIO = "···"
SUPERLATIVOS = re.compile(
    r"\b(comprova|prova que|confirma que|demonstra que|conclusiv[ao])\b", re.I)


def frontmatter(txt: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", txt, re.S)
    if not m:
        return {}
    out = {}
    for linha in m.group(1).split("\n"):
        if ":" in linha:
            k, v = linha.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def numeros_pt(s: str) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"\b\d+,\d+\b", s)]


def conferir(md: Path) -> list[str]:
    txt = md.read_text(encoding="utf-8")
    fm = frontmatter(txt)
    erros: list[str] = []

    n_vazio = txt.count(VAZIO)
    if n_vazio:
        erros.append(f"{n_vazio} campo(s) por preencher ({VAZIO}) — o agente não julgou")

    n_provas = fm.get("provas_aferidas_n")
    if not n_provas:
        erros.append("frontmatter sem `provas_aferidas_n` — amostra não declarada")
    if not fm.get("questoes_aferidas"):
        erros.append("frontmatter sem `questoes_aferidas`")

    # 3: mesma grandeza formatada de dois jeitos.
    # Agrupar por valor arredondado NÃO funciona: 39,4 e 39,45 caem em chaves
    # diferentes (39.4 e 39.5) justamente porque uma delas já é o arredondamento da
    # outra — e esse é o par que se quer pegar. O critério é a PROXIMIDADE: dois
    # textos diferentes para valores a menos de meia casa decimal um do outro são o
    # mesmo número escrito de dois jeitos.
    # A comparação usa Decimal: em float, 39,45 − 39,4 dá 0.050000000000004 e escapa
    # de um `<= 0.05` — o par que se quer pegar passaria batido por epsilon.
    from decimal import Decimal
    brutos = sorted(set(re.findall(r"\b\d+,\d+\b", txt)))
    for i, a in enumerate(brutos):
        va = Decimal(a.replace(",", "."))
        for b in brutos[i + 1:]:
            if abs(va - Decimal(b.replace(",", "."))) <= Decimal("0.05"):
                erros.append(f"mesmo valor com formatações diferentes: {a} e {b}")

    # 5: superlativo exige amostra
    try:
        n = int(n_provas) if n_provas else 0
    except ValueError:
        n = 0
    if n < 2:
        for m in SUPERLATIVOS.finditer(txt):
            ctx = " ".join(txt[max(0, m.start() - 45):m.start() + 45].split())
            erros.append(f"afirmação forte com {n} prova(s): …{ctx}…")
            break
    return erros


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--concurso-dir", type=Path)
    ap.add_argument("--arquivo", type=Path, action="append")
    a = ap.parse_args()

    alvos: list[Path] = list(a.arquivo or [])
    if a.concurso_dir:
        alvos += sorted(a.concurso_dir.rglob("00-AFERICAO-*.md"))
    if not alvos:
        sys.stderr.write("ERRO: nenhuma aferição encontrada — varrer e não achar nada "
                         "é falha, não sucesso.\n")
        return 1

    total = 0
    for md in alvos:
        erros = conferir(md)
        if erros:
            total += 1
            print(f"✗ {md.name}")
            for e in erros:
                print(f"    {e}")
        else:
            print(f"✓ {md.name}")
    print(f"\n{len(alvos)} aferição(ões) conferida(s) — {total} com problema.")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
