#!/usr/bin/env python3
"""
test_material_id.py — trava a convenção de identidade de material.

Roda standalone (sem pytest):
    python3 skills/concurso-prep/scripts/tests/test_material_id.py

Os casos NÃO são inventados: cada um é uma linha literal dos mapas ou dos
catálogos dos dois concursos do vault, colhida na auditoria de 03/08/2026. É a
mesma regra que já vale para os fixtures da `concurso-publica` — caso inventado
é teste que se autoconfirma, e este módulo existe justamente porque a realidade
do vault é mais suja do que o formato documentado.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import material_id as m  # noqa: E402

FALHAS: list[str] = []
PASSES = 0


def checar(nome, cond, detalhe=""):
    global PASSES
    if cond:
        print(f"  PASS  {nome}")
        PASSES += 1
    else:
        print(f"  FAIL  {nome}: {detalhe}")
        FALHAS.append(nome)


# --------------------------------------------------------------------------- #
# sobrenome e id
# --------------------------------------------------------------------------- #
def test_sobrenome_de_casos_reais():
    casos = {
        "Fernando Pestana": "pestana",
        "Marcelo Rosenthal": "rosenthal",
        "Cormen, Leiserson, Rivest & Stein": "cormen",
        "Wes McKinney": "mckinney",
        "C. J. Date": "date",
        "Berenice Rojas Couto; Maria Carmelita Yazbek": "couto",
        "Maria Berenice Dias": "dias",
        "Philip Kotler e Kevin Keller": "kotler",
        "": "",
    }
    for autor, esperado in casos.items():
        checar(f"sobrenome({autor!r})", m.sobrenome(autor) == esperado,
               f"deu {m.sobrenome(autor)!r}, esperado {esperado!r}")


def test_as_grafias_do_pestana_convergem():
    """Duas das 4 grafias medidas no vault são o mesmo título com 'Públicos' a
    mais — o ruído de 'para concursos públicos' não pode gerar id diferente."""
    a = m.propor_id("A Gramática para Concursos Públicos", "Fernando Pestana")
    b = m.propor_id("A Gramática para Concursos", "Fernando Pestana")
    checar("grafias_do_pestana_convergem", a == b == "mat-pestana-gramatica",
           f"{a!r} vs {b!r}")


def test_titulo_diferente_nao_converge_em_silencio():
    """`Português para Concursos` e `A Gramática para Concursos`, ambos de
    Pestana, são títulos DIFERENTES no vault. Podem ser a mesma obra mal citada —
    mas isso é decisão humana. A ferramenta não pode fundi-los sozinha."""
    a = m.chave_obra("A Gramática para Concursos", "Fernando Pestana")
    b = m.chave_obra("Português para Concursos", "Fernando Pestana")
    checar("titulo_diferente_nao_converge", a != b, "fundiu obras distintas")


def test_sem_autor_o_id_nao_finge():
    ident = m.propor_id("Matemática básica para concursos", "")
    checar("sem_autor_id_nao_inventa", ident.startswith("mat-") and "-" in ident,
           f"deu {ident!r}")
    checar("sem_autor_id_nao_traz_sobrenome", "pestana" not in ident, ident)


# --------------------------------------------------------------------------- #
# prefixos — os 31 do vault contra os 5 canônicos
# --------------------------------------------------------------------------- #
def test_prefixos_de_norma_convergem():
    """7 rótulos concorrentes para norma foram medidos no vault."""
    for p in ("Norma-fonte", "Lei fonte", "Fonte primária", "Decreto", "Leis",
              "Norma", "Norma-fonte (gratuita, oficial)"):
        tipo, _ = m.tipo_do_prefixo(p)
        checar(f"prefixo_norma({p!r})", tipo == "norma", f"deu {tipo!r}")


def test_parenteses_de_qualificacao_nao_atrapalham():
    """O parêntese precisa sair ANTES da normalização — depois dela os
    parênteses já não existem e o rótulo vira quatro palavras soltas."""
    tipo, _ = m.tipo_do_prefixo("Documento oficial (público)")
    checar("parenteses_de_qualificacao", tipo == "documento", f"deu {tipo!r}")


def test_prefixo_desconhecido_degrada_e_nao_some():
    tipo, canonico = m.tipo_do_prefixo("Referência de apoio (gratuito)")
    checar("prefixo_desconhecido_vira_outro", tipo == "outro", f"deu {tipo!r}")
    checar("prefixo_desconhecido_nao_e_canonico", canonico is False)


def test_forma_canonica_e_reconhecida_como_tal():
    for p, esperado in (("Livro", "livro"), ("Questões", "questoes"),
                        ("YouTube", "video"), ("Documento", "documento")):
        tipo, canonico = m.tipo_do_prefixo(p)
        checar(f"canonico({p!r})", tipo == esperado and canonico is True,
               f"deu ({tipo!r}, {canonico})")


# --------------------------------------------------------------------------- #
# parsing dos itens — as três ordens observadas
# --------------------------------------------------------------------------- #
def test_ordem_titulo_autor_do_mapa():
    i = m.parsear_item(
        "- Livro: *Administração de Marketing* — Philip Kotler e Kevin Keller (Pearson)")
    checar("mapa_titulo", i["titulo"] == "Administração de Marketing", i["titulo"])
    checar("mapa_autor", i["autor"] == "Philip Kotler e Kevin Keller", i["autor"])
    checar("mapa_editora", i["editora"] == "Pearson", i["editora"])


def test_ordem_autor_titulo_do_catalogo():
    """A lista canônica usa a ordem INVERTIDA em relação aos mapas."""
    i = m.parsear_item("- Fernando Pestana — *A Gramática para Concursos*. Método.")
    checar("catalogo_autor", i["autor"] == "Fernando Pestana", i["autor"])
    checar("catalogo_titulo", i["titulo"] == "A Gramática para Concursos", i["titulo"])


def test_ordem_com_virgulas():
    i = m.parsear_item(
        "- Livro: *Informática para Concursos — Teoria e Questões*, "
        "João Antonio Carvalho, Ed. Elsevier")
    checar("virgula_autor", i["autor"] == "João Antonio Carvalho", i["autor"])
    checar("virgula_editora", i["editora"] == "Elsevier", i["editora"])


def test_ponteiro_de_leitura_nao_vira_autor():
    """`(Método), cap. 3` — a cauda de capítulo tem de sair sem levar o autor."""
    i = m.parsear_item("- Livro: *Matemática Financeira Descomplicada* — "
                       "Carlos Alberto Campregher (Método), cap. 3")
    checar("cap_nao_engole_autor", i["autor"] == "Carlos Alberto Campregher", i["autor"])
    checar("cap_editora", i["editora"] == "Método", i["editora"])


def test_capitulo_dentro_do_parentese():
    """`(ou o capítulo de Excel em João Antonio)` — cortar em 'capítulo' antes de
    fechar o parêntese deixava o autor como `Fabrício Melo (ou o`."""
    i = m.parsear_item("- Livro: *Excel para Concursos*, Fabrício Melo "
                       "(ou o capítulo de Excel em João Antonio)")
    checar("parentese_com_capitulo", i["autor"] == "Fabrício Melo", i["autor"])


def test_confissao_de_lacuna_nao_vira_dado():
    """O mapa dizendo que não sabe não pode virar `Autor: verificar autor/`."""
    i = m.parsear_item("- Livro: *Raciocínio Lógico para Concursos* — "
                       "verificar autor/editora atual")
    checar("lacuna_sem_autor", i["autor"] == "", f"deu {i['autor']!r}")
    checar("lacuna_sem_editora", i["editora"] == "", f"deu {i['editora']!r}")
    checar("lacuna_mantem_titulo",
           i["titulo"] == "Raciocínio Lógico para Concursos", i["titulo"])


def test_livro_sem_autor_continua_visivel():
    """São 25 itens assim no vault. Sumir com eles esconde a pendência."""
    i = m.parsear_item("- Livro: Matemática básica para concursos")
    checar("sem_autor_tipo", i["tipo"] == "livro", i["tipo"])
    checar("sem_autor_titulo", i["titulo"] == "Matemática básica para concursos",
           i["titulo"])
    checar("sem_autor_autor_vazio", i["autor"] == "")


def test_item_sem_prefixo_nenhum():
    """27 itens do vault não têm prefixo. Continuam sendo itens."""
    i = m.parsear_item("- Lei nº 8.742/1993 (LOAS) atualizada — fonte primária")
    checar("sem_prefixo_tipo", i["tipo"] == "outro", i["tipo"])
    checar("sem_prefixo_texto_intacto", "8.742" in i["texto"])


def test_continuacao_de_linha_nao_trunca():
    """3 itens do vault quebram em várias linhas; parser linha-a-linha os corta."""
    bloco = ("- 📕 **Fonte principal**: *Manual de Primeiros Socorros*\n"
             "      SAMU-192 São Paulo, 2022 (62 pp.)\n")
    itens = m.itens_do_bloco(bloco)
    checar("continuacao_um_item_so", len(itens) == 1, f"deu {len(itens)}")
    checar("continuacao_texto_completo", "SAMU-192" in itens[0]["texto"],
           itens[0]["texto"])


# --------------------------------------------------------------------------- #
# catálogo
# --------------------------------------------------------------------------- #
def test_round_trip_do_catalogo():
    e = {"titulo": "Gramática para Concursos", "autor": "Marcelo Rosenthal",
         "editora": "Elsevier · 3ª ed., 2019", "isbn": "978-85-352-0000-0",
         "cobre": "lingua-portuguesa", "onde_obter": "editora", "pendencia": "",
         "ancora": "mat-rosenthal-gramatica"}
    volta = m.parsear_catalogo(m.render_entrada(e))
    checar("round_trip_uma_entrada", len(volta) == 1, f"deu {len(volta)}")
    for campo in ("titulo", "autor", "isbn", "cobre", "ancora"):
        checar(f"round_trip_{campo}", volta[0][campo] == e[campo],
               f"{volta[0][campo]!r} != {e[campo]!r}")


def test_campo_vazio_nao_vira_linha_em_branco():
    e = {"titulo": "X", "autor": "Y", "editora": "", "isbn": "", "cobre": "",
         "onde_obter": "", "pendencia": "", "ancora": "mat-y-x"}
    md = m.render_entrada(e)
    checar("campo_vazio_omitido", "ISBN" not in md and "Editora" not in md, md)


def test_wikilink_usa_ancora_e_nao_titulo():
    """O rótulo é para humano e pode mudar; o vínculo é a âncora."""
    e = {"titulo": "Gramática para Concursos", "autor": "Marcelo Rosenthal",
         "ancora": "mat-rosenthal-gramatica"}
    link = m.wikilink(e)
    checar("wikilink_ancora", "#^mat-rosenthal-gramatica" in link, link)
    checar("wikilink_rotulo", link.endswith("|Rosenthal — Gramática para Concursos]]"),
           link)


def test_item_que_ja_aponta_e_lido_pela_ancora():
    i = m.parsear_item(
        "- Livro: [[livros-recomendados#^mat-pestana-gramatica|Pestana — Gramática]] — cap. 4")
    checar("aponta_ancora", i["ancora"] == "mat-pestana-gramatica", i["ancora"])
    checar("aponta_alvo", i["alvo"] == "livros-recomendados", i["alvo"])


def test_casamento_e_exato_ou_nada():
    entradas = [
        {"titulo": "A Gramática para Concursos", "autor": "Fernando Pestana",
         "ancora": "mat-pestana-gramatica"},
        {"titulo": "Conhecimentos Bancários", "autor": "Edgar Abreu",
         "ancora": "mat-abreu-conhecimentos-bancarios"},
    ]
    # casa: mesma obra, editora diferente (as 3 editoras do Abreu no vault)
    i = m.parsear_item("- Livro: *Conhecimentos Bancários* — Edgar Abreu (A Casa do Concurseiro)")
    achada = m.casar_exato(i, entradas)
    checar("casa_apesar_da_editora_divergente",
           achada is not None and achada["ancora"] == "mat-abreu-conhecimentos-bancarios",
           str(achada))
    # NÃO casa: título diferente, mesmo autor
    i2 = m.parsear_item("- Livro: *Português para Concursos* — Fernando Pestana (Elsevier)")
    checar("nao_casa_titulo_diferente", m.casar_exato(i2, entradas) is None,
           "casou por semelhança — o repo proíbe inferir vínculo assim")
    # NÃO casa: sem autor
    i3 = m.parsear_item("- Livro: Matemática básica para concursos")
    checar("nao_casa_sem_correspondente", m.casar_exato(i3, entradas) is None)


def test_ambiguidade_vira_pendencia_nao_desempate():
    entradas = [
        {"titulo": "Gramática", "autor": "Fernando Pestana", "ancora": "mat-a"},
        {"titulo": "Gramática", "autor": "Fernando Pestana", "ancora": "mat-b"},
    ]
    i = m.parsear_item("- Livro: *Gramática* — Fernando Pestana")
    checar("ambiguidade_nao_desempata", m.casar_exato(i, entradas) is None,
           "escolheu uma das duas em silêncio")


def test_ids_unicos_desempatam_sem_reordenar():
    entradas = [
        {"titulo": "Gramática para Concursos", "autor": "Fernando Pestana", "ancora": ""},
        {"titulo": "Gramática para Concursos Públicos", "autor": "Fernando Pestana",
         "ancora": ""},
        {"titulo": "Estatística Básica", "autor": "Morettin", "ancora": "mat-ja-existia"},
    ]
    novos = m.ids_unicos(entradas)
    checar("nao_toca_no_que_ja_tem_id", "2" not in novos, str(novos))
    checar("desempata_colisao", novos["0"] != novos["1"], str(novos))
    checar("desempate_por_sufixo", novos["1"].startswith(novos["0"]), str(novos))


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    for nome, fn in sorted(list(globals().items())):
        if nome.startswith("test_") and callable(fn):
            fn()
    print()
    total = PASSES + len(FALHAS)
    if FALHAS:
        print(f"{PASSES}/{total} testes passaram — {len(FALHAS)} falha(s).")
        sys.exit(1)
    print(f"{PASSES}/{total} testes passaram.")
