// IndraNet — Prüfkorb. Hier wird aus Befunden Bestand: Der Mensch liest
// gegen, korrigiert Schreibweisen und Beziehungen und übernimmt, was trägt.

import * as api from "./api.js";
import { el, leeren, fehler, melden, praed, typAbz, zeit, domain, externOeffnen, vokabular, bestaetigen, TYP_TEXT } from "./ui.js";
import { S, an, senden } from "./zustand.js";

const ART_TEXT = { web: "Web", datei: "Datei", netzwerk: "Netzwerk", register: "Register" };
const STATUS_TEXT = { offen: "offen", uebernommen: "übernommen", teilweise: "teilweise", verworfen: "verworfen" };

export const PRUEFKORB = {
  voll: true,
  abmelden: [],
  async zeigen(main, fundId) {
    let filter = "offen";
    const liste = el("div", { class: "spalte-liste" });
    const detail = el("div", { class: "spalte-detail" });
    main.append(el("div", { class: "zweispaltig" }, liste, detail));

    const listeZeichnen = async (waehle) => {
      const { funde } = await api.get("funde", filter === "alle" ? {} : filter === "offen" ? { status: "offen" } : {});
      const sicht = filter === "erledigt" ? funde.filter(f => f.status !== "offen") : funde;
      leeren(liste).append(el("div", { class: "filter" },
        [["offen", "Offen"], ["erledigt", "Erledigt"], ["alle", "Alle"]].map(([k, t]) =>
          el("button", { class: k === filter ? "aktiv" : "", onclick: () => { filter = k; listeZeichnen(); } }, t))));
      if (!sicht.length) {
        liste.append(el("div", { class: "leer" }, el("b", {}, filter === "offen" ? "Nichts zu prüfen" : "Keine Einträge"),
          filter === "offen" ? "Neue Befunde entstehen durch Recherchen (Suchfeld oben), Datei-Analysen und Freigaben aus Netzwerken." : ""),
          filter === "offen" ? el("button", { class: "knopf klein", onclick: beispielLaden }, "Fiktive Beispielbefunde laden") : null);
        if (!waehle) leeren(detail).append(el("div", { class: "seiteninhalt" }, hilfe()));
        return;
      }
      for (const f of sicht) {
        liste.append(el("div", { class: `fund-karte${f.fund_id === waehle ? " aktiv" : ""}`, "data-id": f.fund_id, onclick: () => {
          liste.querySelectorAll(".fund-karte").forEach(k => k.classList.toggle("aktiv", k.dataset.id === f.fund_id));
          detailZeigen(f.fund_id);
        } },
          el("div", { style: { display: "flex", gap: "8px", alignItems: "center" } }, el("span", { class: `art ${f.art}` }, ART_TEXT[f.art] || f.art),
            el("span", { class: `mono status-${f.status}`, style: { fontSize: "10.5px", marginLeft: "auto" } }, STATUS_TEXT[f.status])),
          el("div", { class: "titel" }, f.titel),
          el("div", { class: "meta" }, el("span", {}, `${f.anzahl.aussagen} Aussagen`), el("span", {}, `${f.anzahl.entitaeten} Entitäten`),
            el("span", {}, `${f.anzahl.quellen} Quellen`), el("span", {}, zeit(f.ts)))));
      }
      const ziel = waehle || sicht[0].fund_id;
      liste.querySelector(`[data-id="${CSS.escape(ziel)}"]`)?.classList.add("aktiv");
      detailZeigen(ziel);
    };

    const detailZeigen = async (id) => {
      leeren(detail).append(el("div", { class: "seiteninhalt" }, el("div", { class: "leer" }, "Lade Befund …")));
      let f;
      try { f = await api.get("fund", { id }); } catch (e) { return fehler(e); }
      leeren(detail).append(...befundAnsicht(f, () => listeZeichnen()).filter(Boolean));
    };

    await listeZeichnen(fundId);
    PRUEFKORB.abmelden.push(an("stats", () => { if (filter === "offen" && !detail.querySelector(".auswahl-leiste")) listeZeichnen(); }));
  },
  verlassen() { PRUEFKORB.abmelden.forEach(f => f()); PRUEFKORB.abmelden = []; },
};

