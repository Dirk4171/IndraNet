// IndraNet — Brücke zu claude.ai: Auftrag kopieren, im eigenen Chat
// ausführen, Antwort einfügen. Für Claude-Abos ohne API-Guthaben.

import * as api from "./api.js";
import { el, leeren, melden, dialog, externOeffnen } from "./ui.js";
import { senden } from "./zustand.js";

const WAS = { web: "Recherche", datei: "Dateianalyse", lagebild: "Lagebild" };

async function inZwischenablage(text, feld) {
  try { await navigator.clipboard.writeText(text); return true; } catch { /* Ersatzweg */ }
  feld.focus(); feld.select();
  try { return document.execCommand("copy"); } catch { return false; }
}

export function brueckeDialog(a) {
  const e = a.ergebnis || {};
  const titel = e.art === "lagebild" ? (e.frage || "Gesamtlage") : e.anfrage;
  const auftrag = el("textarea", { class: "mono", rows: 5, readonly: true, style: { fontSize: "11px" } }, e.auftrag_text || "");
  const antwort = el("textarea", { rows: 6, placeholder: "Antwort von Claude hier einfügen (Strg+V) — die ganze Antwort oder nur den JSON-Block." });
  const rueckmeldung = el("div");

  const kopieren = el("button", { class: "knopf haupt", onclick: async () => {
    const ok = await inZwischenablage(e.auftrag_text || "", auftrag);
    kopieren.textContent = ok ? "✓ Kopiert" : "Bitte von Hand kopieren";
    if (!ok) melden("Kopieren nicht möglich — Text im Feld markieren und Strg+C.", "warn");
  } }, "Auftrag kopieren");

  const schritt2 = e.art === "lagebild"
    ? "Neuen Chat öffnen und den Auftrag einfügen. Eine Websuche ist nicht nötig."
    : e.anhaengen
      ? `Neuen Chat öffnen, die Datei »${e.anfrage}« anhängen und den Auftrag einfügen.`
      : "Neuen Chat öffnen, die Websuche einschalten und den Auftrag einfügen.";

  const uebernehmen = el("button", { class: "knopf haupt", onclick: async () => {
    if (!antwort.value.trim()) { antwort.focus(); return; }
    uebernehmen.disabled = true;
    leeren(rueckmeldung);
    try {
      const r = await api.post("bruecke/antwort", { auftrag: a.id, antwort: antwort.value });
      d.schliessen();
      senden("stats-laden");
      if (r.lagebild_id) {
        melden(`Lagebild aus claude.ai gespeichert: ${r.titel}`);
        senden("zeige", { ansicht: "lagebilder", param: r.lagebild_id });
      } else {
        melden(`${r.aussagen} Aussagen im Prüfkorb${r.verworfen ? ` — ${r.verworfen} verworfen (ohne Beleg-Adresse oder Prädikat nicht in der Liste)` : ""}.`, "info", 8000);
        senden("zeige", { ansicht: "pruefkorb", param: r.fund_id });
      }
    } catch (er) {
      const h = el("div", { class: "hinweis schlecht" }, er.message || String(er));
      rueckmeldung.append(h);
      h.scrollIntoView({ block: "nearest" });
    } finally { uebernehmen.disabled = false; }
  } }, e.art === "lagebild" ? "Lagebild speichern" : "In den Prüfkorb");

  const schritt = (n, text, ...inhalt) => el("div", { style: { display: "grid", gap: "8px" } },
    el("div", { class: "etikett" }, `Schritt ${n} — ${text}`), ...inhalt);

  const d = dialog([
    el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⇄"), `${WAS[e.art] || "Auftrag"} über claude.ai: ${titel}`),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12.5px" } },
      "Ihr Claude-Abo gilt nur in Anthropics eigenen Programmen. Deshalb geht dieser Schritt über Sie: Den Auftrag mit Regeln, Antwortvorlage",
      e.art === "web" ? " und Registerauszügen" : "", " hat IndraNet geschrieben. Die Antwort prüft IndraNet wie jeden KI-Befund — in den Bestand geht nur, was Sie im Prüfkorb übernehmen."),
    schritt(1, `Auftrag kopieren (${(e.auftrag_text || "").length.toLocaleString("de-DE")} Zeichen)`,
      auftrag, el("div", { class: "knopfreihe", style: { justifyContent: "flex-start" } }, kopieren)),
    schritt(2, "In claude.ai ausführen",
      el("p", { style: { margin: 0, fontSize: "13px" } }, schritt2),
      el("div", { class: "knopfreihe", style: { justifyContent: "flex-start" } },
        el("button", { class: "knopf", onclick: () => externOeffnen("https://claude.ai/new", false) }, "↗ claude.ai öffnen")),
      el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } },
        "claude.ai läuft in Ihrem normalen Browser, nicht über Tor. Anthropic sieht den Auftrag unter Ihrem Konto — wie bei jeder Nutzung von Claude.")),
    schritt(3, "Antwort einfügen", antwort, rueckmeldung),
    el("div", { class: "knopfreihe" },
      el("button", { class: "knopf flach", onclick: () => d.schliessen() }, "Später"),
      uebernehmen),
  ], { breit: true });
  return d;
}
