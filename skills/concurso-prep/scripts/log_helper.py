#!/usr/bin/env python3
"""
log_helper.py - Utilitário simples de logging para a skill concurso-prep.

Uso:
    python log_helper.py init <vault-logs-dir>
        Cria diretório de logs e inicia novo arquivo de execução.
        Retorna no stdout o caminho do arquivo de log criado.

    python log_helper.py event <log-file> <event-name> [--data <json-string>]
        Registra um evento no log. data é opcional (info adicional).

    python log_helper.py end <log-file> [--status ok|fail|partial]
        Finaliza o log, calculando duração total.

    python log_helper.py pendencia <vault-logs-dir> <descricao>
        Adiciona linha em pendencias.md.

    python log_helper.py download-falho <vault-logs-dir> <url> <motivo>
        Adiciona linha em downloads-falhos.md.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path


def cmd_init(args):
    logs_dir = Path(args.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = logs_dir / f"execucao-{ts}.log"
    with log_file.open("w", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] START\n")
    print(str(log_file))


def cmd_event(args):
    with open(args.log_file, "a", encoding="utf-8") as f:
        line = f"[{datetime.now().isoformat()}] {args.event_name}"
        if args.data:
            line += f" | {args.data}"
        f.write(line + "\n")


def cmd_end(args):
    log_file = Path(args.log_file)
    # Calcula duração lendo a primeira linha
    start = None
    with log_file.open("r", encoding="utf-8") as f:
        first = f.readline().strip()
        if first.startswith("["):
            start_str = first[1:first.index("]")]
            start = datetime.fromisoformat(start_str)
    end = datetime.now()
    duration = (end - start).total_seconds() if start else 0
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"[{end.isoformat()}] END status={args.status} duration_seconds={duration:.1f}\n")
    print(f"Log finalizado: {log_file} (duração {duration:.1f}s)")


def cmd_pendencia(args):
    logs_dir = _resolver_logs_dir(args.logs_dir, getattr(args, "concurso", None))
    pend = logs_dir / "pendencias.md"
    header = "# Pendências\n\nItens que precisam de ação manual.\n\n"
    if not pend.exists():
        pend.write_text(header, encoding="utf-8")
    with pend.open("a", encoding="utf-8") as f:
        f.write(f"- [ ] [{datetime.now().date()}] {args.descricao}\n")


def cmd_download_falho(args):
    logs_dir = _resolver_logs_dir(args.logs_dir, getattr(args, "concurso", None))
    df = logs_dir / "downloads-falhos.md"
    header = "# Downloads Falhos\n\nURLs que falharam — tentar manualmente.\n\n"
    if not df.exists():
        df.write_text(header, encoding="utf-8")
    with df.open("a", encoding="utf-8") as f:
        f.write(f"- [{datetime.now().isoformat()}] `{args.url}` — {args.motivo}\n")


def _resolver_logs_dir(logs_dir: str, concurso: str | None) -> Path:
    """Item 15: se 'concurso' for dado, usa .logs/{concurso}/ para não misturar
    logs de concursos diferentes. Caso contrário, usa a pasta como veio."""
    base = Path(logs_dir)
    if concurso:
        base = base / concurso
    base.mkdir(parents=True, exist_ok=True)
    return base


def cmd_download_suspeito(args):
    """Item 12: registra download de fora da whitelist (não bloqueado, mas auditável)."""
    logs_dir = _resolver_logs_dir(args.logs_dir, args.concurso)
    ds = logs_dir / "downloads-suspeitos.md"
    header = ("# Downloads Suspeitos\n\nURLs baixadas de fora da whitelist "
              "de domínios confiáveis. Revise a procedência.\n\n")
    if not ds.exists():
        ds.write_text(header, encoding="utf-8")
    with ds.open("a", encoding="utf-8") as f:
        f.write(f"- [{datetime.now().isoformat()}] `{args.url}` — {args.motivo}\n")


def main():
    parser = argparse.ArgumentParser(description="Log helper para concurso-prep")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("logs_dir")
    p_init.set_defaults(func=cmd_init)

    p_event = sub.add_parser("event")
    p_event.add_argument("log_file")
    p_event.add_argument("event_name")
    p_event.add_argument("--data", default=None)
    p_event.set_defaults(func=cmd_event)

    p_end = sub.add_parser("end")
    p_end.add_argument("log_file")
    p_end.add_argument("--status", default="ok", choices=["ok", "fail", "partial"])
    p_end.set_defaults(func=cmd_end)

    p_pend = sub.add_parser("pendencia")
    p_pend.add_argument("logs_dir")
    p_pend.add_argument("descricao")
    p_pend.add_argument("--concurso", default=None, help="subpasta por concurso (item 15)")
    p_pend.set_defaults(func=cmd_pendencia)

    p_df = sub.add_parser("download-falho")
    p_df.add_argument("logs_dir")
    p_df.add_argument("url")
    p_df.add_argument("motivo")
    p_df.add_argument("--concurso", default=None, help="subpasta por concurso (item 15)")
    p_df.set_defaults(func=cmd_download_falho)

    p_ds = sub.add_parser("download-suspeito")
    p_ds.add_argument("logs_dir")
    p_ds.add_argument("url")
    p_ds.add_argument("motivo")
    p_ds.add_argument("--concurso", default=None, help="subpasta por concurso (item 15)")
    p_ds.set_defaults(func=cmd_download_suspeito)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
