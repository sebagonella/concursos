#!/usr/bin/env python3
"""
migrar_materiais.py - Constrói o catálogo de material dos concursos já gerados.

**Dry-run por padrão.** Sem `--aplicar`, nada é escrito: sai só o relatório.

## O que este script resolve

Nos dois concursos do vault, a obra era descrita em dois lugares que nunca se
falavam. A auditoria de 03/08/2026 mediu:

    473 itens de material nos mapas   contra   62 nos catálogos
    interseção: 15,6% (BB) · 5,9% (SEDES)
    5 dos 7 escopos sem catálogo nenhum
    Pestana com 4 grafias e 3 editoras contraditórias; Abreu com 3
    25 livros sem autor · 31 prefixos distintos

Este script faz a parte **mecânica**: varre o que já existe, deduplica por obra,
atribui a âncora e escreve o catálogo de cada escopo. O que ele NÃO faz é
inventar metadado — autor que não está escrito em lugar nenhum não é adivinhado;
vira pendência nomeada, para a pesquisa (Etapa 5 da skill) preencher depois.

## As duas regras que ele não quebra

**Casamento exato ou nada.** Reescrever o item do mapa para apontar ao catálogo
só acontece quando título e sobrenome batem exatamente. Sem limiar de
similaridade: o repo já decidiu duas vezes que não se infere vínculo por
semelhança (mapa↔assunto casa em ~18% dos tópicos), e um falso positivo aqui
manda o estudante ao livro errado.

**Nada do que o usuário escreveu se perde.** A reescrita preserva o ponteiro de
leitura (`— cap. 4`) e faz backup do mapa antes de tocar nele.

Uso:
    python3 migrar_materiais.py --concurso-dir <...>/SEDES_2026
    python3 migrar_materiais.py --concurso-dir <...> --aplicar
    python3 migrar_materiais.py --concurso-dir <...> --aplicar --sem-reescrever-mapas
"""
import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import material_id as mid  # noqa: E402

# H2 **e** H3: o mapa de Português do SEDES escreve o material num único bloco de
# nível 2 no fim do arquivo (11 itens), e não por tópico. É o único caso divergente
# do vault — ignorá-lo perderia justamente os 11 itens que a auditoria não achou.
_H_MATERIAL = re.compile(r"^(#{2,3})\s+.*material recomendado", re.I)
_QUALQUER_H = re.compile(r"^(#{1,6})\s")


def blocos_de_material(texto: str) -> list[tuple[int, int]]:
    """Faixas de linhas [inicio, fim) de cada bloco de material do arquivo."""
    linhas = texto.splitlines()
    faixas, abertura, nivel = [], None, 0
    for i, linha in enumerate(linhas):
        m = _H_MATERIAL.match(linha)
        if m:
            if abertura is not None:
                faixas.append((abertura, i))
            abertura, nivel = i + 1, len(m.group(1))
            continue
        if abertura is not None:
            h = _QUALQUER_H.match(linha)
            if h and len(h.group(1)) <= nivel:
                faixas.append((abertura, i))
                abertura = None
    if abertura is not None:
        faixas.append((abertura, len(linhas)))
    return faixas


def mapas_do_escopo(escopo_dir: Path) -> list[Path]:
    achados = []
    for pasta in ("03-MAPAS-MATERIAS", "03-MAPAS-COMUNS"):
        d = escopo_dir / pasta
        if d.is_dir():
            achados += [m for m in sorted(d.glob("*.md"))
                        if not m.name.startswith("00-INDICE")]
    return achados


