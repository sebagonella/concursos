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


_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_PREFIXO_NUM = re.compile(r"^\d+[-_]")


def _parece_slug(texto: str) -> bool:
    """`lingua-inglesa` é identificador; `Língua Inglesa` é rótulo de leitura."""
    t = (texto or "").strip()
    return bool(t) and " " not in t and t == t.lower()


def _tokens(texto: str) -> frozenset:
    return frozenset(mid.tokens_titulo(texto))


def materias_do_concurso(concurso_dir: Path) -> list[dict]:
    """As matérias do concurso: onde o mapa de cada uma vive e como se chama.

    Três sinais por mapa, porque nenhum é confiável sozinho no vault real: dos 9
    mapas do BB, `materia:` está preenchido em 4 e `materia_id:` em 2. O nome do
    arquivo é o único que existe sempre.
    """
    materias = []
    for escopo_dir in sorted(p for p in concurso_dir.iterdir() if p.is_dir()):
        for mapa in mapas_do_escopo(escopo_dir):
            fm = {}
            m = _FRONTMATTER.match(mapa.read_text(encoding="utf-8"))
            if m:
                fm = dict(re.findall(r'^(\w+):\s*"?([^"\n]*)"?', m.group(1), re.M))
            stem = _PREFIXO_NUM.sub("", mapa.stem)
            chaves = [c for c in (_tokens(fm.get("materia", "")),
                                  _tokens(fm.get("materia_id", "")),
                                  _tokens(stem)) if c]
            materias.append({"escopo": escopo_dir.name, "chaves": chaves,
                             "rotulo": (fm.get("materia") or "").strip() or stem,
                             "declarado": bool(fm.get("materia"))})
    return materias


def resolver_materia(nome: str, materias: list[dict]) -> dict | None:
    """A matéria a que este nome se refere — ou None se não der para saber."""
    alvo = _tokens(nome)
    if not alvo:
        return None
    for m in materias:
        if alvo in m["chaves"]:
            return m
    contidas = [m for m in materias if any(c <= alvo for c in m["chaves"])]
    return contidas[0] if len(contidas) == 1 else None


def resolver_escopo(materia: str, tabela) -> str:
    """Escopo de uma matéria nomeada no catálogo legado — ou "" se não resolver.

    Duas etapas, e a segunda é deliberadamente estreita. O título do catálogo é
    mais longo que o nome do arquivo do mapa ("Conhecimentos Específicos do
    Agente Social" contra `especificos-agente-social`), então casamento exato
    falha em 4 das 5 matérias do SEDES. A saída é **contenção única**: os tokens
    do mapa cabem inteiros dentro do título, e só um mapa satisfaz isso.

    Isso NÃO é o casamento por similaridade que o repo proíbe. Lá o universo era
    203 tópicos contra 92 assuntos, com 18% de acerto; aqui são 4 a 5 mapas do
    mesmo concurso cujos nomes foram derivados desses mesmos títulos. E a
    exigência de unicidade é o que impede o palpite: empate devolve "" e vira
    aviso, nunca escolha silenciosa.
    """
    m = resolver_materia(materia, tabela)
    return m["escopo"] if m else ""


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

    # A PASTA onde o catálogo está não diz a que escopo a obra pertence. O
    # catálogo legado do BB mora em `_COMUM` e traz 25 livros de Tecnologia da
    # Informação, que é matéria de UM cargo — rotear pelo arquivo mandou os 25
    # para o comum. Quem manda é a matéria: o escopo é o do mapa dela.
    materias = materias_do_concurso(concurso_dir)
    for escopo, entradas in catalogos.items():
        for e in entradas:
            fonte = e.get("materia") or e.get("cobre") or ""
            m = resolver_materia(fonte, materias)
            e["_escopo"] = m["escopo"] if m else escopo
            e["_escopo_resolvido"] = m is not None
            if m:
                # O mapa que não declara `materia:` adota o título do catálogo
                # legado como rótulo: `probabilidade-estatistica` é identificador,
                # "Probabilidade e Estatística" é como a pessoa lê. O critério é
                # LEGIBILIDADE, não comprimento — comparar tamanho fazia
                # "Matemática" (9) perder para `matematica` (10).
                if not m["declarado"] and fonte and _parece_slug(m["rotulo"]) \
                        and not _parece_slug(fonte):
                    m["rotulo"] = fonte.strip()
                e["cobre"] = m["rotulo"]
    return itens, catalogos, materias


