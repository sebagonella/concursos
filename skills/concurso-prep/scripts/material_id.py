#!/usr/bin/env python3
"""
material_id.py — FONTE DE VERDADE da identidade de um material. (v1.0.0)

A regra vive aqui e só aqui. Não reimplemente em outro script: a duplicação da
convenção de aprofundamento já custou caro ao projeto, e a lição está registrada
em `aprofundamento_id.py` e `materia_id.py`.

## O problema que este módulo resolve

Uma obra era descrita em dois lugares que nunca se falavam: o catálogo
(`04-MATERIAIS/livros-recomendados.md`) e o `### Material recomendado` de cada
tópico do mapa. A auditoria de 03/08/2026 mediu o estrago nos dois concursos do
vault:

    - 473 itens de material nos mapas, contra 62 nos catálogos;
    - dos 45 itens canônicos do BB, 7 são citados por algum mapa (15,6%);
      dos 17 do SEDES, 1 (5,9%) — e nenhum por um bloco `### Material recomendado`;
    - Fernando Pestana aparece com 4 grafias e 3 editoras CONTRADITÓRIAS
      (Método, Grupo Gen/Método, Elsevier); Edgar Abreu com 3;
    - 28 itens citam livro SEM autor identificado;
    - 31 prefixos distintos para 473 itens;
    - 2 dos 473 itens linkam para algo efetivamente baixado.

A causa não é desleixo de quem escreveu: é que **não existia um lugar onde a obra
fosse descrita uma vez**. Este módulo cria esse lugar e a chave que aponta para
ele.

## A convenção

O catálogo tem uma entrada por obra, com um **block id do Obsidian** no fim:

    ### Gramática para Concursos

    - **Autor:** Marcelo Rosenthal
    - **Editora:** Elsevier · 3ª ed., 2019
    - **ISBN:** 978-85-352-0000-0
    - **Cobre:** lingua-portuguesa
    - **Onde obter:** editora · biblioteca

    ^mat-rosenthal-gramatica

E o tópico do mapa **aponta**, em vez de redigitar:

    - Livro: [[livros-recomendados#^mat-rosenthal-gramatica|Rosenthal — Gramática]] — cap. 4

Por que block id (`^id`) e não `{#id}`: `{#id}` é sintaxe de pandoc/kramdown, que
o Obsidian renderiza como texto literal dentro do heading — o link não resolveria
no vault, que é onde o material é usado. O block id é nativo, sobrevive à edição
do título e já resolve no site sem tocar no `md2html`: `slug_ancora("^mat-x")`
devolve `mat-x`, então basta a página do catálogo emitir esse `id`.

O rótulo depois do `|` é para leitura humana e **não** participa da identidade —
pode ser reescrito à vontade sem quebrar o vínculo.

## Id proposto, id declarado

`propor_id()` é PROPOSTA, não decisão — mesma regra do `materia_id.py`. Uma vez
gravado no catálogo, o id **manda**, e a resolução é sempre por âncora, nunca por
re-derivação do título. Isso importa porque a derivação é instável por natureza:
"Morettin & Bussab" e "Bussab & Morettin" são a mesma obra com o primeiro autor
trocado, e derivar do primeiro sobrenome daria dois ids para um livro só.

Casamento de texto legado contra o catálogo é **exato ou nada**. Não há
similaridade aqui: o repo já decidiu duas vezes que não se infere vínculo por
semelhança (mapa↔assunto casa em ~18% dos tópicos), e um falso positivo aqui
manda o estudante ao livro errado.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# --------------------------------------------------------------------------- #
# normalização
# --------------------------------------------------------------------------- #
VAZIAS = {
    "de", "do", "da", "dos", "das", "e", "em", "no", "na", "nos", "nas",
    "para", "a", "o", "as", "os", "ao", "aos", "com", "sobre", "entre", "por",
    "um", "uma", "the", "of", "and", "for", "to", "in", "on",
}

# Partículas que não são sobrenome. "Wes McKinney" -> mckinney; "Aldaíza Sposati"
# -> sposati; "Maria Berenice Dias" -> dias; "C. J. Date" -> date.
PARTICULAS = {"de", "da", "do", "dos", "das", "e", "van", "von", "del", "della",
              "di", "la", "le", "el", "bin", "ibn", "junior", "jr", "filho",
              "neto", "sobrinho", "orgs", "org", "et", "al"}

# Palavras que aparecem em quase todo título de concurso e não distinguem obra
# nenhuma. Sem isso, `mat-pestana-gramatica-para-concursos` e
# `mat-pestana-gramatica-para-concursos-publicos` seriam ids diferentes para o
# mesmo livro — que é exatamente uma das 4 grafias medidas no vault.
RUIDO_TITULO = {"concurso", "concursos", "publico", "publicos", "para",
                "completo", "completa", "edicao", "vol", "volume"}

TOKENS_NO_ID = 3   # tokens do título no id — o bastante para distinguir, curto o bastante para digitar


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, sem pontuação, espaços colapsados."""
    t = _sem_acento(texto).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def sobrenome(autor: str) -> str:
    """O sobrenome do PRIMEIRO autor, em slug.

    Mesma escolha do slug de fonte no `aprofundamento_id.py`: sobrenome de autor
    (`pestana`, `kotler`) é o que as pessoas usam para se referir à obra.

    Corta em `&`, `;` e ` e ` porque obra com vários autores cita todos, e o id
    fica ilegível com quatro sobrenomes. `Cormen, Leiserson, Rivest & Stein`
    vira `cormen`.
    """
    if not autor:
        return ""
    primeiro = re.split(r"\s*[&;/]\s*|\s+\be\b\s+|\s*,\s*(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])",
                        autor.strip())[0]
    tokens = [t for t in normalizar(primeiro).split()
              if t and t not in PARTICULAS and len(t) > 1]
    return tokens[-1] if tokens else ""


