// IndraNet — Lagebilder: qualifizierte Analysen der KI über den geprüften
// Bestand, in Text und Bild — Kernaussagen mit Beleglage, Schlüsselfiguren
// im Netzausschnitt, Geldflüsse, Zeitleiste, Lücken, Warnsignale.

/* global d3 */
import * as api from "./api.js";
import { el, leeren, fehler, melden, lageAbz, markdown, zeit, bestaetigen } from "./ui.js";
import { netzZeichnen, farbe } from "./netz.js";
import { akteZeigen } from "./akte.js";
import { senden } from "./zustand.js";

export const LAGEBILDER = {
  voll: true,
  komponenten: [],
  async zeigen(main, lagebildId) {
    const { lagebilder } = await api.get("lagebilder");
    const liste = el("div", { class: "spalte-liste" });
    const detail = el("div", { class: "spalte-detail" });
    main.append(el("div", { class: "zweispaltig" }, liste, detail));

    const frage = el("textarea", { rows: 3, placeholder: "Frage an den Bestand (leer = Gesamtlage), z. B. »Über welche Rechtsordnungen fließt das Geld?«" });
    liste.append(el("div", { class: "tafel", style: { padding: "12px" } },
      el("div", { class: "tafel-kopf" }, "Neues Lagebild"), frage,
      el("button", { class: "knopf haupt", onclick: async () => {
        try {
          const r = await api.post("lagebild", { frage: frage.value.trim() });
          senden("auftrag-gestartet", r.auftrag);
          frage.value = ""; if (!r.bruecke) melden("Die KI analysiert den Bestand …");
        } catch (e) { fehler(e); }
      } }, "Analysieren")));
    if (!lagebilder.length) {
      detail.append(el("div", { class: "seiteninhalt" }, el("div", { class: "leer" }, el("b", {}, "Noch kein Lagebild"),
        "Ein Lagebild fasst den geprüften Bestand zusammen: Was ist belegt, was nur behauptet, wo sind Lücken, welche Muster zeigen sich. Die KI kennzeichnet ihre eigenen Schlussfolgerungen getrennt von den Fakten.")));
      return;
    }
    for (const l of lagebilder) {
      liste.append(el("div", { class: "fund-karte", "data-id": l.lagebild_id, onclick: () => waehlen(l.lagebild_id) },
        el("div", { class: "titel" }, l.titel),
        el("div", { class: "meta" }, el("span", {}, zeit(l.ts)), el("span", {}, (l.inhalt.kernaussagen || []).length + " Kernaussagen")),
        l.frage ? el("div", { class: "gedaempft", style: { fontSize: "12px" } }, `»${l.frage}«`) : null));
    }
    const waehlen = async (id) => {
      liste.querySelectorAll(".fund-karte").forEach(k => k.classList.toggle("aktiv", k.dataset.id === id));
      LAGEBILDER.verlassen();
      const l = lagebilder.find(x => x.lagebild_id === id);
      leeren(detail).append(await bericht(l, LAGEBILDER.komponenten, async () => {
        await api.post("lagebild/loeschen", { id });
        senden("zeige", { ansicht: "lagebilder" });
      }));
    };
    waehlen(lagebildId && lagebilder.some(l => l.lagebild_id === lagebildId) ? lagebildId : lagebilder[0].lagebild_id);
  },
  verlassen() { LAGEBILDER.komponenten.forEach(c => c.zerstoeren()); LAGEBILDER.komponenten = []; },
};

async function bericht(l, komponenten, loeschen) {
  const i = l.inhalt;
  const figuren = i.schluesselfiguren || [];
  const huelle = el("div", { class: "mini-netz" });
  const wrap = el("div", { class: "seiteninhalt" },
    el("div", { class: "kopfzeile" },
      el("div", {}, el("span", { class: "etikett" }, `Lagebild · ${zeit(l.ts)} · ${l.modell || ""}`), el("h2", { style: { marginTop: "6px" } }, i.titel || "Lagebild"),
        l.frage ? el("p", {}, `Frage: ${l.frage}`) : null),
      el("div", { class: "rechts" },
        el("button", { class: "knopf", onclick: () => exportieren(l) }, "⇩ Als Markdown"),
        el("button", { class: "knopf gefahr klein", onclick: async () => { if (await bestaetigen("Lagebild löschen?", "Der Bestand bleibt unverändert.", { ok: "Löschen", gefahr: true })) loeschen(); } }, "Löschen"))),
    i.kernaussagen?.length ? el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "01"), "Kernaussagen"),
      el("ul", { class: "liste" }, i.kernaussagen.map(k => el("li", {}, el("div", { class: "zeile" }, lageAbz(k.beleglage), el("span", {}, k.aussage)))))) : null,
    el("div", { class: "raster-2" },
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "02"), "Lage"),
        el("div", { class: "bericht", html: markdown(i.lage) })),
      el("div", { style: { display: "grid", gap: "14px", alignContent: "start" } },
        figuren.length ? el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "03"), "Schlüsselfiguren"),
          huelle,
          el("ul", { class: "liste" }, figuren.map(f => el("li", {}, el("b", {}, f.name), el("span", { class: "gedaempft", style: { fontSize: "12.5px" } }, f.rolle))))) : null,
        i.geldfluesse?.length ? el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "04"), "Geldflüsse"),
          el("div", { class: "fluss-liste" }, i.geldfluesse.map(g => el("div", { class: "fluss" }, el("b", {}, g.von),
            el("span", { class: "pfeil" }, g.betrag || "Zahlung"), el("b", { style: { textAlign: "right" } }, g.an))))) : null,
        i.warnsignale?.length ? el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "05"), "Warnsignale"),
          el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } }, "Hinweise auf mögliche Verschleierung oder Rechtsverstöße — keine Urteile."),
          i.warnsignale.map(w => el("div", { class: "warnsignal" }, w))) : null)),
    i.zeitleiste?.length ? el("div", { class: "tafel zeitleiste" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "06"), "Zeitleiste"), zeitleiste(i.zeitleiste)) : null,
    el("div", { class: "raster-2" },
      i.luecken?.length ? el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "07"), "Lücken"),
        el("ul", { style: { margin: 0, paddingLeft: "18px", display: "grid", gap: "5px", fontSize: "13px" } }, i.luecken.map(x => el("li", {}, x)))) : null,
      i.naechste_schritte?.length ? el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "08"), "Nächste Schritte"),
        el("div", { class: "chips" }, i.naechste_schritte.map(s => el("button", { class: "chip", onclick: () => senden("recherche", { auftrag: s }) }, s)))) : null));

  if (figuren.length) {
    // Netzausschnitt: Schlüsselfiguren und ihre direkten Nachbarn
    const netz = await api.get("netz");
    const namen = new Set(figuren.map(f => f.name.toLowerCase()));
    const kern = new Set(netz.knoten.filter(k => namen.has(k.name.toLowerCase())).map(k => k.id));
    const kanten = netz.kanten.filter(f => kern.has(f.s) || kern.has(f.o));
    const ids = new Set(kanten.flatMap(f => [f.s, f.o]));
    const knoten = netz.knoten.filter(k => ids.has(k.id)).map(k => ({ ...k, markiert: kern.has(k.id) || k.markiert }));
    if (knoten.length) {
      setTimeout(() => komponenten.push(netzZeichnen(huelle, { knoten, kanten }, { mini: true, onKnoten: d => akteZeigen(d.id) })), 30);
    } else huelle.remove();
  }
  return wrap;
}

