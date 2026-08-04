#!/usr/bin/env python3
"""casar_materias.py — liga a matéria da PROVA à matéria APROFUNDADA no vault.

Duas fontes, e nenhuma sozinha basta:

- **A prova** declara as matérias na tabela da capa ("Língua Portuguesa … 1 a 10").
- **O vault** guarda os aprofundamentos em `{escopo}/03-APROFUNDAMENTO/{materia}/assuntos/`.

A descoberta no vault é pelo **filesystem**, não pelo `.meta.json`: o meta do SEDES tem
`materias_por_cargo`, o do BB **não tem** — depender dele quebraria em metade dos
concursos. É a mesma escolha do `site_collector.coletar_materia()`.

Sem casamento confiável a skill **pergunta**, nunca adivinha — a regra do repo sobre
não inferir vínculo por slug vale aqui igual.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrair_questoes import Faixa, distribuicao  # noqa: E402

LIMIAR = 0.62


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()


def _tokens(s: str) -> set[str]:
    # "de", "do", "e" não distinguem matéria nenhuma
    vazias = {"de", "do", "da", "dos", "das", "e", "em", "a", "o"}
    return {t for t in norm(s).split() if t not in vazias and len(t) > 1}


def similaridade(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class MateriaVault:
    materia_id: str
    escopo: str              # _COMUM ou a sigla do cargo
    dir: Path
    n_assuntos: int
    niveis: list[str]        # padrao, detalhado — os que existem


def materias_do_vault(concurso_dir: Path, escopos: list[str] | None = None
                      ) -> list[MateriaVault]:
    """Toda matéria com `assuntos/` sob `03-APROFUNDAMENTO`, em qualquer escopo."""
    out: list[MateriaVault] = []
    for esc_dir in sorted(concurso_dir.iterdir()):
        if not esc_dir.is_dir() or esc_dir.name.startswith("."):
            continue
        if escopos and esc_dir.name not in escopos:
            continue
        raiz = esc_dir / "03-APROFUNDAMENTO"
        if not raiz.is_dir():
            continue
        for mat in sorted(raiz.iterdir()):
            assuntos = mat / "assuntos"
            if not assuntos.is_dir():
                continue
            niveis: set[str] = set()
            n = 0
            for a in assuntos.iterdir():
                if not a.is_dir():
                    continue
                n += 1
                for aprof in a.iterdir():
                    if aprof.is_dir() and "--" in aprof.name:
                        niveis.add(aprof.name.split("--")[0])
            out.append(MateriaVault(materia_id=mat.name, escopo=esc_dir.name,
                                    dir=mat, n_assuntos=n,
                                    niveis=sorted(niveis)))
    return out


def escopos_do_cargo(concurso_dir: Path, cargo: str) -> list[str]:
    """O cargo enxerga as matérias dele MAIS as do `_COMUM` — é como o candidato
    estuda: as gerais valem para todos, as específicas são dele."""
    alvo = cargo.upper()
    nomes = [d.name for d in concurso_dir.iterdir() if d.is_dir()]
    if alvo not in nomes:
        candidatos = [n for n in nomes if alvo in n.upper()]
        if len(candidatos) != 1:
            raise SystemExit(
                f"ERRO: cargo '{cargo}' não encontrado. Disponíveis: "
                + ", ".join(n for n in sorted(nomes) if not n.startswith(".")))
        alvo = candidatos[0]
    return (["_COMUM"] if "_COMUM" in nomes else []) + [alvo]


@dataclass
class Casamento:
    faixa: Faixa
    materia: MateriaVault | None
    score: float


def casar(prova: Path, concurso_dir: Path,
          escopos: list[str] | None = None) -> list[Casamento]:
    vault = materias_do_vault(concurso_dir, escopos)
    out: list[Casamento] = []
    for f in distribuicao(prova):
        melhor, melhor_score = None, 0.0
        for mv in vault:
            s = max(similaridade(f.nome, mv.materia_id),
                    similaridade(f.nome, mv.materia_id.replace("-", " ")))
            if s > melhor_score:
                melhor, melhor_score = mv, s
        out.append(Casamento(faixa=f,
                             materia=melhor if melhor_score >= LIMIAR else None,
                             score=melhor_score))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prova", type=Path, required=True)
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--cargo", help="restringe aos escopos do cargo (+ _COMUM)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    escopos = escopos_do_cargo(a.concurso_dir, a.cargo) if a.cargo else None
    res = casar(a.prova, a.concurso_dir, escopos)

    if a.json:
        print(json.dumps([{
            "materia_prova": c.faixa.nome,
            "primeira": c.faixa.primeira, "ultima": c.faixa.ultima,
            "materia_id": c.materia.materia_id if c.materia else None,
            "escopo": c.materia.escopo if c.materia else None,
            "n_assuntos": c.materia.n_assuntos if c.materia else 0,
            "niveis": c.materia.niveis if c.materia else [],
            "score": round(c.score, 3),
        } for c in res], ensure_ascii=False, indent=2))
        return 0

    for c in res:
        if c.materia:
            print(f"  ✓ {c.faixa.nome:<36} Q{c.faixa.primeira}–{c.faixa.ultima:<3} → "
                  f"{c.materia.escopo}/{c.materia.materia_id} "
                  f"({c.materia.n_assuntos} assuntos · {', '.join(c.materia.niveis)})")
        else:
            print(f"  · {c.faixa.nome:<36} Q{c.faixa.primeira}–{c.faixa.ultima:<3} → "
                  f"sem aprofundamento no vault")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
