// IndraNet — Recherche-Netzwerke: Kolleginnen weltweit einladen, geprüfte
// Funde teilen, Überschneidungen erkennen. Verbindung über Tor, ohne Server.

import * as api from "./api.js";
import { el, leeren, fehler, melden, praed, lageAbz, zeit, seit, dialog, kopieren, domain, externOeffnen } from "./ui.js";
import { S, an, senden } from "./zustand.js";

export const NETZWERKE = {
  abmelden: [],
  async zeigen(main, netzId) {
    let daten;
    try { daten = await api.get("netzwerke"); } catch (e) { return fehler(e); }
    const status = S.status || {};
    const adresse = daten.adresse;
    const wurzel = el("div", { class: "seiteninhalt" });
    main.append(wurzel);

    const torHinweis = adresse
      ? el("div", { class: "hinweis gut" }, "Ihre Installation ist für Netzwerkteilnehmer erreichbar unter ", el("span", { class: "mono" }, adresse), ". Niemand im Netz erfährt Ihre IP-Adresse.")
      : el("div", { class: "hinweis" }, status.tor?.laeuft
        ? `Tor startet (${status.tor.fortschritt} %) — Ihre .onion-Adresse erscheint, sobald die Verbindung steht.`
        : [el("b", {}, "Noch keine Netzwerkadresse. "), "Für Recherche-Netzwerke braucht IndraNet Tor: Unter »System« den Netzweg auf Tor stellen. Tor wird gesucht (Tor Browser oder Tor Expert Bundle) und mitgestartet."],
      !status.tor?.laeuft ? el("div", { style: { marginTop: "8px" } }, el("button", { class: "knopf klein", onclick: () => senden("zeige", { ansicht: "einstellungen" }) }, "Zu den Einstellungen")) : null);

    wurzel.append(el("div", { class: "kopfzeile" },
      el("div", {}, el("h2", {}, "Recherche-Netzwerke"),
        el("p", {}, "Jede Teilnehmerin arbeitet im eigenen, verschlüsselten Projekt und gibt geprüfte Funde gezielt frei. Freigaben sind signiert, kommen mit Quelle und landen bei den anderen im Prüfkorb — die Quelle wird dort selbst abgerufen, bevor etwas in den Bestand geht.")),
      el("div", { class: "rechts" },
        el("button", { class: "knopf", onclick: beitretenDialog }, "Mit Code beitreten"),
        el("button", { class: "knopf haupt", onclick: anlegenDialog }, "Netzwerk gründen"))),
      torHinweis,
      el("div", { class: "kopfzeile" }, el("span", { class: "etikett" }, "Ihr Name im Netz"),
        el("input", { value: daten.name, style: { width: "260px" }, onchange: async (ev) => {
          try { await api.post("projekt/info", { netzname: ev.target.value }); melden("Name gespeichert — gilt für künftige Einladungen und Freigaben."); } catch (e) { fehler(e); }
        } })));

    if (!daten.netzwerke.length) {
      wurzel.append(el("div", { class: "leer" }, el("b", {}, "Noch in keinem Netzwerk"),
        "Gründen Sie ein Netzwerk und laden Sie Kolleginnen per Code ein — oder treten Sie mit einem Code bei, den Sie erhalten haben."));
      return;
    }
    const raster = el("div", { class: "zweispaltig", style: { height: "auto", minHeight: "60vh", border: "1px solid var(--linie)", borderRadius: "var(--r)" } });
    const liste = el("div", { class: "spalte-liste" });
    const detail = el("div", { class: "spalte-detail" });
    raster.append(liste, detail);
    wurzel.append(raster);
    for (const n of daten.netzwerke) {
      liste.append(el("div", { class: "fund-karte", "data-id": n.netz_id, onclick: () => waehlen(n.netz_id) },
        el("div", { class: "titel" }, "⟁ ", n.name),
        el("div", { class: "meta" }, el("span", {}, `${n.mitglieder} Teilnehmer`), el("span", {}, `${n.freigaben} Freigaben`),
          n.neu ? el("span", { style: { color: "var(--einfach)" } }, `${n.neu} neu`) : null),
        el("div", { class: "meta" }, el("span", {}, `abgeglichen ${seit(n.zuletzt_abgleich)}`))));
    }
    const waehlen = async (id) => {
      liste.querySelectorAll(".fund-karte").forEach(k => k.classList.toggle("aktiv", k.dataset.id === id));
      leeren(detail).append(el("div", { class: "seiteninhalt" }, "Lade …"));
      try { leeren(detail).append(await netzDetail(await api.get("netzwerk", { id }), () => waehlen(id))); } catch (e) { fehler(e); }
    };
    waehlen(netzId || daten.netzwerke[0].netz_id);
    NETZWERKE.abmelden.push(an("netzwerke", () => waehlen(liste.querySelector(".aktiv")?.dataset.id || daten.netzwerke[0].netz_id)));
  },
  verlassen() { NETZWERKE.abmelden.forEach(f => f()); NETZWERKE.abmelden = []; },
};

