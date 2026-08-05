#!/usr/bin/env python3
"""
validar_assuntos.py — confere que os `.md` de assunto têm as seções do template.

Existe por um defeito silencioso: 16 assuntos de norma jurídica do vault foram
escritos com uma estrutura própria (`🧩 Estrutura da norma`, `📌 Artigos-chave`,
`⚠️ Pegadinhas Quadrix`, `🔗 Relacionados`) que **não existe em nenhum template
da skill**. O conteúdo ficou bom; o que sumiu foi a seção `📝 Para estudar
depois`, que é onde vivem 100% das tarefas de estudo do vault. Resultado: cinco
matérias inteiras apareciam no site sem tarefa nenhuma, sem erro em lugar nenhum.

O arcabouço sai de `build_subject_md.py` a partir do template; o resumo é escrito
por cima. Nada garantia que a escrita preservasse as seções — agora garante.

Uso:
    python validar_assuntos.py --materia-dir <.../03-APROFUNDAMENTO/{materia}>
    python validar_assuntos.py --concurso-dir <.../CONCURSOS/SEDES_2026>
    python validar_assuntos.py --concurso-dir <...> --corrigir   # acrescenta o que falta

Sai com 1 se algum assunto estiver incompleto (`--corrigir` conserta e sai 0).
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aprofundamento_id as aid  # noqa: E402
import notebooklm_pack as nlp  # noqa: E402

# As seções que o site e o fluxo dependem de encontrar. Deliberadamente curta:
# cobrar o template inteiro engessaria a escrita, que varia entre livro e norma.
# Aqui está só o que QUEBRA alguma coisa quando falta.
OBRIGATORIAS = {
    "Para estudar depois": (
        "é onde vivem as tarefas de estudo; sem ela a matéria aparece no site "
        "sem tarefa nenhuma"),
}

def campo(md: Path, nome: str) -> str:
    txt = md.read_text(encoding="utf-8")
    m = re.search(rf'^{nome}:\s*"?(.+?)"?\s*$', txt, re.MULTILINE)
    return m.group(1).strip() if m else ""


def titulo_do(md: Path) -> str:
    t = campo(md, "title")
    if t:
        return t
    m = re.search(r"^#\s+(.+)$", md.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1).strip() if m else md.stem


def faltantes(md: Path) -> list[str]:
    txt = md.read_text(encoding="utf-8")
    cabecalhos = re.findall(r"^##\s+(.+)$", txt, re.MULTILINE)
    achados = " · ".join(cabecalhos)
    return [nome for nome in OBRIGATORIAS if nome not in achados]


def _frontmatter(md: Path) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", md.read_text(encoding="utf-8"), re.S)
    out = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha:
                k, v = linha.split(":", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def incoerencias(md: Path, pasta: Path) -> list[str]:
    """Avisos de frontmatter que não bate com a identidade da pasta.

    Duas conferências, ambas já implementadas na convenção — aqui elas
    finalmente são CHAMADAS. `conferir_localizacoes` existia desde a 0.4 e
    nenhum script a invocava; `conferir_fontes` nasceu porque o campo `fontes:`
    podia divergir do id sem que nada percebesse, e era dele que o site tirava a
    contagem exibida (selo inflado em 15 dos 29 assuntos multi-nível do vault).

    A comparação é de CONTAGEM, nunca de re-derivação do slug: `slug_fonte` sobre
    "Lei Federal nº 11.340/2006 (Lei Maria da Penha)" devolve `penha`, não
    `lei-11340`, e re-derivar acusaria 8 falsos positivos entre os 55 slugs.
    """
    fm = _frontmatter(md)
    avisos = aid.conferir_fontes(fm, pasta.name)
    # Localização só se cobra de quem se declara de LIVRO. Norma e material
    # próprio não têm página: a fonte é a própria norma (`fonte_norma:`) ou o
    # texto escrito do zero. Cobrar de todos daria 42 falsos positivos nos 177
    # aprofundamentos do vault — e validador que grita onde não há defeito é
    # validador que se aprende a ignorar.
    if aid.localizacoes(fm):
        avisos += aid.conferir_localizacoes(fm, pasta.name)
    return avisos


def secao_de_tarefas(md: Path, slug_assunto: str) -> str:
    """O bloco a acrescentar, montado só com o que o arquivo já afirma.

    Nada de página inventada: a leitura sai do campo `fontes:` do frontmatter,
    que é o que o arquivo declara, e o link dos flashcards sai do arquivo que
    EXISTE ao lado. Um `[[flashcards-{slug}]]` genérico nasceria morto — o nome
    real carrega o identificador do aprofundamento (`flashcards-loas--padrao--
    lei-8742--SEDES_2026`), que é justamente a convenção que impede dois
    `crase.md` de colidirem.
    """
    titulo = titulo_do(md)
    fontes = campo(md, "fontes")
    itens = [f"Ler {fontes}" if fontes else "Ler o material deste assunto"]
    fc = sorted(md.parent.glob("flashcards-*.md"))
    if fc:
        itens.append(f"Revisar os flashcards deste assunto ([[{fc[0].stem}]])")
    itens.append(f"Resolver questões da banca sobre {titulo}")
    itens.append("(Etapa NotebookLM) Gerar podcast/mapa mental a partir deste .md")
    corpo = "\n".join(f"- [ ] {i}" for i in itens)
    return f"\n## 📝 Para estudar depois\n\n{corpo}\n"


def inserir(md: Path, bloco: str) -> None:
    """Acrescenta antes do rodapé de fonte-notebooklm, se houver; senão, no fim.

    Nunca reescreve o que já está no arquivo — o resumo é trabalho do usuário.

    O backup é `.md.bak`, **não** `.bak.md`: quem acha o arquivo principal do
    aprofundamento pega o primeiro `*.md` em ordem, e `…SEDES_2026.bak.md`
    ordena ANTES de `…SEDES_2026.md` — o backup viraria o aprofundamento. Com
    `.md.bak` o `glob("*.md")` nem o enxerga, e o site já o ignora por extensão.
    """
    txt = md.read_text(encoding="utf-8")
    marca = "\n---\n<!-- fonte-notebooklm:"
    if marca in txt:
        cabeca, _, cauda = txt.partition(marca)
        novo = cabeca.rstrip("\n") + "\n" + bloco + marca + cauda
    else:
        novo = txt.rstrip("\n") + "\n" + bloco
    md.with_name(md.name + ".bak").write_text(txt, encoding="utf-8")
    md.write_text(novo, encoding="utf-8")


def varrer(raiz: Path) -> list[tuple[Path, str, list[str]]]:
    """Todo `.md` principal de aprofundamento sob `raiz`, com o que lhe falta."""
    achados = []
    for assuntos_dir in sorted(raiz.rglob("assuntos")):
        if not assuntos_dir.is_dir():
            continue
        for assunto_dir in sorted(p for p in assuntos_dir.iterdir() if p.is_dir()):
            for pasta in nlp.pastas_de_aprofundamento(assunto_dir):
                md = nlp.arquivo_principal(pasta)
                if md is None:
                    continue
                achados.append((md, assunto_dir.name,
                                faltantes(md) + incoerencias(md, pasta)))
    return achados


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--concurso-dir", type=Path)
    ap.add_argument("--materia-dir", type=Path)
    ap.add_argument("--corrigir", action="store_true",
                    help="acrescenta as seções ausentes (com backup .bak.md)")
    args = ap.parse_args()

    raiz = args.concurso_dir or args.materia_dir
    if not raiz or not raiz.is_dir():
        sys.stderr.write("ERRO: informe --concurso-dir ou --materia-dir\n")
        return 2

    achados = varrer(raiz)
    # Quem varre e não acha nada FALHA ALTO. Sair com sucesso sobre zero arquivos
    # é como o `fix_notebooklm_packs` que achava 0 dos 158 pacotes e passava.
    if not achados:
        sys.stderr.write(f"ERRO: nenhum aprofundamento encontrado em {raiz}\n")
        return 2

    incompletos = [(md, assunto, falta) for md, assunto, falta in achados if falta]
    print(f"{len(achados)} aprofundamento(s) conferido(s) — "
          f"{len(incompletos)} incompleto(s).")
    if not incompletos:
        return 0

    for md, assunto, falta in incompletos:
        print(f"  ✗ {assunto}/{md.parent.name}: falta {', '.join(falta)}")
        if args.corrigir:
            inserir(md, secao_de_tarefas(md, assunto))
            print(f"    ✓ seção acrescentada (backup em {md.name}.bak)")

    if args.corrigir:
        return 0
    for nome, porque in OBRIGATORIAS.items():
        print(f"\n`{nome}` {porque}.")
    print("Rode de novo com --corrigir para acrescentar.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
