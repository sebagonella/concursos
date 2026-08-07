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
if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
    total = sum(1 for _ in testes)
    print(f"\n{total - len(FALHAS)}/{total} testes passaram.")
    sys.exit(1 if FALHAS else 0)