async function netzDetail(n, neu) {
  // Überschneidung: Kommt eine Entität der Freigabe auch im eigenen Bestand vor?
  const eigen = await api.get("netz");
  const namen = new Set(eigen.knoten.map(k => k.name.toLowerCase()));
  const gewaehlt = new Set();
  const fremde = n.freigaben.filter(f => !f.eigen);
  const ueber = (f) => namen.has(f.inhalt.subjekt.toLowerCase()) || namen.has(f.inhalt.objekt.toLowerCase());

  const freigabe = (f) => el("div", { class: `freigabe${!f.eigen && ueber(f) ? " ueberschneidung" : ""}` },
    el("div", { class: "autor" },
      !f.eigen && !f.uebernommen ? el("input", { type: "checkbox", onchange: (ev) => ev.target.checked ? gewaehlt.add(f.item_id) : gewaehlt.delete(f.item_id) }) : null,
      el("b", { style: { color: f.eigen ? "var(--akzent)" : "var(--tinte)" } }, f.eigen ? "Sie" : f.autor_name),
      el("span", {}, zeit(f.ts)), f.uebernommen && !f.eigen ? el("span", { style: { color: "var(--bestaetigt)" } }, "im Prüfkorb") : null,
      !f.eigen && ueber(f) ? el("span", { style: { color: "var(--einfach)", marginLeft: "auto" } }, "◆ Überschneidung mit Ihrem Bestand") : null),
    el("div", {}, el("b", {}, f.inhalt.subjekt), " ", el("span", { class: "mono", style: { color: "var(--akzent)" } }, praed(f.inhalt.praedikat)), " ", el("b", {}, f.inhalt.objekt), " ", lageAbz(f.inhalt.beleglage)),
    f.inhalt.kommentar ? el("div", { class: "gedaempft", style: { fontSize: "12.5px" } }, `»${f.inhalt.kommentar}«`) : null,
    el("div", { class: "mono", style: { fontSize: "11px", display: "flex", gap: "10px", flexWrap: "wrap" } },
      f.inhalt.belege.map(b => el("a", { href: "#", title: b.url, onclick: (ev) => { ev.preventDefault(); externOeffnen(b.url, S.torAktiv); } }, `↗ ${b.herausgeber || domain(b.url)}`))));

  return el("div", { class: "seiteninhalt" },
    el("div", { class: "kopfzeile" },
      el("div", {}, el("h2", {}, n.name), n.beschreibung ? el("p", {}, n.beschreibung) : null,
        el("p", { class: "mono" }, `gegründet ${zeit(n.ts)} · zuletzt abgeglichen ${seit(n.zuletzt_abgleich)}`)),
      el("div", { class: "rechts" },
        el("button", { class: "knopf", onclick: async () => { try { await api.post("netzwerk/abgleichen", { netz_id: n.netz_id }); melden("Abgleich läuft …"); } catch (e) { fehler(e); } } }, "⟳ Abgleichen"),
        el("button", { class: "knopf haupt", onclick: () => einladenDialog(n) }, "Einladen"))),
    el("div", { class: "raster-2" },
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "◉"), `Teilnehmer · ${n.mitglieder.length}`),
        n.mitglieder.map(m => el("div", { class: "mitglied" },
          el("i", { class: `punkt ${m.ich ? "gut" : m.fehler ? "schlecht" : m.zuletzt_gesehen ? "gut" : "warn"}` }),
          el("div", {}, el("b", {}, m.name || m.pod_id, m.ich ? " (Sie)" : ""), el("div", { class: "adresse", title: m.adresse }, m.adresse || "keine Adresse")),
          el("span", { class: "rechts", title: m.fehler || "" }, m.ich ? "" : m.fehler ? "nicht erreichbar" : seit(m.zuletzt_gesehen))))),
      el("div", { class: "tafel" }, el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "i"), "So funktioniert es"),
        el("ul", { style: { margin: 0, paddingLeft: "18px", fontSize: "12.5px", display: "grid", gap: "5px" } },
          el("li", {}, "Freigeben: im »Bestand« Fakten anhaken → »Im Netzwerk freigeben«."),
          el("li", {}, "Geteilt werden nur Fakten mit öffentlichen Quellen, signiert mit Ihrem Projektschlüssel."),
          el("li", {}, "IndraNet gleicht alle drei Minuten ab. Wer offline ist, bekommt Freigaben über die anderen nachgereicht."),
          el("li", {}, "Gelb markierte Freigaben berühren Entitäten aus Ihrem eigenen Bestand.")))),
    el("div", { class: "tafel" },
      el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⟁"), `Freigaben · ${n.freigaben.length}`,
        fremde.some(f => !f.uebernommen) ? el("span", { class: "rechts" }, el("button", { class: "knopf klein haupt", onclick: async () => {
          if (!gewaehlt.size) return melden("Bitte Freigaben ankreuzen.", "warn");
          try { const r = await api.post("netzwerk/uebernehmen", { netz_id: n.netz_id, item_ids: [...gewaehlt] }); melden("In den Prüfkorb gelegt."); senden("stats-laden"); senden("zeige", { ansicht: "pruefkorb", param: r.fund_id }); } catch (e) { fehler(e); }
        } }, "Gewählte in den Prüfkorb")) : null),
      n.freigaben.length ? n.freigaben.map(freigabe) : el("div", { class: "leer" }, "Noch keine Freigaben in diesem Netzwerk.")));
}

