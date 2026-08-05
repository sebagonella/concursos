#!/usr/bin/env python3
"""validar_afericao.py — recusa aferição incompleta ou incoerente.

Cinco checagens, cada uma nascida de um defeito real:

1. **Veredicto em branco.** O arcabouço sai com `···` onde o agente precisa julgar.
   Publicar com o marcador seria nota fantasma.
2. **A nota sai das contagens.** Recalcula RESPONDE/PARCIAL/NÃO RESPONDE pelo critério
   declarado da própria skill e compara com a nota escrita, por nível; e confere que as
   contagens somam as `questoes_aferidas` do frontmatter. `SEM MATERIAL` fica fora do
   denominador, como manda o critério.
3. **Formatação única da nota.** O mesmo cálculo saiu **39,4** numa tabela e **39,45**
   noutra do mesmo documento — um é o arredondamento do outro.
4. **N declarado.** Com 1 prova a conclusão desta sessão foi "empate técnico"; com 3,
   inverteu. Afirmação sem amostra declarada é afirmação sem lastro.
5. **Superlativo sem amostra.** "prova que", "comprova", "confirma" exigem N ≥ 2 provas.

Varrer e não achar nada **falha alto** — sair com sucesso sobre zero arquivos é o
defeito que fez o `fix_notebooklm_packs` achar 0 dos 158 pacotes e sair feliz.
"""
from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

VAZIO = "···"
SUPERLATIVOS = re.compile(
    r"\b(comprova|prova que|confirma que|demonstra que|conclusiv[ao])\b", re.I)


def frontmatter(txt: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", txt, re.S)
    if not m:
        return {}
    out = {}
    for linha in m.group(1).split("\n"):
        if ":" in linha:
            k, v = linha.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def numeros_pt(s: str) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"\b\d+,\d+\b", s)]


# Peso de cada veredicto, na ordem em que a tabela de Resultado os lista. É o
# critério declarado no próprio documento: RESPONDE 1,0 · PARCIAL 0,5 · NÃO
# RESPONDE 0,2 (esperança do chute em 5 alternativas).
PESOS = {"resp": Decimal("1.0"), "parc": Decimal("0.5"), "nao": Decimal("0.2")}

_LINHAS = (
    ("resp", re.compile(r"quest[õo]es?\s+plenamente\s+respondidas")),
    ("parc", re.compile(r"respondidas?\s+em\s+parte")),
    ("nao", re.compile(r"^n[ãa]o\s+respondidas")),
    ("sem", re.compile(r"^sem\s+material")),
    ("nota", re.compile(r"^nota$")),
)


def _celulas(linha: str) -> list[str]:
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def _limpo(txt: str) -> str:
    """Rótulo sem markdown, sem parênteses explicativos e em minúsculas."""
    txt = re.sub(r"\*+|`", "", txt)
    txt = re.sub(r"\(.*?\)", "", txt)
    return " ".join(txt.split()).strip().lower()


def _primeiro_numero(cel: str, decimal: bool) -> Decimal | None:
    """O primeiro número da célula. `**35** / 45` é 35; `**8,76** / 10` é 8,76."""
    padrao = r"\d+,\d+" if decimal else r"\d+"
    m = re.search(padrao, re.sub(r"\*+", "", cel))
    return Decimal(m.group(0).replace(",", ".")) if m else None


def conferir_aritmetica(txt: str, questoes: int | None) -> list[str]:
    """A nota declarada tem de sair das contagens declaradas.

    Não basta o agente somar certo uma vez: o documento é reescrito à mão, e a
    tabela de Resultado é o único lugar onde nota e contagens convivem. Aqui a
    nota é RECALCULADA pelo critério da skill e comparada com a escrita.

    Onde não há contagem não há aritmética a conferir, e o check se cala — o
    documento incompleto já é pego pelo marcador `···` do check 1. Isso mantém o
    validador utilizável em variações de formato, que existem: a tabela de Vendas
    e Negociação tem uma coluna de nível e uma linha `Sem material`; a de Língua
    Portuguesa tem duas colunas e nenhuma.
    """
    achado: dict[str, list[str]] = {}
    for linha in txt.split("\n"):
        if not linha.lstrip().startswith("|"):
            continue
        cels = _celulas(linha)
        if len(cels) < 2:
            continue
        rot = _limpo(cels[0])
        for chave, padrao in _LINHAS:
            if padrao.search(rot) and chave not in achado:
                achado[chave] = cels[1:]
                break

    if not all(k in achado for k in ("resp", "parc", "nao", "nota")):
        return []

    erros: list[str] = []
    n_niveis = len(achado["nota"])
    rotulos = [f"nível {i + 1}" for i in range(n_niveis)]
    # nomeia a coluna quando o cabeçalho da tabela traz os níveis em crase
    cab = re.search(r"^\|[^\n]*`([^`]+)`[^\n]*\|$", txt, re.M)
    if cab:
        nomes = re.findall(r"`([^`]+)`", cab.group(0))
        if len(nomes) == n_niveis:
            rotulos = nomes

    for i in range(n_niveis):
        def val(chave: str, dec: bool = False) -> Decimal | None:
            col = achado.get(chave, [])
            return _primeiro_numero(col[i], dec) if i < len(col) else None

        resp, parc, nao = val("resp"), val("parc"), val("nao")
        nota = val("nota", dec=True)
        if None in (resp, parc, nao) or nota is None:
            continue
        sem = val("sem") or Decimal(0)

        denom = resp + parc + nao
        if denom == 0:
            continue
        pontos = resp * PESOS["resp"] + parc * PESOS["parc"] + nao * PESOS["nao"]
        esperada = (pontos / denom * 10).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if abs(esperada - nota) > Decimal("0.01"):
            erros.append(
                f"nota de `{rotulos[i]}` não confere com as contagens: "
                f"{resp}·1,0 + {parc}·0,5 + {nao}·0,2 = {pontos} sobre {denom} "
                f"dá {esperada}, mas o documento diz {nota}".replace(".", ","))

        if questoes is not None and denom + sem != questoes:
            erros.append(
                f"contagens de `{rotulos[i]}` não somam a amostra declarada: "
                f"{resp} + {parc} + {nao} + {sem} (sem material) = {denom + sem}, "
                f"mas o frontmatter diz questoes_aferidas: {questoes}")
    return erros


