// IndraNet — Ansichten: Lage, Netz, Karte, Bestand. Weitere Ansichten
// kommen aus eigenen Modulen und werden hier zusammengeführt.

import * as api from "./api.js";
import { el, leeren, fehler, melden, praed, lageAbz, typAbz, zeit, bestaetigen, dialog, LAGE_TEXT } from "./ui.js";
import { netzZeichnen, lageFarbe } from "./netz.js";
import { karteZeichnen } from "./karte.js";
import { akteZeigen } from "./akte.js";
import { S, an, senden } from "./zustand.js";
import { PRUEFKORB, beispielLaden } from "./pruefkorb.js";
import { LAGEBILDER } from "./lagebilder.js";
import { NETZWERKE } from "./netzwerke.js";
import { QUELLEN, SYSTEM } from "./system.js";

// ===================================================================== LAGE
const LAGE = {
  komponenten: [],
  abmelden: [],
  async zeigen(main) {
    const [netz, karte, vorschl, lagen] = await Promise.all([
      api.get("netz"), api.get("karte"), api.get("vorschlaege"), api.get("lagebilder")]);
    const s = S.stats || {};
    const lage = s.beleglage || {};
    const gesamt = Math.max(1, s.fakten || 0);
    const leerBestand = !netz.knoten.length;

    const kennzahl = (titel, wert, zusatz, akzent) => el("div", { class: `kennzahl${akzent ? " akzent" : ""}` },
      el("span", { class: "etikett" }, titel), el("b", {}, wert ?? 0), zusatz || null);
    const balken = el("div", { class: "balken" },
      ["BESTAETIGT", "EINFACH_BELEGT", "UMSTRITTEN"].map(k => el("i", { style: { width: `${(lage[k] || 0) / gesamt * 100}%`, background: lageFarbe(k) }, title: `${LAGE_TEXT[k]}: ${lage[k] || 0}` })));

    const kKarte = el("div", { class: "tafel kachel-karte" });
    const kNetz = el("div", { class: "tafel kachel-netz" });
    const huelleKarte = el("div", { class: "karte-buehne" });
    const huelleNetz = el("div", { class: "netz-buehne" });
    kKarte.append(huelleKarte, el("div", { class: "kachel-kopf" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "◍"), "Aktionsgebiet")),
      el("div", { class: "kachel-fuss" }, el("button", { class: "knopf klein", onclick: () => senden("zeige", { ansicht: "karte" }) }, "Karte öffnen")));
    kNetz.append(huelleNetz, el("div", { class: "kachel-kopf" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⬡"), "Geflecht")),
      el("div", { class: "kachel-fuss" }, el("button", { class: "knopf klein", onclick: () => senden("zeige", { ansicht: "netz" }) }, "Netz öffnen")));

    const vorschlagListe = el("ul", { class: "liste" });
    const zeichneVorschlaege = (vs) => {
      leeren(vorschlagListe);
      if (!vs.length) vorschlagListe.append(el("div", { class: "leer" }, el("b", {}, "Noch keine Vorschläge"),
        "Nach jeder Übernahme sucht die KI im Hintergrund nach Anschlussstellen."));
      for (const v of vs.slice(0, 8)) {
        vorschlagListe.append(el("li", {},
          el("div", { class: "zeile" }, el("span", { class: "art" }, v.art === "recherche" ? "Recherche" : "Verbindung"),
            el("b", { style: { fontWeight: 600 } }, v.text),
            el("span", { class: "rechts" },
              v.art === "recherche" ? el("button", { class: "knopf klein haupt", onclick: async () => {
                senden("recherche", { auftrag: v.text }); await api.post("vorschlag", { id: v.id, status: "erledigt" }); LAGE.vorschlaege();
              } }, "Los") : el("button", { class: "knopf klein", onclick: async () => {
                senden("recherche", { auftrag: `Verbindung prüfen: ${v.text}. ${v.grund}` }); await api.post("vorschlag", { id: v.id, status: "erledigt" }); LAGE.vorschlaege();
              } }, "Prüfen"),
              el("button", { class: "knopf klein flach", title: "Verwerfen", onclick: async () => { await api.post("vorschlag", { id: v.id, status: "verworfen" }); LAGE.vorschlaege(); } }, "✕"))),
          v.grund ? el("span", { class: "gedaempft", style: { fontSize: "12px" } }, v.grund) : null));
      }
    };
    LAGE.vorschlaege = async () => zeichneVorschlaege((await api.get("vorschlaege")).vorschlaege);
    zeichneVorschlaege(vorschl.vorschlaege);

    const aktivitaet = el("div", { class: "protokoll", style: { maxHeight: "300px" } });
    const zeichneAktivitaet = (auftraege) => {
      leeren(aktivitaet);
      const zeilen = auftraege.flatMap(a => a.meldungen.map(m => ({ ...m, titel: a.titel, laeuft: a.status === "laeuft" })))
        .sort((a, b) => b.ts - a.ts).slice(0, 40);
      if (!zeilen.length) aktivitaet.append(el("div", {}, "Bereit. Suchauftrag oben eingeben oder Datei ins Fenster ziehen."));
      for (const z of zeilen) aktivitaet.append(el("div", { class: z.laeuft ? "neu" : "" }, el("time", {}, zeit(z.ts)), z.text));
    };
    zeichneAktivitaet(S.auftraege || []);

    const letztes = lagen.lagebilder[0];
    main.append(el("div", { class: "lage" },
      el("div", { class: "kennzahlen" },
        kennzahl("Entitäten", s.entitaeten, null, true),
        kennzahl("Fakten", s.fakten, balken),
        kennzahl("Bestätigt", lage.BESTAETIGT || 0, el("span", { class: "gedaempft mono" }, `${Math.round((lage.BESTAETIGT || 0) / gesamt * 100)} % des Bestands`)),
        kennzahl("Umstritten", lage.UMSTRITTEN || 0, el("span", { class: "gedaempft mono" }, "Quellen widersprechen sich")),
        kennzahl("Prüfkorb", s.pruefkorb || 0, s.pruefkorb ? el("button", { class: "knopf klein", onclick: () => senden("zeige", { ansicht: "pruefkorb" }) }, "Prüfen") : el("span", { class: "gedaempft mono" }, "nichts offen")),
        kennzahl("Belege", s.dokumente || 0, el("span", { class: "gedaempft mono" }, "verschlüsselt im Projekt"))),
      kKarte, kNetz,
      el("div", { class: "tafel kachel-vorschlaege" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "KI"), "Anschlussstellen"), vorschlagListe),
      el("div", { class: "tafel kachel-aktivitaet" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "▸"), "Aktivität"), aktivitaet),
      el("div", { class: "tafel kachel-lagebild" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "◫"), "Lagebild"),
        letztes ? [el("b", { style: { fontFamily: "var(--kopf)", fontSize: "15px" } }, letztes.titel),
          el("span", { class: "gedaempft mono" }, zeit(letztes.ts)),
          el("ul", { class: "liste" }, (letztes.inhalt.kernaussagen || []).slice(0, 4).map(k => el("li", {}, el("div", { class: "zeile" }, lageAbz(k.beleglage)), el("span", { style: { fontSize: "12.5px" } }, k.aussage)))),
          el("button", { class: "knopf klein", onclick: () => senden("zeige", { ansicht: "lagebilder", param: letztes.lagebild_id }) }, "Öffnen")]
          : [el("p", { class: "gedaempft", style: { margin: 0, fontSize: "13px" } }, "Die KI fasst den geprüften Bestand zu einem Lagebild zusammen — mit Kernaussagen, Schlüsselfiguren, Geldflüssen, Zeitleiste und Warnsignalen."),
            el("button", { class: "knopf", disabled: leerBestand, onclick: () => api.post("lagebild", { frage: "" }).then((r) => { senden("auftrag-gestartet", r.auftrag); if (!r.bruecke) melden("Lagebild wird erstellt …"); }, fehler) }, "Lagebild erstellen")])));

    let netzK = null;
    if (leerBestand) {
      huelleNetz.append(el("div", { class: "leer", style: { position: "absolute", inset: "50px 20px 20px", display: "grid", placeContent: "center" } },
        el("b", {}, "Noch leer"), "Geben Sie oben einen Namen ein, z. B. eine Firma oder Person. Die KI recherchiert, Sie prüfen, das Netz wächst.",
        el("div", { style: { marginTop: "12px" } }, el("button", { class: "knopf klein", onclick: beispielLaden }, "Fiktive Beispieldaten ausprobieren"))));
    } else {
      netzK = netzZeichnen(huelleNetz, netz, { mini: true, onKnoten: d => akteZeigen(d.id) });
      LAGE.komponenten.push(netzK);
    }
    const karteK = karteZeichnen(huelleKarte, karte, { mini: true, onOrt: o => senden("zeige", { ansicht: "karte", param: o.id }) });
    LAGE.komponenten.push(karteK);

    LAGE.abmelden.push(an("auftraege", zeichneAktivitaet), an("vorschlaege", () => LAGE.vorschlaege()),
      an("bestand-geaendert", async () => {
        if (!netzK) return senden("zeige", { ansicht: "lage" });
        const [n, k] = await Promise.all([api.get("netz"), api.get("karte")]);
        netzK.setzen(n); karteK.setzen(k);
      }));
  },
  verlassen() {
    LAGE.komponenten.forEach(c => c.zerstoeren()); LAGE.komponenten = [];
    LAGE.abmelden.forEach(f => f()); LAGE.abmelden = [];
  },
};

