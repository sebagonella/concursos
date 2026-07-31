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
