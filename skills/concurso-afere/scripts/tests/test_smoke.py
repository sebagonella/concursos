#!/usr/bin/env python3
"""Suíte da concurso-afere. Roda standalone: `python3 scripts/tests/test_smoke.py`.

Cada teste nasceu de um defeito REAL, observado ao aferir as três versões da prova do
BB 2022/001 à mão. Os que reproduzem bug foram conferidos contra o código ingênuo —
se não falham lá, são decoração.

Os PDFs não entram na suíte: `texto()` é substituído por fixtures de string. Isso testa
a lógica que erra (recorte, casamento, contagem) sem depender de poppler nem de arquivo
binário no repo.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

import casar_materias          # noqa: E402
import extrair_questoes        # noqa: E402
import gabarito as gabmod      # noqa: E402
import prova_id                # noqa: E402
import quadrix                 # noqa: E402
import validar_afericao        # noqa: E402

FALHAS: list[str] = []


def checar(cond, nome, detalhe=""):
    if cond:
        print(f"  PASS  {nome}")
    else:
        FALHAS.append(nome)
        print(f"  FAIL  {nome}" + (f": {detalhe}" if detalhe else ""))


# --------------------------------------------------------------------------- #
# fixtures — espelham a saída real do pdftotext nas provas da CESGRANRIO
# --------------------------------------------------------------------------- #
CAPA = """
                                       CONHECIMENTOS BÁSICOS
     Língua Portuguesa            Língua Inglesa            Atualidades do Mercado Financeiro
   Questões       Pontuação     Questões    Pontuação        Questões        Pontuação
    1 a 10      1,5 ponto cada   11 a 15   1,0 ponto cada     21 a 25      1,0 ponto cada
"""

# o texto de apoio numera os parágrafos 1..5 ANTES das questões — foi o que fez o
# primeiro recorte devolver o parágrafo 3 no lugar da questão 3
CORPO = """
LÍNGUA PORTUGUESA
A história do método braile
1

2

3

texto do primeiro parágrafo

1

Diferentemente do método de Barbier, o método de Haüy
(A) era conhecido como grafia sonora.
(B) impossibilitava soletrar palavras.
(C) possibilitava a escrita.
(D) usava letras em relevo.
(E) apresentava pontos e traços.

2

A partir da leitura do texto, constata-se que Braille
(A) comecou a dar aulas quando atingiu a maioridade.
(B) foi adotado por Valentin Haüy depois da tragédia.
(C) queria seguir o ofício do pai.
(D) estudou com bolsa de estudos.
(E) trabalhava em selarias quando criança.

LÍNGUA INGLESA

10

O pronome oblíquo átono está colocado de acordo com a
(A) Braille recebia os alunos.
(B) Quantos impressionaram-nos?
(C) Me surpreende a história.
(D) Seu método não trouxe-lhe reconhecimento.
(E) O menino tornar-se-ia um herói nacional.
"""

# cabeçalho de seção partido em duas linhas, com linha em branco entre elas
CORPO_QUEBRADO = """
ATUALIDADES

DO MERCADO FINANCEIRO

21

Enunciado qualquer
(A) a (B) b (C) c (D) d (E) e
"""

GABARITO_PDF = """
   BANCO DO BRASIL - Prova A - Escriturário – Agente Comercial
                            GABARITO 1
                        LÍNGUA PORTUGUESA
      1- B      2- B      3- E      4- C      5- A
      6- D      7- B      8- E      9- D     10 - C
                          LÍNGUA INGLESA
     11 - B    12 - C    13 - E    14 - E    15 - B
   BANCO DO BRASIL - Prova A - Escriturário – Agente Comercial
                            GABARITO 4
                        LÍNGUA PORTUGUESA
      1- D      2- D      3- A      4- C      5- E
      6- B      7- A      8- D      9- B     10 - E
                          LÍNGUA INGLESA
     11 - A    12 - D    13 - B    14 - C    15 - E
