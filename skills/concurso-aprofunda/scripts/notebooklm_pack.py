#!/usr/bin/env python3
"""
notebooklm_pack.py - Subsistema C (camada manual) da skill concurso-aprofunda.

Para cada assunto já aprofundado, gera um "_fonte-notebooklm.md": o pacote de
embarque para criar, MANUALMENTE, um notebook por assunto no NotebookLM —
com as fontes a subir, prompts prontos (podcast) e roteiro de cliques.

Arquitetura de duas camadas (decidida com o usuário):
  - Esta é a CAMADA MANUAL (garantida): não depende de nenhuma API frágil.
  - A camada automatizada (notebooklm-py) virá depois e reusa este mesmo pacote.

Decisão de design: UM notebook POR ASSUNTO (não por matéria), para manter o
material focado e a qualidade dos derivados alta, e para casar com o
reaproveitamento entre concursos (um notebook de "Crase/Pestana" é reusável).

Uso:
    python notebooklm_pack.py --assuntos-dir <.../assuntos> \
        --concurso "SEDES_2026" --materia "Língua Portuguesa" \
        [--leis-dir <.../leis-baixadas>] [--template <tpl>]

Para cada subpasta de assunto que tenha o .md preenchido, cria o _fonte-notebooklm.md.
"""
import argparse
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aprofundamento_id import eh_pasta_aprofundamento, localizacoes  # noqa: E402
from renomear_aprof import frontmatter_sem_linha_vazia  # noqa: E402


