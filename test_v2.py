"""
IndraNet 2 — Tests der neuen Teile
===================================

    python test_v2.py

Prüft ohne Netz und ohne KI-Schlüssel:
  1  Befund-Normalisierung (Aussagen ohne Beleg fallen weg)
  2  Projekt: Prüfkorb → Übernahme → Beleglage, Widerspruch, Karte
  3  Verschlüsselung: wieder öffnen, falsche Passphrase
  4  Netzwerk: gründen, einladen, beitreten, freigeben, abgleichen,
     gefälschte Freigabe wird verworfen, interne Belege bleiben zurück
  5  Netzweg: Tor gewählt, aber nicht verbunden → kein Abruf
  6  Ortstabelle
  7  Brücke zu claude.ai: Auftrag schreiben, Antwort einlesen (Recherche,
     Lagebild, Datei), kaputte und doppelte Antworten
  8  OpenSanctions-Connector: Antwort parsen, Themen übersetzen, Schlüssel
     im Kopf, fehlender Schlüssel sauber gemeldet
  9  Flug- (ADS-B) und Schiffs-Connector (AIS/Register): Objekt über Kennung,
     Position/Identität geparst, Notfall-Squawk, Token sauber geprüft
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ERGEBNIS = {"ok": 0, "fehler": 0}


def pruefe(bedingung: bool, text: str, info="") -> None:
    if bedingung:
        ERGEBNIS["ok"] += 1
        print(f"  [ok]     {text}  {info}")
    else:
        ERGEBNIS["fehler"] += 1
        print(f"  [FEHLER] {text}  {info}")


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tmp = Path(tempfile.mkdtemp(prefix="indranet-test-"))
    os.environ["INDRANET_DATEN"] = str(tmp / "a")
    try:
        return _lauf(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _lauf(tmp: Path) -> int:
    import beispiel
    import ki
    from netz import Netzweg, NetzwegFehler
    from netzwerk import NetzwerkDienst, Netzwerke, NetzwerkFehler
    from projekt import ProjektFehler, Verwaltung

    print("1) Befund-Normalisierung")
    b = ki.normalisieren({"aussagen": [
        {"subjekt": "A", "praedikat": "director_of", "objekt": "B",
         "beleg": "https://x.example/1", "sicherheit": "hoch"},
        {"subjekt": "A", "praedikat": "director_of", "objekt": "B",
         "beleg": "", "sicherheit": "hoch"},
        {"subjekt": "A", "praedikat": "erfunden", "objekt": "B",
         "beleg": "https://x.example/1"},
        {"subjekt": "A", "praedikat": "paid_to", "objekt": "C",
         "beleg": "S. 4"}],
        "orte": [{"name": "X", "lat": 200, "lon": 0}]})
    pruefe(len(b["aussagen"]) == 1, "nur belegte Web-Aussage bleibt")
    pruefe(len(b["quellen"]) == 1, "Beleg-URL wird als Quelle ergänzt")
    pruefe(not b["orte"], "ungültige Koordinaten verworfen")
    d = ki.normalisieren({"aussagen": [{"subjekt": "A", "praedikat":
                                        "paid_to", "objekt": "C",
                                        "beleg": "S. 4"}]}, datei=True)
    pruefe(len(d["aussagen"]) == 1, "Datei: Fundstelle zählt als Beleg")

    print("2) Projekt und Prüfkorb")
    va = Verwaltung(tmp / "a")
    try:
        va.anlegen("kurz", "123")
        pruefe(False, "zu kurze Passphrase abgelehnt")
    except ProjektFehler:
        pruefe(True, "zu kurze Passphrase abgelehnt")
    pa = va.anlegen("Projekt A", "passphrase-alpha-1", zweck="Test")
    f1, f2 = beispiel.laden(pa)
    pruefe(len(pa.funde("offen")) == 2, "zwei Befunde im Prüfkorb")
    n_vor = pa.stats()["fakten"]
    r = pa.fund_uebernehmen(f1, {"aussagen": list(range(7)),
                                 "entitaeten": [0, 1, 2, 3],
                                 "orte": [0, 1, 2, 3],
                                 "belege_sichern": False}, pruefer="test")
    pruefe(r["aussagen"] == 7 and n_vor == 0, "Übernahme schreibt erst jetzt "
           "in den Bestand", r["status"])
    r = pa.fund_uebernehmen(f2, {"aussagen": [0, 1, 2, 3, 4, 5, 6],
                                 "orte": [0, 1], "belege_sichern": False,
                                 "bearbeitet": {"aussagen": {"1": {
                                     "subjekt": "Erik Svensson"}}}},
                            pruefer="test")
    pruefe(r["status"] == "teilweise", "Teilübernahme vermerkt")
    fakten = {(f["subjekt"], f["praedikat"], f["objekt"]): f
              for f in pa.alle_fakten()}
    holm = fakten.get(("Anders Holm", "director_of", "Mare Liberum Ltd."))
    pruefe(holm and holm["beleglage"] == "BESTAETIGT",
           "zwei unabhängige Quellen → BESTAETIGT")
    sitz = fakten.get(("Mare Liberum Ltd.", "registered_in", "Panama"))
    pruefe(sitz and sitz["beleglage"] == "UMSTRITTEN",
           "zwei Sitze → UMSTRITTEN")
    k = pa.karte()
    namen = {o["name"] for o in k["orte"]}
    pruefe({"Panama", "Oslo", "Tallinn", "Jersey"} <= namen, "Orte auf der Karte",
           ", ".join(sorted(namen)))
    pruefe(any(bg["praedikat"] == "paid_to" for bg in k["boegen"]),
           "Geldfluss als Bogen")
    netz = pa.netz()
    typen = {k["name"]: k["typ"] for k in netz["knoten"]}
    pruefe(typen.get("Anders Holm") == "PERSON" and typen.get("Oslo") == "PLACE",
           "Entitätstypen erkannt")
    text = pa.bestand_text()
    pruefe("UMSTRITTEN" in text and "Anders Holm" in text,
           "Bestand als Text für die KI")

    print("3) Verschlüsselung")
    pa.sichern()
    roh = (tmp / "a" / "projekte" / "Projekt-A.indra").read_bytes()
    pruefe(b"Mare Liberum" not in roh, "kein Klartext im Behälter")
    pa.schliessen()
    try:
        va.oeffnen("Projekt A", "falsch-falsch-falsch")
        pruefe(False, "falsche Passphrase abgewiesen")
    except ProjektFehler:
        pruefe(True, "falsche Passphrase abgewiesen")
    pa = va.oeffnen("Projekt A", "passphrase-alpha-1")
    pruefe(pa.stats()["fakten"] == len(fakten), "Bestand nach Wiederöffnen")

    print("4) Recherche-Netzwerk")
    from einstellungen import Einstellungen
    vb = Verwaltung(tmp / "b")
    pb = vb.anlegen("Projekt B", "passphrase-bravo-2")
    pb.info_setzen(netzname="Redaktion B")
    pa.info_setzen(netzname="Redaktion A")

    def dienst(port, wer):
        d = NetzwerkDienst(Einstellungen(tmp / wer), None, lambda: None)
        d.port = port
        d.eigene_adresse = lambda: f"http://127.0.0.1:{port}"
        return d
    da, db_ = dienst(18911, "a"), dienst(18912, "b")
    na, nb = Netzwerke(pa, da), Netzwerke(pb, db_)
    da.aktuell, db_.aktuell = (lambda: na), (lambda: nb)
    da.starten()
    db_.starten()
    try:
        netz_a = na.anlegen("Konsortium", "Test")
        code = na.einladen(netz_a["netz_id"])["code"]
        pruefe(code.startswith("INDRA1-"), "Einladungscode erzeugt")
        n_b = nb.beitreten(code)
        pruefe(len(n_b["mitglieder"]) == 2, "B ist beigetreten",
               ", ".join(m["name"] for m in n_b["mitglieder"]))
        try:
            vc = Verwaltung(tmp / "c")
            pc = vc.anlegen("Projekt C", "passphrase-charlie-3")
            Netzwerke(pc, dienst(18913, "c")).beitreten(code)
            pruefe(False, "Einladung nur einmal gültig")
        except NetzwerkFehler:
            pruefe(True, "Einladung nur einmal gültig")
        geteilt = na.freigeben(netz_a["netz_id"], [holm["fact_id"]],
                               "Bitte gegenprüfen")
        pruefe(geteilt["geteilt"] == 1, "Fakt mit öffentlichen Belegen geteilt")

        # Ein Fakt, der nur an einem internen Dokument hängt
        from policy import Stufe
        dok = pa.pod.dokument_anlegen(art="notiz", titel="Gespräch",
                                      quelle="Hintergrund", stufe=Stufe.VERTRAULICH,
                                      erfasst_von="test",
                                      notiz="Holm hat Treffen bestätigt")
        fid = pa.store.behaupten(dok["doc_id"], "Anders Holm", "associate_of",
                                 "Erik Svensson", fundstelle="Notiz")
        r = na.freigeben(netz_a["netz_id"], [fid])
        pruefe(r["geteilt"] == 0 and r["abgelehnt"],
               "interner Beleg verlässt das Projekt nicht")

        r = nb.abgleichen(netz_a["netz_id"])
        pruefe(r["neu"] == 1 and r["erreicht"] == 1, "B empfängt die Freigabe",
               json.dumps(r))
        n_b = nb.netz(netz_a["netz_id"])
        f = n_b["freigaben"][0]
        pruefe(f["autor_name"] == "Redaktion A" and
               f["inhalt"]["kommentar"] == "Bitte gegenprüfen",
               "Autor und Kommentar kommen an")
        fund = nb.als_fund(netz_a["netz_id"], [f["item_id"]])
        fb = pb.fund(fund)
        pruefe(fb["art"] == "netzwerk" and len(fb["inhalt"]["aussagen"]) == 2,
               "Freigabe landet im Prüfkorb (je Beleg eine Aussage)")
        pruefe(pb.stats()["fakten"] == 0, "… und noch nicht im Bestand")

        # Gefälschte Freigabe: Inhalt nach dem Signieren verändert
        with pa.lock:
            z = pa.db.execute("SELECT inhalt FROM netz_freigabe").fetchone()
            inhalt = json.loads(z["inhalt"])
            inhalt["objekt"] = "Gefälschte Firma Ltd."
            pa.db.execute("UPDATE netz_freigabe SET inhalt=?, empfangen=?",
                          (json.dumps(inhalt), time.time()))
            pa.db.commit()
        with pb.lock:
            pb.db.execute("DELETE FROM netz_freigabe")
            pb.db.execute("UPDATE netz_mitglied SET seit=0")
            pb.db.commit()
        r = nb.abgleichen(netz_a["netz_id"])
        pruefe(r["neu"] == 0, "veränderte Freigabe wird verworfen")

        # Gegenrichtung: B teilt, A gleicht ab
        pb.fund_uebernehmen(fund, {"aussagen": [0], "belege_sichern": False},
                            pruefer="B")
        fb_fakt = pb.alle_fakten()[0]["fact_id"]
        nb.freigeben(netz_a["netz_id"], [fb_fakt])
        r = na.abgleichen(netz_a["netz_id"])
        pruefe(r["neu"] >= 1, "A empfängt Freigabe von B")
    finally:
        da.stoppen()
        db_.stoppen()

    print("5) Netzweg schließt bei fehlendem Tor")
    e = Einstellungen(tmp / "a")
    e.setzen({"netzweg": "tor"})
    try:
        Netzweg(e, None).abrufen("https://example.org/")
        pruefe(False, "kein Abruf ohne Tor")
    except NetzwegFehler:
        pruefe(True, "kein Abruf ohne Tor — kein stiller Rückfall")
    e.setzen({"netzweg": "direkt"})

    print("6) Ortstabelle")
    from geo import nachschlagen
    pruefe(nachschlagen("BVI")["code"] == "VG", "BVI → VG")
    pruefe(nachschlagen("Limassol (Zypern)")["code"] == "CY", "Klammerzusatz")
    pruefe(nachschlagen("Vereinigtes Königreich")["code"] == "GB", "Umlaut")
    pruefe(nachschlagen("Atlantis") is None, "Unbekanntes wird nicht geraten")

    print("7) Brücke zu claude.ai")
    import auftraege as ab
    import bruecke
    from policy import Stufe
    # Tor gewählt, aber nicht da: Die Registerabfragen scheitern sofort,
    # der Test braucht kein Netz.
    e.setzen({"ki_anbieter": "chat", "netzweg": "tor"})
    nw = Netzweg(e, None)
    kk = ki.KI(e, nw)
    z = kk.zustand()
    pruefe(z["bereit"] and z["bruecke"] and not z["hintergrund"],
           "Anbieter chat: bereit, aber nichts im Hintergrund")
    v = bruecke.vorlage(ki.BEFUND_SCHEMA)
    pruefe(set(v) == set(ki.BEFUND_SCHEMA["properties"])
           and "PERSON | ORG" in v["entitaeten"][0]["typ"],
           "Antwortvorlage aus dem Befund-Schema")

    a = ab.Auftrag("recherche", "Nordkap Shipping AS", pa.name)
    a.ergebnis = ab.bruecke_recherche(pa, nw, "Nordkap Shipping AS")(a.melden)
    t = a.ergebnis["auftrag_text"]
    pruefe(a.ergebnis["offen"] and "AUFTRAG: Nordkap Shipping AS" in t
           and "director_of" in t and "REGISTERAUSZÜGE" in t
           and "Anders Holm" in t,
           "Auftrag mit Regeln, Vokabular, Bestand und Registerteil",
           f"{len(t)} Zeichen")
    befund = {
        "zusammenfassung": "Nordkap Shipping AS sitzt in Oslo.",
        "entitaeten": [{"name": "Nordkap Shipping AS", "typ": "ORG",
                        "beschreibung": "Reederei", "aliase": []}],
        "aussagen": [
            {"subjekt": "Nordkap Shipping AS", "praedikat": "registered_in",
             "objekt": "Oslo", "beleg": "https://register.example/nordkap",
             "zitat": "Forretningsadresse Oslo", "datum": "",
             "sicherheit": "hoch"},
            {"subjekt": "Nordkap Shipping AS", "praedikat": "owned_by",
             "objekt": "Unbekannt", "beleg": "", "zitat": "", "datum": "",
             "sicherheit": "niedrig"}],
        "orte": [{"name": "Oslo", "lat": 59.91, "lon": 10.75,
                  "land_iso": "NO", "genauigkeit": "stadt"}],
        "quellen": [], "offene_fragen": [], "naechste_schritte": []}
    antwort = ("Hier das Ergebnis meiner Recherche:\n\n```json\n"
               + json.dumps(befund, ensure_ascii=False, indent=2)
               + "\n```\n\nViel Erfolg!")
    r = ab.bruecke_einlesen(pa, a, antwort)
    f = pa.fund(r["fund_id"])
    pruefe(r["aussagen"] == 1 and r["verworfen"] == 1,
           "Antwort gelesen, Aussage ohne Beleg verworfen")
    pruefe(f["herkunft"] == bruecke.HERKUNFT and f["status"] == "offen"
           and f["inhalt"]["quellen"], "Fund im Prüfkorb, Herkunft claude.ai")
    try:
        ab.bruecke_einlesen(pa, a, antwort)
        pruefe(False, "zweites Einfügen abgewiesen")
    except bruecke.BrueckeFehler:
        pruefe(True, "zweites Einfügen abgewiesen")
    pruefe(bruecke.json_lesen('Text {"a": [1, 2,], } Ende') == {"a": [1, 2]},
           "JSON ohne Codeblock, mit überzähligen Kommas")
    try:
        bruecke.json_lesen("Ich konnte leider nichts finden.")
        pruefe(False, "Antwort ohne JSON → verständlicher Fehler")
    except bruecke.BrueckeFehler:
        pruefe(True, "Antwort ohne JSON → verständlicher Fehler")

    la = ab.Auftrag("lagebild", "Lagebild", pa.name)
    la.ergebnis = ab.lagebild(pa, kk, "Wer steht hinter Mare Liberum?")(
        la.melden)
    pruefe(la.ergebnis["offen"] and "Mare Liberum" in
           la.ergebnis["auftrag_text"], "Lagebild-Auftrag enthält den Bestand")
    lage = {"titel": "Mare Liberum", "lage": "## Lage\nAnders Holm …",
            "kernaussagen": [{"aussage": "Holm leitet Mare Liberum",
                              "beleglage": "bestaetigt"}],
            "schluesselfiguren": [], "geldfluesse": [], "zeitleiste": [],
            "luecken": [], "warnsignale": [], "naechste_schritte": []}
    r = ab.bruecke_einlesen(pa, la, "```json\n" + json.dumps(lage) + "\n```")
    pruefe(any(x["lagebild_id"] == r["lagebild_id"] for x in pa.lagebilder()),
           "Lagebild aus claude.ai gespeichert")

    dt = ab.Auftrag("datei", "Datei", pa.name)
    dt.ergebnis = ab.datei(
        pa, kk, "Vertrag Nordkap Shipping AS mit Baltic Bunker OÜ\n"
        "Zahlung: 1,2 Mio. EUR".encode(), "vertrag.txt", "text/plain",
        Stufe.INTERN, "test")(dt.melden)
    pruefe(dt.ergebnis["offen"] and not dt.ergebnis["anhaengen"]
           and "Baltic Bunker" in dt.ergebnis["auftrag_text"],
           "Datei-Auftrag enthält den Dateitext")
    befund["aussagen"] = [{"subjekt": "Nordkap Shipping AS",
                           "praedikat": "paid_to",
                           "objekt": "Baltic Bunker OÜ", "beleg": "Zeile 2",
                           "zitat": "Zahlung: 1,2 Mio. EUR", "datum": "",
                           "sicherheit": "mittel"}]
    r = ab.bruecke_einlesen(pa, dt, json.dumps(befund))
    f = pa.fund(r["fund_id"])
    pruefe(r["aussagen"] == 1 and f["art"] == "datei"
           and f["doc_id"] == dt.ergebnis["doc_id"],
           "Datei-Befund mit Fundstelle, an die Datei gebunden")
    e.setzen({"ki_anbieter": "claude", "netzweg": "direkt"})

    print("8) OpenSanctions-Connector")
    import quellen_offen as qo

    class _FakeEinst:
        def __init__(self, key=""):
            self._key = key

        def get(self, name, vorgabe=None):
            return self._key if name == "opensanctions_schluessel" else vorgabe

    class _FakeNetz:
        def __init__(self, antwort, key="testkey"):
            self._a = antwort
            self.einst = _FakeEinst(key)
            self.gesehen = {}

        def json(self, url, params=None, headers=None, timeout=30):
            self.gesehen = {"url": url, "params": params, "headers": headers}
            return self._a

    antwort = {"results": [
        {"id": "NK-xyz", "caption": "Testperson", "schema": "Person",
         "datasets": ["us_ofac_sdn", "eu_fsf"], "target": True,
         "first_seen": "2018-05-01T00:00:00",
         "last_change": "2024-02-02T10:00:00",
         "properties": {"topics": ["sanction", "role.pep", "crime.war"],
                        "country": ["ru"], "birthDate": ["1960-01-01"],
                        "position": ["Minister"]}}]}
    fn = _FakeNetz(antwort)
    tr = qo.opensanctions(fn, "Testperson")
    pruefe(len(tr) == 1 and tr[0]["name"] == "Testperson"
           and tr[0]["typ"] == "Person", "OpenSanctions-Treffer geparst")
    pruefe("auf Sanktionsliste" in tr[0]["einstufung"]
           and "Kriegsverbrech" in tr[0]["einstufung"]
           and "PEP" in tr[0]["einstufung"], "Themen übersetzt",
           tr[0]["einstufung"])
    pruefe(fn.gesehen["headers"]["Authorization"] == "ApiKey testkey",
           "Schlüssel im Authorization-Kopf, nicht in der URL")
    pruefe(tr[0]["url"].endswith("/entities/NK-xyz/")
           and tr[0]["gelistet_in"].startswith("us_ofac_sdn")
           and tr[0]["stand"] == "2024-02-02", "Quelle, Listen und Stand")
    try:
        qo.opensanctions(_FakeNetz(antwort, key=""), "x")
        pruefe(False, "ohne Schlüssel klarer Fehler")
    except RuntimeError as ex:
        pruefe("Schlüssel" in str(ex) and "opensanctions.org" in str(ex),
               "ohne Schlüssel klarer Fehler mit Bezugsquelle")
    r = qo.abfragen(_FakeNetz(antwort, key=""), "opensanctions", "x")
    pruefe(r["treffer"] == [] and "Schlüssel" in r["text"],
           "abfragen meldet fehlenden Schlüssel statt abzustürzen")
    pruefe("opensanctions" in qo.QUELLEN
           and qo.abfragen(fn, "opensanctions", "Testperson")["treffer"][0]
           ["name"] == "Testperson", "als Quelle registriert")

    print("9) Flug- und Schiffs-Connector")

    class _NetzMit:
        def __init__(self, antwort, key=None, keyname="gfw_schluessel"):
            self._a = antwort
            self.gesehen = []

            class _E:
                def get(self, name, vorgabe=None):
                    return key if name == keyname else vorgabe
            self.einst = _E()

        def json(self, url, params=None, headers=None, timeout=30):
            self.gesehen.append({"url": url, "params": params,
                                 "headers": headers})
            return self._a

    flug = {"ac": [{"hex": "3c6444", "flight": "DLH9LW  ", "r": "D-AIMA",
                    "t": "A388", "desc": "AIRBUS A-380-800", "lat": 50.03,
                    "lon": 8.57, "alt_baro": 37000, "gs": 480.0, "track": 95.1,
                    "squawk": "7700", "dbFlags": 0, "seen_pos": 2.0}]}
    nf = _NetzMit(flug)
    tr = qo.flugzeug(nf, "3c6444")
    pruefe(len(tr) == 1 and tr[0]["name"] == "D-AIMA"
           and tr[0]["kennung_hex"] == "3c6444", "Flugzeug geparst")
    pruefe(tr[0]["position"] == "50.0300,8.5700"
           and "A-380" in tr[0]["typ"] and tr[0]["hoehe_ft"] == 37000,
           "Position, Typ und Höhe", tr[0]["position"])
    pruefe(tr[0].get("hinweis") == "Luftnotfall (7700)", "Notfall-Squawk erkannt")
    pruefe(nf.gesehen[0]["url"].lower().endswith("/v2/hex/3c6444")
           and len(nf.gesehen) == 1, "Hex-Kennung direkt abgefragt")
    pruefe(qo.flugzeug(_NetzMit({"ac": []}), "ABC")[:] == [],
           "keine Treffer ist kein Fehler")

    gfw = {"entries": [{
        "registryInfo": [{"shipname": "POLARSTERN", "flag": "DEU",
                          "imo": "8013132", "callsign": "DBLK", "id": "v1",
                          "lengthM": 118.0, "tonnageGt": 12614}],
        "selfReportedInfo": [{"shipname": "POLARSTERN", "ssvid": "211202460",
                              "flag": "DEU", "id": "self1",
                              "transmissionDateTo": "2024-05-01T00:00:00Z"}],
        "combinedSourcesInfo": [{"shiptypes": [{"name": "RESEARCH"}]}],
        "registryOwners": [{"name": "Alfred-Wegener-Institut", "flag": "DEU"}]}]}
    ns = _NetzMit(gfw, key="tok")
    s = qo.schiff(ns, "Polarstern")
    pruefe(len(s) == 1 and s[0]["name"] == "POLARSTERN"
           and s[0]["imo"] == "8013132" and s[0]["mmsi"] == "211202460",
           "Schiff geparst: Name, IMO, MMSI")
    pruefe(s[0]["flagge"] == "DEU" and s[0]["typ"] == "RESEARCH"
           and "Alfred-Wegener" in s[0]["eigner"], "Flagge, Typ, Eigner")
    pruefe(ns.gesehen[0]["headers"]["Authorization"] == "Bearer tok"
           and ns.gesehen[0]["params"]["datasets[0]"]
           == "public-global-vessel-identity:latest", "Token und Dataset")
    try:
        qo.schiff(_NetzMit(gfw, key=None), "Polarstern")
        pruefe(False, "Schiff ohne Token klarer Fehler")
    except RuntimeError as ex:
        pruefe("Token" in str(ex) and "globalfishingwatch.org" in str(ex),
               "Schiff ohne Token klarer Fehler mit Bezugsquelle")
    pruefe({"flugzeug", "schiff"} <= set(qo.QUELLEN), "beide als Quelle gelistet")

    pa.schliessen()
    pb.schliessen()
    print(f"\n{ERGEBNIS['ok']} bestanden, {ERGEBNIS['fehler']} Fehler")
    return 1 if ERGEBNIS["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