// ===================================================================== NETZ
const NETZ = {
  voll: true,
  komponente: null,
  abmelden: [],
  async zeigen(main, fokusId) {
    const daten = await api.get("netz");
    const buehne = el("div", { class: "netz-buehne" });
    const suche = el("input", { class: "feld", placeholder: "Entität suchen …", list: "netz-namen" });
    const namen = el("datalist", { id: "netz-namen" }, daten.knoten.map(k => el("option", { value: k.name })));
    let alle = false;
    const typen = [...new Set(daten.knoten.map(k => k.typ))];
    main.append(buehne,
      el("div", { class: "werkzeuge" }, suche, namen,
        el("button", { class: "knopf klein", onclick: () => NETZ.komponente?.einpassen() }, "Einpassen"),
        el("button", { class: "knopf klein", onclick: () => NETZ.komponente?.neuMischen() }, "Neu anordnen"),
        el("label", { class: "schalter", style: { fontSize: "12px" } }, el("input", { type: "checkbox", onchange: async (ev) => {
          alle = ev.target.checked; NETZ.komponente.setzen(await api.get("netz", alle ? { alle: "1" } : {}));
        } }), "Widerrufene zeigen"),
        el("div", { class: "rechts" }, el("button", { class: "knopf klein", onclick: () => pfadDialog(daten) }, "Pfad finden"))),
      el("div", { class: "legende" },
        el("div", { class: "reihe" }, typen.map(t => typAbz(t))),
        el("div", { class: "reihe" }, ["BESTAETIGT", "EINFACH_BELEGT", "UMSTRITTEN"].map(l => el("span", { class: "kante", style: { color: lageFarbe(l) } }, el("i"), LAGE_TEXT[l])),
          el("span", { class: "kante", style: { color: "var(--t-betrag)" } }, el("i", { style: { background: "none", borderTop: "2px dotted currentColor", height: "0" } }), "Geldfluss"))));
    if (!daten.knoten.length) {
      main.append(el("div", { class: "leer", style: { position: "absolute", inset: "30% 25% auto" } }, el("b", {}, "Das Netz ist noch leer"),
        "Übernehmen Sie Befunde aus dem Prüfkorb — jede bestätigte Aussage wird hier zu einer Kante."));
      return;
    }
    suche.addEventListener("change", () => NETZ.komponente.filtern(suche.value));
    suche.addEventListener("keydown", (ev) => { if (ev.key === "Enter") NETZ.komponente.filtern(suche.value); });
    NETZ.komponente = netzZeichnen(buehne, daten, {
      onKnoten: d => akteZeigen(d.id),
      onDoppel: d => { NETZ.komponente.zentrieren(d.id, 1.8); },
      onKante: f => akteZeigen(f.s),
    });
    if (fokusId) setTimeout(() => { NETZ.komponente.waehlen(fokusId); NETZ.komponente.zentrieren(fokusId); akteZeigen(fokusId); }, 1500);
    NETZ.abmelden.push(an("bestand-geaendert", async () => NETZ.komponente?.setzen(await api.get("netz", alle ? { alle: "1" } : {}))));
  },
  verlassen() {
    NETZ.komponente?.zerstoeren(); NETZ.komponente = null;
    NETZ.abmelden.forEach(f => f()); NETZ.abmelden = [];
  },
};

