#!/usr/bin/env python3
"""quadrix.py — o perfil Instituto Quadrix: caderno, gabarito e divisão por área.

A afere nasceu sobre a CESGRANRIO (BB), e três premissas daquela banca não valem
aqui — medido nos cadernos e no gabarito do SEDES/DF 2026 e em três concursos CRESS:

1. **Tipo não é prova.** A Quadrix aplica cadernos TIPO A, B e C com as MESMAS 60
   questões, só com os blocos em rodízio: no SEDES, Conhecimentos Gerais é 1–20 no
   Tipo A, 41–60 no B e 21–40 no C, com enunciado e letra idênticos. Tratar os três
   como provas — o modelo da CESGRANRIO, onde A/B/C têm questões diferentes — contaria
   cada questão três vezes e triplicaria o `provas_aferidas_n`.
2. **A prova divide por ÁREA, não por matéria.** Os cabeçalhos do caderno são
   "CONHECIMENTOS GERAIS", "…ESPECÍFICOS COMUNS…", "…DA ESPECIALIDADE"; a matéria de
   cada questão não está impressa em lugar nenhum. A faixa é da área, e o vínculo
   questão → matéria do vault é JULGAMENTO do agente (`mapa_questoes.py`).
3. **O gabarito é uma grade** — linha de números, linha de letras —, com uma seção por
   cargo (e por tipo), `X` na questão anulada e "PRELIMINAR"/"DEFINITIVO" no cabeçalho.
   O formato `N - X` da CESGRANRIO não casa nada nele.

O caderno não imprime o tipo: nenhuma página diz "TIPO A". Ele é deduzido pela ordem
dos blocos contra a tabela de divisão do gabarito — e conferido, porque gabarito do
tipo errado devolve 60 respostas plausíveis e erradas, que é o desfecho caro da skill.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrair_questoes import Faixa  # noqa: E402
from gabarito import GabaritoErro  # noqa: E402
from prova_id import texto  # noqa: E402

# Uma questão Quadrix começa sempre por "QUESTÃO N" sozinho na linha (texto sem
# layout). Nos 4 cadernos medidos, 230 de 230 marcadores apareceram assim — é o que
# torna a faixa conferível questão a questão, coisa que o número solto da CESGRANRIO
# não permite.
MARCA = re.compile(r"^QUEST[ÃA]O\s+(\d{1,3})\s*$", re.M)

# Cabeçalho de seção do gabarito: "TDAS - AGENTE SOCIAL (TIPO A)" no SEDES,
# "2.2 ASSISTENTE SOCIAL (CÓDIGO 400)" nos CRESS. O nome não pode conter "(": a linha
# de cabeçalho da tabela de divisão termina em "(TIPO C)" e não é seção.
_CABECALHO = re.compile(
    r"^\s*(?:\d+\.\d+\s+)?(?P<nome>[^\s(][^\n(]*?)\s*"
    r"\((?P<ext>TIPO\s+[A-Z]|C[ÓO]DIGOS?\b[^)\n]*)\)\s*$", re.M)
_NUMEROS = re.compile(r"^\s*\d{1,3}(?:\s+\d{1,3})+\s*$")
_LETRAS = re.compile(r"^\s*[A-EX](?:\s+[A-EX])+\s*$")
_LINHA_AREA = re.compile(
    r"^\s*(?P<nome>[A-Za-zÀ-ÿ][^\d\n]*?)\s{2,}"
    r"(?P<faixas>\d{1,3}\s+a\s+\d{1,3}(?:\s+\d{1,3}\s+a\s+\d{1,3})*)\s*$")

_VAZIAS = {"de", "do", "da", "dos", "das", "e", "em", "a", "o", "as", "os", "no", "na",
           "tipo", "codigo", "codigos", "ate"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()


def tokens(s: str) -> set[str]:
    return {t for t in norm(s).split()
            if t not in _VAZIAS and len(t) > 1 and not t.isdigit()}


def e_quadrix(t: str) -> bool:
    """O caderno abre com "Quadrix | 2026"; o gabarito fecha com "INSTITUTO QUADRIX"."""
    return bool(re.search(r"\bQUADRIX\b", t, re.I))


def banca_do_pdf(pdf: Path) -> str:
    """'quadrix' ou 'cesgranrio'. A CESGRANRIO é o padrão porque foi o formato em que a
    skill nasceu: o que não se reconhece segue pelo caminho antigo, intacto.

    Lê o documento inteiro, não só a capa: o gabarito do SEDES tem 8 páginas e só a
    última assina "INSTITUTO QUADRIX" — ler as duas primeiras o classificava como
    CESGRANRIO e o mandava para o leitor de "N - X", que não acha nada.
    """
    return "quadrix" if e_quadrix(texto(pdf)) else "cesgranrio"


# --------------------------------------------------------------------------- #
# gabarito
# --------------------------------------------------------------------------- #
@dataclass
class SecaoGabarito:
    cargo: str                        # como impresso, sem o parêntese
    tipo: str | None                  # "A".."C"; None quando a prova tem um tipo só
    codigo: str | None                # "400"; None no SEDES, que não imprime código
    respostas: dict[int, str] = field(default_factory=dict)
    anuladas: set[int] = field(default_factory=set)

    @property
    def rotulo(self) -> str:
        return self.cargo + (f" (TIPO {self.tipo})" if self.tipo else "")

    def questoes(self) -> set[int]:
        return set(self.respostas) | self.anuladas


@dataclass
class Divisao:
    """Uma tabela "ÁREA DE CONHECIMENTO × QUESTÕES" do gabarito."""
    titulo: str | None                # cargo ou nível a que ela se aplica; None = todos
    tipos: list[str | None]           # ["A", "B", "C"], ou [None] com uma coluna só
    areas: dict[str, dict[str | None, tuple[int, int]]] = field(default_factory=dict)


@dataclass
class GabaritoQuadrix:
    fonte: str | None                 # "preliminar" | "definitivo"
    secoes: list[SecaoGabarito]
    divisoes: list[Divisao]


def fonte_do_gabarito(t: str) -> str | None:
    """PRELIMINAR e DEFINITIVO não são detalhe: entre um e outro a banca altera e anula
    questões, e a aferição feita sobre o preliminar precisa dizer isso no documento."""
    m = re.search(r"GABARITOS?\s+(PRELIMINAR|DEFINITIVO)", t, re.I)
    return m.group(1).lower() if m else None


def ler_grade(trecho: str) -> tuple[dict[int, str], set[int]]:
    """Pares (linha de números, linha de letras) → respostas e anuladas.

    A grade não admite desalinhamento: 20 números sobre 19 letras significa coluna
    perdida, e casar por posição atribuiria cada letra à questão vizinha.
    """
    linhas = [l for l in trecho.split("\n") if l.strip()]
    resp: dict[int, str] = {}
    anul: set[int] = set()
    i = 0
    while i < len(linhas) - 1:
        if _NUMEROS.match(linhas[i]) and _LETRAS.match(linhas[i + 1]):
            nums = [int(x) for x in linhas[i].split()]
            letras = linhas[i + 1].split()
            if len(nums) != len(letras):
                raise GabaritoErro(
                    f"grade desalinhada: {len(nums)} números ({nums[0]}…{nums[-1]}) "
                    f"sobre {len(letras)} letras — coluna perdida na extração")
            for n, l in zip(nums, letras):
                if l == "X":
                    anul.add(n)
                else:
                    resp[n] = l
            i += 2
            continue
        i += 1
    return resp, anul


def _divisoes(t: str) -> list[Divisao]:
    out: list[Divisao] = []
    titulo: str | None = None
    atual: Divisao | None = None
    for linha in t.split("\n"):
        if re.match(r"^\s*\d+\s+D[AO]S?\s+", linha):          # "1 DA DIVISÃO", "2 DOS…"
            titulo, atual = None, None
            continue
        m_tit = re.match(r"^\s*\d+\.\d+\s+(.+?)\s*$", linha)
        if m_tit:
            titulo, atual = re.sub(r"\s*\([^)]*\)\s*$", "", m_tit.group(1)).strip(), None
            continue
        if re.search(r"[ÁA]REA\s+DE\s+CONHECIMENTO", linha, re.I):
            tipos = re.findall(r"TIPO\s+([A-Z])", linha, re.I) or [None]
            atual = Divisao(titulo=titulo, tipos=[t.upper() if t else None for t in tipos])
            out.append(atual)
            continue
        if atual is None or not linha.strip():
            continue
        m = _LINHA_AREA.match(linha)
        if not m:
            atual = None
            continue
        faixas = [(int(a), int(b)) for a, b in re.findall(r"(\d{1,3})\s+a\s+(\d{1,3})",
                                                          m.group("faixas"))]
        if len(faixas) != len(atual.tipos):
            raise GabaritoErro(
                f"tabela de divisão com {len(atual.tipos)} coluna(s) de tipo, mas a linha "
                f"'{m.group('nome').strip()}' traz {len(faixas)} faixa(s)")
        atual.areas[m.group("nome").strip()] = dict(zip(atual.tipos, faixas))
    return [d for d in out if d.areas]


def ler_gabarito(pdf: Path) -> GabaritoQuadrix:
    t = texto(pdf)
    marcas = list(_CABECALHO.finditer(t))
    secoes: list[SecaoGabarito] = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(t)
        resp, anul = ler_grade(t[m.end():fim])
        if not resp and not anul:
            continue                       # subseção da tabela de divisão, não gabarito
        ext = m.group("ext")
        tipo = re.match(r"TIPO\s+([A-Z])", ext, re.I)
        codigo = re.search(r"(\d{2,})", ext)
        secoes.append(SecaoGabarito(
            cargo=m.group("nome").strip(),
            tipo=tipo.group(1).upper() if tipo else None,
            codigo=codigo.group(1) if codigo and not tipo else None,
            respostas=resp, anuladas=anul))
    if not secoes:
        raise GabaritoErro(f"nenhuma seção de gabarito legível em {pdf.name} — "
                           f"não parece um gabarito Quadrix")
    return GabaritoQuadrix(fonte=fonte_do_gabarito(t), secoes=secoes,
                           divisoes=_divisoes(t))


def divisao_do_cargo(gab: GabaritoQuadrix, cargo: str) -> Divisao:
    """A tabela de divisão que vale para o cargo — ou erro nomeado, nunca palpite.

    Três formatos medidos: uma tabela só para todos os cargos, com uma coluna por tipo
    (SEDES); uma tabela por cargo, com o mesmo título da seção do gabarito (CRESS-MG);
    e uma tabela por NÍVEL de cargo (CRESS-RS). No terceiro, nada no gabarito diz qual
    nível é o do cargo, e escolher seria inventar a faixa.
    """
    if not gab.divisoes:
        raise GabaritoErro("o gabarito não tem tabela de divisão por área")
    if len(gab.divisoes) == 1 and gab.divisoes[0].titulo is None:
        return gab.divisoes[0]
    alvo = norm(cargo)
    casadas = [d for d in gab.divisoes if d.titulo and norm(d.titulo) == alvo]
    if len(casadas) == 1:
        return casadas[0]
    if len(gab.divisoes) == 1:
        return gab.divisoes[0]
    titulos = "; ".join(d.titulo or "(sem título)" for d in gab.divisoes)
    raise GabaritoErro(
        f"o gabarito tem {len(gab.divisoes)} tabelas de divisão ({titulos}) e nenhuma "
        f"nomeia o cargo '{cargo}' — escolher uma seria inventar a faixa das áreas")


# --------------------------------------------------------------------------- #
# caderno
# --------------------------------------------------------------------------- #
def rodapes(t: str) -> list[str]:
    """Linhas que se repetem página a página e dizem algo (o cargo está numa delas).

    No SEDES: "Técnico em Desenvolvimento e Assistência Social (TDAS) | Especialidade:
    Agente Social", 14 vezes. A marca d'água "Prova aplicada" vira fragmentos de duas
    letras ("Pr", "ov") que também se repetem — o mínimo de dois termos os descarta.
    """
    cont = Counter(l.strip() for l in t.split("\n") if l.strip())
    return [l for l, n in cont.items() if n >= 3 and len(tokens(l)) >= 2]


def secoes_do_cargo(t_caderno: str, gab: GabaritoQuadrix,
                    cargo_prova: str | None = None) -> tuple[list[SecaoGabarito], str]:
    """As seções do gabarito que são do cargo do caderno (todas as dos tipos dele).

    Devolve (seções, cargo). Erro nomeado quando nenhum ou mais de um cargo casa: o
    gabarito traz 16 cargos no SEDES, e a seção de um vizinho dá resposta plausível.
    """
    nomes = list(dict.fromkeys(s.cargo for s in gab.secoes))
    if cargo_prova:
        alvo = tokens(cargo_prova)
        casados = [n for n in nomes if alvo and (alvo <= tokens(n) or tokens(n) <= alvo)]
        origem = f"--cargo-prova '{cargo_prova}'"
    else:
        rods = [tokens(r) for r in rodapes(t_caderno)]
        casados = [n for n in nomes if tokens(n) and any(tokens(n) <= r for r in rods)]
        # "ASSISTENTE SOCIAL" e "AGENTE FISCAL – ASSISTENTE SOCIAL" podem caber no
        # mesmo rodapé: vale o mais específico, e empate continua sendo empate.
        if len(casados) > 1:
            maior = max(len(tokens(n)) for n in casados)
            casados = [n for n in casados if len(tokens(n)) == maior]
        origem = "o rodapé do caderno"
    if not casados:
        raise GabaritoErro(
            f"nenhuma seção do gabarito casa com {origem} — cargos no gabarito: "
            + ", ".join(nomes))
    if len(casados) > 1:
        raise GabaritoErro(
            f"{origem} casa com {len(casados)} cargos do gabarito ({', '.join(casados)}) "
            f"— diga qual com --cargo-prova")
    return [s for s in gab.secoes if s.cargo == casados[0]], casados[0]


def cabecalhos_de_area(t_caderno: str, divisao: Divisao) -> dict[str, int]:
    """Posição (índice de linha) do cabeçalho de cada área no caderno.

    O gabarito diz "Conhecimentos Específicos Comuns"; o caderno, "CONHECIMENTOS
    ESPECÍFICOS COMUNS ÀS ESPECIALIDADES DO CARGO TDAS". Casa por sobreposição de
    termos, cada cabeçalho para uma área só — "ESPECIALIDADE" e "ESPECIALIDADES"
    distinguem as duas áreas de específicos, e por isso não se usa só inclusão.
    """
    caixa = re.compile(r"^[A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ \-/]{7,}$")
    linhas = t_caderno.split("\n")
    vistos: dict[str, int] = {}
    for i, l in enumerate(linhas):
        l = l.strip()
        if caixa.match(l) and l not in vistos:
            vistos[l] = i
    pares = []
    for area in divisao.areas:
        ta = tokens(area)
        for cab, i in vistos.items():
            tc = tokens(cab)
            if ta and ta <= tc:
                pares.append((len(ta & tc) / len(ta | tc), area, cab, i))
    out: dict[str, int] = {}
    usados: set[str] = set()
    for _, area, cab, i in sorted(pares, reverse=True):
        if area not in out and cab not in usados:
            out[area] = i
            usados.add(cab)
    return out


def numeros_por_area(t_caderno: str, posicoes: dict[str, int]) -> dict[str, list[int]]:
    """Os números de questão entre o cabeçalho de cada área e o seguinte."""
    linhas = t_caderno.split("\n")
    fim_prova = next((i for i, l in enumerate(linhas)
                      if l.strip().upper().startswith("PROVA DISCURSIVA")), len(linhas))
    ordem = sorted(posicoes.items(), key=lambda kv: kv[1])
    out: dict[str, list[int]] = {}
    for k, (area, ini) in enumerate(ordem):
        fim = ordem[k + 1][1] if k + 1 < len(ordem) else fim_prova
        trecho = "\n".join(linhas[ini:fim])
        out[area] = [int(n) for n in MARCA.findall(trecho)]
    return out


def tipo_do_caderno(t_caderno: str, divisao: Divisao) -> tuple[str | None, str]:
    """Deduz o tipo pela ordem dos blocos. Devolve (tipo, explicação).

    Para cada tipo da tabela, conta quantas questões de cada região do caderno caem na
    faixa que aquele tipo dá à área. Só aceita um vencedor que explique ao menos 90%
    das questões e sem empate — abaixo disso o caderno não é o que se pensa.
    """
    if divisao.tipos == [None]:
        return None, "prova de um tipo só"
    pos = cabecalhos_de_area(t_caderno, divisao)
    faltam = [a for a in divisao.areas if a not in pos]
    if faltam:
        return None, f"cabeçalho de área não achado no caderno: {', '.join(faltam)}"
    nums = numeros_por_area(t_caderno, pos)
    total = sum(len(v) for v in nums.values())
    if not total:
        return None, "nenhum marcador 'QUESTÃO N' no caderno"
    placar = {}
    for tipo in divisao.tipos:
        acertos = 0
        for area, ns in nums.items():
            a, b = divisao.areas[area][tipo]
            acertos += sum(a <= n <= b for n in ns)
        placar[tipo] = acertos
    melhor = max(placar.values())
    vencedores = [t for t, v in placar.items() if v == melhor]
    detalhe = ", ".join(f"{t}: {v}/{total}" for t, v in placar.items())
    if len(vencedores) != 1 or melhor < 0.9 * total:
        return None, f"ordem dos blocos não bate com nenhum tipo ({detalhe})"
    return vencedores[0], detalhe


@dataclass
class ParQuadrix:
    prova: Path
    gabarito: Path
    cargo: str | None = None
    tipo: str | None = None
    fonte: str | None = None
    secao: SecaoGabarito | None = None
    divisao: Divisao | None = None
    faixas: list[Faixa] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)

    def descricao(self) -> str:
        return (f"Quadrix · {self.cargo or 'cargo?'} · tipo {self.tipo or '—'}"
                f" · gabarito {self.fonte or '?'}")


def identificar_par(prova: Path, gabarito: Path,
                    cargo_prova: str | None = None) -> ParQuadrix:
    """Confere caderno e gabarito Quadrix e resolve cargo, tipo e faixas por área.

    Nunca levanta: devolve os problemas NOMEADOS, como `prova_id.conferir_par()`.
    Lista vazia é par confiável.
    """
    par = ParQuadrix(prova=prova, gabarito=gabarito)
    t_cad = texto(prova, layout=False)
    if not MARCA.search(t_cad):
        par.problemas.append(f"{prova.name} não tem marcadores 'QUESTÃO N' — não parece "
                             f"um caderno Quadrix (ou é o gabarito)")
        return par
    try:
        gab = ler_gabarito(gabarito)
    except GabaritoErro as e:
        par.problemas.append(str(e))
        return par
    par.fonte = gab.fonte
    try:
        secoes, par.cargo = secoes_do_cargo(t_cad, gab, cargo_prova)
        par.divisao = divisao_do_cargo(gab, par.cargo)
    except GabaritoErro as e:
        par.problemas.append(str(e))
        return par

    par.tipo, detalhe = tipo_do_caderno(t_cad, par.divisao)
    if par.divisao.tipos != [None] and par.tipo is None:
        par.problemas.append(f"não deu para deduzir o tipo do caderno: {detalhe}")
        return par
    par.secao = next((s for s in secoes if s.tipo == par.tipo), None)
    if par.secao is None:
        tem = ", ".join(s.tipo or "—" for s in secoes)
        par.problemas.append(f"o gabarito não tem a tabela do tipo {par.tipo} para "
                             f"{par.cargo} (tem: {tem})")
        return par

    par.faixas = sorted((Faixa(nome=area, primeira=f[par.tipo][0], ultima=f[par.tipo][1])
                         for area, f in par.divisao.areas.items()),
                        key=lambda x: x.primeira)
    esperadas = {n for f in par.faixas for n in range(f.primeira, f.ultima + 1)}
    faltam = sorted(esperadas - par.secao.questoes())
    if faltam:
        par.problemas.append(f"a seção {par.secao.rotulo} do gabarito não tem as questões "
                             f"{faltam}")
    return par


def bloco_da_area(prova: Path, faixa: Faixa) -> tuple[str, list[str]]:
    """Texto corrido da área, do cabeçalho até a área seguinte, para o AGENTE ler.

    Mesmo princípio de `extrair_questoes.bloco_da_materia()`: não recorta questão a
    questão — em duas colunas o enunciado não é contíguo. O que se garante é que todos
    os números da faixa aparecem no bloco como "QUESTÃO N".
    """
    t = texto(prova, layout=False)
    linhas = t.split("\n")
    div = Divisao(titulo=None, tipos=[None], areas={faixa.nome: {None: (0, 0)}})
    pos = cabecalhos_de_area(t, div)
    avisos: list[str] = []
    if faixa.nome not in pos:
        avisos.append(f"cabeçalho de '{faixa.nome}' não achado no caderno; o bloco é o "
                      f"caderno inteiro")
        bloco = t
    else:
        ini = pos[faixa.nome]
        caixa = re.compile(r"^CONHECIMENTOS\b|^PROVA DISCURSIVA\b")
        fim = next((i for i in range(ini + 1, len(linhas))
                    if caixa.match(linhas[i].strip())), len(linhas))
        bloco = "\n".join(linhas[ini:fim])
    achados = {int(n) for n in MARCA.findall(bloco)}
    faltam = [n for n in range(faixa.primeira, faixa.ultima + 1) if n not in achados]
    if faltam:
        avisos.append(f"não achei 'QUESTÃO N' das questões {faltam} no bloco — confira "
                      f"o recorte antes de julgar")
    return bloco, avisos
