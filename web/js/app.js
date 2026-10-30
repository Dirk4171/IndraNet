// IndraNet — Hauptprogramm der Oberfläche: Start, Projekt, Suche, Ablage,
// Aufträge, Navigation.

import * as api from "./api.js";
import { el, leeren, melden, fehler, dialog, vokabular, zeit, seit, bestaetigen } from "./ui.js";
import { startGlobus } from "./karte.js";
import { S, an, senden } from "./zustand.js";
import { ANSICHTEN } from "./ansichten.js";
import { einstellungenDialog } from "./system.js";
import { brueckeDialog } from "./bruecke.js";

const $ = (s) => document.querySelector(s);
let globus = null;
let aktuelleAnsicht = null;
let suchModus = "web";

// =================================================================== Start
async function init() {
  try {
    const v = await api.get("vokabular");
    vokabular.praedikate = v.praedikate;
    vokabular.typen = v.typen;
    vokabular.quellen = v.quellen;
    await statusLaden();
  } catch (e) { fehler(e); return; }
  verdrahten();
  if (S.status.projekt) await arbeitZeigen(); else await startZeigen();
  setInterval(takt, 2500);
}

async function statusLaden() {
  S.status = await api.get("status");
  const thema = S.status.einstellungen?.thema;
  if (thema && document.documentElement.dataset.thema !== thema) document.documentElement.dataset.thema = thema;
  anzeigenAktualisieren();
  return S.status;
}

async function startZeigen() {
  $("#arbeit").hidden = true;
  $("#start").hidden = false;
  document.title = "IndraNet";
  if (!globus) globus = startGlobus($("#start-globus"));
  const { projekte } = await api.get("projekte");
  const liste = leeren($("#projektliste"));
  $("#projektliste-leer").hidden = projekte.length > 0;
  for (const p of projekte) {
    const li = el("li");
    const form = el("form", { hidden: true, autocomplete: "off" },
      el("input", { type: "password", name: "pw", placeholder: "Passphrase", required: true, autocomplete: "current-password" }),
      el("button", { class: "knopf haupt", type: "submit" }, "Öffnen"));
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const knopf = form.querySelector("button");
      knopf.disabled = true; knopf.textContent = "Entschlüssle …";
      try {
        S.status = await api.post("projekt/oeffnen", { name: p.name, passphrase: form.pw.value });
        await arbeitZeigen();
      } catch (e) { fehler(e); form.pw.select(); }
      finally { knopf.disabled = false; knopf.textContent = "Öffnen"; }
    });
    li.append(el("div", { class: "zeile", onclick: () => { form.hidden = !form.hidden; form.pw.focus(); } },
      el("span", { class: "schloss" }, "🔒"), el("b", {}, p.name.replaceAll("-", " ")),
      el("small", {}, `${(p.groesse / 1024).toFixed(0)} KB · ${zeit(p.geaendert)}`)), form);
    liste.append(li);
  }
  startStatus();
}

function startStatus() {
  const s = S.status;
  const ki = s.ki.bereit ? `KI ${s.ki.modell}` : `KI: ${s.ki.grund}`;
  const weg = s.netzweg.modus === "tor" ? (s.tor.bereit ? "Tor verbunden" : `Tor ${s.tor.fortschritt}%`) : s.netzweg.modus === "proxy" ? "über Proxy" : "direkte Verbindung";
  leeren($("#start-status")).append(
    el("span", {}, el("i", { class: `punkt ${s.ki.bereit ? "gut" : "warn"}` }), " ", ki),
    el("span", {}, el("i", { class: `punkt ${s.netzweg.modus === "direkt" ? "warn" : s.netzweg.bereit ? "gut" : "schlecht"}` }), " Netzweg: ", weg));
}

async function arbeitZeigen() {
  globus?.stop(); globus = null;
  $("#start").hidden = true;
  $("#arbeit").hidden = false;
  const p = S.status.projekt;
  $("#projekt-titel").textContent = p.titel || p.name;
  document.title = `${p.titel || p.name} · IndraNet`;
  await statsLaden();
  zeige(S.ansicht || "lage");
}

async function statsLaden() {
  if (!S.status?.projekt) return;
  try {
    S.stats = await api.get("stats");
    statuszeile();
    senden("stats", S.stats);
  } catch (e) { if (e.code === 409) { S.status.projekt = null; startZeigen(); } }
}