"""

CADERNO_A = "BANCO DO BRASIL - PROVA A\nGABARITO 4\nESCRITURÁRIO - AGENTE COMERCIAL\n"
CADERNO_TEC = "BANCO DO BRASIL - Prova Agente de Tecnologia\nGABARITO 4\n"
GAB_TEC = ("BANCO DO BRASIL - Agente de Tecnologia\nGABARITO 4\n"
           "LÍNGUA PORTUGUESA\n 1- A  2- B  3- D  4- C  5- A\n"
           " 6- B  7- E  8- B  9- C  10 - E\nLÍNGUA INGLESA\n11 - A\n")


def com_texto(mapa: dict[str, str]):
    """Substitui `texto()` nos módulos por um despachante de fixture."""
    def falso(pdf, layout=True, ini=None, fim=None):
        return mapa[Path(pdf).name]
    prova_id.texto = falso
    extrair_questoes.texto = falso
    gabmod.texto = falso
    quadrix.texto = falso


# --------------------------------------------------------------------------- #
def test_faixas_vem_da_capa():
    com_texto({"p.pdf": CAPA})
    fx = extrair_questoes.distribuicao(Path("p.pdf"))
    nomes = {f.nome: (f.primeira, f.ultima) for f in fx}
    checar(nomes.get("Língua Portuguesa") == (1, 10), "faixa de Português vem da capa", nomes)
    checar(nomes.get("Atualidades do Mercado Financeiro") == (21, 25),
           "nome longo da capa é lido inteiro", nomes)


def test_agrupador_nao_vira_materia():
    """CONHECIMENTOS BÁSICOS agrupa blocos; não é matéria."""
    com_texto({"p.pdf": CAPA + CORPO})
    nomes = [s.nome for s in extrair_questoes.secoes(Path("p.pdf"))]
    checar("CONHECIMENTOS BÁSICOS" not in nomes, "agrupador não vira seção de matéria", nomes)


def test_cabecalho_quebrado_em_duas_linhas():
    """'ATUALIDADES' + 'DO MERCADO FINANCEIRO' com linha vazia entre eles."""
    com_texto({"p.pdf": CORPO_QUEBRADO})
    nomes = [s.nome for s in extrair_questoes.secoes(Path("p.pdf"))]
    checar("ATUALIDADES DO MERCADO FINANCEIRO" in nomes,
           "cabeçalho partido em duas linhas é reunido", nomes)


def test_bloco_da_materia_alcanca_a_ultima_questao():
    """A questão 10 aparece DEPOIS do cabeçalho 'LÍNGUA INGLESA' por diagramação.
    Cortar no cabeçalho seguinte perderia uma questão em dez."""
    com_texto({"p.pdf": CAPA + CORPO})
    f = extrair_questoes.Faixa("Língua Portuguesa", 1, 10)
    bloco, avisos = extrair_questoes.bloco_da_materia(Path("p.pdf"), f)
    checar("pronome oblíquo átono" in bloco, "bloco alcança a questão 10", avisos)


def test_gabarito_do_caderno_certo():
    """Usar a tabela do caderno 1 no lugar do 4 troca 9 das 10 respostas."""
    com_texto({"g.pdf": GABARITO_PDF})
    r4 = gabmod.respostas(Path("g.pdf"), "4", "LÍNGUA PORTUGUESA", range(1, 11))
    r1 = gabmod.respostas(Path("g.pdf"), "1", "LÍNGUA PORTUGUESA", range(1, 11))
    checar(r4 == {1: "D", 2: "D", 3: "A", 4: "C", 5: "E",
                  6: "B", 7: "A", 8: "D", 9: "B", 10: "E"},
           "gabarito lê a tabela do caderno pedido", r4)
    checar(sum(1 for q in r4 if r4[q] != r1[q]) == 9,
           "cadernos 1 e 4 divergem em 9 de 10 — por isso a versão importa")


def test_gabarito_recorta_a_secao_da_materia():
    com_texto({"g.pdf": GABARITO_PDF})
    r = gabmod.respostas(Path("g.pdf"), "4", "LÍNGUA PORTUGUESA", range(1, 11))
    checar(11 not in r, "recorte de seção não vaza para Língua Inglesa", r)


def test_caderno_inexistente_falha_alto():
    com_texto({"g.pdf": GABARITO_PDF})
    try:
        gabmod.respostas(Path("g.pdf"), "3", "LÍNGUA PORTUGUESA", range(1, 11))
        checar(False, "caderno inexistente falha alto")
    except gabmod.GabaritoErro as e:
        checar("1" in str(e) and "4" in str(e),
               "erro de caderno nomeia os disponíveis", str(e))


def test_par_com_cargo_trocado_e_recusado():
    """O erro mais caro: prova de um cargo com gabarito de outro. Os dois têm
    'GABARITO 4' e o de Tecnologia nem declara A/B/C — passa despercebido."""
    com_texto({"a.pdf": CADERNO_A, "gtec.pdf": GAB_TEC})
    p = prova_id.identificar(Path("a.pdf"))
    g = prova_id.identificar(Path("gtec.pdf"))
    problemas = prova_id.conferir_par(p, g)
    checar(any("cargo" in x for x in problemas),
           "par com cargo trocado é recusado", problemas)


def test_gabarito_passado_como_caderno_e_recusado():
    """Chegou um arquivo chamado 'PROVA B - ESCRITURÁRIO' que era o gabarito."""
    com_texto({"g.pdf": GABARITO_PDF, "g2.pdf": GABARITO_PDF})
    p = prova_id.identificar(Path("g.pdf"))
    problemas = prova_id.conferir_par(p, prova_id.identificar(Path("g2.pdf")))
    checar(any("GABARITO" in x for x in problemas),
           "gabarito no lugar do caderno é recusado", problemas)


def test_gabarito_expoe_todos_os_cadernos():
    com_texto({"g.pdf": GABARITO_PDF})
    g = prova_id.identificar(Path("g.pdf"))
    checar(g.cadernos == ["1", "4"] and g.caderno is None,
           "gabarito lista seus cadernos e não finge ser de um só", g.cadernos)


# --------------------------------------------------------------------------- #
def _vault(base: Path, materias: dict[str, dict]) -> Path:
    """Fixture do vault espelhando a saída REAL da concurso-aprofunda."""
    conc = base / "BB_2027_PREVISTO"
    (conc / ".meta.json").parent.mkdir(parents=True, exist_ok=True)
    (conc / ".meta.json").write_text(json.dumps({"modo": "previsto", "banca": "X"}),
                                     encoding="utf-8")
    for chave, cfg in materias.items():
        escopo, mid = chave.split("/")
        for i in range(cfg["assuntos"]):
            for nivel in cfg["niveis"]:
                d = conc / escopo / "03-APROFUNDAMENTO" / mid / "assuntos" / f"a{i}" / f"{nivel}--f"
                d.mkdir(parents=True, exist_ok=True)
                (d / f"a{i}--{nivel}--f--BB.md").write_text(
                    "---\ntitle: x\n---\n\n## 🧩 Subtópicos que este assunto engloba\n"
                    "- conceito alfa\n- conceito beta\n\n## 🔗 Conexões\n", encoding="utf-8")
                # ruído que já enganou uma varredura ad-hoc
                (d / "_fonte-notebooklm.md").write_text("pacote", encoding="utf-8")
                (d / f"flashcards-a{i}--{nivel}--f--BB.md").write_text("cards", encoding="utf-8")
    return conc


def test_descobre_materias_e_niveis_do_filesystem():
    """O .meta.json do BB não tem `materias_por_cargo`; depender dele quebraria."""
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/lingua-portuguesa": {"assuntos": 2, "niveis": ["padrao", "detalhado"]},
                                "AGENTE-COMERCIAL/vendas": {"assuntos": 1, "niveis": ["padrao"]}})
        ms = {m.materia_id: m for m in casar_materias.materias_do_vault(conc)}
        checar(sorted(ms) == ["lingua-portuguesa", "vendas"], "descobre matérias", sorted(ms))
        checar(ms["lingua-portuguesa"].niveis == ["detalhado", "padrao"],
               "detecta os dois níveis", ms["lingua-portuguesa"].niveis)
        checar(ms["vendas"].niveis == ["padrao"], "matéria de um nível só")


def test_cargo_enxerga_comum_mais_o_proprio():
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/lingua-portuguesa": {"assuntos": 1, "niveis": ["padrao"]},
                                "AGENTE-COMERCIAL/vendas": {"assuntos": 1, "niveis": ["padrao"]},
                                "AGENTE-DE-TECNOLOGIA/ti": {"assuntos": 1, "niveis": ["padrao"]}})
        esc = casar_materias.escopos_do_cargo(conc, "AGENTE-COMERCIAL")
        checar(esc == ["_COMUM", "AGENTE-COMERCIAL"], "cargo vê o comum e o próprio", esc)
        ms = [m.materia_id for m in casar_materias.materias_do_vault(conc, esc)]
        checar("ti" not in ms, "não traz matéria de outro cargo", ms)


def test_arquivo_principal_ignora_pacote_e_flashcards():
    """`_` ordena antes das letras: `glob('*.md')[0]` pega o pacote NotebookLM.
    Esse erro reportou 17 artigos ausentes onde havia 8."""
    import divergencia_niveis
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/m": {"assuntos": 1, "niveis": ["padrao"]}})
        pasta = conc / "_COMUM/03-APROFUNDAMENTO/m/assuntos/a0/padrao--f"
        escolhido = divergencia_niveis.arquivo_principal(pasta)
        checar(escolhido and escolhido.name.startswith("a0--"),
               "escolhe o .md do assunto, não o _fonte-notebooklm",
               escolhido.name if escolhido else None)


def test_divergencia_exige_os_dois_niveis():
    import divergencia_niveis
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/m": {"assuntos": 2, "niveis": ["padrao"]}})
        r = divergencia_niveis.medir(conc / "_COMUM/03-APROFUNDAMENTO/m")
        checar(r["assuntos_comparados"] == 0,
               "matéria de um nível só não tenta comparar", r["assuntos_comparados"])


# --------------------------------------------------------------------------- #
def _af(txt: str, base: Path) -> Path:
    p = base / "00-AFERICAO-X.md"
    p.write_text(txt, encoding="utf-8")
    return p


CAB = ("---\nprovas_aferidas_n: 3\nquestoes_aferidas: 30\n---\n\n")


def test_validador_recusa_veredicto_em_branco():
    with tempfile.TemporaryDirectory() as d:
        p = _af(CAB + "| Q | ··· |\n", Path(d))
        erros = validar_afericao.conferir(p)
        checar(any("por preencher" in e for e in erros),
               "recusa arcabouço não julgado", erros)


def test_validador_pega_formatacao_dupla():
    """39,4 e 39,45 para o mesmo cálculo apareceram no mesmo documento."""
    with tempfile.TemporaryDirectory() as d:
        p = _af(CAB + "nota 39,4 na tabela e 39,45 no texto\n", Path(d))
        erros = validar_afericao.conferir(p)
        checar(any("formatações diferentes" in e for e in erros),
               "pega o mesmo número escrito de dois jeitos", erros)


def test_validador_pega_arredondamento_para_cima():
    """39,45 arredonda para 39,4 (HALF_EVEN) ou 39,5 (HALF_UP) — os DOIS são o defeito.

    Invariante de desenho, não regressão: este par dista 0,05 e o critério antigo de
    proximidade também o pegava. Existe para travar a escolha de comparar por
    desigualdade em vez de `round()`, que fixaria um modo e deixaria o outro passar.
    """
    with tempfile.TemporaryDirectory() as d:
        p = _af(CAB + "nota 39,45 no texto e 39,5 na tabela\n", Path(d))
        erros = validar_afericao.conferir(p)
        checar(any("formatações diferentes" in e for e in erros),
               "pega o arredondamento para cima também", erros)


def test_validador_aceita_notas_proximas_de_mesma_precisao():
    """8,76 (consolidado) e 8,80 (provas B e C) distam 0,04 e são números DIFERENTES.

    O critério antigo era proximidade absoluta (<= 0,05) e recusava a aferição de
    Vendas e Negociação inteira. Duas notas de mesma precisão a 0,04 uma da outra são
    o resultado normal de uma matéria estável — o defeito que se quer pegar é o mesmo
    número escrito com precisões diferentes, não dois números vizinhos.
    """
    with tempfile.TemporaryDirectory() as d:
        p = _af(CAB + "| consolidado | 8,76 |\n| prova B | 8,80 |\n"
                      "| prova A | 8,67 |\n| pontos | 13,0 e 13,2 |\n", Path(d))
        checar(validar_afericao.conferir(p) == [],
               "aceita notas vizinhas de mesma precisão", validar_afericao.conferir(p))


TAB = ("| | `padrao` |\n|---|---:|\n"
       "| Questões plenamente respondidas | **{r}** / {t} |\n"
       "| Respondidas em parte | {p} |\n"
       "| **Não** respondidas | {n} |\n"
       "| **Sem material** (fora do denominador) | {s} |\n"
       "| **Nota** | **{nota}** / 10 |\n")


def test_validador_recalcula_a_nota_das_contagens():
    """A nota declarada tem de sair das contagens declaradas.

    O docstring anunciava um check 2 ("notas por prova somam ao consolidado") que
    NUNCA existiu no código — em Vendas e Negociação a aritmética (13,0+13,2+13,2
    = 39,4 e 39,4/45 = 8,76) foi conferida à mão. Aqui ele existe, e mais forte:
    recalcula a nota a partir de RESPONDE/PARCIAL/NÃO RESPONDE pelo critério
    declarado da própria skill, em vez de comparar somas parciais.
    """
    cab45 = CAB.replace("questoes_aferidas: 30", "questoes_aferidas: 45")
    with tempfile.TemporaryDirectory() as d:
        # 35*1,0 + 8*0,5 + 2*0,2 = 39,4 sobre 45 => 8,76 (o caso real de Vendas)
        p = _af(cab45 + TAB.format(r=35, p=8, n=2, s=0, t=45, nota="8,76"), Path(d))
        checar(validar_afericao.conferir(p) == [],
               "aceita nota coerente com as contagens", validar_afericao.conferir(p))

        p = _af(cab45 + TAB.format(r=35, p=8, n=2, s=0, t=45, nota="9,10"), Path(d))
        erros = validar_afericao.conferir(p)
        checar(any("não confere com as contagens" in e for e in erros),
               "pega nota que não sai das contagens", erros)


def test_validador_pega_contagem_que_nao_fecha_com_a_amostra():
    """35 + 8 + 2 + 0 tem de dar as 45 questões declaradas no frontmatter."""
    with tempfile.TemporaryDirectory() as d:
        p = _af(CAB.replace("questoes_aferidas: 30", "questoes_aferidas: 45")
                + TAB.format(r=35, p=8, n=1, s=0, t=45, nota="8,73"), Path(d))
        erros = validar_afericao.conferir(p)
        checar(any("não somam" in e for e in erros),
               "pega contagem que não fecha com questoes_aferidas", erros)


def test_validador_ignora_sem_material_no_denominador():
    """SEM MATERIAL sai do denominador — é falha de cobertura, não de profundidade.

    Com 10 respondidas, 0 parciais, 0 não respondidas e 5 sem material, a nota é
    10,0 (10/10), não 6,7 (10/15). Se o denominador incluísse o sem-material, a
    skill puniria o texto por uma lacuna de planejamento — que é exatamente o que
    o critério declarado recusa fazer.
    """
    with tempfile.TemporaryDirectory() as d:
        p = _af(CAB.replace("questoes_aferidas: 30", "questoes_aferidas: 15")
                + TAB.format(r=10, p=0, n=0, s=5, t=15, nota="10,00"), Path(d))
        checar(validar_afericao.conferir(p) == [],
               "sem material fora do denominador", validar_afericao.conferir(p))


def test_validador_confere_cada_nivel_da_tabela():
    """Com dois níveis, cada coluna é uma nota — e cada uma tem de fechar sozinha.

    Reproduz a tabela real de Língua Portuguesa: `padrao` 28/2/0 => 9,67 e
    `detalhado` 25/1/4 => 8,77. Estragar SÓ a segunda coluna tem de ser pego.
    """
    with tempfile.TemporaryDirectory() as d:
        base = ("| | `padrao` | `detalhado` |\n|---|---:|---:|\n"
                "| Questões plenamente respondidas | **28** / 30 | 25 / 30 |\n"
                "| Respondidas em parte | 2 | 1 |\n"
                "| **Não** respondidas | **0** | **4** |\n"
                "| **Nota** | **9,67** / 10 | **{}** / 10 |\n")
        p = _af(CAB + base.format("8,77"), Path(d))
        checar(validar_afericao.conferir(p) == [],
               "aceita as duas colunas corretas", validar_afericao.conferir(p))

        p = _af(CAB + base.format("9,77"), Path(d))
        erros = validar_afericao.conferir(p)
        checar(any("detalhado" in e and "não confere" in e for e in erros),
               "pega o nível errado, nomeando a coluna", erros)


def test_validador_exige_amostra_declarada():
    with tempfile.TemporaryDirectory() as d:
        p = _af("---\nquestoes_aferidas: 10\n---\n\ntexto\n", Path(d))
        erros = validar_afericao.conferir(p)
        checar(any("provas_aferidas_n" in e for e in erros),
               "exige a amostra no frontmatter", erros)


def test_validador_barra_superlativo_com_uma_prova():
    """Com 1 prova a conclusão foi 'empate'; com 3, inverteu."""
    with tempfile.TemporaryDirectory() as d:
        p = _af("---\nprovas_aferidas_n: 1\nquestoes_aferidas: 10\n---\n\n"
                "O resultado comprova que o detalhado é superior.\n", Path(d))
        erros = validar_afericao.conferir(p)
        checar(any("afirmação forte" in e for e in erros),
               "barra superlativo com amostra de 1 prova", erros)


def test_validador_aceita_documento_completo():
    with tempfile.TemporaryDirectory() as d:
        p = _af(CAB + "| nota | 9,67 | 8,77 |\n\nTexto sóbrio, sem exagero.\n", Path(d))
        checar(validar_afericao.conferir(p) == [], "aceita aferição bem formada")


def test_validador_falha_alto_sem_alvo():
    """Varrer e não achar nada é falha, não sucesso — o defeito do fix_notebooklm_packs."""
    with tempfile.TemporaryDirectory() as d:
        sys.argv = ["v", "--concurso-dir", d]
        checar(validar_afericao.main() == 1, "sair sobre zero arquivos é erro")


# --------------------------------------------------------------------------- #
# build_afericao — o único script da skill que ESCREVE no vault, e o que não
# tinha teste nenhum.
# --------------------------------------------------------------------------- #
def _rodar_build(conc: Path, extra: list[str] | None = None) -> dict:
    """Roda o build_afericao sobre a fixture, com `texto()` já substituído."""
    import build_afericao
    sys.argv = ["b", "--concurso-dir", str(conc), "--prova", "p.pdf",
                "--gabarito", "g.pdf", "--materia", "Língua Portuguesa"] + (extra or [])
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        build_afericao.main()
    return json.loads(buf.getvalue())


# gabarito SEM cabeçalho de seção: o fallback é legítimo, mas tem de avisar
GAB_SEM_SECAO = """
   BANCO DO BRASIL - Prova A - Escriturário – Agente Comercial
                            GABARITO 4
      1- D      2- D      3- A      4- C      5- E
      6- B      7- A      8- D      9- B     10 - E
     11 - A    12 - D    13 - B    14 - C    15 - E