function zeitleiste(eintraege) {
  const daten = eintraege.map(e => ({ ...e, t: zeitwert(e.datum) })).filter(e => e.t).sort((a, b) => a.t - b.t);
  const huelle = el("div", { style: { overflowX: "auto" } });
  if (!daten.length) return huelle;
  const breite = Math.max(700, daten.length * 140);
  const svg = d3.select(huelle).append("svg").attr("viewBox", `0 0 ${breite} 150`).style("min-width", `${breite}px`);
  const x = d3.scaleTime().domain(d3.extent(daten, d => d.t)).range([60, breite - 60]);
  if (daten.length === 1) x.domain([new Date(daten[0].t.getTime() - 3e10), new Date(daten[0].t.getTime() + 3e10)]);
  svg.append("line").attr("x1", 20).attr("x2", breite - 20).attr("y1", 75).attr("y2", 75).attr("stroke", farbe("--linie-hell"));
  svg.append("g").attr("transform", "translate(0,75)").call(d3.axisBottom(x).ticks(Math.min(10, daten.length + 2)).tickSize(4))
    .call(g => g.select(".domain").remove()).call(g => g.selectAll("line").attr("stroke", farbe("--linie-hell")));
  const g = svg.selectAll("g.ereignis").data(daten).join("g").attr("class", "ereignis")
    .attr("transform", (d, i) => `translate(${x(d.t)},${i % 2 ? 100 : 50})`);
  g.append("line").attr("y1", 0).attr("y2", (d, i) => i % 2 ? -25 : 25).attr("stroke", farbe("--akzent")).attr("stroke-opacity", .5);
  g.append("circle").attr("cy", (d, i) => i % 2 ? -25 : 25).attr("r", 4).attr("fill", farbe("--akzent"));
  g.append("text").attr("text-anchor", "middle").attr("y", (d, i) => i % 2 ? 22 : -10)
    .text(d => d.ereignis.length > 34 ? d.ereignis.slice(0, 33) + "…" : d.ereignis).append("title").text(d => `${d.datum}: ${d.ereignis}`);
  return huelle;
}

function zeitwert(s) {
  const m = String(s || "").match(/(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/);
  return m ? new Date(+m[1], (+m[2] || 1) - 1, +m[3] || 1) : null;
}

function exportieren(l) {
  const i = l.inhalt;
  const teile = [`# ${i.titel}`, "", `*Lagebild vom ${zeit(l.ts)} — erstellt von ${l.modell || "KI"} auf Grundlage des geprüften Bestands.*`, "",
    l.frage ? `**Frage:** ${l.frage}\n` : "",
    "## Kernaussagen", ...(i.kernaussagen || []).map(k => `- [${k.beleglage}] ${k.aussage}`), "",
    i.lage || "", "",
    "## Schlüsselfiguren", ...(i.schluesselfiguren || []).map(f => `- **${f.name}** — ${f.rolle}`), "",
    "## Geldflüsse", ...(i.geldfluesse || []).map(g => `- ${g.von} → ${g.an}${g.betrag ? ` (${g.betrag})` : ""} [${g.beleglage}]`), "",
    "## Zeitleiste", ...(i.zeitleiste || []).map(z => `- ${z.datum}: ${z.ereignis}`), "",
    "## Warnsignale", ...(i.warnsignale || []).map(w => `- ${w}`), "",
    "## Lücken", ...(i.luecken || []).map(w => `- ${w}`), "",
    "## Nächste Schritte", ...(i.naechste_schritte || []).map(w => `- ${w}`)];
  const blob = new Blob([teile.join("\n")], { type: "text/markdown" });
  const a = el("a", { href: URL.createObjectURL(blob), download: `${(i.titel || "lagebild").replace(/[^\w-]+/g, "_")}.md` });
  document.body.append(a); a.click(); a.remove();
}
