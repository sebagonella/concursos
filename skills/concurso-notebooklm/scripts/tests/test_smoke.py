#!/usr/bin/env python3
"""
test_smoke.py - Smoke tests da skill concurso-notebooklm (camada de contrato).

Roda com pytest ou standalone:
    python scripts/tests/test_smoke.py

A suíte inteira passa SEM a `notebooklm-py` instalada — o `install.sh` roda os
testes logo depois de copiar a skill, então depender da biblioteca aqui quebraria a
instalação de quem só quer o modo manual. Nada neste arquivo importa `notebooklm`.

Os pacotes usados como fixture são gerados pelo `notebooklm_pack.py` DE VERDADE,
nunca escritos à mão: fixture que inventa o que o gerador não produz é teste que se
autoconfirma — já aconteceu duas vezes neste repo.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pacote as pac_mod          # noqa: E402
import plano as plano_mod         # noqa: E402


# --------------------------------------------------------------------------- #
# fixture: pacote gerado pela concurso-aprofunda real
# --------------------------------------------------------------------------- #
def _gerador() -> Path | None:
    """O `notebooklm_pack.py` da skill irmã, quando as duas convivem.

    parents: [0]=tests [1]=scripts [2]=concurso-notebooklm [3]=skills [4]=repo.
    Mesmo precedente de `test_copia_do_aprofundamento_id_nao_divergiu`.
    """
    aqui = Path(__file__).resolve()
    rel = Path("concurso-aprofunda") / "scripts" / "notebooklm_pack.py"
    for cand in (aqui.parents[3] / rel, aqui.parents[4] / "skills" / rel):
        if cand.exists():
            return cand
    return None


def _montar_pacote(d: Path, com_leis: bool = False) -> Path | None:
    """Gera um pacote de verdade e devolve o caminho. None se a irmã não existe."""
    ger = _gerador()
    if ger is None:
        return None
    pasta = d / "assuntos" / "populacao-situacao-rua" / "padrao--dec-7053"
    pasta.mkdir(parents=True, exist_ok=True)
    corpo = "O art. 1º do Decreto 7053 institui a política.\n"
    (pasta / "populacao-situacao-rua--padrao--dec-7053--X_2026.md").write_text(
        '---\ntitle: "População em Situação de Rua"\n'
        'aprofundamento: "padrao--dec-7053"\nnivel: padrao\n'
        'fontes: "Decreto 7.053/2009"\nstatus: concluido\n---\n' + corpo,
        encoding="utf-8")
    cmd = [sys.executable, str(ger), "--assuntos-dir", str(d / "assuntos"),
           "--concurso", "X_2026", "--materia", "Específicos"]
    if com_leis:
        leis = d / "leis"
        leis.mkdir(exist_ok=True)
        (leis / "decreto-7053-2009-populacao-rua.pdf").write_bytes(b"%PDF-1.4\n")
        cmd += ["--leis-dir", str(leis)]
    subprocess.run(cmd, capture_output=True, text=True)
    return pasta / "_fonte-notebooklm.md"


# --------------------------------------------------------------------------- #
# pacote.py — leitura
# --------------------------------------------------------------------------- #
def test_le_o_nome_do_notebook_e_os_arquivos_do_frontmatter():
    """São contrato, não prosa: extrair nome de arquivo de texto corrido foi o que
    fez o roteiro do mapa mental e o do report chegarem vazios ao site."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        base = "populacao-situacao-rua--padrao--dec-7053--X_2026"
        assert p.nome_notebook == "X_2026 — População em Situação de Rua — padrao--dec-7053", \
            p.nome_notebook
        assert p.arquivo_de("podcast") == f"podcast-{base}.m4a", "arquivo do podcast"
        assert p.arquivo_de("video") == f"video-{base}.mp4", "arquivo do vídeo"
        assert p.arquivo_de("report") == f"report-{base}.md", "arquivo do report"
        assert p.status == "nao-criado" and p.url == "" and p.notebook_id == ""


