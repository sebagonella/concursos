#!/usr/bin/env python3
"""
site_builder.py - Subsistema B da skill concurso-publica.

Consome o modelo produzido pelo site_collector.py e gera o site estático:
  - capa do concurso (ficha da prova + matérias)
  - índice por matéria (assuntos com selos de mídia e progresso)
  - página por assunto (resumo + mídias embutidas + quiz de flashcards)

Princípios (decisões aprovadas):
  - Site SÓ LEITURA: o progresso vem do vault e é exibido, nunca editado.
  - Mídia ausente = seção ausente, sem quebrar.
  - Assets locais (sem CDN): o site funciona offline / na rede doméstica.
  - Botão "Abrir no NotebookLM" só se notebooklm_url estiver preenchida.

Uso:
    python site_builder.py --concurso-dir <.../CONCURSOS/SEDES_2026> --out out/site
    python site_builder.py --modelo site-model.json --out out/site
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import md2html  # noqa: E402
from aprofundamento_id import FONTE_PROPRIA  # noqa: E402
from site_collector import coletar_concurso, CATALOGO_MIDIAS, PRIORIDADES  # noqa: E402

ASSETS = AQUI.parent / "assets"


# --------------------------------------------------------------------------- #
# helpers de HTML
# --------------------------------------------------------------------------- #
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def nome_legivel(slug: str) -> str:
    """SEDES_2026 -> SEDES 2026 · BB_2027_PREVISTO -> BB 2027 (previsto)."""
    s = slug.replace("_", " ").strip()
    s = re.sub(r"\bPREVISTO\b", "(previsto)", s)
    s = re.sub(r"\bV(\d+)[- ]OFICIAL\b", r"— oficial (v\1)", s)
    s = re.sub(r"\bV(\d+)[- ]RETIFICADO\b", r"— retificado (v\1)", s)
    return re.sub(r"\s{2,}", " ", s).strip()


# --------------------------------------------------------------------------- #
# rotas: onde cada página mora, decidido ANTES de renderizar
# --------------------------------------------------------------------------- #
# Toda rota é um caminho POSIX relativo à raiz do site, e todo link emitido é
# relativo — é o que permite servir o mesmo site na raiz ou num subpath.
def prefixo_de(rota: str) -> str:
    """Caminho da página até a raiz: `a/b/index.html` → `../../`."""
    return "../" * (len(PurePosixPath(rota).parts) - 1)


def relativo(destino: str, de_rota: str) -> str:
    """URL relativa da página em `de_rota` até `destino` (rota, âncora opcional).

    Substitui os prefixos literais (`"../"`, `"../../"`, `"../../../"`) que
    estavam espalhados pelos templates. Cada nível novo de pasta exigia acertar
    todos eles na mão, e prefixo errado é historicamente a regressão mais comum
    desta skill.
    """
    alvo, _, frag = destino.partition("#")
    partes = PurePosixPath(alvo).parts
    dir_alvo, nome_alvo = partes[:-1], partes[-1]
    dir_atual = PurePosixPath(de_rota).parts[:-1]
    i = 0
    while i < len(dir_atual) and i < len(dir_alvo) and dir_atual[i] == dir_alvo[i]:
        i += 1
    passos = [".."] * (len(dir_atual) - i) + list(dir_alvo[i:]) + [nome_alvo]
    return "/".join(passos) + (f"#{frag}" if frag else "")


class Rotas:
    """Índice `nome-de-arquivo-do-vault → rota no site`.

    Existe por causa do resolvedor de wikilinks: para virar `href`, `[[crase]]`
    precisa da URL de uma página que talvez ainda não tenha sido gerada. Num passo
    único isso é impossível — e era justamente por isso que o resolvedor anterior
    só conseguia ver assuntos irmãos da mesma matéria, deixando morto todo wikilink
    que atravessasse matéria ou apontasse para documento.

    Três classes de alvo, porque nem todo alvo é página:
      - **página**       → rota da página;
      - **artefato embutido** (flashcards) → rota da página que o hospeda + âncora;
      - **arquivo copiado** (mídia, anexo) → rota do arquivo dentro do site.
    Sem essa distinção, os 368 wikilinks de mídia dos pacotes NotebookLM viravam
    parede de link morto.
    """

    EXTENSOES = re.compile(
        r"\.(md|png|jpe?g|svg|webp|pdf|m4a|mp3|wav|ogg|mp4|webm|mov|csv|tsv|txt|pptx)$",
        re.IGNORECASE)

    def __init__(self) -> None:
        self._por_nome: dict[str, str] = {}
        # Rotas de páginas efetivamente emitidas. Serve para NAVEGAÇÃO — que é
        # calculada da rota da própria página —, nunca para resolver wikilink:
        # nomes repetem entre escopos, e usar o índice de nomes para navegar foi
        # o que fez o hub do cargo apontar para a matéria do comum.
        self._paginas: set[str] = set()
        # Âncora de bloco -> rota da página que a CONTÉM. Existe porque o nome do
        # arquivo não desambigua: há um `livros-recomendados.md` por escopo, e
        # `Rotas.chave` reduz tudo ao basename — um `[[livros-recomendados#^mat-x]]`
        # caía sempre na primeira página registrada, e 160 links de material
        # apontaram para uma âncora que não existia naquela página. A âncora, essa,
        # é única dentro do concurso.
        self._por_ancora: dict[str, str] = {}

    @classmethod
    def chave(cls, nome: str) -> str:
        """Último segmento, sem extensão, minúsculo — como o Obsidian casa.

        Os wikilinks do SEDES usam caminho absoluto do vault
        (`[[_COMUM/03-APROFUNDAMENTO/…/crase]]`) e os do BB, nome nu (`[[crase]]`).
        Reduzir os dois ao basename faz as duas convenções caírem na mesma chave.
        """
        base = (nome or "").strip().rstrip("/").split("/")[-1]
        return cls.EXTENSOES.sub("", base).lower()

    def registrar_ancora(self, ancora: str, rota: str) -> None:
        self._por_ancora.setdefault(ancora.lstrip("^").lower(), rota)

    def rota_da_ancora(self, ancora: str) -> str | None:
        return self._por_ancora.get((ancora or "").lstrip("^").lower())

    def marcar(self, rota: str) -> None:
        """Registra que esta rota vira página, sem associá-la a nome nenhum."""
        self._paginas.add(rota)

    def tem_pagina(self, rota: str) -> bool:
        return rota in self._paginas

    def registrar(self, rota: str, *nomes: str, ancora: str = "") -> None:
        """Associa nomes do vault a uma rota. O primeiro registro vence, para uma
        página não ser sequestrada por um homônimo registrado depois."""
        destino = rota + (f"#{ancora}" if ancora else "")
        self._paginas.add(rota)
        for nome in nomes:
            chave = self.chave(nome)
            if chave:
                self._por_nome.setdefault(chave, destino)

    def rota_de(self, nome: str) -> str | None:
        return self._por_nome.get(self.chave(nome))

    def resolvedor(self, rota_atual: str):
        """Closure no formato que o `md2html` espera: `(alvo, âncora) → href`.

        A âncora VENCE o nome quando ela existe: é o único dos dois que
        desambigua entre os sete `livros-recomendados.md` do concurso.
        """
        def resolver(alvo: str, ancora: str = "") -> str | None:
            destino = self.rota_da_ancora(ancora) if ancora else None
            if not destino:
                destino = self._por_nome.get(self.chave(alvo))
            return relativo(destino, rota_atual) if destino else None
        return resolver


_ANCORA_BLOCO = re.compile(r"^\s*\^([A-Za-z0-9][A-Za-z0-9-]*)\s*$", re.M)


def _registrar_ancoras(rotas: "Rotas", doc: dict, rota: str) -> None:
    """Indexa os block ids do documento, para o wikilink com âncora resolver
    para a página que REALMENTE a contém — e não para a primeira homônima."""
    try:
        texto = Path(doc["caminho"]).read_text(encoding="utf-8")
    except OSError:
        return
    for m in _ANCORA_BLOCO.finditer(texto):
        rotas.registrar_ancora(m.group(1), rota)


def rota_irma(rota: str, *segmentos: str) -> str:
    """Rota de uma página vizinha, derivada da rota da página atual.

    A navegação interna do site NÃO pode passar pelo índice de nomes: ele resolve
    por basename e o primeiro registro vence, então com `lingua-portuguesa` no
    `_COMUM` e no cargo, o hub do cargo apontava para a matéria do comum e a sua
    própria ficava órfã. O índice existe para wikilink, onde a ambiguidade é
    inerente; link de navegação é sempre explícito.
    """
    return "/".join([str(PurePosixPath(rota).parent), *segmentos, "index.html"])


def rota_anexo(rota_secao: str, anexo: dict) -> str:
    """Rota de um anexo dentro da seção, preservando a subpasta do vault.

    Fonte única: o registro em `montar_rotas`, o link na página e a cópia do arquivo
    usam esta mesma função. Calcular em três lugares seria convite a divergir — e
    nomes de arquivo repetem entre cargos (`cronograma-macro.md` existe em três),
    então resolver por nome levaria ao arquivo do cargo errado.
    """
    sub = (anexo["subpasta"] + "/") if anexo["subpasta"] else ""
    return f'{PurePosixPath(rota_secao).parent}/arquivos/{sub}{anexo["arquivo"]}'


def ident_aprof(ap: dict, indice: int = 0) -> str:
    """Identificador do aprofundamento usado em pasta de mídia e em `data-aprof`.
    Vive numa função só porque o builder o calculava em dois lugares — e os dois
    tinham de continuar concordando, ou a mídia ia para uma pasta e o HTML
    apontava para outra."""
    return re.sub(r"[^A-Za-z0-9_+-]+", "-",
                  ap.get("aprofundamento") or f"a{indice}")


def nome_escopo(nome: str) -> str:
    """Rótulo de exibição do escopo (`_COMUM` ou um cargo).

    O underscore de `_COMUM` é convenção de PASTA — existe para o Obsidian ordenar
    a pasta antes dos cargos. Numa página web ele lê como nome de arquivo vazado.
    O nome do cargo, ao contrário, fica como está: é o vocabulário que o usuário
    reconhece do edital e do vault.
    """
    if nome in ("_GERAL", ""):
        return ""                      # escopo implícito: não há o que rotular
    if nome == "_COMUM":
        return "Comum a todos os cargos"
    return nome


_VERSAO_ASSET: dict[tuple, str] = {}


def versao_asset(nome: str) -> str:
    """Resumo do conteúdo do asset, para entrar na URL.

    Sem isto o navegador serve **HTML novo com CSS velho**, e o defeito é
    invisível: a página renderiza, só renderiza errado. Aconteceu de verdade —
    o nginx manda `expires 1h` e o telefone reaproveitou a folha antiga, então
    os rótulos das barras saíram no tipo do corpo e a barra de cobertura saiu
    verde (a cor que ela tinha na versão anterior).

    O cache é por (mtime, tamanho): rápido no build de 350 páginas e correto
    quando o arquivo muda no meio da mesma sessão, como nos testes.
    """
    caminho = ASSETS / nome
    try:
        st = caminho.stat()
    except OSError:
        return "0"
    chave = (nome, st.st_mtime_ns, st.st_size)
    if chave not in _VERSAO_ASSET:
        _VERSAO_ASSET[chave] = hashlib.sha256(caminho.read_bytes()).hexdigest()[:8]
    return _VERSAO_ASSET[chave]


def pagina(titulo: str, trilha_html: str, corpo: str, rota: str,
           descricao: str = "") -> str:
    """Esqueleto comum. `rota` é o caminho da própria página relativo à raiz do
    site; o prefixo até os assets sai dela, em vez de ser contado à mão."""
    prefixo = prefixo_de(rota)
    ano = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titulo)}</title>
{f'<meta name="description" content="{esc(descricao)}">' if descricao else ''}
<link rel="stylesheet" href="{prefixo}assets/site.css?v={versao_asset("site.css")}">
<script>
/* aplica o tema antes da pintura, para não piscar */
(function(){{try{{var t=localStorage.getItem("concursos:tema");
if(!t)t=(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches)?"escuro":"claro";
document.documentElement.setAttribute("data-tema",t);}}catch(e){{}}}})();
</script>
</head>
<body>
<header class="topo">
  <div class="topo-interno">
    <a class="marca" href="{prefixo}index.html">Estudo para concursos</a>
    <nav class="trilha">{trilha_html}</nav>
    <button class="tema-troca" type="button">☾ Escuro</button>
  </div>
</header>
<main class="folha">
{corpo}
</main>
<div class="lightbox" role="dialog" aria-label="Mapa mental ampliado"><img alt="Mapa mental ampliado"></div>
<footer class="rodape">
  Gerado a partir do vault em {ano}. Conteúdo de estudo — confira sempre o edital oficial.
</footer>
<script src="{prefixo}assets/site.js?v={versao_asset("site.js")}"></script>
</body>
</html>
"""


