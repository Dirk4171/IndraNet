// IndraNet — Akte einer Entität in der Seitenleiste: Steckbrief, Fakten mit
// Belegen, Notiz, Markierung, Widerruf, Folgerecherche.

import * as api from "./api.js";
import { el, leeren, fehler, melden, praed, typAbz, lageAbz, zeit, bestaetigen, externOeffnen, domain, TYP_TEXT } from "./ui.js";
import { S, senden } from "./zustand.js";

const seite = () => document.getElementById("seite");

export function akteSchliessen() {
  seite().hidden = true;
  leeren(seite());
}

export async function akteZeigen(id) {
  const s = seite();
  s.hidden = false;
  leeren(s).append(el("div", { class: "akte" }, el("div", { class: "leer" }, "Lade Akte …")));
  let e;
  try { e = await api.get("entitaet", { id }); } catch (err) { fehler(err); return akteSchliessen(); }

  const notiz = el("textarea", { rows: 3, placeholder: "Eigene Notiz — bleibt im Projekt" }, e.notiz || "");
  const besch = el("textarea", { rows: 2, placeholder: "Kurzbeschreibung" }, e.beschreibung || "");
  const typ = el("select", {}, Object.entries(TYP_TEXT).filter(([k]) => k !== "AUTO").map(([k, v]) =>
    el("option", { value: k, selected: k === e.typ }, v)));
  const speichern = async (felder) => {
    try { await api.post("entitaet", { name: e.name, ...felder }); melden("Gespeichert."); senden("bestand-geaendert"); }
    catch (err) { fehler(err); }
  };

  const aus = e.fakten.filter(f => f.s === id), ein = e.fakten.filter(f => f.o === id);
  const faktKarte = (f, richtung) => {
    const anderer = richtung === "aus" ? { id: f.o, name: f.objekt } : { id: f.s, name: f.subjekt };
    return el("div", { class: "fakt" },
      el("div", { class: "zeile", style: { display: "flex", gap: "8px", alignItems: "center" } }, lageAbz(f.beleglage),
        el("span", { class: "mono gedaempft", style: { marginLeft: "auto" } }, `${f.quellen.length} Quelle(n)`)),
      el("div", { class: "satz" }, richtung === "aus"
        ? [el("span", { class: "praed" }, praed(f.praedikat)), " ", el("a", { onclick: () => akteZeigen(anderer.id) }, anderer.name)]
        : [el("a", { onclick: () => akteZeigen(anderer.id) }, anderer.name), " ", el("span", { class: "praed" }, praed(f.praedikat)), " ", el("span", { class: "gedaempft" }, "→ diese")]),
      f.widersprueche ? el("div", { class: "hinweis schlecht" }, "Widerspricht: ", f.widersprueche.join(", ")) : null,
      f.belege.map(b => el("div", { class: "beleg" },
        el("div", {}, el("b", {}, b.quelle || "—"), " · ", b.titel || ""),
        b.zitat ? el("div", { style: { fontStyle: "italic" } }, `»${b.zitat}«`) : null,
        el("div", { class: "mono" }, b.fundstelle && !b.fundstelle.startsWith("http") ? `Fundstelle: ${b.fundstelle} · ` : "", `erfasst ${zeit(b.ts)}${b.erfasst_von ? " von " + b.erfasst_von : ""}`),
        el("div", { class: "aktionen" },
          b.url && b.url.startsWith("http") ? el("button", { onclick: () => externOeffnen(b.url, S.torAktiv), title: b.url }, `↗ ${domain(b.url)}`) : null,
          b.abgelegt ? el("button", { onclick: () => window.open(api.belegUrl(b.doc_id), "_blank", "noopener") }, "⛁ gesicherter Beleg") : null,
          el("button", { class: "gefahr", onclick: async () => {
            const grund = await bestaetigen("Aussage widerrufen?", "Die Aussage bleibt sichtbar, zählt aber nicht mehr. Fakten, die nur an ihr hängen, fallen weg.", { ok: "Widerrufen", gefahr: true, feld: "Begründung (steht im Protokoll)" });
            if (!grund) return;
            try { await api.post("aussage/widerrufen", { aussage_id: b.aussage_id, grund }); melden("Widerrufen."); senden("bestand-geaendert"); akteZeigen(id); }
            catch (err) { fehler(err); }
          } }, "widerrufen")))));
  };

  leeren(s).append(el("div", { class: "akte" },
    el("button", { class: "symbol schliessen", onclick: akteSchliessen, title: "Schließen" }, "✕"),
    el("div", { class: "akte-kopf" },
      el("div", { class: "zeile" }, typAbz(e.typ), e.markiert ? el("span", { style: { color: "var(--einfach)" } }, "★ Zielobjekt") : null),
      el("h2", {}, e.name),
      e.namen.length > 1 ? el("div", { class: "gedaempft", style: { fontSize: "12px" } }, "Auch: ", e.namen.map(n => n.anzeige).filter(n => n !== e.name).join(" · ")) : null,
      e.ort ? el("div", { class: "mono gedaempft" }, `◍ ${e.ort.lat.toFixed(3)}, ${e.ort.lon.toFixed(3)} (${e.ort.genauigkeit || "Ort"}, Quelle: ${e.ort.quelle})`) : null,
      el("div", { class: "zeile", style: { flexWrap: "wrap" } },
        el("button", { class: "knopf haupt klein", onclick: () => senden("recherche", { auftrag: e.name, fokus: `Vertiefung zu ${e.name}: Beteiligungen, Geldflüsse, Funktionen, Verfahren` }) }, "⌕ Vertiefen"),
        el("button", { class: "knopf klein", onclick: () => senden("zeige", { ansicht: "netz", param: id }) }, "⬡ Im Netz"),
        el("button", { class: "knopf klein", onclick: () => speichern({ markiert: !e.markiert }).then(() => akteZeigen(id)) }, e.markiert ? "☆ Markierung lösen" : "★ Als Ziel markieren"))),
    e.beschreibung ? el("p", { style: { margin: 0 } }, e.beschreibung) : null,
    el("div", { style: { display: "grid", gap: "8px" } },
      el("h4", {}, `Ausgehend · ${aus.length}`), aus.length ? aus.map(f => faktKarte(f, "aus")) : el("div", { class: "gedaempft" }, "—"),
      el("h4", { style: { marginTop: "8px" } }, `Eingehend · ${ein.length}`), ein.length ? ein.map(f => faktKarte(f, "ein")) : el("div", { class: "gedaempft" }, "—")),
    el("div", { style: { display: "grid", gap: "8px" } },
      el("h4", {}, "Steckbrief"),
      el("label", {}, "Typ", typ),
      el("label", {}, "Beschreibung", besch),
      el("label", {}, "Notiz", notiz),
      el("button", { class: "knopf", onclick: () => speichern({ typ: typ.value, beschreibung: besch.value, notiz: notiz.value }) }, "Speichern"))));
}