def _entradas_do_catalogo_legado(cat: Path) -> list[dict]:
    """O catálogo antigo é `- Autor — *Título*. Editora.` sob `## Matéria`.

    Ler isso importa: são 62 itens que já foram pesquisados uma vez, e descartá-los
    obrigaria a refazer a pesquisa inteira — pior, faria a migração parecer que o
    vault não tinha bibliografia nenhuma.
    """
    texto = cat.read_text(encoding="utf-8")
    # O frontmatter sai FORA. A lista `tags:` do YAML é escrita com `  - item`, que
    # casa o mesmo regex de bullet do corpo — e três tags do BB
    # (`area/carreira`, `concurso/bb/previsto`, `tipo/material`) viraram obras no
    # catálogo, com âncora e tudo. Lixo que entra em silêncio é pior do que erro.
    texto = re.sub(r"^---\s*\n.*?\n---\s*\n", "", texto, count=1, flags=re.DOTALL)
    entradas, materia = [], ""
    for linha in texto.splitlines():
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


def _rotulo_do_mapa(mapa: Path, materias) -> str:
    """O rótulo canônico da matéria deste mapa — o mesmo que o catálogo usa."""
    stem = _PREFIXO_NUM.sub("", mapa.stem)
    m = resolver_materia(stem, materias or [])
    return m["rotulo"] if m else stem