def varrer(concurso_dir: Path) -> tuple[dict, dict]:
    """(itens por escopo, catálogo existente por escopo)."""
    itens: dict[str, list] = defaultdict(list)
    catalogos: dict[str, list] = {}
    for escopo_dir in sorted(p for p in concurso_dir.iterdir() if p.is_dir()):
        escopo = escopo_dir.name
        for mapa in mapas_do_escopo(escopo_dir):
            texto = mapa.read_text(encoding="utf-8")
            linhas = texto.splitlines()
            for ini, fim in blocos_de_material(texto):
                for item in mid.itens_do_bloco("\n".join(linhas[ini:fim])):
                    itens[escopo].append({"mapa": mapa, "item": item})
        cat = escopo_dir / "04-MATERIAIS" / "livros-recomendados.md"
        if cat.exists():
            entradas = mid.parsear_catalogo(cat.read_text(encoding="utf-8"))
            if not entradas:                       # catálogo legado: lista de bullets
                entradas = _entradas_do_catalogo_legado(cat)
            catalogos[escopo] = entradas
    return itens, catalogos


def _entradas_do_catalogo_legado(cat: Path) -> list[dict]:
    """O catálogo antigo é `- Autor — *Título*. Editora.` sob `## Matéria`.

    Ler isso importa: são 62 itens que já foram pesquisados uma vez, e descartá-los
    obrigaria a refazer a pesquisa inteira — pior, faria a migração parecer que o
    vault não tinha bibliografia nenhuma.
    """
    entradas, materia = [], ""
    for linha in cat.read_text(encoding="utf-8").splitlines():
        h = re.match(r"^##\s+(.*)$", linha)
        if h:
            materia = h.group(1).strip()
            continue
        if not re.match(r"^\s*[-*]\s+", linha):
            continue
        item = mid.parsear_item(linha)
        if not item["titulo"]:
            continue
        entradas.append({
            "titulo": item["titulo"], "autor": item["autor"],
            "editora": item["editora"], "isbn": "", "cobre": "",
            "onde_obter": "", "pendencia": "", "ancora": "",
            "materia": materia, "_origem": "catálogo legado",
        })
    return entradas


def consolidar(itens: dict, catalogos: dict) -> tuple[dict, list, list]:
    """Uma entrada por obra, no escopo certo.

    A obra vai para o escopo que a cita. Citada por mapas de mais de um escopo, ou
    por um mapa do `_COMUM`, vai para `_COMUM` — mesma regra de `cargos_ids[]` que
    roteia mapa e catálogo na skill.
    """
    escopos_da_obra: dict[str, set] = defaultdict(set)
    exemplar: dict[str, dict] = {}
    variantes: dict[str, set] = defaultdict(set)

    def registrar(chave, dados, escopo, texto):
        escopos_da_obra[chave].add(escopo)
        variantes[chave].add(texto)
        atual = exemplar.get(chave)
        # fica o exemplar mais completo: quem tem autor vence quem não tem
        pontos = lambda d: bool(d.get("autor")) * 2 + bool(d.get("editora"))
        if atual is None or pontos(dados) > pontos(atual):
            exemplar[chave] = dados

    for escopo, entradas in catalogos.items():
        for e in entradas:
            if not e["titulo"]:
                continue
            chave = mid.chave_obra(e["titulo"], e.get("autor", ""))
            registrar(chave, dict(e), escopo,
                      f'{e["titulo"]} — {e.get("autor", "")} ({e.get("editora", "")})')

    sem_autor, nao_casados = [], []
    for escopo, registros in itens.items():
        for r in registros:
            item = r["item"]
            if item["tipo"] != "livro" or item["ancora"]:
                continue
            if not item["titulo"]:
                continue
            chave = mid.chave_obra(item["titulo"], item["autor"])
            registrar(chave, {"titulo": item["titulo"], "autor": item["autor"],
                              "editora": item["editora"], "isbn": "", "cobre": "",
                              "onde_obter": "", "pendencia": "", "ancora": "",
                              "materia": r["mapa"].stem},
                      escopo, item["texto"])
            if not item["autor"]:
                sem_autor.append({"escopo": escopo, "mapa": r["mapa"].name,
                                  "texto": item["texto"]})

    por_escopo: dict[str, list] = defaultdict(list)
    for chave, escopos in escopos_da_obra.items():
        dados = exemplar[chave]
        destino = "_COMUM" if (len(escopos) > 1 or "_COMUM" in escopos) else next(iter(escopos))
        if not dados.get("autor"):
            dados["pendencia"] = ("autoria não identificada no vault — "
                                  "confirmar autor/editora/edição antes de estudar")
        vs = sorted(v for v in variantes[chave] if v.strip())
        if len(vs) > 1:
            dados["_variantes"] = vs
        por_escopo[destino].append(dados)

    for escopo, entradas in por_escopo.items():
        entradas.sort(key=lambda e: mid.normalizar(e["titulo"]))
        novos = mid.ids_unicos(entradas)
        for i, e in enumerate(entradas):
            if str(i) in novos:
                e["ancora"] = novos[str(i)]
    return dict(por_escopo), sem_autor, nao_casados