def tokens_titulo(titulo: str) -> list[str]:
    """Tokens do título que efetivamente distinguem uma obra de outra."""
    return [t for t in normalizar(titulo).split()
            if t and t not in VAZIAS and t not in RUIDO_TITULO]


def propor_id(titulo: str, autor: str = "") -> str:
    """PROPOSTA de id para uma obra. Determinística e falível por desenho.

    Formato: `mat-{sobrenome}-{titulo curto}`. Sem autor, cai em `mat-{titulo}` —
    o que é honesto: são os 28 casos do vault em que não se sabe quem escreveu, e
    o id não deve fingir que sabe.

    Nunca use isto para RESOLVER um vínculo; use para propor um id novo. Resolver
    é `casar_exato()`, contra as âncoras já declaradas.
    """
    partes = ["mat"]
    s = sobrenome(autor)
    if s:
        partes.append(s)
    t = tokens_titulo(titulo)[:TOKENS_NO_ID]
    if t:
        partes.append("-".join(t))
    elif not s:
        return ""
    return "-".join(partes)


def chave_obra(titulo: str, autor: str = "") -> str:
    """Chave de deduplicação: título normalizado + sobrenome.

    Deliberadamente NÃO inclui editora: as três editoras contraditórias do
    Pestana e as três do Edgar Abreu são justamente o dado errado que se quer
    consolidar, não um eixo de diferenciação.
    """
    return f"{' '.join(tokens_titulo(titulo))}|{sobrenome(autor)}"