// ============================================================== Navigation
export function zeige(name, param) {
  const ansicht = ANSICHTEN[name];
  if (!ansicht) return;
  aktuelleAnsicht?.verlassen?.();
  S.ansicht = name;
  for (const b of document.querySelectorAll(".schiene button")) b.classList.toggle("aktiv", b.dataset.ansicht === name);
  const main = leeren($("#ansicht"));
  main.classList.toggle("voll", !!ansicht.voll);
  aktuelleAnsicht = ansicht;
  Promise.resolve(ansicht.zeigen(main, param)).catch(fehler);
}
window.indra = { zeige };
an("zeige", ({ ansicht, param }) => zeige(ansicht, param));

// ================================================================== Suche
function verdrahten() {
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-ansicht], [data-aktion]");
    if (!b) return;
    if (b.dataset.ansicht) {
      if (!S.status?.projekt) return einstellungenDialog();
      return zeige(b.dataset.ansicht);
    }
    const a = b.dataset.aktion;
    if (a === "einstellungen") einstellungenDialog(() => statusLaden().then(startStatus));
    if (a === "projekt-schliessen") projektSchliessen();
    if (a === "datei-waehlen") $("#datei-feld").click();
    if (a === "auftraege") auftraegeUmschalten();
    if (a === "sichern") api.post("projekt/sichern").then(() => { melden("Projekt verschlüsselt gesichert."); statsLaden(); }, fehler);
  });

  for (const b of document.querySelectorAll(".suche .modus button")) {
    b.addEventListener("click", () => modusSetzen(b.dataset.modus));
  }
  $("#suche").addEventListener("submit", (ev) => { ev.preventDefault(); suchen(); });
  $("#datei-feld").addEventListener("change", (ev) => { dateienAblegen([...ev.target.files]); ev.target.value = ""; });

  $("#form-neu").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    if (f.passphrase.value !== f.passphrase2.value) return melden("Die Passphrasen stimmen nicht überein.", "fehler");
    const knopf = f.querySelector("button[type=submit]");
    knopf.disabled = true; knopf.textContent = "Verschlüssele …";
    try {
      S.status = await api.post("projekt/anlegen", {
        name: f.name.value, zweck: f.zweck.value, netzname: f.netzname.value, passphrase: f.passphrase.value,
      });
      f.reset();
      S.ansicht = "lage";
      await arbeitZeigen();
      melden("Projekt angelegt. Geben Sie oben einen Namen oder eine Firma ein — oder ziehen Sie eine Datei ins Fenster.");
    } catch (e) { fehler(e); }
    finally { knopf.disabled = false; knopf.textContent = "Projekt verschlüsselt anlegen"; }
  });

  // Ablegen per Ziehen
  let tiefe = 0;
  window.addEventListener("dragenter", (ev) => {
    if (!S.status?.projekt || !ev.dataTransfer?.types.includes("Files")) return;
    tiefe++; $("#ablage").hidden = false;
  });
  window.addEventListener("dragleave", () => { if (--tiefe <= 0) { tiefe = 0; $("#ablage").hidden = true; } });
  window.addEventListener("dragover", (ev) => ev.preventDefault());
  window.addEventListener("drop", (ev) => {
    ev.preventDefault(); tiefe = 0; $("#ablage").hidden = true;
    if (S.status?.projekt && ev.dataTransfer.files.length) dateienAblegen([...ev.dataTransfer.files]);
  });

  document.addEventListener("keydown", (ev) => {
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k" && S.status?.projekt) {
      ev.preventDefault(); $("#suche-feld").focus(); $("#suche-feld").select();
    }
  });
}

function modusSetzen(m) {
  suchModus = m;
  for (const b of document.querySelectorAll(".suche .modus button")) b.classList.toggle("aktiv", b.dataset.modus === m);
  $("#register-quelle").hidden = m !== "register";
  $("#suche-feld").placeholder = {
    web: "Name, Firma, Schiff, Frage … oder Datei hierher ziehen",
    register: "Firmen- oder Personenname für das Register",
    frage: "Frage an den eigenen Bestand, z. B. »Wer steht hinter der Mare Liberum Ltd.?«",
  }[m];
  $("#suche-feld").focus();
}

