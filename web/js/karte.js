// IndraNet — Karte des Aktionsgebiets.
// Weltkarte aus Natural-Earth-Daten, die mitgeliefert werden: Es geht keine
// einzige Kachelanfrage nach außen, niemand erfährt, wohin Sie schauen.
// Orte als pulsierende Marken, Beziehungen als Bögen, Geldflüsse fließen.
// Umschaltbar auf einen drehbaren Globus.

/* global d3, topojson */
import { praed, LAGE_TEXT } from "./ui.js";
import { lageFarbe, typFarbe, farbe } from "./netz.js";

let weltDaten = null;
export function welt(aufloesung = "50m") {
  if (!weltDaten) weltDaten = {};
  if (!weltDaten[aufloesung]) {
    weltDaten[aufloesung] = fetch(`/vendor/countries-${aufloesung}.json`).then(r => r.json()).then(t => ({
      laender: topojson.feature(t, t.objects.countries).features,
      grenzen: topojson.mesh(t, t.objects.countries, (a, b) => a !== b),
      land: topojson.feature(t, t.objects.land),
    }));
  }
  return weltDaten[aufloesung];
}

export function karteZeichnen(huelle, daten, opt = {}) {
  const mini = !!opt.mini;
  let modus = opt.modus || "karte";          // karte | globus
  const B = () => huelle.clientWidth || 800;
  const H = () => huelle.clientHeight || 500;

  const svg = d3.select(huelle).append("svg").attr("role", "img")
    .attr("aria-label", "Karte der Orte und Verbindungen");
  const defs = svg.append("defs");
  const verlauf = defs.append("radialGradient").attr("id", "meer-verlauf");
  verlauf.append("stop").attr("offset", "0%").attr("stop-color", farbe("--flaeche"));
  verlauf.append("stop").attr("offset", "100%").attr("stop-color", farbe("--meer"));
  const leuchten = defs.append("filter").attr("id", "marker-glanz").attr("x", "-100%").attr("y", "-100%").attr("width", "300%").attr("height", "300%");
  leuchten.append("feGaussianBlur").attr("stdDeviation", 3).attr("result", "b");
  const mg = leuchten.append("feMerge");
  mg.append("feMergeNode").attr("in", "b");
  mg.append("feMergeNode").attr("in", "SourceGraphic");

  const wurzel = svg.append("g");
  const gGrund = wurzel.append("g");
  const gBoegen = wurzel.append("g");
  const gMarker = wurzel.append("g");

  const tip = document.createElement("div");
  tip.className = "tooltip";
  tip.hidden = true;
  document.body.append(tip);

  let projektion, pfad, k = 1, drehung = [-10, -25, 0], laeuft = null, geo = null;
  const zoom = d3.zoom().scaleExtent([1, 40]).on("zoom", ev => {
    if (modus !== "karte") return;
    k = ev.transform.k;
    wurzel.attr("transform", ev.transform);
    massstab();
  });

  function projektionBauen() {
    if (modus === "globus") {
      const r = Math.min(B(), H()) / 2 - 16;
      projektion = d3.geoOrthographic().scale(r).translate([B() / 2, H() / 2]).rotate(drehung).clipAngle(90);
    } else {
      projektion = d3.geoNaturalEarth1().fitExtent([[12, 12], [B() - 12, H() - 12]], { type: "Sphere" });
    }
    pfad = d3.geoPath(projektion);
  }

  function orte() { return daten.orte || []; }
  function ortNach(id) { return orte().find(o => o.id === id); }

  function grundZeichnen() {
    gGrund.selectAll("*").remove();
    gGrund.append("path").datum({ type: "Sphere" }).attr("class", "meer").attr("fill", modus === "globus" ? "url(#meer-verlauf)" : null);
    gGrund.append("path").datum(d3.geoGraticule10()).attr("class", "gitter");
    if (!geo) return;
    const aktiv = new Set();
    for (const o of orte()) {
      const l = geo.laender.find(f => d3.geoContains(f, [o.lon, o.lat]));
      if (l) aktiv.add(l.id);
    }
    gGrund.selectAll("path.land").data(geo.laender).join("path")
      .attr("class", d => `land${aktiv.has(d.id) ? " aktiv" : ""}`)
      .on("mouseenter", (ev, d) => !mini && zeigeTip(ev, `<b>${esc(d.properties.name)}</b>`))
      .on("mousemove", bewegeTip).on("mouseleave", () => tip.hidden = true)
      .on("click", (ev, d) => {
        if (opt.onKlickOrt) {
          const [lon, lat] = projektion.invert(d3.pointer(ev, wurzel.node()));
          opt.onKlickOrt({ lat, lon, land: d.properties.name });
        }
      });
    gGrund.append("path").datum({ type: "Sphere" }).attr("class", "umriss");
  }

  function bogenPfad(a, b) {
    if (modus === "globus") {
      return pfad({ type: "LineString", coordinates: [[a.lon, a.lat], [b.lon, b.lat]] });
    }
    const p = projektion([a.lon, a.lat]), q = projektion([b.lon, b.lat]);
    if (!p || !q) return null;
    const dx = q[0] - p[0], dy = q[1] - p[1], l = Math.hypot(dx, dy);
    const hub = Math.min(160, l * .32);
    const mx = (p[0] + q[0]) / 2 + dy / (l || 1) * hub * .25, my = (p[1] + q[1]) / 2 - hub;
    return `M${p[0]},${p[1]}Q${mx},${my} ${q[0]},${q[1]}`;
  }

  function zeichnen() {
    projektionBauen();
    grundZeichnen();
    gGrund.selectAll("path").attr("d", pfad);

    // Bögen: mehrere Fakten zwischen denselben Orten bündeln
    const buendel = new Map();
    for (const b of daten.boegen || []) {
      const s = `${b.von}>${b.nach}`;
      if (!buendel.has(s)) buendel.set(s, { ...b, fakten: [] });
      buendel.get(s).fakten.push(b);
    }
    const boegen = [...buendel.values()].map(b => {
      const lagen = b.fakten.map(f => f.beleglage);
      b.lage = lagen.includes("UMSTRITTEN") ? "UMSTRITTEN" : lagen.includes("BESTAETIGT") ? "BESTAETIGT" : "EINFACH_BELEGT";
      b.geld = b.fakten.some(f => f.praedikat === "paid_to");
      return b;
    });
    gBoegen.selectAll("path").data(boegen, d => d.von + ">" + d.nach).join("path")
      .attr("class", d => `bogen${d.geld ? " fluss" : ""}`)
      .attr("stroke", d => d.geld ? farbe("--t-betrag") : lageFarbe(d.lage))
      .attr("stroke-opacity", .85)
      .attr("d", d => { const a = ortNach(d.von), z = ortNach(d.nach); return a && z ? bogenPfad(a, z) : null; })
      .on("mouseenter", (ev, d) => zeigeTip(ev, d.fakten.map(f =>
        `<b>${esc(f.subjekt)}</b> <span class="mono" style="color:var(--akzent)">${esc(praed(f.praedikat))}</span> <b>${esc(f.objekt)}</b> <span class="gedaempft">· ${LAGE_TEXT[f.beleglage]}</span>`).join("<br>")))
      .on("mousemove", bewegeTip).on("mouseleave", () => tip.hidden = true)
      .on("click", (ev, d) => opt.onBogen?.(d));

    const marker = gMarker.selectAll("g.marker").data(orte(), d => d.id).join(enter => {
      const g = enter.append("g").attr("class", "marker");
      g.append("circle").attr("class", "welle");
      g.append("circle").attr("class", "kern").attr("filter", "url(#marker-glanz)");
      g.append("text").attr("class", "zahl").attr("text-anchor", "middle").attr("dy", "0.35em");
      g.append("text").attr("class", "name");
      return g;
    });
    marker.select("circle.welle").attr("stroke", d => markerFarbe(d))
      .style("animation-delay", (d, i) => `${(i * 0.37) % 2.6}s`);
    marker.select("circle.kern").attr("fill", d => markerFarbe(d));
    marker.select("text.zahl").text(d => d.entitaeten.length || "");
    marker.select("text.name").text(d => d.name).style("display", mini ? "none" : null);
    marker.on("mouseenter", (ev, d) => zeigeTip(ev, `<b>${esc(d.name)}</b><br>` +
        (d.entitaeten.length ? d.entitaeten.slice(0, 12).map(e => `<span style="color:${typFarbe(e.typ)}">●</span> ${esc(e.name)} <span class="gedaempft">(${esc(praed(e.praedikat))})</span>`).join("<br>") : '<span class="gedaempft">Ort ohne verankerte Entitäten</span>')))
      .on("mousemove", bewegeTip).on("mouseleave", () => tip.hidden = true)
      .on("click", (ev, d) => { ev.stopPropagation(); opt.onOrt?.(d); });
    positionieren();
    massstab();
  }

  function markerFarbe(d) {
    if (!d.entitaeten.length) return farbe("--t-place");
    const lagen = d.entitaeten.map(e => e.beleglage);
    if (lagen.includes("UMSTRITTEN")) return farbe("--umstritten");
    return farbe("--akzent");
  }

  function positionieren() {
    gMarker.selectAll("g.marker").each(function (d) {
      const p = projektion([d.lon, d.lat]);
      const sichtbar = modus !== "globus" ||
        d3.geoDistance([d.lon, d.lat], [-drehung[0], -drehung[1]]) < Math.PI / 2;
      d3.select(this).style("display", p && sichtbar ? null : "none")
        .attr("transform", p ? `translate(${p[0]},${p[1]})` : null);
    });
  }

  function massstab() {
    const s = modus === "karte" ? 1 / Math.sqrt(k) : 1;
    gMarker.selectAll("g.marker").each(function (d) {
      const r = (mini ? 3.5 : 5) + Math.sqrt(d.entitaeten.length) * (mini ? 2 : 3);
      const g = d3.select(this);
      g.select("circle.kern").attr("r", r * s);
      g.select("circle.welle").attr("r", r * s);
      g.select("text.zahl").style("font-size", `${10 * s}px`).style("display", d.entitaeten.length && r * s > 7 ? null : "none");
      g.select("text.name").attr("x", r * s + 5 * s).attr("dy", "0.35em").style("font-size", `${11 * s}px`);
    });
    gBoegen.selectAll("path").attr("stroke-width", (modus === "karte" ? 1.8 / Math.sqrt(k) : 1.6));
    gGrund.selectAll("path.land").attr("stroke-width", .5 / k);
    gGrund.selectAll("path.gitter").attr("stroke-width", .5 / k);
  }

  function aktionsgebiet(dauer = 900) {
    if (modus !== "karte") return;
    const pkt = orte().map(o => projektion([o.lon, o.lat])).filter(Boolean);
    if (!pkt.length) { svg.transition().duration(dauer).call(zoom.transform, d3.zoomIdentity); return; }
    const [x0, x1] = d3.extent(pkt, p => p[0]), [y0, y1] = d3.extent(pkt, p => p[1]);
    const rand = mini ? 40 : 90;
    const s = Math.max(1, Math.min(8, .9 / Math.max((x1 - x0 + rand * 2) / B(), (y1 - y0 + rand * 2) / H())));
    svg.transition().duration(dauer).call(zoom.transform,
      d3.zoomIdentity.translate(B() / 2, H() / 2).scale(s).translate(-(x0 + x1) / 2, -(y0 + y1) / 2));
  }

  function globusDrehen() {
    stopDrehen();
    let letzte = 0;               // d3.timer zählt ab Start, nicht absolut
    const t = d3.timer(jetzt => {
      if (modus !== "globus") return;
      drehung[0] += (jetzt - letzte) * 0.006;
      letzte = jetzt;
      projektion.rotate(drehung);
      gGrund.selectAll("path").attr("d", pfad);
      gBoegen.selectAll("path").attr("d", d => { const a = ortNach(d.von), z = ortNach(d.nach); return a && z ? bogenPfad(a, z) : null; });
      positionieren();
    });
    laeuft = t;
  }
  function stopDrehen() { if (laeuft) { laeuft.stop(); laeuft = null; } }

  const ziehGlobus = d3.drag().on("start", stopDrehen).on("drag", ev => {
    if (modus !== "globus") return;
    const s = 75 / projektion.scale();
    drehung = [drehung[0] + ev.dx * s * 2, Math.max(-80, Math.min(80, drehung[1] - ev.dy * s * 2)), 0];
    projektion.rotate(drehung);
    gGrund.selectAll("path").attr("d", pfad);
    gBoegen.selectAll("path").attr("d", d => { const a = ortNach(d.von), z = ortNach(d.nach); return a && z ? bogenPfad(a, z) : null; });
    positionieren();
  });

  function modusSetzen(m) {
    modus = m;
    stopDrehen();
    svg.on(".zoom", null).on(".drag", null);
    wurzel.attr("transform", null);
    k = 1;
    if (modus === "karte") {
      svg.call(zoom);
      svg.call(zoom.transform, d3.zoomIdentity);
      zeichnen();
      setTimeout(() => aktionsgebiet(), 50);
    } else {
      // Globus auf den Schwerpunkt des Aktionsgebiets ausrichten
      if (orte().length) {
        const lon = d3.mean(orte(), o => o.lon), lat = d3.mean(orte(), o => o.lat);
        drehung = [-lon, -lat * .6, 0];
      }
      svg.call(ziehGlobus);
      zeichnen();
      if (opt.drehen !== false) globusDrehen();
    }
  }

  function zeigeTip(ev, html) { tip.innerHTML = html; tip.hidden = false; bewegeTip(ev); }
  function bewegeTip(ev) {
    tip.style.left = Math.min(ev.clientX + 14, innerWidth - 340) + "px";
    tip.style.top = (ev.clientY + 14) + "px";
  }

  welt(mini ? "110m" : "50m").then(w => { geo = w; modusSetzen(modus); });
  projektionBauen();

  const beob = new ResizeObserver(() => { if (geo) { zeichnen(); if (modus === "karte") aktionsgebiet(0); } });
  beob.observe(huelle);

  return {
    setzen(neu) { daten = neu; if (geo) { zeichnen(); if (modus === "karte") aktionsgebiet(); } },
    modus: modusSetzen,
    aktionsgebiet,
    zuOrt(o) {
      if (modus === "karte") {
        const p = projektion([o.lon, o.lat]);
        svg.transition().duration(800).call(zoom.transform, d3.zoomIdentity.translate(B() / 2, H() / 2).scale(5).translate(-p[0], -p[1]));
      } else { drehung = [-o.lon, -o.lat, 0]; stopDrehen(); projektion.rotate(drehung); zeichnen(); }
    },
    zerstoeren() { stopDrehen(); beob.disconnect(); tip.remove(); svg.remove(); },
  };
}

