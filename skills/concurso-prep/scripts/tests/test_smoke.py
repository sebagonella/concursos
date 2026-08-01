#!/usr/bin/env python3
"""
test_smoke.py - Testes de fumaça (smoke tests) dos scripts da skill concurso-prep.

Roda com pytest OU standalone (sem pytest instalado):
    pytest scripts/tests/            # se pytest disponível
    python scripts/tests/test_smoke.py   # fallback standalone

Cobre os pontos que já quebraram no passado (item 18 da revisão):
- slugify: acentos, separadores, modo órgão
- diff_editais: mantido/removido/novo/alterado + contenção de tokens + estrutural
- validate_output: estrutura UPPERCASE, .meta.json, soma de questões, wikilink irmão
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # .../scripts
sys.path.insert(0, str(ROOT))

import slugify  # noqa: E402
import diff_editais as de  # noqa: E402
import materia_id as mid  # noqa: E402
import edital_hash as eh  # noqa: E402
import migrar_meta as mm  # noqa: E402


# --------------------------------------------------------------------------- #
# slugify
# --------------------------------------------------------------------------- #
def test_slugify_cargo_acentos():
    assert slugify.slugify_cargo("EDAS Administração") == "EDAS-ADMINISTRACAO"


def test_slugify_cargo_separadores():
    assert slugify.slugify_cargo("Técnico Judiciário - Área") == "TECNICO-JUDICIARIO-AREA"


def test_slugify_orgao():
    assert slugify.slugify_orgao("Sedes/DF", 2026) == "SEDES_2026"


# --------------------------------------------------------------------------- #
# diff_editais
# --------------------------------------------------------------------------- #
def test_diff_mantido_novo_removido():
    v1 = {"M": ["alpha topico", "beta topico"]}
    v2 = {"M": ["alpha topico", "gamma topico"]}
    r = de.diff(v1, v2)
    assert r["resumo"]["n_mantidos"] == 1
    assert r["resumo"]["n_removidos"] == 1
    assert r["resumo"]["n_novos"] == 1


def test_diff_contencao_tokens_vira_alterado():
    # tema expandido deve ser 'alterado', não removido+novo
    v1 = {"M": ["analise swot e bsc"]}
    v2 = {"M": ["analise swot bsc e mapa estrategico"]}
    r = de.diff(v1, v2)
    assert r["resumo"]["n_alterados"] == 1
    assert r["resumo"]["n_removidos"] == 0


def test_diff_estrutural():
    m1 = {"vagas_ac": 3, "salario": "R$ 3.599,70",
          "estrutura_prova": {"objetiva": {"total_questoes": 100}, "discursiva": None}}
    m2 = {"vagas_ac": 23, "salario": "R$ 6.071,09",
          "estrutura_prova": {"objetiva": {"total_questoes": 120}, "discursiva": {"tipo": "x"}}}
    mud = de.diff_estrutural(m1, m2)
    campos = {m["campo"] for m in mud}
    assert "Vagas (AC imediatas)" in campos
    assert "Tem discursiva?" in campos
    assert "Total de questões" in campos


# --------------------------------------------------------------------------- #
# validate_output (via subprocess, testa o CLI de ponta a ponta)
# --------------------------------------------------------------------------- #
def _montar_vault(base: Path, total_q=100, est1=40, est2=60):
    b = base / "SEDES_2026"
    for sub in ["_COMUM/01-EDITAL", "_COMUM/04-MATERIAIS",
                "_COMUM/05-HISTORICO-CONCURSO", "_COMUM/06-SINERGIA",
                "EDAS/02-CRONOGRAMA", "EDAS/03-MAPAS-MATERIAS"]:
        (b / sub).mkdir(parents=True, exist_ok=True)
    (b / ".meta.json").write_text(json.dumps({
        "orgao": "SEDES", "ano": 2026, "modo": "oficial",
        "datas_chave": {"prova_data": "2099-09-06"},
        "estrutura_prova": {"objetiva": {"total_questoes": total_q}},
    }), encoding="utf-8")
    (b / "00-INDICE.md").write_text("# Indice\n[[00-INDICE]]\n", encoding="utf-8")
    # Indice por pasta: a Etapa 10.1 gera, e o fixture tem de espelhar a saida
    # real da skill — sem eles o fixture testava um vault que a skill nao produz.
    (b / "EDAS/03-MAPAS-MATERIAS/00-INDICE.md").write_text("# Mapas\n", encoding="utf-8")
    (b / "_COMUM/04-MATERIAIS/00-INDICE.md").write_text("# Materiais\n", encoding="utf-8")
    (b / "EDAS/03-MAPAS-MATERIAS/01.md").write_text(f"# A\n**Estimativa**: {est1} questoes\n", encoding="utf-8")
    (b / "EDAS/03-MAPAS-MATERIAS/02.md").write_text(f"# B\nEstimativa: {est2} questoes\n", encoding="utf-8")
    (b / "EDAS/02-CRONOGRAMA/cronograma-oficial.md").write_text("# crono\n", encoding="utf-8")
    return b


def _run_validate(path: Path):
    return subprocess.run(
        [sys.executable, str(ROOT / "validate_output.py"), str(path), "--json"],
        capture_output=True, text=True)


def test_validate_estrutura_ok():
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault(Path(d))
        r = _run_validate(b)
        out = json.loads(r.stdout)
        assert out["total_problemas"] == 0, out


def _montar_vault_com_materias(base: Path, com_mapa=True, materia_id=True):
    """Vault mínimo em que o `.meta.json` DECLARA as matérias — é o cruzamento
    que faltava: o validador nunca lia `materias[]`."""
    b = _montar_vault(base)
    meta = json.loads((b / ".meta.json").read_text(encoding="utf-8"))
    meta["materias"] = [{"nome": "Língua Portuguesa", "topicos": ["a"]}]
    meta["materias_por_cargo"] = {
        "EDAS": [{"nome": "Serviço Social", "topicos": ["b"]}]}
    (b / ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
    # Os mapas genericos do fixture base nao correspondem a materia nenhuma — a
    # skill nunca produz isso, e mante-los aqui fazia o teste de cobertura
    # conviver com dois mapas orfaos sem reclamar.
    for generico in ("01.md", "02.md"):
        (b / "EDAS/03-MAPAS-MATERIAS" / generico).unlink(missing_ok=True)
    fm_id = "materia_id: lingua-portuguesa\n" if materia_id else ""
    (b / "EDAS/03-MAPAS-MATERIAS/01-lingua-portuguesa.md").write_text(
        f"---\n{fm_id}---\n# Mapa\n**Estimativa**: 40 questoes\n", encoding="utf-8")
    if com_mapa:
        fm2 = "materia_id: servico-social\n" if materia_id else ""
        (b / "EDAS/03-MAPAS-MATERIAS/06-servico-social.md").write_text(
            f"---\n{fm2}---\n# Mapa\n**Estimativa**: 60 questoes\n", encoding="utf-8")
    return b


def test_validate_acusa_materia_sem_mapa():
    """O check que não existia. `check_soma_questoes` era estruturalmente cego a
    isto: soma os mapas que EXISTEM e aborta com INFO quando não acha nenhum, de
    modo que zero mapas gerados passava como OK."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault_com_materias(Path(d), com_mapa=False)
        out = json.loads(_run_validate(b).stdout)
        cob = out["resultados"]["cobertura_mapas"]
        assert any(i.startswith("FALTA") and "Serviço Social" in i for i in cob), cob
        assert out["total_problemas"] > 0