def slug(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")


def ler_frontmatter(md: Path) -> dict:
    try:
        txt = md.read_text(encoding="utf-8")
    except Exception:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    fm = {}
    if m:
        for linha in m.group(1).split("\n"):
            if ":" in linha:
                k, _, v = linha.partition(":")
                v = v.strip()
                # remover comentário inline do YAML ("padrao   # padrao | detalhado"),
                # preservando '#' dentro de valores entre aspas (ex.: URLs com fragmento)
                if not v.startswith(('"', "'")):
                    v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
                fm[k.strip()] = v.strip('"').strip("'")
    fm["_corpo"] = txt[m.end():] if m else txt
    return fm


def arquivo_principal(pasta: Path) -> Path | None:
    """Acha o .md principal: '{pasta}.md' (legado) ou '{assunto}--{aprof}.md' (novo)."""
    exato = pasta / f"{pasta.name}.md"
    if exato.exists():
        return exato
    candidatos = [p for p in sorted(pasta.glob("*.md"))
                  if not p.name.startswith(("flashcards-", "_", "00-", "report-",
                                            "teste-", "tabela-"))]
    return candidatos[0] if candidatos else None


def pastas_de_aprofundamento(assunto_dir: Path) -> list[Path]:
    """Lista as pastas que contêm um aprofundamento deste assunto.

    Formato atual: {assunto}/{nivel}--{N}f--f1-{fonte}/
    Formatos aceitos por compatibilidade de leitura:
      - {assunto}/aprofundamentos/{id}/   (0.2.x)
      - {assunto}/{assunto}.md            (legado plano)
    """
    achadas = [d for d in sorted(assunto_dir.iterdir())
               if d.is_dir() and eh_pasta_aprofundamento(d.name)]
    antiga = assunto_dir / "aprofundamentos"
    if antiga.is_dir():
        achadas += [d for d in sorted(antiga.iterdir()) if d.is_dir()]
    if (assunto_dir / f"{assunto_dir.name}.md").exists():
        achadas.append(assunto_dir)          # legado convive
    return achadas


def tem_placeholder(corpo: str) -> bool:
    return bool(re.search(r"\{[A-Z_]{3,}\}", corpo))


# Números que sozinhos não identificam norma nenhuma: ano é o caso real e caro.
# `pnas-2004-texto-integral.pdf` tem 2004 como PRIMEIRO grupo de 3-5 dígitos, então
# qualquer corpo que citasse o ano arrastava a PNAS inteira para o notebook.
_RE_ANO = re.compile(r"^(19|20)\d{2}$")


def _numeros_de_norma(stem: str) -> list[str]:
    """Os números do nome do arquivo que podem identificar uma norma, sem os anos."""
    return [n for n in re.findall(r"\d{3,5}", stem) if not _RE_ANO.match(n)]


# O que qualifica um número como NORMA. Sem isto, qualquer número casa: no vault,
# "Cap. 3 — Ortografia 105–142" e "(p. 105)" mandavam a LC 105 (sigilo bancário)
# para o notebook de ortografia, e "art. 109" puxaria a Resolução CNAS 109.
# Página é número, artigo é número, inciso é número — norma é número COM NOME.
_MARCADOR_NORMA = (
    r"(?:lei(?:\s+complementar|\s+federal|\s+distrital|\s+org[âa]nica)?|lc|ldb"
    r"|decreto(?:\s+federal|\s+distrital)?|dec"
    r"|resolu[çc][ãa]o(?:\s+conjunta)?|res|portaria|port"
    r"|emenda(?:\s+constitucional)?|ec|medida\s+provis[óo]ria|mp|s[úu]mula)"
)


def _corpo_tem_numero(corpo_digitos: str, numero: str) -> bool:
    """O número aparece no corpo COMO NORMA, não como página ou artigo.

    Duas exigências, cada uma nascida de um falso positivo real:

    1. **fronteira**: `105` não pode casar dentro de `1050` — a comparação era
       substring crua;
    2. **marcador**: o número precisa vir depois de "Lei", "Decreto",
       "Resolução"… em até ~40 caracteres, que cobre "Lei Complementar nº
       105/2001" e "Resolução CMN nº 4.949/2021" sem alcançar a frase seguinte.

    O milhar já foi removido pelo chamador, então `8.742` no texto e `8742` no
    nome do arquivo são a mesma lei.
    """
    return re.search(rf"{_MARCADOR_NORMA}[^.\n]{{0,40}}?(?<!\d){re.escape(numero)}(?!\d)",
                     corpo_digitos, re.IGNORECASE) is not None


# Siglas que nomeiam A NORMA, não o órgão que a editou nem o sistema que ela criou.
# A distinção é julgamento, não derivação, e por isso a lista é explícita: medindo o
# vault, "token alfabético final do stem" pegava CDC e LGPD mas também SEGURANCA,
# CLIENTE e HISTORICO, enquanto qualquer regra que aceitasse BACEN fazia toda menção
# ao Banco Central arrastar duas circulares específicas (7 casos), e SUAS — o sistema —
# arrastava a NOB (21 casos). Referência a "CDC" É referência à Lei 8.078; referência
# a "BACEN" não é referência à Circular 3.978.
# Para acrescentar: só entra sigla que o leitor usaria NO LUGAR do número da norma.
_APELIDOS_DE_NORMA = {
    "CDC": "lei-8078",
    "ECA": "lei-8069",
    "LGPD": "lei-13709",
    "LOAS": "lei-8742",
    "LBI": "lei-13146",
    "PNAS": "pnas-",
    "PLD": "pld",
    "PRSA": "prsa-",
    "PRSAC": "prsac-",
}


def _corpo_tem_apelido(corpo: str, stem: str) -> bool:
    """O corpo cita a norma pelo apelido consagrado dela (CDC, LGPD, ECA…)."""
    return any(marca in stem.lower() and re.search(rf"\b{sigla}\b", corpo)
               for sigla, marca in _APELIDOS_DE_NORMA.items())


def leis_relacionadas(corpo: str, leis_dir: Path | None, fm: dict | None = None) -> list[str]:
    """As leis a subir no notebook — declaradas, ou sugeridas pela heurística.

    `fontes_notebook:` no frontmatter é a DECISÃO: quando existe, manda, e a
    heurística nem roda. Sem ele, a heurística sugere — e quem chama deve ecoar o
    que ela escolheu, porque adivinhação silenciosa foi o que pôs leis não
    declaradas em ~75 aprofundamentos do vault.
    """
    # Tolera as duas grafias do frontmatter: `a.pdf, b.pdf` e a lista YAML inline
    # `[a.pdf, b.pdf]`. A `concurso-publica` lê este MESMO campo com `lista_yaml`,
    # que aceita ambas — divergir aqui faria o nome vir com colchete colado,
    # nunca casar com arquivo em disco e virar "fonte faltando" sem motivo
    # aparente. Mesmo campo, dois leitores: têm de ler igual.
    bruto = str((fm or {}).get("fontes_notebook") or "").strip()
    if bruto.startswith("[") and bruto.endswith("]"):
        bruto = bruto[1:-1]
    declaradas = [x.strip().strip('"').strip("'") for x in bruto.split(",") if x.strip()]
    if declaradas:
        return declaradas
    if not leis_dir or not leis_dir.exists():
        return []
    # o corpo sem separador de milhar: "Lei nº 8.742/1993" -> "...8742/1993..."
    corpo_digitos = re.sub(r"(?<=\d)[.\s](?=\d)", "", corpo)
    # Um container por norma: `.md` e `.pdf` do mesmo arquivo são o MESMO texto,
    # não duas fontes. O `.md` vence — é texto puro, menor, e o modelo ingere
    # melhor. Medido: 9 pacotes do vault subiam a norma duas vezes, e um deles
    # mandava 9 fontes que eram a nota + 4 leis × 2 containers.
    por_stem: dict[str, Path] = {}
    for arq in sorted(list(leis_dir.glob("*.md")) + list(leis_dir.glob("*.pdf"))):
        if not (any(_corpo_tem_numero(corpo_digitos, n) for n in _numeros_de_norma(arq.stem))
                or _corpo_tem_apelido(corpo, arq.stem)):
            continue
        atual = por_stem.get(arq.stem)
        if atual is None or (atual.suffix == ".pdf" and arq.suffix == ".md"):
            por_stem[arq.stem] = arq
    return [p.name for p in por_stem.values()]


def clausula_fonte(nota: str) -> str:
    """A âncora de TODO prompt é a nota curada do vault — nunca o livro.

    Subir o livro (ou o recorte dele) é **opcional**: `montar_lista_fontes` o marca
    como *(Referência)*. Prompt que nomeasse a obra mandava o modelo consultar uma
    fonte que pode não estar no notebook — o prompt e a instrução de fontes se
    contradiziam. Aqui só entra o nome do `.md` do aprofundamento, que é sempre o
    item 1 da lista de fontes e, por isso, sempre está no notebook.

    Se um prompt novo precisar citar material, cite POR AQUI. Há teste que varre
    todos os blocos de prompt gerados e falha se algum nomear PDF, página ou obra.
    """
    return f'Baseie-se na nota "{nota}" deste notebook.'


def montar_prompt_audio(assunto: str, materia: str, nivel: str = "padrao",
                        nota: str = "") -> str:
    fonte = f" {clausula_fonte(nota)}" if nota else ""
    if nivel == "detalhado":
        return (
            f"Faca um episodio APROFUNDADO sobre {assunto} para concurso publico."
            f"{fonte} Trate os casos especiais e as excecoes, nao so a regra "
            f"geral. Traga exemplos resolvidos comentando o raciocinio e mencione "
            f"as divergencias entre autores quando existirem. Publico: candidato "
            f"que ja domina o basico e quer fechar o assunto."
        )
    return (
        f"Foque em {assunto} para um concurso público.{fonte} Explique as regras "
        f"principais de forma didática, com exemplos práticos, e destaque as pegadinhas "
        f"e os erros mais comuns que bancas exploram. Priorize o que mais cai em prova "
        f"objetiva. Use linguagem clara, como uma aula de revisao para quem ja estudou "
        f"o basico. Evite enrolacao e frases de efeito; va direto ao ponto."
    )


def montar_prompt_mindmap(assunto: str, nota: str = "") -> str:
    # aqui a cláusula vai na FRENTE: a frase de abertura termina em dois-pontos que
    # introduzem a lista de ramos, e encaixar no meio partiria a enumeração
    fonte = f"{clausula_fonte(nota)} " if nota else ""
    return (
        f"{fonte}Construa o mapa mental de {assunto} com estes ramos centrais: "
        f"(1) CONCEITO/definicao; (2) REGRAS gerais; (3) CASOS ESPECIAIS e excecoes; "
        f"(4) PEGADINHAS de prova; (5) CONEXOES com outros assuntos. "
        f"Sob cada ramo, agrupe os subtopicos como nos-filhos, do mais cobrado ao menos. "
        f"Priorize o que cai em concurso e mantenha os rotulos curtos."
    )


def montar_prompt_video(assunto: str, nota: str = "") -> str:
    fonte = f" {clausula_fonte(nota)}" if nota else ""
    return (
        f"Faca um video-aula explicativo sobre {assunto} para quem estuda para "
        f"concurso.{fonte} Enfatize as regras que mais caem e mostre 2-3 exemplos "
        f"resolvidos passo a passo. Dedique um trecho as pegadinhas classicas da banca. "
        f"Publico: candidato que ja viu o basico e quer fixar e evitar erros."
    )


def montar_prompt_report(assunto: str, nota: str = "") -> str:
    fonte = f" {clausula_fonte(nota)}" if nota else ""
    return (
        f"Gere um guia de estudos de {assunto} para concurso.{fonte} Use esta estrutura: "
        f"1) Resumo das regras essenciais; 2) Quadro de casos (obrigatorio/proibido/"
        f"facultativo, quando aplicavel); 3) Lista de pegadinhas com exemplo de cada; "
        f"4) 5 dicas rapidas de memorizacao. Seja objetivo e use exemplos curtos."
    )


def montar_perguntas(assunto: str) -> str:
    qs = [
        f"Quais são as 5 regras mais importantes de {assunto} para concurso?",
        f"Quais as pegadinhas mais comuns de {assunto} em provas?",
        f"Me dê 10 exemplos comentados sobre {assunto}.",
        f"Qual a diferença entre os casos que mais confundem em {assunto}?",
    ]
    return "\n".join(f"- {q}" for q in qs)


def montar_lista_fontes(assunto_md: Path, leis: list[str], fm: dict) -> str:
    linhas = [f"1. **`{assunto_md.name}`** — o resumo curado deste assunto (fonte principal)."]
    # um item por fonte: num aprofundamento combinado o recorte de UMA delas não
    # representa o material, e listar só a primeira faria o usuário subir metade
    for loc in localizacoes(fm):
        linhas.append(f"{len(linhas) + 1}. *(Referência)* trecho do livro: {loc} — opcional, "
                      "suba o recorte dessas páginas se quiser mais profundidade.")
    n = len(linhas) + 1
    for lei in leis:
        linhas.append(f"{n}. **`{lei}`** — legislação relacionada (já baixada pela concurso-prep).")
        n += 1
    return "\n".join(linhas)


# chaves do pacote que o gerador NÃO sabe reconstruir: são escritas por fora, à mão
# pelo usuário ou pela automação. `notebooklm_url` e `notebooklm_status` têm lugar
# fixo no template; qualquer outra `notebooklm_*` é reemitida no bloco EXTRA.
CAMPOS_FIXOS_NB = ("notebooklm_url", "notebooklm_status")
CHAVE_NB = re.compile(r"^(notebooklm_[a-z0-9_]+):\s*(.*)$", re.MULTILINE)


def herdar_campos(destino: Path) -> dict:
    """Lê do pack existente tudo que o gerador não sabe reconstruir.

    Devolve `{"url":…, "status":…, "extras": {chave: valor}}`. O corpo do pacote é
    100% derivável do assunto — fontes, prompts, roteiro, perguntas —, mas o bloco
    `notebooklm_*` não: ele é escrito por FORA, pelo usuário que cola o link ou pela
    automação que registra o notebook criado. Sem herdar, a regeneração manda tudo
    para o `.bak.md` e o site perde o botão "Abrir no NotebookLM" sem erro nenhum.

    Herda por PREFIXO, não por lista: campo novo que a automação passe a gravar
    sobrevive sozinho, sem precisar lembrar de vir aqui. Foi justamente esquecer de
    estender esta função que apagaria `notebooklm_id` na primeira regeração.
    """
    vazio = {"url": "", "status": "nao-criado", "extras": {}}
    if not destino.exists():
        return vazio
    try:
        txt = destino.read_text(encoding="utf-8")
    except OSError:
        return vazio
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    if not m:
        return vazio

    achados = {}
    for chave, bruto in CHAVE_NB.findall(m.group(1)):
        valor = bruto.strip().strip('"').strip("'")
        if valor.lower() in ("", "null", "~"):
            continue
        achados[chave] = valor

    return {
        "url": achados.get("notebooklm_url", ""),
        "status": achados.get("notebooklm_status", "nao-criado"),
        "extras": {k: v for k, v in achados.items() if k not in CAMPOS_FIXOS_NB},
    }


def bloco_extras_nb(extras: dict) -> str:
    """As chaves `notebooklm_*` herdadas que não têm lugar fixo no template."""
    return "\n".join(f'{k}: "{v}"' for k, v in sorted(extras.items()))


def preencher(tpl: str, ctx: dict) -> str:
    out = tpl
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", str(v))
    return frontmatter_sem_linha_vazia(out)


def gerar_para_pasta(pasta: Path, subdir: Path, *, concurso: str = "", materia: str = "",
                     leis_dir: Path = None, tpl: str) -> dict:
    """Gera/atualiza o `_fonte-notebooklm.md` de UMA pasta de aprofundamento.

    Extraída de `main()` para que quem mexe numa pasta só (ampliar_aprofundamento.py,
    depois de renomear) não regenere os pacotes de todos os irmãos, espalhando
    `.bak.md` alheios.

    `subdir` é a pasta do ASSUNTO — a comparação `pasta == subdir` é o que
    distingue o layout plano legado (sem sufixo no nome do notebook).

    Devolve {"estado": "gerado"|"inalterado"|"pulado", ...}; nunca levanta.
    """
    assunto_md = arquivo_principal(pasta)
    if assunto_md is None:
        return {"estado": "pulado", "motivo": "sem .md principal", "pasta": str(pasta)}
    fm = ler_frontmatter(assunto_md)
    if tem_placeholder(fm.get("_corpo", "")):
        return {"estado": "pulado", "motivo": "placeholder por preencher",
                "pasta": f"{subdir.name}/{pasta.name}"}

    assunto = fm.get("title", subdir.name)
    leis = leis_relacionadas(fm.get("_corpo", ""), leis_dir, fm=fm)
    base = assunto_md.stem          # nome único do aprofundamento
    nivel = (fm.get("nivel") or "padrao").strip()
    # a nota do vault é a âncora dos prompts; o livro NUNCA entra neles
    nota = assunto_md.name
    sufixo_nome = "" if pasta == subdir else f" — {fm.get('aprofundamento', pasta.name)}"
    ctx = {
        "ASSUNTO": assunto + sufixo_nome,
        "MATERIA": materia or fm.get("materia", ""),
        "CONCURSO": concurso or fm.get("concurso", ""),
        "TAG_ASSUNTO": subdir.name,
        "SLUG_ASSUNTO": base,
        "LISTA_FONTES": montar_lista_fontes(assunto_md, leis, fm),
        "PROMPT_AUDIO": montar_prompt_audio(assunto, materia, nivel, nota),
        "PROMPT_MINDMAP": montar_prompt_mindmap(assunto, nota),
        "PROMPT_VIDEO": montar_prompt_video(assunto, nota),
        "PROMPT_REPORT": montar_prompt_report(assunto, nota),
        "PERGUNTAS_CHAT": montar_perguntas(assunto),
    }
    destino = pasta / "_fonte-notebooklm.md"

    # Campos que o USUÁRIO preenche à mão viajam do pack antigo para o novo.
    # Sem isso, a regeneração manda o link do notebook para o `.bak.md` e o
    # botão "Abrir no NotebookLM" desaparece do site sem erro nenhum — é a
    # única informação do pacote que não dá para regerar.
    herdado = herdar_campos(destino)
    ctx["NOTEBOOKLM_URL"] = herdado["url"]
    ctx["NOTEBOOKLM_STATUS"] = herdado["status"]
    ctx["NOTEBOOKLM_EXTRA"] = bloco_extras_nb(herdado["extras"])

    novo = preencher(tpl, ctx)
    bak = None
    # preservar trabalho do usuário: só sobrescreve com backup, e só se mudou
    if destino.exists():
        antigo = destino.read_text(encoding="utf-8")
        if antigo == novo:
            return {"estado": "inalterado", "arquivo": str(destino)}
        bak = destino.with_suffix(".bak.md")
        shutil.copy2(destino, bak)
    destino.write_text(novo, encoding="utf-8")
    return {"estado": "gerado", "arquivo": str(destino),
            **({"backup": str(bak)} if bak else {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assuntos-dir", type=Path, required=True)
    ap.add_argument("--concurso", default="")
    ap.add_argument("--materia", default="")
    ap.add_argument("--leis-dir", type=Path, default=None)
    ap.add_argument("--template", type=Path,
                    default=Path(__file__).resolve().parents[1] / "assets/templates/fonte-notebooklm.md.tpl")
    args = ap.parse_args()

    tpl = args.template.read_text(encoding="utf-8")
    gerados, pulados, inalterados, backups = [], [], [], []

    for subdir in sorted(args.assuntos_dir.iterdir()):
        if not subdir.is_dir():
            continue
        # um pacote POR APROFUNDAMENTO: fontes diferentes = notebooks diferentes
        for pasta in pastas_de_aprofundamento(subdir):
            r = gerar_para_pasta(pasta, subdir, concurso=args.concurso,
                                 materia=args.materia, leis_dir=args.leis_dir, tpl=tpl)
            if r["estado"] == "pulado":
                # "sem .md principal" não é pendência de preenchimento: a pasta
                # simplesmente não é um aprofundamento, e antes era ignorada calada
                if r.get("motivo") != "sem .md principal":
                    pulados.append(r["pasta"])
            elif r["estado"] == "inalterado":
                inalterados.append(r["arquivo"])
            else:
                gerados.append(r["arquivo"])
                if r.get("backup"):
                    backups.append(r["backup"])

    print(json.dumps({
        "gerados": len(gerados),
        "inalterados": len(inalterados),
        "backups": backups,
        "pulados_sem_preenchimento": pulados,
        "arquivos": gerados,
    }, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