def planejar_reescrita(itens: dict, por_escopo: dict) -> tuple[list, list]:
    """Itens de mapa que podem virar ponteiro — e os que não podem."""
    todas = [e for entradas in por_escopo.values() for e in entradas]
    casados, pendentes = [], []
    for escopo, registros in itens.items():
        for r in registros:
            item = r["item"]
            if item["tipo"] != "livro" or item["ancora"]:
                continue
            achada = mid.casar_exato(item, todas)
            if achada:
                casados.append({"escopo": escopo, "mapa": r["mapa"],
                                "item": item, "entrada": achada})
            else:
                pendentes.append({"escopo": escopo, "mapa": r["mapa"].name,
                                  "texto": item["texto"],
                                  "motivo": ("sem título reconhecível" if not item["titulo"]
                                             else "nenhuma entrada casa exatamente")})
    return casados, pendentes


_PONTEIRO = re.compile(
    r"\s*[—–,;]?\s*((?:cap|caps|capítulo|capítulos|parte|p|pp|pág|págs|seção|vol|unidade)\b.*)$",
    re.I)


def reescrever_item(texto: str, entrada: dict) -> str:
    """`Livro: *X* — Autor (Ed) — cap. 4` vira `Livro: [[...#^ancora|...]] — cap. 4`.

    O ponteiro de leitura é PRESERVADO: é a única parte do item que o catálogo não
    guarda, e apagá-la perderia trabalho de quem escreveu o mapa.
    """
    prefixo = "Livro: "
    m = re.match(r"^\s*([^:*_\[\]]{1,40}?)\s*:\s+", texto)
    if m:
        prefixo = f"{m.group(1).strip()}: "
    ponteiro = ""
    p = _PONTEIRO.search(texto)
    if p:
        ponteiro = f" — {p.group(1).strip()}"
    return f"{prefixo}{mid.wikilink(entrada)}{ponteiro}"


def aplicar(concurso_dir: Path, por_escopo: dict, casados: list,
            reescrever: bool) -> dict:
    escritos = {"catalogos": [], "mapas": [], "backups": []}
    for escopo, entradas in sorted(por_escopo.items()):
        destino = concurso_dir / escopo / "04-MATERIAIS" / "livros-recomendados.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            bak = destino.with_suffix(".md.bak")
            shutil.copy2(destino, bak)
            escritos["backups"].append(str(bak))
        destino.write_text(_render_catalogo(escopo, entradas), encoding="utf-8")
        escritos["catalogos"].append(str(destino))

    if not reescrever:
        return escritos

    por_mapa: dict[Path, list] = defaultdict(list)
    for c in casados:
        por_mapa[c["mapa"]].append(c)
    for mapa, cs in sorted(por_mapa.items()):
        texto = mapa.read_text(encoding="utf-8")
        novo = texto
        for c in cs:
            antigo = c["item"]["texto"]
            if antigo not in novo:
                continue
            novo = novo.replace(antigo, reescrever_item(antigo, c["entrada"]))
        if novo != texto:
            bak = mapa.with_suffix(".md.bak")
            shutil.copy2(mapa, bak)
            mapa.write_text(novo, encoding="utf-8")
            escritos["mapas"].append(str(mapa))
            escritos["backups"].append(str(bak))
    return escritos


