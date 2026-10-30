"""
IndraNet — Hintergrundaufträge
===============================

Eine Recherche über Tor mit zwanzig Websuchen dauert Minuten. Sie läuft
deshalb als Auftrag im Hintergrund; die Oberfläche fragt den Stand ab und
zeigt live, was die KI gerade sucht.

Die Abläufe selbst stehen unten: Recherche, Datei, Übernahme, Lagebild,
Verknüpfen. Jeder Ablauf schreibt nur in den Prüfkorb oder in die eigenen
Tabellen — in den Bestand geht nur, was ein Mensch übernommen hat.

VERKNÜPFEN IM HINTERGRUND
-------------------------
Nach jeder Übernahme schaut die KI auf den gewachsenen Bestand und schlägt
Folgerecherchen und vermutete Verbindungen vor. Mit eingeschaltetem
Autopilot startet IndraNet die besten Folgerecherchen selbst — ihre
Ergebnisse landen wie alles andere im Prüfkorb.

BRÜCKE ZU CLAUDE.AI
-------------------
Mit KI-Anbieter "chat" endet ein Ablauf nicht mit einem Befund, sondern
mit einem Auftrag zum Kopieren (Ergebnis mit "bruecke": True, "offen":
True). Die eingefügte Antwort liest bruecke_einlesen() — erst dann entsteht
der Fund bzw. das Lagebild.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from policy import Rolle, Stufe


class Auftrag:
    def __init__(self, art: str, titel: str, projekt: str):
        self.id = uuid.uuid4().hex[:12]
        self.art = art
        self.titel = titel
        self.projekt = projekt
        self.status = "wartet"
        self.meldungen: list[tuple[float, str]] = []
        self.ergebnis = None
        self.fehler: str | None = None
        self.start = time.time()
        self.ende: float | None = None

    def melden(self, text: str) -> None:
        self.meldungen.append((time.time(), str(text)[:300]))
        del self.meldungen[:-60]

    def als_dict(self) -> dict:
        return {"id": self.id, "art": self.art, "titel": self.titel,
                "projekt": self.projekt, "status": self.status,
                "meldungen": [{"ts": t, "text": m} for t, m in self.meldungen],
                "ergebnis": self.ergebnis, "fehler": self.fehler,
                "start": self.start, "ende": self.ende}


class Auftraege:
    def __init__(self, threads: int = 3):
        self.pool = ThreadPoolExecutor(max_workers=threads,
                                       thread_name_prefix="indra-auftrag")
        self.alle: dict[str, Auftrag] = {}
        self._lock = threading.Lock()

    def starten(self, art: str, titel: str, projekt: str, funktion) -> Auftrag:
        a = Auftrag(art, titel, projekt)
        with self._lock:
            self.alle[a.id] = a
            # alte, erledigte Aufträge nicht ewig mitschleppen
            erledigt = [x for x in self.alle.values() if x.ende]
            for x in sorted(erledigt, key=lambda x: x.ende)[:-40]:
                self.alle.pop(x.id, None)

        def lauf():
            a.status = "laeuft"
            try:
                a.ergebnis = funktion(a.melden)
                a.status = "fertig"
            except Exception as e:                          # noqa: BLE001
                a.fehler = str(e) or e.__class__.__name__
                a.status = "fehler"
                a.melden("Fehler: " + a.fehler)
                traceback.print_exc()
            finally:
                a.ende = time.time()

        self.pool.submit(lauf)
        return a

    def liste(self, projekt: str | None = None) -> list[dict]:
        with self._lock:
            xs = [a for a in self.alle.values()
                  if projekt is None or a.projekt == projekt]
        return [a.als_dict() for a in sorted(xs, key=lambda a: -a.start)]

    def get(self, aid: str) -> Auftrag | None:
        return self.alle.get(aid)

    def laufend(self, projekt: str) -> int:
        return sum(1 for a in self.alle.values()
                   if a.projekt == projekt and a.status in ("wartet", "laeuft"))


# =============================================================== Abläufe
def recherche(projekt, ki, auftrag: str, fokus: str = ""):
    def lauf(melden):
        melden(f"Recherche gestartet: {auftrag}")
        projekt.verlauf_eintragen("recherche", auftrag)
        befund = ki.recherche(auftrag, projekt.kontext(fokus), melden)
        d = befund.als_dict()
        n = len(d["aussagen"])
        fid = projekt.fund_anlegen(art="web", anfrage=auftrag, befund=d,
                                   herkunft=befund.modell, titel=auftrag)
        melden(f"Fertig: {n} Aussagen, {len(d['entitaeten'])} Entitäten, "
               f"{len(d['quellen'])} Quellen → Prüfkorb")
        return {"fund_id": fid, "aussagen": n}
    return lauf


def bruecke_recherche(projekt, netzweg, auftrag: str, fokus: str = ""):
    """Recherche über claude.ai: Register vorab abfragen, Auftrag schreiben."""
    def lauf(melden):
        import bruecke
        melden(f"Bereite den Auftrag für claude.ai vor: {auftrag}")
        projekt.verlauf_eintragen("recherche", auftrag, "über claude.ai")
        material = bruecke.registerauszuege(netzweg, auftrag, melden)
        text = bruecke.auftrag_recherche(auftrag, projekt.kontext(fokus),
                                         material)
        melden("Auftrag bereit — kopieren, in claude.ai ausführen, Antwort "
               "einfügen.")
        return {"bruecke": True, "offen": True, "art": "web",
                "anfrage": auftrag, "auftrag_text": text}
    return lauf


def bruecke_einlesen(projekt, auftrag: Auftrag, antwort: str) -> dict:
    """Liest die aus claude.ai eingefügte Antwort und legt Fund bzw.
    Lagebild an. Läuft direkt, nicht im Hintergrund — das Ergebnis soll die
    Rechercheurin sofort sehen, auch einen Lesefehler."""
    import bruecke
    e = auftrag.ergebnis or {}
    if not e.get("bruecke"):
        raise bruecke.BrueckeFehler("Dieser Auftrag läuft nicht über claude.ai.")
    if not e.get("offen"):
        raise bruecke.BrueckeFehler("Die Antwort zu diesem Auftrag ist schon "
                                    "übernommen.")
    if e["art"] == "lagebild":
        daten = bruecke.lagebild_lesen(antwort)
        lid = projekt.lagebild_speichern(e.get("frage", ""), daten)
        projekt.sichern()
        raus = {"lagebild_id": lid, "titel": daten["titel"]}
        auftrag.melden(f"Lagebild aus claude.ai gespeichert: {daten['titel']}")
    else:
        datei = e["art"] == "datei"
        d, verworfen = bruecke.befund_lesen(antwort, datei=datei)
        if datei:
            d["quellen"] = [{"url": e["anfrage"], "titel": e["anfrage"],
                             "herausgeber": "eigene Datei", "art": "datei",
                             "datum": ""}]
        fid = projekt.fund_anlegen(
            art=e["art"], anfrage=e["anfrage"], befund=d,
            herkunft=bruecke.HERKUNFT, doc_id=e.get("doc_id"),
            titel=(f"Datei: {e['anfrage']}" if datei else e["anfrage"]))
        raus = {"fund_id": fid, "aussagen": len(d["aussagen"]),
                "verworfen": verworfen}
        auftrag.melden(f"Antwort aus claude.ai: {len(d['aussagen'])} Aussagen "
                       f"→ Prüfkorb" + (f", {verworfen} verworfen (ohne "
                                        "Beleg oder Prädikat nicht in der "
                                        "Liste)" if verworfen else ""))
    auftrag.ergebnis = {**e, **raus, "offen": False, "auftrag_text": None}
    return raus


def register(projekt, netzweg, quelle: str, begriff: str):
    """Direkter Registerabruf ohne KI. Liefert Rohtreffer zum Ansehen."""
    def lauf(melden):
        import quellen_offen
        melden(f"{quelle}: {begriff}")
        projekt.verlauf_eintragen("register", f"{quelle}: {begriff}")
        r = quellen_offen.abfragen(netzweg, quelle, begriff)
        melden(f"{len(r['treffer'])} Treffer")
        return r
    return lauf


def datei(projekt, ki, roh: bytes, dateiname: str, medientyp: str,
          stufe: Stufe, benutzer: str, analysieren: bool = True):
    def lauf(melden):
        melden(f"Lege {dateiname} verschlüsselt ab …")
        with projekt.lock:
            dok = projekt.pod.dokument_anlegen(
                art="datei", titel=dateiname, quelle=f"Datei: {dateiname}",
                stufe=stufe, erfasst_von=benutzer, datei=roh,
                dateiname=dateiname, typ=medientyp)
            projekt.geaendert = True
        projekt.verlauf_eintragen("datei", dateiname,
                                  dok.get("text_hinweis", ""))
        melden(f"Abgelegt ({dok.get('text_abschnitte', 0)} Textabschnitte). "
               + (dok.get("text_hinweis") or ""))
        if not analysieren:
            return {"doc_id": dok["doc_id"]}
        abschnitte = []
        try:
            with projekt.lock:
                e = projekt.pod.beleg_text(dok["doc_id"], Rolle.ADMIN)
            abschnitte = [{"fundstelle": a.fundstelle, "text": a.text}
                          for a in e.abschnitte]
        except Exception:                                   # noqa: BLE001
            pass
        if ki.anbieter == "chat":
            import bruecke
            text, anhaengen = bruecke.auftrag_datei(dateiname, abschnitte,
                                                    projekt.kontext())
            melden("Auftrag für claude.ai bereit"
                   + (" — Datei dort anhängen." if anhaengen else "."))
            return {"doc_id": dok["doc_id"], "bruecke": True, "offen": True,
                    "art": "datei", "anfrage": dateiname,
                    "auftrag_text": text, "anhaengen": anhaengen}
        befund = ki.datei_analysieren(dateiname, abschnitte,
                                      projekt.kontext(), roh=roh,
                                      medientyp=medientyp, fortschritt=melden)
        d = befund.als_dict()
        # Quelle der Aussagen ist die Datei selbst
        d["quellen"] = [{"url": dateiname, "titel": dateiname,
                         "herausgeber": "eigene Datei", "art": "datei",
                         "datum": ""}]
        fid = projekt.fund_anlegen(art="datei", anfrage=dateiname, befund=d,
                                   herkunft=befund.modell, doc_id=dok["doc_id"],
                                   titel=f"Datei: {dateiname}")
        melden(f"Fertig: {len(d['aussagen'])} Aussagen → Prüfkorb")
        return {"fund_id": fid, "doc_id": dok["doc_id"],
                "aussagen": len(d["aussagen"])}
    return lauf


def uebernehmen(projekt, fund_id: str, auswahl: dict, benutzer: str, netzweg,
                nachher=None):
    def lauf(melden):
        melden("Übernehme in den Bestand …")
        r = projekt.fund_uebernehmen(fund_id, auswahl, pruefer=benutzer,
                                     netzweg=netzweg, fortschritt=melden)
        projekt.sichern()
        melden(f"{r['aussagen']} Aussagen, {r['entitaeten']} Entitäten, "
               f"{r['orte']} Orte übernommen und gesichert.")
        if nachher:
            nachher()
        return r
    return lauf


def lagebild(projekt, ki, frage: str):
    def lauf(melden):
        bestand = projekt.bestand_text()
        if bestand.strip() == "FAKTEN:":
            raise RuntimeError("Der Bestand ist noch leer — erst Befunde "
                               "übernehmen, dann analysieren.")
        projekt.verlauf_eintragen("lagebild", frage or "Gesamtlage")
        if ki.anbieter == "chat":
            import bruecke
            melden("Auftrag für claude.ai bereit.")
            return {"bruecke": True, "offen": True, "art": "lagebild",
                    "frage": frage, "auftrag_text": bruecke.auftrag_lagebild(
                        frage, bestand, projekt.kontext())}
        daten = ki.analysieren(frage, bestand, projekt.kontext(), melden)
        lid = projekt.lagebild_speichern(frage, daten)
        projekt.sichern()
        melden("Lagebild gespeichert.")
        return {"lagebild_id": lid, "titel": daten.get("titel")}
    return lauf


def verknuepfen(projekt, ki, auftraege: "Auftraege", einstellungen):
    """Vorschläge nach einer Übernahme; startet im Autopilot Recherchen."""
    def lauf(melden):
        melden("KI sucht Anschlussstellen im Bestand …")
        daten = ki.vorschlagen(projekt.bestand_text(), projekt.kontext())
        n = projekt.vorschlaege_speichern(daten)
        melden(f"{n} neue Vorschläge.")
        gestartet = 0
        if einstellungen.get("autopilot"):
            for r in daten.get("recherchen", [])[:int(
                    einstellungen.get("autopilot_max") or 3)]:
                auftraege.starten("recherche", f"Autopilot: {r['auftrag']}",
                                  projekt.name,
                                  recherche(projekt, ki, r["auftrag"]))
                gestartet += 1
            melden(f"Autopilot: {gestartet} Folgerecherchen gestartet.")
        return {"vorschlaege": n, "autopilot": gestartet}
    return lauf


def abgleich(netzwerke, netz_id: str | None = None):
    def lauf(melden):
        melden("Gleiche mit den Netzwerkteilnehmern ab …")
        r = netzwerke.abgleichen(netz_id)
        melden(f"{r['erreicht']} erreicht, {r['neu']} neue Freigaben, "
               f"{r['fehler']} nicht erreichbar.")
        return r
    return lauf
