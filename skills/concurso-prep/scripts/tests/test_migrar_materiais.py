#!/usr/bin/env python3
"""
test_migrar_materiais.py — trava o comportamento da migração de material.

Roda standalone:
    python3 skills/concurso-prep/scripts/tests/test_migrar_materiais.py

O que precisa estar travado, e por quê:

  - **dry-run é o padrão** — o script escreve no vault do usuário;
  - **nada do que a pessoa escreveu se perde** — o ponteiro de leitura (`cap. 4`)
    sobrevive à reescrita, e há backup antes de tocar no arquivo;
  - **casamento exato ou nada** — sem limiar de similaridade;
  - **o bloco de nível 2** do mapa de Português do SEDES é lido: é o único caso
    divergente do vault (11 itens num bloco `##` no fim do arquivo) e um leitor
    que só olha `###` o perderia inteiro.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import material_id as mid            # noqa: E402
import migrar_materiais as mig       # noqa: E402

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


MAPA = """---
tipo: mapa-materia
materia: "Língua Portuguesa"
---
# Mapa

## 1. Crase

### Material recomendado
- Livro: *A Gramática para Concursos* — Fernando Pestana (Método) — cap. 4
- Questões: https://qconcursos.com/crase

### Meta
- [ ] 30 questões
"""

MAPA_H2 = """---
tipo: mapa-materia
---
# Mapa

## 1. Tópico

### Subtópicos derivados
- [ ] x

## 📎 Material recomendado (referências)

- Livro: *Moderna Gramática Portuguesa* — Evanildo Bechara (Nova Fronteira)
- Livro: *Estatística Básica* — Bussab & Morettin (Saraiva)
"""

CATALOGO_LEGADO = """# Livros