def medidor(linhas: list[dict], compacto: bool = False) -> str:
    """Barras lisas empilhadas — o indicador de AGREGADO.

    Cada linha é `{rotulo, feitos, total, classe, sufixo, indefinida, nota}`.
    Duas cores, ambas do mundo da prova: verde `--confere` (o visto: o que EU
    fiz) para tarefas, azul `--tinta` (a caneta: o que EXISTE) para material.

    A regra de exibição vive aqui e em nenhum outro lugar:

    - `total > 0` sempre aparece, inclusive com `feitos == 0` — esconder o zero
      faria a lacuna sumir justamente onde ela é maior;
    - `total == 0` some, porque não há denominador sobre o que afirmar nada;
    - `indefinida` desenha o trilho hachurado e escreve a ressalva, jamais 0%.
    """
    itens = []
    for ln in linhas:
        total = ln.get("total") or 0
        if not total and not ln.get("indefinida"):
            continue
        feitos = ln.get("feitos") or 0
        pct = round(100 * feitos / total) if total else 0
        if ln.get("indefinida"):
            conta = esc(ln.get("nota") or "desconhecida")
            barra = '<div class="barra-cobertura pequena indefinida"></div>'
            rotulo_aria = f'{ln["rotulo"]}: {ln.get("nota") or "desconhecida"}'
        else:
            conta = f'{feitos}/{total}'
            if ln.get("sufixo"):
                conta += f' · {esc(ln["sufixo"])}'
            if ln.get("nota"):
                conta += f' · {esc(ln["nota"])}'
            classe = f' {ln["classe"]}' if ln.get("classe") else ""
            pequena = " pequena" if compacto else ""
            rotulo_aria = f'{feitos} de {total} · {ln["rotulo"]}'
            barra = (f'<div class="barra-cobertura{pequena}{classe}" role="img"'
                     f' aria-label="{esc(rotulo_aria)}">'
                     f'<span style="width:{pct}%"></span></div>')
        cls_conta = " incerta" if ln.get("indefinida") else ""
        itens.append(
            f'<div class="medidor-linha"><div class="medidor-cabeca">'
            f'<span class="medidor-rotulo">{esc(ln["rotulo"])}</span>'
            f'<span class="medidor-conta{cls_conta}">{conta}</span></div>{barra}</div>')
    return f'<div class="medidor">{"".join(itens)}</div>' if itens else ""


def linhas_do_escopo(escopo: dict) -> list[dict]:
    """As duas medidas de um escopo: o que eu fiz e o que existe de material.

    A matéria sem vínculo fica fora do denominador (senão vira falso zero em
    escala de escopo), mas **nunca fica fora da página**: ou ressalva a barra
    medida, ou — quando não sobrou nada mensurável — é ela que a barra declara.
    """
    cb = escopo.get("cobertura") or {}
    sem_vinc = cb.get("n_sem_vinculo") or 0
    ressalva = f'{sem_vinc} matéria(s) sem vínculo' if sem_vinc else ""
    if not cb.get("n_topicos") and sem_vinc:
        cobertura = {"rotulo": "Tópicos do edital", "indefinida": True,
                     "nota": f'cobertura desconhecida · {ressalva}'}
    else:
        cobertura = {"rotulo": "Tópicos do edital",
                     "feitos": cb.get("n_cobertos", 0),
                     "total": cb.get("n_topicos", 0),
                     "sufixo": f'{cb["pct"]}%' if cb.get("pct") is not None else "",
                     "nota": ressalva}
    return [
        {"rotulo": "Tarefas de estudo", "classe": "tarefa",
         **(escopo.get("progresso_tarefas") or {})},
        cobertura,
    ]


def linhas_da_materia(materia: dict) -> list[dict]:
    """Mesmas duas medidas, mesma ordem — a matéria é o escopo em escala menor."""
    cb = materia.get("cobertura") or {}
    if cb.get("vinculo_ausente"):
        cobertura = {"rotulo": "Tópicos do edital", "indefinida": True,
                     "nota": f'cobertura desconhecida · '
                             f'{cb["n_assuntos"]} assunto(s) sem vínculo'}
    else:
        cobertura = {"rotulo": "Tópicos do edital",
                     "feitos": cb.get("n_cobertos", 0),
                     "total": cb.get("n_topicos", 0),
                     "sufixo": f'{cb["pct"]}%' if cb.get("pct") is not None else ""}
    return [
        {"rotulo": "Tarefas de estudo", "classe": "tarefa",
         **(materia.get("progresso") or {})},
        cobertura,
    ]


def bloco_estudo_herdado(materia: dict, rota: str) -> str:
    """A visão Estudo de uma matéria cujo aprofundamento mora no `_COMUM`.

    O cargo guarda o mapa e o comum guarda o material — é a forma real de três
    matérias do SEDES. Como `tem_estudo` olhava só `materia["assuntos"]`, essas
    matérias ficavam **só com o Plano**, apesar de a cobertura já afirmar 40%,
    60% e 25% de aprofundamento: o caminho até o material existia numa frase
    solta e a aba, não.

    Nada é copiado. Os cards apontam para a página do assunto no outro escopo, e
    os assuntos vêm de `assuntos_herdados` — chave à parte, que a agregação de
    progresso ignora, senão os mesmos checkboxes contariam nos dois escopos.
    """
    externo = materia.get("aprofundamento_em")
    herdados = materia.get("assuntos_herdados") or []
    if not externo or not herdados:
        return ""
    cards = "".join(card_assunto(a, rota_da_materia_irma(externo, rota, a["slug"]))
                    for a in herdados)
    onde = nome_escopo(externo["escopo_nome"]) or externo["escopo_nome"]
    return (f'<section class="grupo"><header><h2>Assuntos aprofundados</h2>'
            f'<span class="quantos">{len(herdados)} assunto(s)</span></header>'
            f'<p class="explica">O material desta matéria vale para todos os cargos '
            f'e fica em <strong>{esc(onde)}</strong>, num lugar só — '
            f'estes cards abrem lá.</p>'
            f'<div class="grade">{cards}</div></section>')


def rota_da_materia_irma(externo: dict, rota: str, assunto: str = "") -> str:
    """Caminho relativo até a matéria (ou o assunto) do outro escopo.

    `rota_irma()` não serve aqui: ela troca o último segmento, e a irmã está dois
    níveis acima, noutro escopo. O cálculo estava embutido em `bloco_cobertura`;
    fica num lugar só porque a aba Estudo herdada precisa do mesmo destino.
    """
    conc = PurePosixPath(rota).parts[0]
    destino = (f'{conc}/{externo["escopo_slug"]}/materias/'
               f'{externo["materia_slug"]}/')
    destino += f'{assunto}/index.html' if assunto else "index.html"
    return relativo(destino, rota)


def barra_de_tarefas(progresso: dict) -> str:
    """A medida de tarefas sozinha — para o assunto, que não tem cobertura.

    Aqui morava o `gabarito()`, as bolhas do cartão-resposta. Elas saíram do
    progresso porque o site passou a ter dois jeitos de mostrar o mesmo número
    em telas vizinhas: barra no card da matéria, bolha no card do assunto. A
    bolha continua viva onde não mede progresso — o selo de nível (meia =
    padrão, cheia = detalhado) e o marcador das listas de tarefa.
    """
    return medidor([{"rotulo": "Tarefas de estudo", "classe": "tarefa",
                     **(progresso or {})}], compacto=True)


def selos_midia(assunto: dict, so_presentes: bool = False) -> str:
    """Selos das mídias. Por padrão mostra também as ausentes (em cinza),
    o que ajuda a ver o que ainda falta gerar no NotebookLM."""
    partes = []
    for chave, (_pref, _ext, icone, rotulo) in CATALOGO_MIDIAS.items():
        tem = bool(assunto["midias"].get(chave))
        if so_presentes and not tem:
            continue
        cls = "selo" if tem else "selo ausente"
        partes.append(f'<span class="{cls}" title="{esc(rotulo)}">{icone}</span>')
    n = assunto["flashcards"].get("n_cards", 0)
    if n or not so_presentes:
        cls = "selo" if n else "selo ausente"
        partes.append(f'<span class="{cls}" title="Cartões didáticos">🃏 {n}</span>')
    return f'<div class="selos">{"".join(partes)}</div>' if partes else ""


# --------------------------------------------------------------------------- #
# flashcards -> JSON para o quiz
# --------------------------------------------------------------------------- #
def parsear_flashcards(caminho: Path) -> list[dict]:
    """Lê o .md de flashcards (multiline '??' ou singleline '::')."""
    try:
        txt = caminho.read_text(encoding="utf-8")
    except Exception:
        return []
    txt = re.sub(r"^---\s*\n.*?\n---\s*\n", "", txt, count=1, flags=re.DOTALL)
    txt = re.sub(r"<!--.*?-->", "", txt, flags=re.DOTALL)
    cards = []

    linhas = txt.split("\n")
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        # multiline: pergunta / ?? / resposta
        if linha == "??" and i > 0:
            frente = linhas[i - 1].strip()
            resposta = []
            j = i + 1
            while j < len(linhas) and linhas[j].strip() and linhas[j].strip() != "??":
                resposta.append(linhas[j].strip())
                j += 1
            if frente and resposta and not frente.startswith((">", "#")):
                cards.append({"f": frente, "v": " ".join(resposta)})
            i = j
            continue
        # singleline: pergunta::resposta
        if "::" in linha and not linha.startswith((">", "#", "-")):
            f, _, v = linha.partition("::")
            if f.strip() and v.strip():
                cards.append({"f": f.strip(), "v": v.strip()})
        i += 1
    return cards


def bloco_quiz(cards: list[dict], link_vault: str | None) -> str:
    if not cards:
        return ""
    dados = json.dumps(cards, ensure_ascii=False)
    # id âncora: os flashcards não são página própria, então os wikilinks que
    # apontam para o `.md` do baralho são resolvidos para cá (ver Rotas)
    return f"""<section class="cartao quiz" id="flashcards">
  <h3>Flashcards ({len(cards)})</h3>
  <div class="carta" role="button" aria-label="Cartão — clique para virar">
    <span class="frente"></span><span class="verso"></span>
  </div>
  <div class="controles">
    <span class="posicao"></span>
    <span>
      <button class="botao secundario" data-acao="virar">Virar</button>
      <button class="botao" data-acao="proxima">Próximo</button>
    </span>
  </div>
  <div class="controles">
    <button class="botao secundario" data-acao="embaralhar">Embaralhar</button>
  </div>
  <p class="dica">Clique no cartão ou use espaço para virar, seta direita para avançar.
  Para revisão espaçada com agendamento, use o baralho no Obsidian.</p>
  <script type="application/json">{dados}</script>
</section>"""


# --------------------------------------------------------------------------- #
# páginas
# --------------------------------------------------------------------------- #
ROTULO_NIVEL = {"detalhado": "Detalhado", "padrao": "Padrão"}


def rotulo_aprof(ap: dict) -> str:
    """Rótulo legível de um aprofundamento: fonte + nível.

    O slug da fonte vem primeiro porque é curto e desenhado para ser lido
    (`pestana`, `lei-8742`). O campo `fontes` do frontmatter costuma guardar o
    **nome do arquivo** do livro, e truncá-lo em 42 caracteres produzia abas como
    "A-Gramatica-para-Concursos-Fernando-Pest… · Detalhado", que não distinguem nada
    quando há duas versões do mesmo livro.
    """
    nivel = ROTULO_NIVEL.get(ap.get("nivel", ""), ap.get("nivel", ""))
    slugs = ap.get("fontes_id") or []
    # `proprio` é token de PATH, não nome de fonte: title-case o transformaria em
    # "Proprio", que não descreve nada e ainda por cima sem acento
    if slugs == [FONTE_PROPRIA]:
        return f"Material próprio · {nivel}"
    if slugs:
        bonito = " + ".join(s.replace("-", " ").title() for s in slugs)
        return f"{bonito} · {nivel}"
    fontes = (ap.get("fontes") or "").strip()
    if fontes:
        curto = fontes if len(fontes) <= 42 else fontes[:40] + "…"
        return f"{curto} · {nivel}"
    ident = ap.get("aprofundamento", "")
    if ident in ("unico", "original", ""):
        return f"Material original · {nivel}"
    return f"{ident} · {nivel}"