def test_extrai_um_prompt_por_geravel():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        assert set(p.prompts) == {"podcast", "mapa_mental", "video", "report"}, p.prompts
        for chave, texto in p.prompts.items():
            assert texto.strip(), f"{chave} com prompt vazio"


def test_o_prompt_usado_e_o_do_pacote_byte_a_byte():
    """Reescrever o prompt aqui criaria duas versões do mesmo texto: a que o usuário
    copia no site e a que a automação envia — e elas divergiriam em silêncio."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        bruto = caminho.read_text(encoding="utf-8")
        assert p.prompts["podcast"] in bruto
        # e ancora na nota do vault, como a concurso-aprofunda garante
        assert "populacao-situacao-rua--padrao--dec-7053--X_2026.md" in p.prompts["podcast"]


def test_comentario_do_template_nao_vira_campo():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        assert not any(k.startswith("#") for k in p.campos), p.campos


def test_pacote_sem_frontmatter_falha_alto():
    """Seguir em frente criaria um notebook sem saber para qual assunto."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "_fonte-notebooklm.md"
        f.write_text("# só um título\n", encoding="utf-8")
        try:
            pac_mod.ler(f)
        except ValueError:
            return
        raise AssertionError("deveria ter recusado o pacote sem frontmatter")


# --------------------------------------------------------------------------- #
# pacote.py — fontes
# --------------------------------------------------------------------------- #
def test_fonte_ausente_vira_pendencia_nomeada():
    """Nunca subir de menos em silêncio: o notebook ficaria sem a lei e ninguém veria."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d), com_leis=True)
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        existentes, faltando = pac_mod.resolver_fontes(p, leis_dir=None)
        assert len(existentes) == 1, "a nota do assunto está ao lado do pacote"
        assert faltando == ["decreto-7053-2009-populacao-rua.pdf"], faltando


def test_fontes_resolvem_com_a_pasta_de_leis():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        caminho = _montar_pacote(d, com_leis=True)
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        existentes, faltando = pac_mod.resolver_fontes(p, leis_dir=d / "leis")
        assert not faltando, faltando
        assert len(existentes) == 2 and all(x.is_file() for x in existentes)


# --------------------------------------------------------------------------- #
# pacote.py — escrita
# --------------------------------------------------------------------------- #
def test_gravar_campos_preserva_o_resto_byte_a_byte():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        antes = caminho.read_text(encoding="utf-8")
        pac_mod.gravar_campos(caminho, {"notebooklm_status": "criado"})
        depois = caminho.read_text(encoding="utf-8")
        assert depois != antes
        assert 'notebooklm_status: "criado"' in depois
        # o corpo (tudo depois do frontmatter) não pode ter mudado
        assert antes.split("\n---\n", 1)[1] == depois.split("\n---\n", 1)[1]


def test_gravar_campos_acrescenta_chave_que_ainda_nao_existe():
    """`notebooklm_id` nasce na primeira execução da automação."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac_mod.gravar_campos(caminho, {"notebooklm_id": "abc-123"})
        assert pac_mod.ler(caminho).notebook_id == "abc-123"


def test_gravar_campos_nao_deixa_arquivo_temporario():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac_mod.gravar_campos(caminho, {"notebooklm_status": "completo"})
        assert not list(caminho.parent.glob(".tmp-*")), "sobrou temporário"


