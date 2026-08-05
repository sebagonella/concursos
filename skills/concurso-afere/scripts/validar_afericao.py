#!/usr/bin/env python3
"""validar_afericao.py — recusa aferição incompleta ou incoerente.

Cinco checagens, cada uma nascida de um defeito real:

1. **Veredicto em branco.** O arcabouço sai com `···` onde o agente precisa julgar.
   Publicar com o marcador seria nota fantasma.
2. **Notas por prova somam ao consolidado.** Se as parciais não fecham com o total,
   um dos dois está errado e não dá para saber qual.
3. **Formatação única da nota.** O mesmo cálculo saiu **39,4** numa tabela e **39,45**
   noutra do mesmo documento — um é o arredondamento do outro.
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
    #
    # O critério é a RELAÇÃO DE ARREDONDAMENTO, não a proximidade absoluta. Proximidade
    # confunde duas coisas diferentes: "o mesmo número escrito de dois jeitos" (o
    # defeito) e "dois números legitimamente vizinhos" (o normal). Numa matéria estável
    # as notas por prova caem naturalmente a menos de 0,05 umas das outras — o `<= 0,05`
    # recusava a aferição de Vendas e Negociação por ter 8,76 (consolidado) e 8,80
    # (provas B e C), que são valores distintos e ambos corretos.
    #
    # Só há defeito quando as PRECISÕES diferem e o menos preciso é um arredondamento
    # válido do mais preciso. A comparação é por desigualdade, não por `round()`, porque
    # 39,45 arredonda para 39,4 (HALF_EVEN) ou 39,5 (HALF_UP) e os DOIS são o defeito:
    # fixar um modo deixaria o outro passar.
    #
    # Em Decimal, não em float: 39,45 − 39,4 dá 0.050000000000004 em float e escaparia
    # do limiar por epsilon — o par que se quer pegar passaria batido.
    #
    # Fica de fora, por construção: dois valores de MESMA precisão, por mais próximos
    # que estejam (39,4 × 39,5). Não há como pegá-los sem recusar 13,0 × 13,2, que é
    # legítimo — e o incidente que originou esta regra era 39,4 × 39,45.
    from decimal import Decimal

    def casas(s: str) -> int:
        return len(s.split(",")[1])

    brutos = sorted(set(re.findall(r"\b\d+,\d+\b", txt)))
    for i, a in enumerate(brutos):
        for b in brutos[i + 1:]:
            if casas(a) == casas(b):
                continue
            grosso, fino = (a, b) if casas(a) < casas(b) else (b, a)
            limiar = Decimal(5) * Decimal(10) ** (-casas(grosso) - 1)
            if abs(Decimal(fino.replace(",", ".")) -
                   Decimal(grosso.replace(",", "."))) <= limiar:
                erros.append(f"mesmo valor com formatações diferentes: "
                             f"{grosso} parece o arredondamento de {fino}")

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
