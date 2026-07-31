---
name: concurso-notebooklm
version: 0.2.0
description: >
  Use quando o usuário quiser EXECUTAR automaticamente os pacotes NotebookLM que a
  skill concurso-aprofunda já preparou no vault — criar o notebook, subir as fontes,
  gerar as mídias (podcast, vídeo, relatório) e salvar os arquivos com o nome que a
  skill concurso-publica reconhece, prontos para o site. Roda SOB DEMANDA, por
  assunto ou por matéria inteira, e grava de volta no vault o endereço do notebook e
  o estado da geração. É camada OPCIONAL sobre o modo manual, que continua valendo
  integralmente. Triggers - "gerar o podcast desse assunto", "criar os notebooks
  dessa matéria", "rodar o NotebookLM automaticamente", "automatizar o pacote do
  NotebookLM", "baixar as mídias do NotebookLM para o vault".
---

# concurso-notebooklm

Executa o que a [`concurso-aprofunda`](../concurso-aprofunda/SKILL.md) preparou. O
pacote `_fonte-notebooklm.md` de cada aprofundamento já é **contrato completo** — ele
declara o nome do notebook, o nome de cada arquivo de saída, as fontes a subir e um
prompt por gerável. Esta skill só executa; não recalcula nada.

> **A automação é camada opcional.** O modo manual — abrir o pacote, copiar o prompt,
> clicar no Estúdio — continua sendo o caminho garantido, e é o que vale quando a
> biblioteca não está instalada ou quando o Google muda o que ela usa por baixo.

## Como usar

```bash
# um aprofundamento
python3 scripts/nlm_run.py --aprofundamento <.../assuntos/crase/padrao--pestana>

# a matéria inteira, com as leis como fonte
python3 scripts/nlm_run.py --assuntos-dir <.../lingua-portuguesa/assuntos> \
    --leis-dir <.../04-MATERIAIS/leis-baixadas>

# escolher o que gerar (padrão: podcast:deep-dive)
    --midias podcast:debate,report      --midias tudo      --midias nada

# ativar o link público do notebook (padrão: não)
    --publicar

# conferir sem tocar em nada
    --dry-run
```

A geração leva minutos, então `nlm_run.py` **não espera** — 66 assuntos seriam horas
com um processo segurando a sessão. Depois:

```bash
python3 scripts/nlm_coleta.py --assuntos-dir <...>
```

Roda quantas vezes quiser: o que já está no disco é pulado e o que ainda gera fica
no sidecar para a próxima passada. Ao final, republique o site.

### Códigos de saída

| | |
|---|---|
| **0** | tudo que foi pedido foi feito |
| **1** | rede ou autenticação — instalar não resolve |
| **2** | degradação parcial (biblioteca ausente, falha isolada) |
| **3** | argumentos inválidos |
| **4** | **quota atingida** — retomável com o mesmo comando |

O **4** é separado do 2 de propósito: é o único caso em que "rode de novo amanhã" é
a instrução certa.

## Por que a dependência é frágil, e o que isso impõe

A `notebooklm-py` não é oficial: roda sobre endpoints internos do Google, com IDs de
RPC fixos no código. O próprio projeto declara que não há garantia de estabilidade, e
trata quebra do Google como evento de *patch* — a cadência observada é de algumas
semanas. Consequências que valem como regra desta skill:

- **Nada aqui pode ser obrigatório.** Sem a biblioteca, a skill degrada e avisa; o
  pacote manual segue completo.
- **A lógica não toca a rede.** `pacote.py` e `plano.py` são stdlib puro e testáveis
  sem conexão. Quando o Google mudar algo, quebra num arquivo só.
- **Conta dedicada.** A credencial de sessão dá acesso à conta Google inteira. Ela
  nunca entra no repo nem no vault — o vault sincroniza com o Drive.

## Módulos