def test_o_que_a_automacao_grava_sobrevive_a_regeracao_do_pacote():
    """O laço completo: a automação escreve, a concurso-aprofunda regera, e o dado
    continua lá. É o contrato que a 0.7.1 da skill irmã passou a garantir."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        caminho = _montar_pacote(d)
        if caminho is None:
            return
        pac_mod.gravar_campos(caminho, {
            "notebooklm_id": "abc-123",
            "notebooklm_url": plano_mod.url_do_notebook("abc-123"),
            "notebooklm_status": "completo"})
        _montar_pacote(d)                      # regera por cima
        p = pac_mod.ler(caminho)
        assert p.notebook_id == "abc-123", "o id do notebook"
        assert p.url.endswith("/abc-123"), "a URL"
        assert p.status == "completo", "o status"


# --------------------------------------------------------------------------- #
# plano.py — o que gerar
# --------------------------------------------------------------------------- #
def test_default_e_so_o_podcast_deep_dive():
    assert plano_mod.parse_midias(None) == [("podcast", "deep-dive")]


def test_nada_gera_zero_midias():
    assert plano_mod.parse_midias("nada") == []


def test_tudo_cobre_os_geraveis_automatizados():
    tipos = {t for t, _ in plano_mod.parse_midias("tudo")}
    assert tipos == {"podcast", "video", "report"}
    assert "mapa_mental" not in tipos, "mapa mental está fora da automação"


def test_variante_explicita_vence_o_padrao():
    assert plano_mod.parse_midias("podcast:debate,report") == [
        ("podcast", "debate"), ("report", "custom")]


def test_mapa_mental_e_recusado_com_a_razao():
    """Recusar explicando é diferente de ignorar: o usuário pediu e merece saber
    por que não vai acontecer."""
    try:
        plano_mod.parse_midias("mapa-mental")
    except plano_mod.MidiaInvalida as e:
        assert "JSON" in str(e), "a razão técnica precisa aparecer"
        assert "à mão" in str(e), "e o caminho alternativo também"
        return
    raise AssertionError("mapa mental deveria ser recusado")


def test_geravel_desconhecido_lista_os_validos():
    try:
        plano_mod.parse_midias("infografico")
    except plano_mod.MidiaInvalida as e:
        assert "podcast" in str(e) and "video" in str(e), str(e)
        return
    raise AssertionError("deveria recusar gerável desconhecido")


def test_variante_desconhecida_lista_as_validas():
    try:
        plano_mod.parse_midias("podcast:epico")
    except plano_mod.MidiaInvalida as e:
        assert "deep-dive" in str(e), str(e)
        return
    raise AssertionError("deveria recusar variante desconhecida")


def test_geravel_repetido_e_erro():
    try:
        plano_mod.parse_midias("podcast:brief,podcast:debate")
    except plano_mod.MidiaInvalida:
        return
    raise AssertionError("pedir o mesmo gerável duas vezes deveria falhar")


def test_arquivo_presente_nao_regera():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        (p.pasta / p.arquivo_de("podcast")).write_bytes(b"x")
        tarefas, pulados = plano_mod.planejar(p, [("podcast", "deep-dive")])
        assert not tarefas
        assert pulados and pulados[0][0] == "podcast"


def test_forcar_regera_mesmo_com_arquivo():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        (p.pasta / p.arquivo_de("podcast")).write_bytes(b"x")
        tarefas, _ = plano_mod.planejar(p, [("podcast", "deep-dive")], forcar=True)
        assert len(tarefas) == 1


def test_extensao_diferente_da_declarada_ainda_conta_como_feito():
    """O container real do download pode não ser o declarado. Regerar por causa
    disso queimaria quota do dia à toa."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        nome = p.arquivo_de("podcast").replace(".m4a", ".mp3")
        (p.pasta / nome).write_bytes(b"x")
        tarefas, pulados = plano_mod.planejar(p, [("podcast", "deep-dive")])
        assert not tarefas and pulados


def test_tarefa_carrega_o_nome_do_arquivo_e_o_prompt():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        p = pac_mod.ler(caminho)
        tarefas, _ = plano_mod.planejar(p, [("podcast", "deep-dive")])
        t = tarefas[0]
        assert t.arquivo == p.arquivo_de("podcast")
        assert t.prompt == p.prompts["podcast"]
        assert t.rotulo == "podcast:deep-dive"