def conferir(md: Path) -> list[str]:
    txt = md.read_text(encoding="utf-8")
    fm = frontmatter(txt)
    erros: list[str] = []

    n_vazio = txt.count(VAZIO)
    if n_vazio:
        erros.append(f"{n_vazio} campo(s) por preencher ({VAZIO}) — o agente não julgou")

    n_provas = fm.get("provas_aferidas_n")
    if not n_provas:
        erros.append("frontmatter sem `provas_aferidas_n` — amostra não declarada")
    if not fm.get("questoes_aferidas"):
        erros.append("frontmatter sem `questoes_aferidas`")

    # 2: a nota sai das contagens, e as contagens fecham com a amostra
    try:
        questoes = int(fm["questoes_aferidas"]) if fm.get("questoes_aferidas") else None
    except ValueError:
        questoes = None
    erros += conferir_aritmetica(txt, questoes)

    # 3: mesma grandeza formatada de dois jeitos.
    #
    # O critério é a RELAÇÃO DE ARREDONDAMENTO, não a proximidade absoluta. Proximidade
    # confunde duas coisas diferentes: "o mesmo número escrito de dois jeitos" (o
    # defeito) e "dois números legitimamente vizinhos" (o normal). Numa matéria estável
    # as notas por prova caem naturalmente a menos de 0,05 umas das outras — o `<= 0,05`
    # recusava a aferição de Vendas e Negociação por ter 8,76 (consolidado) e 8,80
    # (provas B e C), que são valores distintos e ambos corretos.
    #
    # Só há defeito quando as PRECISÕES diferem e o menos preciso é um arredondamento
    # válido do mais preciso. A comparação é por desigualdade, não por `round()`, porque
    # 39,45 arredonda para 39,4 (HALF_EVEN) ou 39,5 (HALF_UP) e os DOIS são o defeito:
    # fixar um modo deixaria o outro passar.
    #
    # Em Decimal, não em float: 39,45 − 39,4 dá 0.050000000000004 em float e escaparia
    # do limiar por epsilon — o par que se quer pegar passaria batido.
    #
    # Fica de fora, por construção: dois valores de MESMA precisão, por mais próximos
    # que estejam (39,4 × 39,5). Não há como pegá-los sem recusar 13,0 × 13,2, que é
    # legítimo — e o incidente que originou esta regra era 39,4 × 39,45.
    def casas(s: str) -> int:
        return len(s.split(",")[1])

    brutos = sorted(set(re.findall(r"\b\d+,\d+\b", txt)))
    for i, a in enumerate(brutos):
        for b in brutos[i + 1:]:
            if casas(a) == casas(b):
                continue
            grosso, fino = (a, b) if casas(a) < casas(b) else (b, a)
            limiar = Decimal(5) * Decimal(10) ** (-casas(grosso) - 1)
            if abs(Decimal(fino.replace(",", ".")) -
                   Decimal(grosso.replace(",", "."))) <= limiar:
                erros.append(f"mesmo valor com formatações diferentes: "
                             f"{grosso} parece o arredondamento de {fino}")

    # 5: superlativo exige amostra
    try:
        n = int(n_provas) if n_provas else 0
    except ValueError:
        n = 0
    if n < 2:
        for m in SUPERLATIVOS.finditer(txt):
            ctx = " ".join(txt[max(0, m.start() - 45):m.start() + 45].split())
            erros.append(f"afirmação forte com {n} prova(s): …{ctx}…")
            break
    return erros


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--concurso-dir", type=Path)
    ap.add_argument("--arquivo", type=Path, action="append")
    a = ap.parse_args()

    alvos: list[Path] = list(a.arquivo or [])
    if a.concurso_dir:
        alvos += sorted(a.concurso_dir.rglob("00-AFERICAO-*.md"))
    if not alvos:
        sys.stderr.write("ERRO: nenhuma aferição encontrada — varrer e não achar nada "
                         "é falha, não sucesso.\n")
        return 1

    total = 0
    for md in alvos:
        erros = conferir(md)
        if erros:
            total += 1
            print(f"✗ {md.name}")
            for e in erros:
                print(f"    {e}")
        else:
            print(f"✓ {md.name}")
    print(f"\n{len(alvos)} aferição(ões) conferida(s) — {total} com problema.")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
