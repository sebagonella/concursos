#!/usr/bin/env python3
"""
CÓPIA SINCRONIZADA — a fonte de verdade é
    skills/concurso-aprofunda/scripts/aprofundamento_id.py

As duas skills são instaladas de forma independente, então a concurso-publica
não pode importar da concurso-aprofunda: esta cópia existe para que o site
consiga LER a estrutura de pastas que a outra skill ESCREVE.

Não edite este arquivo. Edite o original e copie por cima; há teste de smoke
nas duas skills que falha se as cópias divergirem.

aprofundamento_id.py — convenção de nomes de aprofundamento (fonte de verdade).

Um assunto pode ter VÁRIOS aprofundamentos (níveis e fontes diferentes). Cada um
vive na sua própria pasta, sob a pasta do assunto:

    .../03-APROFUNDAMENTO/{slug-materia}/assuntos/{slug-assunto}/
        {nivel}--{fonte1}[+{fonte2}...]/
            {slug-assunto}--{nivel}--{fonte1}[+...]--{CONCURSO}.md
            flashcards-{slug-assunto}--{nivel}--{fonte1}[+...]--{CONCURSO}.md/.csv
            cards.json
            _fonte-notebooklm.md

Princípio: **cada componente existe porque diferencia alguma coisa.**
  - {nivel}    = padrao | detalhado ....... diferencia profundidade
  - {fonteN}   = autor ou norma ........... diferencia origem
  - {CONCURSO} = só no nome do ARQUIVO .... diferencia contexto

O que NÃO entra, por não diferenciar nada:
  - contador de fontes ("2f"): derivável contando os separadores '+';
  - índice posicional ("f1-", "f2-"): a ordem já está na sequência.

Por que o concurso aparece no arquivo e não na pasta: a pasta já vive dentro do
concurso (o path resolve), mas o Obsidian resolve wikilinks pelo NOME do arquivo
— e dois concursos que usem o mesmo livro para o mesmo assunto gerariam
homônimos. Vai no FIM porque o discriminador que se procura é o assunto; o
concurso é desempate.

Por que a fonte aparece mesmo quando há só uma: estabilidade. Omiti-la agora
obrigaria a RENOMEAR o aprofundamento existente quando surgisse uma segunda
fonte — e renomear quebra wikilink e progresso do usuário.

Este módulo é compartilhado — a skill concurso-publica também o usa para LER a
estrutura. Alterar aqui muda as duas skills.
"""
import re
import unicodedata

NIVEIS = ("padrao", "detalhado")
SEP_FONTES = "+"

# ordem importa: o mais específico primeiro (Lei Complementar antes de Lei)
_REGRAS_NORMA = [
    (r"\blei\s+complementar\s+n?[º°o]?\s*([\d.]+)", "lc-{}"),
    (r"\blei\s+distrital\s+n?[º°o]?\s*([\d.]+)", "leidf-{}"),
    (r"\bmedida\s+provis[oó]ria\s+n?[º°o]?\s*([\d.]+)", "mp-{}"),
    (r"\bemenda\s+constitucional\s+n?[º°o]?\s*([\d.]+)", "ec-{}"),
    (r"\bres(?:olu[cç][aã]o)?\.?\s+conjunta\s+([A-Za-z/]+)\s+n?[º°o]?\s*([\d.]+)", "res-conj-{}-{}"),
    (r"\bres(?:olu[cç][aã]o)?\.?\s+([A-Za-z]+)\s+n?[º°o]?\s*([\d.]+)", "res-{}-{}"),
    (r"\bres(?:olu[cç][aã]o)?\.?\s+n?[º°o]?\s*([\d.]+)", "res-{}"),
    (r"\binstru[cç][aã]o\s+normativa\s+n?[º°o]?\s*([\d.]+)", "in-{}"),
    (r"\bportaria\s+n?[º°o]?\s*([\d.]+)", "port-{}"),
    (r"\bdecreto[- ]lei\s+n?[º°o]?\s*([\d.]+)", "dl-{}"),
    (r"\bdecreto\s+n?[º°o]?\s*([\d.]+)", "dec-{}"),
    (r"\blei\s+n?[º°o]?\s*([\d.]+)", "lei-{}"),
    (r"\bs[uú]mula\s+n?[º°o]?\s*([\d.]+)", "sum-{}"),
    (r"\bADO\s+n?[º°o]?\s*([\d.]+)", "stf-ado-{}"),
]

# parênteses que não identificam autor (ano, edição, sigla de lei já tratada)
_PAREN_IGNORAR = re.compile(r"^[\d\s.–—/-]+$")

# tokens que nunca servem como identificador de fonte: ano, edição, ordinal
_TOKEN_RUIM = re.compile(r"^(\d+|\d+ed|ed\d+|vol\d+|tomo\d+|[ivxlc]+)$")


def slug(texto: str) -> str:
    """Normaliza para minúsculas sem acento, separado por hífen."""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto


def _slug_norma(texto: str) -> str | None:
    """Se o texto contiver uma norma reconhecível, devolve seu identificador curto."""
    for padrao, molde in _REGRAS_NORMA:
        m = re.search(padrao, texto, flags=re.IGNORECASE)
        if m:
            grupos = [slug(g).replace("-", "") if g.replace(".", "").isdigit()
                      else slug(g) for g in m.groups()]
            return slug(molde.format(*grupos))
    return None