def test_validate_ok_quando_toda_materia_tem_mapa():
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault_com_materias(Path(d))
        cob = json.loads(_run_validate(b).stdout)["resultados"]["cobertura_mapas"]
        assert not [i for i in cob if not i.startswith("INFO")], cob


def test_validate_le_materias_por_cargo_tambem():
    """Nenhum dos dois lugares é completo sozinho: no SEDES `materias[]` só traz
    as de um cargo; no BB não há `materias_por_cargo` e faltam 3 matérias."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault_com_materias(Path(d))
        meta = json.loads((b / ".meta.json").read_text(encoding="utf-8"))
        assert len(vo.materias_do_meta(meta)) == 2   # 1 de cada lugar


def test_validate_sugere_candidato_por_palavra_nao_por_prefixo():
    """`fundamentos-suas` é o mapa certo de "Fundamentos, Organização, Gestão e
    Marcos Operacionais do SUAS" — compartilham só "suas". E prefixo casava
    lixo: sugeria `conhecimentos-df-…` para "Conhecimentos Específicos"."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault_com_materias(Path(d), materia_id=False)
        meta = json.loads((b / ".meta.json").read_text(encoding="utf-8"))
        meta["materias"] = [
            {"nome": "Fundamentos, Organização, Gestão e Marcos Operacionais do SUAS"},
            {"nome": "Conhecimentos Específicos — Agente Social"},
        ]
        meta.pop("materias_por_cargo")
        (b / ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (b / "EDAS/03-MAPAS-MATERIAS/04-fundamentos-suas.md").write_text(
            "---\n---\n# M\n", encoding="utf-8")
        cob = vo.check_cobertura_mapas(b, meta)
        suas = [i for i in cob if "SUAS" in i]
        assert suas and suas[0].startswith("AVISO"), suas
        assert "fundamentos-suas" in suas[0]
        agente = [i for i in cob if "Agente Social" in i]
        assert agente and agente[0].startswith("FALTA"), agente


def _montar_concurso_com_duplicatas(base: Path, iguais=True):
    """Dois cargos com o MESMO mapa — o defeito que a 1.4.0 corrige na origem."""
    b = base / "BB_2027"
    corpo = "---\nmateria: \"Português\"\n---\n# Mapa\n\n## 1. Crase\n\n- [ ] regra\n"
    for cargo in ("AGENTE-COMERCIAL", "AGENTE-DE-TECNOLOGIA"):
        d = b / cargo / "03-MAPAS-MATERIAS"
        d.mkdir(parents=True)
        txt = corpo if iguais else corpo + f"\n<!-- {cargo} -->\n" * 40
        (d / "01-lingua-portuguesa.md").write_text(txt, encoding="utf-8")
    # só um cargo cobra esta: não pode ser tocada
    (b / "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/08-vendas.md").write_text(
        corpo, encoding="utf-8")
    (b / "_COMUM").mkdir(parents=True, exist_ok=True)
    (b / "00-INDICE.md").write_text(
        "- [[AGENTE-COMERCIAL/03-MAPAS-MATERIAS/01-lingua-portuguesa|Português]]\n",
        encoding="utf-8")
    return b


def _rodar_consolidar(b, *extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "consolidar_mapas_comuns.py"),
         "--concurso-dir", str(b)] + list(extra), capture_output=True, text=True)


def test_consolidar_dry_run_nao_move():
    with tempfile.TemporaryDirectory() as d:
        b = _montar_concurso_com_duplicatas(Path(d))
        out = _rodar_consolidar(b)
        assert out.returncode == 0, out.stderr
        assert (b / "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/01-lingua-portuguesa.md").exists()
        assert not (b / "_COMUM/03-MAPAS-COMUNS").exists()


