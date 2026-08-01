#!/usr/bin/env python3
"""
materia_id.py — FONTE DE VERDADE da identidade de matéria. (v1.0.0)

A regra vive aqui e só aqui. Não reimplemente em outro script: foi a duplicação
da convenção de aprofundamento que já custou caro ao projeto, e a lição está no
`aprofundamento_id.py`.

## O que este módulo defende

O `materia_id` é o vínculo entre o mapa (visão Plano), o aprofundamento (visão
Estudo) e o site. Se ele mudar entre execuções, o vínculo arrebenta: duas
execuções da skill sobre o MESMO edital do SEDES produziram 5-6 matérias em
15/07 e 20 em 01/08, e re-executar hoje deixaria 20 mapas órfãos dos 90 assuntos
já aprofundados.

A decisão registrada (ADR `identidade-da-materia-declarada-e-persistida`) é:

    a estabilidade não vem de uma regra de derivação melhor;
    vem de NÃO RE-DERIVAR.

Por isso a ordem de resolução é sempre:

    1. id DECLARADO no .meta.json  ->  reusa, sempre, sem discussão
    2. título parecido com um declarado  ->  reusa, avisando por qual casou
    3. nada casou  ->  PROPÕE um id e marca `novo`, para confirmação humana

`propor_id()` é proposta, não decisão. Ele erra de propósito em vez de fingir:
nos 5 títulos reais do SEDES a proposta bate com o id declarado em **1** e
diverge em 4 — "Fundamentos, Organização, Gestão e Marcos Operacionais do SUAS"
vira `fundamentos-organizacao-gestao-marcos-operacionais-suas`, e o declarado é
`fundamentos-suas`. É a demonstração de que derivação não substitui declaração,
e há teste que trava isso.
"""
import argparse
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

# Palavras que não distinguem uma matéria de outra.
VAZIAS = {
    "de", "do", "da", "dos", "das", "e", "em", "no", "na", "nos", "nas",
    "para", "a", "o", "as", "os", "ao", "aos", "com", "sobre", "entre", "por",
}

# Preposições que indicam que um conjunto coordenado tem complemento PRÓPRIO.
# É o sinal que separa "Conhecimentos do DF, Política para Mulheres, ..."
# (áreas independentes) de "Fundamentos, Organização, Gestão e Marcos ... do SUAS"
# (aspectos de uma área só, com complemento compartilhado no final).
PREPOSICOES = {"de", "do", "da", "dos", "das", "para", "em", "no", "na", "sobre", "com"}

