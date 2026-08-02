#!/usr/bin/env python3
"""
renomear_aprof.py — máquina de renomeação de pastas de aprofundamento.

Não é executável. É o lugar ÚNICO onde mora o conhecimento de layout que
qualquer renomeação de aprofundamento precisa ter:

  - os arquivos de um aprofundamento repetem o NOME-BASE (`{assunto}--{id}--{CONCURSO}`),
    porque o Obsidian resolve wikilink por nome de arquivo e dois `crase.md` em
    pastas diferentes ficam ambíguos;
  - o índice da matéria vive FORA de `assuntos/` e referencia cada arquivo pelo
    path relativo a partir de `assuntos/`, sem extensão;
  - o pipe do wikilink aparece cru (`|`) e escapado (`\\|`, dentro de tabela), e o
    link também aparece sem alias, terminando em `]]`.

Consumidores:
  - `migrar_aprofundamentos.py` — move layouts antigos para a convenção atual;
  - `ampliar_aprofundamento.py` — troca o conjunto de fontes de um aprofundamento
    existente (`padrao--pestana` -> `padrao--pestana+rosenthal`).

Os dois fazem a MESMA renomeação. Duplicar esta lógica reproduziria o modo de
falha do `fix_notebooklm_packs.py`: uma cópia que deriva do original e um dia
acha zero, calada. Há teste que trava a identidade dos objetos entre os módulos
justamente para ninguém "consertar" copiando de volta.
"""
import re
from pathlib import Path

# Arquivos que pertencem ao aprofundamento e viajam com ele.
# PREFIXOS_RENOMEAR: o nome-base muda, então o arquivo é renomeado.
PREFIXOS_RENOMEAR = ("flashcards-", "podcast-", "mapa-mental-", "video-", "report-")
# ACOMPANHAM: nome fixo, viaja como está.
# `_notebooklm-estado.json` guarda o notebook_id e os ids de tarefa da
# concurso-notebooklm. Antes ele sobrevivia por acidente (caía no `else` que
# mantém o nome) e era DESCARTADO no layout legado-plano, onde a pasta do assunto
# é a própria pasta do aprofundamento — perder o `notebook_id` ali obrigaria a
# recriar o notebook do zero.
ACOMPANHAM = ("cards.json", "_fonte-notebooklm.md", "_fonte-notebooklm.bak.md",
              "_notebooklm-estado.json")

# os três finais possíveis de um wikilink: com alias, com alias dentro de tabela,
# e sem alias
FINAIS_WIKILINK = ("|", "\\|", "]]")


def ler_frontmatter(md: Path) -> dict:
    """Frontmatter plano (`k: v` por linha) + `_corpo`, `_texto` e `_fm_bruto`.

    Deliberadamente não usa YAML: todo leitor de frontmatter deste repo lê
    `k: v` por linha, e o formato dos artefatos é escolhido para caber nisso.
    """
    try:
        txt = md.read_text(encoding="utf-8")
    except Exception:
        return {"_corpo": ""}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    fm = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha and not linha.lstrip().startswith("-"):
                k, _, v = linha.partition(":")
                v = v.strip()
                if not v.startswith(('"', "'")):
                    v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
                fm[k.strip()] = v.strip('"').strip("'")
    fm["_corpo"] = txt[m.end():] if m else txt
    fm["_texto"] = txt
    fm["_fm_bruto"] = m.group(1) if m else ""
    return fm


def atualizar_frontmatter(texto: str, novos: dict) -> str:
    """Insere/atualiza chaves no frontmatter, preservando o resto."""
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", texto, re.DOTALL)
    if not m:
        return texto
    corpo_fm = m.group(2)
    for k, v in novos.items():
        linha = f'{k}: "{v}"' if not str(v).startswith('[') else f"{k}: {v}"
        if re.search(rf"^{re.escape(k)}:", corpo_fm, re.M):
            corpo_fm = re.sub(rf"^{re.escape(k)}:.*$", linha, corpo_fm, count=1, flags=re.M)
        else:
            corpo_fm += f"\n{linha}"
    return m.group(1) + corpo_fm + m.group(3) + texto[m.end():]


def frontmatter_sem_linha_vazia(txt: str) -> str:
    """Tira linhas em branco de dentro do frontmatter.

    Um placeholder que renderiza vazio (bloco de campos herdados, localizações
    extras) deixaria uma linha solta no meio do YAML. Só o frontmatter é tocado —
    o corpo depende das linhas em branco para separar os blocos Markdown.
    """
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", txt, re.DOTALL)
    if not m:
        return txt
    limpo = "\n".join(l for l in m.group(2).split("\n") if l.strip())
    return m.group(1) + limpo + m.group(3) + txt[m.end():]