def test_consolidar_junta_duplicata_e_conserta_o_wikilink():
    """Mover sem reescrever o wikilink deixa o vault cheio de link quebrado —
    os índices apontam para o mapa pelo caminho completo."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_concurso_com_duplicatas(Path(d))
        out = _rodar_consolidar(b, "--aplicar")
        assert out.returncode == 0, out.stderr
        assert (b / "_COMUM/03-MAPAS-COMUNS/01-lingua-portuguesa.md").exists()
        for cargo in ("AGENTE-COMERCIAL", "AGENTE-DE-TECNOLOGIA"):
            assert not (b / cargo / "03-MAPAS-MATERIAS/01-lingua-portuguesa.md").exists()
        # matéria de um cargo só fica onde está
        assert (b / "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/08-vendas.md").exists()
        idx = (b / "00-INDICE.md").read_text(encoding="utf-8")
        assert "_COMUM/03-MAPAS-COMUNS/01-lingua-portuguesa" in idx
        assert "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/01-lingua" not in idx


def test_consolidar_recusa_quando_os_gemeos_divergem():
    """Conteúdos diferentes podem ser matérias diferentes com o mesmo nome de
    arquivo. Escolher um no palpite apagaria trabalho — vira pendência."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_concurso_com_duplicatas(Path(d), iguais=False)
        out = _rodar_consolidar(b, "--aplicar")
        assert out.returncode == 2
        assert "divergem" in out.stderr
        assert (b / "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/01-lingua-portuguesa.md").exists()
        assert (b / "AGENTE-DE-TECNOLOGIA/03-MAPAS-MATERIAS/01-lingua-portuguesa.md").exists()


def test_validate_soma_divergente():
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault(Path(d), total_q=100, est1=40, est2=30)  # soma 70 != 100
        r = _run_validate(b)
        out = json.loads(r.stdout)
        assert any("DIVERGENTE" in i for i in out["resultados"]["soma_questoes"])


# --------------------------------------------------------------------------- #
# runner standalone (sem pytest)
# --------------------------------------------------------------------------- #
# ---------------- validate_output: regressões ---------------- #
import validate_output as vo  # noqa: E402


def test_wikilink_regex_aceita_pipe_escapado_em_tabela():
    """Em tabela markdown o pipe do wikilink vem escapado (\\|); sem tratar isso,
    todo link em tabela virava LINK QUEBRADO — 74 falsos positivos num concurso real."""
    assert vo.WIKILINK_RE.search(r"[[pasta/arquivo\|rotulo]]").group(1) == "pasta/arquivo"
    assert vo.WIKILINK_RE.search("[[arquivo|rotulo]]").group(1) == "arquivo"
    assert vo.WIKILINK_RE.search("[[arquivo#secao]]").group(1) == "arquivo"
    assert vo.WIKILINK_RE.search("[[arquivo]]").group(1) == "arquivo"


def test_estimativa_nao_captura_meta_de_estudo():
    """O regex antigo casava as metas do checklist ('- [ ] 20 questoes de treino')
    e somava milhares, acusando divergencia em todo concurso."""
    assert vo.ESTIMATIVA_RE.search("**Estimativa**: 5 questoes")
    assert vo.ESTIMATIVA_RE.search("Estimativa: ~8 questoes")
    assert not vo.ESTIMATIVA_RE.search("## Meta\n- [ ] 20 questoes de treino")
    assert not vo.ESTIMATIVA_RE.search("- [ ] resolver 15 questoes")


def test_prova_data_aceita_date_do_yaml():
    """O .meta.yml legado e lido pelo YAML, que devolve datetime.date; o strptime
    so aceita str e quebrava o validador inteiro com TypeError."""
    from datetime import date, timedelta
    futuro = date.today() + timedelta(days=30)
    assert vo.check_cronograma_oficial(Path("."), {"datas_chave": {"prova_data": futuro}}) == []
    assert vo.check_cronograma_oficial(
        Path("."), {"datas_chave": {"prova_data": futuro.isoformat()}}) == []


def test_soma_questoes_por_cargo_em_concurso_multicargo():
    """Materias comuns valem para todos os cargos; somar todos juntos acusava
    divergencia em qualquer concurso multi-cargo."""
    with tempfile.TemporaryDirectory() as d:
        raiz = Path(d)
        for cargo, n in (("_COMUM", 40), ("CARGO-A", 30), ("CARGO-B", 30)):
            sub = raiz / cargo / "03-MAPAS-MATERIAS"
            sub.mkdir(parents=True)
            (sub / "m.md").write_text(f"**Estimativa**: {n} questoes\n", encoding="utf-8")
        # cada cargo soma 40 (comum) + 30 (proprio) = 70
        assert vo.check_soma_questoes(raiz, {"estrutura_prova": {"objetiva": {"total_questoes": 70}}}, 5.0) == []
        assert len(vo.check_soma_questoes(raiz, {"estrutura_prova": {"objetiva": {"total_questoes": 100}}}, 5.0)) == 2



def test_diff_aceita_pasta_do_concurso():
    """Passar a PASTA do concurso é o uso natural (é o que a skill tem em mãos);
    antes estourava IsADirectoryError e só aceitava o arquivo de metadata."""
    with tempfile.TemporaryDirectory() as d:
        for v, tops in (("v1", ["1 A", "2 B"]), ("v2", ["1 A", "2 B", "3 C"])):
            pasta = Path(d) / v
            pasta.mkdir()
            (pasta / ".meta.json").write_text(json.dumps(
                {"materias": [{"nome": "M", "topicos": tops}]}), encoding="utf-8")
        v1 = de.carregar_topicos(Path(d) / "v1")
        v2 = de.carregar_topicos(Path(d) / "v2")
        assert v1 == {"M": ["1 A", "2 B"]}
        assert len(v2["M"]) == 3