# Acima disso, dois títulos são considerados a mesma matéria.
LIMIAR_SIMILARIDADE = 0.86


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, sem pontuação, espaços colapsados."""
    t = _sem_acento(texto).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def tokens_significativos(texto: str) -> list[str]:
    return [t for t in normalizar(texto).split() if t and t not in VAZIAS]


def propor_id(nome: str) -> str:
    """PROPOSTA de id — determinística, conservadora e falível por desenho.

    Não tenta adivinhar o "núcleo" do nome e **não corta**: pega todos os tokens
    significativos, na ordem em que aparecem. Id longo e feio é melhor do que id
    truncado — o corte tirava justamente o que distinguia a matéria
    (`nocoes-saude-mental-uso`, cortado antes de "álcool e outras drogas"), e um
    id enganoso é pior do que um id comprido. Quem encurta é o humano, uma vez;
    depois o `.meta.json` manda para sempre.
    """
    return "-".join(tokens_significativos(nome))


def _conjuntos(nome: str) -> list[str]:
    """Fatia o título nos seus conjuntos coordenados (vírgulas e o 'e' final)."""
    partes = [p.strip() for p in re.split(r",", nome) if p.strip()]
    if partes:
        cauda = re.split(r"\s+\be\b\s+", partes[-1])
        partes = partes[:-1] + [c.strip() for c in cauda if c.strip()]
    return partes


def candidato_a_divisao(nome: str) -> tuple[bool, str]:
    """O título junta áreas independentes, ou aspectos de uma área só?

    Sinal: quantos conjuntos coordenados NÃO-FINAIS carregam complemento
    próprio (uma preposição). O último conjunto é ignorado de propósito — é
    onde costuma morar o complemento compartilhado ("... do SUAS").

        "Conhecimentos do Distrito Federal, Política para Mulheres,
         Legislação e Primeiros Socorros"
            -> 'do', 'para'  = 2 complementos próprios  -> CANDIDATO
        "Fundamentos, Organização, Gestão e Marcos Operacionais do SUAS"
            -> 0 complementos próprios                  -> coeso

    Exige VÍRGULA: título coordenado só por "e" ("Noções de Saúde Mental e Uso
    de Álcool e Outras Drogas") é uma área com complemento composto, não uma
    lista de áreas — sem essa exigência a heurística marcava 3 das 20 matérias
    reais, duas delas falso positivo.

    Calibrado nas 20 matérias reais do edital do SEDES 2026, onde marca
    exatamente uma — a mesma que no vault concentra 58 dos 90 assuntos
    aprofundados. É heurística e só PROPÕE: quem divide matéria é o humano.
    """
    if "," not in nome:
        return False, ""
    partes = _conjuntos(nome)
    if len(partes) < 3:
        return False, ""
    proprios = [p for p in partes[:-1]
                if set(normalizar(p).split()) & PREPOSICOES]
    if len(proprios) >= 2:
        return True, ("junta áreas com complemento próprio: "
                      + "; ".join(repr(p) for p in proprios))
    return False, ""


def carregar_declarados(meta: dict) -> dict[str, str]:
    """Ids já declarados no `.meta.json`, de `materias[]` e do formato legado.

    Os dois lugares existem e nenhum é completo sozinho — no SEDES o primeiro
    só traz um cargo e o resto vive em `materias_por_cargo`. Ler um só é o que
    fazia a checagem passar por cima do buraco.

    Retorna {titulo_normalizado: materia_id}.
    """
    declarados: dict[str, str] = {}
    fontes = list(meta.get("materias") or [])
    for lista in (meta.get("materias_por_cargo") or {}).values():
        fontes.extend(lista or [])
    for m in fontes:
        if not isinstance(m, dict):
            continue
        mid = (m.get("materia_id") or "").strip()
        nome = (m.get("nome") or "").strip()
        if mid and nome:
            declarados.setdefault(normalizar(nome), mid)
    return declarados


def resolver(nome: str, declarados: dict[str, str]) -> tuple[str, str, str]:
    """Resolve o id de uma matéria. Retorna (materia_id, origem, detalhe).

    origem:
      `declarado`  — casou exato com um id já declarado. Caminho normal.
      `similar`    — casou por semelhança de título; o detalhe diz com qual.
      `novo`       — nada casou; o id é PROPOSTA e exige confirmação humana.
    """
    chave = normalizar(nome)
    if chave in declarados:
        return declarados[chave], "declarado", ""

    melhor, score = None, 0.0
    for k, mid in declarados.items():
        s = SequenceMatcher(None, chave, k).ratio()
        if s > score:
            melhor, score = (k, mid), s
    if melhor and score >= LIMIAR_SIMILARIDADE:
        return melhor[1], "similar", f"casou com {melhor[0]!r} (score {score:.2f})"

    return propor_id(nome), "novo", "proposta — confirmar antes de gravar"


def analisar(nomes: list[str], meta: dict) -> list[dict]:
    """Resolve uma lista de títulos contra o meta e sinaliza o que precisa de gente."""
    declarados = carregar_declarados(meta)
    saida = []
    for nome in nomes:
        mid, origem, detalhe = resolver(nome, declarados)
        div, motivo = candidato_a_divisao(nome)
        saida.append({
            "nome": nome,
            "materia_id": mid,
            "origem": origem,
            "detalhe": detalhe,
            "candidato_a_divisao": div,
            "motivo_divisao": motivo,
        })
    return saida


def main():
    ap = argparse.ArgumentParser(
        description="Resolve materia_id contra os ids já declarados no .meta.json")
    ap.add_argument("--meta", type=Path,
                    help="caminho do .meta.json (ou da pasta do concurso)")
    ap.add_argument("--nomes", nargs="*", default=[],
                    help="títulos de matéria a resolver")
    ap.add_argument("--parsed", type=Path,
                    help="JSON da Etapa 2; extrai os títulos dele")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    meta = {}
    if args.meta:
        p = args.meta / ".meta.json" if args.meta.is_dir() else args.meta
        if p.exists():
            meta = json.loads(p.read_text(encoding="utf-8"))

    nomes = list(args.nomes)
    if args.parsed and args.parsed.exists():
        d = json.loads(args.parsed.read_text(encoding="utf-8"))
        for m in d.get("materias") or []:
            if isinstance(m, dict) and m.get("nome"):
                nomes.append(m["nome"])

    if not nomes:
        sys.stderr.write("ERRO: nada a resolver (use --nomes ou --parsed)\n")
        sys.exit(1)

    res = analisar(nomes, meta)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        for r in res:
            marca = {"declarado": "=", "similar": "~", "novo": "+"}[r["origem"]]
            print(f"{marca} {r['materia_id']:<40} {r['nome'][:52]}")
            if r["detalhe"]:
                print(f"    {r['detalhe']}")
            if r["candidato_a_divisao"]:
                print(f"    ⚠ candidato a divisão — {r['motivo_divisao']}")
        novos = sum(1 for r in res if r["origem"] == "novo")
        print(f"\n{len(res)} matéria(s): {len(res) - novos} resolvida(s) pelo "
              f".meta.json, {novos} exigindo confirmação.")

    # Id novo é decisão humana pendente, não resultado pronto.
    sys.exit(2 if any(r["origem"] == "novo" for r in res) else 0)


if __name__ == "__main__":
    main()
