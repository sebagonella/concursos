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
    eh_pasta_aprofundamento, parse_id, rotulo, localizacoes_por_fonte, FONTE_PROPRIA,
)


def cobertura_da_materia(materia: dict, assuntos=None) -> dict:
    """Quantos tópicos do edital têm pelo menos um assunto aprofundado.

    É **contagem**, não estimativa: usa o `topico_id` gravado na Etapa 2, o mesmo
    que alimenta o agrupamento. Nada aqui é inferido por slug.

    Deliberadamente NÃO existe nota de qualidade. Os sinais que poderiam compô-la
    estão saturados no vault real — placeholders não preenchidos: 0 arquivos;
    `status`: todos `revisar`; `confianca_localizacao: baixa`: 0 de 92 — então a
    nota seria uma constante disfarçada de métrica. O que se mede é cobertura; o
    que se mostra além disso é o que EXISTE em cada assunto (ver `sinais_do_assunto`).
    """
    mapa = materia.get("mapa")
    if not mapa:
        return {}
    # `assuntos` pode vir de fora: a matéria do cargo costuma ter o MAPA enquanto o
    # aprofundamento vive no _COMUM. Contar só os próprios daria 0% numa matéria
    # inteiramente aprofundada, do outro lado do atalho.
    ass = materia["assuntos"] if assuntos is None else assuntos
    vinculados = {t for a in ass for t in (a.get("topico_id") or [])}

    # Guarda contra o falso zero: se HÁ assuntos e NENHUM tem vínculo, a
    # cobertura é desconhecida, não zero. Reportar 0% aqui diria "nada foi
    # aprofundado" sobre uma matéria inteiramente aprofundada, só que sem o
    # `topico_id` gravado — que é o falso negativo que este projeto proíbe desde
    # a regra do link tópico→assunto.
    if ass and not vinculados:
        return {"vinculo_ausente": True, "n_assuntos": len(ass)}
    sem = [{"numero": t["numero"], "titulo": t["titulo"]}
           for t in mapa["topicos"] if t["slug"] not in vinculados]
    n_top = mapa["n_topicos"]
    n_cob = n_top - len(sem)
    return {
        "n_topicos": n_top,
        "n_cobertos": n_cob,
        "pct": round(100 * n_cob / n_top) if n_top else 0,
        "topicos_sem": sem,
        # profundidade do que existe — contagem, não julgamento
        "n_detalhado": sum(1 for a in ass if "detalhado" in (a.get("niveis") or [])),
        "n_com_midia": sum(1 for a in ass if any((a.get("midias") or {}).values())),
    }


def cobertura_do_escopo(materias: list[dict]) -> dict:
    """Cobertura do escopo: a soma dos tópicos das suas matérias.

    Somar em vez de contar "matérias aprofundadas" é o que faz a barra do escopo
    ser exatamente a soma das barras das matérias — matéria com 1 assunto de 60
    não pode pesar igual a uma completa.

    As duas exclusões do denominador são a mesma regra do falso zero:
    matéria sem mapa não tem tópico para cobrir, e matéria com `vinculo_ausente`
    tem cobertura DESCONHECIDA. Jogar qualquer uma das duas no denominador como
    zero afirmaria "não aprofundado" sobre trabalho que pode estar feito. As sem
    vínculo saem contadas em `n_sem_vinculo`, para a página ressalvar por escrito
    em vez de silenciar.
    """
    n_top = n_cob = n_com_mapa = n_sem_vinculo = 0
    for m in materias:
        cb = m.get("cobertura") or {}
        if cb.get("vinculo_ausente"):
            n_sem_vinculo += 1
            continue
        if not cb.get("n_topicos"):
            continue
        n_com_mapa += 1
        n_top += cb["n_topicos"]
        n_cob += cb["n_cobertos"]
    return {
        "n_topicos": n_top,
        "n_cobertos": n_cob,
        # `None`, nunca 0: sem denominador não há o que afirmar
        "pct": round(100 * n_cob / n_top) if n_top else None,
        "n_materias": len(materias),
        "n_com_mapa": n_com_mapa,
        "n_sem_vinculo": n_sem_vinculo,
    }


def somar_progressos(*partes: dict) -> dict:
    """Soma `{total, feitos}`. As partes são contadas em lugares diferentes do
    escopo e nunca se sobrepõem — ver `coletar_escopo`."""
    return {
        "total": sum((p or {}).get("total", 0) for p in partes),
        "feitos": sum((p or {}).get("feitos", 0) for p in partes),
    }


def progresso_da_materia(materia: dict) -> dict:
    """Tarefas de estudo da matéria: os assuntos MAIS os itens do plano.

    Os checkboxes do mapa do edital ("Ler as páginas", "Resolver 30 questões",
    os subtópicos derivados) são tarefa de estudo do mesmo tipo das do
    aprofundamento — a aba Plano já os mostra como "N/M itens do plano". Ficaram
    de fora até a 0.17.0 com o argumento de que 1.998 itens nunca marcados
    afogariam as ~200 do aprofundamento; o uso mostrou o contrário: **12 das 22
    matérias do vault não mostravam barra nenhuma** por causa dessa exclusão.

    O mapa EMPRESTADO não entra. `cruzar_materias_comuns` anexa o mapa do cargo
    à matéria irmã do `_COMUM`, e a mesma regra que já vale para tarefa vale
    aqui: conta quem guarda o arquivo. Somar dos dois lados contaria 237 itens
    em dobro só no `_COMUM` do SEDES.
    """
    partes = [a["progresso"] for a in materia.get("assuntos") or []]
    if materia.get("mapa") and not materia.get("mapa_em"):
        partes.append(materia["mapa"]["progresso"])
    return somar_progressos(*partes)


def sinais_do_assunto(aprofs: list[dict], principal: dict) -> dict:
    """O que EXISTE neste assunto — tudo verificável no disco.

    Sem score: cada campo é contagem ou presença, e o leitor tira a conclusão.
    """
    return {
        "n_cards": max((a.get("flashcards") or {}).get("n_cards", 0) for a in aprofs)
        if aprofs else 0,
        "tem_ancoras": any(a.get("tem_ancoras") for a in aprofs),
        "palavras": max((a.get("palavras") or 0) for a in aprofs) if aprofs else 0,
    }


