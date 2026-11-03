/* Motor da página de alianças: o mesmo cálculo de eleicoes/modelos/proporcional.py (distribuir), em JavaScript.
   tests/test_proporcional.py confere que os dois dão os mesmos eleitos. */
(function (raiz) {
  "use strict";

  function quociente(V, n) {
    var q = Math.floor(V / n), r = V - q * n;
    return q + (2 * r > n ? 1 : 0);
  }

  /* votos: {agrem: votos}; listas: {agrem: [[id, votos], ...] em ordem}; vagas; regra.
     Devolve {eleitos: [id...], qe}. */
  function distribuir(votos, listas, vagas, regra) {
    var nomes = Object.keys(votos).sort();
    var V = 0;
    nomes.forEach(function (a) { V += votos[a]; });
    if (V <= 0 || vagas <= 0) return { eleitos: [], qe: 0 };
    var qe = quociente(V, vagas);
    var pos = {}, cad = {}, eleitos = [];
    nomes.forEach(function (a) { pos[a] = 0; cad[a] = 0; if (!listas[a]) listas[a] = []; });
    function proximo(a, minimo) {
      var l = listas[a], i = pos[a];
      return i < l.length && l[i][1] >= minimo ? l[i][0] : null;
    }
    function eleger(a, id) { eleitos.push(id); pos[a] += 1; cad[a] += 1; }

    var maior = Math.max.apply(null, nomes.map(function (a) { return votos[a]; }));
    if (maior < qe) {
      var todos = [];
      nomes.forEach(function (a) { listas[a].forEach(function (c) { todos.push(c); }); });
      todos.sort(function (x, y) { return y[1] - x[1] || (x[2] < y[2] ? -1 : x[2] > y[2] ? 1 : 0); });
      return { eleitos: todos.slice(0, vagas).map(function (c) { return c[0]; }), qe: qe };
    }
    nomes.forEach(function (a) {
      var k = Math.floor(votos[a] / qe);
      for (var j = 0; j < k; j++) {
        var id = proximo(a, regra.minimo_qp * qe);
        if (id === null || eleitos.length >= vagas) break;
        eleger(a, id);
      }
    });
    var disputam = nomes.filter(function (a) { return votos[a] >= regra.barreira * qe; });
    var fase = "media";
    while (eleitos.length < vagas) {
      var aptos, minimo;
      if (fase === "media") {
        minimo = regra.minimo_sobras * qe;
        aptos = disputam.filter(function (a) { return proximo(a, minimo) !== null; });
        if (!aptos.length) { fase = "fase3"; continue; }
      } else {
        minimo = 0;
        var grupo = regra.fase3 === "barreira" ? disputam : nomes;
        aptos = grupo.filter(function (a) { return proximo(a, 0) !== null; });
        if (!aptos.length) aptos = nomes.filter(function (a) { return proximo(a, 0) !== null; });
        if (!aptos.length) break;
      }
      var melhor = null, bm = -1, bv = -1;
      aptos.forEach(function (a) {
        var m = votos[a] / (cad[a] + 1);
        if (m > bm || (m === bm && votos[a] > bv)) { melhor = a; bm = m; bv = votos[a]; }
      });
      eleger(melhor, proximo(melhor, minimo));
    }
    return { eleitos: eleitos, qe: qe };
  }

  /* dados: JSON exportado por scripts/aliancas.py; cenario: {base: "real"|"partido", grupos: [[siglas]], ufs: null|[UF]}.
     Devolve {UF: {eleitos: [índices de candidatos], qe, agrem: {sigla: lista}}}. */
  function simularUF(dados, uf, cenario) {
    var d = dados.ufs[uf], siglas = dados.partidos;
    var agrem = {}, votos = {}, listas = {};
    var aplica = !cenario.ufs || cenario.ufs.indexOf(uf) >= 0;
    Object.keys(d.p).forEach(function (s) {
      var a = cenario.base === "partido" ? s : d.p[s][1];
      if (aplica) {
        (cenario.grupos || []).forEach(function (g) {
          if (g.indexOf(s) >= 0) a = g.length > 1 ? "Aliança " + g.join(" / ") : g[0];
        });
      }
      agrem[s] = a;
      votos[a] = (votos[a] || 0) + d.p[s][0];
    });
    d.c.forEach(function (c, i) {
      var a = agrem[siglas[c[1]]] || siglas[c[1]];
      if (!(a in votos)) return;     // partido sem votos registrados na circunscrição (o motor em Python faz igual)
      (listas[a] = listas[a] || []).push([i, c[2], i]);
    });
    var r = distribuir(votos, listas, d.vagas, dados.regra);
    return { eleitos: r.eleitos, qe: r.qe, agrem: agrem };
  }

  function simular(dados, cenario) {
    var out = {};
    Object.keys(dados.ufs).sort().forEach(function (uf) { out[uf] = simularUF(dados, uf, cenario); });
    return out;
  }

  var Motor = { quociente: quociente, distribuir: distribuir, simularUF: simularUF, simular: simular };
  if (typeof module !== "undefined" && module.exports) module.exports = Motor;
  else raiz.Motor = Motor;
})(this);
