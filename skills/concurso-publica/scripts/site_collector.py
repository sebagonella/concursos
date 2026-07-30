#!/usr/bin/env python3
"""
site_collector.py - Subsistema A da skill concurso-publica.

Varre a pasta de um concurso no vault (saída das skills concurso-prep e
concurso-aprofunda) e monta o MODELO do site: um site-model.json descrevendo
matérias, assuntos, mídias disponíveis, flashcards, progresso e documentos
de apoio. O gerador de páginas (site_builder.py) consome esse modelo.

Princípios (do plano aprovado):
  - O vault é a fonte de verdade; o site é derivado regenerável.
  - Site SÓ LEITURA: o progresso é LIDO do vault na geração (checkboxes dos .md),
    nunca editado pelo site.
  - Detecção de mídia por PRESENÇA de arquivo (podcast-*.m4a, video-*.mp4,
    mapa-mental-*.png, report-*.md). Mídia ausente = seção ausente, sem quebrar.
  - Link NotebookLM interativo só se `notebooklm_url:` estiver preenchida no
    frontmatter do _fonte-notebooklm.md do assunto.

Uso:
    python site_collector.py --concurso-dir <vault>/.../CONCURSOS/SEDES_2026 \
        [--out site-model.json] [--json]

Saída (resumo do modelo):
{
  "concurso": "SEDES_2026",
  "meta": {...},                      # do .meta.json se existir
  "cargos": [
    { "nome": "EDAS-ADMINISTRACAO",
      "materias": [
        { "nome": "Língua Portuguesa", "slug": "lingua-portuguesa",
          "docs_apoio": [...],        # 00-COBERTURA, 00-GUIA..., mapa-localizacao
          "assuntos": [
            { "slug": "crase", "titulo": "Crase", "status": "concluido",
              "paginas_livro": "1018–1045",
              "resumo_md": "<caminho>",
              "midias": {"podcast": "...", "video": null, "mapa_mental": "...",
                          "report": null},
              "flashcards": {"obsidian": "...", "anki": "...", "n_cards": 8},
              "notebooklm_url": null,
              "progresso": {"total": 4, "feitos": 1} } ] } ] } ]
}
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aprofundamento_id import (  # noqa: E402
    eh_pasta_aprofundamento, parse_id, rotulo,
)


# --------------------------------------------------------------------------- #
# util
# --------------------------------------------------------------------------- #
def norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def ler_frontmatter(md: Path) -> dict:
    try:
        txt = md.read_text(encoding="utf-8")
    except Exception:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    fm = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha:
                k, _, v = linha.partition(":")
                v = v.strip()
                # remover comentário inline do YAML ("padrao   # padrao | detalhado"),
                # preservando '#' dentro de valores entre aspas (ex.: URLs com fragmento)
                if not v.startswith(('"', "'")):
                    v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
                fm[k.strip()] = v.strip('"').strip("'")
    fm["_corpo"] = txt[m.end():] if m else txt
    return fm


def contar_progresso(corpo: str) -> dict:
    """Conta checkboxes '- [ ]' / '- [x]' no corpo (progresso lido do vault)."""
    feitos = len(re.findall(r"^\s*-\s*\[[xX]\]", corpo, re.MULTILINE))
    abertos = len(re.findall(r"^\s*-\s*\[\s\]", corpo, re.MULTILINE))
    return {"total": feitos + abertos, "feitos": feitos}


def contar_cards(fc_md: Path) -> int:
    """Conta cartões no formato multiline (linhas '??' isoladas) ou singleline (::)."""
    try:
        txt = fc_md.read_text(encoding="utf-8")
    except Exception:
        return 0
    multi = len(re.findall(r"^\?\?\s*$", txt, re.MULTILINE))
    if multi:
        return multi
    # singleline: linhas com '::' fora do frontmatter
    corpo = re.sub(r"^---.*?---\s*\n", "", txt, flags=re.DOTALL)
    return len([l for l in corpo.split("\n") if "::" in l and not l.startswith(">")])


# Catálogo de mídias geráveis (Estúdio do NotebookLM + nativas da skill).
# chave: (prefixos aceitos no nome do arquivo, extensões, ícone, rótulo)
CATALOGO_MIDIAS = {
    "podcast":     (("podcast", "audio", "resumo-audio"), (".m4a", ".mp3", ".wav", ".ogg"), "🎧", "Resumo em áudio"),
    "video":       (("video", "resumo-video"), (".mp4", ".webm", ".mov"), "🎬", "Resumo em vídeo"),
    "slides":      (("slides", "apresentacao"), (".pdf", ".pptx"), "📊", "Apresentação de slides"),
    "mapa_mental": (("mapa-mental", "mapa"), (".png", ".jpg", ".jpeg", ".svg", ".webp"), "🧠", "Mapa mental"),
    "infografico": (("infografico", "infografia"), (".png", ".jpg", ".jpeg", ".svg", ".webp", ".pdf"), "📈", "Infográfico"),
    "report":      (("report", "relatorio"), (".md", ".pdf", ".txt"), "📄", "Relatório"),
    "teste":       (("teste", "quiz"), (".md", ".pdf", ".txt"), "✍️", "Teste"),
    "tabela":      (("tabela", "tabela-dados", "dados"), (".csv", ".md", ".tsv"), "🗂️", "Tabela de dados"),
}

PRIORIDADES = ("alta", "media", "base")


def normalizar_prioridade(valor: str) -> str | None:
    """Aceita 'alta', 'Prioridade alta', 'média', 'media', 'base', 'baixa', 'leitura'."""
    v = norm(valor or "").strip()
    v = re.sub(r"^prioridade\s+", "", v)      # "prioridade alta" -> "alta"
    if v.startswith("alta"):
        return "alta"
    if v.startswith("med"):
        return "media"
    if v.startswith(("base", "baix", "leitura")):
        return "base"
    return None


# "Prioridade alta (...): Crase, Regência, Concordância."  /  "Média: X, Y."
LINHA_PRIORIDADE = re.compile(
    r"^\s*(prioridade\s+alta|alta|m[ée]dia|base(?:/leitura)?|baixa)\b[^:]*:\s*(.+?)\.?\s*$",
    re.IGNORECASE)


def prioridades_do_guia(materia_dir: Path) -> dict[str, str]:
    """Fallback: deriva a prioridade de cada assunto a partir da seção
    'Ordem sugerida' do 00-GUIA-NOTEBOOKLM.md, quando o frontmatter não a traz.
    Retorna {termo_normalizado: prioridade}."""
    mapa: dict[str, str] = {}
    for md in materia_dir.glob("00-GUIA*.md"):
        try:
            txt = md.read_text(encoding="utf-8")
        except Exception:
            continue
        for linha in txt.split("\n"):
            m = LINHA_PRIORIDADE.match(linha.strip())
            if not m:
                continue
            prio = normalizar_prioridade(m.group(1))
            if not prio:
                continue
            for termo in m.group(2).split(","):
                t = norm(termo).strip(" .;")
                if t and len(t) > 2:
                    mapa[t] = prio
    return mapa


def casar_prioridade(titulo: str, slug: str, mapa: dict[str, str]) -> str | None:
    """Casa o assunto com os termos do guia (que costumam ser abreviados:
    'Concordância' para 'Concordância verbal e nominal')."""
    if not mapa:
        return None
    alvo_t, alvo_s = norm(titulo), slug.replace("-", " ")
    for termo, prio in mapa.items():
        if termo in alvo_t or termo in alvo_s or alvo_t.startswith(termo):
            return prio
    # tentativa por palavra significativa
    for termo, prio in mapa.items():
        palavras = [p for p in termo.split() if len(p) > 4]
        if palavras and all(p in alvo_t for p in palavras):
            return prio
    return None


# Documento "como a banca cobra esta matéria", exibido antes dos assuntos
DOC_BANCA = re.compile(
    r"^(como[-_ ].*(cobra|banca)|.*banca.*cobra|analise[-_ ]?banca|00-BANCA)",
    re.IGNORECASE)


def achar_doc_banca(materia_dir: Path) -> str | None:
    for md in sorted(materia_dir.glob("*.md")):
        if DOC_BANCA.match(md.stem):
            return md.name
    return None


def extrair_paginas(fm: dict) -> str | None:
    loc = fm.get("localizacao_livro", "")
    m = re.search(r"p[áa]gs?\.\s*([^\"]+)$", loc)
    return m.group(1).strip() if m else None


def detectar_midias(subdir: Path, slug: str) -> dict:
    """Detecta cada tipo de mídia por PRESENÇA de arquivo, tolerando variações
    de nome (prefixo-slug.ext, prefixo-qualquercoisa.ext)."""
    achadas = {}
    for chave, (prefixos, exts, _ic, _rot) in CATALOGO_MIDIAS.items():
        encontrado = None
        for pref in prefixos:
            for ext in exts:
                p = subdir / f"{pref}-{slug}{ext}"
                if p.exists():
                    encontrado = p.name
                    break
            if encontrado:
                break
        if not encontrado:
            for pref in prefixos:
                for p in sorted(subdir.glob(f"{pref}-*")):
                    if p.suffix.lower() in exts and not p.name.startswith("flashcards-"):
                        encontrado = p.name
                        break
                if encontrado:
                    break
        achadas[chave] = encontrado
    return achadas


# --------------------------------------------------------------------------- #
# coleta de um assunto
# --------------------------------------------------------------------------- #
def _arquivo_principal(pasta: Path) -> Path | None:
    """Acha o .md principal de uma pasta de aprofundamento (ou de assunto legado).
    Aceita '{pasta}.md' (legado) e '{assunto}--{aprof}.md' (novo)."""
    exato = pasta / f"{pasta.name}.md"
    if exato.exists():
        return exato
    candidatos = [p for p in sorted(pasta.glob("*.md"))
                  if not p.name.startswith(("flashcards-", "_", "00-"))
                  and not p.name.startswith(("report-", "teste-", "tabela-"))]
    return candidatos[0] if candidatos else None


def coletar_aprofundamento(subdir: Path, slug_assunto: str,
                           mapa_prio: dict | None = None) -> dict | None:
    principal = _arquivo_principal(subdir)
    if principal is None:
        return None
    slug = principal.stem
    fm = ler_frontmatter(principal)
    corpo = fm.get("_corpo", "")

    midias = detectar_midias(subdir, slug)

    fc_md = subdir / f"flashcards-{slug}.md"
    fc_csv = subdir / f"flashcards-{slug}.csv"
    # tolerância: se o nome exato não existir, aceitar qualquer flashcards-*.{md,csv}
    # (na prática o "assunto" usado na geração pode ser mais curto que o slug da pasta)
    if not fc_md.exists():
        candidatos = sorted(subdir.glob("flashcards-*.md"))
        if candidatos:
            fc_md = candidatos[0]
    if not fc_csv.exists():
        candidatos = sorted(subdir.glob("flashcards-*.csv"))
        if candidatos:
            fc_csv = candidatos[0]
    flashcards = {
        "obsidian": fc_md.name if fc_md.exists() else None,
        "anki": fc_csv.name if fc_csv.exists() else None,
        "n_cards": contar_cards(fc_md) if fc_md.exists() else 0,
    }

    # link NotebookLM interativo (Decisão 5): só se preenchido no pack
    nb_url = None
    pack = subdir / "_fonte-notebooklm.md"
    if pack.exists():
        nb_fm = ler_frontmatter(pack)
        url = nb_fm.get("notebooklm_url", "").strip()
        if url and url.lower() not in ("", "null", "~"):
            nb_url = url

    # prioridade: frontmatter primeiro; senão deriva do guia da matéria
    prioridade = normalizar_prioridade(fm.get("prioridade", ""))
    if not prioridade:
        prioridade = casar_prioridade(fm.get("title", slug), slug, mapa_prio or {})

    # o nome da pasta é a fonte mais confiável da identidade do aprofundamento:
    # o frontmatter pode faltar (material antigo) ou estar desatualizado
    info_pasta = parse_id(subdir.name)
    aprof_id = (fm.get("aprofundamento") or "").strip()
    if info_pasta:
        aprof_id = subdir.name
        nivel = info_pasta["nivel"]
    else:
        nivel = (fm.get("nivel") or "padrao").strip()

    return {
        "slug": slug,
        "slug_assunto": slug_assunto,
        "aprofundamento": aprof_id,
        "rotulo": rotulo(aprof_id) if info_pasta else (aprof_id or "Original"),
        "nivel": nivel,
        "n_fontes_id": info_pasta["n_fontes"] if info_pasta else None,
        "fontes_id": info_pasta["fontes"] if info_pasta else [],
        "fontes": fm.get("fontes", ""),
        "titulo": fm.get("title", slug_assunto),
        "prioridade": prioridade,
        "status": fm.get("status", "?"),
        "paginas_livro": extrair_paginas(fm),
        "resumo_md": str(principal),
        "midias": midias,
        "flashcards": flashcards,
        "notebooklm_url": nb_url,
        "progresso": contar_progresso(corpo),
        "tem_pack_notebooklm": pack.exists(),
    }




ORDEM_NIVEL = {"detalhado": 0, "padrao": 1}


def uniao_midias(aprofs: list[dict]) -> dict:
    """União das mídias de TODOS os aprofundamentos do assunto.

    O selo no card afirma "existe podcast para este assunto", e isso é verdade se
    QUALQUER aprofundamento tiver o arquivo. Antes o valor era herdado do
    aprofundamento principal e, como `ORDEM_NIVEL` põe `detalhado` na frente, um
    assunto cuja mídia estava no `padrao` aparecia sem mídia nenhuma. Era o caso do
    único assunto do vault com podcast, vídeo e mapa mental: os três estão em
    `padrao--pestana`, e o site anunciava "0 com áudio" na matéria inteira.

    O valor guardado é o nome de arquivo do primeiro aprofundamento que o tem, e
    serve como INDICADOR DE PRESENÇA — quem precisa do caminho real usa
    `aprofundamentos[i]["midias"]`, que é relativo à pasta daquele aprofundamento.
    """
    return {chave: next((a["midias"][chave] for a in aprofs
                         if a.get("midias", {}).get(chave)), None)
            for chave in CATALOGO_MIDIAS}


def uniao_flashcards(aprofs: list[dict], principal: dict) -> dict:
    """Presença de flashcards em qualquer aprofundamento; contagem do principal.

    Mesma armadilha da `uniao_midias`: a presença é do conjunto, senão a matéria
    reporta "0 com flashcards" quando só o nível não-principal os tem. Já `n_cards`
    continua sendo o do principal — somar baralhos de níveis diferentes daria um
    número que não corresponde a nenhum baralho de verdade.
    """
    return {
        "obsidian": next((a["flashcards"]["obsidian"] for a in aprofs
                          if a.get("flashcards", {}).get("obsidian")), None),
        "anki": next((a["flashcards"]["anki"] for a in aprofs
                      if a.get("flashcards", {}).get("anki")), None),
        "n_cards": principal["flashcards"].get("n_cards", 0),
    }


def coletar_assunto(subdir: Path, mapa_prio: dict | None = None) -> dict | None:
    """Coleta UM assunto com TODOS os seus aprofundamentos.

    Layout atual:
      assuntos/<assunto>/<nivel>--<N>f--f1-<fonte>[--f2-...]/<arquivo>.md
    Layouts anteriores, ainda lidos (o site nunca deve quebrar por causa de
    material que o usuário não migrou):
      assuntos/<assunto>/aprofundamentos/<fonte--nivel>/<arquivo>.md   (0.2.x)
      assuntos/<assunto>/<assunto>.md                                  (legado plano)
    """
    slug_assunto = subdir.name
    aprofs = []

    for sub in sorted(subdir.iterdir()):
        if sub.is_dir() and eh_pasta_aprofundamento(sub.name):
            a = coletar_aprofundamento(sub, slug_assunto, mapa_prio)
            if a:
                aprofs.append(a)

    pasta_aprof = subdir / "aprofundamentos"
    if pasta_aprof.is_dir():
        for sub in sorted(pasta_aprof.iterdir()):
            if sub.is_dir():
                a = coletar_aprofundamento(sub, slug_assunto, mapa_prio)
                if a:
                    aprofs.append(a)

    # legado (ou coexistência): arquivo direto na pasta do assunto
    legado = coletar_aprofundamento(subdir, slug_assunto, mapa_prio)
    if legado:
        # se já há aprofundamentos organizados, o arquivo solto é o material
        # anterior à reorganização — rotula como "original" em vez de descartar
        if not legado.get("aprofundamento"):
            legado["aprofundamento"] = "original" if aprofs else "unico"
        legado["legado"] = True
        aprofs.append(legado)

    if not aprofs:
        return None

    # ordenar: detalhado primeiro, depois padrão; empate pelo id
    aprofs.sort(key=lambda a: (ORDEM_NIVEL.get(a["nivel"], 2), a["aprofundamento"]))

    principal = aprofs[0]
    # dados do assunto: herdados do aprofundamento principal
    return {
        "slug": slug_assunto,
        "titulo": principal["titulo"],
        "prioridade": next((a["prioridade"] for a in aprofs if a.get("prioridade")), None),
        "paginas_livro": principal.get("paginas_livro"),
        "n_aprofundamentos": len(aprofs),
        "niveis": sorted({a["nivel"] for a in aprofs}),
        # fontes distintas entre todos os aprofundamentos deste assunto
        "fontes": sorted({f.strip() for a in aprofs
                          for f in (a.get("fontes") or "").split(",") if f.strip()}),
        "n_fontes": len({f.strip() for a in aprofs
                         for f in (a.get("fontes") or "").split(",") if f.strip()}),
        "aprofundamentos": aprofs,
        # agregados do CONJUNTO de aprofundamentos: presença de mídia e de
        # flashcards não podem vir do principal (ver uniao_midias)
        "midias": uniao_midias(aprofs),
        "flashcards": uniao_flashcards(aprofs, principal),
        # atalhos do principal
        "resumo_md": principal["resumo_md"],
        "notebooklm_url": principal.get("notebooklm_url"),
        "progresso": principal["progresso"],
    }


# --------------------------------------------------------------------------- #
# coleta de uma matéria (pasta com assuntos/)
# --------------------------------------------------------------------------- #
DOCS_APOIO_CONHECIDOS = re.compile(
    r"^(00-COBERTURA|00-GUIA|00-INDICE|COMO-USAR)", re.IGNORECASE)


def coletar_materia(materia_dir: Path) -> dict | None:
    assuntos_dir = materia_dir / "assuntos"
    if not assuntos_dir.is_dir():
        return None
    mapa_prio = prioridades_do_guia(materia_dir)
    assuntos = []
    for sub in sorted(assuntos_dir.iterdir()):
        if sub.is_dir():
            a = coletar_assunto(sub, mapa_prio)
            if a:
                assuntos.append(a)
    if not assuntos:
        return None

    docs = []
    for md in sorted(materia_dir.glob("*.md")):
        if DOCS_APOIO_CONHECIDOS.match(md.name):
            docs.append(md.name)

    # nome legível da matéria: do índice, ou title-case do slug
    nome = materia_dir.name.replace("-", " ").title()
    for md in materia_dir.glob("00-INDICE*.md"):
        fm = ler_frontmatter(md)
        if fm.get("materia"):
            nome = fm["materia"]
            break
        if fm.get("title"):
            nome = fm["title"]
            break

    mapa_loc = materia_dir / "mapa-localizacao.json"
    doc_banca = achar_doc_banca(materia_dir)
    return {
        "nome": nome,
        "doc_banca": doc_banca,
        "slug": materia_dir.name,
        "dir": str(materia_dir),
        "docs_apoio": docs,
        "mapa_localizacao": mapa_loc.name if mapa_loc.exists() else None,
        "assuntos": assuntos,
        "n_assuntos": len(assuntos),
        "n_com_podcast": sum(1 for a in assuntos if a["midias"]["podcast"]),
        "n_com_flashcards": sum(1 for a in assuntos if a["flashcards"]["obsidian"]),
        "por_prioridade": {p: sum(1 for a in assuntos if a.get("prioridade") == p)
                           for p in PRIORIDADES},
    }


# --------------------------------------------------------------------------- #
# seções numeradas do concurso
# --------------------------------------------------------------------------- #
# Tabela declarativa pasta-do-vault → seção-do-site. O `modo` diz quem cuida do
# conteúdo: `documentos` é o tratamento genérico (um .md = uma página, + anexos);
# `materias` e `mapas` têm páginas próprias, montadas em outro lugar.
#
# `03-MAPAS-MATERIAS` e `03-MAPAS-COMUNS` são dois nomes para a mesma coisa: o
# primeiro é por cargo, o segundo é o que o SEDES usa no _COMUM.
SECOES = {
    # o edital é o que se CONSULTA ("o que a regra diz"), não o que se estuda hoje —
    # fica no registro quieto, mas em primeiro lugar dentro dele
    "01-EDITAL":             ("01", "Edital", "edital", "consulta", "documentos"),
    "02-CRONOGRAMA":         ("02", "Cronograma", "cronograma", "estudo", "documentos"),
    "03-MAPAS-MATERIAS":     ("03", "Mapas de matéria", "mapas", "estudo", "mapas"),
    "03-MAPAS-COMUNS":       ("03", "Mapas comuns", "mapas", "estudo", "mapas"),
    "03-APROFUNDAMENTO":     ("03", "Aprofundamento", "aprofundamento", "estudo", "materias"),
    "04-MATERIAIS":          ("04", "Materiais", "materiais", "consulta", "documentos"),
    "05-HISTORICO-CONCURSO": ("05", "Histórico do concurso", "historico", "consulta", "documentos"),
    "06-SINERGIA":           ("06", "Sinergia", "sinergia", "consulta", "documentos"),
    "07-DISCURSIVA":         ("07", "Discursiva", "discursiva", "estudo", "documentos"),
    "08-TITULOS":            ("08", "Títulos", "titulos", "estudo", "documentos"),
}

# Artefatos que existem para navegar no Obsidian, não para ler na web: a navegação
# do site É o índice, e republicá-lo cria uma segunda lista que envelhece. O
# 99-Status continua sendo LIDO (alimenta o progresso do escopo), só não vira página.
DOCS_NAO_PUBLICAVEIS = re.compile(r"^(00-INDICE|99-Status)", re.IGNORECASE)

# Template não preenchido: `{ASSUNTO}`, `{MATERIA}`… Publicar isso seria mostrar
# arcabouço como conteúdo.
PLACEHOLDER_RE = re.compile(r"\{[A-Z_][A-Z0-9_]{2,}\}")

EXT_DOC = (".md",)


def slug_doc(nome: str) -> str:
    """Slug de URL de um documento, sem o prefixo numérico do vault.

    O número existe para ordenar no explorador de arquivos; na URL ele só polui.
    E no SEDES o número exibido no índice às vezes difere do prefixo do arquivo, o
    que torna o prefixo uma fonte ruim de identidade.
    """
    base = re.sub(r"\.md$", "", nome, flags=re.IGNORECASE)
    base = re.sub(r"^\d{2}[-_ ]+", "", base)
    base = norm(base)
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "documento"


def titulo_doc(md: Path, fm: dict, corpo: str) -> str:
    """Título legível: frontmatter, senão o primeiro H1, senão o nome do arquivo."""
    for chave in ("title", "titulo"):
        if fm.get(chave):
            return fm[chave]
    m = re.search(r"^#\s+(.+)$", corpo, re.MULTILINE)
    if m:
        return re.sub(r"\s*[·—-]\s*$", "", m.group(1).strip())
    return re.sub(r"^\d{2}[-_ ]+", "", md.stem).replace("-", " ").strip().capitalize()


def coletar_documento(md: Path) -> dict | None:
    fm = ler_frontmatter(md)
    corpo = fm.get("_corpo", "")
    if PLACEHOLDER_RE.search(corpo):
        return None                     # arcabouço não preenchido não vira página
    return {
        "arquivo": md.name,
        "caminho": str(md),
        "slug": slug_doc(md.name),
        "titulo": titulo_doc(md, fm, corpo),
        "resumo": primeiro_paragrafo_curto(corpo),
        "progresso": contar_progresso(corpo),
        "n_secoes": len(re.findall(r"^##\s+", corpo, re.MULTILINE)),
    }


def primeiro_paragrafo_curto(corpo: str, limite: int = 160) -> str:
    for linha in corpo.split("\n"):
        s = linha.strip()
        if not s or s.startswith(("#", ">", "-", "*", "|", "```", "<!--", "!")):
            continue
        s = re.sub(r"[*`\[\]]", "", s)
        return (s[:limite] + "…") if len(s) > limite else s
    return ""


def coletar_secao(secao_dir: Path, info: tuple) -> dict:
    """Uma seção numerada: os `.md` viram documentos, o resto vira anexo.

    Recursivo porque `04-MATERIAIS/leis-baixadas/` é subpasta — e é lá que estão as
    55 leis. Anexo guarda tamanho para a página poder avisar o peso antes do clique.
    """
    ordinal, rotulo, slug, registro, modo = info
    documentos, anexos = [], []

    alvos = [secao_dir] if secao_dir.is_file() else sorted(secao_dir.rglob("*"))
    for p in alvos:
        if p.is_dir() or p.name.startswith("."):
            continue
        if p.suffix.lower() in EXT_DOC:
            if DOCS_NAO_PUBLICAVEIS.match(p.stem):
                continue
            doc = coletar_documento(p)
            if doc:
                documentos.append(doc)
        else:
            anexos.append({
                "arquivo": p.name,
                "caminho": str(p),
                "extensao": p.suffix.lower().lstrip("."),
                "bytes": p.stat().st_size,
                "subpasta": (str(p.parent.relative_to(secao_dir))
                             if secao_dir.is_dir() and p.parent != secao_dir else ""),
            })

    documentos.sort(key=lambda d: d["arquivo"])
    anexos.sort(key=lambda a: (a["subpasta"], a["arquivo"]))
    return {
        "ordinal": ordinal, "rotulo": rotulo, "slug": slug,
        "registro": registro, "modo": modo,
        "dir": str(secao_dir),
        "documentos": documentos, "anexos": anexos,
        "n_documentos": len(documentos), "n_anexos": len(anexos),
        "bytes_anexos": sum(a["bytes"] for a in anexos),
    }


def progresso_do_status(escopo_dir: Path) -> dict:
    """Progresso declarado no `99-Status.md` — lido, mas não republicado."""
    for md in escopo_dir.glob("99-Status*.md"):
        fm = ler_frontmatter(md)
        return contar_progresso(fm.get("_corpo", ""))
    return {"total": 0, "feitos": 0}


def coletar_escopo(escopo_dir: Path) -> dict:
    """Um escopo: `_COMUM` ou um cargo, com suas seções e suas matérias."""
    nome = escopo_dir.name
    secoes = []
    for filho in sorted(escopo_dir.iterdir()):
        chave = filho.name if filho.is_dir() else filho.stem
        info = SECOES.get(chave.upper())
        if not info:
            continue
        if info[4] in ("materias", "mapas"):
            continue                    # têm páginas próprias, montadas fora daqui
        s = coletar_secao(filho, info)
        if s["documentos"] or s["anexos"]:
            secoes.append(s)

    # matérias aprofundadas do escopo. Segue por `rglob("assuntos")` de propósito:
    # tolera o layout atual (`03-APROFUNDAMENTO/{materia}/assuntos/`) e os
    # anteriores, sem o site quebrar por material que o usuário não migrou.
    materias = []
    for materia_dir in achar_materias(escopo_dir):
        m = coletar_materia(materia_dir)
        if m:
            materias.append(m)
    materias.sort(key=lambda m: m["slug"])

    secoes.sort(key=lambda s: (s["ordinal"], s["slug"]))
    prog_docs = {"total": 0, "feitos": 0}
    for s in secoes:
        for d in s["documentos"]:
            prog_docs["total"] += d["progresso"]["total"]
            prog_docs["feitos"] += d["progresso"]["feitos"]
    prog_assuntos = {"total": 0, "feitos": 0}
    for m in materias:
        for a in m["assuntos"]:
            prog_assuntos["total"] += a["progresso"]["total"]
            prog_assuntos["feitos"] += a["progresso"]["feitos"]

    return {
        "tipo": "comum" if nome.upper() in ("_COMUM", "COMUM") else "cargo",
        "nome": nome,
        "slug": re.sub(r"[^a-z0-9-]+", "-", norm(nome).strip("_")).strip("-") or "escopo",
        "secoes": secoes,
        "materias": materias,
        "n_materias": len(materias),
        "n_assuntos": sum(m["n_assuntos"] for m in materias),
        "progresso": prog_assuntos,
        "progresso_documentos": prog_docs,
        "progresso_status": progresso_do_status(escopo_dir),
    }


def achar_escopos(base: Path) -> list[Path]:
    """Escopos do concurso: `_COMUM` e cada pasta de cargo na raiz.

    A varredura ANTES partia de `rglob("assuntos")` na raiz do concurso, então a
    árvore inteira do site era descoberta a partir da existência de
    aprofundamento — e um escopo que só tem `01-EDITAL` (o caso do `_COMUM` em
    qualquer concurso antes da Etapa 2) nunca era descoberto. Nada dele podia ser
    publicado, por construção.
    """
    return sorted(p for p in base.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


# --------------------------------------------------------------------------- #
# coleta do concurso
# --------------------------------------------------------------------------- #
def achar_materias(base: Path) -> list[Path]:
    """Encontra pastas de matéria: qualquer dir contendo 'assuntos/' com subpastas.
    Cobre tanto o layout {CARGO}/03-MAPAS-MATERIAS/{materia}/ quanto layouts
    achatados (matéria direto na raiz)."""
    achadas = []
    for assuntos_dir in base.rglob("assuntos"):
        if assuntos_dir.is_dir() and any(p.is_dir() for p in assuntos_dir.iterdir()):
            achadas.append(assuntos_dir.parent)
    return sorted(set(achadas))


def cargo_de(materia_dir: Path, base: Path) -> str:
    """Deriva o escopo da matéria: o PRIMEIRO componente sob a raiz do concurso.

    É assim que o vault organiza — `_COMUM/` para o que é transversal e
    `{CARGO}/` para o resto — e é o que o usuário vê no Obsidian.

    A versão anterior procurava o segmento `03-MAPAS` no caminho e devolvia o
    componente anterior a ele. Como o aprofundamento vive em `03-APROFUNDAMENTO`,
    a condição **nunca casava** com o vault real e TODA matéria caía em `_GERAL`,
    deixando a capa do concurso sem nenhum agrupamento. O teste não pegou porque a
    fixture montava os assuntos sob `03-MAPAS-MATERIAS`, um layout que a
    `concurso-aprofunda` não produz.

    Matéria solta na raiz do concurso (layout achatado) continua em `_GERAL`.
    """
    try:
        rel = materia_dir.relative_to(base)
    except ValueError:
        return "_GERAL"
    partes = rel.parts
    return partes[0] if len(partes) >= 2 else "_GERAL"


def coletar_concurso(base: Path) -> dict:
    meta = {}
    meta_path = base / ".meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {"_erro": ".meta.json malformado"}

    escopos = []
    for escopo_dir in achar_escopos(base):
        e = coletar_escopo(escopo_dir)
        if e["secoes"] or e["materias"]:
            escopos.append(e)

    # layout achatado: matéria direto na raiz do concurso, sem escopo. Vira um
    # escopo implícito, que o builder não rotula.
    soltas = [m for m in (coletar_materia(d) for d in achar_materias(base)
                          if cargo_de(d, base) == "_GERAL") if m]
    if soltas:
        escopos.append({
            "tipo": "geral", "nome": "_GERAL", "slug": "geral",
            "secoes": [], "materias": soltas,
            "n_materias": len(soltas),
            "n_assuntos": sum(m["n_assuntos"] for m in soltas),
            "progresso": {"total": 0, "feitos": 0},
            "progresso_documentos": {"total": 0, "feitos": 0},
            "progresso_status": {"total": 0, "feitos": 0},
        })

    # `_COMUM` primeiro (é o que vale para todos), cargos em ordem alfabética
    escopos.sort(key=lambda e: (e["tipo"] != "comum", e["nome"]))

    return {
        "concurso": base.name,
        "dir": str(base),
        "meta": {k: v for k, v in meta.items() if k in
                 ("orgao", "ano", "banca", "modo", "datas_chave", "estrutura_prova",
                  "vagas_ac", "vagas_total", "salario")},
        "escopos": escopos,
        # alias de compatibilidade: `--modelo site-model.json` é contrato público e
        # documentado no SKILL.md. Sai numa versão futura, com aviso.
        "cargos": escopos,
        "resumo": {
            "n_escopos": len(escopos),
            "n_cargos": sum(1 for e in escopos if e["tipo"] == "cargo"),
            "n_materias": sum(e["n_materias"] for e in escopos),
            "n_assuntos": sum(e["n_assuntos"] for e in escopos),
            "n_documentos": sum(s["n_documentos"] for e in escopos
                                for s in e["secoes"]),
            "n_anexos": sum(s["n_anexos"] for e in escopos for s in e["secoes"]),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Coleta o modelo do site de um concurso")
    ap.add_argument("--concurso-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.concurso_dir.is_dir():
        sys.stderr.write(f"ERRO: não é diretório: {args.concurso_dir}\n")
        sys.exit(1)

    modelo = coletar_concurso(args.concurso_dir)

    if modelo["resumo"]["n_assuntos"] == 0:
        sys.stderr.write("AVISO: nenhum assunto aprofundado encontrado. "
                         "Rode a concurso-aprofunda antes de publicar.\n")

    saida = json.dumps(modelo, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(saida, encoding="utf-8")
        sys.stderr.write(f"OK: modelo salvo em {args.out}\n")
    if args.json or not args.out:
        print(saida)
    sys.exit(0)


if __name__ == "__main__":
    main()