function pfadDialog(daten) {
  const namen = daten.knoten.map(k => k.name).sort();
  const liste = el("datalist", { id: "pfad-namen" }, namen.map(n => el("option", { value: n })));
  const von = el("input", { list: "pfad-namen", placeholder: "von …" });
  const nach = el("input", { list: "pfad-namen", placeholder: "nach …" });
  const ergebnis = el("div", { style: { display: "grid", gap: "8px" } });
  const finden = () => {
    // Breitensuche im Netz — clientseitig, der Bestand liegt ohnehin vor
    const a = daten.knoten.find(k => k.name === von.value), b = daten.knoten.find(k => k.name === nach.value);
    leeren(ergebnis);
    if (!a || !b) return ergebnis.append(el("div", { class: "gedaempft" }, "Bitte zwei Entitäten aus der Liste wählen."));
    const nb = new Map();
    for (const f of daten.kanten) {
      (nb.get(f.s) || nb.set(f.s, []).get(f.s)).push([f.o, f]);
      (nb.get(f.o) || nb.set(f.o, []).get(f.o)).push([f.s, f]);
    }
    const vor = new Map([[a.id, null]]);
    const schlange = [a.id];
    while (schlange.length && !vor.has(b.id)) {
      const x = schlange.shift();
      for (const [y, f] of nb.get(x) || []) if (!vor.has(y)) { vor.set(y, [x, f]); schlange.push(y); }
    }
    if (!vor.has(b.id)) return ergebnis.append(el("div", { class: "hinweis" }, "Keine Verbindung im Bestand. Das heißt nicht, dass keine besteht — nur, dass sie nicht belegt ist."));
    const schritte = [];
    for (let x = b.id; vor.get(x); x = vor.get(x)[0]) schritte.unshift(vor.get(x)[1]);
    const schwach = schritte.reduce((m, f) => ({ BESTAETIGT: 0, EINFACH_BELEGT: 1, UMSTRITTEN: 2, WIDERRUFEN: 3 }[f.beleglage] > m[0] ? [{ BESTAETIGT: 0, EINFACH_BELEGT: 1, UMSTRITTEN: 2, WIDERRUFEN: 3 }[f.beleglage], f.beleglage] : m), [-1, "BESTAETIGT"])[1];
    ergebnis.append(el("div", { class: "hinweis" }, `${schritte.length} Schritt(e). Schwächstes Glied: `, lageAbz(schwach)),
      ...schritte.map(f => el("div", { class: "fluss" }, el("b", {}, f.subjekt), el("span", { class: "mono", style: { color: "var(--akzent)" } }, praed(f.praedikat)), el("b", {}, f.objekt))));
  };
  dialog([el("div", { class: "tafel-kopf" }, "Verbindung zwischen zwei Entitäten"), liste,
    el("div", { class: "raster-2" }, von, nach), el("button", { class: "knopf haupt", onclick: finden }, "Pfad suchen"), ergebnis],
  { breit: true });
}

