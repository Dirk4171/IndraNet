// IndraNet — Netzansicht. Kraftgraph aus Entitäten und Fakten.
// Kanten nach Beleglage gefärbt; Geldflüsse (paid_to) fließen sichtbar;
// Umstrittenes pulsiert rot. Klick wählt, Doppelklick zeigt das Umfeld.

/* global d3 */
import { praed, TYP_TEXT, LAGE_TEXT } from "./ui.js";

const FORM = {
  PERSON: d3.symbolCircle, ORG: d3.symbolSquare, PLACE: d3.symbolDiamond,
  VESSEL: d3.symbolTriangle, ADRESSE: d3.symbolDiamond, AMT: d3.symbolWye,
  KENNUNG: d3.symbolCross, BETRAG: d3.symbolStar, DATUM: d3.symbolCross,
  REGISTER: d3.symbolSquare,
};

export function farbe(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}
export function typFarbe(typ) {
  return farbe(`--t-${(typ || "org").toLowerCase()}`) || farbe("--t-org");
}
export function lageFarbe(lage) {
  return farbe({ BESTAETIGT: "--bestaetigt", EINFACH_BELEGT: "--einfach",
    UMSTRITTEN: "--umstritten", WIDERRUFEN: "--widerrufen" }[lage] || "--gedaempft");
}

