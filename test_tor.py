"""
IndraNet 2 — Test über das echte Tor-Netz
==========================================

    python test_tor.py

Braucht Internet und Tor (Ordner tor/ oder Tor Browser). Dauert einige
Minuten: Zwei Tor-Prozesse bauen ihre Verbindung auf und veröffentlichen
je einen Onion-Dienst. Dann tritt B per Einladungscode über Tor dem
Netzwerk von A bei, beide geben Fakten frei und gleichen ab — Ende zu Ende
über .onion-Adressen, ohne dass einer die IP des anderen kennt.

Die Brückeneinstellung wird übernommen ("auto" schaltet bei gestörter
direkter Verbindung selbst auf obfs4).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

ERGEBNIS = {"ok": 0, "fehler": 0}


def pruefe(bedingung: bool, text: str, info="") -> None:
    ERGEBNIS["ok" if bedingung else "fehler"] += 1
    print(f"  [{'ok' if bedingung else 'FEHLER'}]{' ' * (5 if bedingung else 1)}"
          f"{text}  {info}", flush=True)


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tmp = Path(tempfile.mkdtemp(prefix="indranet-tor-"))
    dienste = []
    try:
        return _lauf(tmp, dienste)
    finally:
        for t in dienste:
            t.stoppen()
        shutil.rmtree(tmp, ignore_errors=True)


def _lauf(tmp: Path, dienste: list) -> int:
    import beispiel
    from einstellungen import Einstellungen
    from netz import Netzweg
    from netzwerk import NetzwerkDienst, Netzwerke, NetzwerkFehler
    from projekt import Verwaltung
    from tor import TorDienst

    print("1) Zwei Tor-Prozesse mit Onion-Dienst")
    teilnehmer = {}
    for wer, socks, port in (("a", 19251, 18951), ("b", 19252, 18952)):
        e = Einstellungen(tmp / wer)
        e.setzen({"netzweg": "tor", "tor_socks_port": socks,
                  "netzwerk_port": port})
        t = TorDienst(tmp / wer, e)
        dienste.append(t)
        t.starten(dienst_port=port)
        teilnehmer[wer] = (e, t, port)
    beginn = time.time()
    for wer, (e, t, port) in teilnehmer.items():
        bereit = t.warten(300)
        pruefe(bereit, f"Tor {wer.upper()} verbunden",
               f"{round(time.time() - beginn)} s, Brücke: {t.bruecke or 'keine'}")
        if not bereit:
            print("   ", t.status())
            return 1
        pruefe(bool(t.onion), f"Onion-Adresse {wer.upper()}", t.onion)

    print("2) Ausgang über Tor")
    e, t, _ = teilnehmer["a"]
    r = Netzweg(e, t).pruefen()
    pruefe(r.get("ist_tor") is True, "check.torproject.org erkennt Tor",
           r.get("ip") or r.get("fehler"))

    print("3) Netzwerk über .onion")
    va, vb = Verwaltung(tmp / "a"), Verwaltung(tmp / "b")
    pa = va.anlegen("Projekt A", "passphrase-alpha-1")
    pb = vb.anlegen("Projekt B", "passphrase-bravo-2")
    pa.info_setzen(netzname="Redaktion A")
    pb.info_setzen(netzname="Redaktion B")
    f1, _ = beispiel.laden(pa)
    pa.fund_uebernehmen(f1, {"aussagen": list(range(7)),
                             "belege_sichern": False}, pruefer="A")

    da = NetzwerkDienst(teilnehmer["a"][0], teilnehmer["a"][1], lambda: None)
    db_ = NetzwerkDienst(teilnehmer["b"][0], teilnehmer["b"][1], lambda: None)
    na, nb = Netzwerke(pa, da), Netzwerke(pb, db_)
    da.aktuell, db_.aktuell = (lambda: na), (lambda: nb)
    da.starten()
    db_.starten()
    try:
        pruefe(da.eigene_adresse().endswith(".onion"),
               "eigene Adresse ist .onion", da.eigene_adresse())
        netz = na.anlegen("Konsortium über Tor")
        code = na.einladen(netz["netz_id"])["code"]

        # Ein frisch veröffentlichter Onion-Dienst ist oft erst nach ein,
        # zwei Minuten auffindbar — mehrfach versuchen.
        beigetreten, fehler, versuch_start = None, None, time.time()
        while time.time() - versuch_start < 300:
            try:
                beigetreten = nb.beitreten(code)
                break
            except NetzwerkFehler as ex:
                fehler = str(ex)
                break
            except Exception as ex:                         # noqa: BLE001
                fehler = f"{ex.__class__.__name__}: {ex}"
                time.sleep(15)
        pruefe(beigetreten is not None, "B tritt über Tor bei",
               f"{round(time.time() - versuch_start)} s"
               + ("" if beigetreten else f" — {fehler}"))
        if beigetreten is None:
            return 1

        fakt = next(f for f in pa.alle_fakten()
                    if f["praedikat"] == "director_of")
        na.freigeben(netz["netz_id"], [fakt["fact_id"]], "über Tor geteilt")
        r = nb.abgleichen(netz["netz_id"])
        pruefe(r["neu"] == 1, "B empfängt Freigabe über .onion", str(r))
        empfangen = nb.netz(netz["netz_id"])["freigaben"]
        pruefe(bool(empfangen) and
               empfangen[0]["inhalt"]["kommentar"] == "über Tor geteilt",
               "Inhalt und Signatur stimmen")

        fid = nb.als_fund(netz["netz_id"], [empfangen[0]["item_id"]])
        pb.fund_uebernehmen(fid, {"aussagen": [0], "belege_sichern": False},
                            pruefer="B")
        nb.freigeben(netz["netz_id"], [pb.alle_fakten()[0]["fact_id"]])
        # Auch B's Onion-Dienst braucht nach dem Start eine Weile, bis A ihn
        # findet. Im Betrieb übernimmt das der Abgleich alle drei Minuten.
        versuch_start = time.time()
        while True:
            r = na.abgleichen(netz["netz_id"])
            if r["erreicht"] or time.time() - versuch_start > 300:
                break
            time.sleep(15)
        grund = next((m["fehler"] for m in na.netz(netz["netz_id"])["mitglieder"]
                      if m.get("fehler")), "")
        pruefe(r["neu"] >= 1, "A empfängt Freigabe von B über .onion",
               f"{r}, {round(time.time() - versuch_start)} s"
               + (f" — {grund}" if grund and not r["neu"] else ""))
        mitglieder = na.netz(netz["netz_id"])["mitglieder"]
        pruefe(all(m["adresse"].endswith(".onion") for m in mitglieder),
               "alle Teilnehmer nur mit .onion-Adresse bekannt")
    finally:
        da.stoppen()
        db_.stoppen()
        pa.schliessen()
        pb.schliessen()

    print(f"\n{ERGEBNIS['ok']} bestanden, {ERGEBNIS['fehler']} Fehler")
    return 1 if ERGEBNIS["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