// ==================================================================== KARTE
const KARTE = {
  voll: true,
  komponente: null,
  abmelden: [],
  async zeigen(main, ortId) {
    const daten = await api.get("karte");
    const buehne = el("div", { class: "karte-buehne" });
    let modus = "karte";
    const gruppe = el("div", { class: "gruppe" },
      ["karte", "globus"].map(m => el("button", { class: m === modus ? "aktiv" : "", onclick: (ev) => {
        modus = m; [...gruppe.children].forEach(b => b.classList.toggle("aktiv", b === ev.target));
        KARTE.komponente.modus(m);
      } }, m === "karte" ? "Weltkarte" : "Globus")));
    const ortListe = el("div", { class: "unverortet" });
    const zeichneUnverortet = (d) => {
      leeren(ortListe);
      ortListe.hidden = !d.unverortet.length;
      ortListe.append(el("h4", {}, `Ohne Koordinaten · ${d.unverortet.length}`),
        el("p", { class: "gedaempft", style: { margin: 0, fontSize: "11.5px" } }, "Per OpenStreetMap suchen (über den Netzweg) oder auf die Karte klicken und den Ort setzen."));
      for (const n of d.unverortet) {
        ortListe.append(el("div", { class: "reihe" }, el("span", { title: n }, n),
          el("button", { class: "knopf klein", onclick: async () => {
            try { await api.post("ort/nominatim", { name: n }); melden(`${n} verortet.`); KARTE.neu(); } catch (e) { fehler(e); }
          } }, "Suchen"),
          el("button", { class: "knopf klein flach", title: "Auf der Karte setzen", onclick: () => { KARTE.setzeOrt = n; melden(`Klicken Sie auf die Karte, um »${n}« zu setzen.`, "info", 6000); } }, "◎")));
      }
    };
    main.append(buehne,
      el("div", { class: "werkzeuge" }, gruppe,
        el("button", { class: "knopf klein", onclick: () => KARTE.komponente.aktionsgebiet() }, "Aktionsgebiet"),
        el("span", { class: "rechts" })),
      ortListe,
      el("div", { class: "legende" },
        el("div", { class: "reihe" }, el("span", { class: "kante", style: { color: "var(--akzent)" } }, el("i", { style: { width: "10px", height: "10px", borderRadius: "50%" } }), "Ort mit Entitäten"),
          el("span", { class: "kante", style: { color: "var(--t-betrag)" } }, el("i"), "Geldfluss"),
          el("span", { class: "kante", style: { color: lageFarbe("BESTAETIGT") } }, el("i"), "bestätigt"),
          el("span", { class: "kante", style: { color: lageFarbe("EINFACH_BELEGT") } }, el("i"), "einfach"),
          el("span", { class: "kante", style: { color: lageFarbe("UMSTRITTEN") } }, el("i"), "umstritten"))),
      el("div", { class: "karte-ecke" }, "Kartendaten: Natural Earth · lokal, ohne Kachelabruf",
        el("br"), `${daten.orte.length} Orte · ${daten.boegen.length} Verbindungen · ${daten.ohne_ort} Entitäten ohne Ort`));
    zeichneUnverortet(daten);
    KARTE.komponente = karteZeichnen(buehne, daten, {
      onOrt: (o) => ortAkte(o),
      onBogen: (b) => akteZeigen(b.fakten[0] && daten.orte.find(o => o.id === b.von)?.entitaeten[0]?.id),
      onKlickOrt: async (p) => {
        if (!KARTE.setzeOrt) return;
        const name = KARTE.setzeOrt; KARTE.setzeOrt = null;
        try { await api.post("ort", { name, lat: p.lat, lon: p.lon }); melden(`${name} gesetzt.`); KARTE.neu(); } catch (e) { fehler(e); }
      },
    });
    KARTE.neu = async () => { const d = await api.get("karte"); KARTE.komponente.setzen(d); zeichneUnverortet(d); };
    if (ortId) setTimeout(() => { const o = daten.orte.find(x => x.id === ortId); if (o) { KARTE.komponente.zuOrt(o); ortAkte(o); } }, 900);
    KARTE.abmelden.push(an("bestand-geaendert", () => KARTE.neu()));
  },
  verlassen() {
    KARTE.komponente?.zerstoeren(); KARTE.komponente = null;
    KARTE.abmelden.forEach(f => f()); KARTE.abmelden = [];
  },
};

