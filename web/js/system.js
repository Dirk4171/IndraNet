// IndraNet — Quellen (Register direkt, Zustand der Anschlüsse, Verlauf) und
// System (KI, Netzweg, Tor, Verhalten).

import * as api from "./api.js";
import { el, leeren, fehler, melden, dialog, zeit, seit, externOeffnen } from "./ui.js";
import { S, an, senden } from "./zustand.js";

// ================================================================== QUELLEN
export const QUELLEN = {
  abmelden: [],
  async zeigen(main) {
    const [{ quellen }, { verlauf }] = await Promise.all([api.get("quellen"), api.get("verlauf")]);
    const ergebnis = el("div", { style: { display: "grid", gap: "10px" } });
    const quelle = el("select", {}, quellen.map(q => el("option", { value: q.quelle }, q.beschreibung)));
    const begriff = el("input", { placeholder: "Firmen- oder Personenname" });
    const abfragen = async () => {
      if (!begriff.value.trim()) return;
      try {
        const r = await api.post("register", { quelle: quelle.value, begriff: begriff.value.trim() });
        senden("auftrag-gestartet", r.auftrag);   // Ende wird registriert, auch bei Sofort-Fehlern
        leeren(ergebnis).append(el("div", { class: "leer" }, "Abfrage läuft …"));
      } catch (e) { fehler(e); }
    };
    begriff.addEventListener("keydown", ev => { if (ev.key === "Enter") abfragen(); });

    main.append(el("div", { class: "seiteninhalt" },
      el("div", { class: "kopfzeile" }, el("div", {}, el("h2", {}, "Quellen"),
        el("p", {}, "Offene Register und Datenbestände, direkt abgefragt — ohne KI, über Ihren Netzweg. Die KI nutzt dieselben Anschlüsse während einer Recherche selbständig."))),
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⌗"), "Register abfragen"),
        el("div", { style: { display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.4fr) auto", gap: "8px" } }, quelle, begriff,
          el("button", { class: "knopf haupt", onclick: abfragen }, "Abfragen")),
        ergebnis),
      el("div", { class: "raster-2" },
        el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "♥"), "Zustand der Anschlüsse"),
          el("ul", { class: "liste" }, quellen.map(q => el("li", {}, el("div", { class: "zeile" },
            el("i", { class: `punkt ${q.ok === null ? "" : q.ok ? "gut" : "schlecht"}` }), el("b", {}, q.beschreibung),
            el("span", { class: "rechts mono gedaempft" }, q.zuletzt ? seit(q.zuletzt) : "noch nicht benutzt")),
            q.fehler ? el("span", { class: "mono", style: { color: "var(--umstritten)", fontSize: "11px" } }, q.fehler) : null)))),
        el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⌚"), "Verlauf"),
          verlauf.length ? el("div", { class: "protokoll", style: { maxHeight: "420px" } }, verlauf.map(v =>
            el("div", {}, el("time", {}, zeit(v.ts)), el("span", { style: { color: "var(--akzent)" } }, v.art.toUpperCase()), " ", v.eingabe)))
            : el("div", { class: "gedaempft" }, "Noch nichts."))),
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, "Lizenzen der Daten"),
        el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12.5px" } },
          "GLEIF und Wikidata: CC0. Wikipedia: CC BY-SA. ICIJ Offshore Leaks: ODbL, Quelle ICIJ nennen; die Datenbank enthält auch legale Gesellschaften — ein Treffer ist kein Beleg für Fehlverhalten. OpenSanctions: CC BY-NC 4.0, Quelle OpenSanctions nennen, nur nicht-kommerziell; eine Listung ist ein Prüfhinweis, kein Urteil. Flugdaten: adsb.lol, offenes ADS-B-Empfängernetz, Quelle nennen. Schiffsdaten: Global Fishing Watch, Quelle nennen, nicht-kommerziell. GDELT: frei mit Quellenangabe. Kartendaten: Natural Earth, gemeinfrei."))));

    const zeichneErgebnis = (a) => {
      leeren(ergebnis);
      ergebnis.append(el("div", { class: "etikett" }, `Ergebnis: ${a.titel}`));
      if (a.status === "fehler") return ergebnis.append(el("div", { class: "hinweis schlecht" }, a.fehler));
      const r = a.ergebnis;
      if (!r.treffer.length) return ergebnis.append(el("div", { class: "hinweis" }, r.text));
      for (const t of r.treffer) {
        const name = t.name || t.titel;
        ergebnis.append(el("div", { class: "freigabe" },
          el("div", { class: "zeile", style: { display: "flex", gap: "10px", alignItems: "center" } }, el("b", {}, name || "—"),
            el("span", { style: { marginLeft: "auto", display: "flex", gap: "6px" } },
              t.url ? el("button", { class: "knopf klein flach", onclick: () => externOeffnen(t.url, S.torAktiv) }, "↗ Quelle") : null,
              name ? el("button", { class: "knopf klein", onclick: () => senden("recherche", { auftrag: name, fokus: `Ausgangspunkt: Treffer in ${r.quelle}` }) }, "⌕ KI-Recherche") : null)),
          el("div", { class: "mono gedaempft", style: { fontSize: "11.5px", display: "grid", gap: "2px" } },
            Object.entries(t).filter(([k, v]) => !["name", "titel", "url"].includes(k) && v).map(([k, v]) => el("span", {}, `${k}: ${v}`)))));
      }
    };
    if (S.letztesRegister) zeichneErgebnis(S.letztesRegister);
    QUELLEN.abmelden.push(an("register-ergebnis", zeichneErgebnis));
  },
  verlassen() { QUELLEN.abmelden.forEach(f => f()); QUELLEN.abmelden = []; },
};