# --------------------------------------------------------------------------- #
# plano.py — URL e container
# --------------------------------------------------------------------------- #
def test_url_e_derivada_do_id_sem_rede():
    assert plano_mod.url_do_notebook("abc") == \
        "https://notebooklm.google.com/notebook/abc"
    assert plano_mod.url_do_notebook("") == ""


def test_container_sai_dos_bytes_nao_da_extensao():
    """O site casa prefixo E extensão: nome errado não vira outro tipo, vira
    INVISÍVEL — que é o pior desfecho, porque é silencioso."""
    assert plano_mod.container_dos_bytes(b"\x00\x00\x00\x18ftypM4A ") == ".m4a"
    # o cabeçalho REAL do NotebookLM, observado em 2026-07-31: brand `dash`,
    # fMP4 auto-contido com AAC. Não é o `M4A ` que se esperaria — e é por isso
    # que a checagem olha o `ftyp` na posição 4, não a brand.
    assert plano_mod.container_dos_bytes(b"\x00\x00\x00\x18ftypdash\x00\x00\x00\x00") == ".m4a"
    assert plano_mod.container_dos_bytes(b"ID3\x04\x00\x00") == ".mp3"
    assert plano_mod.container_dos_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ") == ".wav"
    assert plano_mod.container_dos_bytes(b"OggS\x00\x02\x00\x00") == ".ogg"
    assert plano_mod.container_dos_bytes(b"<!DOCTYPE html><html>") == ".html"
    assert plano_mod.container_dos_bytes(b"qualquer lixo") == ""


def test_extensoes_do_podcast_sao_as_que_o_site_reconhece():
    """Guarda cruzada: se a concurso-publica mudar o catálogo, isto avisa aqui em
    vez de o arquivo sumir da página."""
    aqui = Path(__file__).resolve()
    rel = Path("concurso-publica") / "scripts" / "site_collector.py"
    fonte = next((c for c in (aqui.parents[3] / rel, aqui.parents[4] / "skills" / rel)
                  if c.exists()), None)
    if fonte is None:
        return
    txt = fonte.read_text(encoding="utf-8")
    import re
    m = re.search(r'"podcast":\s*\(\([^)]*\),\s*\(([^)]*)\)', txt)
    assert m, "não achei o catálogo de mídias da concurso-publica"
    aceitas = set(re.findall(r'"(\.[a-z0-9]+)"', m.group(1)))
    for ext in (".m4a", ".mp3", ".wav", ".ogg"):
        assert ext in aceitas, f"{ext} deixou de ser reconhecida como podcast"


# --------------------------------------------------------------------------- #
# porta.py — a fronteira, e o dublê que a espelha
# --------------------------------------------------------------------------- #
import inspect                    # noqa: E402
import porta as porta_mod         # noqa: E402
import executor as exe_mod        # noqa: E402


def test_dublê_tem_a_mesma_assinatura_do_protocolo():
    """Dublê e interface não podem divergir sem alguém ver — é o mesmo princípio do
    fixture que espelha o gerador real."""
    for nome, metodo in inspect.getmembers(porta_mod.PortaNotebookLM, inspect.isfunction):
        if nome.startswith("_"):
            continue
        real = getattr(porta_mod.PortaFalsa, nome, None)
        assert real is not None, f"PortaFalsa não implementa {nome}"
        esperado = list(inspect.signature(metodo).parameters)
        obtido = list(inspect.signature(real).parameters)
        assert esperado == obtido, f"{nome}: {esperado} != {obtido}"


