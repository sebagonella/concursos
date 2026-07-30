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
| `--dry-run` | mostra exatamente o que mudaria no servidor, sem enviar |
| `--so-build` | gera o site local e para (bom para conferir antes) |
| `--setup` | primeira instalação / recriar o container |

O rsync usa `--delete`: o que sai do vault sai do site, mantendo os dois em sincronia. Publicar um concurso **não remove os demais** — o índice raiz é reconstruído a partir dos manifestos de todos os concursos já publicados.

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