export async function recherchieren(auftrag, fokus = "") {
  try {
    const r = await api.post("recherche", { auftrag, fokus });
    melden(r.bruecke ? `Auftrag für claude.ai wird vorbereitet: »${auftrag}« — IndraNet fragt erst die Register ab.`
      : `Recherche läuft: »${auftrag}«. Ergebnisse landen im Prüfkorb.`);
    S.bekannteAuftraege.set(r.auftrag, "laeuft");
    auftraegeLaden(true);
    return r;
  } catch (e) { fehler(e); }
}
an("recherche", ({ auftrag, fokus }) => recherchieren(auftrag, fokus));

async function suchen() {
  const feld = $("#suche-feld");
  const text = feld.value.trim();
  if (!text) return;
  try {
    if (suchModus === "web") await recherchieren(text);
    else if (suchModus === "register") {
      const r = await api.post("register", { quelle: $("#register-quelle").value, begriff: text });
      S.bekannteAuftraege.set(r.auftrag, "laeuft");
      melden(`Registerabfrage läuft: ${$("#register-quelle").selectedOptions[0].textContent}`);
    } else {
      const r = await api.post("lagebild", { frage: text });
      S.bekannteAuftraege.set(r.auftrag, "laeuft");
      if (!r.bruecke) melden("Die KI wertet den Bestand aus — das Lagebild erscheint unter »Lagebilder«.");
    }
    feld.value = "";
    auftraegeLaden(true);
  } catch (e) { fehler(e); }
}

// ================================================================== Ablage
function dateienAblegen(dateien) {
  if (!dateien.length) return;
  const stufe = el("select", { name: "stufe" },
    el("option", { value: "OEFFENTLICH" }, "Öffentlich — Register, Presse, Veröffentlichtes"),
    el("option", { value: "INTERN", selected: true }, "Intern — eigene Recherche, unveröffentlicht"),
    el("option", { value: "VERTRAULICH" }, "Vertraulich — Hintergrund, Quelle bekannt"),
    el("option", { value: "WHISTLEBLOWER" }, "Whistleblower — Quelle gefährdet"));
  const kiOk = S.status.ki.bereit;
  const analyse = el("input", { type: "checkbox", checked: kiOk, disabled: !kiOk });
  const d = dialog([
    el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⇪"), `${dateien.length} Datei(en) ablegen`),
    el("ul", { class: "liste" }, dateien.map(f => el("li", {}, el("div", { class: "zeile" },
      el("b", {}, f.name), el("span", { class: "rechts mono gedaempft" }, `${(f.size / 1024).toFixed(0)} KB`))))),
    el("label", {}, "Schutzstufe", stufe),
    el("label", { class: "schalter" }, analyse, !kiOk ? `KI-Analyse nicht verfügbar (${S.status.ki.grund})`
      : S.status.ki.bruecke ? "In claude.ai analysieren — IndraNet schreibt den Auftrag zum Kopieren"
        : "Von der KI analysieren lassen — Ergebnisse gehen in den Prüfkorb"),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } },
      "Jede Datei wird verschlüsselt im Projekt abgelegt. Word, Excel, PowerPoint, OpenDocument, PDF, E-Mail, Text, CSV, JSON, HTML werden gelesen; Scans und Bilder liest die Claude-KI direkt."),
    el("div", { class: "knopfreihe" },
      el("button", { class: "knopf flach", onclick: () => d.schliessen() }, "Abbrechen"),
      el("button", { class: "knopf haupt", onclick: async () => {
        d.schliessen();
        for (const f of dateien) {
          try {
            const r = await api.hochladen(f, { stufe: stufe.value, analysieren: analyse.checked });
            S.bekannteAuftraege.set(r.auftrag, "laeuft");
            melden(`${f.name}: abgelegt${r.analyse ? ", Analyse läuft" : ""}.`);
          } catch (e) { fehler(e); }
        }
        auftraegeLaden(true);
      } }, "Ablegen")),
  ]);
}

// ================================================================ Aufträge
let tafelOffen = false;
function auftraegeUmschalten() {
  tafelOffen = !tafelOffen;
  $("#auftraege-tafel").hidden = !tafelOffen;
  if (tafelOffen) auftraegeZeichnen();
}

