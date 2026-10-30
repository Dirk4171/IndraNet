// IndraNet — gemeinsamer Zustand der Oberfläche und ein kleiner Ereignisbus.

export const S = {
  status: null,       // /api/status
  stats: null,        // /api/stats
  ansicht: "lage",
  auftraege: [],
  bekannteAuftraege: new Map(),   // id -> status, um Übergänge zu erkennen
  get torAktiv() { return this.status?.netzweg?.modus === "tor"; },
};

const hoerer = new Map();

export function an(name, f) {
  if (!hoerer.has(name)) hoerer.set(name, new Set());
  hoerer.get(name).add(f);
  return () => hoerer.get(name).delete(f);
}

export function senden(name, daten) {
  for (const f of hoerer.get(name) || []) {
    try { f(daten); } catch (e) { console.error(e); }
  }
}