def bloco_aprofundamento(ap: dict, materia: dict, assunto: dict, destino_dir: Path,
                         indice: int, ativo: bool,
                         rotas: "Rotas", rota: str) -> tuple[str, str]:
    """Renderiza UM aprofundamento: corpo (coluna esquerda) + cartões (lateral)."""
    origem_dir = Path(ap["resumo_md"]).parent

    corpo_md = Path(ap["resumo_md"]).read_text(encoding="utf-8")
    corpo_html = md2html.converter(corpo_md,
                                   wikilink_resolver=rotas.resolvedor(rota))

    # mídias deste aprofundamento vão para media/<id>/ (não colidem entre si)
    ident = ident_aprof(ap, indice)
    midia_dir = destino_dir / "media" / ident
    blocos = []

    def copiar(nome: str) -> str:
        midia_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem_dir / nome, midia_dir / nome)
        return f"media/{ident}/{nome}"

    def baixar(src: str, rotulo: str = "Baixar") -> str:
        nome = src.split("/")[-1]
        return (f'<a class="baixar" href="{esc(src)}" download="{esc(nome)}">'
                f'⤓ {esc(rotulo)}</a>')

    def cabecalho(rotulo: str, src: str) -> str:
        return f'<div class="titulo-linha"><h3>{esc(rotulo)}</h3>{baixar(src)}</div>'

    m = ap["midias"]
    if m.get("podcast"):
        src = copiar(m["podcast"])
        blocos.append(f'<section class="cartao">{cabecalho("Resumo em áudio", src)}'
                      f'<audio controls preload="none" src="{esc(src)}"></audio></section>')
    if m.get("video"):
        src = copiar(m["video"])
        blocos.append(f'<section class="cartao">{cabecalho("Resumo em vídeo", src)}'
                      f'<video controls preload="none" src="{esc(src)}"></video></section>')
    if m.get("mapa_mental"):
        src = copiar(m["mapa_mental"])
        blocos.append(f'<section class="cartao mapa-mental">{cabecalho("Mapa mental", src)}'
                      f'<img src="{esc(src)}" alt="Mapa mental" loading="lazy"></section>')
    if m.get("infografico"):
        src = copiar(m["infografico"])
        if src.lower().endswith(".pdf"):
            blocos.append(f'<section class="cartao">{cabecalho("Infográfico", src)}'
                          f'<a class="botao secundario" href="{esc(src)}" target="_blank" '
                          f'rel="noopener">Abrir infográfico</a></section>')
        else:
            blocos.append(f'<section class="cartao mapa-mental">{cabecalho("Infográfico", src)}'
                          f'<img src="{esc(src)}" alt="Infográfico" loading="lazy"></section>')
    if m.get("slides"):
        src = copiar(m["slides"])
        blocos.append(f'<section class="cartao">{cabecalho("Apresentação de slides", src)}'
                      f'<a class="botao secundario" href="{esc(src)}" target="_blank" '
                      f'rel="noopener">Abrir slides</a></section>')

    extras = []
    for chave in ("teste", "tabela"):
        if m.get(chave):
            src = copiar(m[chave])
            _p, _e, icone, rotulo = CATALOGO_MIDIAS[chave]
            extras.append(f'<li><span class="rot">{icone} {esc(rotulo)}</span>{baixar(src)}</li>')
    if extras:
        blocos.append(f'<section class="cartao"><h3>Outros materiais</h3>'
                      f'<ul class="midias-extra">{"".join(extras)}</ul></section>')

    fc = ap["flashcards"].get("obsidian")
    if fc:
        cards = parsear_flashcards(origem_dir / fc)
        b = bloco_quiz(cards, None)
        if b:
            blocos.append(b)

    if ap.get("notebooklm_url"):
        blocos.append(f'<section class="cartao"><h3>NotebookLM</h3>'
                      f'<p style="font-size:.88rem;margin:0 0 .6rem">Mapa interativo e chat com as fontes.</p>'
                      f'<a class="botao secundario" target="_blank" rel="noopener" '
                      f'href="{esc(ap["notebooklm_url"])}">Abrir no NotebookLM</a></section>')

    if m.get("report"):
        rep = m["report"]
        if rep.lower().endswith((".md", ".txt")):
            src = copiar(rep)
            corpo_html += (f'\n<h2 id="relatorio">Relatório {baixar(src, "baixar")}</h2>\n'
                           + md2html.converter(
                               (origem_dir / rep).read_text(encoding="utf-8"),
                               wikilink_resolver=rotas.resolvedor(rota)))
        else:
            src = copiar(rep)
            blocos.append(f'<section class="cartao">{cabecalho("Relatório", src)}'
                          f'<a class="botao secundario" href="{esc(src)}" target="_blank" '
                          f'rel="noopener">Abrir relatório</a></section>')

    cls = "aprof" + (" ativo" if ativo else "")
    pag = ap.get("paginas_livro")
    ficha = []
    if ap.get("fontes"):
        ficha.append(f'<div><dt>Fonte</dt><dd style="font-size:.92rem">{esc(ap["fontes"])}</dd></div>')
    # Uma linha por fonte quando o aprofundamento é combinado. Mostrar só a
    # primeira faria o leitor procurar no livro errado as outras — e o texto do
    # ponteiro vai inteiro, porque metade do vault escreve em prosa livre
    # ("slides 12 a 21") que nenhuma regex de página extrai.
    locs = [l for l in (ap.get("localizacoes") or []) if l.get("texto")]
    if len(locs) > 1:
        itens = "".join(
            f'<div>{esc(l["fonte"]) + ": " if l.get("fonte") else ""}{esc(l["texto"])}</div>'
            for l in locs)
        ficha.append(f'<div><dt>Onde está</dt>'
                     f'<dd style="font-size:.92rem">{itens}</dd></div>')
    elif pag:
        ficha.append(f'<div><dt>No livro</dt><dd style="font-size:.92rem">págs. {esc(pag)}</dd></div>')
    ficha.append(f'<div><dt>Nível</dt><dd style="font-size:.92rem">'
                 f'{esc(ROTULO_NIVEL.get(ap.get("nivel",""), ap.get("nivel","")))}</dd></div>')

    corpo = (f'<article class="papel {cls}" data-aprof="{esc(ident)}">'
             f'<dl class="ficha">{"".join(ficha)}</dl>'
             f'{corpo_html}</article>')
    lateral = (f'<div class="{cls}" data-aprof="{esc(ident)}">'
               f'{barra_de_tarefas(ap["progresso"])}{"".join(blocos)}</div>')
    return corpo, lateral


def pagina_assunto(assunto: dict, materia: dict, concurso: str,
                   destino_dir: Path, rotas: "Rotas", rota: str,
                   rota_materia: str, rota_capa: str,
                   rota_notebooklm: str | None = None) -> str:
    titulo = assunto["titulo"]
    aprofs = assunto.get("aprofundamentos") or []

    corpos, laterais, abas = [], [], []
    for i, ap in enumerate(aprofs):
        ativo = (i == 0)
        c, l = bloco_aprofundamento(ap, materia, assunto, destino_dir, i, ativo,
                                    rotas, rota)
        corpos.append(c)
        laterais.append(l)
        ident = ident_aprof(ap, i)
        abas.append(f'<button class="aba{" ativa" if ativo else ""}" '
                    f'data-alvo="{esc(ident)}" type="button">{esc(rotulo_aprof(ap))}</button>')

    seletor = ""
    if len(aprofs) > 1:
        seletor = (f'<div class="seletor-aprof" role="tablist" '
                   f'aria-label="Versões deste assunto">'
                   f'<span class="rotulo">Aprofundamentos</span>{"".join(abas)}</div>')

    corpo = f"""<div class="papel cabecalho-assunto">
  <div class="sobrancelha">{esc(materia["nome"])}</div>
  <h1>{esc(titulo)}</h1>
  {selos_aprofundamento(assunto)}
  {seletor}
</div>
<div class="colunas" style="margin-top:1.25rem">
  <div>{"".join(corpos)}</div>
  <aside class="lateral">
    <section class="cartao">
      <h3>Este assunto</h3>
      {selos_midia(assunto)}
      {f'<a class="botao secundario" style="margin-top:.7rem" '
       f'href="{esc(relativo(rota_notebooklm, rota))}">Pacote NotebookLM</a>'
       if rota_notebooklm else ''}
    </section>
    {"".join(laterais)}
  </aside>
</div>"""

    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="{relativo(rota_materia, rota)}">{esc(materia["nome"])}</a> › '
              f'{esc(titulo)}')
    descricao = ""
    if aprofs:
        try:
            descricao = md2html.primeiro_paragrafo(
                Path(aprofs[0]["resumo_md"]).read_text(encoding="utf-8"), limite=180)
        except Exception:
            descricao = ""
    return pagina(f"{titulo} — {nome_legivel(concurso)}", trilha, corpo, rota,
                  descricao)


def bloco_pack(pack: dict, ap: dict, ativo: bool, ident: str) -> str:
    """Um pacote NotebookLM: as fontes a subir e os prompts a colar.

    Esta é a única página do site cuja razão de existir é uma **ação**, não leitura —
    daí o prompt vir com botão de copiar e o roteiro de cliques ao lado. O vault tem
    92 pacotes prontos e um único assunto com mídia de verdade: o gargalo não é ter o
    roteiro, é executá-lo 92 vezes.
    """
    fontes = "".join(
        f'<li>{md2html.converter(f, pular_frontmatter=False)}</li>'
        for f in pack["fontes"])

    prompts = []
    for p in pack["prompts"]:
        roteiro = "".join(f"<li>{esc(l)}</li>" for l in p["roteiro"])
        # com que nome salvar: sem isto o arquivo baixado não casa com o que o site
        # procura para detectar a mídia, e o gerável fica invisível na página
        arq = ""
        if p.get("arquivo_saida"):
            arq = (f'<p class="arquivo-saida">Salvar como '
                   f'<code>{esc(p["arquivo_saida"])}</code></p>')
        prompts.append(f"""<section class="cartao prompt">
  <div class="titulo-linha">
    <h3>{p["icone"]} {esc(p["rotulo"])}</h3>
    <button class="baixar copiar" type="button" data-copiar>⧉ Copiar</button>
  </div>
  <pre class="texto-prompt">{esc(p["prompt"])}</pre>
  {arq}
  {f'<ul class="roteiro">{roteiro}</ul>' if roteiro else ''}
</section>""")

    perguntas = "".join(f"<li>{esc(q)}</li>" for q in pack["perguntas"])
    checklist = "".join(
        f'<li class="tarefa {"feito" if c["feito"] else "aberto"}">'
        f'<span class="bolha" aria-hidden="true"></span><span>{esc(c["texto"])}</span></li>'
        for c in pack["checklist"])

    botao = ""
    if pack["url"]:
        botao = (f'<a class="botao" target="_blank" rel="noopener" '
                 f'href="{esc(pack["url"])}">Abrir no NotebookLM</a>')
    else:
        botao = ('<p class="meta">Sem link salvo. Depois de criar o notebook, '
                 'preencha <code>notebooklm_url:</code> no pacote, no vault.</p>')

    midias_prontas = [rot for chave, (_p, _e, ic, rot) in CATALOGO_MIDIAS.items()
                      if ap["midias"].get(chave)]
    estado = (f'<p class="meta">Já gerado: {esc(", ".join(midias_prontas))}.</p>'
              if midias_prontas
              else '<p class="meta">Nada gerado ainda para este aprofundamento.</p>')

    # o nome vem ANTES das fontes porque é essa a ordem da ação: criar o notebook,
    # depois subir. E é por APROFUNDAMENTO — dois aprofundamentos do mesmo assunto
    # são dois notebooks, com nomes diferentes; por isso mora aqui e não no
    # cabeçalho da página, que é único e mostraria o nome errado nas outras abas.
    nome = ""
    if pack.get("nome_notebook"):
        nome = (f'<p class="nome-notebook copiavel">Criar notebook com o nome '
                f'<code class="texto-copiavel">{esc(pack["nome_notebook"])}</code> '
                f'<button class="copiar" type="button" data-copiar>⧉</button></p>')

    cls = "aprof" + (" ativo" if ativo else "")
    return f"""<div class="{cls}" data-aprof="{esc(ident)}">
  <section class="papel">
    <h2 id="fontes">1 · Fontes para subir no notebook</h2>
    {nome}
    <ol class="fontes-pack">{fontes}</ol>
    {estado}
    {botao}
  </section>
  <div class="grade-prompts">{"".join(prompts)}</div>
  <section class="papel" style="margin-top:1.25rem">
    <h2 id="perguntas">Perguntas úteis no chat</h2>
    <ul>{perguntas}</ul>
    <h2 id="checklist">Checklist</h2>
    <ul class="tarefas">{checklist}</ul>
    <p class="meta">O progresso vem do vault e é só leitura — marque no Obsidian.</p>
  </section>
</div>"""


def pagina_notebooklm(assunto: dict, materia: dict, concurso: str, rotas: "Rotas",
                      rota: str, rota_assunto: str, rota_capa: str) -> str:
    """Uma página por ASSUNTO, com abas por aprofundamento.

    Não uma por pacote: entre `padrao--X` e `detalhado--X` só o prompt de áudio
    difere — o resto é nome de arquivo. Página por aprofundamento daria 92 páginas com
    ~95% de conteúdo repetido, e o seletor em abas já existe.
    """
    packs = [(ap, ap.get("pack_notebooklm")) for ap in assunto["aprofundamentos"]]
    packs = [(ap, p) for ap, p in packs if p]
    if not packs:
        return ""

    corpos, abas = [], []
    for i, (ap, p) in enumerate(packs):
        ident = ident_aprof(ap, i)
        corpos.append(bloco_pack(p, ap, i == 0, ident))
        abas.append(f'<button class="aba{" ativa" if i == 0 else ""}" '
                    f'data-alvo="{esc(ident)}" type="button">'
                    f'{esc(rotulo_aprof(ap))}</button>')

    seletor = ""
    if len(packs) > 1:
        seletor = (f'<div class="seletor-aprof" role="tablist" '
                   f'aria-label="Aprofundamentos"><span class="rotulo">Pacote de</span>'
                   f'{"".join(abas)}</div>')

    corpo = f"""<div class="papel cabecalho-assunto">
  <div class="sobrancelha">NotebookLM · {esc(materia["nome"])}</div>
  <h1>{esc(assunto["titulo"])}</h1>
  <p class="meta">Roteiro e prompts para gerar as mídias no Estúdio do NotebookLM.</p>
  {seletor}
</div>
{"".join(corpos)}"""
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="{relativo(rota_assunto, rota)}">{esc(assunto["titulo"])}</a> › '
              f'NotebookLM')
    return pagina(f'NotebookLM: {assunto["titulo"]} — {nome_legivel(concurso)}',
                  trilha, corpo, rota)


ROTULOS_PRIORIDADE = {
    "alta":  ("Prioridade alta", "Os que mais derrubam candidato — comece por aqui."),
    "media": ("Prioridade média", "Importantes, mas depois de dominar os de alta."),
    "base":  ("Base e leitura", "Fundamentos e assuntos de leitura; reforçam o resto."),
}


