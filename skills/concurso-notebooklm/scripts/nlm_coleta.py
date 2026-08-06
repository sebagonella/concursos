#!/usr/bin/env python3
"""
nlm_coleta.py — baixa o que ficou pronto e salva com o nome que o site reconhece.

    nlm_coleta.py --aprofundamento <.../assuntos/crase/padrao--pestana>
    nlm_coleta.py --assuntos-dir <.../lingua-portuguesa/assuntos>

Roda quantas vezes quiser: o que já está no disco é pulado, e o que ainda está
gerando continua no sidecar para a próxima passada.

A extensão do arquivo salvo sai dos BYTES, não da declaração — o site casa prefixo e
extensão, então nome errado não vira outro tipo de mídia, vira invisível.

Códigos de saída: 0 tudo coletado · 1 rede/auth · 2 degradação parcial ·
3 argumentos inválidos.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import executor as exe_mod      # noqa: E402
import pacote as pac_mod        # noqa: E402
import porta as porta_mod       # noqa: E402
from nlm_run import pacotes_alvo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    alvo = ap.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--assuntos-dir", type=Path)
    alvo.add_argument("--aprofundamento", type=Path)
    ap.add_argument("--assunto", action="append", default=[])
    ap.add_argument("--ignorar-idade", action="store_true",
                    help="não desistir de tarefa antiga (padrão: desiste após 6h)")
    ap.add_argument("--executavel", default="notebooklm")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    alvos = pacotes_alvo(args)
    if not alvos:
        sys.stderr.write("Nenhum pacote encontrado. Confira o caminho.\n")
        return 3

    pendentes = []
    for caminho in alvos:
        try:
            pac = pac_mod.ler(caminho)
        except ValueError:
            continue
        estado = exe_mod._ler_sidecar(pac.pasta)
        if estado.get("tarefas"):
            pendentes.append((pac, estado["tarefas"]))

    if args.dry_run:
        print(json.dumps({
            "modo": "dry-run",
            "com_tarefas_em_voo": len(pendentes),
            "itens": [{"pacote": p.pasta.name,
                       "tarefas": [{"tipo": t["tipo"], "pedido_em": t.get("pedido_em")}
                                   for t in ts]}
                      for p, ts in pendentes],
        }, indent=2, ensure_ascii=False))
        return 0

    if not pendentes:
        print(json.dumps({"coletadas": 0,
                          "nota": "nenhuma geração em voo — nada a coletar"},
                         indent=2, ensure_ascii=False))
        return 0

    args.executavel = porta_mod.PortaCLI.achar_executavel(args.executavel)
    if not porta_mod.PortaCLI.disponivel(args.executavel):
        sys.stderr.write(f"ERRO: `{args.executavel}` não encontrado.\n"
                         "  pip install -r skills/concurso-notebooklm/requirements.txt\n")
        return 2

    porta = porta_mod.PortaCLI(args.executavel)
    itens, baixadas, falhou, rels = [], 0, False, []
    for pac, _ in pendentes:
        try:
            rel = exe_mod.coletar(pac, porta, forcar_idade=args.ignorar_idade)
        except porta_mod.ErroDaPorta as e:
            sys.stderr.write(f"ERRO de rede/auth em {pac.pasta.name}: {e}\n")
            return 1
        rels.append(rel)
        baixadas += len(rel.baixadas)
        falhou = falhou or bool(rel.falhas)
        itens.append({"pacote": pac.pasta.name, "baixadas": rel.baixadas,
                      "falhas": rel.falhas,
                      "ainda_gerando": pac_mod.ler(pac.caminho).status == "gerando"})

    print(json.dumps({"coletadas": baixadas, "itens": itens},
                     indent=2, ensure_ascii=False))
    if any(i["ainda_gerando"] for i in itens):
        sys.stderr.write("\nAinda há geração em voo. Rode este mesmo comando de novo "
                         "em alguns minutos.\n")
    elif baixadas:
        sys.stderr.write("\nPronto. Republique o site para o material aparecer:\n"
                         "  skills/concurso-publica — site_collector + site_builder\n")
    # Mesmo motivo do nlm_run: o código de saída é do relatório, não recomputado.
    pior = max((r.codigo_saida for r in rels), default=0)
    return max(pior, 2) if falhou else pior


if __name__ == "__main__":
    sys.exit(main())
