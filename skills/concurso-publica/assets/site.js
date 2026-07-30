/* site.js — interações mínimas do site de estudo.
   Sem dependências, sem armazenamento: o site é só leitura (o progresso
   de verdade vive no vault). O quiz é prática rápida, não revisão espaçada. */

(function () {
  "use strict";

  /* ---------------- Quiz de flashcards ---------------- */
  function iniciarQuiz(raiz) {
    var dados = raiz.querySelector("script[type='application/json']");
    if (!dados) return;

    var cards;
    try {
      cards = JSON.parse(dados.textContent);
    } catch (e) {
      return;
    }
    if (!cards.length) return;

    var carta = raiz.querySelector(".carta");
    var frente = raiz.querySelector(".frente");
    var verso = raiz.querySelector(".verso");
    var posicao = raiz.querySelector(".posicao");
    var btnVirar = raiz.querySelector("[data-acao='virar']");
    var btnProxima = raiz.querySelector("[data-acao='proxima']");
    var btnEmbaralhar = raiz.querySelector("[data-acao='embaralhar']");

    var ordem = cards.map(function (_, i) { return i; });
    var atual = 0;

    function mostrar() {
      var c = cards[ordem[atual]];
      frente.textContent = c.f;
      verso.textContent = c.v;
      carta.classList.remove("virada");
      posicao.textContent = (atual + 1) + " / " + cards.length;
    }

    function virar() { carta.classList.toggle("virada"); }

    function proxima() {
      atual = (atual + 1) % cards.length;
      mostrar();
    }

    function embaralhar() {
      for (var i = ordem.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var t = ordem[i]; ordem[i] = ordem[j]; ordem[j] = t;
      }
      atual = 0;
      mostrar();
    }

    carta.addEventListener("click", virar);
    if (btnVirar) btnVirar.addEventListener("click", virar);
    if (btnProxima) btnProxima.addEventListener("click", proxima);
    if (btnEmbaralhar) btnEmbaralhar.addEventListener("click", embaralhar);

    // teclado: espaço vira, seta direita avança
    raiz.addEventListener("keydown", function (ev) {
      if (ev.key === " " || ev.key === "Enter") { ev.preventDefault(); virar(); }
      if (ev.key === "ArrowRight") { ev.preventDefault(); proxima(); }
    });
    carta.setAttribute("tabindex", "0");

    mostrar();
  }

  /* ---------------- Lightbox do mapa mental ---------------- */
  function iniciarLightbox() {
    var caixa = document.querySelector(".lightbox");
    if (!caixa) return;
    var alvo = caixa.querySelector("img");

    document.querySelectorAll(".mapa-mental img").forEach(function (img) {
      img.addEventListener("click", function () {
        alvo.src = img.src;
        caixa.classList.add("aberto");
      });
    });

    function fechar() { caixa.classList.remove("aberto"); }
    caixa.addEventListener("click", fechar);
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") fechar();
    });
  }

  /* ---------------- Tema claro / escuro ----------------
     Preferência de leitura (não é progresso de estudo — este continua vindo
     só do vault). Guarda a escolha e respeita o padrão do sistema. */
  var CHAVE_TEMA = "concursos:tema";

  function aplicarTema(tema) {
    document.documentElement.setAttribute("data-tema", tema);
    var btn = document.querySelector(".tema-troca");
    if (btn) {
      var escuro = tema === "escuro";
      btn.textContent = escuro ? "☀ Claro" : "☾ Escuro";
      btn.setAttribute("aria-label",
        escuro ? "Mudar para tema claro" : "Mudar para tema escuro");
    }
  }

  function temaInicial() {
    var salvo = null;
    try { salvo = localStorage.getItem(CHAVE_TEMA); } catch (e) { /* modo restrito */ }
    if (salvo === "claro" || salvo === "escuro") return salvo;
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
  }

  function iniciarTema() {
    aplicarTema(temaInicial());
    var btn = document.querySelector(".tema-troca");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var novo = document.documentElement.getAttribute("data-tema") === "escuro"
        ? "claro" : "escuro";
      aplicarTema(novo);
      try { localStorage.setItem(CHAVE_TEMA, novo); } catch (e) { /* ignora */ }
    });
  }

  /* ---------------- Seletor de aprofundamentos ----------------
     Um assunto pode ter vários aprofundamentos (fontes/níveis diferentes).
     As abas alternam qual está visível — corpo e lateral juntos. */
  /* Pega TODOS os seletores, não só o primeiro: a página de matéria tem o seletor
     de visão (Plano/Estudo) e a de assunto o de aprofundamento — e desde a aba de
     visão podem coexistir na mesma página. */
  function iniciarSeletorAprof() {
    document.querySelectorAll(".seletor-aprof").forEach(function (seletor) {
      var abas = seletor.querySelectorAll(".aba");
      abas.forEach(function (aba) {
        aba.addEventListener("click", function () {
          var alvo = aba.getAttribute("data-alvo");
          var visao = aba.getAttribute("data-visao-alvo");
          var eixo = aba.getAttribute("data-eixo-alvo");
          abas.forEach(function (b) { b.classList.toggle("ativa", b === aba); });

          if (eixo) {
            /* O seletor de eixo vive DENTRO da visão Estudo. Alternar `.eixo`
               no documento inteiro seria o mesmo erro que a busca global de
               `.visao` cometeria ao existir um segundo eixo: um seletor
               desligaria o bloco do outro. Limita-se ao contêiner do seletor. */
            var caixa = seletor.parentElement || document;
            caixa.querySelectorAll(":scope > .eixo").forEach(function (bloco) {
              bloco.classList.toggle("ativo",
                bloco.getAttribute("data-eixo") === eixo);
            });
          } else if (visao) {
            document.querySelectorAll(".visao").forEach(function (bloco) {
              bloco.classList.toggle("ativo",
                bloco.getAttribute("data-visao") === visao);
            });
          } else {
            document.querySelectorAll(".aprof").forEach(function (bloco) {
              bloco.classList.toggle("ativo",
                bloco.getAttribute("data-aprof") === alvo);
            });
          }
          // pausa mídia do bloco que saiu de vista
          document.querySelectorAll(
            ".aprof:not(.ativo) audio, .aprof:not(.ativo) video," +
            ".visao:not(.ativo) audio, .visao:not(.ativo) video"
          ).forEach(function (m) { try { m.pause(); } catch (e) {} });
        });
      });
    });
  }

  /* ---------------- Copiar prompt ----------------
     O pacote NotebookLM existe para ser EXECUTADO: o prompt vai daqui para o campo
     "Customize" do Estúdio. Um toque, sem seleção manual. */
  function iniciarCopiar() {
    document.querySelectorAll("[data-copiar]").forEach(function (botao) {
      botao.addEventListener("click", function () {
        var cartao = botao.closest(".prompt");
        var pre = cartao && cartao.querySelector(".texto-prompt");
        if (!pre) return;
        var texto = pre.textContent;
        var original = botao.textContent;

        function ok() {
          botao.textContent = "✓ Copiado";
          setTimeout(function () { botao.textContent = original; }, 2000);
        }
        function copiaManual() {
          // fallback para navegador sem clipboard API ou fora de contexto seguro
          var area = document.createElement("textarea");
          area.value = texto;
          area.setAttribute("readonly", "");
          area.style.position = "fixed";
          area.style.opacity = "0";
          document.body.appendChild(area);
          area.select();
          try { document.execCommand("copy"); ok(); } catch (e) {
            botao.textContent = "Selecione e copie";
            setTimeout(function () { botao.textContent = original; }, 2000);
          }
          document.body.removeChild(area);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(texto).then(ok, copiaManual);
        } else {
          copiaManual();
        }
      });
    });
  }

  /* ---------------- detalhes do tópico (aba Plano) ----------------
     O <details> é nativo de propósito: abre sem JavaScript, imprime e é o que
     faz o Ctrl+F do Chrome saltar para dentro do tópico. Este punhado de linhas
     existe pelo que o nativo NÃO cobre: o Firefox não expande na busca da
     página, e quem manda imprimir quer o plano inteiro, não só os títulos.
     Nada é persistido — é preferência de leitura, e o progresso mora no vault. */
  function iniciarDetalhesDoPlano() {
    var caixas = document.querySelectorAll(".mais-topico");
    if (!caixas.length) return;

    var botao = document.querySelector("[data-expandir]");
    if (botao) {
      botao.addEventListener("click", function () {
        var abrir = botao.getAttribute("data-expandir") === "abrir";
        caixas.forEach(function (d) { d.open = abrir; });
        botao.setAttribute("data-expandir", abrir ? "fechar" : "abrir");
        botao.textContent = abrir ? "Recolher tudo" : "Expandir tudo";
      });
    }

    var antes = [];
    window.addEventListener("beforeprint", function () {
      antes = [];
      caixas.forEach(function (d) { antes.push(d.open); d.open = true; });
    });
    window.addEventListener("afterprint", function () {
      caixas.forEach(function (d, i) { d.open = !!antes[i]; });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    iniciarTema();
    iniciarSeletorAprof();
    iniciarCopiar();
    iniciarDetalhesDoPlano();
    document.querySelectorAll(".quiz").forEach(iniciarQuiz);
    iniciarLightbox();
  });
})();
