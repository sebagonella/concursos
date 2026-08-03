# Deploy — site de estudo em `concursos.casa:8099`

Serve o site estático num container Docker isolado, com limites de recurso.

## Como funciona (e por que é simples)

O container usa **bind mount**: o site vive numa pasta do servidor (`/opt/concursos/site`) montada dentro do nginx. Consequência prática — **atualizar o site é só sincronizar arquivos**. Não há rebuild de imagem, não há restart de container, não há downtime.

O container responde **diretamente** em `concursos.casa:8099`, servindo o site na **raiz** (`/`). Não é preciso proxy reverso na frente.

```
Sua máquina (vault)                    Servidor (Linux)
  ├── gera o site                        ├── /opt/concursos/
  └── rsync ──────────────────────────▶  │   ├── docker-compose.yml
                                          │   ├── nginx.conf
                                          │   └── site/          ← bind mount
                                          └── container nginx:alpine
                                              host 8099 → container 80
                                                      ▲
                                            http://concursos.casa:8099/
```

> O caminho antigo `/concursos` continua respondendo — redireciona para a raiz, para não quebrar links já salvos.

## Instalação (uma vez)

Na sua máquina, a partir da raiz do repositório:

```bash
# 1. configure o destino (opcional — o default já é concursos.casa)
cat > deploy/deploy.env <<'CFG'
CONCURSOS_HOST=concursos.casa
CONCURSOS_USER=seu-usuario
CONCURSOS_DIR=/opt/concursos
CONCURSOS_PORTA=8099
CFG

# 2. prepara o servidor e sobe o container
./deploy/deploy.sh --setup
```

O `--setup` cria `/opt/concursos/`, copia `docker-compose.yml` e `nginx.conf`, e sobe o container.

> As variáveis antigas `BEELINK_HOST/USER/DIR` continuam aceitas como fallback,
> para não quebrar um `deploy.env` já existente de quando o servidor era o beelink.

> Se `/opt` exigir root, use um caminho do seu usuário (ex.: `CONCURSOS_DIR=$HOME/concursos`).

### Resolver o nome `concursos.casa`

O container atende qualquer nome que chegue nele; falta apenas o nome resolver para o IP do servidor:

- **DNS local** (roteador, Pi-hole, AdGuard, Unbound): crie um registro A `concursos.casa` → IP do servidor. É o caminho recomendado — vale para todos os dispositivos da casa de uma vez.
- **Alternativa rápida**: adicionar em `/etc/hosts` (Linux/macOS) ou `C:\Windows\System32\drivers\etc\hosts` de cada máquina:
  ```
  192.168.0.10   concursos.casa
  ```

Se o servidor já usa outro domínio local, os dois podem coexistir: o `server_name` aceita `concursos.casa` e qualquer outro nome que chegue na porta 8099.

## Uso no dia a dia

Toda vez que você atualizar o concurso no vault:

```bash
./deploy/deploy.sh --concurso-dir ~/vault/30_AREAS/CARREIRA/CONCURSOS/SEDES_2026
```

| Flag | O que faz |
|---|---|
| `--dry-run` | mostra exatamente o que mudaria no servidor, sem enviar (o build local é refeito) |
| `--so-build` | gera o site local e para (bom para conferir antes) |
| `--so-este` | constrói só o concurso pedido; avisa quais vão como estão |
| `--setup` | primeira instalação / recriar o container |

