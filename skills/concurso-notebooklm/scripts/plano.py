#!/usr/bin/env python3
"""
plano.py — decidir o que gerar, e com que nome salvar.

Puro: só lê `Pacote` e checa presença de arquivo. Nenhuma rede, nenhum import da
biblioteca do NotebookLM. É aqui que mora o comportamento — a fronteira de rede
(`porta.py`) só executa o que este módulo decidiu.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pacote import Pacote

# Cada gerável: variantes aceitas e a variante padrão.
# `mapa_mental` está FORA de propósito — ver `MAPA_MENTAL_FORA`.
GERAVEIS = {
    "podcast": (("deep-dive", "brief", "critique", "debate"), "deep-dive"),
    "video": (("explainer", "brief"), "explainer"),
    "report": (("custom", "study-guide", "briefing", "blog"), "custom"),
}

# O default é só o podcast. O mapa mental saiu do default por decisão do dono do
# repo, e a razão é técnica: a biblioteca não aceita prompt customizado para mapa
# mental (o `PROMPT_MINDMAP` do pacote não seria enviado) e o download vem em JSON,
# formato que o `CATALOGO_MIDIAS` da concurso-publica não reconhece — o arquivo
# ficaria invisível no site. Enquanto isso não se resolver, mapa mental é manual.
PADRAO = ("podcast:deep-dive",)

MAPA_MENTAL_FORA = (
    "mapa mental está fora da automação por ora: a biblioteca não aceita prompt "
    "customizado para ele e o download vem em JSON, que o site não reconhece como "
    "mídia. Gere-o à mão pelo roteiro da seção 3 do pacote."
)

TOKENS_ESPECIAIS = ("nada", "tudo")


class MidiaInvalida(ValueError):
    """Argumento de --midias que não dá para atender. Vira exit 3."""


@dataclass(frozen=True)
class Tarefa:
    tipo: str            # podcast | video | report
    variante: str        # deep-dive, explainer, custom…
    arquivo: str         # nome com que salvar, vindo do pacote
    prompt: str          # o prompt curado, como está no pacote

    @property
    def rotulo(self) -> str:
        return f"{self.tipo}:{self.variante}"


def parse_midias(texto: str | None) -> list:
    """`"podcast:debate,report"` → `[("podcast","debate"), ("report","custom")]`.

    Valida à mão porque `argparse` não valida CSV — mesmo caminho do `--formatos`
    do `fetch_lei.py`. Token inválido nomeia as opções válidas em vez de falhar seco.
    """
    bruto = (texto or ",".join(PADRAO)).strip()
    if not bruto or bruto == "nada":
        return []
    if bruto == "tudo":
        return [(t, GERAVEIS[t][1]) for t in GERAVEIS]

    escolhidas, vistos = [], set()
    for pedaco in bruto.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        tipo, _, variante = pedaco.partition(":")
        tipo = tipo.strip().replace("-", "_")
        variante = variante.strip()

        if tipo == "mapa_mental":
            raise MidiaInvalida(MAPA_MENTAL_FORA)
        if tipo not in GERAVEIS:
            validos = ", ".join(sorted(GERAVEIS)) + ", " + ", ".join(TOKENS_ESPECIAIS)
            raise MidiaInvalida(f"gerável desconhecido: {pedaco!r}. Válidos: {validos}")

        aceitas, padrao = GERAVEIS[tipo]
        if variante and variante not in aceitas:
            raise MidiaInvalida(
                f"variante desconhecida para {tipo}: {variante!r}. "
                f"Válidas: {', '.join(aceitas)}")
        if tipo in vistos:
            raise MidiaInvalida(f"{tipo} pedido mais de uma vez")
        vistos.add(tipo)
        escolhidas.append((tipo, variante or padrao))
    return escolhidas


def ja_existe(pac: Pacote, tipo: str) -> bool:
    """Presença de arquivo é o sinal de 'feito'.

    Mesma regra que o site usa para detectar mídia — um segundo lugar guardando
    'isto já foi gerado' envelheceria em desacordo com o disco.
    """
    nome = pac.arquivo_de(tipo)
    if nome and (pac.pasta / nome).is_file():
        return True
    # tolera outra extensão da mesma família: o container real do download pode não
    # ser o declarado, e regerar por causa disso queimaria quota à toa
    if not nome:
        return False
    prefixo = nome.split(".")[0]
    return any(p.is_file() for p in pac.pasta.glob(f"{prefixo}.*"))


def planejar(pac: Pacote, midias: list, forcar: bool = False) -> tuple[list, list]:
    """Devolve `(tarefas, pulados)` para um pacote.

    `pulados` é lista de `(tipo, motivo)` — e existe para o relatório poder dizer
    por que não fez, em vez de silenciar.
    """
    tarefas, pulados = [], []
    for tipo, variante in midias:
        if not forcar and ja_existe(pac, tipo):
            pulados.append((tipo, "já existe arquivo na pasta"))
            continue
        arquivo = pac.arquivo_de(tipo)
        if not arquivo:
            pulados.append((tipo, f"o pacote não declara `arquivo_{tipo}`"))
            continue
        prompt = pac.prompts.get(tipo, "")
        if not prompt:
            pulados.append((tipo, "o pacote não traz prompt para este gerável"))
            continue
        tarefas.append(Tarefa(tipo=tipo, variante=variante,
                              arquivo=arquivo, prompt=prompt))
    return tarefas, pulados


def url_do_notebook(notebook_id: str) -> str:
    """O endereço do notebook é derivável do id — não custa uma chamada de rede.

    Compartilhar publicamente é OUTRA coisa (`sharing.set_public`), tem efeito de
    acesso e fica atrás de flag própria.
    """
    if not notebook_id:
        return ""
    return f"https://notebooklm.google.com/notebook/{notebook_id}"


def extensao_de(nome: str) -> str:
    return Path(nome).suffix.lower()


def container_dos_bytes(cabecalho: bytes) -> str:
    """Adivinha o container por assinatura, para não confiar na extensão declarada.

    A biblioteca grava no caminho que recebe: se pedirmos `.m4a` e vier MP3, o
    arquivo fica com nome errado e o site — que casa prefixo E extensão — não o vê.
    Silêncio é o pior desfecho, então a extensão sai dos bytes.
    """
    if len(cabecalho) >= 12 and cabecalho[4:8] == b"ftyp":
        return ".m4a"
    if cabecalho[:3] == b"ID3" or cabecalho[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    if cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WAVE":
        return ".wav"
    if cabecalho[:4] == b"OggS":
        return ".ogg"
    if re.match(rb"\s*(<!DOCTYPE|<html)", cabecalho, re.I):
        return ".html"
    return ""