"""


def test_empate_entre_materias_homonimas_nao_e_desempatado_no_palpite():
    """Regressão: `if s > melhor_score` ficava com o primeiro da iteração.

    O caso é real e está nomeado no CLAUDE.md: matéria homônima no `_COMUM` e no
    cargo — no SEDES, `servico-social` existe nos dois — dá score IDÊNTICO, e uma
    das duas era medida sem que nada dissesse qual. O SKILL.md promete "sem
    casamento confiável, PERGUNTA"; medir o material errado e reportar como se
    fosse o outro é o desfecho caro desta skill.
    """
    com_texto({"p.pdf": CADERNO_A + CAPA + CORPO, "g.pdf": GABARITO_PDF})
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {
            "_COMUM/lingua-portuguesa": {"assuntos": 1, "niveis": ["padrao"]},
            "AGENTE-COMERCIAL/lingua-portuguesa": {"assuntos": 1, "niveis": ["padrao"]}})
        cs = {c.faixa.nome: c for c in casar_materias.casar(conc and Path("p.pdf"), conc)}
        c = cs["Língua Portuguesa"]
        checar(len(c.empatados) == 2, "o empate é registrado, não resolvido",
               [m.escopo for m in c.empatados])
        checar({m.escopo for m in c.empatados} == {"_COMUM", "AGENTE-COMERCIAL"},
               "os dois escopos aparecem", [m.escopo for m in c.empatados])

        import build_afericao
        try:
            build_afericao.coletar(Path("p.pdf"), Path("g.pdf"), conc,
                                   "Língua Portuguesa", None)
            checar(False, "empate faz o build recusar")
        except SystemExit as e:
            checar("não dá para escolher sem palpite" in str(e),
                   "a recusa explica o motivo", str(e))
            checar("--escopo" in str(e), "a recusa oferece a saída", str(e))


def test_escopo_desfaz_o_empate():
    """A recusa só é útil se houver saída: `--escopo` restringe e o build volta."""
    com_texto({"p.pdf": CADERNO_A + CAPA + CORPO, "g.pdf": GABARITO_PDF})
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {
            "_COMUM/lingua-portuguesa": {"assuntos": 1, "niveis": ["padrao"]},
            "AGENTE-COMERCIAL/lingua-portuguesa": {"assuntos": 1, "niveis": ["padrao"]}})
        import build_afericao
        dados = build_afericao.coletar(Path("p.pdf"), Path("g.pdf"), conc,
                                       "Língua Portuguesa", ["AGENTE-COMERCIAL"])
        checar(dados["materia"].escopo == "AGENTE-COMERCIAL",
               "mede o escopo pedido", dados["materia"].escopo)


def test_sem_empate_o_casamento_segue_direto():
    """Um candidato só continua sendo escolha legítima — a recusa é do EMPATE."""
    com_texto({"p.pdf": CADERNO_A + CAPA + CORPO})
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/lingua-portuguesa":
                                {"assuntos": 1, "niveis": ["padrao"]}})
        c = next(c for c in casar_materias.casar(Path("p.pdf"), conc)
                 if c.faixa.nome == "Língua Portuguesa")
        checar(c.empatados == [], "sem empate, lista vazia", c.empatados)
        checar(c.materia is not None, "e a matéria é casada")


def test_fallback_do_gabarito_avisa_em_vez_de_engolir():
    """Regressão: `except GabaritoErro: respostas(gab, caderno, None, faixa)`.

    O fallback é legítimo — há gabarito sem cabeçalho de seção —, mas o `except`
    mudo descartava justamente a mensagem que existe para ser lida ("recorte de
    seção errado ou tabela em formato novo"). E o que se perde não é cosmético: sem
    o recorte por seção a leitura varre a tabela INTEIRA, e a faixa numérica passa a
    ser a única defesa contra pegar a resposta de outra matéria.
    """
    com_texto({"p.pdf": CADERNO_A + CAPA + CORPO, "g.pdf": GAB_SEM_SECAO})
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/lingua-portuguesa":
                                {"assuntos": 2, "niveis": ["padrao"]}})
        import build_afericao
        dados = build_afericao.coletar(Path("p.pdf"), Path("g.pdf"), conc,
                                       "Língua Portuguesa", None)
        # o fallback funcionou: as respostas vieram
        checar(dados["gabarito"].get(1) == "D", "o fallback ainda lê o gabarito",
               dados["gabarito"])
        av = " ".join(dados["avisos"])
        checar("SEM recorte de seção" in av, "o fallback avisa que perdeu o recorte", av)
        checar("1–10" in av, "o aviso diz qual faixa filtrou", av)


def test_gabarito_com_secao_nao_gera_aviso():
    """Ausente e vazio são coisas diferentes: leitura limpa não inventa alarme."""
    com_texto({"p.pdf": CADERNO_A + CAPA + CORPO, "g.pdf": GABARITO_PDF})
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/lingua-portuguesa":
                                {"assuntos": 2, "niveis": ["padrao"]}})
        import build_afericao
        dados = build_afericao.coletar(Path("p.pdf"), Path("g.pdf"), conc,
                                       "Língua Portuguesa", None)
        av = " ".join(dados["avisos"])
        checar("SEM recorte" not in av, "sem defeito, sem aviso de recorte", av)


def test_build_afericao_nao_sobrescreve_julgamento():
    """Regressão: `destino.write_text(doc)` era incondicional.

    O `00-AFERICAO-*.md` guarda o JULGAMENTO do agente — veredicto por questão,
    conceito decisivo, ações — e o script só sabe montar o arcabouço com `···`.
    Regravar por cima destrói exatamente o trabalho que a skill declara não saber
    fazer sozinha. É a mesma proteção que o build_subject_md.py dá ao resumo.
    """
    com_texto({"p.pdf": CADERNO_A + CAPA + CORPO, "g.pdf": GABARITO_PDF})
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/lingua-portuguesa":
                                {"assuntos": 2, "niveis": ["padrao"]}})
        r1 = _rodar_build(conc)
        destino = Path(r1["aferições"][0]["destino"])
        checar(destino.exists(), "primeira execução grava a aferição")

        julgado = destino.read_text(encoding="utf-8").replace(
            "···", "NOTA 9,67 — julgamento escrito à mão")
        destino.write_text(julgado, encoding="utf-8")

        r2 = _rodar_build(conc)
        checar("julgamento escrito à mão" in destino.read_text(encoding="utf-8"),
               "segunda execução NÃO apaga o julgamento")
        checar(r2["aferições"][0]["pulado"] is True,
               "o relatório JSON diz que pulou", r2["aferições"][0].get("pulado"))


def _materia_fake(niveis=("padrao",)):
    """MateriaVault mínima: `montar` só precisa de niveis/dir/materia_id."""
    return casar_materias.MateriaVault(
        materia_id="lingua-portuguesa", escopo="_COMUM",
        dir=Path(tempfile.gettempdir()) / "nao-existe", n_assuntos=3,
        niveis=list(niveis))


def test_tabela_usa_o_numero_real_da_questao():
    """Regressão: a coluna Q imprimia `i + 1`, renumerando de 1 a N.

    Numa faixa 21–25 a tabela saía `Q1…Q5` enquanto o `--bloco-out` que o agente lê
    traz os números reais — o cruzamento questão↔veredicto era feito contra rótulos
    que não existem na prova. Invisível só em Português, que começa em 1.
    """
    import build_afericao
    dados = [{"versao": "A", "caderno": "4", "prova": Path("p.pdf"),
              "gabarito": {21: "A", 22: "B", 23: "C", 24: "D", 25: "E"},
              "faixa": extrair_questoes.Faixa("Língua Portuguesa", 21, 25),
              "materia": _materia_fake(), "bloco": "", "avisos": []}]
    linhas = build_afericao.montar(dados, Path("/tmp"), "CESGRANRIO").splitlines()
    qs = [ln.split("|")[1].strip() for ln in linhas
          if ln.startswith("|") and ln.split("|")[1].strip().isdigit()]
    checar(qs == ["21", "22", "23", "24", "25"],
           "a coluna Q traz o número real da questão", qs)


def test_provas_com_faixas_diferentes_nao_estouram_nem_pareiam_errado():
    """Regressão: `sorted(d["gabarito"])[i]` indexava CADA prova pela posição da
    primeira. Contagens diferentes davam IndexError; faixas diferentes casavam
    gabaritos de questões distintas em silêncio, que é o pior dos dois."""
    import build_afericao
    def d(versao, gab):
        return {"versao": versao, "caderno": "4", "gabarito": gab,
                "prova": Path(f"{versao}.pdf"),
                "faixa": extrair_questoes.Faixa("Língua Portuguesa", 1, 3),
                "materia": _materia_fake(), "bloco": "", "avisos": []}
    dados = [d("A", {1: "A", 2: "B", 3: "C"}),
             d("B", {1: "E", 3: "D"})]                      # sem a 2, e mais curta
    linhas = [ln for ln in build_afericao.montar(dados, Path("/tmp"), "X").splitlines()
              if ln.startswith("|") and ln.split("|")[1].strip().isdigit()]
    celulas = {ln.split("|")[1].strip(): [c.strip() for c in ln.split("|")[2:4]]
               for ln in linhas}
    checar(celulas.get("1") == ["A", "E"], "questão 1 pareia com a 1", celulas.get("1"))
    checar(celulas.get("2") == ["B", "?"],
           "questão ausente numa prova vira '?', não a resposta da seguinte",
           celulas.get("2"))
    checar(celulas.get("3") == ["C", "D"], "questão 3 pareia com a 3", celulas.get("3"))


def test_build_afericao_forcar_faz_backup():
    """`--forcar` é a saída explícita — e mesmo ela guarda o que havia."""
    com_texto({"p.pdf": CADERNO_A + CAPA + CORPO, "g.pdf": GABARITO_PDF})
    with tempfile.TemporaryDirectory() as d:
        conc = _vault(Path(d), {"_COMUM/lingua-portuguesa":
                                {"assuntos": 2, "niveis": ["padrao"]}})
        destino = Path(_rodar_build(conc)["aferições"][0]["destino"])
        destino.write_text("JULGAMENTO ANTIGO\n", encoding="utf-8")

        r = _rodar_build(conc, ["--forcar"])
        checar(r["aferições"][0]["pulado"] is False, "com --forcar não pula")
        checar("JULGAMENTO ANTIGO" not in destino.read_text(encoding="utf-8"),
               "com --forcar regenera")
        bak = destino.with_suffix(".md.bak")
        checar(bak.exists() and "JULGAMENTO ANTIGO" in bak.read_text(encoding="utf-8"),
               "o backup preserva o julgamento anterior")


# --------------------------------------------------------------------------- #
# Quadrix — fixtures são a saída REAL do pdftotext (ver tests/fixtures/quadrix/):
# os três gabaritos inteiros e o recorte estrutural dos cadernos do SEDES/DF 2026.
# --------------------------------------------------------------------------- #
FIX = AQUI / "fixtures" / "quadrix"
GAB_SEDES = (FIX / "gabarito-sedes-2026-preliminar.layout.txt").read_text(encoding="utf-8")
GAB_CRESS_MG = (FIX / "gabarito-cress-mg-2024-definitivo.layout.txt").read_text(encoding="utf-8")
GAB_CRESS_RS = (FIX / "gabarito-cress-rs-2026-definitivo.layout.txt").read_text(encoding="utf-8")
CAD_200_A = (FIX / "caderno-sedes-2026-200-tipo-a.raw.txt").read_text(encoding="utf-8")
CAD_200_B = (FIX / "caderno-sedes-2026-200-tipo-b.raw.txt").read_text(encoding="utf-8")


def com_paginas(mapa: dict[str, str]):
    """Como `com_texto`, mas respeita `ini`/`fim` cortando nas quebras de página
    (`\\f`), como o pdftotext faz. Sem isso, ler "só as primeiras páginas" e ler o
    documento inteiro dão o mesmo resultado no teste — e o defeito não aparece."""
    def falso(pdf, layout=True, ini=None, fim=None):
        paginas = mapa[Path(pdf).name].split("\f")
        if ini or fim:
            paginas = paginas[(ini or 1) - 1:fim]
        return "\f".join(paginas)
    for mod in (prova_id, extrair_questoes, gabmod, quadrix):
        mod.texto = falso


def _vault_quadrix(base: Path, materias: dict[str, dict]) -> Path:
    """Vault do SEDES: concurso oficial da Quadrix, assuntos com `materia:` no
    frontmatter — de onde a aferição Quadrix tira o nome legível da matéria."""
    conc = base / "SEDES_2026"
    conc.mkdir(parents=True)
    (conc / ".meta.json").write_text(
        json.dumps({"modo": "oficial", "banca": "Instituto Quadrix"}), encoding="utf-8")
    for chave, cfg in materias.items():
        escopo, mid = chave.split("/")
        for i in range(cfg["assuntos"]):
            for nivel in cfg["niveis"]:
                d = conc / escopo / "03-APROFUNDAMENTO" / mid / "assuntos" / f"a{i}" / f"{nivel}--f"
                d.mkdir(parents=True, exist_ok=True)
                (d / f"a{i}--{nivel}--f--SEDES_2026.md").write_text(
                    f'---\ntitle: x\nmateria: "{cfg["nome"]}"\n---\n\n'
                    "## 🧩 Subtópicos que este assunto engloba\n- conceito alfa\n",
                    encoding="utf-8")
    return conc


def _rodar(argv: list[str]) -> dict:
    import build_afericao
    import io
    from contextlib import redirect_stdout
    sys.argv = ["b"] + argv
    buf = io.StringIO()
    with redirect_stdout(buf):
        build_afericao.main()
    return json.loads(buf.getvalue())


def test_quadrix_banca_lida_no_documento_inteiro():
    """Regressão: a banca era lida só das duas primeiras páginas.

    O gabarito do SEDES tem 8 páginas e só a ÚLTIMA assina "INSTITUTO QUADRIX".
    Lido pela capa, ele virava CESGRANRIO e ia para o leitor de "N - X", que não
    acha nada nele.
    """
    com_paginas({"g.pdf": GAB_SEDES, "c.pdf": CAD_200_A})
    checar("QUADRIX" not in GAB_SEDES.split("\f")[0].upper(),
           "fixture: a primeira página do gabarito não diz Quadrix")
    checar(quadrix.banca_do_pdf(Path("g.pdf")) == "quadrix",
           "gabarito de 8 páginas é reconhecido como Quadrix")
    checar(quadrix.banca_do_pdf(Path("c.pdf")) == "quadrix", "caderno também")
    com_texto({"bb.pdf": CADERNO_A + CAPA + CORPO})
    checar(quadrix.banca_do_pdf(Path("bb.pdf")) == "cesgranrio",
           "a CESGRANRIO segue pelo caminho antigo")


def test_gabarito_quadrix_le_a_grade_por_cargo_e_tipo():
    """O gabarito Quadrix é grade (números sobre letras), uma seção por cargo e tipo.
    O leitor da CESGRANRIO procura "N - X" e "GABARITO n" — não acha nada nele."""
    com_texto({"g.pdf": GAB_SEDES})
    try:
        gabmod.respostas(Path("g.pdf"), "1")
        checar(False, "fixture: o leitor da CESGRANRIO não lê a grade")
    except gabmod.GabaritoErro:
        checar(True, "fixture: o leitor da CESGRANRIO não lê a grade")
    g = quadrix.ler_gabarito(Path("g.pdf"))
    checar(len(g.secoes) == 45, "15 cargos × 3 tipos = 45 seções", len(g.secoes))
    checar(g.fonte == "preliminar", "lê PRELIMINAR do cabeçalho", g.fonte)
    s = next(x for x in g.secoes if x.cargo == "TDAS - AGENTE SOCIAL" and x.tipo == "A")
    checar([s.respostas[q] for q in range(1, 6)] == ["C", "B", "C", "B", "D"],
           "Agente Social, tipo A, questões 1-5", [s.respostas[q] for q in range(1, 6)])
    checar(len(s.respostas) == 60 and not s.anuladas, "60 respostas, nenhuma anulada")
    d = g.divisoes[0]
    checar(d.tipos == ["A", "B", "C"], "tabela de divisão com uma coluna por tipo", d.tipos)
    checar(d.areas["Conhecimentos Gerais"] == {"A": (1, 20), "B": (41, 60), "C": (21, 40)},
           "Conhecimentos Gerais muda de faixa conforme o tipo",
           d.areas.get("Conhecimentos Gerais"))


def test_tipos_quadrix_sao_as_mesmas_questoes_em_rodizio():
    """O número que sustenta a convenção: nos tipos A/B/C a área Conhecimentos Gerais
    tem as MESMAS 20 respostas, só em outra faixa (1–20, 41–60, 21–40). Aferir dois
    tipos contaria cada questão duas vezes."""
    com_texto({"g.pdf": GAB_SEDES})
    g = quadrix.ler_gabarito(Path("g.pdf"))
    sec = {x.tipo: x for x in g.secoes if x.cargo == "TDAS - AGENTE SOCIAL"}
    cg = {t: [sec[t].respostas[q] for q in range(a, a + 20)]
          for t, a in (("A", 1), ("B", 41), ("C", 21))}
    checar(cg["A"] == cg["B"] == cg["C"], "as 20 respostas de CG coincidem nos 3 tipos")


def test_anulada_quadrix_vira_anulada_e_nao_resposta():
    """A Quadrix marca a anulada com `X` ("Item 37: anulado.", CRESS-MG 2024). A regex
    da CESGRANRIO só aceita [A-E]: a questão sumia, e o fallback estourava traceback."""
    com_texto({"g.pdf": GAB_CRESS_MG})
    g = quadrix.ler_gabarito(Path("g.pdf"))
    s = next(x for x in g.secoes if x.cargo == "ASSISTENTE SOCIAL")
    checar(s.anuladas == {37} and 37 not in s.respostas, "a 37 é anulada", s.anuladas)
    checar(s.codigo == "400" and s.tipo is None, "seção por código, sem tipo")
    checar(g.fonte == "definitivo", "lê DEFINITIVO do cabeçalho", g.fonte)
    d = quadrix.divisao_do_cargo(g, "ASSISTENTE SOCIAL")
    checar(d.areas == {"Conhecimentos Básicos": {None: (1, 20)},
                       "Conhecimentos Específicos": {None: (21, 60)}},
           "a tabela de divisão é a do próprio cargo", d.areas)


def test_divisao_por_nivel_falha_alto():
    """CRESS-RS divide por NÍVEL de cargo, e nada no gabarito diz o nível de cada
    cargo. Escolher uma tabela seria inventar a faixa das áreas."""
    com_texto({"g.pdf": GAB_CRESS_RS})
    g = quadrix.ler_gabarito(Path("g.pdf"))
    try:
        quadrix.divisao_do_cargo(g, "AGENTE FISCAL – ASSISTENTE SOCIAL")
        checar(False, "tabela por nível é recusada")
    except gabmod.GabaritoErro as e:
        checar("inventar" in str(e), "a recusa diz por quê", str(e))


def test_tipo_do_caderno_deduzido_pela_ordem_dos_blocos():
    """Nenhuma página do caderno imprime o tipo: ele sai da ordem dos blocos contra a
    tabela de divisão. No tipo B, Conhecimentos Gerais é a ÚLTIMA área (41–60)."""
    com_texto({"a.pdf": CAD_200_A, "b.pdf": CAD_200_B, "g.pdf": GAB_SEDES})
    pa = quadrix.identificar_par(Path("a.pdf"), Path("g.pdf"))
    pb = quadrix.identificar_par(Path("b.pdf"), Path("g.pdf"))
    checar(pa.problemas == [] and pa.tipo == "A", "caderno A é tipo A", pa.problemas)
    checar(pb.problemas == [] and pb.tipo == "B", "caderno B é tipo B", pb.problemas)
    checar(pa.cargo == "TDAS - AGENTE SOCIAL", "cargo lido do rodapé", pa.cargo)
    cg_b = next(f for f in pb.faixas if f.nome == "Conhecimentos Gerais")
    checar((cg_b.primeira, cg_b.ultima) == (41, 60), "no tipo B, CG é 41–60",
           (cg_b.primeira, cg_b.ultima))
    checar(pb.secao.respostas[41] == pa.secao.respostas[1],
           "e a resposta da 41 do B é a da 1 do A")


def test_gabarito_de_outro_concurso_e_recusado():
    """Gabarito errado não dá erro — dá resposta plausível. Caderno do SEDES com o
    gabarito do CRESS-MG: nenhum cargo casa com o rodapé, e a recusa nomeia os cargos."""
    com_texto({"a.pdf": CAD_200_A, "g.pdf": GAB_CRESS_MG})
    p = quadrix.identificar_par(Path("a.pdf"), Path("g.pdf"))
    checar(p.problemas and "nenhuma seção do gabarito casa" in p.problemas[0],
           "par de concursos diferentes é recusado", p.problemas)
    checar("ASSISTENTE SOCIAL" in p.problemas[0], "a recusa lista os cargos do gabarito")


def test_cargo_ambiguo_nao_e_desempatado():
    """`--cargo-prova SOCIAL` casa com Agente, Cuidador e Serviço Social: escolher um
    seria ler a seção de um cargo vizinho, com 60 respostas plausíveis."""
    com_texto({"a.pdf": CAD_200_A, "g.pdf": GAB_SEDES})
    p = quadrix.identificar_par(Path("a.pdf"), Path("g.pdf"), cargo_prova="SOCIAL")
    checar(p.problemas and "casa com" in p.problemas[0] and "cargos" in p.problemas[0],
           "o empate é recusado e nomeado", p.problemas)


def test_quadrix_recusa_dois_tipos_da_mesma_prova():
    """Os tipos são as mesmas questões: dois cadernos na mesma execução dobrariam a
    amostra declarada (`provas_aferidas_n`) sem nenhuma questão nova."""
    com_texto({"a.pdf": CAD_200_A, "b.pdf": CAD_200_B, "g.pdf": GAB_SEDES})
    with tempfile.TemporaryDirectory() as d:
        conc = _vault_quadrix(Path(d), {"_COMUM/lingua-portuguesa":
                                        {"assuntos": 1, "niveis": ["padrao"],
                                         "nome": "Língua Portuguesa"}})
        try:
            _rodar(["--concurso-dir", str(conc), "--prova", "a.pdf", "--prova", "b.pdf",
                    "--gabarito", "g.pdf", "--gabarito", "g.pdf"])
            checar(False, "dois tipos são recusados")
        except SystemExit as e:
            checar("duas vezes" in str(e), "a recusa explica a contagem dobrada", str(e))


def _mapa_preenchido(caminho: Path, atribuicao) -> None:
    m = json.loads(caminho.read_text(encoding="utf-8"))
    for q, item in m["questoes"].items():
        item["materia"] = atribuicao(int(q))
    caminho.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")


def test_quadrix_mapa_em_duas_etapas_gera_uma_afericao_por_materia():
    """A matéria de cada questão não está impressa na prova Quadrix: é julgamento do
    agente. O script grava o esqueleto, recusa o que não foi preenchido e só então
    gera uma aferição por matéria, cada uma com as suas questões."""
    com_texto({"a.pdf": CAD_200_A, "g.pdf": GAB_SEDES})
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        conc = _vault_quadrix(base, {
            "_COMUM/lingua-portuguesa": {"assuntos": 2, "niveis": ["padrao", "detalhado"],
                                         "nome": "Língua Portuguesa"},
            "_COMUM/conhecimentos-df": {"assuntos": 1, "niveis": ["padrao"],
                                        "nome": "Conhecimentos do DF"}})
        mapa = base / "mapa-cg.json"
        r1 = _rodar(["--concurso-dir", str(conc), "--prova", "a.pdf", "--gabarito",
                     "g.pdf", "--area", "Conhecimentos Gerais", "--mapa-out", str(mapa)])
        m = json.loads(mapa.read_text(encoding="utf-8"))
        checar(r1["a_preencher"] == 20 and len(m["questoes"]) == 20,
               "esqueleto com as 20 questões da área", r1["a_preencher"])
        checar(m["questoes"]["1"] == {"gabarito": "C", "materia": "···"},
               "gabarito preenchido, matéria por julgar", m["questoes"]["1"])
        checar(sorted(m["candidatas"]) == ["_COMUM/conhecimentos-df",
                                           "_COMUM/lingua-portuguesa"],
               "candidatas vêm do vault", m["candidatas"])

        try:
            _rodar(["--concurso-dir", str(conc), "--mapa", str(mapa)])
            checar(False, "mapa não preenchido é recusado")
        except SystemExit as e:
            checar("por preencher" in str(e), "a recusa aponta o que falta", str(e)[:80])

        _mapa_preenchido(mapa, lambda q: ("_COMUM/lingua-portuguesa" if q <= 8 else
                                          "fora-do-vault" if q == 20 else
                                          "_COMUM/conhecimentos-df"))
        r2 = _rodar(["--concurso-dir", str(conc), "--mapa", str(mapa)])
        por = {x["materia"]: x for x in r2["aferições"]}
        checar(por["lingua-portuguesa"]["questoes"] == list(range(1, 9)),
               "Português recebe as 8 questões atribuídas", por["lingua-portuguesa"]["questoes"])
        checar(por["conhecimentos-df"]["questoes"] == list(range(9, 20)),
               "Conhecimentos do DF recebe as 11", por["conhecimentos-df"]["questoes"])
        checar(r2["fora_do_vault"] == [20], "a questão fora do vault aparece no relatório",
               r2["fora_do_vault"])
        doc = Path(por["lingua-portuguesa"]["destino"]).read_text(encoding="utf-8")
        checar("questoes_aferidas: 8" in doc and 'gabarito_fonte: "preliminar"' in doc,
               "frontmatter com a amostra e a fonte do gabarito")
        checar('cargo_prova: "TDAS - AGENTE SOCIAL"' in doc and "tipo_caderno: A" in doc,
               "frontmatter diz o caderno — o comparar_gabaritos precisa disso")
        checar("Gabarito PRELIMINAR" in doc, "a ressalva do preliminar vai no documento")
        checar("# 🎯 Aferição do material contra prova real — Língua Portuguesa" in doc,
               "o título é a matéria do vault, não a área da prova")
        checar("{" not in doc.split("---")[1], "nenhum placeholder vaza no frontmatter")


def test_quadrix_mapa_nao_e_fonte_do_gabarito():
    """O mapa é editado à mão. Se a letra do gabarito mudou nele, a etapa 2 recusa:
    o gabarito vem sempre do PDF, relido."""
    com_texto({"a.pdf": CAD_200_A, "g.pdf": GAB_SEDES})
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        conc = _vault_quadrix(base, {"_COMUM/lingua-portuguesa":
                                     {"assuntos": 1, "niveis": ["padrao"],
                                      "nome": "Língua Portuguesa"}})
        mapa = base / "m.json"
        _rodar(["--concurso-dir", str(conc), "--prova", "a.pdf", "--gabarito", "g.pdf",
                "--area", "Conhecimentos Gerais", "--mapa-out", str(mapa)])
        _mapa_preenchido(mapa, lambda q: "_COMUM/lingua-portuguesa")
        m = json.loads(mapa.read_text(encoding="utf-8"))
        m["questoes"]["1"]["gabarito"] = "A"
        mapa.write_text(json.dumps(m), encoding="utf-8")
        try:
            _rodar(["--concurso-dir", str(conc), "--mapa", str(mapa)])
            checar(False, "gabarito editado no mapa é recusado")
        except SystemExit as e:
            checar("não é fonte do gabarito" in str(e), "a recusa diz por quê", str(e)[:90])


def test_area_ambigua_e_recusada():
    """`--area "Conhecimentos Específicos"` casa com as duas áreas de específicos do
    SEDES. A primeira versão ficava com a primeira por substring e aferia a área errada
    sem aviso."""
    com_texto({"a.pdf": CAD_200_A, "g.pdf": GAB_SEDES})
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        conc = _vault_quadrix(base, {"_COMUM/lingua-portuguesa":
                                     {"assuntos": 1, "niveis": ["padrao"],
                                      "nome": "Língua Portuguesa"}})
        try:
            _rodar(["--concurso-dir", str(conc), "--prova", "a.pdf", "--gabarito", "g.pdf",
                    "--area", "Conhecimentos Específicos", "--mapa-out",
                    str(base / "m.json")])
            checar(False, "área ambígua é recusada")
        except SystemExit as e:
            checar("casa com 2 áreas" in str(e), "a recusa nomeia as duas", str(e))
        r = _rodar(["--concurso-dir", str(conc), "--prova", "a.pdf", "--gabarito", "g.pdf",
                    "--area", "Conhecimentos Específicos Comuns", "--mapa-out",
                    str(base / "m2.json")])
        checar(r["faixa"] == [21, 40], "o nome completo escolhe a área", r["faixa"])


def test_mapa_valida_questao_faltando_e_materia_desconhecida():
    import mapa_questoes
    m = {"faixa": [1, 3], "candidatas": ["_COMUM/a"],
         "questoes": {"1": {"gabarito": "A", "materia": "_COMUM/a"},
                      "2": {"gabarito": "B", "materia": "_COMUM/z"}}}
    erros = mapa_questoes.validar(m, {"_COMUM/a"})
    checar(any("faltam as questões [3]" in e for e in erros),
           "questão esquecida é erro — sumiria da amostra", erros)
    checar(any("'_COMUM/z' não está entre as candidatas" in e for e in erros),
           "matéria fora das candidatas é erro", erros)


def test_anulada_sai_do_denominador_e_entra_na_amostra():
    """Anulada é retirada pela banca: não mede nada, mas foi aferida. O validador
    antigo somava resp+parc+não+sem e acusava a amostra de não fechar."""
    with tempfile.TemporaryDirectory() as d:
        txt = (CAB.replace("questoes_aferidas: 30", "questoes_aferidas: 8")
               .replace("provas_aferidas_n: 3", "provas_aferidas_n: 1")
               + "| | `padrao` |\n|---|---:|\n"
               "| Questões plenamente respondidas | 5 |\n| Respondidas em parte | 1 |\n"
               "| Não respondidas | 1 |\n| **Sem material** (fora do denominador) | 0 |\n"
               "| **Anuladas** (fora do denominador) | 1 |\n| **Nota** | **8,14** |\n")
        erros = validar_afericao.conferir(_af(txt, Path(d)))
        checar(erros == [], "anulada fora do denominador e dentro da amostra", erros)
        sem_linha = txt.replace("| **Anuladas** (fora do denominador) | 1 |\n", "")
        erros = validar_afericao.conferir(_af(sem_linha, Path(d)))
        checar(any("não somam a amostra" in e for e in erros),
               "sem contar a anulada, a amostra não fecha", erros)


def test_montar_preenche_anulada_e_nao_vaza_placeholder_na_cesgranrio():
    import build_afericao
    base = {"versao": "A", "caderno": "4", "prova": Path("p.pdf"),
            "faixa": extrair_questoes.Faixa("Língua Portuguesa", 1, 3),
            "materia": _materia_fake(), "bloco": "", "avisos": []}
    ces = build_afericao.montar([dict(base, gabarito={1: "A", 2: "B", 3: "C"})],
                                Path("/tmp"), "CESGRANRIO")
    checar("{" not in ces and "Anuladas" not in ces and "PRELIMINAR" not in ces,
           "CESGRANRIO sai sem os campos opcionais")
    fm = ces.split("---")[1]
    checar("\n\n" not in fm.strip("\n"), "nem linha em branco no frontmatter")
    qx = build_afericao.montar([dict(base, gabarito={1: "A", 2: "⊘", 3: "C"},
                                     anuladas={2}, gabarito_fonte="preliminar")],
                               Path("/tmp"), "Quadrix")
    linha2 = next(ln for ln in qx.splitlines() if ln.startswith("| 2 |"))
    checar(linha2.rstrip().endswith("| ⊘ |"), "a anulada já vem com veredicto ⊘", linha2)
    checar("**Anuladas** (fora do denominador)" in qx, "e a linha de anuladas aparece")


def test_gabarito_com_tres_digitos():
    """Prova de 100+ questões: a regex `\\d{1,2}` lia "100 - B" como "00 - B"."""
    com_texto({"g.pdf": "GABARITO 1\n 99 - A   100 - B   101 - C\n"})
    r = gabmod.respostas(Path("g.pdf"), "1", questoes=range(99, 102))
    checar(r == {99: "A", 100: "B", 101: "C"}, "lê questões de três dígitos", r)


def test_comparar_gabaritos_aponta_so_o_que_rejulgar():
    """Do preliminar ao definitivo: letra trocada e questão anulada voltam para o
    agente; o resto continua valendo. Restrito às questões da aferição."""
    import comparar_gabaritos as cg
    dif = cg.diferencas({1: "A", 2: "B", 3: "C"}, set(), {1: "A", 2: "D"}, {3})
    checar([x["questao"] for x in dif["alteradas"]] == [2], "letra trocada", dif["alteradas"])
    checar(dif["anuladas_novas"] == [3], "anulada no definitivo", dif["anuladas_novas"])
    checar(dif["rejulgar"] == [2, 3], "as duas voltam para o agente", dif["rejulgar"])
    so = cg.diferencas({1: "A", 2: "B", 3: "C"}, set(), {1: "A", 2: "D"}, {3}, [1, 3])
    checar(so["rejulgar"] == [3], "restrito às questões da aferição", so["rejulgar"])

    import build_afericao
    doc = build_afericao.montar([{
        "versao": "A", "caderno": None, "prova": Path("p.pdf"), "rotulo": "Tipo A",
        "faixa": extrair_questoes.Faixa("Conhecimentos Gerais", 1, 20),
        "materia": _materia_fake(), "bloco": "", "avisos": [],
        "gabarito": {4: "B", 7: "C", 12: "A"}}], Path("/tmp"), "Quadrix")
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "00-AFERICAO-X.md"
        md.write_text(doc, encoding="utf-8")
        checar(cg.questoes_da_afericao(md) == [4, 7, 12],
               "lê as questões que a aferição julgou", cg.questoes_da_afericao(md))


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
    total = sum(1 for _ in testes)
    print(f"\n{total - len(FALHAS)}/{total} testes passaram.")
    sys.exit(1 if FALHAS else 0)