function anlegenDialog() {
  const name = el("input", { placeholder: "z. B. Hafen-Konsortium 2026", maxlength: 80 });
  const besch = el("textarea", { rows: 2, placeholder: "Worum geht es? (sehen nur Eingeladene)" });
  const d = dialog([el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⟁"), "Netzwerk gründen"),
    el("label", {}, "Name", name), el("label", {}, "Beschreibung", besch),
    el("div", { class: "knopfreihe" }, el("button", { class: "knopf flach", onclick: () => d.schliessen() }, "Abbrechen"),
      el("button", { class: "knopf haupt", onclick: async () => {
        try { const n = await api.post("netzwerk/anlegen", { name: name.value, beschreibung: besch.value }); d.schliessen(); melden("Netzwerk gegründet."); senden("zeige", { ansicht: "netzwerke", param: n.netz_id }); } catch (e) { fehler(e); }
      } }, "Gründen"))]);
}

async function einladenDialog(n) {
  let r;
  try { r = await api.post("netzwerk/einladen", { netz_id: n.netz_id }); } catch (e) { return fehler(e); }
  const d = dialog([el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "✉"), `Einladung in »${n.name}«`),
    el("p", { style: { margin: 0, fontSize: "13px" } }, "Geben Sie diesen Code über einen sicheren Kanal weiter (Signal, persönlich). Er gilt einmal und 48 Stunden. Wer ihn hat, kann beitreten."),
    el("div", { class: "code-feld" }, r.code),
    el("div", { class: "knopfreihe" }, el("button", { class: "knopf", onclick: () => kopieren(r.code) }, "Kopieren"),
      el("button", { class: "knopf haupt", onclick: () => d.schliessen() }, "Fertig"))]);
}

function beitretenDialog() {
  const code = el("textarea", { rows: 4, placeholder: "INDRA1-…", class: "mono" });
  const d = dialog([el("div", { class: "tafel-kopf" }, el("span", { class: "ecke" }, "⟁"), "Einem Netzwerk beitreten"),
    el("label", {}, "Einladungscode", code),
    el("p", { class: "gedaempft", style: { margin: 0, fontSize: "12px" } }, "IndraNet meldet sich über Tor bei der einladenden Person. Dafür muss Tor laufen und die Gegenseite IndraNet mit geöffnetem Projekt betreiben."),
    el("div", { class: "knopfreihe" }, el("button", { class: "knopf flach", onclick: () => d.schliessen() }, "Abbrechen"),
      el("button", { class: "knopf haupt", onclick: async (ev) => {
        ev.target.disabled = true; ev.target.textContent = "Verbinde …";
        try { const n = await api.post("netzwerk/beitreten", { code: code.value }); d.schliessen(); melden(`Beigetreten: ${n.name}`); senden("zeige", { ansicht: "netzwerke", param: n.netz_id }); }
        catch (e) { fehler(e); ev.target.disabled = false; ev.target.textContent = "Beitreten"; }
      } }, "Beitreten"))]);
}
