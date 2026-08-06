#!/usr/bin/env python3
"""
nlm_run.py — cria o notebook, sobe as fontes e dispara as gerações.

    # um aprofundamento
    nlm_run.py --aprofundamento <.../assuntos/crase/padrao--pestana>
    # a matéria inteira
    nlm_run.py --assuntos-dir <.../lingua-portuguesa/assuntos> --leis-dir <...>
    # escolher o que gerar (padrão: podcast:deep-dive)
    nlm_run.py --aprofundamento <...> --midias podcast:debate,report
    # conferir sem tocar em nada
    nlm_run.py --assuntos-dir <...> --dry-run

NÃO espera a geração terminar: são minutos por item, e 66 itens seriam horas com um
processo segurando a sessão. Ao final, o relatório diz o comando da coleta.

Códigos de saída, no padrão do `fetch_lei.py`:
    0  tudo que foi pedido foi disparado
    1  rede/auth — instalar não resolve
    2  degradação parcial (biblioteca ausente, ou alguma falha isolada)
    3  argumentos inválidos
    4  quota atingida — retomável com o MESMO comando
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
import plano as plano_mod       # noqa: E402
import porta as porta_mod       # noqa: E402

PACOTE = "_fonte-notebooklm.md"


def pacotes_alvo(args) -> list:
    """Os `_fonte-notebooklm.md` a processar, em ordem estável."""
    if args.aprofundamento:
        p = Path(args.aprofundamento) / PACOTE
        return [p] if p.is_file() else []
    raiz = Path(args.assuntos_dir)
    achados = []
    for assunto in sorted(raiz.iterdir()):
        if not assunto.is_dir():
            continue
        if args.assunto and assunto.name not in args.assunto:
            continue
        achados.extend(sorted(assunto.glob(f"*/{PACOTE}")))
    return achados


def main() -> int:
    ap = argparse.ArgumentParser()
    alvo = ap.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--assuntos-dir", type=Path, help="a matéria inteira")
    alvo.add_argument("--aprofundamento", type=Path, help="uma pasta {nivel}--{fonte}")
    ap.add_argument("--assunto", action="append", default=[],
                    help="restringe a estes slugs (repetível)")
    ap.add_argument("--leis-dir", type=Path, default=None)
    ap.add_argument("--midias", default=None,
                    help="ex.: podcast:deep-dive,report · `nada` · `tudo`")
    ap.add_argument("--publicar", action="store_true",
                    help="ativa o link público do notebook (padrão: não)")
    ap.add_argument("--limite", type=int, default=0,
                    help="teto de itens nesta execução (0 = sem teto)")
    ap.add_argument("--forcar", action="store_true",
                    help="regera mesmo com o arquivo já presente")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--executavel", default="notebooklm")
    args = ap.parse_args()

    try:
        midias = plano_mod.parse_midias(args.midias)
    except plano_mod.MidiaInvalida as e:
        sys.stderr.write(f"ERRO: {e}\n")
        return 3

    alvos = pacotes_alvo(args)
    if not alvos:
        sys.stderr.write("Nenhum pacote encontrado. Confira o caminho.\n")
        return 3

    # planeja TUDO antes de tocar na rede: o dry-run tem de ser o mesmo cálculo
    planos, erros = [], []
    for caminho in alvos:
        try:
            pac = pac_mod.ler(caminho)
        except ValueError as e:
            erros.append((str(caminho), str(e)))
            continue
        tarefas, pulados = plano_mod.planejar(pac, midias, forcar=args.forcar)
        planos.append((pac, tarefas, pulados))

    if args.limite:
        planos = planos[:args.limite]

    if args.dry_run:
        print(json.dumps({
            "modo": "dry-run",
            "pacotes": len(planos),
            "a_disparar": sum(len(t) for _, t, _ in planos),
            "itens": [{"pacote": str(p.caminho.parent.name),
                       "notebook": p.nome_notebook,
                       "ja_tem_id": bool(p.notebook_id),
                       "tarefas": [t.rotulo for t in ts],
                       "pulados": [{"tipo": k, "motivo": m} for k, m in pl]}
                      for p, ts, pl in planos],
            "erros": erros,
        }, indent=2, ensure_ascii=False))
        return 0

    args.executavel = porta_mod.PortaCLI.achar_executavel(args.executavel)
    if not porta_mod.PortaCLI.disponivel(args.executavel):
        sys.stderr.write(
            f"ERRO: `{args.executavel}` não encontrado.\n"
            "  pip install -r skills/concurso-notebooklm/requirements.txt\n"
            "O pacote manual continua completo — veja o `_fonte-notebooklm.md`.\n")
        return 2

    porta = porta_mod.PortaCLI(args.executavel)
    relatorios, quota, falhou = [], False, bool(erros)
    for pac, tarefas, pulados in planos:
        try:
            rel = exe_mod.executar(pac, tarefas, porta, leis_dir=args.leis_dir,
                                   publicar=args.publicar)
        except porta_mod.ErroDaPorta as e:
            sys.stderr.write(f"ERRO de rede/auth em {pac.pasta.name}: {e}\n")
            return 1
        rel.pulados.extend(pulados)
        relatorios.append((pac, rel))
        quota = quota or bool(rel.sem_quota)
        falhou = falhou or bool(rel.falhas)
        if quota:
            break            # não adianta insistir: a quota é da conta, não do item

    total = sum(len(r.disparadas) for _, r in relatorios)
    print(json.dumps({
        "pacotes": len(relatorios),
        "disparadas": total,
        "erros": erros,
        "itens": [{"pacote": p.pasta.name, "notebook_id": r.notebook_id,
                   "url": r.url, "criou_notebook": r.criou_notebook,
                   "fontes_subidas": r.fontes_subidas,
                   "fontes_faltando": r.fontes_faltando,
                   "disparadas": r.disparadas, "pulados": r.pulados,
                   "sem_quota": r.sem_quota, "falhas": r.falhas}
                  for p, r in relatorios],
    }, indent=2, ensure_ascii=False))

    # O exit code sai do RELATÓRIO, não de um cálculo paralelo. Antes,
    # `Relatorio.codigo_saida` era código morto: aqui se remontava
    # `2 if falhou else 0` à mão e a quota noutro ponto, então a regra vivia num
    # lugar que ninguém lia — e `fontes_faltando` nunca chegava ao chamador.
    pior = max((r.codigo_saida for _, r in relatorios), default=0) if relatorios else 0
    faltando = sorted({n for _, r in relatorios for n in r.fontes_faltando})

    if quota:
        sys.stderr.write(
            "\nParou na quota diária. O teto não é informado pelo servidor — o que se\n"
            "sabe é que ele recusou. Retome amanhã com o MESMO comando: o que já\n"
            "existe é pulado.\n")
        return 4
    if total:
        onde = args.aprofundamento or args.assuntos_dir
        sys.stderr.write(
            f"\n{total} geração(ões) pedida(s). Elas levam minutos. Colete com:\n"
            f"  python3 {AQUI / 'nlm_coleta.py'} "
            f"{'--aprofundamento' if args.aprofundamento else '--assuntos-dir'} {onde}\n")
    if faltando:
        # Aviso junto do bloco final: mensagem no meio de saída longa não se lê.
        sys.stderr.write(
            f"\nATENÇÃO: {len(faltando)} fonte(s) declarada(s) NÃO encontrada(s) em disco —\n"
            f"o notebook foi montado sem ela(s): {', '.join(faltando)}\n")
    return max(pior, 2) if falhou else pior


if __name__ == "__main__":
    sys.exit(main())
