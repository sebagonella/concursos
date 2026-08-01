#!/usr/bin/env python3
"""
validate_parsed.py — valida a saída da Etapa 2 contra `assets/schema-edital.json`. (v1.0.0)

Roda ENTRE a Etapa 2 e a Etapa 3. Saída fora do contrato **para o fluxo**: era a
ausência deste passo que deixava cada execução inventar o seu próprio formato, e
daí saírem `.meta.json` diferentes entre si e do documentado — inclusive um que
perdeu o conteúdo programático de um cargo inteiro.

## Por que um checador próprio em vez de `jsonschema`

O repo é stdlib e as dependências são opcionais. Mas checador parcial silencioso
é a doença que estamos consertando (o `check_soma_questoes` "passava" no SEDES
porque não casava nada). Então aqui o contrato é o inverso:

    toda palavra-chave usada no schema TEM de estar implementada;
    se aparecer uma que o checador não conhece, ele FALHA ALTO.

Assim o checador nunca valida menos do que o schema promete. Há teste que varre
o schema inteiro cobrando essa propriedade.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_PADRAO = Path(__file__).resolve().parent.parent / "assets" / "schema-edital.json"

# Palavras-chave que RESTRINGEM o dado — todas implementadas em `_validar`.
IMPLEMENTADAS = {
    "type", "required", "properties", "items", "enum", "pattern", "minItems",
}
# Palavras-chave de anotação: não restringem nada, ignorar é correto.
ANOTACOES = {"$schema", "$id", "title", "description", "$comment", "examples", "default"}

TIPOS = {
    "object": dict, "array": list, "string": str, "integer": int,
    "number": (int, float), "boolean": bool, "null": type(None),
}


def keywords_do_schema(schema, achadas=None) -> set:
    """Toda palavra-chave usada em qualquer profundidade do schema."""
    achadas = achadas if achadas is not None else set()
    if isinstance(schema, dict):
        for k, v in schema.items():
            if k in ("properties",):
                for sub in (v or {}).values():
                    keywords_do_schema(sub, achadas)
                achadas.add(k)
            elif k in ("items",):
                keywords_do_schema(v, achadas)
                achadas.add(k)
            else:
                achadas.add(k)
                if isinstance(v, dict):
                    keywords_do_schema(v, achadas)
    return achadas


def conferir_cobertura(schema) -> list[str]:
    """O checador cobre tudo o que o schema usa? Se não, é erro de programa."""
    usadas = keywords_do_schema(schema)
    desconhecidas = usadas - IMPLEMENTADAS - ANOTACOES
    if desconhecidas:
        return [f"ERRO DE PROGRAMA: o schema usa {sorted(desconhecidas)}, que "
                f"validate_parsed.py não implementa. Implemente ou remova — "
                f"validar menos do que o schema promete é o defeito que este "
                f"script existe para não repetir."]
    return []


def _tipo_ok(valor, tipos) -> bool:
    if isinstance(tipos, str):
        tipos = [tipos]
    for t in tipos:
        esperado = TIPOS.get(t)
        if esperado is None:
            continue
        # bool é subclasse de int em Python; "integer" não pode aceitar True.
        if t in ("integer", "number") and isinstance(valor, bool):
            continue
        if isinstance(valor, esperado):
            return True
    return False


def _validar(dado, schema, caminho: str, erros: list):
    if "type" in schema and not _tipo_ok(dado, schema["type"]):
        erros.append(f"{caminho}: esperado {schema['type']}, veio "
                     f"{type(dado).__name__}")
        return

    if "enum" in schema and dado not in schema["enum"]:
        erros.append(f"{caminho}: {dado!r} fora de {schema['enum']}")

    if "pattern" in schema and isinstance(dado, str):
        if not re.search(schema["pattern"], dado):
            erros.append(f"{caminho}: {dado!r} não casa com "
                         f"/{schema['pattern']}/")

    if isinstance(dado, dict):
        for obrigatorio in schema.get("required", []):
            if obrigatorio not in dado:
                erros.append(f"{caminho}: falta o campo obrigatório "
                             f"{obrigatorio!r}")
        for chave, sub in (schema.get("properties") or {}).items():
            if chave in dado:
                _validar(dado[chave], sub, f"{caminho}.{chave}", erros)

    if isinstance(dado, list):
        if "minItems" in schema and len(dado) < schema["minItems"]:
            erros.append(f"{caminho}: {len(dado)} item(ns), mínimo "
                         f"{schema['minItems']}")
        if "items" in schema:
            for i, item in enumerate(dado):
                _validar(item, schema["items"], f"{caminho}[{i}]", erros)


def checagens_de_coerencia(dado: dict) -> list[str]:
    """O que o JSON Schema não expressa, mas quebra o fluxo adiante."""
    erros = []
    siglas = {c.get("sigla") for c in dado.get("cargos_validados") or []
              if isinstance(c, dict)}

    for i, m in enumerate(dado.get("materias") or []):
        if not isinstance(m, dict):
            continue
        onde = f"materias[{i}] ({m.get('materia_id') or m.get('nome')!r})"
        # Cargo citado por matéria tem de existir em cargos_validados: é o que
        # impede a matéria órfã que o BB produziu — mapa gerado para um cargo
        # que o meta não conhece.
        desconhecidos = [c for c in (m.get("cargos_ids") or []) if c not in siglas]
        if desconhecidos:
            erros.append(f"{onde}: cargos_ids {desconhecidos} não estão em "
                         f"cargos_validados[].sigla")

    # Todo cargo validado precisa ser coberto por ao menos uma matéria; senão o
    # cargo entra no concurso sem conteúdo programático — foi exatamente o que
    # aconteceu com o AGENTE-COMERCIAL do BB.
    cobertos = {c for m in dado.get("materias") or []
                if isinstance(m, dict) for c in (m.get("cargos_ids") or [])}
    for s in sorted(siglas - cobertos):
        erros.append(f"cargo {s!r} não tem NENHUMA matéria — o conteúdo "
                     f"programático dele não seria gravado no .meta.json")

    ids = [m.get("materia_id") for m in dado.get("materias") or []
           if isinstance(m, dict)]
    repetidos = sorted({i for i in ids if i and ids.count(i) > 1})
    if repetidos:
        erros.append(f"materia_id repetido: {repetidos} — o id é o vínculo com "
                     f"o aprofundamento e tem de ser único")

    if (dado.get("datas_chave") or {}) and str(dado.get("modo", "oficial")) != "previsto":
        if not (dado.get("datas_chave") or {}).get("prova_data"):
            erros.append("modo oficial sem datas_chave.prova_data — o "
                         "cronograma da Etapa 4 não tem âncora")
    return erros


def main():
    ap = argparse.ArgumentParser(
        description="Valida a saída da Etapa 2 contra o schema do contrato")
    ap.add_argument("parsed", type=Path)
    ap.add_argument("--schema", type=Path, default=SCHEMA_PADRAO)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    schema = json.loads(args.schema.read_text(encoding="utf-8"))

    erros = conferir_cobertura(schema)
    if erros:
        for e in erros:
            print(e, file=sys.stderr)
        sys.exit(3)

    try:
        dado = json.loads(args.parsed.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERRO: {args.parsed} não é JSON válido: {e}", file=sys.stderr)
        sys.exit(1)

    _validar(dado, schema, "$", erros)
    erros += checagens_de_coerencia(dado)

    if args.json:
        print(json.dumps({"ok": not erros, "erros": erros}, indent=2,
                         ensure_ascii=False))
    else:
        if erros:
            print(f"=== {len(erros)} violação(ões) do contrato da Etapa 2 ===\n")
            for e in erros:
                print(f"  - {e}")
            print("\nO fluxo NÃO deve seguir: as etapas seguintes assumem este "
                  "contrato.")
        else:
            print("OK: a saída da Etapa 2 respeita o contrato.")

    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
