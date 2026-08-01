#!/usr/bin/env python3
"""
pacote.py — ler e escrever o `_fonte-notebooklm.md`.

É o ÚNICO módulo desta skill que toca o arquivo do pacote. Todo o resto trabalha
sobre o objeto `Pacote`, o que mantém a decisão do que gerar testável sem disco e
sem rede.

O pacote é gerado pela `concurso-aprofunda` e já é contrato completo: o frontmatter
declara o nome do notebook e o nome de cada arquivo de saída, e o corpo traz as
fontes a subir e um prompt por gerável. Nada aqui recalcula esses valores — extrair
nome de arquivo de texto corrido foi exatamente o defeito que fez o roteiro do mapa
mental e o do report chegarem vazios ao site.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Título do H2 → chave do gerável. As chaves são as do `CATALOGO_MIDIAS` da
# `concurso-publica`, para o nome do arquivo salvo casar com o que o site detecta.
SECOES_PROMPT = (
    ("podcast", re.compile(r"podcast|audio overview", re.I)),
    ("mapa_mental", re.compile(r"mapa mental|mind map", re.I)),
    ("video", re.compile(r"v[íi]deo|video overview", re.I)),
    ("report", re.compile(r"report|relat[óo]rio", re.I)),
)

FRONTMATTER = re.compile(r"^(---\s*\n)(.*?)(\n---\s*\n)", re.DOTALL)
LINHA_CHAVE = re.compile(r"^([a-z_][a-z0-9_]*):\s*(.*)$", re.MULTILINE)
ITEM_FONTE = re.compile(r"^\d+\.\s+(?:\*\((?:Refer[êe]ncia)\)\*\s*)?(.*)$", re.MULTILINE)
NOME_EM_CRASE = re.compile(r"`([^`]+)`")


@dataclass
class Pacote:
    caminho: Path
    campos: dict = field(default_factory=dict)      # frontmatter inteiro
    prompts: dict = field(default_factory=dict)     # chave → texto do prompt
    fontes: list = field(default_factory=list)      # nomes de arquivo, na ordem

    @property
    def pasta(self) -> Path:
        return self.caminho.parent

    @property
    def nome_notebook(self) -> str:
        return self.campos.get("nome_notebook", "")

    @property
    def notebook_id(self) -> str:
        return self.campos.get("notebooklm_id", "")

    @property
    def url(self) -> str:
        return self.campos.get("notebooklm_url", "")

    @property
    def status(self) -> str:
        return self.campos.get("notebooklm_status", "nao-criado")

    def arquivo_de(self, tipo: str) -> str:
        """O nome com que salvar o gerável, como o pacote o declara."""
        return self.campos.get(f"arquivo_{tipo}", "")


def _desaspar(valor: str) -> str:
    v = valor.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def ler(caminho: Path) -> Pacote:
    """Lê o pacote. Levanta `ValueError` se não for um pacote reconhecível.

    Falhar alto é deliberado: um pacote sem frontmatter é sinal de arquivo truncado
    ou de outra coisa com o mesmo nome, e seguir em frente criaria um notebook sem
    saber para qual assunto.
    """
    if not caminho.is_file():
        raise ValueError(f"pacote inexistente: {caminho}")
    txt = caminho.read_text(encoding="utf-8")
    m = FRONTMATTER.match(txt)
    if not m:
        raise ValueError(f"pacote sem frontmatter: {caminho}")

    campos = {}
    for linha in m.group(2).split("\n"):
        if linha.lstrip().startswith("#"):
            continue                      # comentário do template
        achado = LINHA_CHAVE.match(linha)
        if achado:
            campos[achado.group(1)] = _desaspar(achado.group(2))

    corpo = txt[m.end():]
    return Pacote(caminho=caminho, campos=campos,
                  prompts=_prompts_do_corpo(corpo), fontes=_fontes_do_corpo(corpo))


def _prompts_do_corpo(corpo: str) -> dict:
    """Um prompt por gerável, do primeiro bloco cercado de cada seção.

    O texto vai para o NotebookLM como está: é o prompt curado pela skill anterior,
    ancorado na nota do vault. Reescrevê-lo aqui seria ter duas versões do mesmo
    prompt, e a do site (que o usuário copia à mão) divergiria da automatizada.
    """
    achados = {}
    for bloco in re.split(r"^##\s+", corpo, flags=re.MULTILINE)[1:]:
        linhas = bloco.split("\n")
        titulo = linhas[0].strip()
        cercas = re.findall(r"^```\s*\n(.*?)^```", "\n".join(linhas[1:]),
                            re.MULTILINE | re.DOTALL)
        if not cercas:
            continue
        for chave, padrao in SECOES_PROMPT:
            if padrao.search(titulo):
                achados.setdefault(chave, cercas[0].strip())
                break
    return achados


def _fontes_do_corpo(corpo: str) -> list:
    """Os nomes de arquivo da seção 1, na ordem em que devem ser subidos."""
    for bloco in re.split(r"^##\s+", corpo, flags=re.MULTILINE)[1:]:
        linhas = bloco.split("\n")
        if not re.search(r"fontes para subir", linhas[0], re.I):
            continue
        nomes = []
        for item in ITEM_FONTE.findall("\n".join(linhas[1:])):
            achado = NOME_EM_CRASE.search(item)
            if achado:
                nomes.append(achado.group(1))
        return nomes
    return []


def resolver_fontes(pac: Pacote, leis_dir: Path | None = None) -> tuple[list, list]:
    """Casa cada nome de fonte com um arquivo no disco.

    A primeira fonte é a nota do assunto, que vive ao lado do pacote; as demais são
    leis, que vivem na pasta de leis-baixadas do concurso. Devolve
    `(existentes, faltando)` — fonte que não existe vira PENDÊNCIA nomeada, nunca
    upload silencioso de menos.
    """
    existentes, faltando = [], []
    for nome in pac.fontes:
        candidatos = [pac.pasta / nome]
        if leis_dir:
            candidatos.append(Path(leis_dir) / nome)
        achado = next((c for c in candidatos if c.is_file()), None)
        (existentes.append(achado) if achado else faltando.append(nome))
    return existentes, faltando


def gravar_campos(caminho: Path, campos: dict) -> None:
    """Reescreve SÓ as chaves dadas no frontmatter, preservando o resto.

    Escrita atômica (arquivo temporário na mesma pasta + `os.replace`): o pacote é
    documento do vault, sincronizado com o Drive, e uma escrita interrompida no meio
    deixaria o usuário sem o roteiro. Chave que ainda não existe é acrescentada ao
    fim do frontmatter — é o caso do `notebooklm_id` na primeira execução.
    """
    txt = caminho.read_text(encoding="utf-8")
    m = FRONTMATTER.match(txt)
    if not m:
        raise ValueError(f"pacote sem frontmatter: {caminho}")

    linhas = m.group(2).split("\n")
    pendentes = dict(campos)
    for i, linha in enumerate(linhas):
        achado = LINHA_CHAVE.match(linha)
        if achado and achado.group(1) in pendentes:
            chave = achado.group(1)
            linhas[i] = f'{chave}: "{pendentes.pop(chave)}"'
    for chave, valor in pendentes.items():
        linhas.append(f'{chave}: "{valor}"')

    novo = m.group(1) + "\n".join(linhas) + m.group(3) + txt[m.end():]
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False,
                                      dir=str(caminho.parent),
                                      prefix=".tmp-", suffix=".md")
    try:
        tmp.write(novo)
        tmp.close()
        os.replace(tmp.name, caminho)
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)
        raise