// --------------------------------------------- Startbild: Globus auf Canvas
export function startGlobus(canvas) {
  const ctx = canvas.getContext("2d");
  let lauf = null;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  welt("110m").then(w => {
    const groesse = () => {
      const r = canvas.getBoundingClientRect();
      canvas.width = r.width * dpr; canvas.height = r.height * dpr;
      return r;
    };
    let r = groesse();
    const proj = d3.geoOrthographic().clipAngle(90);
    const pfad = d3.geoPath(proj, ctx);
    const gitter = d3.geoGraticule10();
    // Ein paar Lichtpunkte über den Kontinenten — rein dekorativ
    const punkte = d3.range(140).map(() => {
      let p; do { p = [Math.random() * 360 - 180, Math.random() * 140 - 60]; } while (!d3.geoContains(w.land, p));
      return { p, t: Math.random() * 6 };
    });
    const paare = d3.range(14).map(() => [punkte[Math.floor(Math.random() * punkte.length)].p, punkte[Math.floor(Math.random() * punkte.length)].p]);
    const akzent = farbe("--akzent"), linie = farbe("--linie-hell"), land = farbe("--land"), rand = farbe("--land-rand");
    window.addEventListener("resize", () => { r = groesse(); });
    lauf = d3.timer(t => {
      const s = Math.min(r.width, r.height) / 2 * dpr * .92;
      proj.scale(s).translate([r.width * dpr / 2, r.height * dpr / 2]).rotate([t * 0.008, -18, 0]);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const glanz = ctx.createRadialGradient(r.width * dpr / 2, r.height * dpr / 2, s * .2, r.width * dpr / 2, r.height * dpr / 2, s * 1.08);
      glanz.addColorStop(0, "rgba(56,225,208,0.05)"); glanz.addColorStop(1, "rgba(56,225,208,0)");
      ctx.fillStyle = glanz; ctx.beginPath(); ctx.arc(r.width * dpr / 2, r.height * dpr / 2, s * 1.08, 0, 2 * Math.PI); ctx.fill();
      ctx.beginPath(); pfad({ type: "Sphere" }); ctx.strokeStyle = linie; ctx.lineWidth = dpr; ctx.stroke();
      ctx.beginPath(); pfad(gitter); ctx.strokeStyle = "rgba(56,225,208,0.07)"; ctx.lineWidth = .6 * dpr; ctx.stroke();
      ctx.beginPath(); pfad(w.land); ctx.fillStyle = land; ctx.fill(); ctx.strokeStyle = rand; ctx.lineWidth = .6 * dpr; ctx.stroke();
      ctx.lineWidth = 1.1 * dpr;
      for (const [a, b] of paare) {
        ctx.beginPath(); pfad({ type: "LineString", coordinates: [a, b] });
        ctx.strokeStyle = "rgba(56,225,208,0.32)"; ctx.stroke();
      }
      const mitte = proj.invert([r.width * dpr / 2, r.height * dpr / 2]);
      for (const q of punkte) {
        if (d3.geoDistance(q.p, mitte) > Math.PI / 2) continue;
        const [x, y] = proj(q.p);
        const a = .35 + .65 * Math.abs(Math.sin(t / 900 + q.t));
        ctx.fillStyle = akzent; ctx.globalAlpha = a;
        ctx.beginPath(); ctx.arc(x, y, 1.6 * dpr, 0, 2 * Math.PI); ctx.fill();
        ctx.globalAlpha = 1;
      }
    });
  });
  return { stop() { lauf?.stop(); } };
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