def fontes_externas(aprofs: list[dict]) -> set[str]:
    """Fontes de verdade do assunto, ignorando o material próprio.

    "material próprio" ocupa o campo `fontes:` do frontmatter porque o template
    precisa preencher alguma coisa — mas não é fonte, é a declaração de que não
    há nenhuma. Somá-lo faria o card dizer "2 fontes" onde há uma norma e um
    texto escrito do zero.
    """
    return {f.strip()
            for a in aprofs
            if (a.get("fontes_id") or []) != [FONTE_PROPRIA]
            for f in (a.get("fontes") or "").split(",") if f.strip()}


# --------------------------------------------------------------------------- #
# util
# --------------------------------------------------------------------------- #
def norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def lista_yaml(valor) -> list[str]:
    """Lê uma lista YAML inline (`[a, b]`) do frontmatter, que o parser daqui
    entrega como string crua.

    `[]` e ausência dão a mesma coisa — lista vazia significa "ainda não
    vinculado", e é um estado legítimo que o site precisa saber distinguir de
    um vínculo errado.
    """
    if isinstance(valor, list):
        return [str(v).strip() for v in valor if str(v).strip()]
    s = (valor or "").strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    return [p.strip().strip('"').strip("'") for p in s.split(",") if p.strip()]


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

# Aferição do material contra prova real (skill `concurso-afere`), publicada com
# CONTEÚDO — não como nome numa lista. Ela mede a matéria em que está e traz as
# ações corretivas; a de Vendas e Negociação tem 267 linhas de tabela e análise.
DOC_AFERICAO = re.compile(r"^00-AFERICAO", re.IGNORECASE)


def achar_doc_banca(materia_dir: Path) -> str | None:
    for md in sorted(materia_dir.glob("*.md")):
        if DOC_BANCA.match(md.stem):
            return md.name
    return None


def achar_docs_afericao(materia_dir: Path) -> list[str]:
    """TODAS as aferições da matéria, da mais recente para a mais antiga.

    Uma matéria pode ser aferida mais de uma vez — contra outra prova, ou contra
    a mesma depois de corrigido o material. Devolver só a primeira em ordem
    alfabética escondia as demais **em silêncio**, que é exatamente o defeito que
    a publicação da aferição veio consertar (o `00-AFERICAO-*` fora da allowlist),
    reaparecendo em outra forma.

    A ordem é pelo `data:` do frontmatter, decrescente: a última medição é a que
    interessa primeiro e as anteriores viram histórico. Sem `data:`, cai no nome
    do arquivo — nunca some, no pior caso fica no fim.
    """
    achados = []
    for md in sorted(materia_dir.glob("*.md")):
        if DOC_AFERICAO.match(md.stem):
            data = (ler_frontmatter(md) or {}).get("data") or ""
            achados.append((str(data), md.name))
    achados.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [nome for _, nome in achados]


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

    # pacote NotebookLM: roteiro + prompts, e o link interativo se preenchido
    pack_info = coletar_pack_notebooklm(subdir)
    nb_url = pack_info["url"] if pack_info else None
    pack = subdir / "_fonte-notebooklm.md"

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
        # o vínculo com o plano do edital, GRAVADO na Etapa 2 — não inferido aqui
        "materia_id": (fm.get("materia_id") or "").strip(),
        "topico_id": lista_yaml(fm.get("topico_id")),
        "topico": lista_yaml(fm.get("topico")),
        "status": fm.get("status", "?"),
        "paginas_livro": extrair_paginas(fm),
        # Uma entrada por fonte, na ordem do id. `paginas_livro` continua sendo só a
        # da fonte 1 (é o que os leitores antigos consomem); esta lista é o texto
        # inteiro de cada ponteiro, que metade do vault escreve em prosa livre e
        # nenhuma regex extrai. Casada com o slug da fonte pela posição.
        "localizacoes": [{"fonte": f, "texto": t}
                         for f, t in localizacoes_por_fonte(fm, aprof_id)],
        "resumo_md": str(principal),
        "midias": midias,
        "flashcards": flashcards,
        "notebooklm_url": nb_url,
        "progresso": contar_progresso(corpo),
        # sinais verificáveis do que existe neste aprofundamento: 33 dos 92
        # assuntos do vault não têm trechos-âncora, e o tamanho do resumo varia
        # de 840 a 4.217 palavras — os dois discriminam, ao contrário de
        # `status` e `confianca`, que estão saturados
        "tem_ancoras": bool(re.search(r"^##.*(Trechos-âncora|Artigos-chave)", corpo,
                                      re.MULTILINE | re.IGNORECASE)),
        "palavras": len(corpo.split()),
        "tem_pack_notebooklm": pack.exists(),
        "pack_notebooklm": pack_info,
    }




# --------------------------------------------------------------------------- #
# pacote NotebookLM
# --------------------------------------------------------------------------- #
# O `_fonte-notebooklm.md` tem template rígido: as mesmas 9 seções nos 92 arquivos
# do vault e ZERO H3. A extração é determinística por isso — e o que interessa são
# os 4 blocos de código, que são prompts para copiar e colar no Estúdio.
PROMPTS_PACK = (
    ("podcast",     re.compile(r"podcast|audio overview", re.I), "🎧", "Podcast"),
    ("mapa_mental", re.compile(r"mapa mental|mind map", re.I),   "🧠", "Mapa mental"),
    ("video",       re.compile(r"v[ií]deo|video overview", re.I), "🎬", "Vídeo"),
    ("report",      re.compile(r"report|relat[oó]rio", re.I),    "📄", "Relatório"),
)