function ortAkte(o) {
  const s = document.getElementById("seite");
  s.hidden = false;
  leeren(s).append(el("div", { class: "akte" },
    el("button", { class: "symbol schliessen", onclick: () => { s.hidden = true; } }, "✕"),
    el("div", { class: "akte-kopf" }, typAbz("PLACE"), el("h2", {}, o.name),
      el("div", { class: "mono gedaempft" }, `${o.lat.toFixed(3)}, ${o.lon.toFixed(3)} · ${o.genauigkeit || ""} · Quelle: ${o.quelle || "—"}`),
      el("div", { class: "zeile" }, el("button", { class: "knopf klein", onclick: () => akteZeigen(o.id) }, "Akte des Ortes"))),
    el("h4", {}, `Hier verankert · ${o.entitaeten.length}`),
    el("ul", { class: "liste" }, o.entitaeten.map(e => el("li", { style: { cursor: "pointer" }, onclick: () => akteZeigen(e.id) },
      el("div", { class: "zeile" }, typAbz(e.typ), el("span", { class: "rechts" }, lageAbz(e.beleglage))),
      el("b", {}, e.name), el("span", { class: "mono gedaempft" }, praed(e.praedikat)))))));
}

// ================================================================== BESTAND
const BESTAND = {
  async zeigen(main) {
    const [netz, dub] = await Promise.all([api.get("netz", { alle: "1" }), api.get("dubletten")]);
    const fakten = netz.kanten.sort((a, b) => b.zeit - a.zeit);
    const gewaehlt = new Set();
    let filter = "alle", text = "";
    const tbody = el("tbody");
    const zaehler = el("span", { class: "mono gedaempft" });
    const zeichnen = () => {
      leeren(tbody);
      const t = text.toLowerCase();
      const sicht = fakten.filter(f => (filter === "alle" || f.beleglage === filter) &&
        (!t || `${f.subjekt} ${f.objekt} ${praed(f.praedikat)}`.toLowerCase().includes(t)));
      zaehler.textContent = `${sicht.length} von ${fakten.length} Fakten · ${gewaehlt.size} gewählt`;
      for (const f of sicht) {
        const cb = el("input", { type: "checkbox", checked: gewaehlt.has(f.fact_id), onchange: (ev) => {
          ev.target.checked ? gewaehlt.add(f.fact_id) : gewaehlt.delete(f.fact_id); zaehler.textContent = `${sicht.length} von ${fakten.length} Fakten · ${gewaehlt.size} gewählt`;
        } });
        tbody.append(el("tr", { class: f.beleglage === "WIDERRUFEN" ? "aus" : "" },
          el("td", {}, cb),
          el("td", {}, el("a", { class: "ent", style: { cursor: "pointer" }, onclick: () => akteZeigen(f.s) }, f.subjekt)),
          el("td", {}, el("span", { class: "praed" }, praed(f.praedikat))),
          el("td", {}, el("a", { class: "ent", style: { cursor: "pointer" }, onclick: () => akteZeigen(f.o) }, f.objekt)),
          el("td", {}, lageAbz(f.beleglage), f.widersprueche ? el("div", { class: "gedaempft", style: { fontSize: "11px", marginTop: "4px" } }, "vs. ", f.widersprueche.join(", ")) : null),
          el("td", { class: "mono gedaempft" }, f.quellen.join(", ")),
          el("td", { class: "mono gedaempft" }, zeit(f.zeit))));
      }
    };
    const filterKnoepfe = el("div", { class: "filter", style: { maxWidth: "560px" } },
      [["alle", "Alle"], ["BESTAETIGT", "Bestätigt"], ["EINFACH_BELEGT", "Einfach"], ["UMSTRITTEN", "Umstritten"], ["WIDERRUFEN", "Widerrufen"]].map(([k, t]) =>
        el("button", { class: k === filter ? "aktiv" : "", onclick: (ev) => { filter = k; [...filterKnoepfe.children].forEach(b => b.classList.toggle("aktiv", b === ev.target)); zeichnen(); } }, t)));

    const dubListe = el("ul", { class: "liste" });
    for (const v of dub.vorschlaege.slice(0, 30)) {
      dubListe.append(el("li", {},
        el("div", { class: "zeile" }, el("b", {}, v.a), el("span", { class: "gedaempft" }, "↔"), el("b", {}, v.b),
          el("span", { class: "rechts mono gedaempft" }, `${Math.round(v.score * 100)} % · ${v.grund}`)),
        v.warnung ? el("div", { class: "hinweis" }, v.warnung) : null,
        el("div", { class: "zeile" },
          el("button", { class: "knopf klein", onclick: async () => {
            const begruendung = await bestaetigen("Zusammenführen?", `»${v.a}« und »${v.b}« werden als dieselbe Entität geführt. Das steht mit Begründung im Protokoll.`, { ok: "Zusammenführen", feld: "Begründung, z. B. gleiche Registernummer" });
            if (!begruendung) return;
            try { await api.post("verschmelzen", { von: v.key_a, nach: v.key_b, begruendung }); melden("Zusammengeführt."); senden("stats-laden"); senden("zeige", { ansicht: "bestand" }); } catch (e) { fehler(e); }
          } }, "Dieselbe"),
          el("button", { class: "knopf klein flach", onclick: async () => {
            try { await api.post("trennen", { a: v.key_a, b: v.key_b, begruendung: "verschieden" }); melden("Als verschieden vermerkt."); senden("zeige", { ansicht: "bestand" }); } catch (e) { fehler(e); }
          } }, "Verschieden"))));
    }

    main.append(el("div", { class: "seiteninhalt" },
      el("div", { class: "kopfzeile" },
        el("div", {}, el("h2", {}, "Bestand"), el("p", {}, "Alle geprüften Fakten mit ihrer Beleglage. Bestätigt heißt: mindestens zwei unabhängige Quellen. Wählen Sie Fakten aus, um sie im Recherche-Netzwerk freizugeben.")),
        el("div", { class: "rechts" },
          el("button", { class: "knopf", onclick: () => freigabeDialog([...gewaehlt]) }, "⟁ Im Netzwerk freigeben"),
          el("a", { class: "knopf", href: api.dossierUrl(), download: "" }, "⇩ Dossier (Markdown)"))),
      el("div", { class: "kopfzeile" }, filterKnoepfe,
        el("input", { placeholder: "Filtern …", style: { width: "260px" }, oninput: (ev) => { text = ev.target.value; zeichnen(); } }), zaehler),
      fakten.length ? el("div", { class: "tafel", style: { padding: 0, overflow: "auto", maxHeight: "60vh" } },
        el("table", { class: "tabelle" }, el("thead", {}, el("tr", {}, ["", "Subjekt", "Beziehung", "Objekt", "Beleglage", "Quellen", "Erfasst"].map(h => el("th", {}, h)))), tbody))
        : el("div", { class: "leer" }, el("b", {}, "Noch keine Fakten"), "Fakten entstehen, wenn Sie Befunde aus dem Prüfkorb übernehmen."),
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "≈"), `Mögliche Dubletten · ${dub.vorschlaege.length}`),
        el("p", { class: "gedaempft", style: { margin: 0, fontSize: "13px" } }, "Ähnliche Namen, die dieselbe Person oder Firma meinen könnten. Nichts wird automatisch zusammengeführt — »Anders Holm« aus dem Register und aus dem Leak sind womöglich zwei Menschen."),
        dub.vorschlaege.length ? dubListe : el("div", { class: "gedaempft" }, "Keine Kandidaten."))));
    zeichnen();
  },
};