// =================================================================== SYSTEM
export const SYSTEM = {
  async zeigen(main) {
    main.append(await einstellungenForm());
  },
};

export async function einstellungenDialog(nachher) {
  const d = dialog([await einstellungenForm(() => { d.schliessen(); nachher?.(); })], { breit: true });
}

async function einstellungenForm(fertig) {
  const e = await api.get("einstellungen");
  const w = { ...e };
  const radio = (name, werte) => el("div", { class: "wahl" }, werte.map(([wert, text]) => el("label", {},
    el("input", { type: "radio", name, value: wert, checked: e[name] === wert, onchange: () => { w[name] = wert; sichtbarkeit(); } }), el("span", {}, text))));
  const feld = (name, attrs = {}) => el("input", { value: e[name] ?? "", ...attrs, oninput: (ev) => { w[name] = attrs.type === "number" ? +ev.target.value : ev.target.value; } });
  const schalter = (name, text) => el("label", { class: "schalter" }, el("input", { type: "checkbox", checked: !!e[name], onchange: (ev) => { w[name] = ev.target.checked; } }), text);
  const schluessel = el("input", { type: "password", placeholder: e.claude_schluessel_gesetzt ? "•••••••• hinterlegt — leer lassen zum Behalten" : "sk-ant-…", autocomplete: "off" });
  const osSchluessel = el("input", { type: "password", placeholder: e.opensanctions_schluessel_gesetzt ? "•••••••• hinterlegt — leer lassen zum Behalten" : "ApiKey …", autocomplete: "off" });
  const gfwSchluessel = el("input", { type: "password", placeholder: e.gfw_schluessel_gesetzt ? "•••••••• hinterlegt — leer lassen zum Behalten" : "Token …", autocomplete: "off" });

  const claudeTeil = el("div", { style: { display: "grid", gap: "10px" } },
    el("label", {}, "Modell", el("select", { onchange: (ev) => { w.claude_modell = ev.target.value; } },
      e.modelle.map(m => el("option", { value: m.id, selected: m.id === e.claude_modell }, m.name)))),
    el("label", {}, "API-Schlüssel ", el("span", { class: "gedaempft" }, `(geschützt: ${e.schluessel_schutz})`), schluessel),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } }, "Schlüssel unter console.anthropic.com anlegen. Eine Recherche mit Websuche kostet je nach Modell und Tiefe etwa 0,05 – 0,60 €."));
  const chatTeil = el("div", { style: { display: "grid", gap: "8px" } },
    el("p", { style: { margin: 0, fontSize: "13px" } }, "Für Claude Pro oder Max ohne API-Guthaben: IndraNet schreibt jeden Auftrag — mit Regeln, Antwortvorlage und vorab abgefragten Registerauszügen — zum Kopieren. Sie führen ihn in Ihrem Chat auf claude.ai aus und fügen die Antwort wieder ein; sie landet im Prüfkorb."),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } }, "Das Abo gilt nur in Anthropics eigenen Programmen, deshalb dieser Weg über Sie. Im Hintergrund arbeitet die KI so nicht: keine Vorschläge nach der Übernahme, kein Autopilot."));
  const ollamaTeil = el("div", { style: { display: "grid", gap: "10px" } },
    el("label", {}, "Ollama-Adresse", feld("ollama_url")),
    el("label", {}, "Modell", feld("ollama_modell", { placeholder: "z. B. qwen3:14b" })),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } }, "Läuft vollständig lokal. Ohne eigene Websuche: IndraNet sammelt Suchtreffer und Registerauszüge und legt sie dem Modell vor."));
  // Nur die API geht von IndraNet aus ins Netz; claude.ai läuft im Browser,
  // Ollama auf dem eigenen Rechner.
  const kiProxy = schalter("ki_ueber_proxy", "KI-Anfragen ebenfalls über Tor/Proxy leiten");
  const proxyTeil = el("label", {}, "Proxy-Adresse", feld("proxy_url", { placeholder: "socks5://127.0.0.1:1080 oder http://host:port" }));

  const quellenTafel = el("div", { class: "tafel" },
    el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⌗"), "Datenquellen mit Zugang"),
    el("label", {}, "OpenSanctions-API-Schlüssel ", el("span", { class: "gedaempft" }, `(geschützt: ${e.schluessel_schutz})`), osSchluessel),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } },
      "Sanktionslisten, politisch exponierte Personen (PEP), Fahndungen und organisierte Kriminalität aus über 250 amtlichen Quellen. Schlüssel unter opensanctions.org/api — für journalistische und gemeinnützige Arbeit kostenlos."),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } },
      "Daten unter CC BY-NC 4.0: Quelle OpenSanctions nennen, nur nicht-kommerziell. Kommerzielle Redaktionen brauchen eine Lizenz von OpenSanctions. Ohne Schlüssel bleiben die übrigen Quellen (GLEIF, Wikidata, Wikipedia u. a.) nutzbar."),
    el("label", { style: { marginTop: "6px" } }, "Global-Fishing-Watch-Token (Schiffe) ", el("span", { class: "gedaempft" }, `(geschützt: ${e.schluessel_schutz})`), gfwSchluessel),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } },
      "Schiffe über Name, IMO oder MMSI: Identität, Flagge, Eigner und Typ aus über 40 Registern und AIS. Token unter globalfishingwatch.org/our-apis/tokens — für Recherche und gemeinnützige Arbeit kostenlos; Global Fishing Watch als Quelle nennen. Flugzeuge (ADS-B über adsb.lol) brauchen keinen Zugang."),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } },
      "Flug- und Schiffssuche gelten Fahrzeugen über ihre Kennung (Kennzeichen, Hex, Rufzeichen, IMO, MMSI) und deren Haltern — nicht dem Aufenthalt einer Person."));
  const torStatus = el("dl", { class: "zustandsfeld" });
  const BRUECKEN = [["auto", "Automatisch — direkt, bei Störung obfs4"], ["aus", "Keine Brücken (direkt)"],
    ["obfs4", "obfs4"], ["snowflake", "Snowflake"], ["meek", "meek (Azure)"], ["eigene", "Eigene Brücken"]];
  const brueckenWahl = el("select", { onchange: (ev) => { w.tor_bruecken = ev.target.value; eigeneTeil.hidden = w.tor_bruecken !== "eigene"; } });
  const eigeneTeil = el("label", {}, "Brückenzeilen (eine je Zeile, von bridges.torproject.org)",
    el("textarea", { rows: 3, class: "mono", placeholder: "obfs4 192.0.2.1:443 FINGERABDRUCK cert=… iat-mode=0",
      oninput: (ev) => { w.tor_eigene_bruecken = ev.target.value; } }, e.tor_eigene_bruecken || ""));
  eigeneTeil.hidden = e.tor_bruecken !== "eigene";
  const torTeil = el("div", { style: { display: "grid", gap: "10px" } }, torStatus,
    el("label", {}, "Brücken", brueckenWahl),
    eigeneTeil,
    el("label", {}, "Pfad zu tor.exe (leer = automatisch suchen)", feld("tor_pfad", { placeholder: "…\\Tor Browser\\Browser\\TorBrowser\\Tor\\tor.exe" })),
    el("div", { style: { display: "flex", gap: "8px", flexWrap: "wrap" } },
      el("button", { class: "knopf klein", onclick: async () => { try { await api.post("einstellungen", w); await api.post("tor/starten", { neu: true }); melden("Tor startet …"); torZeigen(); } catch (er) { fehler(er); } } }, "Tor (neu) starten"),
      el("button", { class: "knopf klein flach", onclick: async () => { await api.post("tor/stoppen"); torZeigen(); } }, "Stoppen")));
  const pruefErgebnis = el("div");

  const torZeigen = async () => {
    const t = (await api.get("status")).tor;
    // Nur Brückenarten anbieten, deren Programme vorhanden sind
    if (!brueckenWahl.options.length) brueckenWahl.append(...BRUECKEN
      .filter(([k]) => ["auto", "aus", "eigene"].includes(k) || t.brueckenarten.includes(k))
      .map(([k, text]) => el("option", { value: k, selected: e.tor_bruecken === k }, text)));
    brueckenWahl.disabled = !t.brueckenarten.length;
    leeren(torStatus).append(...[
      el("dt", {}, "Tor"), el("dd", {}, t.gefunden ? t.pfad : el("span", { style: { color: "var(--umstritten)" } }, "nicht gefunden")),
      el("dt", {}, "Zustand"), el("dd", {}, t.bereit ? el("span", { style: { color: "var(--bestaetigt)" } }, "verbunden") : t.laeuft ? `startet … ${t.fortschritt} %` : "aus"),
      el("dt", {}, "Brücke"), el("dd", {}, t.bruecken || (t.laeuft ? "keine (direkt)" : "—")),
      el("dt", {}, "Onion"), el("dd", {}, t.onion || "—"),
      t.hinweis ? el("dt", {}, "Hinweis") : null, t.hinweis ? el("dd", { style: { fontFamily: "var(--text)", color: "var(--einfach)" } }, t.hinweis) : null,
      t.fehler ? el("dt", {}, "Fehler") : null, t.fehler ? el("dd", { style: { color: "var(--umstritten)" } }, t.fehler) : null].filter(Boolean));
    if (!t.gefunden) torStatus.append(el("dt", {}, "Hilfe"), el("dd", { style: { fontFamily: "var(--text)" } },
      "Tor Browser installieren (torproject.org) — IndraNet findet dessen tor.exe selbst. Oder das »Tor Expert Bundle« in den Ordner tor neben IndraNet entpacken."));
    if (t.laeuft && !t.bereit) setTimeout(torZeigen, 2000);
  };

  function sichtbarkeit() {
    claudeTeil.hidden = w.ki_anbieter !== "claude";
    chatTeil.hidden = w.ki_anbieter !== "chat";
    kiProxy.hidden = w.ki_anbieter !== "claude";
    ollamaTeil.hidden = w.ki_anbieter !== "ollama";
    proxyTeil.hidden = w.netzweg !== "proxy";
    torTeil.hidden = w.netzweg !== "tor";
  }

  const speichern = async () => {
    const daten = { ...w };
    delete daten.modelle;
    if (schluessel.value.trim()) daten.claude_schluessel = schluessel.value.trim(); else delete daten.claude_schluessel;
    if (osSchluessel.value.trim()) daten.opensanctions_schluessel = osSchluessel.value.trim(); else delete daten.opensanctions_schluessel;
    if (gfwSchluessel.value.trim()) daten.gfw_schluessel = gfwSchluessel.value.trim(); else delete daten.gfw_schluessel;
    try {
      await api.post("einstellungen", daten);
      schluessel.value = "";
      melden("Einstellungen gespeichert.");
      senden("status-laden");
      fertig?.();
    } catch (er) { fehler(er); }
  };

  const form = el("div", { class: fertig ? "" : "seiteninhalt", style: { display: "grid", gap: "16px" } },
    el("div", { class: "kopfzeile" }, el("div", {}, el("h2", {}, "System"),
      el("p", {}, "Gilt für alle Projekte auf diesem Rechner. Datenordner: ", el("span", { class: "mono" }, e.datenordner))),
      el("div", { class: "rechts" }, fertig ? el("button", { class: "knopf flach", onclick: fertig }, "Schließen") : null,
        el("button", { class: "knopf haupt", onclick: speichern }, "Speichern"))),
    el("div", { class: "einst-raster" },
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "KI"), "Künstliche Intelligenz"),
        radio("ki_anbieter", [["claude", "Claude-API"], ["chat", "claude.ai (Abo)"], ["ollama", "Lokal"], ["aus", "Aus"]]), claudeTeil, chatTeil, ollamaTeil,
        kiProxy),
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "IP"), "Netzweg & Verschleierung"),
        radio("netzweg", [["direkt", "Direkt"], ["tor", "Tor"], ["proxy", "Proxy"]]),
        el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } }, "Bestimmt, über welchen Weg Websuche, Register und Quellseiten abgerufen werden. Bei Tor oder Proxy gilt: kein stiller Rückfall auf die direkte Verbindung."),
        torTeil, proxyTeil,
        el("button", { class: "knopf klein", onclick: async () => {
          leeren(pruefErgebnis).append(el("span", { class: "gedaempft" }, "Prüfe …"));
          try { await api.post("einstellungen", { netzweg: w.netzweg, proxy_url: w.proxy_url }); } catch { /* weiter prüfen */ }
          const r = await api.post("netzweg/pruefen");
          leeren(pruefErgebnis).append(el("div", { class: `hinweis ${r.ok && (r.ist_tor || w.netzweg !== "tor") ? "gut" : "schlecht"}` },
            r.ok ? `Nach außen sichtbar als ${r.ip}${r.ist_tor ? " — ein Tor-Ausgang." : w.netzweg === "direkt" ? " — das ist Ihre eigene Adresse." : "."}` : `Prüfung fehlgeschlagen: ${r.fehler}`));
        } }, "Verbindung prüfen"), pruefErgebnis),
      quellenTafel,
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⚙"), "Verhalten"),
        schalter("belege_sichern", "Quellseiten beim Übernehmen verschlüsselt sichern"),
        schalter("autopilot", "Autopilot: Folgerecherchen nach jeder Übernahme selbständig starten"),
        el("label", {}, "Höchstens so viele Folgerecherchen je Übernahme", feld("autopilot_max", { type: "number", min: 1, max: 10 })),
        schalter("netzwerk_dienst", "Für Recherche-Netzwerke erreichbar sein (.onion-Dienst)"),
        el("label", {}, "Erscheinungsbild", el("select", { onchange: (ev) => { w.thema = ev.target.value; document.documentElement.dataset.thema = ev.target.value; } },
          [["lagezentrale", "Lagezentrale (dunkel)"], ["archiv", "Archiv (hell)"]].map(([k, t]) => el("option", { value: k, selected: e.thema === k }, t))))),
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "§"), "Verantwortung"),
        el("p", { style: { margin: 0, fontSize: "13px" } }, "IndraNet verarbeitet öffentlich zugängliche Daten — auch über Menschen. Für Journalistinnen gilt das Medienprivileg (Art. 85 DSGVO, Landespressegesetze), für alle die Sorgfaltspflichten des Pressekodex: Unschuldsvermutung, Verdachtsberichterstattung nur mit Mindestbestand an Beweistatsachen, Schutz Unbeteiligter."),
        el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } }, "Ein Treffer in einem Leak oder Register ist kein Beleg für eine Straftat. Die KI irrt — deshalb geht nichts ohne Ihre Prüfung in den Bestand."))));
  sichtbarkeit();
  torZeigen();
  document.documentElement.dataset.thema = e.thema || "lagezentrale";
  return form;
}