# --------------------------------------------------------------------------- #
# prefixos dos itens
# --------------------------------------------------------------------------- #
# Conjunto canônico. O vault real tem 31 prefixos distintos para 473 itens — 7
# rótulos concorrentes só para "norma" (`Norma-fonte`, `Norma`, `Lei fonte`,
# `Lei`, `Leis`, `Decreto`, `Fonte primária`) e 27 itens sem prefixo nenhum.
# O mapa de sinônimos existe para LER o legado; a escrita nova usa só as chaves.
PREFIXOS = {
    "livro":    ("Livro", ("livro", "livro/ebook", "livro (didatico)", "livro/lei",
                           "obra", "referencia conceitual")),
    "norma":    ("Norma", ("norma", "norma-fonte", "lei", "lei fonte", "leis",
                           "decreto", "resolucao", "fonte primaria",
                           "norma/jurisprudencia")),
    "questoes": ("Questões", ("questoes", "banco de questoes")),
    "video":    ("YouTube", ("youtube", "video", "canal", "playlist")),
    "documento": ("Documento", ("documento", "documento oficial", "documentacao",
                                "documentacao oficial", "orientacoes tecnicas",
                                "cartilha", "manual")),
}

# As chaves são guardadas JÁ normalizadas: `normalizar()` troca o hífen por
# espaço, então `"norma-fonte"` só casa se o sinônimo passar pela mesma função.
_SINONIMO = {}
for _chave, (_rotulo, _sins) in PREFIXOS.items():
    for _s in _sins:
        _SINONIMO[normalizar(_s)] = _chave


def tipo_do_prefixo(prefixo: str) -> tuple[str, bool]:
    """(tipo canônico, o prefixo já estava na forma canônica?).

    Prefixo desconhecido devolve `("outro", False)` — nunca vira palpite e nunca
    some. É a mesma regra do rótulo de H3 fora do template: publica-se com o
    texto do vault E avisa-se. Dos 473 itens, ~40 caem aqui, e sumir com eles
    seria repetir o defeito que apagou 50 blocos dos mapas.
    """
    if not prefixo:
        return "outro", False
    # O parêntese de qualificação sai ANTES de normalizar: `normalizar()` já
    # apaga os parênteses, e depois dele "Norma-fonte (gratuita, oficial)" é
    # indistinguível de um rótulo de quatro palavras. Eram 40 itens de norma
    # caindo em `outro` por causa da ordem das duas linhas.
    bruto = normalizar(re.sub(r"\s*\([^)]*\)\s*", " ", prefixo))
    chave = _SINONIMO.get(bruto)
    if not chave:
        return "outro", False
    return chave, prefixo.strip() == PREFIXOS[chave][0]


# --------------------------------------------------------------------------- #
# itens de material (o `### Material recomendado` do mapa)
# --------------------------------------------------------------------------- #
_ITEM = re.compile(r"^\s*[-*]\s+(.*)$")
_PREFIXO = re.compile(r"^\s*([^:*_\[\]]{1,40}?)\s*:\s+(.*)$")
_WIKILINK_ANCORA = re.compile(r"\[\[([^\]|#]+?)#\^([A-Za-z0-9-]+)(?:\|([^\]]*))?\]\]")
# `*Título*` em qualquer das três ordens observadas no vault. O que vem depois
# do título é tratado à parte por `_autor_editora()`, porque a cauda varia muito
# mais do que o título: `(Editora), cap. 3`, `, Autor, Ed. X`, `— Autor (Ed.)`.
_TITULO_MARCADO = re.compile(r"\*([^*]+)\*")
# `Autor — *Título*. Editora.`, a ordem INVERTIDA das listas canônicas
_AUTOR_TITULO = re.compile(r"^([^*(]+?)\s*[—–]\s*\*([^*]+)\*\.?\s*(.*)$")
# cauda que não é autor nem editora: ponteiro de leitura, comentário
_CAUDA = re.compile(
    r"\s*[—–,;(]?\s*\b(cap|caps|cap\.|capítulo|capítulos|parte|partes|p|pp|pág|págs|"
    r"seção|secao|vol|volume|unidade|módulo|modulo)\b.*$", re.I)
_MARCA_EDITORA = re.compile(r"\b(?:ed|editora|edit)\.?\s+(.+)$", re.I)


