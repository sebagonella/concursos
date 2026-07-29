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


def diff_estrutural(m1: dict, m2: dict) -> list[dict]:
    """Item 16: compara campos estruturais da prova entre as duas versoes."""
    def get(d, *ks, default=None):
        for k in ks:
            if not isinstance(d, dict):
                return default
            d = d.get(k, {})
        return d if d != {} else default

    campos = [
        ("Total de questões", get(m1, "estrutura_prova", "objetiva", "total_questoes"),
                              get(m2, "estrutura_prova", "objetiva", "total_questoes")),
        ("Tem discursiva?", bool(get(m1, "estrutura_prova", "discursiva")),
                            bool(get(m2, "estrutura_prova", "discursiva"))),
        ("Vagas (AC imediatas)", get(m1, "vagas_ac"), get(m2, "vagas_ac")),
        ("Vagas totais", get(m1, "vagas_total"), get(m2, "vagas_total")),
        ("Salário", get(m1, "salario"), get(m2, "salario")),
        ("Data da prova", get(m1, "datas_chave", "prova_data"),
                          get(m2, "datas_chave", "prova_data")),
    ]
    mudancas = []
    for nome, v1, v2 in campos:
        if v1 is None and v2 is None:
            continue
        if v1 != v2:
            mudancas.append({"campo": nome, "de": v1, "para": v2})
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


def main():
    parser = argparse.ArgumentParser(description="Diff de conteudo programatico V1 vs V2")
    parser.add_argument("--v1", type=Path, required=True, help="meta da versao prevista")
    parser.add_argument("--v2", type=Path, required=True, help="meta da versao oficial")
    parser.add_argument("--json", action="store_true", help="Saida em JSON")
    args = parser.parse_args()

    v1 = carregar_topicos(args.v1)
    v2 = carregar_topicos(args.v2)
    resultado = diff(v1, v2)
    # item 16: diff estrutural
    meta1 = carregar_meta_completo(args.v1)
    meta2 = carregar_meta_completo(args.v2)
    resultado["estrutural"] = diff_estrutural(meta1, meta2)

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return

    r = resultado["resumo"]
    print("=== Reconciliacao: Previsto (V1) vs Oficial (V2) ===\n")
    print(f"🟢 Mantidos:  {r['n_mantidos']}")
    print(f"🔴 Removidos: {r['n_removidos']}")
    print(f"🆕 Novos:     {r['n_novos']}")
    print(f"🔀 Alterados: {r['n_alterados']}\n")

    if resultado["estrutural"]:
        print("--- 🏗️  MUDANCAS ESTRUTURAIS ---")
        for e in resultado["estrutural"]:
            print(f"  {e['campo']}: {e['de']} -> {e['para']}")
        print()

    if resultado["removidos"]:
        print("--- 🔴 REMOVIDOS (parar de estudar) ---")
        for x in resultado["removidos"]:
            print(f"  [{x['materia']}] {x['topico']}")
        print()
    if resultado["novos"]:
        print("--- 🆕 NOVOS (comecar a estudar) ---")
        for x in resultado["novos"]:
            print(f"  [{x['materia']}] {x['topico']}")
        print()
    if resultado["alterados"]:
        print("--- 🔀 ALTERADOS (revisar) ---")
        for x in resultado["alterados"]:
            print(f"  [{x['de']['materia']}] '{x['de']['topico']}'")
            print(f"     -> '{x['para']['topico']}' (similaridade {x['score']})")
        print()


if __name__ == "__main__":
    main()