def selos_aprofundamento(assunto: dict) -> str:
    """Sinaliza no card: quantas fontes e quais níveis de aprofundamento existem.

    Usa a bolha do cartão-resposta (assinatura visual do site) para comunicar
    profundidade: bolha PELA METADE = padrão, bolha CHEIA = detalhado.
    """
    niveis = assunto.get("niveis") or []
    n_fontes = assunto.get("n_fontes") or 0
    n_aprof = assunto.get("n_aprofundamentos") or 0
    if not niveis and n_fontes <= 1 and n_aprof <= 1:
        return ""   # caso simples: não poluir o card

    partes = []

    # Fonte só vira SELO quando há mais de uma — com uma única, o nome dela é dado,
    # não estado, e vive na linha de contexto do card, junto das páginas do livro.
    if n_fontes > 1:
        titulo = "; ".join(assunto.get("fontes") or [])
        partes.append(f'<span class="selo-aprof" title="{esc(titulo)}">'
                      f'📚 {n_fontes} fontes</span>')

    # níveis — meia bolha (padrão) e/ou bolha cheia (detalhado)
    tem_padrao = "padrao" in niveis
    tem_detalhado = "detalhado" in niveis
    if tem_padrao and tem_detalhado:
        rot, cls, titulo = "Padrão + Detalhado", "ambos", "Há versão padrão e detalhada"
    elif tem_detalhado:
        rot, cls, titulo = "Detalhado", "detalhado", "Aprofundamento detalhado"
    elif tem_padrao:
        rot, cls, titulo = "Padrão", "padrao", "Aprofundamento padrão (revisão)"
    else:
        rot = cls = titulo = ""
    if rot:
        bolhas = ('<span class="bolha meia"></span><span class="bolha cheia"></span>'
                  if cls == "ambos" else
                  f'<span class="bolha {"cheia" if cls == "detalhado" else "meia"}"></span>')
        partes.append(f'<span class="selo-aprof nivel-{cls}" title="{esc(titulo)}">'
                      f'{bolhas}{esc(rot)}</span>')

    # "N versões" só com mais de uma FONTE: com uma fonte, duas versões são
    # exatamente "Padrão + Detalhado", que o selo de nível ao lado já disse — era
    # a redundância mais visível do card antigo.
    if n_aprof > 1 and n_fontes > 1:
        partes.append(f'<span class="selo-aprof" title="Versões deste assunto">'
                      f'⇄ {n_aprof} versões</span>')

    return f'<div class="selos-aprof">{"".join(partes)}</div>'


def card_assunto(a: dict, href: str, selo_topico: dict | None = None) -> str:
    # Uma linha de contexto discreta: onde está no livro e de qual fonte veio. Selo
    # é para estado (nível, o que já foi gerado); texto é para dado.
    ctx = []
    if a.get("paginas_livro"):
        ctx.append(f'págs. {a["paginas_livro"]}')
    fontes = a.get("fontes") or []
    if len(fontes) == 1:
        ctx.append(fontes[0])
    pag = f'<span class="meta">{esc(" · ".join(ctx))}</span>' if ctx else ""
    # o que EXISTE neste assunto — contagem e presença, nunca julgamento
    s = a.get("sinais") or {}
    sin = []
    if s.get("n_cards"):
        sin.append(f'{s["n_cards"]} cards')
    if s and not s.get("tem_ancoras"):
        sin.append("sem trechos-âncora")
    sinais = f'<span class="sinais">{esc(" · ".join(sin))}</span>' if sin else ""
    # Em grade corrida o tópico não tem cabeçalho para chamar de seu, então vem
    # no card — a informação do edital não se perde por causa do layout.
    top = ""
    if selo_topico:
        # Quando o assunto nasceu 1:1 do tópico — que é a regra em edital plano —
        # o título do tópico é o título do card. Repetir os dois é ruído; sobra
        # só o número, que é o que localiza no plano.
        rot = f'tópico {selo_topico["numero"]}'
        if _norm_txt(selo_topico["titulo"]) != _norm_txt(a["titulo"]):
            rot += f' · {selo_topico["titulo"][:38]}'
        top = (f'<span class="selo-topico" title="{esc(selo_topico["titulo"])}">'
               f'{esc(rot)}</span>')
    return f"""<a class="item" href="{esc(href)}">
  {top}
  <h3>{esc(a["titulo"])}</h3>
  {pag}
  {sinais}
  {selos_aprofundamento(a)}
  {selos_midia(a, so_presentes=True)}
  {barra_de_tarefas(a["progresso"])}
</a>"""


def assuntos_do_topico(topico: dict, materia: dict) -> list[str]:
    """Assuntos aprofundados que correspondem a um tópico do mapa.

    **Só casamento exato**, e é uma decisão, não uma limitação de tempo. Derivar por
    slugificação daria link errado na maior parte: dos 203 tópicos dos 24 mapas do
    vault, só ~18% casam por slug. No SEDES o tópico "Domínio da estrutura
    morfossintática do período" explode em 7 assuntos; nas matérias de "lei como
    fonte" o assunto É uma norma, e a relação é N:M; e 9 assuntos de Português do
    SEDES foram reaproveitados do BB, então os slugs seguem o edital do outro
    concurso.

    O risco não é a ausência de link — é o falso negativo: tópico sem link lido como
    "não tem aprofundamento" quando ele existe com outro nome, escondendo trabalho
    já feito. Por isso, sem casamento, a página **não afirma nada**. Quem quiser o
    link fino preenche `mapa-aliases.json`.
    """
    slugs = {a["slug"] for a in materia["assuntos"]}
    aliases = materia.get("aliases_mapa") or {}
    alvo = aliases.get(_norm_txt(topico["titulo"]))
    if alvo:
        return [s for s in alvo if s in slugs]
    return [topico["slug"]] if topico["slug"] in slugs else []