export function netzZeichnen(huelle, daten, opt = {}) {
  const mini = !!opt.mini;
  const breite = () => huelle.clientWidth || 800;
  const hoehe = () => huelle.clientHeight || 600;

  const svg = d3.select(huelle).append("svg").attr("role", "img")
    .attr("aria-label", "Netz der Entitäten und Beziehungen");
  const defs = svg.append("defs");
  const glanz = defs.append("filter").attr("id", "glanz").attr("x", "-80%").attr("y", "-80%")
    .attr("width", "260%").attr("height", "260%");
  glanz.append("feGaussianBlur").attr("stdDeviation", 4).attr("result", "b");
  const m = glanz.append("feMerge");
  m.append("feMergeNode").attr("in", "b");
  m.append("feMergeNode").attr("in", "SourceGraphic");
  for (const lage of ["BESTAETIGT", "EINFACH_BELEGT", "UMSTRITTEN", "WIDERRUFEN"]) {
    defs.append("marker").attr("id", `pfeil-${lage}`).attr("viewBox", "0 -4 8 8")
      .attr("refX", 8).attr("refY", 0).attr("markerWidth", 6).attr("markerHeight", 6)
      .attr("orient", "auto").append("path").attr("d", "M0,-4L8,0L0,4").attr("fill", lageFarbe(lage));
  }

  const welt = svg.append("g");
  const gKanten = welt.append("g");
  const gKantenText = welt.append("g");
  const gKnoten = welt.append("g");
  let k = 1;

  const zoom = d3.zoom().scaleExtent([0.12, 6]).on("zoom", (ev) => {
    welt.attr("transform", ev.transform);
    k = ev.transform.k;
    beschriften();
  });
  svg.call(zoom).on("dblclick.zoom", null);

  const tip = document.createElement("div");
  tip.className = "tooltip";
  tip.hidden = true;
  document.body.append(tip);

  let knoten = [], kanten = [], gewaehlt = null, nachbarn = new Map();
  let simulation = null, selKnoten, selKanten, selKantenText, ersteMal = true;

  function radius(d) { return Math.min(26, 6 + Math.sqrt(d.grad || 0) * 3.4) * (mini ? .8 : 1); }

  function setzen(neu) {
    const alt = new Map(knoten.map(n => [n.id, n]));
    knoten = neu.knoten.filter(n => opt.alleKnoten || n.grad > 0 || neu.kanten.length === 0)
      .map(n => Object.assign(alt.get(n.id) || {}, n));
    const ids = new Set(knoten.map(n => n.id));
    // Mehrere Fakten zwischen demselben Paar: als gefächerte Bögen
    const paar = new Map();
    kanten = neu.kanten.filter(f => ids.has(f.s) && ids.has(f.o)).map(f => {
      const schl = [f.s, f.o].sort().join("|");
      const n = paar.get(schl) || 0;
      paar.set(schl, n + 1);
      return { ...f, source: f.s, target: f.o, nr: n };
    });
    nachbarn = new Map();
    for (const f of kanten) {
      if (!nachbarn.has(f.s)) nachbarn.set(f.s, new Set());
      if (!nachbarn.has(f.o)) nachbarn.set(f.o, new Set());
      nachbarn.get(f.s).add(f.o); nachbarn.get(f.o).add(f.s);
    }
    zeichnen();
  }

  function zeichnen() {
    selKanten = gKanten.selectAll("path").data(kanten, d => d.fact_id).join("path")
      .attr("class", d => `kante-linie ${d.beleglage}${d.praedikat === "paid_to" ? " fluss" : ""}`)
      .attr("stroke", d => lageFarbe(d.beleglage))
      .attr("stroke-width", d => d.beleglage === "BESTAETIGT" ? 2.2 : 1.4)
      .attr("marker-end", d => mini ? null : `url(#pfeil-${d.beleglage})`)
      .style("stroke-dasharray", d => d.praedikat === "paid_to" ? "2 6" : null)
      .style("animation", d => d.praedikat === "paid_to" ? "fliessen .9s linear infinite" : null)
      .on("mouseenter", (ev, d) => zeigeTip(ev, `<b>${esc(d.subjekt)}</b> <span class="mono" style="color:var(--akzent)">${esc(praed(d.praedikat))}</span> <b>${esc(d.objekt)}</b><br><span class="gedaempft">${LAGE_TEXT[d.beleglage]} · ${d.quellen.length} Quelle(n): ${esc(d.quellen.join(", "))}</span>`))
      .on("mousemove", bewegeTip).on("mouseleave", () => tip.hidden = true)
      .on("click", (ev, d) => { ev.stopPropagation(); opt.onKante?.(d); });

    selKantenText = gKantenText.selectAll("text").data(mini ? [] : kanten, d => d.fact_id).join("text")
      .attr("class", "kante-text").attr("text-anchor", "middle").text(d => praed(d.praedikat));

    selKnoten = gKnoten.selectAll("g.knoten").data(knoten, d => d.id).join(enter => {
      const g = enter.append("g").attr("class", "knoten");
      g.append("circle").attr("class", "ring").attr("r", 14).attr("fill", "none");
      g.append("path").attr("class", "form");
      g.append("text").attr("class", "name").attr("dy", "0.32em");
      g.append("text").attr("class", "stern").attr("text-anchor", "middle");
      return g;
    });
    selKnoten.classed("markiert", d => d.markiert)
      .call(d3.drag().on("start", ziehStart).on("drag", ziehen).on("end", ziehEnde))
      .on("click", (ev, d) => { ev.stopPropagation(); waehlen(d.id); opt.onKnoten?.(d); })
      .on("dblclick", (ev, d) => { ev.stopPropagation(); opt.onDoppel?.(d); })
      .on("mouseenter", (ev, d) => zeigeTip(ev, `<b>${esc(d.name)}</b><br><span class="gedaempft">${TYP_TEXT[d.typ] || d.typ} · ${d.grad} Verbindung(en)</span>${d.beschreibung ? "<br>" + esc(d.beschreibung) : ""}`))
      .on("mousemove", bewegeTip).on("mouseleave", () => tip.hidden = true);
    selKnoten.select("path.form")
      .attr("d", d => d3.symbol(FORM[d.typ] || d3.symbolCircle, Math.PI * radius(d) ** 2 * .9)())
      .attr("fill", d => typFarbe(d.typ))
      .attr("filter", d => d.markiert ? "url(#glanz)" : null);
    selKnoten.select("text.name").attr("x", d => radius(d) + 5).text(d => d.name);
    selKnoten.select("text.stern").attr("y", d => -radius(d) - 4).text(d => d.markiert ? "★" : "");
    svg.on("click", () => { waehlen(null); opt.onLeer?.(); });

    if (simulation) simulation.stop();
    simulation = d3.forceSimulation(knoten)
      .force("link", d3.forceLink(kanten).id(d => d.id).distance(d => mini ? 55 : 90 + (d.nr * 10)).strength(.7))
      .force("ladung", d3.forceManyBody().strength(mini ? -140 : -320))
      .force("kollision", d3.forceCollide().radius(d => radius(d) + (mini ? 4 : 10)))
      .force("x", d3.forceX(breite() / 2).strength(.045))
      .force("y", d3.forceY(hoehe() / 2).strength(.06))
      .alphaDecay(.028)
      .on("tick", ticken)
      .stop();
    // Layout vorab rechnen, damit das Netz sofort ruhig und eingepasst
    // erscheint, statt erst durchs Bild zu schwingen.
    const neueKnoten = knoten.some(n => n.x === undefined || n.vx === undefined);
    for (let i = 0; i < (neueKnoten ? 260 : 40); i++) simulation.tick();
    ticken();
    einpassen(neueKnoten && !ersteMal ? 500 : 0);
    ersteMal = false;
    simulation.alpha(.04).restart();
    beschriften();
    hervorheben();
  }

  function kurve(d) {
    const sx = d.source.x, sy = d.source.y, tx = d.target.x, ty = d.target.y;
    const dx = tx - sx, dy = ty - sy, l = Math.hypot(dx, dy) || 1;
    const rt = radius(d.target) + 3;
    const ex = tx - dx / l * rt, ey = ty - dy / l * rt;
    if (!d.nr) return `M${sx},${sy}L${ex},${ey}`;
    const bogen = (d.nr % 2 ? 1 : -1) * Math.ceil(d.nr / 2) * 26;
    const mx = (sx + ex) / 2 - dy / l * bogen, my = (sy + ey) / 2 + dx / l * bogen;
    return `M${sx},${sy}Q${mx},${my} ${ex},${ey}`;
  }

  function ticken() {
    selKanten.attr("d", kurve);
    selKantenText.attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2 - 4 - d.nr * 8);
    selKnoten.attr("transform", d => `translate(${d.x},${d.y})`);
  }

  function beschriften() {
    if (!selKnoten) return;
    selKnoten.select("text.name").style("display", d =>
      (mini ? d.grad >= 3 || d.markiert : (k > .55 || d.grad >= 3 || d.markiert || d.id === gewaehlt)) ? null : "none");
    selKantenText?.style("display", k > 1.15 && !mini ? null : "none");
  }

  function hervorheben() {
    if (!selKnoten) return;
    const nb = gewaehlt ? nachbarn.get(gewaehlt) || new Set() : null;
    selKnoten.classed("gewaehlt", d => d.id === gewaehlt)
      .classed("gedimmt", d => nb !== null && d.id !== gewaehlt && !nb.has(d.id));
    selKanten.classed("gedimmt", d => nb !== null && d.s !== gewaehlt && d.o !== gewaehlt);
    beschriften();
  }

  function waehlen(id) { gewaehlt = id; hervorheben(); }

  function ziehStart(ev, d) { if (!ev.active) simulation.alphaTarget(.25).restart(); d.fx = d.x; d.fy = d.y; }
  function ziehen(ev, d) { d.fx = ev.x; d.fy = ev.y; }
  function ziehEnde(ev, d) { if (!ev.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }

  function zeigeTip(ev, html) { tip.innerHTML = html; tip.hidden = false; bewegeTip(ev); }
  function bewegeTip(ev) {
    const x = Math.min(ev.clientX + 14, innerWidth - 340);
    tip.style.left = x + "px"; tip.style.top = (ev.clientY + 14) + "px";
  }

  function zentrieren(id, massstab = 1.4) {
    const n = knoten.find(x => x.id === id);
    if (!n || n.x === undefined) return;
    svg.transition().duration(650).call(zoom.transform,
      d3.zoomIdentity.translate(breite() / 2, hoehe() / 2).scale(massstab).translate(-n.x, -n.y));
  }

  function einpassen(dauer = 700) {
    if (!knoten.length) return;
    const xs = knoten.map(n => n.x), ys = knoten.map(n => n.y);
    const [x0, x1, y0, y1] = [d3.min(xs) - 40, d3.max(xs) + 120, d3.min(ys) - 30, d3.max(ys) + 30];
    const s = Math.min(mini ? 1.3 : 1.8, .92 / Math.max((x1 - x0) / breite(), (y1 - y0) / hoehe(), .01));
    const t = d3.zoomIdentity.translate(breite() / 2, hoehe() / 2).scale(s).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    if (dauer) svg.transition().duration(dauer).call(zoom.transform, t);
    else svg.call(zoom.transform, t);
  }

  function filtern(text) {
    const t = (text || "").trim().toLowerCase();
    if (!t) { waehlen(null); return; }
    const treffer = knoten.find(n => n.name.toLowerCase().includes(t));
    if (treffer) { waehlen(treffer.id); zentrieren(treffer.id); opt.onKnoten?.(treffer); }
  }

  setzen(daten);

  let letzteGroesse = `${breite()}x${hoehe()}`;
  const beob = new ResizeObserver(() => {
    const g = `${breite()}x${hoehe()}`;
    if (g === letzteGroesse) return;
    letzteGroesse = g;
    einpassen(0);
  });
  beob.observe(huelle);

  return {
    setzen, waehlen, zentrieren, einpassen, filtern,
    neuMischen() { simulation.alpha(1).restart(); },
    zerstoeren() { simulation?.stop(); beob.disconnect(); tip.remove(); svg.remove(); },
  };
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