export async function beispielLaden() {
  try {
    const r = await api.post("beispiel");
    melden("Zwei fiktive Beispielbefunde liegen im Prüfkorb.");
    senden("stats-laden");
    senden("zeige", { ansicht: "pruefkorb", param: r.funde[0] });
  } catch (e) { fehler(e); }
}

function hilfe() {
  return el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "?"), "So arbeitet der Prüfkorb"),
    el("ol", { style: { margin: 0, paddingLeft: "18px", display: "grid", gap: "6px", fontSize: "13px" } },
      el("li", {}, "Die KI liefert Befunde: Aussagen mit Quelle, Entitäten, Orte. Nichts davon steht schon im Bestand."),
      el("li", {}, "Sie lesen gegen: Stimmt die Zuordnung? Ist es dieselbe Person? Trägt die Quelle die Aussage?"),
      el("li", {}, "Schreibweisen und Beziehungen lassen sich direkt in der Tabelle korrigieren."),
      el("li", {}, "Beim Übernehmen wird jede Quellseite abgerufen und verschlüsselt im Projekt gesichert — Webseiten ändern sich, Ihr Beleg nicht."),
      el("li", {}, "Zwei unabhängige Quellen für dieselbe Aussage machen sie »bestätigt«.")));
}

function befundAnsicht(f, nachher) {
  const b = f.inhalt;
  const offen = f.status === "offen";
  const wahl = {
    aussagen: new Set(b.aussagen.map((a, i) => a.sicherheit !== "niedrig" ? i : -1).filter(i => i >= 0)),
    entitaeten: new Set(b.entitaeten.map((_, i) => i)),
    orte: new Set(b.orte.map((_, i) => i)),
  };
  const bearbeitet = { aussagen: {}, entitaeten: {} };
  const zaehler = el("span", { class: "mono gedaempft" });
  const zaehlen = () => { zaehler.textContent = `${wahl.aussagen.size}/${b.aussagen.length} Aussagen · ${wahl.entitaeten.size}/${b.entitaeten.length} Entitäten · ${wahl.orte.size}/${b.orte.length} Orte gewählt`; };
  const quellen = new Map(b.quellen.map(q => [q.url, q]));

  const cb = (gruppe, i) => el("input", { type: "checkbox", checked: wahl[gruppe].has(i), disabled: !offen, onchange: (ev) => {
    ev.target.checked ? wahl[gruppe].add(i) : wahl[gruppe].delete(i);
    ev.target.closest("tr")?.classList.toggle("aus", !ev.target.checked);
    zaehlen();
  } });
  const editierbar = (gruppe, i, feld, wert, klasse = "ent") => el("span", {
    class: klasse, contenteditable: offen ? "plaintext-only" : "false", spellcheck: "false",
    oninput: (ev) => { (bearbeitet[gruppe][i] ||= {})[feld] = ev.target.textContent.trim(); },
  }, wert);

  const praedikate = Object.keys(vokabular.praedikate).filter(p => !p.endsWith("_reverse") && !["beneficially_owned_by", "shares_held_by", "controlled_by", "subsidiary_of", "has_director", "employs", "office_held_by", "advised_by", "registry_of", "residence_of", "address_used_by", "identifies", "nationals", "received_from", "date_of", "lists_entity", "operated_by", "sanctions"].includes(p));
  const praedWahl = (i, wert) => offen ? el("select", { class: "mono", style: { width: "auto", padding: "3px 6px", fontSize: "11.5px", color: "var(--akzent)" }, onchange: (ev) => { (bearbeitet.aussagen[i] ||= {}).praedikat = ev.target.value; } },
    praedikate.map(p => el("option", { value: p, selected: p === wert }, praed(p)))) : el("span", { class: "praed" }, praed(wert));

  const aussagenTabelle = el("table", { class: "tabelle" },
    el("thead", {}, el("tr", {}, ["", "Subjekt", "Beziehung", "Objekt", "Sicherheit", "Beleg"].map(h => el("th", {}, h)))),
    el("tbody", {}, b.aussagen.map((a, i) => el("tr", { class: wahl.aussagen.has(i) ? "" : "aus" },
      el("td", {}, cb("aussagen", i)),
      el("td", {}, editierbar("aussagen", i, "subjekt", a.subjekt, `ent${a._bekannt_s ? "" : " neu"}`)),
      el("td", {}, praedWahl(i, a.praedikat)),
      el("td", {}, editierbar("aussagen", i, "objekt", a.objekt, `ent${a._bekannt_o ? "" : " neu"}`), a.zitat ? el("div", { class: "zitat" }, `»${a.zitat}«`) : null),
      el("td", {}, el("span", { class: `mono sicherheit-${a.sicherheit}` }, a.sicherheit), a.datum ? el("div", { class: "mono gedaempft", style: { fontSize: "10.5px" } }, a.datum) : null),
      el("td", {}, a.beleg.startsWith("http")
        ? [el("a", { class: "beleg", href: "#", title: a.beleg, onclick: (ev) => { ev.preventDefault(); externOeffnen(a.beleg, S.torAktiv); } }, `↗ ${quellen.get(a.beleg)?.herausgeber || domain(a.beleg)}`),
          el("span", { class: "beleg" }, domain(a.beleg))]
        : el("span", { class: "beleg" }, a.beleg))))));

  const entTabelle = el("table", { class: "tabelle" },
    el("thead", {}, el("tr", {}, ["", "Name", "Typ", "Beschreibung"].map(h => el("th", {}, h)))),
    el("tbody", {}, b.entitaeten.map((e, i) => el("tr", {},
      el("td", {}, cb("entitaeten", i)),
      el("td", {}, editierbar("entitaeten", i, "name", e.name, `ent${e._bekannt ? "" : " neu"}`),
        e.aliase?.length ? el("div", { class: "gedaempft", style: { fontSize: "11px" } }, "auch: ", e.aliase.join(", ")) : null),
      el("td", {}, offen ? el("select", { style: { width: "auto", padding: "3px 6px", fontSize: "11.5px" }, onchange: (ev) => { (bearbeitet.entitaeten[i] ||= {}).typ = ev.target.value; } },
        Object.entries(TYP_TEXT).filter(([k]) => k !== "AUTO").map(([k, v]) => el("option", { value: k, selected: k === e.typ }, v))) : typAbz(e.typ)),
      el("td", { style: { fontSize: "12.5px" } }, editierbar("entitaeten", i, "beschreibung", e.beschreibung, ""))))));

  const orteTabelle = el("table", { class: "tabelle" },
    el("thead", {}, el("tr", {}, ["", "Ort", "Koordinaten", "Genauigkeit"].map(h => el("th", {}, h)))),
    el("tbody", {}, b.orte.map((o, i) => el("tr", {}, el("td", {}, cb("orte", i)), el("td", { class: "ent" }, o.name),
      el("td", { class: "mono" }, `${o.lat.toFixed(4)}, ${o.lon.toFixed(4)} ${o.land_iso ? "· " + o.land_iso : ""}`),
      el("td", { class: "mono gedaempft" }, o.genauigkeit)))));

  const quellenListe = el("ul", { class: "liste" }, b.quellen.map(q => el("li", {},
    el("div", { class: "zeile" }, el("span", { class: "art" }, q.art), el("b", {}, q.herausgeber || domain(q.url)),
      el("span", { class: "rechts mono gedaempft" }, q.datum || "")),
    el("span", { style: { fontSize: "12.5px" } }, q.titel),
    q.url.startsWith("http") ? el("a", { class: "mono", style: { fontSize: "11px", wordBreak: "break-all" }, href: "#", onclick: (ev) => { ev.preventDefault(); externOeffnen(q.url, S.torAktiv); } }, q.url) : null)));

  const sicherBelege = el("input", { type: "checkbox", checked: S.status?.einstellungen?.belege_sichern ?? true });
  const leiste = offen ? el("div", { class: "auswahl-leiste" }, zaehler,
    el("label", { class: "schalter", style: { fontSize: "12px" } }, sicherBelege, "Quellseiten verschlüsselt sichern"),
    el("div", { class: "rechts" },
      el("button", { class: "knopf gefahr", onclick: async () => {
        const notiz = await bestaetigen("Befund verwerfen?", "Der Befund bleibt im Protokoll sichtbar, geht aber nicht in den Bestand.", { ok: "Verwerfen", gefahr: true });
        if (notiz === null) return;
        try { await api.post("fund/verwerfen", { fund_id: f.fund_id }); melden("Verworfen."); senden("stats-laden"); nachher(); } catch (e) { fehler(e); }
      } }, "Verwerfen"),
      el("button", { class: "knopf haupt", onclick: async (ev) => {
        if (!wahl.aussagen.size && !wahl.entitaeten.size && !wahl.orte.size) return melden("Nichts ausgewählt.", "warn");
        ev.target.disabled = true;
        try {
          await api.post("fund/uebernehmen", { fund_id: f.fund_id, auswahl: {
            aussagen: [...wahl.aussagen], entitaeten: [...wahl.entitaeten], orte: [...wahl.orte],
            bearbeitet, belege_sichern: sicherBelege.checked } });
          melden("Übernahme läuft — Quellen werden gesichert, danach sucht die KI nach Anschlussstellen.");
          senden("stats-laden");
          setTimeout(nachher, 600);
        } catch (e) { fehler(e); ev.target.disabled = false; }
      } }, "Auswahl übernehmen"))) : null;
  zaehlen();

  const abschnitt = (titel, n, inhalt) => n ? el("div", { class: "tafel", style: { padding: "14px 0 0" } },
    el("div", { class: "tafel-kopf", style: { padding: "0 14px" } }, titel, el("span", { class: "mono gedaempft" }, n)),
    el("div", { style: { overflow: "auto" } }, inhalt)) : null;

  return [el("div", { class: "seiteninhalt" },
    el("div", { class: "kopfzeile" },
      el("div", {}, el("div", { style: { display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" } },
        el("span", { class: `art ${f.art}` }, ART_TEXT[f.art] || f.art), el("span", { class: `mono status-${f.status}` }, STATUS_TEXT[f.status]),
        el("span", { class: "mono gedaempft" }, `${zeit(f.ts)}${f.herkunft ? " · " + f.herkunft : ""}`)),
        el("h2", {}, f.titel)),
      el("div", { class: "rechts" }, f.art !== "datei" ? el("button", { class: "knopf", onclick: () => senden("recherche", { auftrag: f.anfrage }) }, "⟳ Erneut recherchieren") : null)),
    b.zusammenfassung ? el("div", { class: "zusammenfassung" }, b.zusammenfassung) : null,
    b._suchen?.length ? el("details", {}, el("summary", { class: "etikett", style: { cursor: "pointer" } }, `Suchspur der KI · ${b._suchen.length} Schritte`),
      el("div", { class: "suchspur", style: { marginTop: "8px" } }, b._suchen.map(s => el("span", {}, s)))) : null,
    abschnitt("Aussagen", b.aussagen.length, aussagenTabelle),
    b.aussagen.length === 0 ? el("div", { class: "hinweis" }, "Keine belegten Aussagen gefunden. Prüfen Sie die offenen Fragen — oder formulieren Sie den Auftrag konkreter (Firmensitz, Land, Funktion).") : null,
    el("div", { class: "raster-2" }, abschnitt("Entitäten", b.entitaeten.length, entTabelle), abschnitt("Orte", b.orte.length, orteTabelle)),
    abschnitt("Quellen", b.quellen.length, el("div", { style: { padding: "0 14px 14px" } }, quellenListe)),
    el("div", { class: "raster-2" },
      b.offene_fragen.length ? el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, "Offene Fragen"),
        el("ul", { style: { margin: 0, paddingLeft: "18px", display: "grid", gap: "4px", fontSize: "13px" } }, b.offene_fragen.map(q => el("li", {}, q)))) : null,
      b.naechste_schritte.length ? el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, "Folgerecherchen"),
        el("div", { class: "chips" }, b.naechste_schritte.map(s => el("button", { class: "chip", onclick: () => senden("recherche", { auftrag: s }) }, s)))) : null)),
  leiste];
}
