// IndraNet — Bausteine der Oberfläche: Elemente, Meldungen, Dialoge,
// Formatierung, Vokabular.

export const LAGE_TEXT = {
  BESTAETIGT: "bestätigt", EINFACH_BELEGT: "einfach belegt",
  UMSTRITTEN: "umstritten", WIDERRUFEN: "widerrufen",
  bestaetigt: "bestätigt", einfach: "einfach belegt", umstritten: "umstritten",
  schlussfolgerung: "Schlussfolgerung",
};

export const TYP_TEXT = {
  PERSON: "Person", ORG: "Organisation", PLACE: "Ort", VESSEL: "Schiff",
  ADRESSE: "Adresse", AMT: "Amt", KENNUNG: "Kennung", BETRAG: "Betrag",
  DATUM: "Datum", REGISTER: "Register", AUTO: "Entität",
};

export const vokabular = { praedikate: {} };

export function praed(p) { return vokabular.praedikate[p] || p.replaceAll("_", " "); }

// ------------------------------------------------------------------ DOM
export function el(tag, attrs = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kinder.flat()) {
    if (k === null || k === undefined || k === false) continue;
    e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return e;
}

export function leeren(e) { while (e.firstChild) e.firstChild.remove(); return e; }

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ------------------------------------------------------------- Abzeichen
export function lageAbz(lage) {
  return el("span", { class: `lage-abz lage-${lage}` }, LAGE_TEXT[lage] || lage);
}
export function typAbz(typ) {
  return el("span", { class: `typ ${typ || "AUTO"}` }, el("i"), TYP_TEXT[typ] || typ || "Entität");
}

// ------------------------------------------------------------ Meldungen
export function melden(text, art = "info", dauer = 5200) {
  const m = el("div", { class: `meldung ${art}` }, text);
  document.getElementById("meldungen").append(m);
  setTimeout(() => m.remove(), dauer);
}
export function fehler(e) { melden(e?.message || String(e), "fehler", 8000); }

// --------------------------------------------------------------- Dialog
export function dialog(inhalt, { breit = false } = {}) {
  const huelle = document.getElementById("dialog-huelle");
  leeren(huelle);
  const d = el("div", { class: `tafel dialog${breit ? " breit" : ""}`, role: "dialog", "aria-modal": "true" });
  d.append(...[inhalt].flat());
  huelle.append(d);
  huelle.hidden = false;
  const zu = () => { huelle.hidden = true; leeren(huelle); document.removeEventListener("keydown", esc_); };
  const esc_ = (ev) => { if (ev.key === "Escape") zu(); };
  document.addEventListener("keydown", esc_);
  huelle.onclick = (ev) => { if (ev.target === huelle) zu(); };
  setTimeout(() => d.querySelector("input, textarea, select, button.haupt")?.focus(), 30);
  return { element: d, schliessen: zu };
}

export function bestaetigen(titel, text, { ok = "Bestätigen", gefahr = false, feld = null } = {}) {
  return new Promise(res => {
    const eingabe = feld ? el("textarea", { rows: 3, placeholder: feld }) : null;
    const d = dialog([
      el("div", { class: "tafel-kopf" }, titel),
      el("p", { class: "gedaempft", style: { margin: 0 } }, text),
      eingabe ? el("label", {}, feld, eingabe) : null,
      el("div", { class: "knopfreihe" },
        el("button", { class: "knopf flach", onclick: () => { d.schliessen(); res(null); } }, "Abbrechen"),
        el("button", { class: `knopf ${gefahr ? "gefahr" : "haupt"}`, onclick: () => {
          if (eingabe && !eingabe.value.trim()) { eingabe.focus(); return; }
          d.schliessen(); res(eingabe ? eingabe.value.trim() : true);
        } }, ok)),
    ]);
  });
}

// ------------------------------------------------------------- Formate
export function zeit(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  const heute = new Date();
  const gleich = d.toDateString() === heute.toDateString();
  return gleich ? d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit" }) + " " +
      d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}
export function seit(ts) {
  if (!ts) return "nie";
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "gerade eben";
  if (s < 3600) return `vor ${Math.round(s / 60)} min`;
  if (s < 86400) return `vor ${Math.round(s / 3600)} h`;
  return `vor ${Math.round(s / 86400)} Tagen`;
}
export function domain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; }
}

// Kleiner, sicherer Markdown-Leser: Überschriften, Listen, Fett, Kursiv.
// Erst maskieren, dann formatieren — kein HTML aus der KI erreicht das DOM.
export function markdown(text) {
  const zeilen = esc(text || "").split(/\r?\n/);
  const raus = [];
  let liste = false;
  const inline = s => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>").replace(/`(.+?)`/g, "<code>$1</code>");
  for (const z of zeilen) {
    const m = z.match(/^(#{1,4})\s+(.*)$/);
    const li = z.match(/^\s*[-*•]\s+(.*)$/) || z.match(/^\s*\d+[.)]\s+(.*)$/);
    if (!li && liste) { raus.push("</ul>"); liste = false; }
    if (m) raus.push(`<h${Math.min(m[1].length + 1, 4)}>${inline(m[2])}</h${Math.min(m[1].length + 1, 4)}>`);
    else if (li) { if (!liste) { raus.push("<ul>"); liste = true; } raus.push(`<li>${inline(li[1])}</li>`); }
    else if (z.trim()) raus.push(`<p>${inline(z)}</p>`);
  }
  if (liste) raus.push("</ul>");
  return raus.join("");
}

// Externe Adressen: öffnen ohne Referrer. Im Tor-Modus vorher warnen —
// der normale Browser geht NICHT über Tor.
export function externOeffnen(url, torAktiv) {
  const los = () => window.open(url, "_blank", "noopener,noreferrer");
  if (!torAktiv) return los();
  bestaetigen("Seite außerhalb von Tor öffnen?",
    `IndraNet ruft über Tor ab, Ihr Browser aber nicht. Wenn Sie ${domain(url)} jetzt öffnen, sieht die Seite Ihre echte IP-Adresse. Besser: Adresse kopieren und im Tor Browser öffnen.`,
    { ok: "Trotzdem öffnen" }).then(ja => ja && los());
}

export function kopieren(text) {
  navigator.clipboard?.writeText(text).then(() => melden("In die Zwischenablage kopiert."),
    () => melden("Kopieren nicht möglich — bitte von Hand markieren.", "warn"));
}