| Arquivo | Responsabilidade |
|---|---|
| `scripts/pacote.py` | ler e escrever o `_fonte-notebooklm.md` — o único que toca o arquivo |
| `scripts/plano.py` | decidir o que gerar, nomear a saída, adivinhar o container pelos bytes |
| `scripts/porta.py` | a fronteira com o NotebookLM — e o dublê que a espelha |
| `scripts/executor.py` | junta plano e porta; cria, sobe, dispara e coleta |
| `scripts/nlm_run.py` · `nlm_coleta.py` | os dois comandos |
| `scripts/salvar_sessao.py` | recupera um login que o detector quebrado não gravou |

**A fronteira é a CLI, não a API Python.** A biblioteca expõe as duas, mas a API é
`async` e mora em módulos com underscore que o próprio projeto declara instáveis; a
CLI é a superfície pública e devolve JSON. Falar com ela por subprocess mantém esta
skill **síncrona**, como o resto do repositório, e é o mesmo padrão que o
`fetch_lei.py` usa para o `pdftotext`.

**Onde cada dado mora:** durável e humano (`notebooklm_id`, `url`, `status`, data) vai
para o **frontmatter do pacote**; volátil e de máquina (os `task_id` em voo) vai para
o sidecar `_notebooklm-estado.json`, que começa com `_` e por isso o site ignora. Id
opaco num documento curado é ruído, e cada mudança dele dispararia o backup do
gerador.

## O que se pode gerar

| Gerável | Variantes | Padrão |
|---|---|---|
| `podcast` | `deep-dive` · `brief` · `critique` · `debate` | `deep-dive` |
| `video` | `explainer` · `brief` | `explainer` |
| `report` | `custom` · `study-guide` · `briefing` · `blog` | `custom` |

O **default é `podcast:deep-dive`**. Dois tokens especiais: `nada` (cria o notebook e
sobe as fontes, sem gerar mídia) e `tudo`.

> **Mapa mental está fora da automação, por ora.** Duas razões técnicas: a biblioteca
> não aceita prompt customizado para ele — o `PROMPT_MINDMAP` do pacote não seria
> enviado — e o download vem em **JSON**, formato que o catálogo de mídias da
> `concurso-publica` não reconhece: o arquivo ficaria **invisível no site**. Pedir
> `mapa-mental` é recusado **com a razão**, não ignorado. Gere-o à mão pelo roteiro
> da seção 3 do pacote.

## Convenções invioláveis

- **O prompt enviado é o do pacote, byte a byte.** Reescrevê-lo aqui criaria duas
  versões do mesmo texto — a que o usuário copia no site e a que a automação manda —
  e elas divergiriam sem ninguém ver.
- **O nome do arquivo salvo vem do `arquivo_*` do frontmatter**, que é exatamente o
  que o `CATALOGO_MIDIAS` da `concurso-publica` detecta. Nome fora do padrão não vira
  outro tipo de mídia: vira **invisível**, que é pior por ser silencioso.
- **A extensão sai dos bytes, não da declaração.** A biblioteca grava no caminho que
  recebe; se pedirmos `.m4a` e vier MP3, o site não acha o arquivo.
- **Presença de arquivo é o sinal de "feito".** É a mesma regra do site — um segundo
  lugar guardando "isto já foi gerado" envelheceria em desacordo com o disco.
- **Fonte que não existe vira pendência nomeada.** Subir de menos em silêncio deixaria
  o notebook sem a lei e ninguém veria.
- **O que a automação grava sobrevive à regeração do pacote.** A `concurso-aprofunda`
  herda por prefixo `notebooklm_*` desde a 0.7.1; sem isso o endereço iria para o
  `.bak.md` na primeira vez que alguém regerasse.

## Instalação

```bash
pip install -r skills/concurso-notebooklm/requirements.txt
```

A suíte de testes passa **sem** a biblioteca instalada — o `install.sh` roda os testes
logo depois de copiar a skill, e quem só quer o modo manual não deve ser bloqueado.