def itens_do_bloco(markdown: str) -> list[dict]:
    """Os itens de um bloco `### Material recomendado`, um dict por item.

    Junta linha de continuação ao item anterior. Três itens do vault quebram em
    várias linhas (os blocos 📕/📗/📙 de primeiros socorros) e um parser
    linha-a-linha os trunca no meio.
    """
    itens: list[dict] = []
    for linha in (markdown or "").splitlines():
        m = _ITEM.match(linha)
        if m:
            itens.append(_parsear_texto(m.group(1).strip()))
        elif itens and linha.strip() and linha.startswith((" ", "\t")):
            itens[-1]["texto"] = f'{itens[-1]["texto"]} {linha.strip()}'
    return itens


def parsear_item(linha: str) -> dict:
    """Um item de material, a partir da linha inteira (com ou sem o `- `)."""
    m = _ITEM.match(linha)
    return _parsear_texto((m.group(1) if m else linha).strip())


def _parsear_texto(texto: str) -> dict:
    """Decompõe o item. Campo que não dá para determinar volta vazio, nunca
    inventado — 'sem autor' é um dado, e é o dado que se quer poder contar."""
    item = {"texto": texto, "prefixo": "", "tipo": "outro", "canonico": False,
            "ancora": "", "alvo": "", "rotulo": "", "titulo": "", "autor": "",
            "editora": "", "resto": ""}

    corpo = texto
    m = _PREFIXO.match(texto)
    if m:
        item["prefixo"] = m.group(1).strip()
        corpo = m.group(2).strip()
        item["tipo"], item["canonico"] = tipo_do_prefixo(item["prefixo"])
    item["resto"] = corpo

    # já aponta para o catálogo? então a identidade está resolvida e é ela que vale
    w = _WIKILINK_ANCORA.search(corpo)
    if w:
        item["alvo"] = w.group(1).strip()
        item["ancora"] = w.group(2).strip()
        item["rotulo"] = (w.group(3) or "").strip()
        if not item["prefixo"]:
            item["tipo"], item["canonico"] = "livro", False
        return item

    # ordem invertida primeiro: `Autor — *Título*. Editora.` (listas canônicas)
    a = _AUTOR_TITULO.match(corpo)
    if a:
        item["autor"] = a.group(1).strip(" .,")
        item["titulo"] = a.group(2).strip()
        item["editora"] = _editora_de_cauda(a.group(3))
        return item

    t = _TITULO_MARCADO.search(corpo)
    if t:
        item["titulo"] = t.group(1).strip()
        antes = corpo[:t.start()].strip()
        # Ordem invertida que o `_AUTOR_TITULO` não pegou porque o autor tem
        # parêntese: `Cormen, Leiserson, Rivest & Stein (CLRS) — *Algoritmos*.
        # Elsevier.` Sem esta saída o autor sumia e "Elsevier" era lido COMO
        # autor — pior que perder o dado, é gravar o dado errado.
        if antes and antes[-1] in "—–-":
            item["autor"] = re.sub(r"\s*\([^)]*\)\s*", " ",
                                   antes.rstrip(" —–-")).strip(" .,")
            item["editora"] = _editora_de_cauda(corpo[t.end():])
        else:
            item["autor"], item["editora"] = _autor_editora(corpo[t.end():])
        return item

    # sem título marcado: o item inteiro é o título. É o caso de
    # `Livro: Matemática básica para concursos` — os itens sem autor nenhum, que
    # precisam CONTINUAR VISÍVEIS como pendência em vez de sumir do catálogo.
    item["titulo"] = _CAUDA.sub("", corpo).strip(" .,")
    return item