def _norm_txt(s: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


# Ícone e rótulo de reserva de cada seção do tópico. O rótulo exibido é sempre o
# LITERAL do vault (`Pegadinhas da Quadrix neste tópico` nomeia a banca, e isso é
# informação); estes só entram quando o vault não deu rótulo nenhum.
SECOES_TOPICO = {
    "topicos_edital": ("📜", "Tópicos do edital"),
    "subtopicos":     ("",   "Subtópicos derivados"),
    "material":       ("📚", "Material recomendado"),
    "pegadinhas":     ("⚠️", "Pegadinhas da banca"),
    "meta":           ("🎯", "Meta"),
    "extra":          ("📌", "Complemento"),
}

# Acima disto, o detalhe do tópico nasce recolhido. As matérias do SEDES têm 5 a 7
# tópicos e cabem abertas; as do BB têm 14, 17 e 24 — cinco seções × 24 tópicos numa
# página só é um paredão em que nada se acha.
TOPICOS_PARA_RECOLHER = 8


def blocos_de(topico: dict) -> list[dict]:
    """Blocos do tópico, tolerando o modelo antigo.

    `--modelo site-model.json` é contrato público: um arquivo salvo com a 0.7.x
    não pode quebrar o build. Lá o campo era `secoes` (dict chave->markdown), sem
    rótulo, sem sufixo e sem contagem — degrada para um bloco por chave.
    """
    if topico.get("blocos") is not None:
        return topico["blocos"]
    return [{"chave": k, "rotulo": SECOES_TOPICO.get(k, ("", k))[1],
             "sufixo": "", "markdown": v, "itens": [], "n_itens": 0}
            for k, v in (topico.get("secoes") or {}).items() if v]


def subtopicos_de(topico: dict) -> list[dict]:
    """Subtópicos do tópico. No modelo antigo eram `list[str]`, sem estado nem grupo."""
    return [s if isinstance(s, dict) else {"texto": s, "feito": None, "grupo": ""}
            for s in (topico.get("subtopicos") or [])]


def rotulo_do_bloco(bloco: dict) -> str:
    icone, reserva = SECOES_TOPICO.get(bloco["chave"], ("📌", "Complemento"))
    texto = bloco.get("rotulo") or reserva
    return f"{icone} {texto}".strip()


def lista_subtopicos(topico: dict) -> str:
    """O checklist derivado, agrupado pelo bloco de origem.

    Fica FORA da dobra: é o que transforma o título do tópico em plano de estudo, e
    é por ele que se passa o olho. O grupo aparece porque `— LEI 8.662/1993
    (DECORAR ARTIGOS)` diz de que aquele checklist é; sem ele, quatro listas
    distintas viravam uma só, sem assunto.
    """
    subs = subtopicos_de(topico)
    if not subs:
        return ""
    partes, grupo_aberto, lista_aberta = [], None, False
    for s in subs:
        if s.get("grupo") != grupo_aberto:
            if lista_aberta:
                partes.append("</ul>")
            grupo_aberto = s.get("grupo")
            if grupo_aberto:
                partes.append(f'<p class="grupo-sub">{esc(grupo_aberto)}</p>')
            partes.append('<ul class="tarefas">')
            lista_aberta = True
        if s.get("feito") is None:
            # bullet simples dentro do bloco de subtópicos: não é item marcável, e
            # dar-lhe uma bolha o fazia parecer checkbox em aberto — a lista passava
            # a mostrar mais itens do que o contador do rodapé conta. 2 tópicos do
            # vault caem aqui (`Estrutura de Dados`, `fundamentos-assistencia-social`).
            partes.append(f'<li class="livre"><span>{esc(s["texto"])}</span></li>')
        else:
            marca = "feito" if s["feito"] else "aberto"
            partes.append(f'<li class="tarefa {marca}">'
                          f'<span class="bolha" aria-hidden="true"></span>'
                          f'<span>{esc(s["texto"])}</span></li>')
    if lista_aberta:
        partes.append("</ul>")
    return f'<div class="subtopicos">{"".join(partes)}</div>'


def pistas_do_topico(blocos: list[dict]) -> str:
    """O que o `<summary>` conta com o detalhe FECHADO.

    Uma dobra muda ("mostrar mais") obriga a abrir 24 tópicos para descobrir onde
    está o que interessa. Contando, ela já informa — e a decisão de abrir passa a
    ser do estudante.
    """
    pistas = []
    for b in blocos:
        if b["chave"] in ("topicos_edital", "subtopicos") or not b["markdown"]:
            continue
        icone = SECOES_TOPICO.get(b["chave"], ("📌", ""))[0]
        n = b.get("n_itens") or 0
        if b["chave"] == "pegadinhas" and n:
            texto = f"{n} pegadinha{'s' if n > 1 else ''}"
        elif b["chave"] == "material" and n:
            texto = f"{n} materiais" if n > 1 else "1 material"
        elif b["chave"] == "meta":
            texto = "meta"
        else:
            texto = b.get("rotulo") or "complemento"
        pistas.append(f'<span class="pista">{esc(icone)} {esc(texto)}</span>')
    return f'<span class="pistas">{"".join(pistas)}</span>' if pistas else ""


def secoes_do_topico(topico: dict, blocos: list[dict], resolver) -> str:
    """Material, pegadinhas, meta e os complementos — em markdown convertido.

    Passa por `md2html.converter` de propósito: é o que faz a tabela do mnemônico
    virar tabela, o negrito da lei aparecer e o wikilink do material virar link. O
    `prefixo_id` evita que o mesmo H4 em dois tópicos gere `id` duplicado.
    """
    fora = ("topicos_edital", "subtopicos")
    partes = []
    for b in blocos:
        if b["chave"] in fora or not b["markdown"].strip():
            continue
        ident = (f't{topico["numero"]}-{b["chave"]}' if b["chave"] != "extra"
                 else f't{topico["numero"]}-{md2html.slug_ancora(b["rotulo"])}')
        corpo = md2html.converter(b["markdown"], wikilink_resolver=resolver,
                                  prefixo_id=f't{topico["numero"]}-')
        partes.append(f'<section class="secao-topico" data-secao="{esc(b["chave"])}">'
                      f'<h4 id="{esc(ident)}">{esc(rotulo_do_bloco(b))}</h4>'
                      f'{corpo}</section>')
    return "".join(partes)


def rota_materiais_do_escopo(rotas: "Rotas", rota: str) -> str:
    """Rota da página de Materiais do escopo desta página, ou "" se não houver.

    Calculada da rota da PRÓPRIA página (`{conc}/{escopo}/materias/…`), nunca
    procurada pelo nome: `materiais` existe em vários escopos e o índice de nomes
    devolveria sempre o primeiro registrado.
    """
    partes = rota.split("/")
    if len(partes) < 3:
        return ""
    candidata = f"{partes[0]}/{partes[1]}/materiais/index.html"
    return relativo(candidata, rota) if rotas.tem_pagina(candidata) else ""


def bloco_plano(materia: dict, rotas: "Rotas", rota: str) -> str:
    """A aba **Plano**: o que o edital exige, tópico por tópico.

    Três camadas por tópico, e a divisão não é estética: o **literal do edital** e o
    **checklist de subtópicos** ficam sempre à vista — o primeiro é a autoridade
    (uma linha), o segundo é a superfície de varredura. Material, pegadinhas, meta e
    complementos vão para um `<details>` nativo: `<details>` porque funciona sem
    JavaScript, imprime e é o que faz o Ctrl+F do Chrome abrir o tópico certo.

    O progresso do mapa é exibido separado do aprofundamento. Os 24 mapas do vault
    somam 2.220 checkboxes, nenhum marcado — jogá-los na mesma barra faria o
    progresso do aprofundamento desaparecer num denominador de milhares que ninguém
    pretende marcar pela web.
    """
    mapa = materia.get("mapa")
    if not mapa:
        return ""
    resolver = rotas.resolvedor(rota)
    aberto = mapa["n_topicos"] <= TOPICOS_PARA_RECOLHER
    itens = []
    for t in mapa["topicos"]:
        n = t["numero"]
        blocos = blocos_de(t)
        alvos = assuntos_do_topico(t, materia)
        link = ""
        if alvos:
            hrefs = [f'<a href="{esc(relativo(rota_irma(rota, slug), rota))}">estudar</a>'
                     for slug in alvos]
            link = f'<span class="ir">{" · ".join(hrefs)}</span>'
        prio = (f'<span class="selo-prio prio-{t["prioridade"]}">'
                f'{esc(ROTULOS_PRIORIDADE[t["prioridade"]][0])}</span>'
                if t.get("prioridade") in ROTULOS_PRIORIDADE else "")

        edital = "".join(
            f'<div class="literal-edital">'
            f'{md2html.converter(b["markdown"], wikilink_resolver=resolver, prefixo_id=f"t{n}-")}'
            f'</div>'
            for b in blocos if b["chave"] == "topicos_edital" and b["markdown"].strip())

        secoes = secoes_do_topico(t, blocos, resolver)
        detalhe = ""
        if secoes:
            detalhe = (f'<details class="mais-topico"{" open" if aberto else ""}>'
                       f'<summary><span class="rot">Detalhes do tópico</span>'
                       f'{pistas_do_topico(blocos)}</summary>'
                       f'<div class="secoes-topico">{secoes}</div></details>')

        pg = t["progresso"]
        itens.append(f"""<li class="topico">
  <div class="linha">
    <span class="num">{n}</span>
    <h3 id="t{n}">{esc(t["titulo"])}</h3>
    {prio}{link}
  </div>
  {edital}
  {lista_subtopicos(t)}
  {detalhe}
  {f'<span class="meta">{pg["feitos"]}/{pg["total"]} itens do plano</span>' if pg["total"] else ''}
</li>""")

    aux = "".join(
        f'<section class="papel" style="margin-top:1rem">'
        f'<h2 id="{esc(md2html.slug_ancora(a["titulo"]))}">{esc(a["titulo"])}</h2>'
        f'{md2html.converter(a["corpo"], wikilink_resolver=resolver)}'
        f'</section>'
        for a in mapa["auxiliares"] if a["corpo"].strip())

    prog = mapa["progresso"]
    resumo = (f'{mapa["n_topicos"]} tópicos do edital · '
              f'{prog["feitos"]}/{prog["total"]} itens do plano')
    # o plano pode vir do escopo vizinho: dizer de onde é honesto e evita a
    # impressão de que o cargo tem um mapa próprio que não tem
    origem = ""
    if materia.get("mapa_em"):
        origem = (f'<p class="meta origem-plano">Plano do edital de '
                  f'{esc(nome_escopo(materia["mapa_em"]["escopo_nome"]))} — '
                  f'esta matéria é compartilhada.</p>')
    expandir = ('<button class="expandir" type="button" data-expandir="abrir">'
                'Expandir tudo</button>') if not aberto else ""
    return f"""<div class="visao plano ativo" data-visao="plano">
  <section class="papel">
    <div class="cabeca-plano"><p class="meta">{esc(resumo)}</p>{expandir}</div>
    {origem}
    <ol class="lista-topicos">{"".join(itens)}</ol>
  </section>
  {bloco_material_por_topico(materia, resolver, rota_materiais_do_escopo(rotas, rota))}
  {aux}
</div>"""


TIPO_MATERIAL = (
    ("livro",    "📕", re.compile(r"^(livro|livro/lei|livro \(didático\)|livro/ebook)\b", re.I)),
    ("video",    "▶",  re.compile(r"^(youtube|v[ií]deo|canal)\b", re.I)),
    ("questoes", "✎",  re.compile(r"^(quest[oõ]es|banco de quest[oõ]es)\b", re.I)),
    ("norma",    "⚖",  re.compile(r"^(lei|norma|norma-fonte|lei fonte|refer[eê]ncia legal|"
                                  r"fonte prim[aá]ria|documenta[cç][aã]o|documento)\b", re.I)),
)


def tipo_do_material(texto: str) -> tuple[str, str]:
    """Classifica o item pelo rótulo que o mapa já usa (`Livro:`, `Questões:`…).

    Rótulo desconhecido NÃO vira palpite: fica como `outro`, com marcador neutro.
    São ~40 dos 458 itens do vault — normas e documentos que o autor acrescentou
    fora da tripla do template, e que não podem sumir só por não casarem.
    """
    for chave, icone, padrao in TIPO_MATERIAL:
        if padrao.match(texto.strip()):
            return chave, icone
    return "outro", "·"


def bloco_material_por_topico(materia: dict, resolver=None,
                              rota_materiais: str = "") -> str:
    """Todo o material recomendado da matéria, na ordem do edital.

    **Derivado**, não redigitado: os itens já estão em `### Material recomendado`
    de cada tópico do mapa. Antes só dava para vê-los abrindo um `<details>` por
    tópico; a bibliografia de `04-MATERIAIS/` é a outra metade, agrupada por
    matéria, e as duas não se falavam.
    """
    mapa = materia.get("mapa")
    if not mapa:
        return ""
    secoes, total = [], 0
    for t in mapa["topicos"]:
        itens = [i for b in (t.get("blocos") or []) if b["chave"] == "material"
                 for i in (b.get("itens") or [])]
        if not itens:
            continue
        lis = []
        for i in itens:
            texto = i["texto"]
            _, icone = tipo_do_material(texto)
            lis.append(f'<li><span class="ic" aria-hidden="true">{icone}</span>'
                       f'{md2html._inline(esc(texto), resolver)}</li>')
            total += 1
        secoes.append(f'<section class="mat-topico">'
                      f'<h3><span class="num">{t["numero"]}</span>'
                      f'{esc(t["titulo"])}</h3><ul>{"".join(lis)}</ul></section>')
    if not secoes:
        return ""
    # O texto antigo mandava o leitor a "Materiais, no menu do concurso" — menu
    # que não existe (o esqueleto da página tem só marca, trilha e tema), para uma
    # página que, no cargo, também não existia. Agora é link calculado da rota da
    # própria página, não texto morto.
    ponte = (f' · <a href="{rota_materiais}">a bibliografia completa fica em Materiais</a>'
             if rota_materiais else "")
    return f"""<section class="papel material-topicos">
  <h2 id="material-por-topico">Material por tópico</h2>
  <p class="meta">{total} itens, na ordem do edital{ponte}</p>
  {"".join(secoes)}
</section>"""


def bloco_cobertura_edital(materia: dict) -> str:
    """Quanto do edital já tem aprofundamento, e o que falta — por nome.

    Duas medidas separadas e ambas verificáveis: a **cobertura** é contagem de
    tópicos; a **profundidade** é o que existe (detalhado, mídia). Não há nota
    sintética: os sinais que a comporiam estão saturados no vault, e uma nota
    constante disfarçada de métrica é o oposto do que este site se propõe.

    Matéria em 0% mostra 0% — esconder faria a lacuna sumir justamente onde ela
    é maior.
    """
    cb = materia.get("cobertura") or {}
    if not cb.get("n_topicos"):
        return ""
    pct = cb["pct"]
    faltam = cb["topicos_sem"]
    lista = ""
    if faltam:
        itens = "".join(f'<li><span class="num">{t["numero"]}</span>{esc(t["titulo"])}</li>'
                        for t in faltam)
        lista = (f'<details class="lacunas"><summary>{len(faltam)} tópico(s) ainda '
                 f'sem aprofundamento</summary><ul>{itens}</ul></details>')
    prof = []
    if cb["n_detalhado"]:
        prof.append(f'{cb["n_detalhado"]} em nível detalhado')
    if cb["n_com_midia"]:
        prof.append(f'{cb["n_com_midia"]} com mídia')
    return f"""<section class="papel cobertura-edital">
  <h2 id="cobertura-do-edital">Cobertura do edital</h2>
  <div class="barra-cobertura" role="img"
       aria-label="{cb["n_cobertos"]} de {cb["n_topicos"]} tópicos">
    <span style="width:{pct}%"></span>
  </div>
  <p class="meta">{cb["n_cobertos"]}/{cb["n_topicos"]} tópicos ({pct}%)
     {f'· {" · ".join(prof)}' if prof else ''}</p>
  {lista}
</section>"""


def bussola_recolhida(html_doc: str) -> str:
    """A bússola da banca abre FECHADA, com o título à vista.

    Ela é o primeiro bloco da visão Estudo, e uma bússola bem escrita passa
    fácil dos 2.700px. Aberta, ela empurrava o primeiro grupo de assuntos para
    3.131px — 2,3 telas abaixo numa janela de 1.321px —, e a aba Estudo parecia
    NÃO TER a matéria: o relato foi literalmente "nem existe dentro de Estudo".
    O incentivo ficava invertido, porque quanto melhor o documento, mais ele
    escondia justamente o que a aba existe para mostrar. Medido no vault: as
    duas matérias com bússola escrita tinham ~6.000 e ~7.400 caracteres antes
    do primeiro assunto; as sem bússola, 64 e 101.

    Recolher preserva as duas coisas: o documento continua sendo o primeiro
    bloco (a `concurso-aprofunda` o quer antes da lista, para orientar o
    estudo), e a lista volta para a primeira tela. Um clique traz o texto
    inteiro, e o `<details>` é nativo — sem depender do site.js.
    """
    return _doc_recolhido(html_doc, "bussola", "Como a banca cobra esta matéria",
                          "perfil da banca nesta matéria")


def afericao_recolhida(html_doc: str) -> str:
    """A aferição contra prova real, publicada com CONTEÚDO e fechada.

    Antes ela não aparecia: `DOCS_APOIO_CONHECIDOS` não casava `00-AFERICAO-*`,
    e o arquivo era ignorado em silêncio. Publicá-la só como NOME numa lista de
    "documentos de apoio" também não serve — ela é a análise que mede a matéria,
    com nota, distribuição por assunto e ações corretivas (267 linhas em Vendas e
    Negociação). Fechada pelo mesmo motivo da bússola: é ainda maior que ela, e
    documento longo no topo de uma aba esconde o que a aba existe para mostrar.
    """
    return _doc_recolhido(html_doc, "afericao", "Aferição contra prova real",
                          "o material medido contra o gabarito oficial")


def _doc_recolhido(html_doc: str, classe: str, titulo_padrao: str, dica: str) -> str:
    """Documento de apoio no topo de uma aba: `<details>` fechado, título à vista.

    Um só lugar para a regra, porque ela vale para qualquer documento longo que
    abra uma aba — foi generalizada quando a aferição virou o segundo caso. O
    `<details>` é nativo: não depende do site.js, e o `@media print` reabre.
    """
    m = re.match(r"\s*<h1[^>]*>(.*?)</h1>", html_doc, re.S)
    titulo = m.group(1).strip() if m else titulo_padrao
    corpo = html_doc[m.end():] if m else html_doc
    return (f'<details class="papel {classe}" style="margin-top:1.25rem">'
            f'<summary><span class="bussola-titulo">{titulo}</span>'
            f'<span class="bussola-dica">{dica}</span>'
            f'</summary><div class="bussola-corpo">{corpo}</div></details>')


def agrupar_por_topico(materia: dict, href_de) -> str:
    """Os assuntos aprofundados na ordem do plano do edital.

    Usa o `topico_id` **gravado** no frontmatter pela Etapa 2, nunca inferência
    por slug — a regra continua a mesma de `assuntos_do_topico`. A diferença é
    que agora existe dado: a skill que criou o assunto sabia de qual tópico ele
    veio, e passou a registrar.

    Assunto sem vínculo vai para um balde próprio, visível. Escondê-lo faria a
    matéria parecer menor do que é; e o balde cheio é justamente o sinal de que
    falta rodar o backfill.
    """
    mapa = materia.get("mapa")
    if not mapa:
        return ""
    por_topico: dict[str, list] = {}
    for a in materia["assuntos"]:
        for tid in (a.get("topico_id") or []):
            por_topico.setdefault(tid, []).append(a)
    if not por_topico:
        return ""

    # Agrupar só quando agrupar de fato junta alguma coisa.
    #
    # O tópico vem do edital, verbatim — não é nosso para engordar. Mas edital
    # plano existe: o do BB tem 24 itens numa matéria só, e cada assunto nasceu
    # 1:1 de um item. Nesse caso "agrupar" produz 15 cabeçalhos pesados para 15
    # cards, que é mais moldura que conteúdo. Quando o agrupamento não reduz
    # nada, a ordem do edital vira uma grade única e o tópico vira selo no card:
    # a mesma informação, sem a moldura.
    com_assunto = [t for t in mapa["topicos"] if por_topico.get(t["slug"])]
    n_ass = len({a["slug"] for doss in por_topico.values() for a in doss})
    agrupa = bool(com_assunto) and len(com_assunto) <= max(1, n_ass * 0.6)

    secoes = []
    if agrupa:
        for t in com_assunto:
            doss = por_topico[t["slug"]]
            cards = "".join(card_assunto(a, href_de(a)) for a in doss)
            secoes.append(f"""<section class="grupo-topico">
  <header><span class="num">{t["numero"]}</span><h2>{esc(t["titulo"])}</h2>
  <span class="quantos">{len(doss)} assuntos</span></header>
  <div class="grade">{cards}</div>
</section>""")
    else:
        vistos, cards = set(), []
        for t in com_assunto:
            for a in por_topico[t["slug"]]:
                if a["slug"] in vistos:
                    continue
                vistos.add(a["slug"])
                cards.append(card_assunto(a, href_de(a), selo_topico=t))
        secoes.append(f"""<section class="grupo-topico corrido">
  <header><h2>Na ordem do edital</h2>
  <span class="quantos">{len(cards)} assuntos</span></header>
  <div class="grade">{"".join(cards)}</div>
</section>""")

    vinculados = {a["slug"] for doss in por_topico.values() for a in doss}
    soltos = [a for a in materia["assuntos"] if a["slug"] not in vinculados]
    if soltos:
        cards = "".join(card_assunto(a, href_de(a)) for a in soltos)
        secoes.append(f"""<section class="grupo-topico sem-topico">
  <header><h2>Ainda sem tópico</h2>
  <span class="quantos">{len(soltos)} assuntos</span></header>
  <p class="explica">Aprofundados antes de o vínculo com o plano existir.</p>
  <div class="grade">{cards}</div>
</section>""")
    return "".join(secoes)


def bloco_cobertura(materia: dict, rotas: "Rotas", rota: str) -> str:
    """O que o vault AFIRMA sobre a cobertura, em vez de adivinhação.

    Existe porque o link fino tópico→assunto não é derivável (ver
    `assuntos_do_topico`). Em vez de inferir, mostra o que já está escrito: a lista
    real de assuntos aprofundados (varredura de pasta, a verdade do disco) e, quando
    a matéria tem, os documentos de cobertura e pendências que a Etapa 2 gerou.
    """
    partes = []
    if materia["assuntos"]:
        partes.append(f'<p>{materia["n_assuntos"]} assunto(s) aprofundado(s) — '
                      f'a lista completa está na visão <strong>Estudo</strong>.</p>')
    externo = materia.get("aprofundamento_em")
    if externo:
        partes.append(
            f'<p>O aprofundamento desta matéria fica em '
            f'<a href="{esc(rota_da_materia_irma(externo, rota))}">'
            f'{esc(nome_escopo(externo["escopo_nome"]))}</a> — '
            f'{externo["n_assuntos"]} assunto(s), aproveitados por este cargo.</p>')
    for nome, rotulo in (("00-COBERTURA-LIVRO.md", "Cobertura do livro"),
                         ("00-PENDENCIAS-FORA-DO-LIVRO.md", "Fora do livro")):
        alvo = Path(materia["dir"]) / nome
        if alvo.exists():
            partes.append(f'<h3>{esc(rotulo)}</h3>'
                          + md2html.converter(alvo.read_text(encoding="utf-8"),
                                              wikilink_resolver=rotas.resolvedor(rota)))
    if not partes:
        return ""
    return (f'<section class="papel cobertura" style="margin-top:1.25rem">'
            f'<h2 id="cobertura">Cobertura desta matéria</h2>'
            f'{"".join(partes)}</section>')


def pagina_materia(materia: dict, concurso: str, materia_dir: Path,
                   rotas: "Rotas", rota: str, rota_capa: str) -> str:
    def href_de(a: dict) -> str:
        return relativo(rota_irma(rota, a["slug"]), rota)

    # agrupar por prioridade, na ordem alta -> média -> base -> sem classificação
    grupos = []
    for prio in PRIORIDADES:
        doss = [a for a in materia["assuntos"] if a.get("prioridade") == prio]
        if not doss:
            continue
        titulo, explica = ROTULOS_PRIORIDADE[prio]
        cards = "".join(card_assunto(a, href_de(a)) for a in doss)
        grupos.append(f"""<section class="grupo-prioridade" data-prio="{prio}">
  <header><h2>{esc(titulo)}</h2><span class="quantos">{len(doss)} assuntos</span></header>
  <p class="explica">{esc(explica)}</p>
  <div class="grade">{cards}</div>
</section>""")

    sem_prio = [a for a in materia["assuntos"] if not a.get("prioridade")]
    if sem_prio:
        cards = "".join(card_assunto(a, href_de(a)) for a in sem_prio)
        grupos.append(f"""<section class="grupo-prioridade" data-prio="sem">
  <header><h2>Demais assuntos</h2><span class="quantos">{len(sem_prio)} assuntos</span></header>
  <div class="grade">{cards}</div>
</section>""")

    grupos_topico = agrupar_por_topico(materia, href_de)

    # "Como a banca cobra esta matéria" — antes dos assuntos, e RECOLHIDA
    bloco_banca = ""
    if materia.get("doc_banca"):
        try:
            texto = (materia_dir / materia["doc_banca"]).read_text(encoding="utf-8")
            bloco_banca = bussola_recolhida(
                md2html.converter(texto, wikilink_resolver=rotas.resolvedor(rota)))
        except Exception:
            bloco_banca = ""

    bloco_afericao = ""
    if materia.get("doc_afericao"):
        try:
            texto = (materia_dir / materia["doc_afericao"]).read_text(encoding="utf-8")
            bloco_afericao = afericao_recolhida(
                md2html.converter(texto, wikilink_resolver=rotas.resolvedor(rota)))
        except Exception:
            bloco_afericao = ""

    docs = ""
    outros = [d for d in materia.get("docs_apoio", [])
              if d not in (materia.get("doc_banca"), materia.get("doc_afericao"))]
    if outros:
        lista = "".join(f"<li>{esc(d)}</li>" for d in outros)
        docs = (f'<section class="papel" style="margin-top:1.5rem">'
                f'<h2>Documentos de apoio (no vault)</h2><ul>{lista}</ul></section>')

    pp = materia.get("por_prioridade", {})
    resumo_prio = " · ".join(
        f"{pp.get(k, 0)} {ROTULOS_PRIORIDADE[k][0].lower()}"
        for k in PRIORIDADES if pp.get(k))

    plano = bloco_plano(materia, rotas, rota)
    cobertura = bloco_cobertura(materia, rotas, rota)
    cob_edital = bloco_cobertura_edital(materia)
    herdado = bloco_estudo_herdado(materia, rota)

    # Uma matéria, duas visões: Plano (o mapa do edital) e Estudo (os assuntos
    # aprofundados). São ângulos diferentes do MESMO recorte — separá-los em duas
    # páginas obrigaria a saber em qual procurar. Reusa o seletor em abas que já
    # existe na página de assunto, em vez de inventar componente.
    # `herdado` conta como Estudo: o material EXISTE, só mora no `_COMUM`. Olhar
    # apenas `materia["assuntos"]` deixava três matérias do SEDES com o Plano
    # sozinho, apesar de a cobertura já afirmar 40%, 60% e 25% de aprofundamento.
    tem_estudo = bool(materia["assuntos"]) or bool(herdado)
    seletor = ""
    if plano and tem_estudo:
        seletor = ('<div class="seletor-aprof" role="tablist" aria-label="Visões">'
                   '<span class="rotulo">Visão</span>'
                   '<button class="aba ativa" data-visao-alvo="plano" type="button">'
                   'Plano</button>'
                   '<button class="aba" data-visao-alvo="estudo" type="button">'
                   'Estudo</button></div>')

    # Dois eixos de leitura para o mesmo conjunto: pela ordem do edital (o que a
    # prova cobra) e por prioridade (por onde começar). Só aparece quando os dois
    # eixos existem — oferecer um agrupamento vazio seria pior que não oferecer.
    eixo = ""
    corpo_estudo = "".join(grupos)
    if grupos_topico and grupos:
        eixo = ('<div class="seletor-aprof seletor-eixo" role="tablist"'
                ' aria-label="Agrupar por">'
                '<span class="rotulo">Agrupar por</span>'
                '<button class="aba ativa" data-eixo-alvo="topico" type="button">'
                'Tópico do edital</button>'
                '<button class="aba" data-eixo-alvo="prioridade" type="button">'
                'Prioridade</button></div>')
        corpo_estudo = (f'<div class="eixo ativo" data-eixo="topico">{grupos_topico}</div>'
                        f'<div class="eixo" data-eixo="prioridade">{"".join(grupos)}</div>')

    estudo = ""
    if tem_estudo:
        ativo = " ativo" if not plano else ""
        estudo = (f'<div class="visao{ativo}" data-visao="estudo">'
                  f'{bloco_banca}{bloco_afericao}{cob_edital}{eixo}{corpo_estudo}{herdado}'
                  f'{docs}{cobertura}</div>')
    elif cobertura:
        estudo = cobertura

    linha_resumo = []
    if materia["assuntos"]:
        linha_resumo.append(f'{materia["n_assuntos"]} assuntos aprofundados')
        if materia["n_com_podcast"]:
            linha_resumo.append(f'{materia["n_com_podcast"]} com áudio')
        if materia["n_com_flashcards"]:
            linha_resumo.append(f'{materia["n_com_flashcards"]} com flashcards')
    elif herdado:
        # `n_assuntos` é 0 aqui: dizer "0 assuntos aprofundados" numa matéria que
        # tem aprofundamento seria a afirmação errada que este conserto veio tirar
        n = len(materia.get("assuntos_herdados") or [])
        linha_resumo.append(f'{n} assuntos aprofundados no material comum')

    corpo = f"""<div class="papel">
  <div class="sobrancelha">{esc(nome_legivel(concurso))}</div>
  <h1>{esc(materia["nome"])}</h1>
  {f'<p>{esc(" · ".join(linha_resumo))}</p>' if linha_resumo else ''}
  {f'<p class="meta">{esc(resumo_prio)}</p>' if resumo_prio else ''}
  {seletor}
</div>
{plano}
{estudo if (plano and tem_estudo) else (estudo or bloco_banca + bloco_afericao + cob_edital + eixo + corpo_estudo + docs)}"""
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a>'
              f' › {esc(materia["nome"])}')
    return pagina(f'{materia["nome"]} — {nome_legivel(concurso)}', trilha, corpo, rota)