Um comando basta, mesmo com vários concursos publicados: o deploy **reconstrói todos os
concursos presentes no build** antes de enviar — [por quê](#por-que-o-deploy-reconstrói-todos-os-concursos-e-não-só-o-que-você-pediu).

O rsync usa `--delete`: o que sai do vault sai do site, mantendo os dois em sincronia. Publicar um concurso **não remove os demais** — o índice raiz é reconstruído a partir dos manifestos de todos os concursos já publicados.

Configuração vem, nesta ordem: **variável de ambiente** > `deploy/deploy.env` > padrões do script.

## Dimensionamento (3 usuários simultâneos)

| Recurso | Limite | Consumo real esperado |
|---|---|---|
| CPU | 0.50 core | quase zero em repouso; picos curtos ao servir arquivos |
| RAM | 128 MB | ~10-20 MB em repouso, ~40-60 MB em pico |

**Por que tão pouco:** servir estáticos é trabalho de I/O, não de CPU. O nginx usa `sendfile`, que entrega o arquivo direto pelo kernel — mesmo streaming de vídeo quase não consome processador. Os limites são cerca de 2x o pico esperado, de propósito.

Logs têm rotação (`max-size: 5m`, 3 arquivos) e o `access_log` está desligado, para não encher o disco.

## Verificação

```bash
# no servidor
docker compose -f /opt/concursos/docker-compose.yml ps
docker stats concursos-site --no-stream       # consumo real de CPU/RAM

# de qualquer máquina da rede
curl -I http://concursos.casa:8099/healthz    # deve responder 200
curl -I http://concursos.casa:8099/           # o site
```

## Solução de problemas

### Por que o deploy reconstrói todos os concursos, e não só o que você pediu

Não é desperdício: é o que impede o site de publicar conteúdo velho sem avisar.

O `deploy.sh` tem duas operações com escopos que **não coincidem**:

1. o `--concurso-dir` nomeia **um** concurso;
2. o envio é `rsync --delete` do `out/site/` **inteiro**.

E o `out/site/` **acumula** — o `site_builder.py` limpa só a pasta do concurso que está
gerando, de propósito (apagar o resto mataria os concursos irmãos e o `assets/`
compartilhado). Construir apenas o concurso pedido, portanto, mandava os outros para o
servidor com o conteúdo da sessão em que foram gerados.

Por isso o deploy, antes de enviar, **reconstrói todo concurso presente no build**. Ele
descobre de onde cada um veio pelo campo `origem` do manifesto
(`out/site/{slug}/.concurso.json`), que o gerador grava desde a `concurso-publica` 0.14.0:

```
🏗️  Gerando o site — 2 concursos no build:
   [1/2] SEDES_2026
         ✓ 412 páginas
   [2/2] BB_2027_PREVISTO
         ✓ 190 páginas
🚀 Enviando para ...
```

**Manifesto antigo, sem o campo `origem`?** O deploy procura a pasta irmã de
`--concurso-dir` (os concursos moram todos lado a lado no vault) e **ecoa o palpite** —
`(origem deduzida da pasta irmã: …)`. Palpite que não aparece na tela é palpite que ninguém
confere.

**E se a pasta de origem sumiu** (renomeada, vault não montado)? O concurso é republicado
**como está** e o deploy avisa — nomeando o concurso e a data daquele build, no começo e de
novo no fim da saída. Ele não decide sozinho entre publicar conteúdo velho e despublicar
conteúdo bom.

**Para pular a reconstrução dos demais:** `--so-este`. Constrói só o de `--concurso-dir` e
avisa, nomeando os que vão como estão e de quando são.

```bash
./deploy/deploy.sh --concurso-dir <.../SEDES_2026> --so-este
```

> ⚠️ **Não apague o `out/site/` para "forçar" a reconstrução de um só.** O envio é
> `rsync --delete` do diretório inteiro: com apenas um concurso no build, o rsync **remove
> do servidor** todos os outros. Esvaziar o build só é correto quando você realmente quer um
> site de um concurso só — e aí a remoção é o efeito desejado, não um acidente.

O `out/site/` funciona, na prática, como **espelho do que está publicado** — não é cache
descartável.

> **De onde veio esta regra.** O `BB_2027_PREVISTO` foi republicado com um build de véspera
> enquanto se publicava o `SEDES_2026`: sem a ficha das duas fontes, sem o conteúdo do
> Rosenthal, e sem uma linha de erro na saída do comando. Nada quebrou, e é exatamente esse o
> problema — **falha silenciosa**, a classe que este repositório trata como a pior. O
> contorno documentado na ocasião (`rm -rf out/site`) era pior que o defeito: trocava
> publicar conteúdo velho por **despublicar** conteúdo bom. Hoje há suíte
> (`scripts/tests/test_deploy.sh`) que reproduz o caso original.

### Uma mídia dá 403 e as outras abrem

O `rsync -a` preserva a permissão da origem. Arquivo que está `0600` no vault chega
`0600` no servidor, e o nginx do container — que roda com outro usuário — devolve
**403** só naquele arquivo. Aconteceu com um podcast de 41 MB do SEDES enquanto as
outras 85 mídias abriam normalmente.

Desde a correção o deploy sincroniza com `--chmod=D755,F644`, normalizando a
permissão **no destino**: o site é artefato derivado e não deve herdar como o arquivo
acabou salvo no vault. Para conferir que não há resíduo antigo no servidor:

```bash
ssh <user>@<host> "find /opt/docker/concursos/site -type f ! -perm -o=r | wc -l"
# 0 = nenhum arquivo ilegível para o nginx
```


**"Não resolve o nome"** — falta o registro DNS local (ou a entrada no `hosts`). Teste primeiro pelo IP: `http://IP-DO-SERVIDOR:8099/`.

**Porta ocupada** — o `--setup` confere antes de subir e diz quem está usando. Para trocar, basta a variável; o mapeamento do compose a segue:

```bash
CONCURSOS_PORTA=8100 ./deploy/deploy.sh --setup   # ou fixe em deploy/deploy.env
```

A porta interna do nginx é sempre 80 e não muda. Para ver o que ocupa uma porta no servidor: `ss -ltnp | grep 8099`.

**403 Forbidden** — `site/` está vazio: não há `index.html` e o autoindex é desligado. É o estado normal entre o `--setup` e o primeiro deploy, e o `--setup` deixa lá uma página explicando isso. O container está bom — confirme com `curl -s http://concursos.casa:8099/healthz`, que responde `ok` mesmo com o site vazio. A correção é publicar:

```bash
./deploy/deploy.sh --concurso-dir <vault>/30_AREAS/CARREIRA/CONCURSOS/SEDES_2026
```

**Container reiniciando** — `docker compose logs` no servidor. Se for OOM, aumente `mem_limit` (improvável nesse porte).

**Quer colocar atrás de um proxy depois?** Aponte o proxy para a porta 8099 sem reescrever o caminho, ou mude o mapeamento para `127.0.0.1:8099:80` para o container deixar de ser acessível direto pela rede.