def _autor_editora(cauda: str) -> tuple[str, str]:
    """Autor e editora a partir do que vem DEPOIS do título.

    A cauda é a parte que mais varia no vault — as três formas medidas são
    `— Autor (Editora)`, `, Autor, Ed. Editora` e `(Editora)` sem autor — e
    ainda pode continuar em ponteiro de leitura (`, cap. 3`). Tratar isso com um
    regex único fazia o casamento exigir fim de linha, e 27 livros COM autor
    eram contados como sem: pendência inventada é tão ruim quanto pendência
    escondida.
    """
    # O parêntese sai PRIMEIRO. `_CAUDA` casa "capítulo", que também aparece
    # DENTRO do parêntese (`(ou o capítulo de Excel em João Antonio)`); cortando
    # antes, o parêntese ficava sem fecho e o autor saía como `Fabrício Melo (ou o`.
    editora = ""
    par = re.search(r"\(([^)]*)\)", cauda)
    if par:
        editora = par.group(1).strip()
        cauda = (cauda[:par.start()] + " " + cauda[par.end():]).strip()

    cauda = _CAUDA.sub("", cauda).strip().lstrip(" —–-,;:.")
    if not cauda:
        return "", _limpar_editora(editora)

    # A cauda inteira é o mapa dizendo que não sabe ("verificar autor/editora
    # atual"). Sem esta saída, a marca de editora ainda casava e gravava
    # `**Editora:** atual` — dado inventado a partir de uma confissão de lacuna.
    if not _parece_autor(cauda):
        return "", _limpar_editora(editora)

    # O marcador explícito VENCE o parêntese. `Ed. JusPodivm (violência contra a
    # mulher)` tem editora e qualificação, e tomar o parêntese primeiro gravava
    # "violência contra a mulher" no campo Editora do catálogo.
    marca = _MARCA_EDITORA.search(cauda)
    if marca:
        editora = marca.group(1).strip(" .,")
        cauda = cauda[:marca.start()].strip()

    autor = cauda.strip(" .,;—–-")
    if not _parece_autor(autor):
        autor = ""
    return autor, _limpar_editora(editora)


# Texto que ocupa o lugar do autor sem ser autor. `*Raciocínio Lógico para
# Concursos* — verificar autor/editora atual` é o próprio mapa dizendo que NÃO
# sabe quem escreveu: tratar isso como autor produziria a entrada de catálogo
# `**Autor:** verificar autor/`, que é pior do que assumir a pendência.
_NAO_AUTOR = re.compile(
    r"^(ou|e|com|ver|veja|idem|qualquer|verificar|conferir|consultar|coletanea|"
    r"coletânea|material|manual|texto|edicao|edição|apostila|capitulo|capítulo)\b",
    re.I)


def _parece_autor(texto: str) -> bool:
    """Autor começa com MAIÚSCULA — pessoa ou instituição.

    A lista de palavras acima nunca daria conta sozinha: o vault produziu
    `apenas consulta`, `voltada a provas CESGRANRIO`, `foco em CESGRANRIO`,
    `referência de trilha`, `coletâneas de referência` e `de cursinhos
    atualizados para o edital vigente` — todas frases de qualificação que caíram
    no campo do autor. Acrescentar cada uma seria correr atrás do vault.

    O sinal estrutural é o mesmo que separa editora de prosa: nome próprio
    começa em maiúscula (`Fernando Pestana`, `Ministério da Saúde`, `CFESS`),
    qualificação começa em minúscula. Quando erra, erra para pendência — que é
    o lado certo de errar.
    """
    t = (texto or "").strip()
    if not t or _NAO_AUTOR.match(t):
        return False
    letras = [c for c in t if c.isalpha()]
    return bool(letras) and letras[0].isupper()


def _editora_de_cauda(texto: str) -> str:
    """Editora, quando a cauda é SÓ editora — o caso da ordem invertida.

    Nas listas canônicas a forma é `Autor — *Título*. Editora.`, então tudo que
    sobra depois do título é candidato a editora. As três formas medidas no
    catálogo do vault, e o que cada uma tem de resolver:

        `Ed. Método.`                                 -> marcador a remover
        `Ed. JusPodivm (violência contra a mulher).`  -> marcador + qualificação
        `Método (referência consagrada para ...).`    -> só qualificação

    O marcador vence; a qualificação entre parênteses é descartada; sobra o nome.
    """
    t = _CAUDA.sub("", texto or "").strip()
    t = re.sub(r"\s*\([^)]*\)\s*", " ", t).strip(" .,;")
    marca = _MARCA_EDITORA.search(t)
    if marca:
        t = marca.group(1)
    return _limpar_editora(t)