# --------------------------------------------------------------------------- #
# materia_id — identidade declarada e persistida (ADR de 2026-08-01)
# --------------------------------------------------------------------------- #
# Meta como o do SEDES: ids declarados em `materias[]` E em `materias_por_cargo`
# (nenhum dos dois é completo sozinho).
META_DECLARADO = {
    "materias": [
        {"nome": "Língua Portuguesa", "materia_id": "lingua-portuguesa"},
        {"nome": "Conhecimentos do DF, Política para Mulheres, Legislação e Primeiros Socorros",
         "materia_id": "conhecimentos-df-legislacao-primeiros-socorros"},
        {"nome": "Programas, Benefícios e Instrumentos Socioassistenciais do DF",
         "materia_id": "programas-beneficios-df"},
    ],
    "materias_por_cargo": {
        "ASSISTENTE-SOCIAL": [
            {"nome": "Direitos, Violações de Direitos e Vulnerabilidades Sociais",
             "materia_id": "direitos-violacoes-vulnerabilidades"},
        ]
    },
}


def test_materia_id_reusa_o_declarado_mesmo_com_titulo_reescrito():
    """O defeito que motivou o ADR: re-derivar o id a cada execução.

    O parser de 01/08 escreveu 'Conhecimentos do Distrito Federal...' onde o de
    15/07 tinha 'Conhecimentos do DF...'. Derivando, o id muda e os 58 assuntos
    aprofundados sob ele ficam órfãos. Resolvendo contra o declarado, não muda.
    """
    decl = mid.carregar_declarados(META_DECLARADO)
    got, origem, _ = mid.resolver(
        "Conhecimentos do Distrito Federal, Política para Mulheres, "
        "Legislação e Primeiros Socorros", decl)
    assert got == "conhecimentos-df-legislacao-primeiros-socorros", got
    assert origem == "similar", origem


def test_materia_id_le_tambem_o_formato_por_cargo():
    decl = mid.carregar_declarados(META_DECLARADO)
    got, origem, _ = mid.resolver(
        "Direitos, Violações de Direitos e Vulnerabilidades Sociais", decl)
    assert got == "direitos-violacoes-vulnerabilidades", got
    assert origem == "declarado", origem


def test_materia_id_e_estavel_entre_execucoes():
    decl = mid.carregar_declarados(META_DECLARADO)
    nomes = [m["nome"] for m in META_DECLARADO["materias"]]
    a = [mid.resolver(n, decl)[0] for n in nomes]
    b = [mid.resolver(n, decl)[0] for n in nomes]
    assert a == b == ["lingua-portuguesa",
                      "conhecimentos-df-legislacao-primeiros-socorros",
                      "programas-beneficios-df"], a


def test_materia_id_derivacao_nao_substitui_declaracao():
    """Trava a tese do ADR: derivar erra, e é por isso que se declara.

    Se um dia alguém 'melhorar' o propor_id a ponto de acertar sempre, este
    teste avisa — e a conversa volta a ser sobre persistir, não sobre derivar.
    """
    divergem = [m["nome"] for m in META_DECLARADO["materias"]
                if mid.propor_id(m["nome"]) != m["materia_id"]]
    assert len(divergem) >= 2, divergem


def test_materia_id_candidato_a_divisao_exige_virgula():
    """Sem exigir vírgula, a heurística marcava 3 das 20 matérias reais do
    SEDES — duas delas falso positivo."""
    heterogenea = ("Conhecimentos do Distrito Federal, Política para Mulheres, "
                   "Legislação e Primeiros Socorros")
    assert mid.candidato_a_divisao(heterogenea)[0] is True

    # coordenação só com "e": uma área com complemento composto, não uma lista
    for coesa in ("Noções de Saúde Mental e Uso de Álcool e Outras Drogas",
                  "População em Situação de Rua e Noções de Abordagem e Acolhimento"):
        assert mid.candidato_a_divisao(coesa)[0] is False, coesa

    # vírgulas, mas com complemento compartilhado no fim: aspectos de UMA área
    coesa_com_virgula = "Fundamentos, Organização, Gestão e Marcos Operacionais do SUAS"
    assert mid.candidato_a_divisao(coesa_com_virgula)[0] is False


# --------------------------------------------------------------------------- #
# validate_parsed — o contrato da Etapa 2
# --------------------------------------------------------------------------- #
def _parsed_valido():
    return {
        "orgao": "Secretaria X", "orgao_sigla": "SEDES", "ano": 2026,
        "banca": "Instituto Quadrix",
        "datas_chave": {"prova_data": "2026-09-06"},
        "cargos_validados": [{"nome_completo": "Agente Social", "sigla": "AGENTE-SOCIAL"}],
        "estrutura_prova": {"objetiva": {"total_questoes": 60}},
        "materias": [{
            "nome": "Língua Portuguesa", "materia_id": "lingua-portuguesa",
            "tipo": "gerais", "subitem_edital": "20.2.2.1",
            "topicos": ["1 Compreensão de textos."],
            "cargos_ids": ["AGENTE-SOCIAL"],
        }],
    }


def _validar_parsed(dado):
    import validate_parsed as vp
    schema = json.loads((ROOT.parent / "assets" / "schema-edital.json")
                        .read_text(encoding="utf-8"))
    erros = []
    vp._validar(dado, schema, "$", erros)
    return erros + vp.checagens_de_coerencia(dado)


def test_validate_parsed_aceita_saida_conforme():
    assert _validar_parsed(_parsed_valido()) == []


def test_validate_parsed_pega_cargo_sem_nenhuma_materia():
    """O defeito do BB: AGENTE-COMERCIAL validado e sem conteúdo programático
    em lugar nenhum do meta. Uma reconciliação perderia o cargo inteiro."""
    d = _parsed_valido()
    d["cargos_validados"].append({"nome_completo": "Cuidador", "sigla": "CUIDADOR-SOCIAL"})
    erros = _validar_parsed(d)
    assert any("CUIDADOR-SOCIAL" in e and "NENHUMA matéria" in e for e in erros), erros