async function auftraegeLaden(oeffnen = false) {
  if (!S.status?.projekt) return;
  const { auftraege } = await api.get("auftraege");
  S.auftraege = auftraege;
  for (const a of auftraege) {
    const alt = S.bekannteAuftraege.get(a.id);
    if (alt && alt !== a.status && (a.status === "fertig" || a.status === "fehler")) auftragFertig(a);
    S.bekannteAuftraege.set(a.id, a.status);
  }
  const laufend = auftraege.filter(a => a.status === "laeuft" || a.status === "wartet").length;
  const anz = $("#anz-auftraege");
  anz.classList.toggle("arbeitet", laufend > 0);
  anz.querySelector("span").textContent = laufend ? `${laufend} LÄUFT` : "AUFTRÄGE";
  if (oeffnen && !tafelOffen && laufend) auftraegeUmschalten();
  if (tafelOffen) auftraegeZeichnen();
  senden("auftraege", auftraege);
}

function auftragFertig(a) {
  if (a.status === "fehler") { melden(`${a.titel}: ${a.fehler}`, "fehler", 10000); return; }
  const e = a.ergebnis || {};
  if (e.bruecke && e.offen) { brueckeDialog(a); return; }
  if (a.art === "recherche" || a.art === "datei") {
    melden(`${a.titel}: ${e.aussagen ?? 0} Aussagen im Prüfkorb.`);
    statsLaden();
    if (S.ansicht === "pruefkorb" || S.ansicht === "lage") zeige(S.ansicht, S.ansicht === "pruefkorb" ? e.fund_id : undefined);
  } else if (a.art === "uebernahme") {
    melden(`${e.aussagen} Aussagen übernommen und gesichert.`);
    statsLaden();
    senden("bestand-geaendert");
  } else if (a.art === "lagebild") {
    melden(`Lagebild fertig: ${e.titel || ""}`);
    zeige("lagebilder", e.lagebild_id);
  } else if (a.art === "register") {
    S.letztesRegister = a;
    if (S.ansicht !== "quellen") zeige("quellen"); else senden("register-ergebnis", a);
  } else if (a.art === "verknuepfen") {
    if (e.vorschlaege) melden(`${e.vorschlaege} neue Vorschläge der KI.`);
    statsLaden();
    senden("vorschlaege");
  } else if (a.art === "abgleich") {
    senden("netzwerke");
  }
}

function auftraegeZeichnen() {
  const t = leeren($("#auftraege-tafel"));
  t.append(el("div", { class: "tafel-kopf" }, "Hintergrundaufträge",
    el("span", { class: "rechts" }, el("button", { class: "knopf klein flach", onclick: auftraegeUmschalten }, "✕"))));
  if (!S.auftraege.length) t.append(el("div", { class: "leer" }, "Noch keine Aufträge in dieser Sitzung."));
  for (const a of S.auftraege.slice(0, 12)) {
    const offen = a.status === "fertig" && a.ergebnis?.bruecke && a.ergebnis?.offen;
    t.append(el("div", { class: "auftrag" },
      el("div", { class: "zeile" }, el("span", { class: `zustand ${offen ? "wartet" : a.status}` }, offen ? "Ihre Antwort" : { wartet: "wartet", laeuft: "läuft", fertig: "fertig", fehler: "Fehler" }[a.status]),
        el("b", {}, a.titel), el("span", { class: "mono gedaempft" }, zeit(a.start))),
      el("div", { class: "protokoll" }, a.meldungen.slice(-7).map((m, i, xs) =>
        el("div", { class: i === xs.length - 1 && a.status === "laeuft" ? "neu" : "" }, el("time", {}, zeit(m.ts)), m.text))),
      a.fehler ? el("div", { class: "fehler" }, a.fehler) : null,
      offen ? el("button", { class: "knopf klein haupt", onclick: () => { brueckeDialog(a); auftraegeUmschalten(); } }, "⇄ Auftrag für claude.ai") : null,
      a.status === "fertig" && a.ergebnis?.fund_id ? el("button", { class: "knopf klein", onclick: () => { zeige("pruefkorb", a.ergebnis.fund_id); auftraegeUmschalten(); } }, "Im Prüfkorb ansehen") : null));
  }
}

