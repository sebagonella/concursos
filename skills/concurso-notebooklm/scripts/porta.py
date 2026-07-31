#!/usr/bin/env python3
"""
porta.py — a fronteira com o NotebookLM. É o único lugar que fala com o mundo.

Duas decisões que sustentam o resto:

**A fronteira é a CLI, não a API Python.** A `notebooklm-py` expõe as duas, mas a
API é `async` e mora em módulos com underscore, que o próprio projeto declara
instáveis; a CLI é a superfície pública, devolve JSON com `--json` e é a que foi
verificada em campo. Falar com ela por subprocess mantém esta skill **síncrona** —
como o resto do repositório, que não tem uma linha de `async` — e é o mesmo padrão
que o `fetch_lei.py` usa para o `pdftotext` e o `fix_notebooklm_packs.py` para o
gerador. Também torna a degradação trivial: sem o executável, não há o que importar.

**O vocabulário de estado é nosso.** `Resultado.estado` não repete os nomes da
biblioteca. É o que faz a fronteira sobreviver ao Google renomear coisas: quando
quebrar, quebra aqui, num arquivo só.

A `PortaFalsa` vive NESTE módulo, ao lado do Protocol, de propósito — dublê e
interface não podem divergir sem alguém ver. Não existe flag para usá-la em
produção: não se embarca um jeito de fingir sucesso.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

# estados que o executor entende — fechado de propósito
PENDENTE, PROCESSANDO, PRONTO, FALHOU, SEM_QUOTA = (
    "pendente", "processando", "pronto", "falhou", "sem-quota")

# como cada gerável se chama na CLI (`notebooklm generate <sub>`)
SUBCOMANDO = {"podcast": "audio", "video": "video", "report": "report"}


@dataclass(frozen=True)
class Resultado:
    estado: str
    task_id: str = ""
    detalhe: str = ""

    @property
    def acabou(self) -> bool:
        return self.estado in (PRONTO, FALHOU, SEM_QUOTA)


class PortaNotebookLM(Protocol):
    """O que o executor precisa do mundo. Nada além disto."""

    def criar_notebook(self, titulo: str) -> str: ...
    def listar_fontes(self, nb: str) -> list: ...
    def subir_fonte(self, nb: str, caminho: Path) -> str: ...
    def gerar(self, nb: str, tipo: str, prompt: str, opcoes: dict) -> Resultado: ...
    def estados(self, nb: str) -> dict: ...
    def baixar(self, nb: str, tipo: str, artifact_id: str, destino: Path) -> Path: ...
    def publicar(self, nb: str) -> str: ...


# --------------------------------------------------------------------------- #
# dublê — para os testes, e só para eles
# --------------------------------------------------------------------------- #
@dataclass
class PortaFalsa:
    """Dublê determinístico, sem rede.

    `roteiro` programa a n-ésima resposta por tipo, para exercitar quota e falha:
        PortaFalsa(roteiro={"podcast": ["pronto", "sem-quota"]})
    `chamadas` guarda `(metodo, kwargs)` — é dele que os testes fazem as asserções.
    """
    roteiro: dict = field(default_factory=dict)
    fontes: dict = field(default_factory=dict)
    chamadas: list = field(default_factory=list)
    # 12 bytes de um fMP4 real: é o cabeçalho que o NotebookLM devolve de verdade
    conteudo: bytes = b"\x00\x00\x00\x18ftypdash\x00\x00\x00\x00"
    _n: dict = field(default_factory=dict)
    _seq: int = 0

    def _reg(self, metodo, **kw):
        self.chamadas.append((metodo, kw))

    def criar_notebook(self, titulo: str) -> str:
        self._reg("criar_notebook", titulo=titulo)
        self._seq += 1
        return f"nb-{self._seq}"

    def listar_fontes(self, nb: str) -> list:
        self._reg("listar_fontes", nb=nb)
        return list(self.fontes.get(nb, []))

    def subir_fonte(self, nb: str, caminho: Path) -> str:
        self._reg("subir_fonte", nb=nb, caminho=Path(caminho).name)
        self.fontes.setdefault(nb, []).append(Path(caminho).name)
        return f"src-{len(self.fontes[nb])}"

    def gerar(self, nb: str, tipo: str, prompt: str, opcoes: dict) -> Resultado:
        self._reg("gerar", nb=nb, tipo=tipo, prompt=prompt, opcoes=dict(opcoes))
        i = self._n.get(tipo, 0)
        self._n[tipo] = i + 1
        fila = self.roteiro.get(tipo, [])
        estado = fila[i] if i < len(fila) else PRONTO
        if estado == SEM_QUOTA:
            return Resultado(SEM_QUOTA, "", "quota diária atingida")
        return Resultado(PENDENTE, f"task-{tipo}-{i}")

    def estados(self, nb: str) -> dict:
        """Toda tarefa disparada aparece pronta, com um artifact_id derivado dela."""
        self._reg("estados", nb=nb)
        return {f"task-{tipo}-{i}": Resultado(PRONTO, f"task-{tipo}-{i}", f"art-{tipo}-{i}")
                for tipo, n in self._n.items() for i in range(n)}

    def baixar(self, nb: str, tipo: str, artifact_id: str, destino: Path) -> Path:
        self._reg("baixar", nb=nb, tipo=tipo, artifact_id=artifact_id,
                  destino=Path(destino).name)
        Path(destino).write_bytes(self.conteudo)
        return Path(destino)

    def publicar(self, nb: str) -> str:
        self._reg("publicar", nb=nb)
        return f"https://notebooklm.google.com/notebook/{nb}"


# --------------------------------------------------------------------------- #
# a porta de verdade
# --------------------------------------------------------------------------- #
class ErroDaPorta(RuntimeError):
    """Falha ao falar com o NotebookLM. Vira exit 1 — instalar não resolve."""


class PortaCLI:
    """Adaptador sobre o executável `notebooklm`."""

    def __init__(self, executavel: str = "notebooklm", timeout: int = 300,
                 idioma: str = "pt_BR"):
        self.exe = executavel
        self.timeout = timeout
        self.idioma = idioma

    # -- infraestrutura ----------------------------------------------------- #
    def _rodar(self, *args: str, timeout: int | None = None) -> dict:
        cmd = [self.exe, *args, "--json"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout or self.timeout)
        except FileNotFoundError as e:
            raise ErroDaPorta(f"executável `{self.exe}` não encontrado") from e
        except subprocess.TimeoutExpired as e:
            raise ErroDaPorta(f"`{args[0]}` expirou em {timeout or self.timeout}s") from e
        try:
            saida = json.loads(r.stdout or "{}")
        except json.JSONDecodeError:
            # nunca ecoar stdout inteiro: pode carregar cookie/URL assinada
            raise ErroDaPorta(
                f"`{' '.join(args[:2])}` devolveu saída não-JSON (rc={r.returncode})")
        if isinstance(saida, dict) and saida.get("error"):
            raise ErroDaPorta(f"{saida.get('code', 'ERRO')}: {saida.get('message', '')}")
        if r.returncode != 0:
            raise ErroDaPorta(f"`{' '.join(args[:2])}` falhou (rc={r.returncode})")
        return saida

    @staticmethod
    def disponivel(executavel: str = "notebooklm") -> bool:
        return shutil.which(executavel) is not None or Path(executavel).is_file()

    @staticmethod
    def achar_executavel(preferido: str = "notebooklm") -> str:
        """Prefere o `notebooklm` de uma venv do projeto ao do PATH.

        Vale a pena porque o erro que isso evita é confuso: com duas instalações
        (uma no `~/.local`, outra na venv), o PATH escolhe a errada, e as versões
        guardam a credencial em caminhos DIFERENTES — a 0.3.x em
        `$NOTEBOOKLM_HOME/storage_state.json`, a 0.7.x em `profiles/<nome>/`. O
        sintoma vira "Auth not found" logo depois de um login bem-sucedido.
        """
        if preferido != "notebooklm":
            return preferido
        for base in (Path.cwd(), *Path.cwd().parents):
            cand = base / ".venv" / "bin" / "notebooklm"
            if cand.is_file():
                return str(cand)
            if (base / ".git").is_dir():
                break
        return preferido

    # -- operações ---------------------------------------------------------- #
    def criar_notebook(self, titulo: str) -> str:
        d = self._rodar("create", titulo)
        nb = (d.get("notebook") or {}).get("id", "")
        if not nb:
            raise ErroDaPorta("criação não devolveu id de notebook")
        return nb

    def listar_fontes(self, nb: str) -> list:
        d = self._rodar("source", "list", "-n", nb)
        return [s.get("title", "") for s in d.get("sources", [])]

    def subir_fonte(self, nb: str, caminho: Path) -> str:
        # o título vem do NOME DO ARQUIVO, e é por isso que não se renomeia no
        # upload: os prompts do pacote ancoram na nota justamente pelo nome
        d = self._rodar("source", "add", "-n", nb, str(caminho), timeout=600)
        return (d.get("source") or {}).get("id", "")

    def gerar(self, nb: str, tipo: str, prompt: str, opcoes: dict) -> Resultado:
        sub = SUBCOMANDO.get(tipo)
        if sub is None:
            return Resultado(FALHOU, "", f"gerável sem subcomando: {tipo}")
        args = ["generate", sub, prompt, "-n", nb, "--no-wait",
                "--language", opcoes.get("idioma", self.idioma)]
        if tipo == "podcast":
            args += ["--format", opcoes.get("variante", "deep-dive"),
                     "--length", opcoes.get("duracao", "long")]
        elif tipo == "video":
            args += ["--format", opcoes.get("variante", "explainer")]
        elif tipo == "report":
            args += ["--format", opcoes.get("variante", "custom")]
        try:
            d = self._rodar(*args)
        except ErroDaPorta as e:
            msg = str(e).lower()
            if "quota" in msg or "rate" in msg or "limit" in msg:
                return Resultado(SEM_QUOTA, "", str(e))
            return Resultado(FALHOU, "", str(e))
        task = d.get("task_id", "")
        # task vazia = nenhuma tarefa nasceu. É como a quota se manifesta quando o
        # servidor recusa sem erro explícito — e o sinal sobrevive a mudança de
        # mensagem, ao contrário de casar string.
        if not task:
            return Resultado(SEM_QUOTA, "", d.get("status", "sem task_id"))
        return Resultado(PENDENTE, task)

    def estados(self, nb: str) -> dict:
        """UMA listagem por notebook, nunca uma consulta por tarefa.

        A CLI relista todos os artefatos a cada consulta; perguntar por tarefa
        multiplicaria chamadas sem ganhar nada. `detalhe` carrega o artifact_id,
        que é o que o download precisa.
        """
        d = self._rodar("artifact", "list", "-n", nb)
        mapa = {}
        for a in d.get("artifacts", []):
            bruto = (a.get("status") or "").lower()
            if bruto in ("completed", "complete", "ready", "done"):
                estado = PRONTO
            elif bruto in ("failed", "error", "cancelled"):
                estado = FALHOU
            elif bruto in ("running", "processing", "in_progress"):
                estado = PROCESSANDO
            else:
                estado = PENDENTE
            ident = a.get("id", "")
            mapa[ident] = Resultado(estado, ident, ident)
        return mapa

    def baixar(self, nb: str, tipo: str, artifact_id: str, destino: Path) -> Path:
        sub = SUBCOMANDO.get(tipo, tipo)
        args = ["download", sub, str(destino), "-n", nb]
        if artifact_id:
            args += ["-a", artifact_id]
        self._rodar(*args, timeout=900)
        if not Path(destino).is_file():
            raise ErroDaPorta(f"download de {tipo} não produziu arquivo")
        return Path(destino)

    def publicar(self, nb: str) -> str:
        d = self._rodar("share", "public", "--enable", "-n", nb)
        return d.get("share_url", "")