def tamanho_legivel(n: int) -> str:
    for unidade, limite in (("GB", 1 << 30), ("MB", 1 << 20), ("kB", 1 << 10)):
        if n >= limite:
            return f"{n / limite:.1f} {unidade}".replace(".0 ", " ")
    return f"{n} B"


def lista_documentos(secao: dict, rotas: "Rotas", rota: str) -> str:
    """As seções de CONSULTA num registro tipográfico, sem card.

    Card com sombra e progresso é para o que se estuda; transformar "Sinergia" em
    peer visual de "Crase" faria a página competir consigo mesma. Aqui a hierarquia
    é só tipográfica.
    """
    itens = []
    for doc in secao["documentos"]:
        href = rota_irma(rota, doc["slug"])
        meta = []
        if doc["n_secoes"]:
            meta.append(f'{doc["n_secoes"]} seções')
        if doc["progresso"]["total"]:
            meta.append(f'{doc["progresso"]["feitos"]}/{doc["progresso"]["total"]} itens')
        itens.append(
            f'<li><a href="{esc(relativo(href, rota))}">{esc(doc["titulo"])}</a>'
            + (f'<span class="meta">{esc(" · ".join(meta))}</span>' if meta else "")
            + (f'<p class="resumo">{esc(doc["resumo"])}</p>' if doc["resumo"] else "")
            + "</li>")
    return f'<ul class="lista-docs">{"".join(itens)}</ul>' if itens else ""


def lista_anexos(secao: dict, rotas: "Rotas", rota: str) -> str:
    """Anexos com tamanho, para o peso ser visível ANTES do clique — há PDF de
    quase 10 MB, e quem abre no celular na rede doméstica agradece o aviso."""
    if not secao["anexos"]:
        return ""
    itens = []
    for a in secao["anexos"]:
        rel = relativo(rota_anexo(rota, a), rota)
        itens.append(
            f'<li><span class="rot">{esc(a["arquivo"])}</span>'
            f'<span class="meta">{esc(tamanho_legivel(a["bytes"]))}</span>'
            f'<a class="baixar" href="{esc(rel)}" download="{esc(a["arquivo"])}">'
            f'⤓ Baixar</a></li>')
    total = tamanho_legivel(secao["bytes_anexos"])
    return (f'<section class="papel" style="margin-top:1.5rem">'
            f'<h2 id="arquivos">Arquivos ({secao["n_anexos"]} · {esc(total)})</h2>'
            f'<ul class="midias-extra">{"".join(itens)}</ul></section>')


def pagina_escopo(escopo: dict, concurso: str, rotas: "Rotas", rota: str,
                  rota_capa: str) -> str:
    """Hub de um escopo (`_COMUM` ou um cargo).

    Focal: as matérias, que é onde se estuda. Depois as seções de estudo, e por
    último as de consulta, num registro visivelmente mais quieto.
    """
    rotulo = nome_escopo(escopo["nome"]) or nome_legivel(concurso)

    grupos = []
    if escopo["materias"]:
        cards = []
        for mat in escopo["materias"]:
            href = relativo(rota_irma(rota, "materias", mat["slug"]), rota)
            # o que a matéria TEM, não zeros: matéria só com plano dizia
            # "0 assuntos · 0 com áudio", que não informa nada
            partes = []
            if mat["n_assuntos"]:
                partes.append(f'{mat["n_assuntos"]} assuntos')
                if mat["n_com_podcast"]:
                    partes.append(f'{mat["n_com_podcast"]} com áudio')
            if mat.get("mapa"):
                partes.append(f'{mat["mapa"]["n_topicos"]} tópicos do edital')
            if mat.get("aprofundamento_em"):
                partes.append("aprofundado no comum")
            # as duas medidas já no hub: são as perguntas que se fazem ao escolher
            # a matéria — "quanto eu já fiz?" e "quanto disto tem material?"
            cards.append(f"""<a class="item" href="{esc(href)}">
  <h3>{esc(mat["nome"])}</h3>
  <div class="meta">{esc(" · ".join(partes))}</div>
  {medidor(linhas_da_materia(mat), compacto=True)}
</a>""")
        n_top = sum(m["mapa"]["n_topicos"] for m in escopo["materias"] if m.get("mapa"))
        quantos = [f'{len(escopo["materias"])} matérias']
        if escopo["n_assuntos"]:
            quantos.append(f'{escopo["n_assuntos"]} assuntos aprofundados')
        if n_top:
            quantos.append(f"{n_top} tópicos do edital")
        grupos.append(f"""<section class="grupo grupo-escopo">
  <header><h2>Matérias</h2>
  <span class="quantos">{esc(" · ".join(quantos))}</span></header>
  <div class="grade">{"".join(cards)}</div>
</section>""")

    for registro, titulo, explica in (
            ("estudo", "Estudo e planejamento",
             "O que fazer e como treinar."),
            ("consulta", "Consulta",
             "As regras, as fontes e o histórico — para conferir quando precisar.")):
        secoes = [s for s in escopo["secoes"] if s["registro"] == registro]
        if not secoes:
            continue
        blocos = []
        for s in secoes:
            # a rota da seção é sempre `{escopo}/{slug}/index.html`, mesmo quando ela
            # foi colapsada no documento único — o caminho é o mesmo, muda o conteúdo
            href = relativo(f'{PurePosixPath(rota).parent}/{s["slug"]}/index.html', rota)
            n = []
            if s["n_documentos"] > 1:
                n.append(f'{s["n_documentos"]} documentos')
            if s["n_anexos"]:
                n.append(f'{s["n_anexos"]} arquivo(s) · {tamanho_legivel(s["bytes_anexos"])}')
            blocos.append(
                f'<li><span class="ordinal">{esc(s["ordinal"])}</span>'
                f'<a href="{esc(href)}">{esc(s["rotulo"])}</a>'
                f'<span class="meta">{esc(" · ".join(n))}</span></li>')
        grupos.append(f"""<section class="grupo grupo-escopo" data-registro="{registro}">
  <header><h2>{esc(titulo)}</h2><span class="quantos">{len(secoes)} seções</span></header>
  <p class="explica">{esc(explica)}</p>
  <ul class="lista-secoes">{"".join(blocos)}</ul>
</section>""")

    corpo = f"""<div class="papel">
  <div class="sobrancelha">{esc(nome_legivel(concurso))}</div>
  <h1>{esc(rotulo)}</h1>
  {medidor(linhas_do_escopo(escopo))}
</div>
<div style="margin-top:1.25rem">{"".join(grupos)}</div>"""
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a>'
              f' › {esc(rotulo)}')
    return pagina(f"{rotulo} — {nome_legivel(concurso)}", trilha, corpo, rota)


