#!/usr/bin/env python3
"""divergencia_niveis.py — o `detalhado` cobre o que o `padrao` promete?

A hipótese natural é que "detalhado" seja "padrão com mais profundidade". **Não é o
que o vault mostra.** Medido nos 9 assuntos de Língua Portuguesa do BB: em média
**22%** dos conceitos que o `padrao` declara na própria seção "🧩 Subtópicos que este
assunto engloba" **não aparecem em lugar nenhum** do `.md` do `detalhado` — pior caso
44%, em compreensão de textos.

Isso não é curiosidade: custou 4 das 30 questões aferidas, todas de coesão referencial,
que existe no `padrao` e não no `detalhado`.

A medição é por palavra, então tem margem — "anafora" ausente é forte, "frases" pode
ser ruído. Serve para **apontar onde olhar**, não para condenar sozinha.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# `arquivo_principal()` mora na concurso-aprofunda e é a fonte de verdade sobre qual
# `.md` de uma pasta de aprofundamento é o do assunto. Reimplementar já custou caro:
# uma varredura ad-hoc pegou `_fonte-notebooklm.md` (o `_` ordena antes das letras) e
# reportou 17 artigos ausentes onde havia 8.
_APROFUNDA = (Path(__file__).resolve().parents[3]
              / "concurso-aprofunda" / "scripts")
if _APROFUNDA.is_dir():
    sys.path.insert(0, str(_APROFUNDA))
try:
    from notebooklm_pack import arquivo_principal        # type: ignore
except ImportError:  # instalação isolada: degrada com a MESMA regra de exclusão
    def arquivo_principal(pasta: Path):                  # type: ignore
        exato = pasta / f"{pasta.name}.md"
        if exato.exists():
            return exato
        cands = [p for p in sorted(pasta.glob("*.md"))
                 if not p.name.startswith(("flashcards-", "_", "00-", "report-",
                                           "teste-", "tabela-"))]
        return cands[0] if cands else None


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s)


def corpo(md: Path) -> str:
    t = md.read_text(encoding="utf-8")
    m = re.match(r"---\n.*?\n---\n", t, re.S)
    return norm(t[m.end():] if m else t)


def subtopicos_declarados(md: Path) -> set[str]:
    """Palavras de conteúdo da seção '🧩 Subtópicos que este assunto engloba'."""
    t = md.read_text(encoding="utf-8")
    m = re.search(r"##[^\n]*Subt[óo]picos[^\n]*\n(.*?)(?=\n##\s)", t, re.S)
    if not m:
        return set()
    return {w for w in norm(m.group(1)).split() if len(w) > 5}


def _pasta_do_nivel(assunto_dir: Path, nivel: str) -> Path | None:
    for d in sorted(assunto_dir.iterdir()):
        if d.is_dir() and d.name.split("--")[0] == nivel:
            return d
    return None


def medir(materia_dir: Path, base: str = "padrao",
          alvo: str = "detalhado") -> dict:
    assuntos_dir = materia_dir / "assuntos"
    linhas, tot_conc, tot_perd = [], 0, 0
    for a in sorted(assuntos_dir.iterdir()):
        if not a.is_dir():
            continue
        pb, pa = _pasta_do_nivel(a, base), _pasta_do_nivel(a, alvo)
        if not pb or not pa:
            continue
        mb, ma = arquivo_principal(pb), arquivo_principal(pa)
        if not mb or not ma:
            continue
        conceitos = subtopicos_declarados(mb)
        if not conceitos:
            continue
        texto_alvo = corpo(ma)
        perdidos = sorted(w for w in conceitos if w not in texto_alvo)
        tot_conc += len(conceitos)
        tot_perd += len(perdidos)
        linhas.append({"assunto": a.name, "conceitos": len(conceitos),
                       "perdidos": len(perdidos),
                       "perda": round(len(perdidos) / len(conceitos), 3),
                       "exemplos": perdidos[:8]})
    return {"materia": materia_dir.name, "base": base, "alvo": alvo,
            "assuntos_comparados": len(linhas),
            "conceitos": tot_conc, "perdidos": tot_perd,
            "perda_media": round(tot_perd / tot_conc, 3) if tot_conc else None,
            "por_assunto": sorted(linhas, key=lambda x: -x["perda"])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--materia-dir", type=Path, required=True)
    ap.add_argument("--base", default="padrao")
    ap.add_argument("--alvo", default="detalhado")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    r = medir(a.materia_dir, a.base, a.alvo)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0
    if not r["assuntos_comparados"]:
        print(f"  {r['materia']}: não há assunto com os dois níveis "
              f"({a.base} e {a.alvo}) — nada a comparar.")
        return 0
    print(f"  {r['materia']} · {r['assuntos_comparados']} assuntos com os dois níveis")
    for l in r["por_assunto"]:
        print(f"    {l['assunto'][:44]:<44} {l['conceitos']:>3} conceitos · "
              f"{l['perdidos']:>2} ausentes ({l['perda']:.0%})")
        if l["exemplos"]:
            print(f"      ex.: {', '.join(l['exemplos'][:6])}")
    print(f"    {'TOTAL':<44} {r['conceitos']:>3} · {r['perdidos']:>2} "
          f"({r['perda_media']:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