def test_fonte_faltando_muda_o_codigo_de_saida():
    """Notebook criado sem a lei declarada não pode sair 0.

    A "pendência nomeada" ia só para o stdout: não mudava o exit code, não era
    gravada no vault e não bloqueava a geração. Quem automatiza olha o código de
    saída — e ele dizia que estava tudo bem.
    """
    rel = exe_mod.Relatorio(fontes_faltando=["lei-8742-1993-loas.pdf"])
    assert rel.codigo_saida == 2, rel.codigo_saida
    # quota tem precedência: é o único caso em que "rode amanhã" é a instrução
    rel2 = exe_mod.Relatorio(fontes_faltando=["x.pdf"], sem_quota=[("podcast", "teto")])
    assert rel2.codigo_saida == 4, rel2.codigo_saida


def test_nlm_run_usa_o_codigo_de_saida_do_relatorio():
    """`codigo_saida` era CÓDIGO MORTO: os dois comandos remontavam o exit à mão.

    `nlm_run.py` fazia `return 2 if falhou else 0` e `nlm_coleta.py` idem, com a
    quota remontada em outro ponto. Corrigir só a propriedade não mudaria nada —
    é preciso que os `main()` a consultem, senão a regra vive num lugar que
    ninguém lê.
    """
    fonte = (ROOT / "nlm_run.py").read_text(encoding="utf-8")
    assert "codigo_saida" in fonte, "nlm_run.py não consulta o codigo_saida"
    fonte_c = (ROOT / "nlm_coleta.py").read_text(encoding="utf-8")
    assert "codigo_saida" in fonte_c, "nlm_coleta.py não consulta o codigo_saida"


def test_fontes_subidas_e_faltando_sao_gravadas_no_pacote():
    """Sem isto, não há como saber com que fontes um podcast foi feito.

    O relatório morria no stdout. Os campos vão com o prefixo `notebooklm_` de
    propósito: `herdar_campos` herda por prefixo, então sobrevivem a toda
    regeração futura do pacote sem código novo.
    """
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d), com_leis=True)
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa()
        exe_mod.executar(pac, [], porta, leis_dir=None)
        txt = caminho.read_text(encoding="utf-8")
        assert "notebooklm_fontes_subidas:" in txt, txt[:400]
        assert "notebooklm_fontes_faltando:" in txt, txt[:400]
        assert "decreto-7053-2009-populacao-rua.pdf" in txt, "a pendência não foi gravada"


def test_notebook_existente_nao_e_recriado():
    """Reexecutar sobre 66 assuntos criaria 66 duplicados e queimaria a quota."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac_mod.gravar_campos(caminho, {"notebooklm_id": "ja-existe"})
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa()
        rel = exe_mod.executar(pac, [], porta)
        assert rel.notebook_id == "ja-existe"
        assert not any(m == "criar_notebook" for m, _ in porta.chamadas)


def test_fonte_ja_no_notebook_nao_e_ressubida():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        caminho = _montar_pacote(d, com_leis=True)
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa()
        exe_mod.executar(pac, [], porta, leis_dir=d / "leis")
        primeira = [k for k, _ in porta.chamadas].count("subir_fonte")
        assert primeira == 2, primeira
        exe_mod.executar(pac_mod.ler(caminho), [], porta, leis_dir=d / "leis")
        assert [k for k, _ in porta.chamadas].count("subir_fonte") == primeira


def test_o_prompt_que_chega_na_porta_e_o_do_pacote():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa()
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive")])
        exe_mod.executar(pac, tarefas, porta)
        gerar = [kw for m, kw in porta.chamadas if m == "gerar"]
        assert len(gerar) == 1
        assert gerar[0]["prompt"] == pac.prompts["podcast"]
        assert gerar[0]["opcoes"]["idioma"] == "pt_BR", "o default da lib é 'en'"


def test_quota_de_um_tipo_nao_impede_os_outros():
    """As quotas são separadas por gerável: abortar tudo no primeiro estouro de
    áudio desperdiçaria os tetos muito mais folgados de report."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa(roteiro={"podcast": ["sem-quota"]})
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive"), ("report", "custom")])
        rel = exe_mod.executar(pac, tarefas, porta)
        assert [t for t, _ in rel.sem_quota] == ["podcast"]
        assert [t for t, _ in rel.disparadas] == ["report"]
        assert rel.codigo_saida == 4, "quota é retomável, e o código diz isso"


