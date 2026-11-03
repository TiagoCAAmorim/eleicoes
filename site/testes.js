/* Exploradores das páginas de testes (governador, prefeito, teste de estresse).
 *
 * Cada <div class="explorador" data-dados="testes/x.json" data-parte="t2" data-tipo="t2|t1|estresse"> vira:
 * seletores (eleição, apuração sorteada, viés), um gráfico da previsão ao longo da apuração e um quadro com o
 * que o modelo dizia no momento escolhido (controle deslizante ou passando o mouse no gráfico).
 * Os JSON são gerados por eleicoes/site/testes.py a partir dos rejogos em resultados/. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var CACHE = {};
  var TICKS = [0, 1, 5, 10, 20, 30, 50, 70, 90];

  function carregar(url) {
    if (!CACHE[url]) CACHE[url] = fetch(url).then(function (r) { return r.json(); });
    return CACHE[url];
  }
  function num(x, n) {
    if (x === null || x === undefined) return "–";
    return x.toFixed(n === undefined ? 1 : n).replace(".", ",");
  }
  function chance(p) {
    if (p === null || p === undefined) return "–";
    if (p >= 0.995 && p < 1) return "> 99%";
    if (p > 0 && p <= 0.005) return "< 1%";
    return Math.round(100 * p) + "%";
  }
  function el(tag, attrs, pai) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === "texto") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]);
    }
    if (pai) pai.appendChild(e);
    return e;
  }
  function svg(tag, attrs, pai) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (pai) pai.appendChild(e);
    return e;
  }
  function campo(pai, rotulo) {
    var l = el("label", {}, pai);
    l.appendChild(document.createTextNode(rotulo + " "));
    return el("select", {}, l);
  }
  function opcoes(sel, lista, valor) {
    sel.innerHTML = "";
    lista.forEach(function (o) {
      var op;
      if (o.grupo) {
        op = sel.querySelector('optgroup[label="' + o.grupo + '"]') || el("optgroup", { label: o.grupo }, sel);
        el("option", { value: o.valor, texto: o.texto }, op);
      } else {
        el("option", { value: o.valor, texto: o.texto }, sel);
      }
    });
    if (valor !== undefined) sel.value = valor;
  }

  /* --- gráfico: % apurado (escala raiz) x % dos válidos ---------------------------------------------- */
  function grafico(alvo, cfg) {
    // cfg: {pcts, series: [{cor, nome, pontos: [[media,p05,p25,p75,p95]|null...], real}], extra: [{pontos, nome}], i}
    alvo.innerHTML = "";
    // largura real do contêiner: no celular o texto do gráfico fica do mesmo tamanho que no computador
    var W = Math.max(300, Math.round(alvo.clientWidth || 640)), H = W < 520 ? 240 : 300;
    var m = { e: 40, d: 10, t: 12, b: 34 };
    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img", class: "grafico-svg" }, alvo);
    var vals = [];
    cfg.series.forEach(function (se) {
      se.pontos.forEach(function (p) { if (p && p[1] !== null) vals.push(p[1], p[4]); });
      if (se.real !== null && se.real !== undefined) vals.push(se.real);
    });
    (cfg.extra || []).forEach(function (x) { x.pontos.forEach(function (v) { if (v !== null) vals.push(v); }); });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var passo = hi - lo > 40 ? 10 : hi - lo > 16 ? 5 : hi - lo > 6 ? 2 : 1;
    lo = Math.max(0, Math.floor(lo / passo) * passo);
    hi = Math.min(100, Math.ceil(hi / passo) * passo);
    if (hi === lo) hi = lo + passo;
    var X = function (p) { return m.e + Math.sqrt(p / 100) * (W - m.e - m.d); };
    var Y = function (v) { return m.t + (hi - v) / (hi - lo) * (H - m.t - m.b); };
    var eixo = svg("g", { class: "eixo" }, s);
    for (var v = lo; v <= hi + 1e-9; v += passo) {
      svg("line", { x1: m.e, x2: W - m.d, y1: Y(v), y2: Y(v), class: "grade" }, eixo);
      var t = svg("text", { x: m.e - 6, y: Y(v) + 4, "text-anchor": "end" }, eixo);
      t.textContent = v + "%";
    }
    (W < 520 ? [0, 1, 5, 10, 30, 50, 90] : TICKS).forEach(function (p) {
      var t = svg("text", { x: X(p), y: H - m.b + 18, "text-anchor": "middle" }, eixo);
      t.textContent = p + "%";
    });
    var tx = svg("text", { x: W - m.d, y: H - 4, "text-anchor": "end", class: "rotulo-eixo" }, eixo);
    tx.textContent = "seções apuradas";
    if (cfg.ref50 && lo < 50 && hi > 50) {
      svg("line", { x1: m.e, x2: W - m.d, y1: Y(50), y2: Y(50), class: "ref50" }, s);
    }
    function caminho(pontos, f) {
      var d = "", aberto = false;
      cfg.pcts.forEach(function (p, i) {
        var v = pontos[i] ? f(pontos[i]) : null;
        if (v === null || v === undefined) return;  // momento sem rejogo: liga os vizinhos
        d += (aberto ? "L" : "M") + X(p).toFixed(1) + "," + Y(v).toFixed(1);
        aberto = true;
      });
      return d;
    }
    function faixa(pontos, a, b) {
      var ida = [], volta = [];
      cfg.pcts.forEach(function (p, i) {
        var q = pontos[i];
        if (!q || q[a] === null) return;
        ida.push(X(p).toFixed(1) + "," + Y(q[b]).toFixed(1));
        volta.unshift(X(p).toFixed(1) + "," + Y(q[a]).toFixed(1));
      });
      return ida.length ? "M" + ida.concat(volta).join("L") + "Z" : "";
    }
    cfg.series.forEach(function (se) {
      var g = svg("g", { style: "color:" + se.cor }, s);
      svg("path", { d: faixa(se.pontos, 1, 4), class: "banda90" }, g);
      svg("path", { d: faixa(se.pontos, 2, 3), class: "banda50" }, g);
      if (se.real !== null && se.real !== undefined) {
        svg("line", { x1: m.e, x2: W - m.d, y1: Y(se.real), y2: Y(se.real), class: "real" }, g);
      }
      svg("path", { d: caminho(se.pontos, function (q) { return q[0]; }), class: "linha" }, g);
    });
    (cfg.extra || []).forEach(function (x) {
      svg("path", { d: caminho(x.pontos.map(function (v) { return v === null ? null : [v]; }),
        function (q) { return q[0]; }), class: "parcial" }, s);
    });
    var cursor = svg("line", { y1: m.t, y2: H - m.b, class: "cursor" }, s);
    var marcas = svg("g", {}, s);
    function marcar(i) {
      var p = cfg.pcts[i];
      cursor.setAttribute("x1", X(p)); cursor.setAttribute("x2", X(p));
      marcas.innerHTML = "";
      cfg.series.forEach(function (se) {
        var q = se.pontos[i];
        if (q && q[0] !== null) svg("circle", { cx: X(p), cy: Y(q[0]), r: 4.5, class: "ponto", style: "fill:" + se.cor }, marcas);
      });
    }
    marcar(cfg.i);
    // passar o mouse ou o dedo escolhe o momento mais próximo
    var alvoToque = svg("rect", { x: m.e, y: m.t, width: W - m.e - m.d, height: H - m.t - m.b, class: "toque" }, s);
    function mover(ev) {
      var r = s.getBoundingClientRect();
      var cx = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * W / r.width;
      var melhor = 0, dist = 1e9;
      cfg.pcts.forEach(function (p, i) {
        var ok = cfg.series.some(function (se) { return se.pontos[i] && se.pontos[i][0] !== null; });
        if (ok && Math.abs(X(p) - cx) < dist) { dist = Math.abs(X(p) - cx); melhor = i; }
      });
      cfg.aoEscolher(melhor);
    }
    alvoToque.addEventListener("mousemove", mover);
    alvoToque.addEventListener("touchstart", mover, { passive: true });
    alvoToque.addEventListener("touchmove", mover, { passive: true });
    return marcar;
  }

  var CORES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)"];

  function legenda(pai, itens) {
    var l = el("div", { class: "legenda" }, pai);
    itens.forEach(function (it) {
      var s = el("span", {}, l);
      el("i", { class: it.classe || "", style: it.cor ? "background:" + it.cor : "" }, s);
      s.appendChild(document.createTextNode(it.nome));
    });
  }

  /* --- explorador -------------------------------------------------------------------------------- */
  function explorador(raiz, dados) {
    var tipo = raiz.getAttribute("data-tipo"), parte = raiz.getAttribute("data-parte");
    var pcts = dados.pcts;
    var lista = tipo === "estresse" ? dados.anos : dados[parte];
    var vagas = raiz.getAttribute("data-vagas") === "sim";
    raiz.innerHTML = "";
    var campos = el("div", { class: "linha-campos" }, raiz);
    var selE = campo(campos, tipo === "estresse" ? "Eleição de base" : "Eleição");
    var selV = null, selVar = null;
    if (raiz.hasAttribute("data-vies")) selV = campo(campos, "Viés de ordem");
    var selR = campo(campos, "Apuração sorteada");
    if (tipo === "estresse") selVar = campo(campos, "Modelo");
    var titulo = el("p", { class: "explorador-titulo" }, raiz);
    var leg = el("div", {}, raiz);
    var area = el("div", { class: "grafico" }, raiz);
    var deslize = el("label", { class: "deslize" }, raiz);
    deslize.appendChild(document.createTextNode("Momento da apuração "));
    var rng = el("input", { type: "range", min: 0, max: pcts.length - 1, step: 1, value: 0 }, deslize);
    var quadro = el("div", { class: "quadro", "aria-live": "polite" }, raiz);
    var i = 4, marcar = null;

    if (tipo === "estresse") {
      opcoes(selE, lista.map(function (a, k) { return { valor: k, texto: "2º turno presidencial " + a.ano }; }), lista.length - 1);
    } else {
      opcoes(selE, lista.map(function (e) { return { valor: e.id, texto: e.rotulo, grupo: String(e.ano) }; }));
    }
    if (selV) opcoes(selV, [{ valor: "moderado", texto: "moderado" }, { valor: "forte", texto: "forte (pessimista)" }]);

    function atual() {
      if (tipo === "estresse") return lista[+selE.value];
      for (var k = 0; k < lista.length; k++) if (lista[k].id === selE.value) return lista[k];
      return lista[0];
    }
    function bloco(e) { return selV ? e.vies[selV.value] : e; }

    function trocarEleicao() {
      var e = atual(), b = bloco(e);
      if (tipo === "estresse") {
        opcoes(selVar, e.variantes.map(function (v) { return { valor: v.id, texto: v.nome }; }));
        opcoes(selR, e.rodadas.map(function (r, k) {
          var g = Math.abs(r.gama);
          var nivel = g > 0.06 ? "viés forte" : g > 0.03 ? "viés como em 2026" : "viés leve";
          return { valor: k, texto: r.n + " · " + nivel + " nas cidades" };
        }));
      } else {
        opcoes(selR, b.rodadas.map(function (_, k) { return { valor: k, texto: String(k + 1) }; }));
      }
      desenhar();
    }

    function desenhar() {
      var e = atual(), b = bloco(e), r = (tipo === "estresse" ? e.rodadas : b.rodadas)[+selR.value || 0];
      var series = [], extra = [];
      leg.innerHTML = "";
      if (tipo === "t2") {
        series.push({ cor: CORES[0], pontos: r.pontos, real: e.real });
        titulo.textContent = e.rotulo + ": " + e.A + (e.pA ? " (" + e.pA + ")" : "") + " x " + e.B +
          (e.pB ? " (" + e.pB + ")" : "") + ". Linha: % de " + e.A + ", o mais votado no 1º turno, nos votos válidos.";
        legenda(leg, [{ cor: CORES[0], nome: "previsão para " + e.A }, { classe: "l-banda", cor: CORES[0], nome: "intervalos de 50% e 90%" },
          { classe: "l-real", nome: "resultado: " + num(e.real) + "%" }]);
      } else if (tipo === "t1") {
        e.candidatos.forEach(function (c, k) {
          series.push({ cor: CORES[k % CORES.length], pontos: r.cands[k], real: c.real, nome: c.nome });
        });
        titulo.textContent = e.rotulo + ": votação de cada candidato nos votos válidos.";
        legenda(leg, e.candidatos.map(function (c, k) {
          return { cor: CORES[k % CORES.length], nome: c.nome + (c.partido ? " (" + c.partido + ")" : "") };
        }).concat([{ classe: "l-real", nome: "resultado final" }]));
      } else {
        var v = selVar.value;
        series.push({ cor: CORES[0], pontos: r.var[v], real: r.final });
        extra.push({ pontos: r.parcial });
        titulo.textContent = "Apuração sintética " + r.n + " sobre o 2º turno presidencial de " + e.ano +
          ": % do candidato A nos válidos. Viés entre cidades (beta) " + num(r.beta, 2) +
          "; dentro das cidades (gama) " + num(r.gama, 2) + ".";
        legenda(leg, [{ cor: CORES[0], nome: "previsão" }, { classe: "l-banda", cor: CORES[0], nome: "intervalos de 50% e 90%" },
          { classe: "l-parcial", nome: "só o que já foi apurado" }, { classe: "l-real", nome: "resultado sorteado: " + num(r.final) + "%" }]);
      }
      // o momento escolhido precisa ter dados nesta série (o prefeito do 1º turno não tem 3% e 20%)
      while (i > 0 && !series[0].pontos[i]) i--;
      marcar = grafico(area, { pcts: pcts, series: series, extra: extra, i: i, ref50: tipo !== "t1",
        aoEscolher: function (k) { escolher(k); } });
      rng.value = i;
      ler();
    }

    function escolher(k) {
      var e = atual(), b = bloco(e), r = (tipo === "estresse" ? e.rodadas : b.rodadas)[+selR.value || 0];
      var p0 = tipo === "t1" ? r.cands[0] : tipo === "t2" ? r.pontos : r.var[selVar.value];
      var ok = function (j) { return p0[j] && p0[j][0] !== null; };
      if (!ok(k)) {  // momento sem rejogo (o prefeito do 1º turno não tem 3% e 20%): vai para o vizinho
        k = ok(k + (k >= i ? 1 : -1)) ? k + (k >= i ? 1 : -1) : i;
      }
      i = k; rng.value = k;
      if (marcar) marcar(k);
      ler();
    }

    function ler() {
      var e = atual(), b = bloco(e), r = (tipo === "estresse" ? e.rodadas : b.rodadas)[+selR.value || 0];
      var p = pcts[i];
      var momento = p === 0 ? "Antes de abrir as urnas" : "Com " + p + "% das seções apuradas";
      quadro.innerHTML = "";
      el("p", { class: "quadro-momento", texto: momento }, quadro);
      if (tipo === "t2" || tipo === "estresse") {
        var q = tipo === "t2" ? r.pontos[i] : r.var[selVar.value][i];
        var nomeA = tipo === "t2" ? e.A : "A", nomeB = tipo === "t2" ? e.B : "B";
        var real = tipo === "t2" ? e.real : r.final;
        var dentro = q[1] <= real && real <= q[4];
        var t = el("table", {}, quadro);
        var linhas = [
          ["Previsão para " + nomeA, num(q[0]) + "%"],
          ["Intervalo de 90%", num(q[1]) + "% a " + num(q[4]) + "%"],
          ["Chance de " + nomeA + " vencer", chance(q[5])],
          ["Chance de " + nomeB + " vencer", chance(q[5] === null ? null : 1 - q[5])],
          [tipo === "t2" ? "Resultado" : "Resultado sorteado", num(real) + "% " + (dentro ? "(dentro do intervalo)" : "(fora do intervalo)")]
        ];
        if (tipo === "estresse" && p > 0) linhas.splice(1, 0, ["Só o que já foi apurado", num(r.parcial[i]) + "%"]);
        linhas.forEach(function (l, k) {
          var tr = el("tr", {}, t);
          el("th", { texto: l[0] }, tr);
          var td = el("td", { class: "num", texto: l[1] }, tr);
          if (k === linhas.length - 1 && !dentro) td.className = "num neg";
        });
      } else {
        var t1 = el("table", {}, quadro);
        var cab = el("tr", {}, el("thead", {}, t1));
        var col = vagas && e.vagas === 2 ? "Chance de eleger (2 vagas)" : vagas ? "Chance de eleger" : "Vence no 1º turno";
        ["Candidato", "Previsão", "90%", col].concat(vagas ? [] : ["Vai ao 2º turno"]).concat(["Real"])
          .forEach(function (c, k) { el("th", { texto: c, class: k ? "num" : "" }, cab); });
        var tb = el("tbody", {}, t1);
        e.candidatos.forEach(function (c, k) {
          var q = r.cands[k][i];
          var tr = el("tr", {}, tb);
          var td = el("td", {}, tr);
          el("i", { class: "pino", style: "background:" + CORES[k % CORES.length] }, td);
          td.appendChild(document.createTextNode(c.nome));
          el("td", { class: "num", texto: num(q[0]) + "%" }, tr);
          el("td", { class: "num", texto: num(q[1]) + "–" + num(q[4]) + "%" }, tr);
          el("td", { class: "num", texto: chance(q[7]) }, tr);
          if (!vagas) el("td", { class: "num", texto: chance(q[6]) }, tr);
          var dentro = q[1] <= c.real && c.real <= q[4];
          el("td", { class: "num" + (dentro ? "" : " neg"), texto: num(c.real) + "%" }, tr);
        });
        if (!vagas && r.prob2t[i] !== null) {
          el("p", { class: "meta", texto: "Chance de haver 2º turno: " + chance(r.prob2t[i]) + "." }, quadro);
        }
      }
    }

    selE.addEventListener("change", trocarEleicao);
    if (selV) selV.addEventListener("change", trocarEleicao);
    selR.addEventListener("change", desenhar);
    if (selVar) selVar.addEventListener("change", desenhar);
    rng.addEventListener("input", function () { escolher(+rng.value); });
    var largura = 0;
    window.addEventListener("resize", function () {
      if (Math.abs(area.clientWidth - largura) > 40) { largura = area.clientWidth; desenhar(); }
    });

    raiz.escolherEleicao = function (id) {
      if (!lista.some(function (e) { return e.id === id; })) return false;
      selE.value = id; trocarEleicao();
      return true;
    };
    var inicial = raiz.getAttribute("data-inicial");
    if (inicial && lista.some(function (e) { return e.id === inicial; })) selE.value = inicial;
    trocarEleicao();
  }

  function iniciar() {
    var exps = Array.prototype.slice.call(document.querySelectorAll(".explorador"));
    var prontos = exps.map(function (raiz) {
      return carregar(raiz.getAttribute("data-dados")).then(function (d) { explorador(raiz, d); }, function () {
        raiz.innerHTML = '<p class="meta">Não foi possível carregar os dados deste gráfico.</p>';
      });
    });
    // links do índice das eleições: abrem a eleição no explorador da mesma seção
    document.addEventListener("click", function (ev) {
      var a = ev.target.closest ? ev.target.closest("a[data-eleicao]") : null;
      if (!a) return;
      var sec = a.closest("[data-secao]");
      var exp = sec && sec.querySelector(".explorador");
      if (exp && exp.escolherEleicao && exp.escolherEleicao(a.getAttribute("data-eleicao"))) {
        ev.preventDefault();
        exp.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    Promise.all(prontos).then(function () {
      var id = decodeURIComponent(location.hash.slice(1));
      if (!id) return;
      exps.some(function (exp) { return exp.escolherEleicao && exp.escolherEleicao(id); });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();
})();
