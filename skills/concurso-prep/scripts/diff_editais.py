#!/usr/bin/env python3
"""
diff_editais.py - Compara o conteudo programatico de duas versoes (previsto vs oficial).

Le os campos `materias[].topicos` de dois arquivos .meta.yml (ou JSON) e classifica
cada topico em: mantido, removido, novo ou alterado.

Uso:
    python diff_editais.py --v1 <meta-v1.yml-ou-json> --v2 <meta-v2.yml-ou-json> [--json]

Saida: relatorio legivel (ou JSON com --json) das mudancas.

Heuristica de matching:
- Normaliza texto (lowercase, sem acento, sem pontuacao, espacos colapsados)
- IDENTICO: normalizacao igual -> mantido
- SIMILAR (>= LIMIAR de similaridade): -> alterado (mesmo tema, redacao mudou)
- SEM PAR no outro lado: novo (so na v2) ou removido (so na v1)
"""
import argparse
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

LIMIAR_SIMILAR = 0.72


def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in nfkd if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def carregar_topicos(path: Path) -> dict[str, list[str]]:
    """Retorna {materia: [topicos]}. Prefere .meta.json; YAML como fallback legado."""
    # Aceita a PASTA do concurso ou o arquivo de metadata direto: passar a pasta
    # e o natural para quem usa (é o que a skill tem em mãos) e antes estourava
    # IsADirectoryError.
    if path.is_dir():
        for cand in (".meta.json", ".meta.yml"):
            if (path / cand).exists():
                path = path / cand
                break
        else:
            sys.exit(f"ERRO: nem .meta.json nem .meta.yml em {path}")
    raw = path.read_text(encoding="utf-8")
    data = None
    # Tentar JSON primeiro (formato preferido desde v1.2)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: tentar PyYAML se disponivel (arquivos .meta.yml legados)
        try:
            import yaml
        except ImportError:
            sys.stderr.write(
                "AVISO: arquivo nao e JSON e PyYAML nao esta instalado. "
                "Prefira .meta.json ou instale: pip install pyyaml\n"
            )
            sys.exit(3)
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as e:  # item 10: YAML malformado nao pode subir cru
            sys.stderr.write(f"ERRO: YAML malformado em {path}: {e}\n")
            sys.exit(3)
    if not isinstance(data, dict):
        sys.stderr.write(f"ERRO: conteudo de {path} nao e um objeto/dict.\n")
        sys.exit(3)
    materias = {}
    for m in data.get("materias", []):
        nome = m.get("nome", "SEM_NOME")
        materias[nome] = m.get("topicos", [])
    return materias


CARGO_UNICO = "(cargo único)"


def carregar_por_cargo(path: Path) -> dict[str, dict[str, list[str]]]:
    """Retorna {cargo: {materia: [topicos]}} — a visão que a reconciliação exige.

    O item 8 diz que a reconciliação roda POR CARGO, e não rodava: `carregar_topicos`
    lê só `materias[]`, e `materias_por_cargo` não era conhecido em lugar nenhum deste
    script. Num concurso de 3 cargos como o SEDES, remover tópicos da matéria específica
    de 2 deles resultava em **0 removidos** — a mudança passava em silêncio.

    Três formatos convivem no vault e todos precisam ser lidos:
      - `materias[].cargos_ids`  -> schema novo, sem ambiguidade
      - `materias_por_cargo`     -> formato do SEDES; é a visão completa por cargo
      - `materias[]` sem nada    -> cargo único (ou meta incompleto, que o
                                    validate_output acusa como mapa órfão)
    """
    data = carregar_meta_completo(path)
    materias = [m for m in (data.get("materias") or []) if isinstance(m, dict)]
    por_cargo: dict[str, dict[str, list[str]]] = {}

    def por(cargo, m):
        por_cargo.setdefault(cargo, {})[m.get("nome", "SEM_NOME")] = m.get("topicos") or []

    com_ids = [m for m in materias if m.get("cargos_ids")]
    for m in com_ids:
        for c in m["cargos_ids"]:
            por(c, m)

    legado = data.get("materias_por_cargo") or {}
    for cargo, lista in legado.items():
        for m in lista or []:
            if isinstance(m, dict):
                por(cargo, m)

    # Matéria de `materias[]` que não apareceu em nenhum cargo não pode sumir do
    # diff só porque o formato antigo não dizia de quem ela é.
    if legado:
        ja_vistas = {n for mats in por_cargo.values() for n in mats}
        for m in materias:
            if m.get("cargos_ids") or m.get("nome", "SEM_NOME") in ja_vistas:
                continue
            for cargo in por_cargo:
                por(cargo, m)
    elif not com_ids:
        for m in materias:
            por(CARGO_UNICO, m)

    return por_cargo or {CARGO_UNICO: {}}


def similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def contencao_tokens(a: str, b: str) -> float:
    """Fracao de tokens do menor conjunto contidos no maior.
    Captura casos de 'tema expandido' (ex: 'SWOT e BSC' dentro de
    'SWOT, BSC e mapa estrategico'), onde o SequenceMatcher pontua baixo
    por causa do tamanho, mas o tema e o mesmo."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    menor = ta if len(ta) <= len(tb) else tb
    inter = ta & tb
    return len(inter) / len(menor)


def sao_o_mesmo_tema(a: str, b: str, limiar: float) -> tuple[bool, float]:
    """Combina similaridade de sequencia com contencao de tokens.
    Retorna (eh_alterado, score_reportado)."""
    s = similaridade(a, b)
    if s >= limiar:
        return True, s
    # sinal secundario: forte contencao + alguma similaridade textual
    c = contencao_tokens(a, b)
    if c >= 0.80 and s >= 0.45:
        return True, round(max(s, c), 2)
    return False, s


def carregar_meta_completo(path: Path) -> dict:
    """Carrega o meta inteiro (nao so materias) para o diff estrutural."""
    # Aceita a PASTA do concurso ou o arquivo de metadata direto: passar a pasta
    # e o natural para quem usa (é o que a skill tem em mãos) e antes estourava
    # IsADirectoryError.
    if path.is_dir():
        for cand in (".meta.json", ".meta.yml"):
            if (path / cand).exists():
                path = path / cand
                break
        else:
            sys.exit(f"ERRO: nem .meta.json nem .meta.yml em {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml
            return yaml.safe_load(raw) or {}
        except Exception:
            return {}


def _get(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    return d if d != {} else default


def _primeiro(meta: dict, caminhos: list[tuple]):
    """Primeiro caminho que existir. Os campos de vagas/salario nao moram sempre
    no mesmo lugar: o schema novo os poe na raiz, e o `.meta.json` do SEDES os tem
    em `cargo.vagas_imediatas` / `cargo.remuneracao`. Olhando so a raiz, o diff
    estrutural ficava CEGO justamente para vagas e salario — que sao, junto com as
    datas, o que retificacao costuma mexer (B.4). Verificado: mudar
    `cargo.vagas_imediatas` de 133 para 150 no SEDES nao produzia mudanca nenhuma.
    """
    for c in caminhos:
        v = _get(meta, *c)
        if v is not None:
            return v
    return None


def _por_cargo_estrutural(meta: dict) -> dict[str, dict]:
    """{sigla: {vagas/salario}} a partir de `cargos_validados` ou `cargos_multi`."""
    out = {}
    for lista in (meta.get("cargos_validados"), meta.get("cargos_multi")):
        for c in lista or []:
            if not isinstance(c, dict):
                continue
            sigla = c.get("sigla") or c.get("slug")
            if not sigla:
                continue
            out.setdefault(sigla, {
                "Vagas (AC imediatas)": c.get("vagas_ac") or c.get("vagas_imediatas"),
                "Vagas totais": c.get("vagas_total"),
                "Salário": c.get("salario") or c.get("remuneracao"),
            })
    return out


def diff_estrutural(m1: dict, m2: dict) -> list[dict]:
    """Item 16: compara campos estruturais da prova entre as duas versoes."""
    campos = [
        ("Total de questões", ["estrutura_prova", "objetiva", "total_questoes"]),
        ("Data da prova", ["datas_chave", "prova_data"]),
    ]
    alias = {
        "Vagas (AC imediatas)": [("vagas_ac",), ("cargo", "vagas_ac"),
                                 ("cargo", "vagas_imediatas")],
        "Vagas totais": [("vagas_total",), ("cargo", "vagas_total")],
        "Salário": [("salario",), ("cargo", "salario"), ("cargo", "remuneracao")],
    }

    mudancas = []
    for nome, caminho in campos:
        v1, v2 = _get(m1, *caminho), _get(m2, *caminho)
        if (v1 is not None or v2 is not None) and v1 != v2:
            mudancas.append({"campo": nome, "de": v1, "para": v2})

    d1, d2 = bool(_get(m1, "estrutura_prova", "discursiva")), \
        bool(_get(m2, "estrutura_prova", "discursiva"))
    if d1 != d2:
        mudancas.append({"campo": "Tem discursiva?", "de": d1, "para": d2})

    for nome, caminhos in alias.items():
        v1, v2 = _primeiro(m1, caminhos), _primeiro(m2, caminhos)
        if (v1 is not None or v2 is not None) and v1 != v2:
            mudancas.append({"campo": nome, "de": v1, "para": v2})

    # Multi-cargo: vagas e salario sao POR CARGO, e uma retificacao pode mexer em
    # um cargo so — o campo agregado nao mostra isso.
    pc1, pc2 = _por_cargo_estrutural(m1), _por_cargo_estrutural(m2)
    for sigla in sorted(set(pc1) | set(pc2)):
        for campo in ("Vagas (AC imediatas)", "Vagas totais", "Salário"):
            v1, v2 = pc1.get(sigla, {}).get(campo), pc2.get(sigla, {}).get(campo)
            if (v1 is not None or v2 is not None) and v1 != v2:
                mudancas.append({"campo": f"{campo} [{sigla}]", "de": v1, "para": v2})
    return mudancas


def diff(v1: dict[str, list[str]], v2: dict[str, list[str]]) -> dict:
    # Achatar em (materia, topico, normalizado)
    def achatar(d):
        out = []
        for materia, topicos in d.items():
            for t in topicos:
                out.append({"materia": materia, "topico": t, "norm": normalizar(t)})
        return out

    flat1 = achatar(v1)
    flat2 = achatar(v2)
    norm1 = {x["norm"] for x in flat1}
    norm2 = {x["norm"] for x in flat2}

    mantidos, removidos, novos, alterados = [], [], [], []
    usados_v2 = set()

    # Mantidos: norm identico nos dois
    for x in flat1:
        if x["norm"] in norm2:
            mantidos.append(x)
            usados_v2.add(x["norm"])

    # Para os que nao casaram exato, tentar similaridade
    restantes_v1 = [x for x in flat1 if x["norm"] not in norm2]
    restantes_v2 = [x for x in flat2 if x["norm"] not in norm1]

    for x in restantes_v1:
        melhor, melhor_score, melhor_eh = None, 0.0, False
        for y in restantes_v2:
            if y["norm"] in usados_v2:
                continue
            eh, score = sao_o_mesmo_tema(x["norm"], y["norm"], LIMIAR_SIMILAR)
            if eh and score > melhor_score:
                melhor, melhor_score, melhor_eh = y, score, True
        if melhor and melhor_eh:
            alterados.append({"de": x, "para": melhor, "score": round(melhor_score, 2)})
            usados_v2.add(melhor["norm"])
        else:
            removidos.append(x)

    for y in restantes_v2:
        if y["norm"] not in usados_v2:
            novos.append(y)

    return {
        "mantidos": mantidos,
        "removidos": removidos,
        "novos": novos,
        "alterados": alterados,
        "resumo": {
            "n_mantidos": len(mantidos),
            "n_removidos": len(removidos),
            "n_novos": len(novos),
            "n_alterados": len(alterados),
        },
    }


def diff_por_cargo(pc1: dict, pc2: dict, cargo_filtro: str | None = None) -> dict:
    """Roda o diff uma vez por cargo (item 8) e consolida.

    Cargo que existe num lado e não no outro é reportado — retificação que cria ou
    extingue cargo é justamente o tipo de mudança que não pode passar batida.
    """
    cargos = sorted(set(pc1) | set(pc2))
    if cargo_filtro:
        cargos = [c for c in cargos if c == cargo_filtro]
    por_cargo, totais = {}, {"n_mantidos": 0, "n_removidos": 0, "n_novos": 0,
                             "n_alterados": 0}
    for c in cargos:
        r = diff(pc1.get(c, {}), pc2.get(c, {}))
        r["so_na_v1"] = c not in pc2
        r["so_na_v2"] = c not in pc1
        por_cargo[c] = r
        for k in totais:
            totais[k] += r["resumo"][k]
    return {
        "por_cargo": por_cargo,
        "cargos_removidos": sorted(set(pc1) - set(pc2)),
        "cargos_novos": sorted(set(pc2) - set(pc1)),
        "resumo": totais,
    }


def titulo_do_caso(meta1: dict, meta2: dict) -> str:
    """CASO A (previsto -> oficial) ou CASO B (oficial -> retificado).

    O cabeçalho era fixo em "Previsto (V1) vs Oficial (V2)", inclusive numa
    retificação — o B.5 manda ajustar e ninguém ajustava.
    """
    if str(meta1.get("modo", "")).lower() == "previsto":
        return "Reconciliacao: Previsto (V1) vs Oficial (V2)"
    return "Reconciliacao: Oficial vigente vs Retificado"


def main():
    parser = argparse.ArgumentParser(description="Diff de conteudo programatico V1 vs V2")
    parser.add_argument("--v1", type=Path, required=True, help="meta da versao prevista")
    parser.add_argument("--v2", type=Path, required=True, help="meta da versao oficial")
    parser.add_argument("--cargo", default=None,
                        help="restringe o diff a um cargo (default: todos)")
    parser.add_argument("--json", action="store_true", help="Saida em JSON")
    args = parser.parse_args()

    resultado = diff_por_cargo(carregar_por_cargo(args.v1),
                               carregar_por_cargo(args.v2), args.cargo)
    # item 16: diff estrutural
    meta1 = carregar_meta_completo(args.v1)
    meta2 = carregar_meta_completo(args.v2)
    resultado["estrutural"] = diff_estrutural(meta1, meta2)

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return

    r = resultado["resumo"]
    print(f"=== {titulo_do_caso(meta1, meta2)} ===\n")
    print(f"🟢 Mantidos:  {r['n_mantidos']}")
    print(f"🔴 Removidos: {r['n_removidos']}")
    print(f"🆕 Novos:     {r['n_novos']}")
    print(f"🔀 Alterados: {r['n_alterados']}\n")

    if resultado["estrutural"]:
        print("--- 🏗️  MUDANCAS ESTRUTURAIS ---")
        for e in resultado["estrutural"]:
            print(f"  {e['campo']}: {e['de']} -> {e['para']}")
        print()
    for c in resultado["cargos_removidos"]:
        print(f"⚠️  CARGO REMOVIDO na nova versao: {c}")
    for c in resultado["cargos_novos"]:
        print(f"⚠️  CARGO NOVO na nova versao: {c}")
    if resultado["cargos_removidos"] or resultado["cargos_novos"]:
        print()

    for cargo, res in resultado["por_cargo"].items():
        rc = res["resumo"]
        if not (rc["n_removidos"] or rc["n_novos"] or rc["n_alterados"]):
            print(f"### {cargo}: sem mudancas ({rc['n_mantidos']} topicos mantidos)\n")
            continue
        print(f"### {cargo}  "
              f"🟢{rc['n_mantidos']} 🔴{rc['n_removidos']} "
              f"🆕{rc['n_novos']} 🔀{rc['n_alterados']}")
        if res["removidos"]:
            print("--- 🔴 REMOVIDOS (parar de estudar) ---")
            for x in res["removidos"]:
                print(f"  [{x['materia']}] {x['topico']}")
        if res["novos"]:
            print("--- 🆕 NOVOS (comecar a estudar) ---")
            for x in res["novos"]:
                print(f"  [{x['materia']}] {x['topico']}")
        if res["alterados"]:
            print("--- 🔀 ALTERADOS (revisar) ---")
            for x in res["alterados"]:
                print(f"  [{x['de']['materia']}] '{x['de']['topico']}'")
                print(f"     -> '{x['para']['topico']}' (similaridade {x['score']})")
        print()


if __name__ == "__main__":
    main()