def _render_catalogo(escopo: str, entradas: list) -> str:
    cabeca = [
        "---", "tipo: material", f'escopo: "{escopo}"', "---", "",
        f"# 📚 Catálogo de Material — {escopo}", "",
        "> **Catálogo canônico deste escopo.** Cada obra é descrita **uma vez**, aqui;",
        "> os tópicos dos mapas apontam para estas entradas em vez de redigitar título",
        "> e autor. Só referências: **não há reprodução de conteúdo**.",
        "",
        "> Para citar num mapa:",
        "> `- Livro: [[livros-recomendados#^mat-pestana-gramatica|Pestana — A Gramática]] — cap. 4`",
        "", "---", "",
    ]
    corpo = []
    for e in entradas:
        corpo.append(mid.render_entrada(e))
        if e.get("_variantes"):
            corpo.append("<!-- grafias encontradas no vault, consolidadas aqui:\n"
                         + "\n".join(f"     · {v}" for v in e["_variantes"]) + "\n-->\n")
    return "\n".join(cabeca) + "\n".join(corpo)


def relatorio(concurso: str, por_escopo: dict, casados: list, pendentes: list,
              sem_autor: list) -> str:
    linhas = [f"# Migração de materiais — {concurso}", ""]
    total = sum(len(v) for v in por_escopo.values())
    linhas.append(f"**{total} obras distintas** em {len(por_escopo)} escopo(s):")
    for escopo, entradas in sorted(por_escopo.items()):
        com_pend = sum(1 for e in entradas if e.get("pendencia"))
        linhas.append(f"  - {escopo}: {len(entradas)} entradas "
                      f"({com_pend} com pendência de autoria)")
    linhas += ["", f"**Itens de mapa que viram ponteiro:** {len(casados)}",
               f"**Itens que ficam como estão (pendência):** {len(pendentes)}", ""]
    if pendentes:
        linhas.append("## Não casaram — decisão humana")
        for p in pendentes[:40]:
            linhas.append(f"  - [{p['escopo']}/{p['mapa']}] {p['texto'][:90]}")
            linhas.append(f"      motivo: {p['motivo']}")
        if len(pendentes) > 40:
            linhas.append(f"  … e mais {len(pendentes) - 40}")
        linhas.append("")
    if sem_autor:
        linhas.append("## Livros sem autor identificado")
        linhas.append("Entram no catálogo marcados como pendência — nunca maquiados.")
        for s in sem_autor[:30]:
            linhas.append(f"  - [{s['escopo']}/{s['mapa']}] {s['texto'][:90]}")
        if len(sem_autor) > 30:
            linhas.append(f"  … e mais {len(sem_autor) - 30}")
        linhas.append("")
    variantes = [(escopo, e) for escopo, ents in por_escopo.items()
                 for e in ents if e.get("_variantes")]
    if variantes:
        linhas.append("## Grafias consolidadas")
        for escopo, e in variantes:
            linhas.append(f"  - {e['titulo']} ({escopo}) — {len(e['_variantes'])} grafias:")
            for v in e["_variantes"]:
                linhas.append(f"      · {v[:100]}")
    return "\n".join(linhas)


