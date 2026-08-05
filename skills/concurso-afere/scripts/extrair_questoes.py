#!/usr/bin/env python3
"""extrair_questoes.py — seções da prova e o bloco de questões de cada uma.

Três armadilhas medidas em provas reais da CESGRANRIO:

1. **Duas colunas.** Com `pdftotext -layout` a ordem de leitura embaralha (a questão
   5 aparece entre a 9 e a 10). Sem `-layout` a ordem sai correta — por isso o corpo
   é sempre lido sem layout, ao contrário da tabela de gabarito.

2. **Cabeçalho de seção quebrado em duas linhas.** "ATUALIDADES" numa linha e
   "DO MERCADO FINANCEIRO" na seguinte. Casar linha a linha perde a seção inteira.

3. **A última questão cai depois do cabeçalho da seção seguinte.** A questão 10 de
   Português aparece fisicamente abaixo de "LÍNGUA INGLESA" por causa da diagramação.
   Cortar no cabeçalho seguinte perde uma questão em dez.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prova_id import texto  # noqa: E402

# Cabeçalhos que existem no caderno mas NÃO são matéria: agrupam blocos.
AGRUPADORES = {"CONHECIMENTOS BÁSICOS", "CONHECIMENTOS ESPECÍFICOS",
               "CONHECIMENTOS GERAIS", "PROVA OBJETIVA", "REDAÇÃO"}

# Margem para o defeito 3: quanto texto pegar além do cabeçalho seguinte.
FOLGA_FIM = 1500


@dataclass
class Secao:
    nome: str                       # como aparece no caderno
    inicio: int                     # posição no texto
    bloco: str = ""                 # questões
    questoes: list[int] = field(default_factory=list)


@dataclass
class Faixa:
    nome: str
    primeira: int
    ultima: int

    @property
    def n(self) -> int:
        return self.ultima - self.primeira + 1


def distribuicao(pdf: Path) -> list[Faixa]:
    """Matérias e faixas de questão, lidas da TABELA DA CAPA.

    A capa declara "Língua Portuguesa … 1 a 10 … Língua Inglesa … 11 a 15". Isso é
    fato publicado pela banca — muito melhor que inferir a faixa contando números no
    corpo, que confunde numeração de questão com numeração de linha do texto e com
    número solto dentro de alternativa.

    A tabela é alinhada em colunas: a linha de nomes e a linha de faixas trazem os
    mesmos itens, na mesma ordem da esquerda para a direita. Casa-se por ORDEM, não
    por posição de caractere — alinhamento de coluna varia com o tamanho do nome.
    """
    t = texto(pdf, layout=True, ini=1, fim=1)
    linhas = t.split("\n")
    out: list[Faixa] = []
    for i, l in enumerate(linhas):
        faixas = re.findall(r"(\d{1,3})\s+a\s+(\d{1,3})", l)
        if not faixas:
            continue
        # a linha de nomes é a última acima que não seja cabeçalho da tabela
        nomes: list[str] = []
        for j in range(i - 1, max(i - 5, -1), -1):
            cand = linhas[j]
            if re.search(r"Quest[õo]es|Pontua[çc][ãa]o", cand, re.I):
                continue
            nomes = [n.strip() for n in re.split(r"\s{3,}", cand.strip()) if n.strip()]
            if len(nomes) == len(faixas):
                break
            nomes = []
        if len(nomes) != len(faixas):
            continue
        for nome, (a, b) in zip(nomes, faixas):
            out.append(Faixa(nome=nome, primeira=int(a), ultima=int(b)))
    return out


def _juntar_quebrados(linhas: list[str]) -> list[tuple[str, int]]:
    """Une cabeçalho partido em duas linhas. Devolve (nome, índice da 1ª linha)."""
    CAIXA = re.compile(r"^[A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ \-/]{4,}$")
    out: list[tuple[str, int]] = []
    i = 0
    while i < len(linhas):
        l = linhas[i].strip()
        if CAIXA.match(l):
            nome, fim = l, i
            # A continuação pode vir separada por linhas em branco — o pdftotext
            # insere quebras onde o PDF tinha só um salto de linha na arte. Sem
            # pular os vazios, "ATUALIDADES" e "DO MERCADO FINANCEIRO" viram duas
            # seções e a matéria some do casamento.
            j = i + 1
            while j < len(linhas) and not linhas[j].strip():
                j += 1
            if j < len(linhas):
                prox = linhas[j].strip()
                if CAIXA.match(prox) and re.match(r"^(DE|DA|DO|DAS|DOS|E|EM)\b", prox):
                    nome, fim = f"{l} {prox}", j
            out.append((nome, i))
            i = fim + 1
        else:
            i += 1
    return out


def bloco_da_materia(pdf: Path, faixa: Faixa) -> tuple[str, list[str]]:
    """Texto corrido da matéria, para o AGENTE ler. Devolve (bloco, avisos).

    Deliberadamente NÃO recorta questão a questão. Tentei: em PDF de duas colunas o
    texto de uma questão **não é contíguo** — na Prova A as questões 3 e 6 aparecem
    lado a lado e a 4 e a 5 depois, então qualquer corte "até a próxima marca"
    trunca o enunciado no meio. Recorte cirúrgico aqui seria precisão fingida.

    O que o script garante é o que dá para garantir: o bloco contém a matéria inteira
    e **todos os números da faixa aparecem nele**. Quem lê e separa as questões é o
    agente — que precisa ler o enunciado inteiro de qualquer forma para julgar.
    """
    t = texto(pdf, layout=False)
    avisos: list[str] = []

    # início: o cabeçalho da matéria no corpo; se não achar, o número da 1ª questão
    ini = None
    alvo = _norm(faixa.nome)
    for s in secoes(pdf):
        if _norm(s.nome) == alvo or alvo.startswith(_norm(s.nome)):
            ini = s.inicio
            break
    if ini is None:
        m = re.search(rf"\n{faixa.primeira}\n", t)
        ini = m.start() if m else 0
        avisos.append(f"cabeçalho de '{faixa.nome}' não localizado no corpo; "
                      f"recorte começou pela questão {faixa.primeira}")

    # fim: a primeira questão da matéria seguinte, com folga para a diagramação
    m_fim = re.search(rf"\n{faixa.ultima + 1}\n", t[ini:])
    fim = ini + m_fim.start() + FOLGA_FIM if m_fim else len(t)
    bloco = t[ini:min(fim, len(t))]

    faltam = [n for n in range(faixa.primeira, faixa.ultima + 1)
              if not re.search(rf"\n{n}\n", bloco)]
    if faltam:
        avisos.append(f"não achei a marca das questões {faltam} no bloco — "
                      f"confira o recorte antes de julgar")
    return bloco, avisos


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def secoes(pdf: Path, so_materias: bool = True) -> list[Secao]:
    """Seções do caderno, na ordem, já com o bloco de questões de cada uma."""
    t = texto(pdf, layout=False)
    linhas = t.split("\n")
    # posição de cada linha no texto, para recortar depois
    pos, acc = [], 0
    for l in linhas:
        pos.append(acc)
        acc += len(l) + 1

    achados = _juntar_quebrados(linhas)
    vistos: dict[str, Secao] = {}
    for nome, idx in achados:
        if so_materias and nome.strip() in AGRUPADORES:
            continue
        if so_materias and re.match(r"^(BANCO|AGENTE|GABARITO|LEIA|ATEN|ESCRITUR)", nome):
            continue
        # primeira ocorrência manda: as seguintes são rodapé de página
        if nome not in vistos:
            vistos[nome] = Secao(nome=nome, inicio=pos[idx])

    ordenadas = sorted(vistos.values(), key=lambda s: s.inicio)
    for i, s in enumerate(ordenadas):
        fim = ordenadas[i + 1].inicio if i + 1 < len(ordenadas) else len(t)
        # FOLGA_FIM cobre a questão que a diagramação empurrou para depois do
        # cabeçalho seguinte (ver defeito 3 no topo do arquivo)
        s.bloco = t[s.inicio:min(fim + FOLGA_FIM, len(t))]
        s.questoes = sorted({int(q) for q in re.findall(r"\n(\d{1,2})\n", s.bloco)})
    return ordenadas


def bloco_da_secao(pdf: Path, nome: str) -> Secao | None:
    alvo = nome.strip().upper()
    for s in secoes(pdf):
        if s.nome.upper() == alvo or alvo in s.nome.upper():
            return s
    return None


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prova", type=Path)
    ap.add_argument("--secao", help="recorta uma seção e imprime o bloco")
    ap.add_argument("--todas", action="store_true", help="inclui agrupadores")
    a = ap.parse_args()

    if a.secao:
        alvo = _norm(a.secao)
        f = next((x for x in distribuicao(a.prova)
                  if _norm(x.nome) == alvo or alvo in _norm(x.nome)), None)
        if not f:
            sys.stderr.write(
                f"ERRO: '{a.secao}' não está na tabela da capa. Disponíveis: "
                + ", ".join(x.nome for x in distribuicao(a.prova)) + "\n")
            return 1
        bloco, avisos = bloco_da_materia(a.prova, f)
        for av in avisos:
            sys.stderr.write(f"AVISO: {av}\n")
        print(bloco)
        return 2 if avisos else 0

    faixas = distribuicao(a.prova)
    if faixas:
        print("  matérias e faixas, pela tabela da CAPA:")
        for f in faixas:
            print(f"    {f.nome:<38} questões {f.primeira}–{f.ultima}  ({f.n})")
        print()
    print("  seções encontradas no CORPO:")
    for s in secoes(a.prova, so_materias=not a.todas):
        print(f"    {s.nome:<38} ({len(s.bloco)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