def bloco_herdado(secao: dict, slug_conc: str, rota: str) -> str:
    """O que este escopo herda do `_COMUM`, como link — nunca como cópia.

    Existe porque a bibliografia mora no `_COMUM` e o estudante do cargo não tinha
    caminho nenhum até ela: a seção simplesmente não existia no galho do cargo, e
    sumia sem aviso. O conteúdo continua num lugar só; aqui vai o ponteiro.
    """
    herdado = secao.get("herdado_de")
    if not herdado:
        return ""
    destino = (f'{slug_conc}/{herdado["escopo_slug"]}'
               f'/{herdado["secao_slug"]}/index.html')
    partes = []
    if herdado["n_documentos"]:
        partes.append(f'{herdado["n_documentos"]} documento(s)')
    if herdado["n_anexos"]:
        partes.append(f'{herdado["n_anexos"]} arquivo(s)')
    resumo = " · ".join(partes) or "sem conteúdo"
    proprio = secao["documentos"] or secao["anexos"]
    titulo = ("Também vale para este cargo" if proprio
              else f'{esc(secao["rotulo"])} deste concurso')
    return f"""<section class="cartao herdado">
  <h2>{titulo}</h2>
  <p class="meta">Vale para todos os cargos e fica em
     <strong>{esc(nome_escopo(herdado["escopo"]) or herdado["escopo"])}</strong>,
     num lugar só — {esc(resumo)}.</p>
  <p><a class="botao" href="{relativo(destino, rota)}">Abrir {esc(herdado["rotulo"])} do comum</a></p>
</section>"""


def pagina_secao(secao: dict, escopo: dict, concurso: str, rotas: "Rotas",
                 rota: str, rota_escopo: str, rota_capa: str,
                 slug_conc: str = "") -> str:
    """Índice de uma seção: seus documentos, seus anexos e o que ela herda."""
    rotulo_esc = nome_escopo(escopo["nome"]) or nome_legivel(concurso)
    proprio = secao["documentos"] or secao["anexos"]
    corpo = f"""<div class="papel">
  <div class="sobrancelha">{esc(secao["ordinal"])} · {esc(rotulo_esc)}</div>
  <h1>{esc(secao["rotulo"])}</h1>
  {lista_documentos(secao, rotas, rota) if proprio else ""}
</div>
{bloco_herdado(secao, slug_conc, rota)}
{lista_anexos(secao, rotas, rota)}"""
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="{relativo(rota_escopo, rota)}">{esc(rotulo_esc)}</a> › '
              f'{esc(secao["rotulo"])}')
    return pagina(f'{secao["rotulo"]} — {nome_legivel(concurso)}', trilha, corpo, rota)


def bloco_sumario(md: str, rota_atual: str) -> str:
    """Índice de seções na lateral, quando o documento é longo o bastante.

    Reusa `.colunas`/`.lateral` da página de assunto em vez de inventar layout: os
    documentos do vault têm de 50 a 2.400 linhas, e rolar 600 linhas sem índice é o
    que faz a pessoa desistir e voltar ao Obsidian.
    """
    itens = md2html.sumario(md)
    if len(itens) < 4:
        return ""
    links = "".join(
        f'<li class="n{x["nivel"]}"><a href="#{esc(x["id"])}">{esc(x["texto"])}</a></li>'
        for x in itens)
    return (f'<section class="cartao sumario"><h3>Nesta página</h3>'
            f'<ul>{links}</ul></section>')


def pagina_documento(doc: dict, secao: dict, escopo: dict, concurso: str,
                     rotas: "Rotas", rota: str, trilha_meio: tuple,
                     rota_capa: str, slug_conc: str = "") -> str:
    md = Path(doc["caminho"]).read_text(encoding="utf-8")
    corpo_html = md2html.converter(md, wikilink_resolver=rotas.resolvedor(rota))
    sumario = bloco_sumario(md, rota)

    if sumario:
        corpo = (f'<div class="colunas">'
                 f'<article class="papel">{corpo_html}</article>'
                 f'<aside class="lateral">{sumario}</aside></div>')
    else:
        corpo = f'<article class="papel">{corpo_html}</article>'

    # A seção colapsada É este documento, então o que ela herda tem de aparecer
    # AQUI. Quando cada cargo ganhou catálogo próprio, a seção passou a ter um
    # documento só, colapsou, e o bloco de herança sumiu junto: o cargo exibia a
    # própria bibliografia e perdia o caminho para a do comum, que é a maior.
    corpo += bloco_herdado(secao, slug_conc, rota)

    # o nível do meio da trilha é a seção quando ela tem índice próprio, e o escopo
    # quando a seção É este documento
    rota_meio, rotulo_meio = trilha_meio
    trilha = (f'<a href="{relativo(rota_capa, rota)}">{esc(nome_legivel(concurso))}</a> › '
              f'<a href="{relativo(rota_meio, rota)}">{esc(rotulo_meio)}</a> › '
              f'{esc(doc["titulo"])}')
    return pagina(f'{doc["titulo"]} — {nome_legivel(concurso)}', trilha, corpo, rota,
                  doc.get("resumo", ""))


def fmt_valor(campo: str, v) -> str:
    """Salário numérico vira moeda; o resto sai como veio.

    O `.meta.json` guarda `remuneracao: 4762.97`, e imprimir isso cru numa ficha
    de concurso fica com cara de dado bruto vazado para a tela.
    """
    if campo == "salario" and isinstance(v, (int, float)):
        return "R$ " + f"{v:,.2f}".replace(",", "·").replace(".", ",").replace("·", ".")
    return str(v)


def pagina_capa(modelo: dict, rotas: "Rotas", rota: str) -> str:
    meta = modelo.get("meta", {})
    campos = []
    if meta.get("banca"):
        campos.append(("Banca", meta["banca"]))
    dk = meta.get("datas_chave") or {}
    if dk.get("prova_data"):
        try:
            d = datetime.strptime(dk["prova_data"], "%Y-%m-%d")
            faltam = (d - datetime.now()).days
            campos.append(("Prova", d.strftime("%d/%m/%Y") +
                           (f" · faltam {faltam} dias" if faltam > 0 else "")))
        except ValueError:
            campos.append(("Prova", dk["prova_data"]))
    # Vagas e salário são POR CARGO num concurso multi-cargo, e é assim que o
    # `.meta.json` os guarda — em `cargos_validados[]`. Lendo só da raiz, os dois
    # campos NUNCA renderizavam: o SEDES tem 3 cargos com vagas e salários
    # diferentes, e não existe número de raiz que os represente sem inventar um
    # agregado. Preferir a raiz quando ela existir (concurso de cargo único),
    # cair para o detalhe por cargo quando não.
    for rotulo, campo in (("Vagas (AC)", "vagas_ac"), ("Salário", "salario")):
        if meta.get(campo):
            campos.append((rotulo, fmt_valor(campo, meta[campo])))
            continue
        por_cargo = []
        for c in meta.get("cargos_validados") or []:
            if not isinstance(c, dict):
                continue
            v = c.get(campo) or (c.get("vagas_total") if campo == "vagas_ac" else None)
            # A sigla é o identificador que o site usa na navegação inteira; usar
            # `nome_legivel` aqui seria errado — ela é para slug de CONCURSO.
            if c.get("sigla") and v:
                por_cargo.append((c["sigla"], fmt_valor(campo, v)))
        if por_cargo:
            campos.append((rotulo + " por cargo",
                           " · ".join(f"{s}: {v}" for s, v in por_cargo)))
    ep = meta.get("estrutura_prova") or {}
    if isinstance(ep, dict) and (ep.get("objetiva") or {}).get("total_questoes"):
        campos.append(("Questões", ep["objetiva"]["total_questoes"]))

    ficha = ""
    if campos:
        ficha = ('<dl class="ficha">' + "".join(
            f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in campos)
            + "</dl>")

    # Um card por escopo — o galho, não a matéria. A grade de matérias, que ficava
    # aqui, desceu para o hub do escopo: na capa o que importa é escolher o cargo.
    cards = []
    for escopo in modelo.get("escopos") or modelo["cargos"]:
        href = relativo(rota_irma(rota, escopo["slug"]), rota)
        # só o que o escopo TEM: cargo sem aprofundamento próprio dizia
        # "0 assunto(s)", que ocupa a linha sem informar nada
        n = [f'{escopo["n_materias"]} matéria(s)']
        if escopo["n_assuntos"]:
            n.append(f'{escopo["n_assuntos"]} assuntos aprofundados')
        n_docs = sum(s["n_documentos"] for s in escopo.get("secoes") or [])
        if n_docs:
            n.append(f"{n_docs} documento(s)")
        cards.append(f"""<a class="item concurso-item" href="{esc(href)}">
  <h3>{esc(nome_escopo(escopo["nome"]) or "Material")}
  {'<span class="tag">comum</span>' if escopo["tipo"] == "comum" else ""}</h3>
  <div class="meta">{esc(" · ".join(n))}</div>
  {medidor(linhas_do_escopo(escopo), compacto=True)}
</a>""")

    r = modelo["resumo"]
    resumo_txt = (f'{r["n_materias"]} matéria(s) · {r["n_assuntos"]} assuntos '
                  f'aprofundados · {r.get("n_documentos", 0)} documento(s)')
    corpo = f"""<div class="papel">
  <div class="sobrancelha">Preparação</div>
  <h1>{esc(nome_legivel(modelo["concurso"]))}</h1>
  {ficha}
  <p>{esc(resumo_txt)}</p>
</div>
<div class="grade" style="margin-top:1.25rem">{"".join(cards)}</div>"""
    trilha = f'<a href="{relativo("index.html", rota)}">Concursos</a>'
    return pagina(nome_legivel(modelo["concurso"]), trilha, corpo, rota)


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def pagina_raiz(concursos: list[dict]) -> str:
    """Índice de TODOS os concursos publicados (a porta de entrada do site)."""
    if not concursos:
        corpo = ('<div class="papel"><h1>Nenhum concurso publicado</h1>'
                 '<p>Gere um concurso com a skill <code>concurso-publica</code>.</p></div>')
        return pagina("Estudo para concursos", "", corpo, "index.html")

    def cartao(c: dict) -> str:
        etiquetas = []
        if c.get("banca"):
            etiquetas.append(esc(c["banca"]))
        if c.get("prova_data"):
            try:
                d = datetime.strptime(c["prova_data"], "%Y-%m-%d")
                faltam = (d - datetime.now()).days
                etiquetas.append(d.strftime("%d/%m/%Y") +
                                 (f" · faltam {faltam} dias" if faltam > 0 else " · realizada"))
            except ValueError:
                etiquetas.append(esc(c["prova_data"]))
        nome = c["concurso"]
        tag = ""
        if "PREVISTO" in nome.upper():
            tag = '<span class="tag">previsto</span>'
        elif "RETIFICADO" in nome.upper():
            tag = '<span class="tag">retificado</span>'
        return f"""<a class="item concurso-item" href="{esc(c["slug"])}/index.html">
  <h3>{esc(nome_legivel(nome))}{tag}</h3>
  <div class="meta">{" · ".join(etiquetas)}</div>
  <div class="resumo">{c.get("n_materias", 0)} matéria(s) · {c.get("n_assuntos", 0)} assuntos aprofundados</div>
</a>"""

    # agrupar por órgão
    por_orgao: dict[str, list[dict]] = {}
    for c in concursos:
        orgao = (c.get("orgao") or re.split(r"[_-]", c["concurso"])[0] or "Outros").upper()
        por_orgao.setdefault(orgao, []).append(c)

    def chave_data(c):
        return c.get("prova_data") or "9999"

    blocos = []
    for orgao in sorted(por_orgao):
        lista = sorted(por_orgao[orgao], key=chave_data)
        cartoes = "".join(cartao(c) for c in lista)
        plural = "concurso" if len(lista) == 1 else "concursos"
        blocos.append(f"""<section class="grupo-orgao">
  <header><h2>{esc(orgao)}</h2><span class="quantos">{len(lista)} {plural}</span></header>
  <div class="grade">{cartoes}</div>
</section>""")
    itens = blocos

    corpo = f"""<div class="papel">
  <div class="sobrancelha">Vault de estudos</div>
  <h1>Concursos</h1>
  <p>{len(concursos)} concurso(s) em {len(por_orgao)} órgão(s), publicados a partir do vault.</p>
</div>
<div style="margin-top:1.25rem">{"".join(itens)}</div>"""
    return pagina("Estudo para concursos", "", corpo, "index.html")