def test_validate_parsed_pega_cargo_id_desconhecido():
    d = _parsed_valido()
    d["materias"][0]["cargos_ids"] = ["CARGO-FANTASMA"]
    erros = _validar_parsed(d)
    assert any("CARGO-FANTASMA" in e for e in erros), erros


def test_validate_parsed_pega_materia_id_repetido():
    d = _parsed_valido()
    d["materias"].append(dict(d["materias"][0]))
    erros = _validar_parsed(d)
    assert any("repetido" in e for e in erros), erros


def test_validate_parsed_exige_sigla_uppercase():
    d = _parsed_valido()
    d["cargos_validados"][0]["sigla"] = "Agente Social"
    erros = _validar_parsed(d)
    assert any("sigla" in e for e in erros), erros


def test_validate_parsed_exige_topicos_nao_vazios():
    """`topicos` vazio é matéria sem conteúdo programático — e o mapper não tem
    como ir buscar o literal em lugar nenhum (ele não lê arquivo)."""
    d = _parsed_valido()
    d["materias"][0]["topicos"] = []
    erros = _validar_parsed(d)
    assert any("topicos" in e for e in erros), erros


def test_validate_parsed_nunca_valida_menos_que_o_schema():
    """Anti-vacuidade: se o schema usar palavra-chave que o checador não
    implementa, isso é ERRO — não silêncio. É a lição do check_soma_questoes,
    que 'passava' no SEDES porque não casava nada."""
    import validate_parsed as vp
    schema = json.loads((ROOT.parent / "assets" / "schema-edital.json")
                        .read_text(encoding="utf-8"))
    assert vp.conferir_cobertura(schema) == []


# --------------------------------------------------------------------------- #
# validate_output — os checks que passavam sem verificar nada
# --------------------------------------------------------------------------- #
def test_estimativa_aceita_faixa():
    """Os 9 mapas do SEDES escrevem faixa ('~14 a 16 questões'). O regex antigo
    só casava inteiro, então não casava NENHUM — o check abortava com INFO e
    reportava OK. O concurso onde a soma 'passava' era o único onde ela nunca
    tinha sido calculada."""
    casos = {
        "**Estimativa**: ~14 a 16 questões (das 40)": (14, 16),
        "**Estimativa**: ~12–14 questões": (12, 14),
        "**Estimativa**: 8-10 questões": (8, 10),
        "Estimativa desta matéria**: ~10 a 12 questões": (10, 12),
        "**Estimativa**: 15 questões": (15, 15),
        "**Estimativa**: ~4 questões (faixa 3–5)": (4, 4),
    }
    for texto, esperado in casos.items():
        assert vo.faixa_estimada(texto) == esperado, (texto, vo.faixa_estimada(texto))


def test_estimativa_ainda_ignora_meta_de_treino():
    """A correção não pode reabrir o defeito de 1.3.1: o checklist de estudo
    ('- [ ] 20 questões de treino') somava 3769 numa prova de 70."""
    assert vo.faixa_estimada("- [ ] 20 questões de treino\n- [ ] 50 questões") is None


def test_soma_sem_estimativa_nao_e_info():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        mapas = root / "CARGO-X" / "03-MAPAS-MATERIAS"
        mapas.mkdir(parents=True)
        (mapas / "01-lingua.md").write_text("# Mapa\nsem estimativa aqui\n",
                                            encoding="utf-8")
        meta = {"estrutura_prova": {"objetiva": {"total_questoes": 60}}}
        issues = vo.check_soma_questoes(root, meta, 5.0)
        reais = [i for i in issues if not i.startswith("INFO:")]
        assert reais, issues
        assert any("SEM ESTIMATIVA" in i for i in reais), reais


def test_soma_com_faixa_aceita_total_dentro_do_intervalo():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        mapas = root / "CARGO-X" / "03-MAPAS-MATERIAS"
        mapas.mkdir(parents=True)
        (mapas / "01-a.md").write_text("**Estimativa**: 25 a 35 questões\n",
                                       encoding="utf-8")
        (mapas / "02-b.md").write_text("**Estimativa**: 25 a 35 questões\n",
                                       encoding="utf-8")
        meta = {"estrutura_prova": {"objetiva": {"total_questoes": 60}}}
        reais = [i for i in vo.check_soma_questoes(root, meta, 5.0)
                 if not i.startswith("INFO:")]
        assert reais == [], reais


def test_wikilink_para_fora_do_concurso_nao_e_falso_positivo():
    """Os 19 'links quebrados' do SEDES apontavam para PDFs que existem em
    40_RECURSOS/LIVROS/ — fora da pasta do concurso, dentro do vault."""
    with tempfile.TemporaryDirectory() as d:
        vault = Path(d)
        (vault / ".obsidian").mkdir()
        livro = vault / "40_RECURSOS" / "LIVROS"
        livro.mkdir(parents=True)
        (livro / "manual.pdf").write_bytes(b"%PDF-1.4 x")
        root = vault / "30_AREAS" / "CARREIRA" / "CONCURSOS" / "X_2026"
        root.mkdir(parents=True)
        (root / "nota.md").write_text(
            "ver [[40_RECURSOS/LIVROS/manual.pdf]]\n", encoding="utf-8")

        assert len(vo.check_wikilinks(root)) == 1          # sem vault: acusa
        assert vo.check_wikilinks(root, vault) == []       # com vault: resolve
        assert vo.achar_vault_root(root) == vault