async function freigabeDialog(factIds) {
  if (!factIds.length) return melden("Bitte zuerst Fakten in der Tabelle auswählen.", "warn");
  const { netzwerke } = await api.get("netzwerke");
  if (!netzwerke.length) return melden("Noch kein Recherche-Netzwerk — legen Sie unter »Netzwerke« eines an oder treten Sie einem bei.", "warn");
  const wahl = el("select", {}, netzwerke.map(n => el("option", { value: n.netz_id }, `${n.name} (${n.mitglieder} Teilnehmer)`)));
  const kommentar = el("textarea", { rows: 2, placeholder: "Hinweis an die Kolleginnen (optional)" });
  const d = dialog([
    el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⟁"), `${factIds.length} Fakt(en) freigeben`),
    el("div", { class: "hinweis" }, "Geteilt werden nur Fakten mit öffentlichen Belegen (Webseiten, Register, Presse) — mit Quelladresse und Ihrer Signatur. Hochgeladene interne Dokumente und Notizen verlassen das Projekt nicht."),
    el("label", {}, "Netzwerk", wahl), el("label", {}, "Kommentar", kommentar),
    el("div", { class: "knopfreihe" }, el("button", { class: "knopf flach", onclick: () => d.schliessen() }, "Abbrechen"),
      el("button", { class: "knopf haupt", onclick: async () => {
        try {
          const r = await api.post("netzwerk/freigeben", { netz_id: wahl.value, fact_ids: factIds, kommentar: kommentar.value });
          d.schliessen();
          melden(`${r.geteilt} Fakt(en) freigegeben.${r.abgelehnt.length ? ` ${r.abgelehnt.length} zurückgehalten: ${r.abgelehnt[0].grund}` : ""}`, r.abgelehnt.length ? "warn" : "info", 9000);
        } catch (e) { fehler(e); }
      } }, "Freigeben"))]);
}

export const ANSICHTEN = {
  lage: LAGE, pruefkorb: PRUEFKORB, netz: NETZ, karte: KARTE, bestand: BESTAND,
  lagebilder: LAGEBILDER, netzwerke: NETZWERKE, quellen: QUELLEN, einstellungen: SYSTEM,
};