def coletar_pack_notebooklm(subdir: Path) -> dict | None:
    """Extrai do pacote o que é ACIONÁVEL: fontes a subir e os prompts a colar.

    O levantamento do vault mostrou 92 pacotes prontos e **um** assunto com mídia
    de verdade. O gargalo do fluxo não é ter o roteiro, é executá-lo 92 vezes — daí
    a página existir para dar o prompt a um toque, não para ser lida.

    Os 4 wikilinks da seção "Arquivos gerados" NÃO são parseados: dos 368 do vault,
    só 6 têm arquivo. A presença de mídia continua vindo de `detectar_midias()`.
    """
    pack = subdir / "_fonte-notebooklm.md"
    if not pack.exists():
        return None
    fm = ler_frontmatter(pack)
    corpo = fm.get("_corpo", "")

    # cada bloco cercado é um prompt; o rótulo vem do H2 que o precede
    prompts = []
    for bloco in re.split(r"^##\s+", corpo, flags=re.MULTILINE)[1:]:
        linhas = bloco.split("\n")
        titulo = re.sub(r"^\d+\.\s*", "", linhas[0].strip())
        fences = re.findall(r"^```\s*\n(.*?)^```", "\n".join(linhas[1:]),
                            re.MULTILINE | re.DOTALL)
        if not fences:
            continue
        chave = icone = rotulo = None
        for k, padrao, ic, rot in PROMPTS_PACK:
            if padrao.search(titulo):
                chave, icone, rotulo = k, ic, rot
                break
        corpo_bloco = "\n".join(linhas[1:])
        prompts.append({
            "chave": chave or slug_doc(titulo),
            "icone": icone or "✨",
            "rotulo": rotulo or titulo,
            "titulo_secao": titulo,
            "prompt": fences[0].strip(),
            "roteiro": _roteiro_do_bloco(corpo_bloco),
            # com que nome salvar o gerável — o que a automação vai consumir
            "arquivo_saida": _arquivo_de_saida(fm, chave, corpo_bloco),
        })

    fontes = re.findall(r"^\d+\.\s+(.*)$",
                        _secao_do_pack(corpo, r"fontes para subir"), re.MULTILINE)
    perguntas = re.findall(r"^[-*]\s+(.*)$",
                           _secao_do_pack(corpo, r"perguntas [uú]teis"), re.MULTILINE)
    checklist = re.findall(r"^\s*-\s*\[([ xX])\]\s*(.+)$",
                           _secao_do_pack(corpo, r"checklist"), re.MULTILINE)

    return {
        "caminho": str(pack),
        "status": (fm.get("notebooklm_status") or "").strip() or "nao-criado",
        "url": _url_do_pack(fm),
        # o nome com que criar o notebook — é POR APROFUNDAMENTO, não por assunto
        "nome_notebook": _nome_do_notebook(fm, corpo),
        "fontes": [re.sub(r"\*\*", "", f).strip() for f in fontes],
        "prompts": prompts,
        "perguntas": [re.sub(r"\*\*", "", p).strip() for p in perguntas],
        "checklist": [{"feito": m[0].lower() == "x", "texto": m[1].strip()}
                      for m in checklist],
        "progresso": contar_progresso(corpo),
    }


def _secao_do_pack(corpo: str, padrao: str) -> str:
    for bloco in re.split(r"^##\s+", corpo, flags=re.MULTILINE)[1:]:
        linhas = bloco.split("\n")
        if re.search(padrao, linhas[0], re.I):
            return "\n".join(linhas[1:])
    return ""


# linhas do bloco que são estrutura, não instrução: blockquote, título, comentário,
# separador, wikilink solto e item de lista numerada (que é a lista de fontes)
_ROTEIRO_ESTRUTURAL = re.compile(r"^(>|#{1,6}\s|<!--|-{3,}\s*$|\[\[|\d+\.\s)")


def _roteiro_do_bloco(texto: str) -> list[str]:
    """As linhas de "onde clicar" — o que o pacote chama de roteiro do Estúdio.

    Regra ABERTA: toda linha de instrução entra, seja bullet ou parágrafo. A regra
    anterior exigia bullet **e** um verbo de lista fechada, e no template real as
    três linhas que mais importam são parágrafo:

        Studio → **Audio Overview** → clique em **Customize**.
        Generate → ao terminar, ⋮ → Download. O NotebookLM gera **`.m4a`**.
        Salve nesta pasta como **`podcast-{SLUG}.m4a`**.

    Resultado: o mapa mental e o report, cujas instruções são TODAS parágrafo,
    chegavam ao site com `roteiro: []` — está congelado assim no
    `examples/site-model-exemplo.json`. Lista fechada falha em silêncio (some linha,
    ninguém vê); regra aberta falha barulhento (aparece linha a mais, que se vê e se
    corrige). Prosa que não é roteiro vai como blockquote no template, e o `>` é
    justamente a válvula de escape reconhecida aqui.
    """
    linhas, dentro_do_fence = [], False
    for bruta in texto.split("\n"):
        l = bruta.strip()
        if l.startswith("```"):
            # o rótulo que só ANUNCIA o prompt ("Prompt «no que focar»:") não é
            # roteiro — o próprio bloco vem logo abaixo
            if not dentro_do_fence and linhas and linhas[-1].endswith(":"):
                linhas.pop()
            dentro_do_fence = not dentro_do_fence
            continue
        if dentro_do_fence or not l or _ROTEIRO_ESTRUTURAL.match(l):
            continue
        linhas.append(re.sub(r"\*\*|`", "", l).strip(" -*·"))
    return linhas


def _nome_do_notebook(fm: dict, corpo: str) -> str | None:
    """Nome sugerido do notebook: contrato no frontmatter, prosa como fallback.

    A chave `nome_notebook:` passou a ser emitida pela concurso-aprofunda; os packs
    gerados antes disso só têm a frase da seção 1, e o site lê o vault como ele
    está — que sempre atrasa em relação ao código.
    """
    if (v := (fm.get("nome_notebook") or "").strip()):
        return v
    m = re.search(r'chamado\s+\*\*"([^"]+)"\*\*',
                  _secao_do_pack(corpo, r"fontes para subir"))
    return m.group(1) if m else None


# nome de arquivo em negrito+código: `**\`podcast-x.m4a\`**`. O filtro de stem
# descarta o `**\`.m4a\`**` solto da linha do Generate, que é extensão, não arquivo.
_ARQ_SAIDA = re.compile(r"\*\*`([^`]*\.[A-Za-z0-9]{2,4})`\*\*")


def _arquivo_de_saida(fm: dict, chave: str | None, bloco: str) -> str | None:
    """O nome com que salvar o gerável. Frontmatter primeiro, prosa como fallback."""
    if chave and (v := (fm.get(f"arquivo_{chave}") or "").strip()):
        return v
    cand = [m.group(1) for m in _ARQ_SAIDA.finditer(bloco)
            if not m.group(1).startswith(".")]
    return cand[-1] if cand else None


def _url_do_pack(fm: dict) -> str | None:
    url = (fm.get("notebooklm_url") or "").strip()
    return url if url and url.lower() not in ("", "null", "~") else None


# `padrao` primeiro: é a aba que abre e o aprofundamento que representa o assunto.
# Entra-se num assunto para REVISAR — o resumo de revisão é o caminho comum, e o
# tratamento exaustivo é a exceção, a um clique de distância. O desempate dentro do
# mesmo nível é alfabético pelo id do aprofundamento (ver o `sort` em `coletar_assunto`).
ORDEM_NIVEL = {"padrao": 0, "detalhado": 1}