def ler_manifestos(raiz: Path) -> list[dict]:
    """Lê os manifestos de todos os concursos já publicados nesta pasta.
    Permite deploy incremental: publicar um concurso não apaga os outros do índice."""
    achados = []
    for man in sorted(raiz.glob("*/.concurso.json")):
        try:
            achados.append(json.loads(man.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return achados


def copiar_anexos(secao: dict, destino: Path, rota_secao: str) -> None:
    """Copia os anexos da seção para dentro do site, na rota já registrada.

    O site precisa ser autossuficiente: servido pelo nginx a partir de `/srv/site`,
    nada que esteja fora dessa pasta é alcançável pelo navegador. Sem a cópia, o
    link da lei funcionaria só na máquina do vault.
    """
    for a in secao["anexos"]:
        alvo = destino / rota_anexo(rota_secao, a)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        origem = Path(a["caminho"])
        # o rmtree do concurso já limpou; a checagem cobre anexo homônimo em duas
        # subpastas da mesma seção, que resolveria para a mesma rota
        if not alvo.exists():
            shutil.copy2(origem, alvo)


def montar_rotas(modelo: dict, slug_conc: str) -> tuple[Rotas, list[dict]]:
    """Passo 1 do build: decide onde cada página mora e indexa os nomes do vault.

    Roda ANTES de qualquer renderização, porque o resolvedor de wikilinks precisa
    conhecer a URL de páginas que ainda não existem. Devolve o índice de rotas e o
    plano de renderização (a lista do que gerar, na ordem).
    """
    rotas = Rotas()
    plano: list[dict] = []

    rota_capa = f"{slug_conc}/index.html"
    # Só o nome do concurso. `00-INDICE` NÃO é registrado: o vault tem esse nome em
    # meia dúzia de lugares (raiz do concurso, materiais, leis-baixadas, mapas), e
    # registrá-lo aqui fazia todo `[[00-INDICE]]` do vault — inclusive o das leis —
    # cair na capa do concurso. Wikilink resolvido para o lugar errado é pior que
    # wikilink morto: o morto avisa, o errado não.
    rotas.registrar(rota_capa, modelo["concurso"])
    plano.append({"rota": rota_capa, "tipo": "capa"})

    for escopo in modelo.get("escopos") or modelo["cargos"]:
        esc_slug = escopo.get("slug") or "geral"
        rota_esc = f"{slug_conc}/{esc_slug}/index.html"
        # o `99-Status` não vira página (a navegação do site é o índice), mas quem
        # aponta para ele quer o progresso — e os checkboxes dele são uma das três
        # parcelas da barra de tarefas que o hub mostra
        rotas.registrar(rota_esc, escopo["nome"], "99-Status")
        plano.append({"rota": rota_esc, "tipo": "escopo", "escopo": escopo,
                      "rota_capa": rota_capa})

        for secao in escopo.get("secoes") or []:
            rota_sec = f'{slug_conc}/{esc_slug}/{secao["slug"]}/index.html'
            rotulo_esc = nome_escopo(escopo["nome"])

            # Seção com um documento só e sem anexo É o documento. Um índice que
            # lista um único item é página inútil, e gerava caminho redundante
            # (`titulos/titulos/`, `cronograma/cronograma-macro/`).
            if len(secao["documentos"]) == 1 and not secao["anexos"]:
                doc = secao["documentos"][0]
                rotas.registrar(rota_sec, doc["arquivo"], doc["slug"], secao["slug"])
                _registrar_ancoras(rotas, doc, rota_sec)
                plano.append({"rota": rota_sec, "tipo": "documento", "doc": doc,
                              "secao": secao, "escopo": escopo,
                              "trilha_meio": (rota_esc, rotulo_esc),
                              "rota_capa": rota_capa,
                              # a seção foi colapsada: a rota da página É a da seção,
                              # então é aqui que os anexos dela seriam copiados
                              "colapsada": True})
                continue

            rotas.marcar(rota_sec)
            plano.append({"rota": rota_sec, "tipo": "secao", "secao": secao,
                          "escopo": escopo, "rota_escopo": rota_esc,
                          "rota_capa": rota_capa})

            for doc in secao["documentos"]:
                rota_doc = (f'{slug_conc}/{esc_slug}/{secao["slug"]}'
                            f'/{doc["slug"]}/index.html')
                _registrar_ancoras(rotas, doc, rota_doc)
                # o documento é citado pelo nome do arquivo (com e sem prefixo
                # numérico) — as duas formas aparecem nos wikilinks do vault
                rotas.registrar(rota_doc, doc["arquivo"], doc["slug"])
                plano.append({"rota": rota_doc, "tipo": "documento", "doc": doc,
                              "secao": secao, "escopo": escopo,
                              "trilha_meio": (rota_sec, secao["rotulo"]),
                              "rota_capa": rota_capa})

            # anexos: rota determinística, registrada antes da cópia, para que os
            # wikilinks que apontam direto para o PDF da lei resolvam
            for anexo in secao["anexos"]:
                rotas.registrar(rota_anexo(rota_sec, anexo), anexo["arquivo"])

        for materia in escopo["materias"]:
            rota_mat = f'{slug_conc}/{esc_slug}/materias/{materia["slug"]}/index.html'
            rotas.registrar(rota_mat, materia["slug"],
                            f'00-INDICE-{materia["slug"]}')
            plano.append({"rota": rota_mat, "tipo": "materia", "materia": materia,
                          "escopo": escopo, "rota_escopo": rota_esc,
                          "rota_capa": rota_capa})

            for assunto in materia["assuntos"]:
                rota_a = (f'{slug_conc}/{esc_slug}/materias/{materia["slug"]}'
                          f'/{assunto["slug"]}/index.html')
                aprofs = assunto.get("aprofundamentos") or []
                # 1ª classe — página: o slug da pasta e o nome de cada .md de
                # aprofundamento (o Obsidian resolve por nome de arquivo, e o nome
                # completo é `{assunto}--{nivel}--{fonte}--{CONCURSO}`)
                nomes = [assunto["slug"]] + [Path(a["resumo_md"]).stem for a in aprofs]
                rotas.registrar(rota_a, *nomes)

                for i, ap in enumerate(aprofs):
                    ident = ident_aprof(ap, i)
                    # 2ª classe — artefato embutido: flashcards não são página,
                    # então o wikilink do baralho vai para a âncora do quiz
                    for chave in ("obsidian", "anki"):
                        fc = (ap.get("flashcards") or {}).get(chave)
                        if fc:
                            rotas.registrar(rota_a, fc, ancora="flashcards")
                    # 3ª classe — arquivo copiado: mídia vive em media/<ident>/.
                    # A rota é determinística, então dá para registrar aqui, antes
                    # da cópia — e é o que impede os 368 wikilinks de mídia dos
                    # pacotes NotebookLM de virarem parede de link morto.
                    for nome in (ap.get("midias") or {}).values():
                        if nome:
                            rotas.registrar(
                                f'{slug_conc}/{esc_slug}/materias/{materia["slug"]}'
                                f'/{assunto["slug"]}/media/{ident}/{nome}', nome)

                rota_nb = (f'{slug_conc}/{esc_slug}/materias/{materia["slug"]}'
                           f'/{assunto["slug"]}/notebooklm/index.html')
                tem_pack = any(ap.get("pack_notebooklm") for ap in aprofs)
                plano.append({"rota": rota_a, "tipo": "assunto", "assunto": assunto,
                              "materia": materia, "escopo": escopo,
                              "rota_materia": rota_mat, "rota_capa": rota_capa,
                              "rota_notebooklm": rota_nb if tem_pack else None})
                if tem_pack:
                    rotas.registrar(rota_nb, f'_fonte-notebooklm-{assunto["slug"]}')
                    plano.append({"rota": rota_nb, "tipo": "notebooklm",
                                  "assunto": assunto, "materia": materia,
                                  "rota_assunto": rota_a, "rota_capa": rota_capa})
    return rotas, plano


def construir(modelo: dict, destino: Path, com_raiz: bool = True) -> dict:
    """Gera o site de UM concurso em destino/<slug-do-concurso>/ e (re)gera o
    índice raiz listando todos os concursos publicados em destino/."""
    destino.mkdir(parents=True, exist_ok=True)

    concurso = modelo["concurso"]
    slug_conc = re.sub(r"[^A-Za-z0-9_-]+", "-", concurso).strip("-").lower()
    base = destino / slug_conc

    # Limpar SÓ a pasta deste concurso antes de gerar. Sem isso, quando a
    # estrutura de pastas muda, o layout antigo sobrevive em out/ — e o
    # `rsync --delete` do deploy NÃO o remove, porque ele existe na origem.
    # O escopo é deliberado: apagar `destino` mataria os concursos irmãos e o
    # assets/ compartilhado, e o índice raiz é remontado dos manifestos.
    #
    # Custo conhecido: a mídia é recopiada a cada build (um podcast passa de
    # 70 MB). O deploy não sofre — `copy2` preserva o mtime, então o rsync
    # continua incremental — mas o disco local reescreve tudo. A correção certa é
    # varrer por diferença contra o conjunto de arquivos efetivamente escritos, o
    # que fica natural quando a tabela de rotas existir; guarda de mtime aqui não
    # resolveria nada, porque o rmtree apaga a mídia antes da comparação.
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)

    # assets ficam na raiz e são compartilhados por todos os concursos
    dest_assets = destino / "assets"
    dest_assets.mkdir(exist_ok=True)
    for nome in ("site.css", "site.js"):
        origem = ASSETS / nome
        if origem.exists():
            shutil.copy2(origem, dest_assets / nome)

    # ---- passo 1: decidir as rotas ----------------------------------------- #
    rotas, plano = montar_rotas(modelo, slug_conc)

    # ---- passo 2: renderizar ---------------------------------------------- #
    n_paginas = 0
    rota_capa = f"{slug_conc}/index.html"
    for item in plano:
        rota = item["rota"]
        alvo = destino / rota
        alvo.parent.mkdir(parents=True, exist_ok=True)
        tipo = item["tipo"]
        if tipo == "capa":
            html_pag = pagina_capa(modelo, rotas, rota)
        elif tipo == "escopo":
            html_pag = pagina_escopo(item["escopo"], concurso, rotas, rota, rota_capa)
        elif tipo == "secao":
            html_pag = pagina_secao(item["secao"], item["escopo"], concurso, rotas,
                                    rota, item["rota_escopo"], rota_capa, slug_conc)
            copiar_anexos(item["secao"], destino, rota)
        elif tipo == "documento":
            html_pag = pagina_documento(item["doc"], item["secao"], item["escopo"],
                                        concurso, rotas, rota, item["trilha_meio"],
                                        rota_capa, slug_conc)
            # Só quando a seção foi colapsada neste documento: aí a rota da página é
            # a da seção e `rota_anexo` acerta o destino. Copiar aqui sempre fazia
            # CADA documento receber uma cópia inteira dos anexos da seção — 685
            # PDFs no vault real em vez de 78, e o site pulando de 260 MB para 534.
            if item.get("colapsada"):
                copiar_anexos(item["secao"], destino, rota)
        elif tipo == "materia":
            html_pag = pagina_materia(item["materia"], concurso,
                                      Path(item["materia"]["dir"]),
                                      rotas, rota, item["rota_escopo"])
        elif tipo == "notebooklm":
            html_pag = pagina_notebooklm(item["assunto"], item["materia"], concurso,
                                         rotas, rota, item["rota_assunto"], rota_capa)
        else:
            html_pag = pagina_assunto(item["assunto"], item["materia"], concurso,
                                      alvo.parent, rotas, rota,
                                      item["rota_materia"], rota_capa,
                                      item.get("rota_notebooklm"))
        alvo.write_text(html_pag, encoding="utf-8")
        n_paginas += 1

    # manifesto deste concurso (alimenta o índice raiz e o deploy)
    #
    # `origem` é o que permite RECONSTRUIR este concurso sem que ninguém precise
    # lembrar de onde ele veio. O deploy envia o `out/site/` inteiro com
    # `rsync --delete`, mas só constrói o concurso que recebeu por argumento — sem
    # este campo, um concurso construído numa sessão anterior é republicado com o
    # conteúdo daquela data, sem aviso. Foi o que aconteceu com o BB_2027_PREVISTO
    # enquanto se publicava o SEDES_2026.
    meta = modelo.get("meta", {})
    (base / ".concurso.json").write_text(json.dumps({
        "concurso": concurso,
        "slug": slug_conc,
        "origem": modelo.get("dir"),
        "orgao": meta.get("orgao") or re.split(r"[_-]", concurso)[0],
        "banca": meta.get("banca"),
        "prova_data": (meta.get("datas_chave") or {}).get("prova_data"),
        "n_materias": modelo["resumo"]["n_materias"],
        "n_assuntos": modelo["resumo"]["n_assuntos"],
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    n_concursos = 0
    if com_raiz:
        manifestos = ler_manifestos(destino)
        (destino / "index.html").write_text(pagina_raiz(manifestos), encoding="utf-8")
        n_paginas += 1
        n_concursos = len(manifestos)

    return {"paginas": n_paginas, "concurso": concurso,
            "destino": str(base), "concursos_no_indice": n_concursos}


def main():
    ap = argparse.ArgumentParser(description="Gera o site estático de um concurso")
    ap.add_argument("--concurso-dir", type=Path, default=None)
    ap.add_argument("--modelo", type=Path, default=None,
                    help="usar um site-model.json já coletado")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if args.modelo:
        modelo = json.loads(args.modelo.read_text(encoding="utf-8"))
    elif args.concurso_dir:
        if not args.concurso_dir.is_dir():
            sys.stderr.write(f"ERRO: não é diretório: {args.concurso_dir}\n")
            sys.exit(1)
        modelo = coletar_concurso(args.concurso_dir)
    else:
        sys.stderr.write("ERRO: informe --concurso-dir ou --modelo\n")
        sys.exit(1)

    if modelo["resumo"]["n_assuntos"] == 0:
        sys.stderr.write("AVISO: nenhum assunto aprofundado — o site sairá vazio.\n")

    r = construir(modelo, args.out)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