def test_mapa_orfao_e_problema_nao_info():
    """Mapa sem matéria no meta é conteúdo programático perdido — foi assim que
    o BB ficou com as 3 matérias do AGENTE-COMERCIAL fora do .meta.json."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        mapas = root / "CARGO-X" / "03-MAPAS-MATERIAS"
        mapas.mkdir(parents=True)
        (mapas / "01-vendas.md").write_text(
            "---\nmateria_id: vendas-e-negociacao\n---\n", encoding="utf-8")
        meta = {"materias": [{"nome": "Língua Portuguesa",
                              "materia_id": "lingua-portuguesa"}]}
        issues = vo.check_cobertura_mapas(root, meta)
        orfao = [i for i in issues if "vendas" in i]
        assert orfao and not orfao[0].startswith("INFO:"), issues


def test_estrutura_exige_mapas_comuns_em_multicargo():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "00-INDICE.md").write_text("x", encoding="utf-8")
        (root / ".meta.json").write_text("{}", encoding="utf-8")
        for p in ("01-EDITAL", "04-MATERIAIS", "05-HISTORICO-CONCURSO", "06-SINERGIA"):
            (root / "_COMUM" / p).mkdir(parents=True)
        (root / "_COMUM" / "04-MATERIAIS" / "00-INDICE.md").write_text("x", encoding="utf-8")
        for c in ("CARGO-A", "CARGO-B"):
            (root / c).mkdir()
        issues = vo.check_structure(root)
        assert any("03-MAPAS-COMUNS" in i for i in issues), issues


# --------------------------------------------------------------------------- #
# diff_editais — reconciliação POR CARGO (item 8)
# --------------------------------------------------------------------------- #
def _meta_multicargo(topicos_servico_social):
    """Espelha o .meta.json real do SEDES: `materias[]` só traz as de um cargo e o
    resto vive em `materias_por_cargo`."""
    return {
        "modo": "oficial",
        "materias": [{"nome": "Língua Portuguesa", "topicos": ["1 Crase.", "2 Regência."]}],
        "materias_por_cargo": {
            "AGENTE-SOCIAL": [
                {"nome": "Língua Portuguesa", "topicos": ["1 Crase.", "2 Regência."]},
                {"nome": "Específicos — Agente", "topicos": ["1 Rede.", "2 PSB."]},
            ],
            "ASSISTENTE-SOCIAL": [
                {"nome": "Língua Portuguesa", "topicos": ["1 Crase.", "2 Regência."]},
                {"nome": "Específicos — Serviço Social", "topicos": topicos_servico_social},
            ],
        },
    }


def test_diff_enxerga_mudanca_em_cargo_que_nao_esta_em_materias():
    """O defeito: removi 3 tópicos da matéria do ASSISTENTE-SOCIAL no SEDES real e o
    diff reportou 0 removidos. Ele lia só `materias[]` — num concurso de 3 cargos,
    mudança em 2 deles passava em silêncio."""
    with tempfile.TemporaryDirectory() as d:
        v1, v2 = Path(d) / "v1.json", Path(d) / "v2.json"
        v1.write_text(json.dumps(_meta_multicargo(["1 Ética.", "2 Pesquisa.", "3 Estado."])),
                      encoding="utf-8")
        v2.write_text(json.dumps(_meta_multicargo(["1 Ética."])), encoding="utf-8")
        r = de.diff_por_cargo(de.carregar_por_cargo(v1), de.carregar_por_cargo(v2))
        assert r["resumo"]["n_removidos"] == 2, r["resumo"]
        assert r["por_cargo"]["ASSISTENTE-SOCIAL"]["resumo"]["n_removidos"] == 2
        assert r["por_cargo"]["AGENTE-SOCIAL"]["resumo"]["n_removidos"] == 0


def test_diff_avisa_cargo_criado_ou_extinto():
    with tempfile.TemporaryDirectory() as d:
        v1, v2 = Path(d) / "v1.json", Path(d) / "v2.json"
        m1 = _meta_multicargo(["1 Ética."])
        m2 = json.loads(json.dumps(m1))
        del m2["materias_por_cargo"]["AGENTE-SOCIAL"]
        m2["materias_por_cargo"]["CUIDADOR-SOCIAL"] = [
            {"nome": "Específicos — Cuidador", "topicos": ["1 Acolhimento."]}]
        v1.write_text(json.dumps(m1), encoding="utf-8")
        v2.write_text(json.dumps(m2), encoding="utf-8")
        r = de.diff_por_cargo(de.carregar_por_cargo(v1), de.carregar_por_cargo(v2))
        assert r["cargos_removidos"] == ["AGENTE-SOCIAL"], r["cargos_removidos"]
        assert r["cargos_novos"] == ["CUIDADOR-SOCIAL"], r["cargos_novos"]


def test_diff_le_cargos_ids_do_schema_novo():
    with tempfile.TemporaryDirectory() as d:
        v = Path(d) / "v.json"
        v.write_text(json.dumps({"materias": [
            {"nome": "LP", "topicos": ["a"], "cargos_ids": ["A", "B"]},
            {"nome": "Esp", "topicos": ["b"], "cargos_ids": ["B"]}]}), encoding="utf-8")
        pc = de.carregar_por_cargo(v)
        assert set(pc) == {"A", "B"}
        assert set(pc["B"]) == {"LP", "Esp"} and set(pc["A"]) == {"LP"}


def test_diff_estrutural_acha_vagas_fora_da_raiz():
    """Descoberto rodando a reconciliação ponta a ponta: mudar
    `cargo.vagas_imediatas` de 133 para 150 no SEDES não produzia mudança nenhuma.
    O diff olhava só a raiz, e o `.meta.json` do SEDES guarda vagas e salário em
    `cargo.*` — justamente o que retificação mexe (B.4)."""
    m1 = {"cargo": {"vagas_imediatas": 133, "remuneracao": 4762.97}}
    m2 = {"cargo": {"vagas_imediatas": 150, "remuneracao": 4762.97}}
    campos = {m["campo"] for m in de.diff_estrutural(m1, m2)}
    assert "Vagas (AC imediatas)" in campos, campos
    assert "Salário" not in campos, campos


def test_diff_estrutural_por_cargo():
    """Retificação pode mexer nas vagas de UM cargo; o número agregado esconde."""
    m1 = {"cargos_multi": [{"sigla": "A", "vagas_total": 10},
                           {"sigla": "B", "vagas_total": 20}]}
    m2 = {"cargos_multi": [{"sigla": "A", "vagas_total": 10},
                           {"sigla": "B", "vagas_total": 35}]}
    campos = {m["campo"] for m in de.diff_estrutural(m1, m2)}
    assert "Vagas totais [B]" in campos, campos
    assert "Vagas totais [A]" not in campos, campos


def test_diff_cabecalho_muda_entre_caso_A_e_B():
    """O B.5 manda ajustar o cabeçalho na retificação; ele era fixo em
    'Previsto (V1) vs Oficial (V2)' em qualquer caso."""
    assert "Previsto" in de.titulo_do_caso({"modo": "previsto"}, {"modo": "oficial"})
    assert "Retificado" in de.titulo_do_caso({"modo": "oficial"}, {"modo": "oficial"})


# --------------------------------------------------------------------------- #
# edital_hash — a regra que não tinha executor
# --------------------------------------------------------------------------- #
def test_edital_hash_e_do_texto_e_reproduzivel():
    assert eh.hash_texto("Art. 1º\nTexto.") == eh.hash_texto("Art. 1º\nTexto.")


def test_edital_hash_ignora_ruido_irrelevante():
    """Hash que muda com CRLF ou espaço no fim de linha acusa retificação onde não
    houve — e o R.0.2 decide reconciliação com base nele."""
    base = "Art. 1º\nTexto da lei."
    assert eh.hash_texto(base) == eh.hash_texto("Art. 1º\r\nTexto da lei.  ")
    assert eh.hash_texto(base) == eh.hash_texto(base + "\n\n\n")


def test_edital_hash_distingue_texto_de_bytes():
    """O SEDES gravou o hash dos BYTES do PDF onde o SKILL manda gravar o do TEXTO.
    São valores diferentes, e confundi-los faz o R.0.2 nunca reconhecer 'idêntico'."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "e.txt"
        # CRLF e linhas em branco no fim: e onde a canonicalizacao faz efeito e o
        # hash do texto deixa de ser o dos bytes. Num PDF a diferenca e sempre
        # grande; aqui basta que exista.
        p.write_bytes("Art. 1º\r\nTexto.  \r\n\r\n".encode("utf-8"))
        r = eh.hashes_do_edital(p)
        assert r["edital_hash"] == eh.hash_texto("Art. 1º\nTexto."), r["edital_hash"]
        assert r["edital_hash"] != eh.hash_bytes(p)


