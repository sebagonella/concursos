---
title: "Fonte NotebookLM — {ASSUNTO}"
tipo: fonte-notebooklm
materia: "{MATERIA}"
concurso: "{CONCURSO}"
assunto: "{ASSUNTO}"
tags: [notebooklm, concurso/aprofundamento, {TAG_ASSUNTO}]
notebooklm_status: {NOTEBOOKLM_STATUS}
# Cole aqui o link do notebook depois de criá-lo: é o que faz o botão
# "Abrir no NotebookLM" aparecer no site gerado pela concurso-publica.
notebooklm_url: "{NOTEBOOKLM_URL}"
# Identificadores que a concurso-publica publica e que a automação vai consumir.
# Ficam aqui, e não só na prosa, porque extrair nome de arquivo por regex de texto
# corrido já falhou: o roteiro do mapa mental e o do report chegavam vazios ao site.
# Chaves PLANAS de propósito — o leitor de frontmatter é `k: v` por linha, sem YAML
# aninhado.
nome_notebook: "{CONCURSO} — {ASSUNTO}"
arquivo_podcast: "podcast-{SLUG_ASSUNTO}.m4a"
arquivo_mapa_mental: "mapa-mental-{SLUG_ASSUNTO}.png"
arquivo_video: "video-{SLUG_ASSUNTO}.mp4"
arquivo_report: "report-{SLUG_ASSUNTO}.md"
---

# 🎙️ Pacote NotebookLM — {ASSUNTO}

> Roteiro para gerar podcast, mapa mental, vídeo e report deste assunto no NotebookLM.
> Um notebook **por assunto** — mantém o material focado e a qualidade alta.
> Prompts finos abaixo assumem **NotebookLM Plus** (Google AI Pro), onde todos os
> geráveis aceitam prompt customizado.

## 1. Fontes para subir no notebook

Crie um notebook novo chamado **"{CONCURSO} — {ASSUNTO}"** e adicione estas fontes (painel esquerdo → *Add source*):

{LISTA_FONTES}

> 💡 O `.md` do assunto já é um resumo curado — é a fonte principal. As leis/PDFs
> relacionados dão profundidade. As páginas do livro indicadas no `.md` bastam como
> referência (suba só o recorte daquelas páginas, se quiser).

## 2. 🎧 Podcast (Audio Overview)

Studio → **Audio Overview** → clique em **Customize**.
- **Formato:** Deep Dive (completo) · alternativas: Brief (revisão rápida), Critique, Debate.
- **Duração:** Longer (mais completo) · ou Default/Shorter para revisão.
- **Idioma:** Português (Brasil).
- **Prompt "no que focar":**

```
{PROMPT_AUDIO}
```

Generate → ao terminar, ⋮ → Download. O NotebookLM gera **`.m4a`**.
Salve nesta pasta como **`podcast-{SLUG_ASSUNTO}.m4a`**.

## 3. 🧠 Mapa Mental (Mind Map)

Studio → **Mind Map** → **Customize** (disponível no Plus desde mai/2026 — o prompt é lido como *especificação de estrutura*).
- **Prompt de estrutura:**

```
{PROMPT_MINDMAP}
```

Generate → explore os nós (cada nó abre um chat). Download (⋮ → Download) como imagem.
Salve como **`mapa-mental-{SLUG_ASSUNTO}.png`**.

## 4. 🎬 Vídeo (Video Overview)

Studio → **Video Overview** → **Customize**.
- **Formato:** Explainer (aula) · alternativa: Brief.
- **Estilo visual:** escolha um limpo/didático (ex.: "Whiteboard" ou "Clean").
- **Prompt "no que enfatizar":**

```
{PROMPT_VIDEO}
```

Generate (leva ~10–15 min). Download.
Salve como **`video-{SLUG_ASSUNTO}.mp4`**.

## 5. 📄 Report (Relatório / Guia de estudos)

Studio → **Reports** → **Create your own** (ou escolha o template *Study guide*).
- **Prompt do report:**

```
{PROMPT_REPORT}
```

Generate → o report é salvo como nota no notebook. Copie o conteúdo e salve nesta pasta como **`report-{SLUG_ASSUNTO}.md`**.

## 6. 🔗 Arquivos gerados (preencha os links conforme for salvando)

> Salve cada arquivo NESTA pasta do assunto e os wikilinks abaixo passam a funcionar.
> Se você não gerar ou não baixar algum, tudo bem — deixe o item desmarcado.

- 🎧 Podcast: [[podcast-{SLUG_ASSUNTO}.m4a]]
- 🧠 Mapa mental: [[mapa-mental-{SLUG_ASSUNTO}.png]]
- 🎬 Vídeo: [[video-{SLUG_ASSUNTO}.mp4]]
- 📄 Report: [[report-{SLUG_ASSUNTO}.md]]

## 7. 💬 Perguntas úteis no chat do notebook

{PERGUNTAS_CHAT}

## ✅ Checklist

- [ ] Notebook criado com as fontes
- [ ] 🎧 Podcast gerado e salvo
- [ ] 🧠 Mapa mental gerado e salvo
- [ ] 🎬 Vídeo gerado e salvo (opcional)
- [ ] 📄 Report gerado e salvo (opcional)
- [ ] Atualizar `notebooklm_status: criado` no topo deste arquivo

> No **Plus** não há gargalo de quantidade de podcasts/dia — gere à vontade.
> (No gratuito são 3/dia; priorize os assuntos mais difíceis.) Cada membro do
> plano familiar tem os limites Plus na própria conta, se ativou o benefício do AI Pro.

---
<!-- Quando a automação (notebooklm-py) estiver disponível, este mesmo pacote
     alimenta o script que cria o notebook e sobe as fontes automaticamente. -->