def _limpar_editora(texto: str) -> str:
    """Editora só quando é editora.

    O mesmo parêntese que às vezes traz a editora traz, com a mesma frequência,
    uma qualificação em prosa: `(violência contra a mulher)`, `(rede de saúde
    mental / RAPS)`, `(referência consagrada para bancários CESGRANRIO)`. Dois
    sinais separam um do outro no vault real, e nenhum sozinho basta:

      - nome de editora começa com MAIÚSCULA (`Método`, `Pearson`, `JusPodivm`);
        qualificação começa em minúscula;
      - nome de editora é curto (`A Casa do Concurseiro` já é o extremo);
        qualificação é frase.
    """
    t = (texto or "").strip(" .,")
    if not t or not _parece_autor(t) or len(t) > 60:
        return ""
    if t[0].islower() or len(t.split()) > 4:
        return ""
    return t


# --------------------------------------------------------------------------- #
# o catálogo
# --------------------------------------------------------------------------- #
CAMPOS = ("autor", "editora", "isbn", "cobre", "onde_obter", "pendencia")
_ROTULO_CAMPO = {"autor": "Autor", "editora": "Editora", "isbn": "ISBN",
                 "cobre": "Cobre", "onde_obter": "Onde obter",
                 "pendencia": "⚠️ Pendência"}
_CAMPO_POR_ROTULO = {normalizar(v): k for k, v in _ROTULO_CAMPO.items()}

_H3 = re.compile(r"^###\s+(.*?)\s*$")
_BLOCO_ID = re.compile(r"^\s*\^([A-Za-z0-9-]+)\s*$")
_CAMPO = re.compile(r"^\s*[-*]\s+\*\*(.+?):?\*\*\s*(.*)$")


def parsear_catalogo(md: str) -> list[dict]:
    """As entradas de um `livros-recomendados.md`, na ordem do arquivo.

    Entrada sem block id é devolvida com `ancora: ""` — o catálogo legado não
    tem nenhum, e a migração precisa enxergá-las para poder atribuir id.
    """
    entradas: list[dict] = []
    atual: dict | None = None
    for linha in (md or "").splitlines():
        h = _H3.match(linha)
        if h:
            atual = {"titulo": h.group(1).strip(), "ancora": "", "materia": "",
                     **{c: "" for c in CAMPOS}}
            entradas.append(atual)
            continue
        if atual is None:
            continue
        b = _BLOCO_ID.match(linha)
        if b:
            atual["ancora"] = b.group(1)
            continue
        c = _CAMPO.match(linha)
        if c:
            campo = _CAMPO_POR_ROTULO.get(normalizar(c.group(1)))
            if campo:
                atual[campo] = c.group(2).strip()
    # H3 sem NENHUM campo e sem âncora não é entrada: é subseção temática, que é
    # como o catálogo legado do BB organiza a matéria de TI ("### Machine
    # Learning / IA", "### Big Data"). Contá-las como obra gerava 8 falsos
    # positivos de "entrada sem autor" — e um validador que grita no lugar
    # errado ensina a ignorar o validador.
    return [e for e in entradas
            if e["ancora"] or any(e.get(c) for c in CAMPOS)]


def render_entrada(entrada: dict) -> str:
    """Uma entrada do catálogo em markdown, com o block id no fim.

    Campo vazio é OMITIDO — linha `**ISBN:**` em branco é ruído que parece dado
    faltando por descuido. O que falta e importa aparece em `pendencia`, com o
    que se procurou, para dar para distinguir 'não encontrei' de 'não procurei'.
    """
    linhas = [f'### {entrada["titulo"]}', ""]
    for campo in CAMPOS:
        valor = (entrada.get(campo) or "").strip()
        if valor:
            linhas.append(f'- **{_ROTULO_CAMPO[campo]}:** {valor}')
    linhas.append("")
    if entrada.get("ancora"):
        linhas.append(f'^{entrada["ancora"]}')
    return "\n".join(linhas) + "\n"