# --------------------------------------------------------------------------- #
# Etapa 9b — títulos por cargo
# --------------------------------------------------------------------------- #
def _vault_titulos(base: Path, meta_extra: dict, com_arquivo: list[str]):
    root = base / "X_2026"
    for c in ("EDAS-SERVICO-SOCIAL", "TDAS-AGENTE-SOCIAL"):
        (root / c).mkdir(parents=True)
        if c in com_arquivo:
            (root / c / "08-TITULOS.md").write_text("# Títulos\n", encoding="utf-8")
    meta = {"estrutura_prova": {"objetiva": {"total_questoes": 60}}}
    meta.update(meta_extra)
    return root, meta


def test_titulos_acusa_cargo_elegivel_sem_arquivo():
    with tempfile.TemporaryDirectory() as d:
        root, meta = _vault_titulos(
            Path(d),
            {"estrutura_prova_por_cargo": {
                "EDAS-SERVICO-SOCIAL": {"titulos": {"presente": True}},
                "TDAS-AGENTE-SOCIAL": {"titulos": {"presente": False}}}},
            com_arquivo=[])
        issues = vo.check_titulos(root, meta)
        assert any("EDAS-SERVICO-SOCIAL" in i and i.startswith("FALTA") for i in issues), issues
        assert not any("TDAS" in i for i in issues), issues


def test_titulos_acusa_meta_incoerente():
    """O caso real do SEDES: o ASSISTENTE-SOCIAL (que é EDAS) tem 08-TITULOS.md e o
    meta grava um único `titulos.presente: false` com a ressalva em prosa."""
    with tempfile.TemporaryDirectory() as d:
        root, meta = _vault_titulos(
            Path(d),
            {"estrutura_prova": {"objetiva": {"total_questoes": 60},
                                 "titulos": {"presente": False,
                                             "obs": "exclusiva para EDAS"}}},
            com_arquivo=["EDAS-SERVICO-SOCIAL"])
        issues = vo.check_titulos(root, meta)
        assert any("META INCOERENTE" in i and "EDAS-SERVICO-SOCIAL" in i
                   for i in issues), issues


def test_titulos_ok_quando_por_cargo_esta_correto():
    with tempfile.TemporaryDirectory() as d:
        root, meta = _vault_titulos(
            Path(d),
            {"estrutura_prova_por_cargo": {
                "EDAS-SERVICO-SOCIAL": {"titulos": {"presente": True}},
                "TDAS-AGENTE-SOCIAL": {"titulos": {"presente": False}}}},
            com_arquivo=["EDAS-SERVICO-SOCIAL"])
        assert vo.check_titulos(root, meta) == []


def test_template_titulos_existe_e_tem_o_que_a_etapa_promete():
    tpl = (ROOT.parent / "assets" / "templates" / "titulos.md.tpl").read_text(
        encoding="utf-8")
    for campo in ("{{QUADRO_ALINEAS}}", "{{MAX_PONTOS}}", "{{REGRAS_ENTREGA}}",
                  "{{CHECKLIST_EXPERIENCIA}}", "tipo: documentacao"):
        assert campo in tpl, campo