def test_task_id_vazio_conta_como_quota():
    """É assim que o servidor recusa sem erro explícito — e o sinal sobrevive a
    mudança de mensagem, ao contrário de casar string."""
    class SemTask(porta_mod.PortaFalsa):
        def gerar(self, nb, tipo, prompt, opcoes):
            self._reg("gerar", nb=nb, tipo=tipo, prompt=prompt, opcoes=dict(opcoes))
            return porta_mod.Resultado(porta_mod.SEM_QUOTA, "", "sem task_id")

    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive")])
        rel = exe_mod.executar(pac, tarefas, SemTask())
        assert rel.sem_quota and not rel.disparadas


def test_task_id_vai_para_o_sidecar_nao_para_o_frontmatter():
    """Id opaco é ruído num documento curado, muda a cada execução (e cada mudança
    dispara backup no gerador), e não é escalar — pode haver vários em voo."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive")])
        exe_mod.executar(pac, tarefas, porta_mod.PortaFalsa())
        assert "task_id" not in caminho.read_text(encoding="utf-8")
        side = json.loads((pac.pasta / exe_mod.SIDECAR).read_text(encoding="utf-8"))
        assert side["tarefas"][0]["tipo"] == "podcast"
        assert side["tarefas"][0]["task_id"]
        assert pac_mod.ler(caminho).status == "gerando"


def test_sidecar_e_invisivel_para_o_site():
    """Começa com `_`, como o próprio pacote — o coletor do site ignora os dois."""
    assert exe_mod.SIDECAR.startswith("_")


def test_coleta_baixa_nomeia_e_marca_completo():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa()
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive")])
        exe_mod.executar(pac, tarefas, porta)
        rel = exe_mod.coletar(pac_mod.ler(caminho), porta)
        esperado = pac.arquivo_de("podcast")
        assert rel.baixadas == [esperado], rel.baixadas
        assert (pac.pasta / esperado).is_file()
        assert not list(pac.pasta.glob("*.parcial")), "não pode sobrar parcial"
        assert pac_mod.ler(caminho).status == "completo"


def test_estados_e_uma_chamada_por_notebook():
    """A consulta relista todos os artefatos; perguntar por tarefa multiplicaria
    chamadas sem ganhar nada."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa()
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive"), ("report", "custom")])
        exe_mod.executar(pac, tarefas, porta)
        antes = [k for k, _ in porta.chamadas].count("estados")
        exe_mod.coletar(pac_mod.ler(caminho), porta)
        assert [k for k, _ in porta.chamadas].count("estados") == antes + 1


def test_container_divergente_renomeia_e_corrige_o_pacote():
    """Se vier MP3 onde o pacote diz M4A, o arquivo é salvo com a extensão real E o
    pacote é corrigido — senão ele passa a mentir para o site."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa(conteudo=b"ID3\x04\x00\x00\x00\x00\x00\x00\x00\x00")
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive")])
        exe_mod.executar(pac, tarefas, porta)
        exe_mod.coletar(pac_mod.ler(caminho), porta)
        depois = pac_mod.ler(caminho)
        assert depois.arquivo_de("podcast").endswith(".mp3"), depois.arquivo_de("podcast")
        assert (pac.pasta / depois.arquivo_de("podcast")).is_file()


def test_download_html_e_descartado():
    """Página de erro salva com nome de mídia seria o pior desfecho: o site
    mostraria um player que não toca."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        porta = porta_mod.PortaFalsa(
            conteudo=b"<!DOCTYPE html><html><body>erro</body></html>")
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive")])
        exe_mod.executar(pac, tarefas, porta)
        rel = exe_mod.coletar(pac_mod.ler(caminho), porta)
        assert not rel.baixadas
        assert rel.falhas and "HTML" in rel.falhas[0][1]
        assert not list(pac.pasta.glob("podcast-*"))


