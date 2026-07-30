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
  function iniciarSeletorAprof() {
    var seletor = document.querySelector(".seletor-aprof");
    if (!seletor) return;
    var abas = seletor.querySelectorAll(".aba");

    abas.forEach(function (aba) {
      aba.addEventListener("click", function () {
        var alvo = aba.getAttribute("data-alvo");
        abas.forEach(function (b) { b.classList.toggle("ativa", b === aba); });
        document.querySelectorAll(".aprof").forEach(function (bloco) {
          bloco.classList.toggle("ativo", bloco.getAttribute("data-aprof") === alvo);
        });
        // pausa mídia do aprofundamento que saiu de vista
        document.querySelectorAll(".aprof:not(.ativo) audio, .aprof:not(.ativo) video")
          .forEach(function (m) { try { m.pause(); } catch (e) {} });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    iniciarTema();
    iniciarSeletorAprof();
    document.querySelectorAll(".quiz").forEach(iniciarQuiz);
    iniciarLightbox();
  });
})();