def planejar_movimentos(origem: Path, md_principal: Path, base_novo: str,
                        formato: str = "") -> list[tuple[Path, str]]:
    """Cede [(arquivo de origem, nome no destino)] para a pasta inteira.

    `formato == "legado-plano"` significa que a pasta de origem é a pasta do
    ASSUNTO, e não a do aprofundamento: ali convivem arquivos alheios (outros
    aprofundamentos, anotações), que não podem ser arrastados junto. Nos demais
    formatos a pasta é do aprofundamento e tudo que está nela pertence a ele.
    """
    movimentos = []
    for p in sorted(origem.iterdir()):
        if p.is_dir():
            continue
        nome = p.name
        if p == md_principal:
            novo = f"{base_novo}.md"
        elif nome.startswith(PREFIXOS_RENOMEAR):
            prefixo = next(x for x in PREFIXOS_RENOMEAR if nome.startswith(x))
            novo = f"{prefixo}{base_novo}{p.suffix}"
        elif nome in ACOMPANHAM:
            novo = nome
        elif formato == "legado-plano":
            continue        # arquivo alheio ao aprofundamento: não mexe
        else:
            novo = nome
        movimentos.append((p, novo))
    return movimentos


def mapa_de_links(movimentos, aprof_id: str) -> dict:
    """'trecho antigo' -> 'trecho novo' para os wikilinks de UM aprofundamento.

    Duas granularidades, porque o vault usa as duas:
      - path relativo a partir de `assuntos/`, sem extensão — como os índices de
        matéria escrevem;
      - stem solto entre `[[ ]]` — como o Obsidian resolve por nome de arquivo.

    Omitir qualquer uma delas deixa link quebrado: o cabeçalho de
    `consolidar_mapas_comuns.py` registra que foi exatamente esse o defeito de
    uma migração anterior.
    """
    mapa = {}
    for p_antigo, nome_novo in movimentos:
        p_antigo = Path(p_antigo)
        stem_antigo, stem_novo = p_antigo.stem, Path(nome_novo).stem
        partes = p_antigo.parts
        if "assuntos" in partes:
            i = len(partes) - 1 - partes[::-1].index("assuntos")
            rel_antigo = "/".join(partes[i:-1] + (stem_antigo,))
            rel_novo = "/".join(partes[i:i + 2] + (aprof_id, stem_novo))
            for fim in FINAIS_WIKILINK:
                mapa[rel_antigo + fim] = rel_novo + fim
        if stem_antigo != stem_novo:
            for fim in FINAIS_WIKILINK:
                mapa["[[" + stem_antigo + fim] = "[[" + stem_novo + fim
    return mapa


def reescrever_referencias(raiz: Path, mapa: dict, aplicar: bool) -> list[dict]:
    """Atualiza wikilinks que apontam para os paths/nomes antigos.

    Os índices de matéria (00-INDICE-*.md) vivem FORA de assuntos/ e referenciam
    cada assunto pelo path completo — sem esta etapa, a renomeação deixa o vault
    cheio de link quebrado.

    `mapa` leva 'trecho antigo' -> 'trecho novo', aplicado do mais longo para o
    mais curto (para o path completo casar antes do nome solto).
    """
    tocados = []
    chaves = sorted(mapa, key=len, reverse=True)
    for md in sorted(Path(raiz).rglob("*.md")):
        try:
            txt = md.read_text(encoding="utf-8")
        except Exception:
            continue
        novo, trocas = txt, 0
        for antigo in chaves:
            if antigo in novo:
                trocas += novo.count(antigo)
                novo = novo.replace(antigo, mapa[antigo])
        if trocas:
            tocados.append({"arquivo": str(md), "trocas": trocas})
            if aplicar:
                md.write_text(novo, encoding="utf-8")
    return tocados


def reescrever_wikilinks_flashcards(texto: str, base_novo: str) -> str:
    """Aponta `[[flashcards-...]]` do corpo para o nome-base novo.

    Vive aqui e não em `reescrever_referencias` porque é o link que o próprio
    arquivo movido faz para o seu par — não depende do mapa global.
    """
    return re.sub(r"\[\[flashcards-[^\]|]*?(\|[^\]]*)?\]\]",
                  lambda m: f"[[flashcards-{base_novo}{m.group(1) or ''}]]", texto)
