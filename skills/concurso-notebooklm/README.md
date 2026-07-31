# concurso-notebooklm

Executa automaticamente os pacotes NotebookLM que a `concurso-aprofunda` deixou
prontos no vault: cria o notebook, sobe as fontes, gera as mídias e salva os arquivos
com o nome que a `concurso-publica` reconhece — de modo que o site publique sem
nenhum passo manual.

Versão atual: **0.1.0** (camada de contrato: ler o pacote, decidir o que gerar,
nomear a saída e gravar os metadados de volta no vault — ainda **sem** falar com o
NotebookLM).

## O problema que ela resolve

O vault tem **158 pacotes prontos** e um punhado de mídias geradas. O gargalo nunca
foi ter o roteiro: é executá-lo 158 vezes, à mão, no Estúdio.

## O que já funciona

- Ler o `_fonte-notebooklm.md` e extrair o nome do notebook, o nome de cada arquivo de
  saída, um prompt por gerável e as fontes a subir.
- Resolver cada fonte num arquivo real do disco — a nota do assunto ao lado do pacote,
  as leis na pasta de leis-baixadas —, reportando **por nome** o que faltar.
- Decidir o que gerar, pulando o que já tem arquivo na pasta.
- Gravar de volta no pacote o endereço do notebook e o estado, de forma atômica e
  preservando o resto do arquivo byte a byte.

## O que ainda não

A fronteira de rede. Nada aqui conversa com o NotebookLM nesta versão.

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

## Testes

```bash
python3 scripts/tests/test_smoke.py
```

Passam **sem** a biblioteca instalada, e os pacotes usados como fixture são gerados
pelo `notebooklm_pack.py` de verdade — fixture que inventa o que o gerador não produz
é teste que se autoconfirma.
