#!/usr/bin/env python3
"""
salvar_sessao.py — grava o `storage_state.json` a partir do perfil já logado.

Existe por causa de um defeito da `notebooklm-py` 0.7.3: depois do login ela espera
que a página fique em `notebooklm.google.com`
(`page.wait_for_url` em `cli/services/playwright_login.py`), mas desde o rebrand
"Gemini Notebook" o Google leva a sessão para `notebook.google.com`. A URL nunca
casa, o comando espera os 5 minutos e desiste **sem gravar nada** — embora o login
tenha funcionado e os cookies estejam no perfil persistente.

Este script faz só o passo que faltou: abre o MESMO perfil, confirma que a sessão
está viva e grava o `storage_state.json` onde a biblioteca o procura.

Não faz login e não inventa credencial: sem sessão de pé, ele diz isso e **não
escreve arquivo nenhum** — a credencial é a chave da conta Google inteira, e um
arquivo pela metade seria pior que a ausência dele.

Uso (com a venv onde a notebooklm-py está instalada):
    python3 scripts/salvar_sessao.py [--perfil NOME]

Feche o navegador antes: o perfil fica travado enquanto o Chromium estiver aberto.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Os dois hosts: o novo (pós-rebrand) e o antigo. A sessão vale nos dois — o
# `auth check` mostra `OSID` em ambos —, e visitar os dois garante que os cookies
# de ambos entrem no storage_state.
ALVOS = ("https://notebook.google.com/", "https://notebooklm.google.com/")

# o que a biblioteca exige para considerar a sessão utilizável
COOKIES_DE_SESSAO = (
    ("SID", "__Secure-1PSIDTS"),
    ("OSID",),
    ("APISID", "SAPISID"),
)


def _dependencias():
    """Importa o que é opcional, com mensagem útil em vez de traceback."""
    try:
        from notebooklm import paths
    except ImportError:
        sys.stderr.write(
            "ERRO: notebooklm-py não está instalada.\n"
            "  pip install -r skills/concurso-notebooklm/requirements.txt\n")
        return None, None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.stderr.write(
            "ERRO: playwright não está instalado (só é preciso para esta recuperação).\n"
            "  pip install 'notebooklm-py[browser]'\n")
        return None, None
    return paths, sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", default=None,
                    help="perfil da notebooklm-py (padrão: o ativo)")
    args = ap.parse_args()

    paths, sync_playwright = _dependencias()
    if paths is None:
        return 2                      # degradação: falta dependência opcional

    if args.perfil:
        os.environ["NOTEBOOKLM_PROFILE"] = args.perfil

    perfil = Path(paths.get_browser_profile_dir())
    destino = Path(paths.get_storage_path())
    if not perfil.is_dir():
        sys.stderr.write(f"ERRO: perfil não encontrado: {perfil}\n"
                         "Rode `notebooklm login` uma vez antes.\n")
        return 1

    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(
                str(perfil), headless=True, args=["--no-sandbox"])
        except Exception as e:
            sys.stderr.write(
                f"ERRO: não consegui abrir o perfil — feche o navegador antes.\n  {e}\n")
            return 1
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            for url in ALVOS:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                except Exception as e:
                    sys.stderr.write(f"  aviso: {url} não abriu ({type(e).__name__})\n")

            estado = ctx.storage_state()
            nomes = {c["name"] for c in estado.get("cookies", [])}
            if not any(set(grupo) <= nomes for grupo in COOKIES_DE_SESSAO):
                sys.stderr.write(
                    "ERRO: a sessão do Google não está de pé neste perfil.\n"
                    "Refaça o login no navegador e rode isto de novo — nada foi escrito.\n")
                return 1

            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps(estado, indent=2), encoding="utf-8")
            destino.chmod(0o600)
            print(json.dumps({
                "storage_state": str(destino),
                "cookies": len(estado.get("cookies", [])),
                "bytes": destino.stat().st_size,
            }, indent=2, ensure_ascii=False))
            print("\nConfira com: notebooklm auth check", file=sys.stderr)
            return 0
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
