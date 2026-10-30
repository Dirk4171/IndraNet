// IndraNet — Verbindung zum lokalen Server.
// Jede Anfrage trägt die Sitzungsmarke aus der ausgelieferten Seite.

const TOKEN = document.querySelector('meta[name="indra-token"]').content;

export class ApiFehler extends Error {
  constructor(text, code) { super(text); this.code = code; }
}

async function antwort(r) {
  let daten = null;
  try { daten = await r.json(); } catch { /* kein JSON */ }
  if (!r.ok) throw new ApiFehler((daten && daten.fehler) || `HTTP ${r.status}`, r.status);
  return daten;
}

export async function get(pfad, parameter = {}) {
  const q = new URLSearchParams(parameter).toString();
  const r = await fetch(`/api/${pfad}${q ? "?" + q : ""}`, {
    headers: { "X-Indra-Token": TOKEN }, cache: "no-store",
  });
  return antwort(r);
}

export async function post(pfad, koerper = {}) {
  const r = await fetch(`/api/${pfad}`, {
    method: "POST",
    headers: { "X-Indra-Token": TOKEN, "Content-Type": "application/json" },
    body: JSON.stringify(koerper),
  });
  return antwort(r);
}

export async function hochladen(datei, { stufe = "INTERN", analysieren = true } = {}) {
  const r = await fetch("/api/datei", {
    method: "POST",
    headers: {
      "X-Indra-Token": TOKEN,
      "X-Dateiname": encodeURIComponent(datei.name),
      "X-Stufe": stufe,
      "X-Analysieren": analysieren ? "1" : "0",
      "Content-Type": datei.type || "application/octet-stream",
    },
    body: datei,
  });
  return antwort(r);
}

// Belege und Exporte werden in einem neuen Fenster geöffnet. Die Marke geht
// dabei als Parameter mit — nur an den eigenen Server, nie nach außen.
export function belegUrl(docId, laden = false) {
  return `/api/beleg?doc_id=${encodeURIComponent(docId)}&t=${encodeURIComponent(TOKEN)}${laden ? "&laden=1" : ""}`;
}

export function dossierUrl() {
  return `/api/dossier?t=${encodeURIComponent(TOKEN)}`;
}