def wikilink(entrada: dict, arquivo: str = "livros-recomendados") -> str:
    """O wikilink que o mapa deve escrever para citar esta entrada.

    `arquivo` deve vir com o CAMINHO do escopo
    (`ASSISTENTE-SOCIAL/04-MATERIAIS/livros-recomendados`), não só o nome: há um
    catálogo por escopo, e sete arquivos com o mesmo nome no concurso. Com o nome
    nu, o Obsidian escolhe um deles por proximidade e o site resolvia sempre para
    o primeiro registrado — foram 160 links apontando para âncora que não existia
    naquela página.
    """
    rotulo = entrada["titulo"]
    s = sobrenome(entrada.get("autor", ""))
    if s:
        rotulo = f'{s.capitalize()} — {entrada["titulo"]}'
    return f'[[{arquivo}#^{entrada["ancora"]}|{rotulo}]]'


def casar_exato(item: dict, entradas: list[dict]) -> dict | None:
    """A entrada de catálogo que corresponde a este item — ou None.

    EXATO OU NADA. Casa por âncora (quando o item já aponta) ou por
    `chave_obra`. Sem limiar de similaridade, de propósito: um falso positivo
    aqui manda o estudante ao livro errado, e o repo já decidiu duas vezes que
    não se infere vínculo por semelhança.

    Ambiguidade (duas entradas com a mesma chave) devolve None: é pendência para
    humano, não desempate silencioso.
    """
    if item.get("ancora"):
        achadas = [e for e in entradas if e.get("ancora") == item["ancora"]]
        return achadas[0] if len(achadas) == 1 else None
    if not item.get("titulo"):
        return None
    chave = chave_obra(item["titulo"], item.get("autor", ""))
    achadas = [e for e in entradas
               if chave_obra(e["titulo"], e.get("autor", "")) == chave]
    return achadas[0] if len(achadas) == 1 else None


def ids_unicos(entradas: list[dict]) -> dict[str, str]:
    """Atribui um id a cada entrada sem âncora, desempatando com sufixo.

    Duas obras distintas podem propor o mesmo id (mesmo sobrenome, títulos que
    colidem depois do corte). O desempate é posicional e ESTÁVEL na ordem do
    arquivo — nunca reordena o que já existe.
    """
    usados = {e["ancora"] for e in entradas if e.get("ancora")}
    novos: dict[str, str] = {}
    for i, e in enumerate(entradas):
        if e.get("ancora"):
            continue
        base = propor_id(e["titulo"], e.get("autor", "")) or f"mat-{i + 1}"
        cand, n = base, 2
        while cand in usados:
            cand, n = f"{base}-{n}", n + 1
        usados.add(cand)
        novos[str(i)] = cand
    return novos


def main() -> int:
    ap = argparse.ArgumentParser(description="Convenção de identidade de material")
    ap.add_argument("--propor", nargs="+", metavar=("TITULO", "AUTOR"),
                    help="propõe o id de uma obra")
    ap.add_argument("--parsear-item", metavar="LINHA",
                    help="decompõe um item de `### Material recomendado`")
    ap.add_argument("--catalogo", type=Path,
                    help="lista as entradas de um livros-recomendados.md")
    a = ap.parse_args()

    if a.propor:
        titulo = a.propor[0]
        autor = a.propor[1] if len(a.propor) > 1 else ""
        print(propor_id(titulo, autor))
    elif a.parsear_item:
        print(json.dumps(parsear_item(a.parsear_item), indent=2, ensure_ascii=False))
    elif a.catalogo:
        entradas = parsear_catalogo(a.catalogo.read_text(encoding="utf-8"))
        print(json.dumps(entradas, indent=2, ensure_ascii=False))
    else:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
