#!/usr/bin/env python3
"""build_afericao.py — monta o ARCABOUÇO da aferição. Não julga.

Mesma divisão de `build_subject_md.py`: o script prepara tudo o que é determinístico
(faixa oficial de questões, gabarito do caderno certo, matéria casada, níveis
existentes, divergência entre níveis, ressalva de tautologia) e deixa **uma linha por
questão com o veredicto em branco**, para o agente preencher lendo o material.

Preencher veredicto por conta seria inventar nota — e a nota é justamente o que se
quer confiável. `validar_afericao.py` recusa arcabouço entregue com campo vazio.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from casar_materias import casar, escopos_do_cargo, norm          # noqa: E402
from divergencia_niveis import medir                              # noqa: E402
from extrair_questoes import bloco_da_materia                     # noqa: E402
from gabarito import GabaritoErro, respostas                      # noqa: E402
from prova_id import conferir_par, identificar                    # noqa: E402

TPL = Path(__file__).resolve().parents[1] / "assets/templates/afericao-materia.md.tpl"
VAZIO = "···"          # marcador do que o agente precisa preencher


def _fmt(n: float) -> str:
    """Formatação ÚNICA de nota. Existe porque o mesmo número saiu como 39,4 numa
    tabela e 39,5 noutra do mesmo documento — dois valores para um cálculo só."""
    return f"{n:.2f}".replace(".", ",")


def _fmt1(n: float) -> str:
    return f"{n:.1f}".replace(".", ",")


def ressalva_tautologia(concurso_dir: Path) -> str:
    """Se o vault foi montado do MESMO edital da prova, a cobertura de tópico não
    mede nada — os assuntos saíram do programa que a prova cobra. A ressalva é
    escrita sozinha para não depender de alguém lembrar."""
    meta = concurso_dir / ".meta.json"
    modo = None
    if meta.exists():
        try:
            modo = json.loads(meta.read_text(encoding="utf-8")).get("modo")
        except json.JSONDecodeError:
            pass
    if modo == "previsto":
        return (
            "\nO material deste concurso está em **`modo: previsto`** e foi montado a "
            "partir de um **edital anterior usado como proxy**. Se a prova aferida for "
            "desse mesmo edital, a **cobertura de tópico é tautológica** — os assuntos "
            "saíram do programa que ela cobra, e 100% de aderência é aritmética, não "
            "validação. O que a prova mede de verdade é a **profundidade**: dado que o "
            "tópico está lá, o material escrito basta para responder?\n")
    return ("\nConfira se o material foi montado a partir do mesmo edital da prova. Se "
            "foi, a cobertura de tópico não mede nada — só a profundidade mede.\n")


def coletar(prova: Path, gab: Path, concurso_dir: Path, materia_alvo: str,
            escopos: list[str] | None) -> dict:
    pid, gid = identificar(prova), identificar(gab)
    problemas = conferir_par(pid, gid)
    if problemas:
        raise SystemExit("ERRO: par prova/gabarito inconsistente — "
                         + " · ".join(problemas))

    alvo = norm(materia_alvo)
    c = next((x for x in casar(prova, concurso_dir, escopos)
              if norm(x.faixa.nome) == alvo or alvo in norm(x.faixa.nome)
              or (x.materia and alvo in norm(x.materia.materia_id))), None)
    if c is None:
        raise SystemExit(f"ERRO: matéria '{materia_alvo}' não está na capa de {prova.name}")
    if c.materia is None:
        raise SystemExit(f"ERRO: '{c.faixa.nome}' não tem aprofundamento no vault "
                         f"(score {c.score:.2f}) — nada a aferir")

    faixa = range(c.faixa.primeira, c.faixa.ultima + 1)
    try:
        gabs = respostas(gab, pid.caderno, c.faixa.nome, faixa)
    except GabaritoErro:
        gabs = respostas(gab, pid.caderno, None, faixa)
    bloco, avisos = bloco_da_materia(prova, c.faixa)
    return {"prova": prova, "versao": pid.versao, "caderno": pid.caderno,
            "faixa": c.faixa, "materia": c.materia, "gabarito": gabs,
            "bloco": bloco, "avisos": avisos}


def montar(dados: list[dict], concurso_dir: Path, banca: str) -> str:
    m = dados[0]["materia"]
    niveis = m.niveis
    n_q = sum(len(d["gabarito"]) for d in dados)

    cab = " | ".join(f"`{n}`" for n in niveis)
    sep = "|".join(["---:"] * len(niveis))
    tabela = (f"| | {cab} |\n|---|{sep}|\n"
              + "\n".join(f"| {rot} | " + " | ".join([VAZIO] * len(niveis)) + " |"
                          for rot in ("Questões plenamente respondidas",
                                      "Respondidas em parte", "Não respondidas",
                                      "**Sem material** (fora do denominador)",
                                      "**Nota**")))

    linhas = ["| Q | " + " | ".join(f"{d['versao'] or '?'}" for d in dados)
              + " | Assunto cobrado | " + " | ".join(f"`{n}`" for n in niveis) + " |",
              "|:-:|" + "|".join([":-:"] * len(dados)) + "|---|"
              + "|".join([":-:"] * len(niveis)) + "|"]
    for i, q in enumerate(sorted(dados[0]["gabarito"])):
        gab_cols = " | ".join(d["gabarito"].get(sorted(d["gabarito"])[i], "?")
                              for d in dados)
        linhas.append(f"| {i + 1} | {gab_cols} | {VAZIO} | "
                      + " | ".join([VAZIO] * len(niveis)) + " |")

    div = "_Só um nível aprofundado nesta matéria — nada a comparar._"
    if len(niveis) > 1:
        r = medir(m.dir)
        if r["assuntos_comparados"]:
            piores = "\n".join(
                f"| {l['assunto'][:44]} | {l['conceitos']} | {l['perdidos']} | {l['perda']:.0%} |"
                for l in r["por_assunto"][:5])
            div = (f"Conceitos que o `padrao` declara cobrir e **não aparecem** no "
                   f"`detalhado` — média **{r['perda_media']:.0%}** "
                   f"({r['perdidos']} de {r['conceitos']}):\n\n"
                   f"| Assunto | conceitos | ausentes | perda |\n|---|---:|---:|---:|\n"
                   f"{piores}\n")

    fontes = "\n".join(
        f"- Prova **{d['versao']}** (caderno {d['caderno']}): `{d['prova'].name}` — "
        f"gabarito: " + " ".join(f"{q}-{r}" for q, r in sorted(d["gabarito"].items()))
        for d in dados)

    ctx = {
        "DATA": date.today().isoformat(),
        "MATERIA_NOME": dados[0]["faixa"].nome,
        "MATERIA_ID": m.materia_id,
        "CONCURSO": concurso_dir.name,
        "BANCA": banca,
        "PROVAS_AFERIDAS": ", ".join(
            f"Prova {d['versao']} (caderno {d['caderno']})" for d in dados),
        "GABARITO_FONTE": "gabaritos oficiais da banca",
        "N_QUESTOES": n_q,
        "N_PROVAS": len(dados),
        "RESSALVA_TAUTOLOGIA": ressalva_tautologia(concurso_dir),
        "TABELA_RESULTADO": tabela,
        "NOTAS_POR_PROVA": ("### Nota de cada prova, isoladamente\n\n"
                            "| Prova | " + " | ".join(f"`{n}`" for n in niveis) + " |\n"
                            "|:-:|" + "|".join(["---:"] * len(niveis)) + "|\n"
                            + "\n".join(f"| **{d['versao']}** | "
                                        + " | ".join([VAZIO] * len(niveis)) + " |"
                                        for d in dados)) if len(dados) > 1 else "",
        "TABELA_QUESTOES": "\n".join(linhas),
        "TABELA_DISTRIBUICAO": VAZIO,
        "DIVERGENCIA_NIVEIS": div,
        "ACOES": VAZIO,
        "FONTES": fontes,
        "TAREFAS_EXTRA": VAZIO,
    }
    txt = TPL.read_text(encoding="utf-8")
    for k, v in ctx.items():
        txt = txt.replace("{" + k + "}", str(v))
    return txt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--prova", type=Path, action="append", required=True)
    ap.add_argument("--gabarito", type=Path, action="append")
    ap.add_argument("--materia", action="append",
                    help="repetível. Sem isto e sem --cargo, lista as aferíveis e sai")
    ap.add_argument("--cargo", help="todas as matérias aprofundadas do cargo (+ _COMUM)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--bloco-out", type=Path,
                    help="grava o texto das questões, para o agente ler")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    gabs = a.gabarito or []
    if not gabs:
        for p in a.prova:
            irmao = p.with_name(p.stem + "-gabarito.pdf")
            if not irmao.exists():
                raise SystemExit(f"ERRO: gabarito de {p.name} não informado e "
                                 f"{irmao.name} não existe ao lado")
            gabs.append(irmao)
    if len(gabs) != len(a.prova):
        raise SystemExit("ERRO: informe um gabarito por prova, na mesma ordem")

    if a.materia and a.cargo:
        raise SystemExit("ERRO: --materia e --cargo são mutuamente exclusivos. "
                         "Use --cargo para todas, ou --materia (repetível) para escolher.")

    escopos = escopos_do_cargo(a.concurso_dir, a.cargo) if a.cargo else None
    casados = [c for c in casar(a.prova[0], a.concurso_dir, escopos) if c.materia]

    if not a.materia and not a.cargo:
        # Nunca assumir "todas" por omissão: aferir a matéria errada gasta o trabalho
        # do agente e produz documento que parece válido.
        print("Matérias aferíveis nesta prova (escolha com --materia, ou --cargo para todas):")
        for c in casados:
            print(f"  {c.faixa.nome:<38} Q{c.faixa.primeira}–{c.faixa.ultima:<4} "
                  f"{c.materia.escopo}/{c.materia.materia_id} "
                  f"({c.materia.n_assuntos} assuntos · {', '.join(c.materia.niveis)})")
        if not casados:
            print("  (nenhuma — o vault não tem aprofundamento das matérias desta prova)")
        return 0

    alvos = a.materia or [c.faixa.nome for c in casados]
    if a.cargo and not alvos:
        raise SystemExit(f"ERRO: nenhuma matéria aprofundada para o cargo {a.cargo}")

    banca = "—"
    meta = a.concurso_dir / ".meta.json"
    if meta.exists():
        try:
            banca = json.loads(meta.read_text(encoding="utf-8")).get("banca", "—")
        except json.JSONDecodeError:
            pass

    resumo = []
    for alvo in alvos:
        dados = [coletar(p, g, a.concurso_dir, alvo, escopos)
                 for p, g in zip(a.prova, gabs)]
        for d in dados:
            for av in d["avisos"]:
                sys.stderr.write(f"AVISO ({d['prova'].name} · {alvo}): {av}\n")

        doc = montar(dados, a.concurso_dir, banca)
        m = dados[0]["materia"]
        destino = (a.out if a.out and len(alvos) == 1
                   else m.dir / f"00-AFERICAO-{m.materia_id.upper()}.md")

        if not a.dry_run:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(doc, encoding="utf-8")
            if a.bloco_out:
                saida = (a.bloco_out if len(alvos) == 1
                         else a.bloco_out.with_name(
                             f"{a.bloco_out.stem}-{m.materia_id}{a.bloco_out.suffix}"))
                saida.write_text("\n\n".join(
                    f"=========== PROVA {d['versao']} (caderno {d['caderno']}) — gabarito: "
                    + " ".join(f"{q}-{r}" for q, r in sorted(d["gabarito"].items()))
                    + " ===========\n" + d["bloco"] for d in dados), encoding="utf-8")

        resumo.append({
            "materia": m.materia_id, "escopo": m.escopo,
            "provas": [d["versao"] for d in dados],
            "questoes": sum(len(d["gabarito"]) for d in dados),
            "niveis": m.niveis, "assuntos": m.n_assuntos,
            "compara_niveis": len(m.niveis) > 1,
            "destino": str(destino), "a_preencher": doc.count(VAZIO),
        })

    print(json.dumps({"dry_run": a.dry_run, "materias": len(resumo),
                      "aferições": resumo}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