def uniao_midias(aprofs: list[dict]) -> dict:
    """União das mídias de TODOS os aprofundamentos do assunto.

    O selo no card afirma "existe podcast para este assunto", e isso é verdade se
    QUALQUER aprofundamento tiver o arquivo. Antes o valor era herdado do
    aprofundamento principal, e um assunto cuja mídia estivesse no aprofundamento
    que não é o principal aparecia sem mídia nenhuma. Era o caso do único assunto do
    vault com podcast, vídeo e mapa mental: os três estão em `padrao--pestana`, que
    à época era o secundário, e o site anunciava "0 com áudio" na matéria inteira.

    A união vale independentemente da ordem — e tem de continuar valendo: `ORDEM_NIVEL`
    já foi `detalhado` primeiro e hoje é `padrao`, sem que este cálculo mude.

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

    # ordenar: padrão primeiro, depois detalhado; empate alfabético pelo id.
    # `aprofs[0]` é o principal — abre a aba e representa o assunto no card.
    #
    # O 2º componente desempata ANTES do alfabético e existe por um motivo: o
    # aprofundamento do layout plano legado não tem identidade de fonte e recebe o id
    # `original`, que por acaso vem antes de `padrao--*` no alfabeto. Sem isto, um
    # assunto que ainda tivesse o arquivo legado abriria nele em vez de abrir no
    # aprofundamento de verdade. Não há nenhum no vault hoje — é rede para o caso.
    aprofs.sort(key=lambda a: (ORDEM_NIVEL.get(a["nivel"], 2),
                               0 if a.get("n_fontes_id") is not None else 1,
                               a["aprofundamento"]))

    principal = aprofs[0]
    # dados do assunto: herdados do aprofundamento principal
    return {
        "slug": slug_assunto,
        "titulo": principal["titulo"],
        "prioridade": next((a["prioridade"] for a in aprofs if a.get("prioridade")), None),
        "paginas_livro": principal.get("paginas_livro"),
        "n_aprofundamentos": len(aprofs),
        "niveis": sorted({a["nivel"] for a in aprofs}),
        # Fontes distintas entre todos os aprofundamentos deste assunto.
        # O material próprio NÃO conta como fonte: ele é a ausência de fonte
        # externa. Contá-lo fazia o card anunciar "2 fontes" para um assunto com
        # uma norma e um texto escrito do zero — que é afirmar o que não é.
        "fontes": sorted(fontes_externas(aprofs)),
        "n_fontes": len(fontes_externas(aprofs)),
        "aprofundamentos": aprofs,
        # o vínculo com o tópico é do ASSUNTO, então vale a união do que os
        # aprofundamentos declararam: basta um deles saber o tópico para o
        # assunto saber. Ordem estável para o site não oscilar entre gerações.
        "materia_id": next((a["materia_id"] for a in aprofs if a.get("materia_id")), ""),
        "topico_id": sorted({t for a in aprofs for t in a.get("topico_id") or []}),
        "topico": sorted({t for a in aprofs for t in a.get("topico") or []}),
        # agregados do CONJUNTO de aprofundamentos: presença de mídia e de
        # flashcards não podem vir do principal (ver uniao_midias)
        "midias": uniao_midias(aprofs),
        "flashcards": uniao_flashcards(aprofs, principal),
        "sinais": sinais_do_assunto(aprofs, principal),
        # Tarefas do assunto: a UNIÃO dos aprofundamentos, não as do principal.
        # Cada aprofundamento traz o seu checklist ("ler as páginas X do
        # Pestana"), e o da versão detalhada é trabalho tão real quanto o da
        # padrão. Contando só `aprofs[0]` o vault perdia 181 checkboxes em 29
        # assuntos — dois de português apareciam zerados tendo 8 e 7 tarefas.
        # (A lateral da página segue mostrando o do aprofundamento aberto, que
        # é o que aquela aba representa.)
        "progresso": somar_progressos(*[a["progresso"] for a in aprofs]),
        # atalhos do principal
        "resumo_md": principal["resumo_md"],
        "notebooklm_url": principal.get("notebooklm_url"),
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
    docs_afericao = achar_docs_afericao(materia_dir)

    # Aliases OPCIONAIS tópico-do-mapa → assunto(s), preenchidos à mão quando o
    # usuário quiser o link fino. Ausente = sem links extras, e nenhum palpite: o
    # casamento automático só vale quando o slug bate exatamente.
    aliases = {}
    alias_f = materia_dir / "mapa-aliases.json"
    if alias_f.exists():
        try:
            bruto = json.loads(alias_f.read_text(encoding="utf-8"))
            aliases = {norm(k): (v if isinstance(v, list) else [v])
                       for k, v in bruto.items()}
        except (json.JSONDecodeError, AttributeError):
            aliases = {}
    return {
        "nome": nome,
        # `materia_id` é o join com o mapa do edital, e existe porque o nome da
        # pasta NÃO serve: no vault a mesma matéria aparece como
        # `direitos-violacoes` (aprofundamento) e `direitos-violacoes-vulnerabilidades`
        # (mapa), com três grafias diferentes do nome. Casar por pasta falhava em
        # 5 das 9 matérias aprofundadas.
        "materia_id": next((a["materia_id"] for a in assuntos if a.get("materia_id")),
                           materia_dir.name),
        "doc_banca": doc_banca,
        "docs_afericao": docs_afericao,
        "slug": materia_dir.name,
        "dir": str(materia_dir),
        "docs_apoio": docs,
        "mapa_localizacao": mapa_loc.name if mapa_loc.exists() else None,
        "aliases_mapa": aliases,
        "assuntos": assuntos,
        # Valor inicial: aqui o mapa ainda não foi anexado. `atualizar_progresso`
        # recalcula com `progresso_da_materia`, que soma os itens do plano —
        # e que documenta por que só os assuntos PRÓPRIOS entram.
        "progresso": somar_progressos(*[a["progresso"] for a in assuntos]),
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
# Extensões que NUNCA viram anexo publicado. Backup é trabalho interno do vault:
# os scripts que reescrevem material deixam `.md.bak` ao lado do arquivo, e a
# varredura recursiva os transformava em anexo — os backups apareciam no site
# como arquivo para baixar, e ainda impediam a seção de colapsar num documento
# só, criando uma página de índice a mais.
IGNORAR_EXT = {".bak", ".tmp", ".swp", ".orig", ".rej"}

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
# 99-Status continua sendo LIDO — é uma das três parcelas de `progresso_tarefas`,
# ao lado dos assuntos e dos documentos de seção —, só não vira página.
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
    """Resumo de uma linha para o índice da seção — ou nada.

    Só aceita linha que COMEÇA como frase (maiúscula ou dígito). Sem isso, o
    extrator pegava a continuação de um parágrafo partido no meio e o índice exibia
    fragmentos como "…realização de concursos públicos no DF (não "isenção"). Mantida
    por constar". Meio resumo errado é pior que nenhum: ocupa a linha e desinforma.
    """
    for linha in corpo.split("\n"):
        s = linha.strip()
        if not s or s.startswith(("#", ">", "-", "*", "|", "```", "<!--", "!")):
            continue
        s = re.sub(r"[*`\[\]]", "", s).strip()
        if not s or not (s[0].isupper() or s[0].isdigit()):
            return ""
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
        if p.is_dir() or p.name.startswith(".") or p.suffix.lower() in IGNORAR_EXT:
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


# --------------------------------------------------------------------------- #
# mapa de matéria (a aba "Plano")
# --------------------------------------------------------------------------- #
# O template do mapa é rígido a ~98%, mas os rótulos de H3 variam: "Pegadinhas"
# aparece em três formas ("### Pegadinhas…", "### ⚠️ Pegadinhas…", "### Pegadinhas da
# Quadrix…") e "Subtópicos derivados" às vezes leva sufixo temático ("— TEORIA").
# Por isso o casamento é por PREFIXO/BUSCA, nunca por igualdade — igualdade
# silenciosamente perderia a seção e o conteúdo sumiria da página.
H3_MAPA = (
    ("topicos_edital", re.compile(r"t[oó]picos do edital", re.I)),
    ("subtopicos",     re.compile(r"^subt[oó]picos derivados", re.I)),
    ("material",       re.compile(r"^material recomendado", re.I)),
    ("pegadinhas",     re.compile(r"pegadinhas", re.I)),
    ("meta",           re.compile(r"^meta\b", re.I)),
)

# `✍️ Meu resumo` existe em 23 dos 24 mapas e está VAZIO em 16 — só rótulos em
# negrito seguidos de um `-` solto. Nos outros 8 é exercício de preenchimento
# (`- CRAS →`, tabela de memorização com células vazias). Numa página web rende
# cabeçalho seguido de nada, ou um exercício que o site não pode receber.
H2_DESCARTAR = re.compile(r"meu resumo", re.I)

# emoji de prioridade embutido no título: `## 19. LGPD 🔴`
PRIORIDADE_EMOJI = {"🔴": "alta", "🟠": "alta", "🟡": "media", "🟢": "base"}

TOPICO_NUMERADO = re.compile(r"^(\d+)\.\s*(.+)$")

# H3 que não casa NENHUM padrão de `H3_MAPA`. Eram descartados em silêncio — e não
# são ruído: `Leis-chave`, `Conceitos-chave / fórmulas`, `Referência legal` e os
# blocos mnemônicos 🧠 (vários com tabela) somam 50 blocos dentro de tópicos
# numerados do vault. É o conteúdo mais trabalhoso de escrever, e era o que sumia.
CHAVE_EXTRA = "extra"

_SUFIXO_RE = re.compile(r"^\s*[—–:-]\s*")
_CHECK_RE = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.+)$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(?!\[[ xX]\])(.+)$")


def _chave_do_h3(rotulo: str) -> tuple[str, str]:
    """(chave canônica, sufixo temático) de um H3 de tópico.

    O sufixo é o que sobra do rótulo depois do trecho reconhecido: em
    `### Subtópicos derivados — LEI 8.662/1993 (DECORAR ARTIGOS)` ele é o que diz
    de que bloco aquele checklist é. Perdê-lo transformava quatro listas distintas
    numa só, sem dizer de quê.
    """
    for chave, padrao in H3_MAPA:
        m = padrao.search(rotulo)
        if m:
            return chave, _SUFIXO_RE.sub("", rotulo[m.end():]).strip()
    return CHAVE_EXTRA, ""


_H4_RE = re.compile(r"^\s*####\s+(.+?)\s*$")

# Os mapas fecham cada tópico com `---`. Como o separador vem depois do último H3,
# ele é absorvido por aquele bloco (quase sempre a `Meta`) e virava um `<hr>` solto
# dentro da seção, com um vão embaixo. É pontuação do documento, não conteúdo.
_SEPARADOR_FINAL = re.compile(r"(?:\n[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*)+\s*$")


def _itens_do_bloco(md: str) -> list[dict]:
    """Itens de um bloco, EM ORDEM: checkbox com estado, bullet com `feito: None`.

    Linha a linha, e não dois `findall`, por duas razões. A ordem: varrer checkbox
    e bullet em passes separados juntava todos os checkbox antes de todos os
    bullets, embaralhando um bloco misto. E o `#### `: dentro de `Subtópicos
    derivados` o vault usa H4 para subdividir (`#### Proteção Social Básica (PSB) —
    ofertada no CRAS`), e como a lista só recolhe bullets, o H4 sumia junto com a
    informação de a que parte cada item pertence.
    """
    itens: list[dict] = []
    subgrupo = ""
    for linha in md.split("\n"):
        m = _H4_RE.match(linha)
        if m:
            subgrupo = re.sub(r"\*\*", "", m.group(1)).strip()
            continue
        m = _CHECK_RE.match(linha)
        if m:
            itens.append({"texto": re.sub(r"\*\*", "", m.group(2)).strip(),
                          "feito": m.group(1).lower() == "x", "subgrupo": subgrupo})
            continue
        m = _BULLET_RE.match(linha)
        if m:
            itens.append({"texto": re.sub(r"\*\*", "", m.group(1)).strip(),
                          "feito": None, "subgrupo": subgrupo})
    return itens


def blocos_do_topico(conteudo: str) -> list[dict]:
    """Todos os H3 de um tópico, na ordem do documento.

    Substitui o `dict` chave->markdown que existia aqui. O dict era lossy por
    construção: um tópico com `### Subtópicos derivados — TEORIA` e
    `### Subtópicos derivados — LEI 8.662/1993` tinha o primeiro sobrescrito pelo
    segundo. São 5 tópicos e 57 subtópicos do vault, e dava para ver na página: o
    tópico 2 de `servico-social` listava 1 item e o rodapé dizia `0/22 itens do
    plano`.
    """
    blocos = []
    for sub in re.split(r"^###\s+", conteudo, flags=re.MULTILINE)[1:]:
        linhas = sub.split("\n")
        rotulo = linhas[0].strip()
        markdown = _SEPARADOR_FINAL.sub("", "\n".join(linhas[1:])).strip()
        chave, sufixo = _chave_do_h3(rotulo)
        itens = _itens_do_bloco(markdown)
        blocos.append({
            "chave": chave,
            "rotulo": rotulo,          # literal do vault: "Pegadinhas da Quadrix…"
            "sufixo": sufixo,
            "markdown": markdown,
            "itens": itens,
            "n_itens": len(itens),
        })
    return blocos


def _prioridade_do_titulo(titulo: str) -> tuple[str, str | None]:
    """Separa o emoji de prioridade do título. Devolve (título limpo, prioridade)."""
    prio = None
    for emoji, valor in PRIORIDADE_EMOJI.items():
        if emoji in titulo:
            prio = valor
            titulo = titulo.replace(emoji, "")
            break
    titulo = re.sub(r"\s*\((BLOCO [^)]+)\)\s*$", "", titulo, flags=re.I)
    return re.sub(r"\s{2,}", " ", titulo).strip(" —-·"), prio


def nome_materia_do_mapa(md: Path, fm: dict, corpo: str) -> str:
    """Nome da MATÉRIA a partir do mapa, sem o rótulo do documento.

    O H1 do mapa é "📚 Mapa de Estudo — Serviço Social", e usá-lo cru fazia o card
    da matéria anunciar o nome do documento em vez do nome da matéria. Só 6 dos 24
    mapas trazem `materia:` no frontmatter, então o resto sai daqui.
    """
    titulo = titulo_doc(md, fm, corpo)
    titulo = re.sub(r"^[^\w(]*", "", titulo)                    # emoji inicial
    titulo = re.sub(r"^mapa\s+de\s+estudo\s*[—–:-]\s*", "", titulo, flags=re.I)
    return titulo.strip() or md.stem


def coletar_mapa(md: Path) -> dict | None:
    """Extrai do mapa de matéria os tópicos do edital, com seus subtópicos.

    É o insumo da aba **Plano**: o que o edital exige, com ou sem aprofundamento
    pronto. O progresso daqui é contado SEPARADAMENTE do aprofundamento — os 24
    mapas do vault somam 2.220 checkboxes, nenhum marcado, e misturá-los com os ~200
    do aprofundamento apagaria a única barra que hoje significa algo.
    """
    fm = ler_frontmatter(md)
    corpo = fm.get("_corpo", "")
    if PLACEHOLDER_RE.search(corpo):
        return None

    topicos, auxiliares = [], []
    for bloco in re.split(r"^##\s+", corpo, flags=re.MULTILINE)[1:]:
        linhas = bloco.split("\n")
        titulo_bruto = linhas[0].strip()
        conteudo = "\n".join(linhas[1:])
        if H2_DESCARTAR.search(titulo_bruto):
            continue

        m = TOPICO_NUMERADO.match(titulo_bruto)
        if not m:
            auxiliares.append({"titulo": _prioridade_do_titulo(titulo_bruto)[0],
                               "corpo": conteudo.strip()})
            continue

        titulo, prio = _prioridade_do_titulo(m.group(2))
        blocos = blocos_do_topico(conteudo)
        # de TODOS os blocos de subtópicos, cada item carregando de qual bloco veio.
        # O grupo junta o sufixo do H3 e o H4 interno: os dois dizem de que parte da
        # matéria aquele checklist é, e sem eles quatro listas viram uma só.
        subtopicos = [dict(i, grupo=" · ".join(p for p in (b["sufixo"],
                                                           i.get("subgrupo")) if p))
                      for b in blocos if b["chave"] == "subtopicos"
                      for i in b["itens"]]
        topicos.append({
            "numero": int(m.group(1)),
            "titulo": titulo,
            "slug": slug_doc(titulo),
            "prioridade": prio,
            "subtopicos": subtopicos,
            "blocos": blocos,
            "progresso": contar_progresso(conteudo),
        })

    if not topicos and not auxiliares:
        return None
    prog = contar_progresso(corpo)
    return {
        "arquivo": md.name,
        "caminho": str(md),
        "materia_id": (fm.get("materia_id") or "").strip() or slug_doc(md.name),
        "titulo": fm.get("materia") or nome_materia_do_mapa(md, fm, corpo),
        "topicos": topicos,
        "auxiliares": auxiliares,
        "n_topicos": len(topicos),
        "progresso": prog,
        # rótulos de H3 fora do template. São publicados do mesmo jeito; ficam
        # listados aqui para a geração poder AVISAR que apareceu forma nova — é
        # como se descobre que um mapa novo inventou uma seção.
        "rotulos_extras": sorted({b["rotulo"] for t in topicos
                                  for b in t["blocos"]
                                  if b["chave"] == CHAVE_EXTRA}),
    }


def achar_mapas(escopo_dir: Path) -> dict[str, Path]:
    """Mapas de matéria do escopo, indexados pelo slug da matéria.

    `03-MAPAS-MATERIAS` (por cargo) e `03-MAPAS-COMUNS` (o que o SEDES usa no
    _COMUM) são dois nomes para a mesma coisa.
    """
    achados: dict[str, Path] = {}
    for nome in ("03-MAPAS-MATERIAS", "03-MAPAS-COMUNS"):
        pasta = escopo_dir / nome
        if not pasta.is_dir():
            continue
        for md in sorted(pasta.glob("*.md")):
            if DOCS_NAO_PUBLICAVEIS.match(md.stem):
                continue
            achados.setdefault(slug_doc(md.name), md)
    return achados


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
    por_slug: dict[str, dict] = {}
    for materia_dir in achar_materias(escopo_dir):
        m = coletar_materia(materia_dir)
        if m:
            materias.append(m)
            por_slug[m["slug"]] = m

    # Uma matéria, duas visões: o mapa (Plano) e o aprofundamento (Estudo) casam
    # pelo slug. Mapa sem aprofundamento vira matéria só com Plano — antes
    # `coletar_materia()` devolvia None sem `assuntos/` e a matéria era descartada
    # em silêncio, o que sumia com o plano de estudo inteiro do cargo.
    por_materia_id = {m["materia_id"]: m for m in materias if m.get("materia_id")}
    for slug, md_mapa in achar_mapas(escopo_dir).items():
        mapa = coletar_mapa(md_mapa)
        if not mapa:
            continue
        # `materia_id` primeiro, nome de pasta como reserva: é o id que resolve o
        # caso real de o mapa e o aprofundamento usarem slugs diferentes para a
        # mesma matéria.
        alvo = por_materia_id.get(mapa["materia_id"]) or por_slug.get(slug)
        if alvo is not None:
            alvo["mapa"] = mapa
        else:
            materias.append({
                "nome": mapa["titulo"], "slug": slug, "dir": str(md_mapa.parent),
                "materia_id": mapa["materia_id"],
                "doc_banca": None, "docs_apoio": [], "mapa_localizacao": None,
                "assuntos": [], "n_assuntos": 0,
                # nada de zero fixo aqui: `atualizar_progresso` conta o mapa, que
                # nestas matérias tem de 35 a 176 itens — era o zero à mão que
                # apagava o único trabalho que elas têm
                "n_com_podcast": 0, "n_com_flashcards": 0,
                "por_prioridade": {p: 0 for p in PRIORIDADES},
                "mapa": mapa,
            })
    materias.sort(key=lambda m: m["slug"])

    secoes.sort(key=lambda s: (s["ordinal"], s["slug"]))
    escopo = {
        "tipo": "comum" if nome.upper() in ("_COMUM", "COMUM") else "cargo",
        "nome": nome,
        "slug": re.sub(r"[^a-z0-9-]+", "-", norm(nome).strip("_")).strip("-") or "escopo",
        "secoes": secoes,
        "materias": materias,
        "n_materias": len(materias),
        "n_assuntos": sum(m["n_assuntos"] for m in materias),
        "progresso_documentos": somar_progressos(
            *[d["progresso"] for s in secoes for d in s["documentos"]]),
        "progresso_status": progresso_do_status(escopo_dir),
    }
    atualizar_progresso(escopo)
    return escopo


def atualizar_progresso(escopo: dict) -> None:
    """Recalcula as tarefas do escopo e das suas matérias.

    Roda duas vezes: em `coletar_escopo`, para o escopo isolado fazer sentido, e
    de novo depois de `cruzar_materias_comuns`, que é quando `mapa_em` passa a
    existir e revela qual mapa é emprestado. É idempotente de propósito.

    As parcelas não se sobrepõem, e por construção: o `99-Status.md` fica na RAIZ
    do escopo (fora das pastas de `SECOES`) e é barrado por
    `DOCS_NAO_PUBLICAVEIS`; e a seção herdada do `_COMUM` é um PONTEIRO com
    `documentos: []`, então a bibliografia comum nunca conta no cargo.
    """
    for m in escopo["materias"]:
        m["progresso"] = progresso_da_materia(m)
    escopo["progresso"] = somar_progressos(*[m["progresso"]
                                             for m in escopo["materias"]])
    escopo["progresso_tarefas"] = somar_progressos(
        escopo["progresso"], escopo["progresso_documentos"],
        escopo["progresso_status"])


# Seções do `_COMUM` que valem para quem estuda por um cargo. `04-MATERIAIS` é a
# bibliografia: quem é do cargo X precisa ver, num lugar só, o que se aplica a ele.
# As outras (edital, histórico, sinergia) ficam de fora por enquanto — herdar tudo
# encheria o galho do cargo com o comum inteiro, e a decisão foi sobre material.
SECOES_HERDAVEIS = ("materiais",)


def herdar_secoes_comuns(escopos: list[dict]) -> None:
    """Faz o galho do cargo enxergar as seções do `_COMUM` que se aplicam a ele.

    Sem isto, a página de Materiais **some em silêncio** no cargo: a coleta é
    estritamente por escopo, e três filtros em cascata (aqui, `montar_rotas` e
    `pagina_escopo`) descartam a seção inexistente sem avisar. Medido no vault em
    03/08/2026: 5 dos 7 escopos não têm `04-MATERIAIS`, então quem estuda por um
    cargo não tem NENHUM caminho de navegação até a bibliografia.

    Herda por REFERÊNCIA, nunca por cópia. O conteúdo continua morando no
    `_COMUM`; o cargo ganha um ponteiro que o builder transforma em link. Copiar
    os anexos para cada cargo multiplicaria os PDFs no disco — é o mesmo defeito
    que já fez o site pular de 78 para 685 PDFs quando os anexos passaram a ser
    copiados por documento em vez de por seção.
    """
    comum = next((e for e in escopos if e["tipo"] == "comum"), None)
    if not comum:
        return
    for herdavel in SECOES_HERDAVEIS:
        origem = next((s for s in comum["secoes"] if s["slug"] == herdavel), None)
        if not origem:
            continue
        ponteiro = {
            "escopo": comum["nome"], "escopo_slug": comum["slug"],
            "secao_slug": origem["slug"], "rotulo": origem["rotulo"],
            "n_documentos": origem["n_documentos"], "n_anexos": origem["n_anexos"],
        }
        for escopo in escopos:
            if escopo is comum or escopo["tipo"] == "geral":
                continue
            # o cargo só herda se tiver conteúdo próprio — cargo sem matéria
            # nenhuma não precisa de página de bibliografia
            if not escopo["materias"]:
                continue
            propria = next((s for s in escopo["secoes"] if s["slug"] == herdavel), None)
            if propria:
                propria["herdado_de"] = ponteiro
                continue
            escopo["secoes"].append({
                "ordinal": origem["ordinal"], "rotulo": origem["rotulo"],
                "slug": origem["slug"], "registro": origem["registro"],
                "modo": origem["modo"], "dir": "",
                "documentos": [], "anexos": [],
                "n_documentos": 0, "n_anexos": 0, "bytes_anexos": 0,
                "herdado_de": ponteiro,
            })
        comum_secao = origem
        comum_secao.setdefault("herdada_por", [])
        comum_secao["herdada_por"] = [
            e["nome"] for e in escopos
            if e is not comum and e["tipo"] != "geral" and e["materias"]
        ]
    for escopo in escopos:
        escopo["secoes"].sort(key=lambda s: (s["ordinal"], s["slug"]))


def cruzar_materias_comuns(escopos: list[dict]) -> None:
    """Liga as duas metades de uma matéria que vive em escopos diferentes.

    Caso real e frequente: no BB o mapa de Língua Portuguesa está na pasta de CADA
    cargo, mas o aprofundamento está no `_COMUM`; no SEDES, o mapa de Serviço Social
    está no ASSISTENTE-SOCIAL e o aprofundamento no `_COMUM`. Sem cruzar, a página
    do cargo mostraria um plano sem conteúdo e a do comum um conteúdo sem plano,
    ambas parecendo incompletas quando o material está todo lá.

    É a decisão "espelho + atalhos": a estrutura continua a do vault, e o atalho
    torna a origem explícita em vez de duplicar material.
    """
    comum = next((e for e in escopos if e["tipo"] == "comum"), None)
    if not comum:
        return
    por_slug = {m["slug"]: m for m in comum["materias"]}
    por_id = {m["materia_id"]: m for m in comum["materias"] if m.get("materia_id")}

    for escopo in escopos:
        if escopo is comum:
            continue
        for mat in escopo["materias"]:
            # o id vem primeiro: é ele que casa `direitos-violacoes` (aprofundamento
            # no comum) com `direitos-violacoes-vulnerabilidades` (mapa no cargo)
            irma = por_id.get(mat.get("materia_id")) or por_slug.get(mat["slug"])
            if not irma:
                continue
            if not mat["assuntos"] and irma["assuntos"]:
                mat["aprofundamento_em"] = {
                    "escopo_slug": comum["slug"], "escopo_nome": comum["nome"],
                    "materia_slug": irma["slug"], "n_assuntos": irma["n_assuntos"],
                }
                # Os assuntos da irmã ficam numa chave PRÓPRIA, nunca em
                # `assuntos`. É o que permite à aba Estudo do cargo existir
                # (senão a matéria fica só com o Plano, que era o defeito) sem
                # que os mesmos checkboxes contem no cargo E no comum — a
                # agregação de progresso lê `assuntos`, e só ela.
                mat["assuntos_herdados"] = irma["assuntos"]
            if not irma.get("mapa") and mat.get("mapa"):
                # ANEXAR o mapa, não só apontar para ele. `mapa_em` sozinho era
                # dado morto: gravado e nunca lido, então a matéria do comum
                # aparecia sem aba Plano mesmo com o plano existindo no cargo —
                # que é exatamente o caso de "Direitos e Violações (EDAS)".
                irma["mapa"] = mat["mapa"]
                irma["mapa_em"] = {
                    "escopo_slug": escopo["slug"], "escopo_nome": escopo["nome"],
                    "materia_slug": mat["slug"],
                }
            elif irma.get("mapa") and mat.get("mapa") and irma is not mat:
                # mesma matéria mapeada em mais de um cargo (o `especificos-cargo`
                # do SEDES atende Agente e Cuidador): registrar os outros para a
                # página poder oferecê-los, em vez de escolher um em silêncio
                irma.setdefault("mapas_extras", []).append({
                    "escopo_slug": escopo["slug"], "escopo_nome": escopo["nome"],
                    "mapa": mat["mapa"],
                })


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


def calcular_cobertura(escopos: list[dict]) -> None:
    """Cobertura de cada matéria, DEPOIS que mapa e aprofundamento se acharam.

    Rodar antes do cruzamento dava 0% em `direitos-violacoes` e `servico-social`:
    o mapa está no cargo e os assuntos no _COMUM, e cada metade sozinha não sabe
    da outra.
    """
    por_id = {}
    for e in escopos:
        for m in e["materias"]:
            if m["assuntos"]:
                por_id.setdefault(m.get("materia_id") or m["slug"], m["assuntos"])
    for e in escopos:
        for m in e["materias"]:
            irma = por_id.get(m.get("materia_id") or m["slug"])
            m["cobertura"] = cobertura_da_materia(
                m, m["assuntos"] if m["assuntos"] else irma)
        # o agregado só existe depois que TODAS as matérias do escopo têm a sua.
        # A matéria emprestada entra no denominador do cargo de propósito: o
        # tópico é do edital daquele cargo, ainda que o material more no comum.
        e["cobertura"] = cobertura_do_escopo(e["materias"])


def avisar_rotulos_extras(escopos: list[dict]) -> list[str]:
    """Avisa quais H3 do mapa saíram do template. Publicar sem avisar esconderia
    que o template e o vault divergiram; avisar sem publicar era o bug antigo."""
    extras: dict[str, int] = {}
    for e in escopos:
        for mat in e["materias"]:
            for rot in ((mat.get("mapa") or {}).get("rotulos_extras") or []):
                extras[rot] = extras.get(rot, 0) + 1
    if extras:
        lista = ", ".join(f"{r} ({n}×)" for r, n in sorted(extras.items()))
        sys.stderr.write(f"AVISO: seções de tópico fora do template do mapa "
                         f"(publicadas assim mesmo): {lista}\n")
    return sorted(extras)


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
        # O progresso é somado de verdade: zerar à mão aqui deixava o escopo com
        # matérias reais exibindo barra vazia. Documentos e status ficam em zero
        # porque neste layout não existe pasta de escopo para varrer — não há
        # `SECOES` nem `99-Status.md` fora de um escopo.
        geral = {
            "tipo": "geral", "nome": "_GERAL", "slug": "geral",
            "secoes": [], "materias": soltas,
            "n_materias": len(soltas),
            "n_assuntos": sum(m["n_assuntos"] for m in soltas),
            "progresso_documentos": {"total": 0, "feitos": 0},
            "progresso_status": {"total": 0, "feitos": 0},
        }
        atualizar_progresso(geral)
        escopos.append(geral)

    # `_COMUM` primeiro (é o que vale para todos), cargos em ordem alfabética
    escopos.sort(key=lambda e: (e["tipo"] != "comum", e["nome"]))
    cruzar_materias_comuns(escopos)
    # de novo, agora que `mapa_em` existe: só depois do cruzamento se sabe qual
    # mapa é emprestado e, portanto, qual não deve entrar na soma deste escopo
    for e in escopos:
        atualizar_progresso(e)
    herdar_secoes_comuns(escopos)
    calcular_cobertura(escopos)
    avisar_rotulos_extras(escopos)

    return {
        "concurso": base.name,
        "dir": str(base),
        # Allowlist deliberada: o modelo do site é contrato público e não deve
        # carregar o `.meta.json` inteiro. `cargos_validados` entrou porque vagas e
        # salário vivem LÁ num concurso multi-cargo — sem ele, os dois campos nunca
        # renderizavam, já que a raiz não tem número que represente 3 cargos com
        # vagas e salários diferentes.
        "meta": {k: v for k, v in meta.items() if k in
                 ("orgao", "ano", "banca", "modo", "datas_chave", "estrutura_prova",
                  "vagas_ac", "vagas_total", "salario", "cargos_validados")},
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
