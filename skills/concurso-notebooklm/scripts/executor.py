#!/usr/bin/env python3
"""
executor.py — junta plano e porta: cria o notebook, sobe as fontes, dispara e coleta.

Puro no sentido que importa: recebe a porta como argumento e nunca a constrói. Toda
a suíte roda com a `PortaFalsa`, sem rede.

Onde cada coisa mora, e por quê:

- **Durável e humano → frontmatter do pacote** (`notebooklm_id`, `notebooklm_url`,
  `notebooklm_status`, `notebooklm_gerado_em`). São poucos, o usuário os lê no
  Obsidian e o site os publica.
- **Volátil e de máquina → sidecar `_notebooklm-estado.json`** (os `task_id` em voo).
  Não vão para o frontmatter por três razões: são ruído num documento curado; mudam a
  cada execução, e cada mudança dispara o backup `.bak.md` do gerador; e um `task_id`
  velho é indistinguível de um vivo, porque a consulta devolve "pendente" para tarefa
  desconhecida. O nome começa com `_`, então o coletor do site já o ignora.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pacote as pac_mod
import plano as plano_mod
import porta as porta_mod

SIDECAR = "_notebooklm-estado.json"

# quanto tempo uma tarefa pode ficar "pendente" antes de virar erro. A consulta
# devolve "pendente" para task_id desconhecido, então sem um teto a coleta esperaria
# para sempre por algo que já morreu.
IDADE_MAXIMA_H = 6


@dataclass
class Relatorio:
    notebook_id: str = ""
    url: str = ""
    criou_notebook: bool = False
    fontes_subidas: list = field(default_factory=list)
    fontes_faltando: list = field(default_factory=list)
    disparadas: list = field(default_factory=list)
    pulados: list = field(default_factory=list)
    baixadas: list = field(default_factory=list)
    falhas: list = field(default_factory=list)
    sem_quota: list = field(default_factory=list)

    def como_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @property
    def codigo_saida(self) -> int:
        if self.sem_quota:
            return 4                       # retomável: mesmo comando amanhã
        if self.falhas:
            return 2                       # degradação parcial
        if self.fontes_faltando:
            # Notebook criado sem a lei declarada não é sucesso. A "pendência
            # nomeada" ia só para o stdout — quem automatiza olha o código de
            # saída, e ele dizia que estava tudo bem.
            return 2
        return 0


def _ler_sidecar(pasta: Path) -> dict:
    p = pasta / SIDECAR
    if not p.is_file():
        return {"tarefas": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tarefas": []}


def _gravar_sidecar(pasta: Path, dados: dict) -> None:
    (pasta / SIDECAR).write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")


def garantir_notebook(pac, porta, rel: Relatorio, hoje: str) -> str:
    """Cria o notebook só se ainda não houver um.

    Sem esta checagem, reexecutar sobre uma matéria de 66 assuntos criaria 66
    notebooks duplicados e queimaria a quota do dia.
    """
    if pac.notebook_id:
        rel.notebook_id = pac.notebook_id
        return pac.notebook_id
    nb = porta.criar_notebook(pac.nome_notebook)
    rel.notebook_id = nb
    rel.criou_notebook = True
    pac_mod.gravar_campos(pac.caminho, {
        "notebooklm_id": nb,
        "notebooklm_url": plano_mod.url_do_notebook(nb),
        "notebooklm_status": "criado",
        "notebooklm_gerado_em": hoje,
    })
    return nb


def garantir_fontes(pac, nb: str, porta, rel: Relatorio, leis_dir: Path | None) -> None:
    """Sobe o que falta, pelo NOME. Ressubir duplicaria a cada execução."""
    existentes, faltando = pac_mod.resolver_fontes(pac, leis_dir)
    rel.fontes_faltando = faltando
    ja_la = set(porta.listar_fontes(nb))
    for caminho in existentes:
        if caminho.name in ja_la:
            continue
        porta.subir_fonte(nb, caminho)
        rel.fontes_subidas.append(caminho.name)

    # O que subiu fica GRAVADO, não só relatado. Sem isto não há como saber com
    # que fontes um podcast foi feito sem abrir o notebook — e o relatório morre
    # no stdout da execução.
    #
    # O prefixo `notebooklm_` é deliberado: `herdar_campos` herda por prefixo, e
    # por isso estes campos sobrevivem a toda regeração futura do pacote sem
    # precisar de código novo. `ja_la` entra na conta porque uma fonte que já
    # estava no notebook também sustenta a mídia gerada.
    pac_mod.gravar_campos(pac.caminho, {
        "notebooklm_fontes_subidas": ", ".join(sorted(ja_la | set(rel.fontes_subidas))),
        "notebooklm_fontes_faltando": ", ".join(faltando),
    })


def executar(pac, tarefas: list, porta, *, leis_dir: Path | None = None,
             publicar: bool = False, hoje: str | None = None) -> Relatorio:
    """Cria o notebook, sobe as fontes e dispara as tarefas. Não espera."""
    hoje = hoje or date.today().isoformat()
    rel = Relatorio()
    nb = garantir_notebook(pac, porta, rel, hoje)
    garantir_fontes(pac, nb, porta, rel, leis_dir)

    if publicar:
        url = porta.publicar(nb)
        rel.url = url or plano_mod.url_do_notebook(nb)
        pac_mod.gravar_campos(pac.caminho, {"notebooklm_url": rel.url})
    else:
        rel.url = pac_mod.ler(pac.caminho).url or plano_mod.url_do_notebook(nb)

    estado = _ler_sidecar(pac.pasta)
    estado["notebook_id"] = nb
    tipos_sem_quota = set()

    for t in tarefas:
        # a quota é POR TIPO: estourar áudio não deve impedir report, que tem teto
        # próprio e muito mais folgado
        if t.tipo in tipos_sem_quota:
            rel.pulados.append((t.tipo, "quota do tipo já estourou nesta execução"))
            continue
        r = porta.gerar(nb, t.tipo, t.prompt,
                        {"variante": t.variante, "idioma": "pt_BR"})
        if r.estado == porta_mod.SEM_QUOTA:
            tipos_sem_quota.add(t.tipo)
            rel.sem_quota.append((t.tipo, r.detalhe))
            continue
        if r.estado == porta_mod.FALHOU:
            rel.falhas.append((t.tipo, r.detalhe))
            continue
        rel.disparadas.append((t.tipo, r.task_id))
        estado["tarefas"] = [x for x in estado.get("tarefas", [])
                             if x.get("tipo") != t.tipo]
        estado["tarefas"].append({"tipo": t.tipo, "task_id": r.task_id,
                                  "pedido_em": hoje, "arquivo": t.arquivo})

    _gravar_sidecar(pac.pasta, estado)
    if rel.disparadas:
        pac_mod.gravar_campos(pac.caminho, {"notebooklm_status": "gerando"})
    return rel


def coletar(pac, porta, *, hoje: str | None = None, forcar_idade: bool = False) -> Relatorio:
    """Baixa o que ficou pronto e nomeia pelo container REAL."""
    hoje = hoje or date.today().isoformat()
    rel = Relatorio(notebook_id=pac.notebook_id, url=pac.url)
    if not pac.notebook_id:
        rel.falhas.append(("*", "o pacote não tem `notebooklm_id` — nada a coletar"))
        return rel

    estado = _ler_sidecar(pac.pasta)
    pendentes = estado.get("tarefas", [])
    if not pendentes:
        return rel

    mapa = porta.estados(pac.notebook_id)          # UMA listagem por notebook
    restantes = []
    for tarefa in pendentes:
        r = mapa.get(tarefa["task_id"])
        if r is None or not r.acabou:
            velha = (not forcar_idade
                     and _dias(tarefa.get("pedido_em", hoje), hoje) * 24 > IDADE_MAXIMA_H)
            if velha:
                rel.falhas.append((tarefa["tipo"],
                                   "tarefa pendente há tempo demais — pode não existir mais"))
                continue
            restantes.append(tarefa)
            continue
        if r.estado == porta_mod.FALHOU:
            rel.falhas.append((tarefa["tipo"], r.detalhe or "geração falhou"))
            continue

        destino = _baixar_e_nomear(pac, porta, tarefa, r, rel)
        if destino is not None:
            rel.baixadas.append(destino.name)

    estado["tarefas"] = restantes
    _gravar_sidecar(pac.pasta, estado)

    if restantes:
        novo_status = "gerando"
    elif rel.falhas:
        novo_status = "parcial"
    else:
        novo_status = "completo"
    pac_mod.gravar_campos(pac.caminho, {"notebooklm_status": novo_status})
    return rel


def _baixar_e_nomear(pac, porta, tarefa: dict, r, rel: Relatorio):
    """Baixa para um `.parcial` e só então decide o nome, pelos bytes.

    O site casa prefixo E extensão: nome com extensão errada não vira outro tipo de
    mídia — vira invisível. Por isso a extensão sai do arquivo, não da declaração; e
    quando divergir, o pacote é corrigido para parar de mentir.
    """
    declarado = tarefa.get("arquivo") or pac.arquivo_de(tarefa["tipo"])
    parcial = pac.pasta / f"{declarado}.parcial"
    try:
        porta.baixar(pac.notebook_id, tarefa["tipo"], r.detalhe or r.task_id, parcial)
    except Exception as e:
        rel.falhas.append((tarefa["tipo"], f"download falhou: {type(e).__name__}"))
        parcial.unlink(missing_ok=True)
        return None

    real = plano_mod.container_dos_bytes(parcial.open("rb").read(16))
    if real == ".html":
        parcial.unlink(missing_ok=True)
        rel.falhas.append((tarefa["tipo"], "o download veio HTML, não mídia"))
        return None

    esperada = Path(declarado).suffix.lower()
    nome = declarado
    if real and real != esperada:
        if real in plano_mod.EXTENSOES_ACEITAS.get(tarefa["tipo"], ()):
            nome = Path(declarado).stem + real
            pac_mod.gravar_campos(pac.caminho, {f"arquivo_{tarefa['tipo']}": nome})
            rel.falhas.append((tarefa["tipo"],
                               f"container {real} != {esperada} — pacote corrigido"))
        else:
            destino = pac.pasta / f"{declarado}{real}.desconhecido"
            parcial.replace(destino)
            rel.falhas.append((tarefa["tipo"],
                               f"container {real} não é reconhecido pelo site"))
            return None

    destino = pac.pasta / nome
    parcial.replace(destino)
    return destino


def _dias(de: str, ate: str) -> int:
    try:
        return (date.fromisoformat(ate) - date.fromisoformat(de)).days
    except ValueError:
        return 0