## Língua Portuguesa
- Fernando Pestana — *A Gramática para Concursos Públicos*. Ed. Método.
- Rocha Lima — *Gramática Normativa da Língua Portuguesa*. Ed. José Olympio.
"""


def _montar(base: Path, com_catalogo=True, mapa=MAPA) -> Path:
    conc = base / "TESTE_2026"
    (conc / "_COMUM" / "03-MAPAS-COMUNS").mkdir(parents=True)
    (conc / "_COMUM" / "03-MAPAS-COMUNS" / "01-portugues.md").write_text(
        mapa, encoding="utf-8")
    if com_catalogo:
        (conc / "_COMUM" / "04-MATERIAIS").mkdir(parents=True)
        (conc / "_COMUM" / "04-MATERIAIS" / "livros-recomendados.md").write_text(
            CATALOGO_LEGADO, encoding="utf-8")
    return conc


def test_enriquecimento_casa_por_ancora_e_nao_apaga():
    """A pesquisa preenche o que falta; o que ela não achou NÃO apaga o que havia.

    Campo vazio no enriquecimento significa "não encontrei", que é diferente de
    "não existe". Deixar o vazio sobrescrever transformaria uma pesquisa
    incompleta em perda de dado já apurado.
    """
    por_escopo = {"_COMUM": [
        {"titulo": "A Gramática para Concursos", "autor": "Fernando Pestana",
         "editora": "Método", "isbn": "", "cobre": "", "onde_obter": "",
         "pendencia": "", "ancora": "mat-pestana-gramatica"},
        {"titulo": "Matemática básica", "autor": "", "editora": "", "isbn": "",
         "cobre": "", "onde_obter": "", "pendencia": "autoria não identificada",
         "ancora": "mat-matematica-basica"},
    ]}
    aplicados, ignorados = mig.aplicar_enriquecimento(por_escopo, [
        {"ancora": "mat-pestana-gramatica", "autor": "", "editora": "",
         "isbn": "978-85-309-8888-8", "pendencia": ""},
        {"ancora": "mat-matematica-basica", "autor": "Fulano de Tal",
         "editora": "Editora Y", "pendencia": ""},
        {"ancora": "mat-que-nao-existe", "autor": "Ninguém"},
    ])
    a, b = por_escopo["_COMUM"]
    checar("enriquece_isbn", a["isbn"] == "978-85-309-8888-8", a["isbn"])
    checar("nao_apaga_autor_existente", a["autor"] == "Fernando Pestana", a["autor"])
    checar("nao_apaga_editora_existente", a["editora"] == "Método", a["editora"])
    checar("preenche_o_que_faltava", b["autor"] == "Fulano de Tal", b["autor"])
    checar("achou_autor_limpa_pendencia", b["pendencia"] == "", b["pendencia"])
    checar("aplicados_conta_so_os_casados", aplicados == 2, str(aplicados))
    checar("ancora_desconhecida_e_reportada",
           ignorados == ["mat-que-nao-existe"], str(ignorados))


def test_enriquecimento_nao_renomeia_a_ancora():
    """Achar o autor depois NÃO muda o id: o mapa já pode estar apontando para
    ele, e renomear é a operação que quebra vínculo — a lição do
    `aprofundamento_id.py` vale igual aqui."""
    por_escopo = {"_COMUM": [
        {"titulo": "Obra X", "autor": "", "editora": "", "isbn": "", "cobre": "",
         "onde_obter": "", "pendencia": "sem autoria", "ancora": "mat-obra-x"},
    ]}
    mig.aplicar_enriquecimento(por_escopo, [
        {"ancora": "mat-obra-x", "autor": "Sobrenome Achado"}])
    checar("ancora_estavel", por_escopo["_COMUM"][0]["ancora"] == "mat-obra-x",
           por_escopo["_COMUM"][0]["ancora"])


def test_bloco_de_nivel_2_e_lido():
    """O mapa de Português do SEDES põe os 11 itens num bloco `##` no fim."""
    faixas = mig.blocos_de_material(MAPA_H2)
    checar("h2_um_bloco", len(faixas) == 1, f"deu {len(faixas)}")
    linhas = MAPA_H2.splitlines()
    ini, fim = faixas[0]
    itens = mid.itens_do_bloco("\n".join(linhas[ini:fim]))
    checar("h2_dois_itens", len(itens) == 2, f"deu {len(itens)}")
    checar("h2_titulo", itens[0]["titulo"] == "Moderna Gramática Portuguesa",
           itens[0]["titulo"])


def test_bloco_h3_para_no_proximo_heading_do_mesmo_nivel():
    faixas = mig.blocos_de_material(MAPA)
    linhas = MAPA.splitlines()
    itens = mid.itens_do_bloco("\n".join(linhas[faixas[0][0]:faixas[0][1]]))
    checar("h3_nao_engole_a_meta", len(itens) == 2, f"deu {len(itens)}")
    checar("h3_nao_pegou_checkbox",
           all("30 questões" not in i["texto"] for i in itens))


def test_dry_run_nao_escreve_nada():
    with tempfile.TemporaryDirectory() as d:
        conc = _montar(Path(d))
        antes = {p: p.read_bytes() for p in conc.rglob("*.md")}
        itens, catalogos = mig.varrer(conc)
        por_escopo, _, _ = mig.consolidar(itens, catalogos)
        mig.planejar_reescrita(itens, por_escopo)
        depois = {p: p.read_bytes() for p in conc.rglob("*.md")}
        checar("dry_run_nao_altera", antes == depois, "arquivo mudou sem --aplicar")
        checar("dry_run_sem_arquivo_novo", set(antes) == set(depois))


def test_catalogo_legado_e_aproveitado():
    """Os 62 itens já pesquisados não podem ser descartados: refazer a pesquisa
    inteira é caro, e o resultado pareceria que o vault não tinha bibliografia."""
    with tempfile.TemporaryDirectory() as d:
        conc = _montar(Path(d))
        _, catalogos = mig.varrer(conc)
        entradas = catalogos["_COMUM"]
        checar("legado_leu_as_duas", len(entradas) == 2, f"deu {len(entradas)}")
        checar("legado_autor", entradas[0]["autor"] == "Fernando Pestana",
               entradas[0]["autor"])
        checar("legado_editora", entradas[0]["editora"] == "Método",
               entradas[0]["editora"])


def test_grafias_da_mesma_obra_viram_uma_entrada():
    """No catálogo: 'A Gramática para Concursos Públicos'; no mapa: '… para
    Concursos'. Mesma obra, duas grafias — uma entrada só."""
    with tempfile.TemporaryDirectory() as d:
        conc = _montar(Path(d))
        itens, catalogos = mig.varrer(conc)
        por_escopo, _, _ = mig.consolidar(itens, catalogos)
        titulos = [e["titulo"] for e in por_escopo["_COMUM"]]
        pestana = [t for t in titulos if "Gramática para Concursos" in t]
        checar("uma_entrada_por_obra", len(pestana) == 1,
               f"{len(pestana)} entradas: {pestana}")