def test_publicar_e_opt_in():
    """Sem a flag, o notebook não vira público — mas a URL é gravada assim mesmo,
    porque ela é derivável e funciona para o dono."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        porta = porta_mod.PortaFalsa()
        exe_mod.executar(pac_mod.ler(caminho), [], porta)
        assert not any(m == "publicar" for m, _ in porta.chamadas)
        assert pac_mod.ler(caminho).url.startswith("https://notebooklm.google.com/")
        exe_mod.executar(pac_mod.ler(caminho), [], porta, publicar=True)
        assert any(m == "publicar" for m, _ in porta.chamadas)


def test_cli_roda_dry_run_sem_a_biblioteca():
    """O dry-run é o relatório honesto do backlog, e não pode exigir dependência."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        r = subprocess.run(
            [sys.executable, str(ROOT / "nlm_run.py"),
             "--aprofundamento", str(caminho.parent), "--dry-run"],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        saida = json.loads(r.stdout)
        assert saida["a_disparar"] == 1
        assert saida["itens"][0]["tarefas"] == ["podcast:deep-dive"]


def test_cli_sem_executavel_degrada_com_exit_2():
    """Sem a biblioteca o pacote manual continua completo — é degradação, não erro
    de rede (que seria 1, e onde instalar não resolveria)."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        r = subprocess.run(
            [sys.executable, str(ROOT / "nlm_run.py"),
             "--aprofundamento", str(caminho.parent),
             "--executavel", "notebooklm-que-nao-existe"],
            capture_output=True, text=True)
        assert r.returncode == 2, (r.returncode, r.stderr)
        assert "manual" in r.stderr


def test_cli_recusa_midia_invalida_com_exit_3():
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        r = subprocess.run(
            [sys.executable, str(ROOT / "nlm_run.py"),
             "--aprofundamento", str(caminho.parent), "--midias", "mapa-mental"],
            capture_output=True, text=True)
        assert r.returncode == 3
        assert "JSON" in r.stderr


def test_prefere_o_notebooklm_da_venv_do_projeto():
    """Regressão de campo: com duas instalações (uma no ~/.local, outra na venv), o
    PATH escolhe a errada — e as versões guardam a credencial em caminhos DIFERENTES.
    O sintoma é "Auth not found" logo depois de um login bem-sucedido."""
    achado = porta_mod.PortaCLI.achar_executavel()
    if (ROOT.parents[2] / ".venv" / "bin" / "notebooklm").is_file():
        assert achado.endswith(".venv/bin/notebooklm"), achado
    # caminho explícito é sempre respeitado
    assert porta_mod.PortaCLI.achar_executavel("/usr/bin/x") == "/usr/bin/x"


def test_disponivel_aceita_caminho_absoluto():
    """`shutil.which` não acha executável fora do PATH — e o da venv está fora."""
    assert not porta_mod.PortaCLI.disponivel("/caminho/que/nao/existe")
    assert porta_mod.PortaCLI.disponivel(sys.executable), "caminho absoluto vale"


def test_relatorio_nunca_carrega_cookie():
    """Segredo em log é vazamento silencioso: o relatório vai para o terminal, para
    o `--json` e para onde o usuário colar."""
    with tempfile.TemporaryDirectory() as d:
        caminho = _montar_pacote(Path(d))
        if caminho is None:
            return
        pac = pac_mod.ler(caminho)
        tarefas, _ = plano_mod.planejar(pac, [("podcast", "deep-dive")])
        rel = exe_mod.executar(pac, tarefas, porta_mod.PortaFalsa())
        texto = json.dumps(rel.como_dict(), ensure_ascii=False)
        for proibido in ("__Secure", "SID=", "SAPISID", "storage_state"):
            assert proibido not in texto, proibido


def _run_standalone():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
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
