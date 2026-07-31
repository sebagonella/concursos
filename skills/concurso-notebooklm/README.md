# concurso-notebooklm

Executa automaticamente os pacotes NotebookLM que a `concurso-aprofunda` deixou
prontos no vault: cria o notebook, sobe as fontes, gera as mídias e salva os arquivos
com o nome que a `concurso-publica` reconhece — de modo que o site publique sem
nenhum passo manual.

Versão atual: **0.2.0** (camada de rede: cria o notebook, sobe as fontes, dispara as
gerações e coleta os arquivos — verificado ponta a ponta contra o NotebookLM).

## O problema que ela resolve

O vault tem **158 pacotes prontos** e um punhado de mídias geradas. O gargalo nunca
foi ter o roteiro: é executá-lo 158 vezes, à mão, no Estúdio.

## Como usar

```bash
# dispara (não espera: a geração leva minutos)
python3 scripts/nlm_run.py --assuntos-dir <.../materia/assuntos> \
    --leis-dir <.../04-MATERIAIS/leis-baixadas> --publicar

# minutos depois, coleta o que ficou pronto
python3 scripts/nlm_coleta.py --assuntos-dir <...>
```

`--dry-run` mostra o plano sem tocar em nada — e funciona **sem** a biblioteca
instalada, porque é o relatório honesto do backlog.

## O que funciona

- Ler o pacote e extrair o nome do notebook, o nome de cada arquivo de saída, um
  prompt por gerável e as fontes a subir.
- Resolver cada fonte num arquivo real do disco, reportando **por nome** o que faltar.
- Criar o notebook só se ainda não houver um, e subir só a fonte que ainda não está
  lá — reexecutar sobre 66 assuntos não duplica nem queima quota.
- Disparar as gerações, guardando os `task_id` num sidecar, e coletar depois.
- Nomear o arquivo baixado pelo container **real**, corrigindo o pacote se divergir.
- Gravar no vault o id, o endereço, o estado e a data — de forma atômica.
- Parar na quota **por tipo** (áudio esgotado não impede report) e sair com **4**,
  que é o código de "rode de novo amanhã".

## Geráveis

| Gerável | Variantes | Padrão |
|---|---|---|
| `podcast` | `deep-dive` · `brief` · `critique` · `debate` | `deep-dive` |
| `video` | `explainer` · `brief` | `explainer` |
| `report` | `custom` · `study-guide` · `briefing` · `blog` | `custom` |

Default: `podcast:deep-dive`. Tokens especiais: `nada` e `tudo`.

**Mapa mental está fora da automação**: a biblioteca não aceita prompt customizado
para ele, e o download vem em JSON — formato que o site não reconhece como mídia.
Pedi-lo é recusado com a razão. Gere-o à mão pelo roteiro do pacote.

## Dependência

`notebooklm-py` é **opcional** e **não-oficial**: roda sobre endpoints internos do
Google e quebra sem aviso. Sem ela, esta skill degrada e o modo manual do pacote
continua completo. A credencial de sessão dá acesso à conta Google inteira — use uma
**conta dedicada**, e nunca guarde o arquivo de sessão no repo nem no vault (que
sincroniza com o Drive).

```bash
pip install -r skills/concurso-notebooklm/requirements.txt
```

## 🛑 O `notebooklm login` trava na 0.7.3 — e não é erro seu

**Sintoma:** o navegador abre, você faz o login com sucesso, mas o terminal fica em
`Waiting for login (up to 5 minutes)...` até estourar o tempo e desistir.

**Causa, verificada no código instalado:** a 0.7.3 espera que, depois do login, a
página fique no host antigo —
`page.wait_for_url(f"{get_base_url()}/**")`, em `cli/services/playwright_login.py`.
Desde o rebrand **"Gemini Notebook"**, o Google leva a sessão para
**`notebook.google.com`**, e a URL nunca casa. Não há saída por configuração: a
variável `NOTEBOOKLM_BASE_URL` é **lista branca** e só aceita
`notebooklm.google.com` e o host enterprise (`_env.py`). O fix existe no `main` do
projeto; não na versão do PyPI.

**Só a detecção quebra.** A sessão em si vale para os dois hosts — o `auth check`
mostra `OSID` tanto em `notebook.google.com` quanto em `notebooklm.google.com` —, e
as chamadas de RPC funcionam normalmente depois que a credencial está salva.

**Contorno recomendado — não usa Playwright, então não há espera de URL:**

```bash
pip install 'notebooklm-py[cookies]'
# faça login na CONTA DEDICADA no seu navegador normal, depois:
notebooklm login --browser-cookies chrome          # ou 'chrome::<perfil>', firefox, brave…
notebooklm auth check                              # deve dizer "Authentication is valid"
```

**Se você já fez o login pelo Playwright e ele expirou esperando**, os cookies estão
no perfil persistente (`~/.notebooklm/profiles/<perfil>/browser_profile`) — só faltou
gravar o `storage_state.json`. Feche o navegador e rode
`scripts/salvar_sessao.py`, que faz exatamente esse último passo e **não escreve nada**
se a sessão não estiver de pé.

## Testes

```bash
python3 scripts/tests/test_smoke.py
```

Passam **sem** a biblioteca instalada, e os pacotes usados como fixture são gerados
pelo `notebooklm_pack.py` de verdade — fixture que inventa o que o gerador não produz
é teste que se autoconfirma.