def consolidar(itens: dict, catalogos: dict, materias: list = None) -> tuple[dict, list, list]:
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

    nao_resolvidos = []
    for escopo, entradas in catalogos.items():
        for e in entradas:
            if not e["titulo"]:
                continue
            destino = e.get("_escopo") or escopo
            if e.get("materia") and not e.get("_escopo_resolvido"):
                nao_resolvidos.append({"escopo": escopo, "materia": e["materia"],
                                       "titulo": e["titulo"]})
            chave = mid.chave_obra(e["titulo"], e.get("autor", ""))
            dados = dict(e)
            dados.setdefault("cobre", "")
            if not dados["cobre"] and e.get("materia"):
                dados["cobre"] = e["materia"]
            registrar(chave, dados, destino,
                      f'{e["titulo"]} — {e.get("autor", "")} ({e.get("editora", "")})')

    sem_autor = []
    for escopo, registros in itens.items():
        for r in registros:
            item = r["item"]
            if item["tipo"] != "livro" or item["ancora"]:
                continue
            if not item["titulo"]:
                continue
            chave = mid.chave_obra(item["titulo"], item["autor"])
            registrar(chave, {"titulo": item["titulo"], "autor": item["autor"],
                              "editora": item["editora"], "isbn": "",
                              "cobre": _rotulo_do_mapa(r["mapa"], materias),
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
    return dict(por_escopo), sem_autor, nao_resolvidos


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


def reescrever_item(texto: str, entrada: dict,
                    arquivo: str = "livros-recomendados") -> str:
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
    return f"{prefixo}{mid.wikilink(entrada, arquivo)}{ponteiro}"


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
    # Agrupado por matéria, e não por acaso: o `Cobre:` de cada entrada mais o
    # `## Matéria` são o que permite a uma execução futura saber a que escopo a
    # obra pertence. Sem eles, o catálogo novo perderia a informação que o legado
    # tinha — e o roteamento voltaria a depender da pasta onde o arquivo está,
    # que foi exatamente o defeito que mandou 25 livros de TI para o comum.
    grupos: dict[str, list] = {}
    for e in entradas:
        grupos.setdefault((e.get("cobre") or e.get("materia") or "Sem matéria"), []).append(e)
    corpo = []
    for materia, itens_g in sorted(grupos.items()):
        corpo.append(f"## {materia}\n")
        for e in itens_g:
            corpo.append(mid.render_entrada(e))
            if e.get("_variantes"):
                corpo.append("<!-- grafias encontradas no vault, consolidadas aqui:\n"
                             + "\n".join(f"     · {v}" for v in e["_variantes"]) + "\n-->\n")
    return "\n".join(cabeca) + "\n".join(corpo)


MARCA_COBERTURA = "## ⚠️ Matérias sem material no catálogo"


def enriquecer_catalogos(concurso_dir: Path, registros: list) -> dict:
    """Aplica metadado pesquisado nos catálogos que JÁ existem, casando por âncora.

    Não passa pela consolidação de propósito: reconstruir o catálogo depois que a
    pesquisa corrigiu uma autoria CRIA duplicata em vez de resolvê-la (medido:
    +23 entradas). O catálogo existente é a autoridade; aqui só se preenche.

    `titulo` só é trocado quando a pesquisa manda explicitamente — é o caso de
    obra que estava com o título errado no vault. A ÂNCORA nunca muda junto: ela
    é a identidade, e o mapa pode já estar apontando para ela.
    """
    por_ancora = {r["ancora"]: r for r in registros if r.get("ancora")}
    tocados, aplicados, ignorados = {}, 0, set(por_ancora)
    for cat in sorted(concurso_dir.glob("*/04-MATERIAIS/livros-recomendados.md")):
        texto = cat.read_text(encoding="utf-8")
        entradas = mid.parsear_catalogo(texto)
        mudou = False
        linhas = texto.splitlines()
        for e in entradas:
            reg = por_ancora.get(e["ancora"])
            if not reg:
                continue
            ignorados.discard(e["ancora"])
            novo = dict(e)
            for campo in ("titulo", *mid.CAMPOS):
                valor = (reg.get(campo) or "").strip()
                if valor:
                    novo[campo] = valor
            # `pendencia` é o único campo em que vazio SIGNIFICA algo: a pesquisa
            # dizendo "fechei, não há mais ressalva". Nos outros, vazio quer dizer
            # "não encontrei" e não pode apagar dado apurado — mas manter uma
            # pendência que já foi resolvida assusta quem lê o catálogo por nada.
            # A distinção é entre chave AUSENTE e chave presente com valor vazio.
            if "pendencia" in reg:
                novo["pendencia"] = (reg["pendencia"] or "").strip()
            if novo == e:
                continue
            ini = fim = None
            for i, l in enumerate(linhas):
                if l.strip() == f'^{e["ancora"]}':
                    fim = i + 1
                    for j in range(i, -1, -1):
                        if linhas[j].startswith("### "):
                            ini = j
                            break
                    break
            if ini is None:
                continue
            linhas = (linhas[:ini]
                      + mid.render_entrada(novo).rstrip("\n").splitlines()
                      + linhas[fim:])
            mudou, aplicados = True, aplicados + 1
        if mudou:
            cat.with_suffix(".md.bak").write_text(texto, encoding="utf-8")
            cat.write_text("\n".join(linhas).rstrip("\n") + "\n", encoding="utf-8")
            tocados[cat.parents[1].name] = True
    return {"aplicados": aplicados, "catalogos": sorted(tocados),
            "ancoras_sem_destino": sorted(ignorados)}


def materias_sem_material(concurso_dir: Path) -> dict[str, list]:
    """Matérias que têm mapa e NENHUMA obra no catálogo do seu escopo.

    Precisa estar escrito no vault e aparecer no site: matéria sem bibliografia
    é lacuna de preparação, e lacuna que só existe na cabeça de quem auditou
    volta a existir na próxima execução. É a mesma regra do resto do projeto —
    o que falta se declara, não se descobre.
    """
    materias = materias_do_concurso(concurso_dir)
    cobertas = set()
    for cat in concurso_dir.glob("*/04-MATERIAIS/livros-recomendados.md"):
        for e in mid.parsear_catalogo(cat.read_text(encoding="utf-8")):
            m = resolver_materia(e.get("cobre", ""), materias)
            if m:
                cobertas.add((m["escopo"], m["rotulo"]))
    faltando: dict[str, list] = defaultdict(list)
    for m in materias:
        if (m["escopo"], m["rotulo"]) not in cobertas:
            faltando[m["escopo"]].append(m["rotulo"])
    return dict(faltando)


def atualizar_cobertura(concurso_dir: Path, aplicar: bool = False) -> dict:
    """(Re)escreve, em cada catálogo, a seção das matérias sem material.

    A seção é sempre reescrita do zero: deixá-la desatualizada seria pior do que
    não tê-la, porque uma lacuna já resolvida continuaria assustando.

    `aplicar` tem default False de propósito, e não é zelo. Este arquivo anuncia
    "dry-run por padrão: sem --aplicar, nada é escrito", mas o `main` chamava esta
    função sem consultar a flag — e o `base = texto[:corte]` abaixo DESCARTA tudo
    o que o usuário tenha escrito depois do marcador de cobertura. Escrita sem
    pedir, sem backup e com truncagem, num arquivo que o usuário edita à mão.
    """
    faltando = materias_sem_material(concurso_dir)
    tocados = {}
    for cat in sorted(concurso_dir.glob("*/04-MATERIAIS/livros-recomendados.md")):
        escopo = cat.parents[1].name
        texto = cat.read_text(encoding="utf-8")
        corte = texto.find(MARCA_COBERTURA)
        base = (texto[:corte] if corte >= 0 else texto).rstrip("\n")
        sem = faltando.get(escopo, [])
        if sem:
            linhas = [f"\n\n{MARCA_COBERTURA}\n",
                      "Estas matérias deste escopo têm mapa de estudo e **nenhuma obra**",
                      "no catálogo. Não é ausência de conteúdo — é bibliografia por levantar.\n"]
            linhas += [f"- {m}" for m in sorted(sem)]
            novo = base + "\n".join(linhas) + "\n"
        else:
            novo = base + "\n"
        if novo != texto:
            if aplicar:
                cat.with_suffix(".md.bak").write_text(texto, encoding="utf-8")
                cat.write_text(novo, encoding="utf-8")
            tocados[escopo] = sem
    return tocados


def fundir_entradas(catalogo: Path, manter: str, remover: str) -> dict:
    """Funde duas entradas do MESMO catálogo: `remover` some, `manter` fica.

    Existe porque re-executar a migração não é idempotente depois que a pesquisa
    corrige uma autoria — reconstruir o catálogo criaria duplicatas em vez de
    resolvê-las. Aqui se edita o catálogo existente, que é a autoridade.

    Os campos vazios de `manter` são preenchidos com os de `remover`: a entrada
    que fica não pode sair mais pobre da fusão. E o título da removida vira
    comentário, porque é a grafia que alguém usou e que ainda está nos mapas.
    """
    texto = catalogo.read_text(encoding="utf-8")
    entradas = {e["ancora"]: e for e in mid.parsear_catalogo(texto)}
    if manter not in entradas or remover not in entradas:
        raise SystemExit(f"ERRO: âncora ausente em {catalogo.name}: "
                         f"{manter if manter not in entradas else remover}")
    a, b = entradas[manter], entradas[remover]
    for campo in mid.CAMPOS:
        if not (a.get(campo) or "").strip() and (b.get(campo) or "").strip():
            a[campo] = b[campo]

    linhas = texto.splitlines()
    ini = fim = None
    for i, linha in enumerate(linhas):
        if linha.strip() == f"^{remover}":
            fim = i + 1
            for j in range(i, -1, -1):
                if linhas[j].startswith("### "):
                    ini = j
                    break
            break
    if ini is None:
        raise SystemExit(f"ERRO: bloco de {remover} não localizado")
    while fim < len(linhas) and not linhas[fim].strip():
        fim += 1
    removidas = "\n".join(linhas[ini:fim])
    novas = linhas[:ini] + linhas[fim:]

    # regravar a entrada que fica, agora completa
    saida, i = [], 0
    while i < len(novas):
        if novas[i].startswith("### ") and _ancora_do_bloco(novas, i) == manter:
            j = i
            while j < len(novas) and novas[j].strip() != f"^{manter}":
                j += 1
            saida.append(mid.render_entrada(a).rstrip("\n"))
            saida.append(f"<!-- grafia consolidada nesta entrada:\n"
                         f"     · {b['titulo']} -->")
            i = j + 1
            continue
        saida.append(novas[i])
        i += 1
    catalogo.with_suffix(".md.bak").write_text(texto, encoding="utf-8")
    catalogo.write_text("\n".join(saida).rstrip("\n") + "\n", encoding="utf-8")
    return {"manteve": manter, "removeu": remover, "titulo_removido": b["titulo"],
            "linhas_removidas": len(removidas.splitlines())}


def _ancora_do_bloco(linhas: list, ini: int) -> str:
    for k in range(ini, min(ini + 30, len(linhas))):
        m = _BLOCO.match(linhas[k])
        if m:
            return m.group(1)
        if k > ini and linhas[k].startswith("### "):
            return ""
    return ""


_BLOCO = re.compile(r"^\s*\^([A-Za-z0-9-]+)\s*$")


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
    ap.add_argument("--fundir", action="append", metavar="MANTER=REMOVER",
                    help="funde duas entradas do mesmo catálogo (repetível)")
    ap.add_argument("--so-mapas", action="store_true",
                    help="reescreve os mapas apontando para o catálogo (dry-run "
                         "sem --aplicar). NÃO reconstrói o catálogo: ele é a autoridade")
    ap.add_argument("--sem-canonizar-prefixos", action="store_true")
    ap.add_argument("--sem-ligar-normas", action="store_true")
    ap.add_argument("--cobertura", action="store_true",
                    help="(re)escreve a seção de matérias sem material nos catálogos")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not a.concurso_dir.is_dir():
        sys.stderr.write(f"ERRO: não é diretório: {a.concurso_dir}\n")
        return 1

    if a.so_mapas:
        r = reescrever_mapas(a.concurso_dir, aplicar=a.aplicar,
                             canonizar=not a.sem_canonizar_prefixos,
                             ligar_normas=not a.sem_ligar_normas)
        if a.json:
            print(json.dumps({k: (len(v) if isinstance(v, list) else v)
                              for k, v in r.items()}, indent=2, ensure_ascii=False))
        else:
            print(f"# Reescrita dos mapas — {a.concurso_dir.name}\n")
            print(f"**{len(r['apontados'])} itens** passam a apontar para o catálogo")
            print(f"**{r['prefixos']} prefixos** canonizados")
            print(f"**{r['normas_ligadas']} normas** ligadas ao PDF baixado")
            print(f"**{len(r['mapas'])} mapas** alterados\n")
            if r["ambiguos"]:
                print("## Ambíguos — ficam como estão")
                for x in r["ambiguos"]:
                    print(f"  - [{x['escopo']}] {x['texto']}")
                    print(f"      entre: {', '.join(x['entre'])}")
            if r["sem_correspondencia"]:
                print("\n## Sem correspondência no catálogo — ficam como estão")
                for x in r["sem_correspondencia"]:
                    print(f"  - [{x['escopo']}] {x['texto']}")
        print("\n(dry-run — nada foi escrito. Use --aplicar.)"
              if not a.aplicar else f"\n✅ {len(r['mapas'])} mapa(s) reescritos, com backup",
              file=sys.stderr if a.json else sys.stdout)
        return 0

    if a.enriquecimento and a.aplicar:
        dados = json.loads(a.enriquecimento.read_text(encoding="utf-8"))
        regs = dados if isinstance(dados, list) else dados.get("obras", [])
        r = enriquecer_catalogos(a.concurso_dir, regs)
        print(f"  {r['aplicados']} entrada(s) atualizadas em {len(r['catalogos'])} catálogo(s)")
        for x in r["ancoras_sem_destino"]:
            print(f"  AVISO: âncora sem destino no catálogo: {x}")
        return 0

    if a.cobertura:
        tocados = atualizar_cobertura(a.concurso_dir, aplicar=a.aplicar)
        if not tocados:
            print("  nenhum catálogo alterado (cobertura já estava correta)")
        for escopo, sem in sorted(tocados.items()):
            print(f"  {escopo}: {len(sem)} matéria(s) sem material" if sem
                  else f"  {escopo}: seção removida (todas cobertas)")
            for m in sem:
                print(f"      · {m}")
        if tocados:
            print("\n(dry-run — nada foi escrito. Use --aplicar.)" if not a.aplicar
                  else f"\n✅ {len(tocados)} catálogo(s) atualizados, com backup")
        return 0

    if a.fundir:
        for par in a.fundir:
            manter, _, remover = par.partition("=")
            alvo = next((c for c in a.concurso_dir.glob("*/04-MATERIAIS/livros-recomendados.md")
                         if f"^{manter}" in c.read_text(encoding="utf-8")
                         and f"^{remover}" in c.read_text(encoding="utf-8")), None)
            if not alvo:
                raise SystemExit(f"ERRO: {manter} e {remover} não estão no mesmo catálogo")
            # Mesma disciplina do resto do arquivo: sem --aplicar, só o relatório.
            # `fundir_entradas` faz backup, mas escrever sem pedir contradiz o
            # contrato anunciado no topo — e é dele que vem a confiança de rodar.
            if not a.aplicar:
                print(f"  (dry-run) fundiria em {alvo.parents[1].name}: "
                      f"{remover.strip()} -> {manter.strip()}")
                continue
            r = fundir_entradas(alvo, manter.strip(), remover.strip())
            print(f"  fundido em {alvo.parents[1].name}: {r['removeu']} -> {r['manteve']} "
                  f"({r['titulo_removido'][:40]!r})")
        if not a.aplicar:
            print("\n(dry-run — nada foi escrito. Use --aplicar.)")
        return 0

    itens, catalogos, materias = varrer(a.concurso_dir)
    if not itens and not catalogos:
        sys.stderr.write("ERRO: nenhum mapa nem catálogo encontrado — "
                         "o caminho é a pasta do concurso?\n")
        return 1

    por_escopo, sem_autor, nao_resolvidos = consolidar(itens, catalogos, materias)

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
        # em `--json` a nota vai para stderr: stdout tem de ser JSON puro, senão
        # quem consome com `json.load` quebra — e foi o que aconteceu
        saida = sys.stderr if a.json else sys.stdout
        print(f"\n✅ {len(escritos['catalogos'])} catálogo(s) e "
              f"{len(escritos['mapas'])} mapa(s) escritos · "
              f"{len(escritos['backups'])} backup(s)", file=saida)
    else:
        print("\n(dry-run — nada foi escrito. Use --aplicar.)",
              file=sys.stderr if a.json else sys.stdout)
    return 0



# =========================================================================== #
# Fase 2: reescrever os mapas para apontar ao catálogo
# =========================================================================== #
_ALIAS = re.compile(r"grafia(?:s)? consolidada[^:]*:\n((?:\s*·[^\n]*\n)+)")
_LINHA_ALIAS = re.compile(r"·\s*(.+?)\s*(?:-->)?\s*$")


def indice_do_catalogo(concurso_dir: Path) -> dict[str, dict[str, set]]:
    """{escopo: {titulo normalizado: {âncoras}}}, incluindo as grafias fundidas.

    A normalização é **estrita** (`normalizar`, não `tokens_titulo`): a do id
    descarta "para concursos", e com ela `A Gramática para Concursos` e
    `Gramática da Língua Portuguesa` colidiam no mesmo catálogo.

    As grafias registradas nas fusões entram como alias — é procedência de
    verdade, gravada no momento em que se decidiu que duas entradas eram a mesma
    obra, e não semelhança calculada agora.
    """
    idx: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for cat in sorted(concurso_dir.glob("*/04-MATERIAIS/livros-recomendados.md")):
        escopo = cat.parents[1].name
        texto = cat.read_text(encoding="utf-8")
        for e in mid.parsear_catalogo(texto):
            if e["titulo"]:
                idx[escopo][mid.normalizar(e["titulo"])].add(e["ancora"])
        for bloco in _ALIAS.finditer(texto):
            pos = texto.rfind("^", 0, bloco.start())
            m = re.match(r"\^([A-Za-z0-9-]+)", texto[pos:]) if pos >= 0 else None
            if not m:
                continue
            for linha in bloco.group(1).splitlines():
                g = _LINHA_ALIAS.search(linha.strip())
                if g:
                    idx[escopo][mid.normalizar(g.group(1))].add(m.group(1))
    return {k: dict(v) for k, v in idx.items()}


# `Lei 8.742/1993`, `Lei nº 8.742/93`, `LC 105/2001`, `Decreto 7.053/2009`,
# `Resolução CNAS nº 145/2004`. O ano de 2 dígitos aparece no vault.
_CITA_NORMA = re.compile(
    r"\b((?:lei\s+complementar|lei|decreto[- ]lei|decreto|resolu[çc][ãa]o|"
    r"portaria|instru[çc][ãa]o\s+normativa|circular|s[úu]mula)"
    r"(?:\s+(?:cmn|cnas|cfess|cfp|conjunta|bacen|normativa))*"
    r"(?:\s*n?[ºo°.]*\s*)\s*)(\d{1,3}(?:\.\d{3})*|\d+)\s*[/-]\s*(\d{2,4})",
    re.IGNORECASE)


def indice_de_leis(concurso_dir: Path) -> dict[tuple, str]:
    """{(numero, ano): nome do PDF} das leis efetivamente baixadas.

    Casa por NÚMERO e ANO, que é exato. Sem isso, 2 dos 473 itens de material do
    vault linkavam para algo baixado — os outros 471 eram texto morto, inclusive
    os 26 que citam norma cujo PDF está a dois diretórios de distância.
    """
    idx: dict[tuple, str] = {}
    for pdf in sorted(concurso_dir.glob("*/04-MATERIAIS/leis-baixadas/*.pdf")):
        m = re.search(r"(\d+)-(\d{4})", pdf.stem)
        if m:
            idx.setdefault((m.group(1).lstrip("0"), m.group(2)), pdf.name)
    return idx


def _link_de_norma(texto: str, leis: dict) -> tuple[str, bool]:
    """Troca a citação da norma por wikilink para o PDF baixado, se houver."""
    if "[[" in texto:
        return texto, False
    achou = False

    def trocar(m):
        nonlocal achou
        if achou:
            return m.group(0)
        numero = m.group(2).replace(".", "").lstrip("0")
        ano = m.group(3)
        if len(ano) == 2:
            candidatos = [a for (n, a) in leis if n == numero and a.endswith(ano)]
            ano = candidatos[0] if len(candidatos) == 1 else ano
        arquivo = leis.get((numero, ano))
        if not arquivo:
            return m.group(0)
        achou = True
        return f"[[{arquivo}|{m.group(0).strip()}]]"

    novo = _CITA_NORMA.sub(trocar, texto, count=1)
    return novo, achou


def reescrever_mapas(concurso_dir: Path, aplicar: bool = False,
                     canonizar: bool = True, ligar_normas: bool = True) -> dict:
    """Faz o item do mapa APONTAR para o catálogo, em vez de redigitar a obra.

    O catálogo é a autoridade: esta função não o reconstrói. Reconstruir depois
    que a pesquisa corrigiu uma autoria CRIA duplicata em vez de resolvê-la.

    Casamento é exato ou nada, e ambiguidade não desempata: `Probabilidade e
    Estatística` serve a Devore e a Morettin no mesmo escopo, e escolher um
    mandaria o estudante ao livro errado.
    """
    idx = indice_do_catalogo(concurso_dir)
    leis = indice_de_leis(concurso_dir)
    autores, arquivo_da_ancora = {}, {}
    for cat in concurso_dir.glob("*/04-MATERIAIS/livros-recomendados.md"):
        rel = f'{cat.parents[1].name}/04-MATERIAIS/{cat.stem}'
        for e in mid.parsear_catalogo(cat.read_text(encoding="utf-8")):
            autores[e["ancora"]] = e.get("autor", "")
            arquivo_da_ancora[e["ancora"]] = rel
    r = {"apontados": [], "ambiguos": [], "sem_correspondencia": [],
         "prefixos": 0, "normas_ligadas": 0, "mapas": []}

    for escopo_dir in sorted(p for p in concurso_dir.iterdir() if p.is_dir()):
        escopo = escopo_dir.name
        cand: dict[str, set] = defaultdict(set)
        for chave, ancoras in idx.get("_COMUM", {}).items():
            cand[chave] |= ancoras
        for chave, ancoras in idx.get(escopo, {}).items():
            cand[chave] |= ancoras

        for mapa in mapas_do_escopo(escopo_dir):
            texto = mapa.read_text(encoding="utf-8")
            linhas = texto.splitlines()
            faixas = blocos_de_material(texto)
            mudou = False
            for ini, fim in faixas:
                for i in range(ini, min(fim, len(linhas))):
                    m = re.match(r"^(\s*[-*]\s+)(.*)$", linhas[i])
                    if not m:
                        continue
                    corpo = m.group(2)
                    item = mid.parsear_item(corpo)
                    novo = corpo

                    if item["tipo"] == "livro" and not item["ancora"] and item["titulo"]:
                        alvo = cand.get(mid.normalizar(item["titulo"]), set())
                        # Título ambíguo com autor escrito no mapa: o sobrenome
                        # desempata. `Português para Concursos` serve a Pestana e a
                        # Douglas, mas o item diz "— Fernando Pestana". Isso é
                        # casamento EXATO num segundo campo, não similaridade.
                        if len(alvo) > 1 and item["autor"]:
                            s = mid.sobrenome(item["autor"])
                            por_autor = {a for a in alvo
                                         if s and s == mid.sobrenome(autores.get(a, ""))}
                            if len(por_autor) == 1:
                                alvo = por_autor
                        ref = {"mapa": str(mapa), "escopo": escopo,
                               "texto": item["texto"][:90]}
                        if len(alvo) == 1:
                            ancora = next(iter(alvo))
                            novo = reescrever_item(
                                corpo, {"titulo": item["titulo"],
                                        "autor": item["autor"], "ancora": ancora},
                                arquivo_da_ancora.get(ancora, "livros-recomendados"))
                            r["apontados"].append({**ref, "ancora": ancora})
                        elif len(alvo) > 1:
                            r["ambiguos"].append({**ref, "entre": sorted(alvo)})
                        else:
                            r["sem_correspondencia"].append(ref)

                    if ligar_normas and item["tipo"] in ("norma", "documento", "outro"):
                        novo, ok = _link_de_norma(novo, leis)
                        r["normas_ligadas"] += int(ok)

                    if canonizar and item["prefixo"] and not item["canonico"] \
                            and item["tipo"] != "outro":
                        rotulo = mid.PREFIXOS[item["tipo"]][0]
                        novo = re.sub(rf"^{re.escape(item['prefixo'])}\s*:",
                                      f"{rotulo}:", novo, count=1)
                        r["prefixos"] += 1

                    if novo != corpo:
                        linhas[i] = m.group(1) + novo
                        mudou = True
            if mudou:
                r["mapas"].append(str(mapa))
                if aplicar:
                    mapa.with_suffix(".md.bak").write_text(texto, encoding="utf-8")
                    mapa.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return r

if __name__ == "__main__":
    sys.exit(main())
