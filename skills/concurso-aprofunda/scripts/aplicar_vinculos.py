#!/usr/bin/env python3
"""
aplicar_vinculos.py — grava no vault o vínculo ASSUNTO -> TÓPICO do edital.

Consome o JSON revisado que sai do `propor_vinculos.py` e escreve `materia_id`,
`topico_id` e `topico` no frontmatter de cada `.md` de aprofundamento.

Disciplina (a mesma do `migrar_aprofundamentos.py`, e pelas mesmas razões):
  - **dry-run é o padrão**; só grava com `--aplicar`
  - **backup** `.bak.md` antes de reescrever, porque dentro desses arquivos mora
    o resumo escrito à mão — o ativo mais caro do vault
  - **só mexe no frontmatter**: o corpo (e o progresso, que são os checkboxes)
    passa intacto
  - **nunca inventa**: `topico_id` vazio é gravado como `[]`, que significa
    "ainda não vinculado" e é um estado legítimo e visível no site
  - pendência vira aviso e exit code 2, nunca silêncio

O que NÃO faz: mover pasta, renomear arquivo, reescrever wikilink. Este script
só acrescenta metadado — foi assim que se escolheu resolver a organização
matéria/tópico/assunto sem tocar em caminho, exatamente para não quebrar os
índices, que referenciam cada assunto pelo path completo.
"""
import argparse
import json
import re
import sys
from pathlib import Path

CAMPOS = ("materia_id", "topico_id", "topico")


def escapar(s: str) -> str:
    return str(s).replace('"', '\\"')


def bloco_vinculo(materia_id: str, topico_ids: list, topicos: list) -> list[str]:
    ids = ", ".join(topico_ids)
    tits = ", ".join(f'"{escapar(t)}"' for t in topicos)
    return [f"materia_id: {materia_id}",
            f"topico_id: [{ids}]",
            f"topico: [{tits}]"]


def reescrever_frontmatter(md: Path, materia_id: str, topico_ids: list,
                           topicos: list) -> tuple[str, str] | None:
    """Devolve (texto_novo, o_que_mudou) ou None se nada muda."""
    txt = md.read_text(encoding="utf-8")
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", txt, re.DOTALL)
    if not m:
        return None
    linhas = m.group(2).split("\n")
    # tira os campos antigos onde quer que estejam, e os reinsere logo depois
    # de `materia:` — posição estável deixa o diff do vault legível
    restantes = [l for l in linhas
                 if not any(l.strip().startswith(c + ":") for c in CAMPOS)]
    novo = bloco_vinculo(materia_id, topico_ids, topicos)
    saida, inserido = [], False
    for l in restantes:
        saida.append(l)
        if not inserido and l.strip().startswith("materia:"):
            saida.extend(novo)
            inserido = True
    if not inserido:
        saida = novo + saida
    corpo_fm = "\n".join(saida)
    texto_novo = m.group(1) + corpo_fm + m.group(3) + txt[m.end():]
    if texto_novo == txt:
        return None
    return texto_novo, f"{materia_id} · {topico_ids or '[]'}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vinculos", type=Path, required=True,
                    help="JSON revisado, saída do propor_vinculos.py")
    ap.add_argument("--aplicar", action="store_true",
                    help="grava de fato. Sem isto, só mostra o que faria.")
    args = ap.parse_args()

    dados = json.loads(args.vinculos.read_text(encoding="utf-8"))
    tocados, pendencias, sem_topico = [], [], []

    for mat in dados.get("materias", []):
        materia_id = (mat.get("materia_id") or "").strip()
        if not materia_id:
            pendencias.append(
                f"matéria {mat['pasta_aprofundamento']!r} sem `materia_id` — sem ele "
                f"o mapa e o aprofundamento não se encontram")
            continue
        # tópicos válidos do mapa escolhido, para não gravar id inexistente
        validos = set()
        for cand in mat.get("mapas_candidatos", []):
            if cand.get("slug") == materia_id or cand.get("materia_id_atual") == materia_id:
                validos |= {t["id"] for t in cand.get("topicos", [])}
        if not validos:
            validos = {t["id"] for c in mat.get("mapas_candidatos", [])
                       for t in c.get("topicos", [])}
        titulo_de = {t["id"]: f'{t["numero"]}. {t["titulo"]}'
                     for c in mat.get("mapas_candidatos", [])
                     for t in c.get("topicos", [])}

        for a in mat.get("assuntos", []):
            ids = [t for t in (a.get("topico_id") or []) if t]
            fora = [t for t in ids if t not in validos]
            if fora:
                pendencias.append(
                    f"{mat['pasta_aprofundamento']}/{a['slug']}: tópico(s) "
                    f"inexistente(s) no mapa: {', '.join(fora)}")
                continue
            if not ids:
                sem_topico.append(f"{mat['pasta_aprofundamento']}/{a['slug']}")
            titulos = [titulo_de.get(t, t) for t in ids]
            for arq in a.get("arquivos", []):
                md = Path(arq)
                if not md.exists():
                    pendencias.append(f"arquivo sumiu: {md}")
                    continue
                r = reescrever_frontmatter(md, materia_id, ids, titulos)
                if not r:
                    continue
                texto, resumo = r
                tocados.append((md, resumo))
                if args.aplicar:
                    # `.md.bak`, NÃO `.bak.md`: o collector do site varre `*.md` na
                    # pasta do aprofundamento e escolhe o principal por ordem
                    # alfabética — `x.bak.md` vem ANTES de `x.md` e era lido no
                    # lugar do arquivo real, servindo a versão sem o vínculo.
                    md.with_suffix(".md.bak").write_text(
                        md.read_text(encoding="utf-8"), encoding="utf-8")
                    md.write_text(texto, encoding="utf-8")

    modo = "APLICADO" if args.aplicar else "DRY-RUN (nada foi escrito)"
    print(f"{modo}: {len(tocados)} arquivo(s)")
    for md, resumo in tocados[:200]:
        print(f"  {md.name}  ->  {resumo}")
    if sem_topico:
        print(f"\n{len(sem_topico)} assunto(s) ficam SEM tópico (gravados com []):")
        for s in sem_topico:
            print(f"  {s}")
    if pendencias:
        sys.stderr.write("\nPENDÊNCIAS (nada gravado para estes):\n")
        for p in pendencias:
            sys.stderr.write(f"  - {p}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