def aplicar_enriquecimento(por_escopo: dict, enriquecido: list) -> tuple[int, list]:
    """Funde o metadado pesquisado nas entradas, casando pela ÂNCORA.

    Casa por âncora e não por título: a âncora é a identidade, e o texto do
    título é justamente o que a pesquisa pode ter corrigido. Campo vazio no
    enriquecimento **não apaga** o que já existia — pesquisa que não achou não é
    o mesmo que dado inexistente.
    """
    por_ancora = {e["ancora"]: e for entradas in por_escopo.values() for e in entradas}
    aplicados, ignorados = 0, []
    for reg in enriquecido:
        alvo = por_ancora.get(reg.get("ancora", ""))
        if not alvo:
            ignorados.append(reg.get("ancora") or reg.get("titulo") or "?")
            continue
        for campo in ("autor", "editora", "isbn", "onde_obter", "cobre"):
            valor = (reg.get(campo) or "").strip()
            if valor:
                alvo[campo] = valor
        # o id foi proposto a partir do que se sabia ANTES da pesquisa; achar o
        # autor não renomeia a âncora, porque o mapa já pode estar apontando
        # para ela — a lição do `aprofundamento_id.py` sobre renomear vale aqui
        if alvo.get("autor"):
            alvo["pendencia"] = (reg.get("pendencia") or "").strip()
        elif reg.get("pendencia"):
            alvo["pendencia"] = reg["pendencia"].strip()
        aplicados += 1
    return aplicados, ignorados


def main() -> int:
    ap = argparse.ArgumentParser(description="Migra o material para o catálogo canônico")
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--listar-obras", action="store_true",
                    help="emite as obras consolidadas em JSON, para pesquisa")
    ap.add_argument("--enriquecimento", type=Path,
                    help="JSON com o metadado pesquisado, casado por âncora")
    ap.add_argument("--aplicar", action="store_true",
                    help="escreve de verdade (padrão: dry-run)")
    ap.add_argument("--sem-reescrever-mapas", action="store_true",
                    help="cria o catálogo mas não toca nos mapas")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not a.concurso_dir.is_dir():
        sys.stderr.write(f"ERRO: não é diretório: {a.concurso_dir}\n")
        return 1

    itens, catalogos = varrer(a.concurso_dir)
    if not itens and not catalogos:
        sys.stderr.write("ERRO: nenhum mapa nem catálogo encontrado — "
                         "o caminho é a pasta do concurso?\n")
        return 1

    por_escopo, sem_autor, _ = consolidar(itens, catalogos)

    if a.enriquecimento:
        dados = json.loads(a.enriquecimento.read_text(encoding="utf-8"))
        aplicados, ignorados = aplicar_enriquecimento(
            por_escopo, dados if isinstance(dados, list) else dados.get("obras", []))
        print(f"# Enriquecimento: {aplicados} obra(s) atualizadas", file=sys.stderr)
        if ignorados:
            print(f"# AVISO: {len(ignorados)} âncora(s) do enriquecimento não existem "
                  f"no catálogo: {', '.join(ignorados[:8])}", file=sys.stderr)

    if a.listar_obras:
        print(json.dumps({
            "concurso": a.concurso_dir.name,
            "obras": [{"escopo": escopo, **{k: v for k, v in e.items()
                                            if not k.startswith("_")}}
                      for escopo, entradas in sorted(por_escopo.items())
                      for e in entradas],
        }, indent=2, ensure_ascii=False))
        return 0

    casados, pendentes = planejar_reescrita(itens, por_escopo)

    if a.json:
        print(json.dumps({
            "concurso": a.concurso_dir.name,
            "obras": {k: len(v) for k, v in por_escopo.items()},
            "casados": len(casados), "pendentes": len(pendentes),
            "sem_autor": len(sem_autor),
        }, indent=2, ensure_ascii=False))
    else:
        print(relatorio(a.concurso_dir.name, por_escopo, casados, pendentes, sem_autor))

    if a.aplicar:
        escritos = aplicar(a.concurso_dir, por_escopo, casados,
                           not a.sem_reescrever_mapas)
        print(f"\n✅ {len(escritos['catalogos'])} catálogo(s) e "
              f"{len(escritos['mapas'])} mapa(s) escritos · "
              f"{len(escritos['backups'])} backup(s)")
    else:
        print("\n(dry-run — nada foi escrito. Use --aplicar.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