def test_log_de_validacao_vai_para_a_subpasta_do_concurso():
    """Item 15: log por concurso. Gravando na raiz de `.logs/`, o vault real acumulou
    43 `validacao-*.json` soltos, sem como saber de qual concurso era cada um."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault(Path(d))
        (Path(d) / ".logs").mkdir()
        _run_validate(b)
        assert list((Path(d) / ".logs" / "SEDES_2026").glob("validacao-*.json"))
        assert not list((Path(d) / ".logs").glob("validacao-*.json"))


# --------------------------------------------------------------------------- #
# migrar_meta — a correção cirúrgica do .meta.json já gerado
# --------------------------------------------------------------------------- #
def test_limpar_texto_pdf_tira_rodape_do_meio_do_topico():
    """O número da página vem numa linha própria antes do form feed e, ao juntar,
    entra NO MEIO do tópico: 'ambiente Linux (SUSE 34 SLES 15 SP2)'."""
    bruto = "ambiente Linux (SUSE\n\n                    34\n\fSLES 15 SP2) 2 - Edição"
    assert "34" not in mm.limpar_texto_pdf(bruto)
    assert "SUSE" in mm.limpar_texto_pdf(bruto) and "SLES" in mm.limpar_texto_pdf(bruto)


def test_topicos_do_edital_para_no_anexo_seguinte():
    """O último tópico de 'Vendas e Negociação' engolia 'ANEXO IV - CRONOGRAMA',
    porque o cabeçalho do anexo usa travessão e não dois-pontos."""
    texto = ("VENDAS E NEGOCIAÇÃO: 1 - Primeiro topico. 2 - Segundo topico.\n"
             "ANEXO IV - CRONOGRAMA\n outra coisa qualquer\n")
    t = mm.topicos_do_edital(texto, "Vendas e Negociação")
    assert len(t) == 2, t
    assert "ANEXO" not in t[-1], t[-1]


def test_estrutura_por_cargo_sai_de_cargos_multi():
    meta = {"cargos_multi": [
        {"sigla": "TDAS-A", "titulos": False, "discursiva": "redação"},
        {"sigla": "EDAS-B", "titulos": True, "discursiva": "estudo de caso"}]}
    saida, _ = mm.corr_estrutura_por_cargo(meta)
    assert saida["EDAS-B"]["titulos"]["presente"] is True
    assert saida["TDAS-A"]["titulos"]["presente"] is False


def test_estrutura_por_cargo_nao_grava_quando_nao_diverge():
    """Se todos os cargos têm a mesma estrutura, o campo agregado basta."""
    meta = {"cargos_multi": [{"sigla": "A", "titulos": False, "discursiva": "redação"},
                             {"sigla": "B", "titulos": False, "discursiva": "redação"}]}
    assert mm.corr_estrutura_por_cargo(meta)[0] is None


def test_cargos_ids_do_formato_do_sedes_e_do_bb():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "A").mkdir()
        (p / "B").mkdir()
        # SEDES: escopo vem de materias_por_cargo
        meta = {"cargos_multi": [{"sigla": "A"}, {"sigla": "B"}],
                "materias": [{"nome": "Português", "topicos": ["x"]}],
                "materias_por_cargo": {"A": [{"nome": "Português"}],
                                       "B": [{"nome": "Português"}]}}
        saida, _ = mm.corr_cargos_ids(meta, p)
        assert saida[0]["cargos_ids"] == ["A", "B"], saida

        # BB: específica vem de cargos_gerados[].especificos; o resto é de todos
        meta2 = {"cargos_gerados": [{"slug": "A", "especificos": [{"nome": "Vendas"}]},
                                    {"slug": "B", "especificos": [{"nome": "TI"}]}],
                 "materias": [{"nome": "Vendas", "topicos": ["x"]},
                              {"nome": "Português", "topicos": ["y"]}]}
        saida2, _ = mm.corr_cargos_ids(meta2, p)
        assert saida2[0]["cargos_ids"] == ["A"], saida2[0]
        assert saida2[1]["cargos_ids"] == ["A", "B"], saida2[1]


def test_comum_significa_mais_de_um_nao_todos():
    """`fundamentos-suas` vale para 2 dos 3 cargos do SEDES e mora em _COMUM — a
    Etapa 5 manda gravar ali mesmo. Tratar _COMUM como 'todos' dava falso alarme."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        for c in ("A", "B", "C"):
            (p / c).mkdir()
        (p / "_COMUM" / "03-MAPAS-COMUNS").mkdir(parents=True)
        (p / "_COMUM" / "03-MAPAS-COMUNS" / "01-suas.md").write_text(
            "---\nmateria_id: suas\n---\n", encoding="utf-8")
        meta = {"cargos_multi": [{"sigla": "A"}, {"sigla": "B"}, {"sigla": "C"}],
                "materias": [{"nome": "SUAS", "materia_id": "suas", "topicos": ["x"]}],
                "materias_por_cargo": {"A": [{"nome": "SUAS"}], "B": [{"nome": "SUAS"}]}}
        saida, pend = mm.corr_cargos_ids(meta, p)
        assert saida[0]["cargos_ids"] == ["A", "B"], saida
        assert pend == [], pend


def test_materia_extraida_sem_mapa_para_conferir_vira_pendencia():
    """Segunda fonte ausente não pode virar silêncio — é a mesma armadilha do check
    que 'passava' porque não encontrava nada."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "_COMUM" / "01-EDITAL").mkdir(parents=True)
        assert mm.topicos_do_mapa(p, "Inexistente") == []


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    falhas = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            falhas += 1
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            falhas += 1
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - falhas}/{len(fns)} testes passaram.")
    return falhas


if __name__ == "__main__":
    sys.exit(1 if _run_standalone() else 0)