def slug_fonte(nome: str) -> str:
    """Deriva o identificador curto de UMA fonte.

    Ordem de tentativa:
      1. norma explícita no texto        -> "Lei nº 8.742/1993"      -> lei-8742
      2. norma dentro de parênteses      -> "PRSAC do BB (Res. CMN 4.945/2021)" -> res-cmn-4945
      3. nome entre parênteses no fim    -> "A Gramática ... (Pestana)"          -> pestana
      4. último token significativo      -> "Conhecimentos Bancarios.pdf"        -> bancarios

    Quando a derivação automática não serve, passe o slug explicitamente
    (--fontes-slug nos scripts) — nunca deixe o nome errado entrar no path.
    """
    nome = str(nome).strip()
    if not nome:
        return "fonte"

    ident = _slug_norma(nome)
    if ident:
        return ident

    m = re.search(r"\(([^)]+)\)\s*$", nome)
    if m:
        dentro = m.group(1).strip()
        if not _PAREN_IGNORAR.match(dentro):
            ident = _slug_norma(dentro)
            if ident:
                return ident
            toks = _tokens_uteis(dentro)
            if toks:
                return toks[-1]
        # parêntese só com ano/edição: descarta e segue com o nome de fora
        nome = nome[: m.start()].strip()

    base = re.sub(r"\.(pdf|epub|txt|md|docx?)$", "", nome, flags=re.IGNORECASE)
    toks = _tokens_uteis(base)
    return toks[-1] if toks else (slug(base) or "fonte")


def _tokens_uteis(texto: str) -> list[str]:
    """Tokens que podem servir de identificador: descarta curtos, anos e edições."""
    return [t for t in slug(texto).split("-")
            if len(t) > 2 and not _TOKEN_RUIM.match(t)]


def slug_suspeito(s: str) -> bool:
    """True quando o slug derivado provavelmente não identifica a fonte.

    Serve para os scripts avisarem e pedirem --fontes-slug explícito, em vez de
    gravar um path ruim no vault (ex.: 'brasil' para o Código de Ética do BB)."""
    return (not s or s == "fonte" or len(s) < 3 or bool(_TOKEN_RUIM.match(s)))


def id_aprofundamento(fontes, nivel: str, fontes_slug=None) -> str:
    """Monta o identificador da PASTA: {nivel}--{fonte1}[+{fonte2}...]

    fontes      : lista de nomes de fonte (a ordem é preservada)
    nivel       : padrao | detalhado
    fontes_slug : lista opcional de slugs já resolvidos, sobrepõe a derivação
    """
    if nivel not in NIVEIS:
        raise ValueError(f"nível inválido: {nivel!r} (esperado: {' | '.join(NIVEIS)})")
    nomes = [f for f in (fontes or []) if str(f).strip()]
    if fontes_slug:
        slugs = [slug(s) for s in fontes_slug if str(s).strip()]
    else:
        slugs = [slug_fonte(f) for f in nomes]
    if not slugs:
        slugs = ["fonte"]
    return f"{nivel}--" + SEP_FONTES.join(slugs)


def nome_base(slug_assunto: str, aprof_id: str, concurso: str = "") -> str:
    """Nome-base dos arquivos dentro da pasta do aprofundamento.

    Inclui o concurso porque o Obsidian resolve wikilink por nome de arquivo:
    sem ele, dois concursos com o mesmo livro produziriam homônimos.
    """
    base = f"{slug_assunto}--{aprof_id}"
    return f"{base}--{concurso}" if concurso else base


_RE_ID = re.compile(r"^(?P<nivel>padrao|detalhado)--(?P<fontes>[a-z0-9][a-z0-9+-]*)$")

# formato 0.3.x: {nivel}--{N}f--f1-{a}[--f2-{b}] — lido para não quebrar vault não migrado
_RE_ID_030 = re.compile(r"^(?P<nivel>padrao|detalhado)--\d+f--(?P<fontes>f1-.+)$")


def parse_id(nome_pasta: str):
    """Lê o identificador de uma pasta de aprofundamento.

    Devolve {"nivel", "n_fontes", "fontes": [slug, ...]} ou None se não casar.
    Usado pela concurso-publica para montar o seletor de versões no site.
    """
    nome_pasta = str(nome_pasta)
    m30 = _RE_ID_030.match(nome_pasta)
    if m30:                                   # formato anterior, normalizado na leitura
        pares = []
        for parte in m30.group("fontes").split("--"):
            mf = re.match(r"^f(\d+)-(.+)$", parte)
            if not mf:
                return None
            pares.append((int(mf.group(1)), mf.group(2)))
        pares.sort()
        return {"nivel": m30.group("nivel"), "n_fontes": len(pares),
                "fontes": [f for _, f in pares], "formato": "0.3"}
    m = _RE_ID.match(nome_pasta)
    if not m:
        return None
    fontes = [f for f in m.group("fontes").split(SEP_FONTES) if f]
    if not fontes:
        return None
    return {
        "nivel": m.group("nivel"),
        "n_fontes": len(fontes),
        "fontes": fontes,
        "formato": "atual",
    }


def eh_pasta_aprofundamento(nome_pasta: str) -> bool:
    return parse_id(nome_pasta) is not None


def rotulo(aprof_id: str) -> str:
    """Rótulo legível para exibir no site/índice: 'Detalhado — pestana'."""
    info = parse_id(aprof_id)
    if not info:
        return aprof_id
    nivel = "Detalhado" if info["nivel"] == "detalhado" else "Padrão"
    return f"{nivel} — {' + '.join(info['fontes'])}"