def test_reescrita_preserva_o_ponteiro_de_leitura():
    """`— cap. 4` é a única parte do item que o catálogo NÃO guarda."""
    entrada = {"titulo": "A Gramática para Concursos", "autor": "Fernando Pestana",
               "ancora": "mat-pestana-gramatica"}
    novo = mig.reescrever_item(
        "Livro: *A Gramática para Concursos* — Fernando Pestana (Método) — cap. 4",
        entrada)
    checar("reescrita_tem_ancora", "#^mat-pestana-gramatica" in novo, novo)
    checar("reescrita_preserva_capitulo", novo.rstrip().endswith("cap. 4"), novo)
    checar("reescrita_preserva_prefixo", novo.startswith("Livro: "), novo)


def test_aplicar_faz_backup_e_escreve():
    with tempfile.TemporaryDirectory() as d:
        conc = _montar(Path(d))
        itens, catalogos = mig.varrer(conc)
        por_escopo, _, _ = mig.consolidar(itens, catalogos)
        casados, _ = mig.planejar_reescrita(itens, por_escopo)
        escritos = mig.aplicar(conc, por_escopo, casados, reescrever=True)
        checar("aplicar_escreveu_catalogo", len(escritos["catalogos"]) == 1,
               str(escritos["catalogos"]))
        checar("aplicar_fez_backup", len(escritos["backups"]) >= 1,
               str(escritos["backups"]))
        mapa = conc / "_COMUM" / "03-MAPAS-COMUNS" / "01-portugues.md"
        texto = mapa.read_text(encoding="utf-8")
        checar("mapa_aponta_para_o_catalogo",
               "livros-recomendados#^" in texto, texto[:200])
        checar("mapa_manteve_o_capitulo", "cap. 4" in texto)
        bak = mapa.with_suffix(".md.bak")
        checar("backup_do_mapa_existe", bak.exists())
        checar("backup_tem_o_texto_original",
               "— Fernando Pestana (Método)" in bak.read_text(encoding="utf-8"))


def test_catalogo_gerado_e_relido_pela_convencao():
    """Round-trip: o que a migração escreve, o `material_id` tem de reler."""
    with tempfile.TemporaryDirectory() as d:
        conc = _montar(Path(d))
        itens, catalogos = mig.varrer(conc)
        por_escopo, _, _ = mig.consolidar(itens, catalogos)
        mig.aplicar(conc, por_escopo, [], reescrever=False)
        cat = conc / "_COMUM" / "04-MATERIAIS" / "livros-recomendados.md"
        lidas = mid.parsear_catalogo(cat.read_text(encoding="utf-8"))
        checar("round_trip_conta", len(lidas) == len(por_escopo["_COMUM"]),
               f'{len(lidas)} lidas vs {len(por_escopo["_COMUM"])} escritas')
        checar("round_trip_todas_com_ancora",
               all(e["ancora"] for e in lidas),
               str([e["titulo"] for e in lidas if not e["ancora"]]))


def test_sem_autor_vira_pendencia_declarada():
    mapa = MAPA.replace(
        "- Livro: *A Gramática para Concursos* — Fernando Pestana (Método) — cap. 4",
        "- Livro: Matemática básica para concursos")
    with tempfile.TemporaryDirectory() as d:
        conc = _montar(Path(d), com_catalogo=False, mapa=mapa)
        itens, catalogos = mig.varrer(conc)
        por_escopo, sem_autor, _ = mig.consolidar(itens, catalogos)
        checar("sem_autor_reportado", len(sem_autor) == 1, str(sem_autor))
        entrada = por_escopo["_COMUM"][0]
        checar("sem_autor_tem_pendencia", bool(entrada["pendencia"]),
               str(entrada))
        checar("sem_autor_nao_inventa_autor", entrada["autor"] == "",
               entrada["autor"])


def test_obra_de_um_cargo_so_fica_no_cargo():
    with tempfile.TemporaryDirectory() as d:
        conc = _montar(Path(d), com_catalogo=False)
        cargo = conc / "CARGO-X" / "03-MAPAS-MATERIAS"
        cargo.mkdir(parents=True)
        (cargo / "02-especificos.md").write_text(
            "# M\n\n### Material recomendado\n"
            "- Livro: *Só do Cargo* — Fulano de Tal (Editora X)\n", encoding="utf-8")
        itens, catalogos = mig.varrer(conc)
        por_escopo, _, _ = mig.consolidar(itens, catalogos)
        no_cargo = [e["titulo"] for e in por_escopo.get("CARGO-X", [])]
        no_comum = [e["titulo"] for e in por_escopo.get("_COMUM", [])]
        checar("obra_do_cargo_no_cargo", "Só do Cargo" in no_cargo, str(no_cargo))
        checar("obra_do_cargo_fora_do_comum", "Só do Cargo" not in no_comum,
               str(no_comum))


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