// =================================================================== Takt
let taktZaehler = 0;
async function takt() {
  taktZaehler++;
  try {
    if (S.status?.projekt) await auftraegeLaden();
    if (taktZaehler % 2 === 0) {
      await statusLaden();
      if (!S.status.projekt && !$("#arbeit").hidden) return startZeigen();
      if (!$("#start").hidden) startStatus();
    }
    if (S.status?.projekt && taktZaehler % 4 === 0) await statsLaden();
  } catch (e) {
    if (e.code === 401) { melden("Sitzung abgelaufen — IndraNet wurde neu gestartet. Seite wird neu geladen.", "warn"); setTimeout(() => location.reload(), 1500); }
  }
}

function anzeigenAktualisieren() {
  const s = S.status;
  if (!s) return;
  const weg = $("#anz-netzweg");
  weg.className = "anzeige";
  if (s.netzweg.modus === "tor") {
    weg.classList.add(s.tor.bereit ? "gut" : s.tor.laeuft ? "arbeitet" : "schlecht");
    const bruecke = s.tor.bruecken ? ` · ${s.tor.bruecken.toUpperCase()}` : "";
    weg.querySelector("span").textContent = s.tor.bereit ? `TOR${bruecke}` : s.tor.laeuft ? `TOR ${s.tor.fortschritt}%${bruecke}` : "TOR AUS";
  } else if (s.netzweg.modus === "proxy") {
    weg.classList.add(s.netzweg.bereit ? "gut" : "schlecht");
    weg.querySelector("span").textContent = "PROXY";
  } else {
    weg.classList.add("warn");
    weg.querySelector("span").textContent = "DIREKT";
  }
  weg.title = s.netzweg.modus === "direkt" ? "Abrufe gehen direkt hinaus — Ihre IP ist sichtbar" : (s.netzweg.fehler || "Abrufe laufen verschleiert");
  const ki = $("#anz-ki");
  ki.className = `anzeige ${s.ki.bereit ? "gut" : "schlecht"}`;
  ki.querySelector("span").textContent = s.ki.bereit ? (s.ki.modell || "KI").replace("claude-", "").replace(/-(\d)-(\d)$/, " $1.$2").toUpperCase() : "KI FEHLT";
  ki.title = s.ki.bereit ? `KI: ${s.ki.modell}` : s.ki.grund;
}

function statuszeile() {
  const s = S.stats;
  if (!s) return;
  const z = leeren($("#statuszeile"));
  const lage = s.beleglage || {};
  z.append(
    el("span", {}, "ENTITÄTEN ", el("b", {}, s.entitaeten)),
    el("span", {}, "FAKTEN ", el("b", {}, s.fakten)),
    el("span", { style: { color: "var(--bestaetigt)" } }, "● ", el("b", {}, lage.BESTAETIGT || 0), " bestätigt"),
    el("span", { style: { color: "var(--einfach)" } }, "● ", el("b", {}, lage.EINFACH_BELEGT || 0), " einfach"),
    el("span", { style: { color: "var(--umstritten)" } }, "● ", el("b", {}, lage.UMSTRITTEN || 0), " umstritten"),
    el("span", {}, "BELEGE ", el("b", {}, s.dokumente)),
    el("span", { class: "rechts" }, s.geaendert ? "◌ Änderungen werden gesichert …" : `⛁ verschlüsselt gesichert ${seit(s.zuletzt_gesichert)}`));
  const zp = $("#z-pruefkorb");
  zp.hidden = !s.pruefkorb; zp.textContent = s.pruefkorb;
}

async function projektSchliessen() {
  const ok = await bestaetigen("Projekt schließen?", "Der Stand wird verschlüsselt gesichert. Laufende Aufträge werden noch zu Ende geführt, ihre Ergebnisse erscheinen beim nächsten Öffnen.", { ok: "Schließen" });
  if (!ok) return;
  aktuelleAnsicht?.verlassen?.(); aktuelleAnsicht = null;
  $("#seite").hidden = true;
  try { S.status = await api.post("projekt/schliessen"); } catch (e) { fehler(e); }
  S.ansicht = "lage";
  startZeigen();
}

an("stats-laden", statsLaden);
// Aufträge aus anderen Ansichten: merken, damit ihr Ende ankommt — ein
// Auftrag für claude.ai ist oft fertig, bevor der Takt ihn laufen sieht.
an("auftrag-gestartet", (id) => { S.bekannteAuftraege.set(id, "laeuft"); auftraegeLaden(true); });
an("status-laden", () => statusLaden());
init();
