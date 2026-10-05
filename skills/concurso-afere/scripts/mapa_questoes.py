#!/usr/bin/env python3
"""mapa_questoes.py — o vínculo questão → matéria do vault, quando a prova não o imprime.

Na CESGRANRIO a capa diz "Língua Portuguesa … 1 a 10", e a matéria de cada questão é
fato publicado. Na Quadrix a prova se divide por ÁREA: "Conhecimentos Gerais, 1 a 20"
mistura Português, legislação do DF e primeiros socorros sem dizer qual é qual. Atribuir
cada questão a uma matéria do vault é JULGAMENTO — e julgamento é do agente, nunca do
script (a regra central da skill).

Por isso a aferição Quadrix tem duas etapas, com este arquivo no meio:

1. `build_afericao.py --area` grava o ESQUELETO: uma entrada por questão da área, com o
   gabarito oficial já preenchido e a matéria em `···`.
2. O agente lê o bloco da área e preenche cada `materia` com uma das `candidatas`
   (`ESCOPO/materia_id`) ou com `fora-do-vault` — questão de matéria que o vault não
   aprofundou em lugar nenhum.
3. `build_afericao.py --mapa` valida o preenchido e gera uma aferição POR MATÉRIA, cada
   uma com só as suas questões, no diretório da própria matéria.

A validação é estrita porque o modo de falha é silencioso: questão esquecida some da
amostra sem erro nenhum, e a nota sai melhor do que é.
"""
from __future__ import annotations

import json
from pathlib import Path

FORMATO = "concurso-afere/mapa-questoes@1"
VAZIO = "···"
FORA = "fora-do-vault"
ANULADA = "⊘"

COMO_PREENCHER = (
    "Para cada questão, troque o '···' de 'materia' por UMA das 'candidatas' "
    "(ESCOPO/materia_id) ou por 'fora-do-vault' quando a matéria da questão não tem "
    "aprofundamento em lugar nenhum do vault. Não altere 'gabarito': ele é conferido "
    "contra o PDF na etapa seguinte. Questão anulada também recebe matéria — ela entra "
    "no documento da matéria marcada com ⊘, fora do denominador.")


def esqueleto(*, concurso_dir: Path, prova: Path, gabarito: Path, cargo: str,
              tipo: str | None, fonte: str | None, area: str, primeira: int,
              ultima: int, respostas: dict[int, str], anuladas: set[int],
              candidatas: list[str]) -> dict:
    questoes = {}
    for q in range(primeira, ultima + 1):
        if q in anuladas:
            questoes[str(q)] = {"gabarito": ANULADA, "anulada": True, "materia": VAZIO}
        else:
            questoes[str(q)] = {"gabarito": respostas[q], "materia": VAZIO}
    return {
        "formato": FORMATO,
        "concurso_dir": str(concurso_dir),
        "prova": str(prova),
        "gabarito": str(gabarito),
        "banca": "quadrix",
        "cargo_prova": cargo,
        "tipo": tipo,
        "gabarito_fonte": fonte,
        "area": area,
        "faixa": [primeira, ultima],
        "candidatas": candidatas,
        "como_preencher": COMO_PREENCHER,
        "questoes": questoes,
    }


def ler(caminho: Path) -> dict:
    try:
        mapa = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"ERRO: {caminho.name} não é JSON válido: {e}")
    if mapa.get("formato") != FORMATO:
        raise SystemExit(f"ERRO: {caminho.name} não é um mapa de questões "
                         f"(formato '{mapa.get('formato')}', esperado '{FORMATO}')")
    return mapa


def validar(mapa: dict, existentes: set[str],
            respostas: dict[int, str] | None = None,
            anuladas: set[int] | None = None) -> list[str]:
    """Problemas do mapa preenchido. Lista vazia = pode gerar os documentos.

    `existentes` são as matérias que o vault tem HOJE (`ESCOPO/materia_id`) — a lista
    de candidatas foi tirada quando o esqueleto nasceu, e o vault pode ter mudado.
    `respostas`/`anuladas`, quando dados, são o gabarito relido do PDF: o mapa é editado
    à mão e não pode ser a fonte do gabarito.
    """
    erros: list[str] = []
    a, b = mapa["faixa"]
    faixa = {str(q) for q in range(a, b + 1)}
    tem = set(mapa["questoes"])
    if faixa - tem:
        erros.append(f"faltam as questões {sorted(map(int, faixa - tem))} — questão "
                     f"esquecida sumiria da amostra sem erro nenhum")
    if tem - faixa:
        erros.append(f"questões fora da faixa {a}–{b}: {sorted(map(int, tem - faixa))}")

    candidatas = set(mapa.get("candidatas") or [])
    for q, item in sorted(mapa["questoes"].items(), key=lambda kv: int(kv[0])):
        mat = (item.get("materia") or "").strip()
        if not mat or mat == VAZIO:
            erros.append(f"questão {q}: matéria por preencher ({VAZIO})")
        elif mat != FORA and mat not in candidatas:
            erros.append(f"questão {q}: '{mat}' não está entre as candidatas")
        elif mat != FORA and mat not in existentes:
            erros.append(f"questão {q}: a matéria '{mat}' não existe mais no vault")

        if respostas is None:
            continue
        n = int(q)
        oficial = ANULADA if n in (anuladas or set()) else respostas.get(n)
        if item.get("gabarito") != oficial:
            erros.append(f"questão {q}: gabarito do mapa ({item.get('gabarito')}) difere "
                         f"do PDF ({oficial}) — o mapa não é fonte do gabarito")
    return erros


def agrupar(mapa: dict) -> tuple[dict[str, list[int]], list[int]]:
    """({matéria: [questões]}, [questões fora do vault]), em ordem de questão."""
    grupos: dict[str, list[int]] = {}
    fora: list[int] = []
    for q, item in sorted(mapa["questoes"].items(), key=lambda kv: int(kv[0])):
        mat = item["materia"].strip()
        if mat == FORA:
            fora.append(int(q))
        else:
            grupos.setdefault(mat, []).append(int(q))
    return grupos, fora
