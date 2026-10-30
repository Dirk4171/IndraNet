"""
IndraNet — Externe Quellen
===========================

Anschluss an öffentliche Datenbestände. Zwei Gestaltungsregeln, die alles
weitere bestimmen:

KORPUS HOLEN, LOKAL ABGLEICHEN
------------------------------
Eine Screening-Anfrage an einen fremden Dienst verrät, wen Sie prüfen. Das
ist dasselbe Leck, das wir für die Föderation mit dem Oblivious PRF
geschlossen haben — eine Ebene tiefer und mit demselben Ausweg: Der Korpus
wird heruntergeladen, der Abgleich läuft auf Ihrem Gerät. Ihre
Entitätsliste verlässt den Pod nicht.

Wo ein Dienst nur online abfragbar ist, muss der Abgleich ausdrücklich
freigegeben werden und wird protokolliert. Voreinstellung ist immer der
lokale Weg.

QUELLEN ALTERN
--------------
Eine Recherche, die auf einem sechs Monate alten Registerauszug steht,
sollte das anzeigen. Jede Quelle führt Buch über letzten Abruf, letzten
Erfolg, Datenstand und Fehler — und die Oberfläche zeigt es an, statt es zu
verschweigen. Die Idee ist bei World Monitor abgeschaut, das den Zustand
seiner Datenzulieferungen öffentlich ausweist, fehlerhafte eingeschlossen.

TREFFER SIND KEINE FAKTEN
-------------------------
Ein Sanktionstreffer ist ein Fund, keine Behauptung. Er wird angezeigt und
kann übernommen werden — aber übernehmen muss ein Mensch. Automatisch
entstehen aus fremden Beständen keine Aussagen im Pod.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

QUELLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS quelle (
  name          TEXT PRIMARY KEY,
  art           TEXT,
  endpunkt      TEXT,
  lizenz        TEXT,
  letzter_abruf REAL,
  letzter_erfolg REAL,
  datensaetze   INTEGER DEFAULT 0,
  stand         TEXT,
  fehler        TEXT,
  lokal         INTEGER DEFAULT 1
);
"""

# Ab wann eine Quelle als veraltet gilt (Sekunden).
FRISCHE_WARNUNG = 7 * 24 * 3600
FRISCHE_ALARM = 30 * 24 * 3600


@dataclass
class Treffer:
    """Ein Fund in einem fremden Bestand. Noch keine Aussage im Pod."""
    entitaet: str              # Anzeigeform aus dem Pod
    cluster_id: str
    quelle: str
    fremd_id: str
    fremd_name: str
    art: str                   # "sanktion" | "pep" | "erwaehnung" | "verbindung"
    merkmale: list = field(default_factory=list)
    score: float = 1.0
    zusatz: dict = field(default_factory=dict)

    def __str__(self) -> str:
        m = ", ".join(self.merkmale) if self.merkmale else self.art
        return (f"{self.entitaet}  ←  {self.fremd_name}  [{self.quelle}] "
                f"{m}  ({self.score:.2f})")


class Quelle:
    """Basis für externe Bestände."""

    art = "generisch"
    lizenz = "unbekannt"
    lokal = True                 # Abgleich läuft auf diesem Gerät

    def __init__(self, name: str, store=None):
        self.name = name
        self.store = store
        self.endpunkt: str | None = None
        self.stand: str | None = None
        self.datensaetze = 0

    # ----------------------------------------------------------- Gesundheit
    def _tabelle(self) -> None:
        if self.store is not None:
            self.store.db.executescript(QUELLE_SCHEMA)

    def melde(self, erfolg: bool, fehler: str | None = None) -> None:
        if self.store is None:
            return
        self._tabelle()
        jetzt = time.time()
        vorher = self.store.db.execute(
            "SELECT letzter_erfolg FROM quelle WHERE name=?",
            (self.name,)).fetchone()
        letzter_erfolg = jetzt if erfolg else (
            vorher["letzter_erfolg"] if vorher else None)
        self.store.db.execute(
            "INSERT OR REPLACE INTO quelle (name,art,endpunkt,lizenz,"
            "letzter_abruf,letzter_erfolg,datensaetze,stand,fehler,lokal) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self.name, self.art, self.endpunkt, self.lizenz, jetzt,
             letzter_erfolg, self.datensaetze, self.stand, fehler,
             int(self.lokal)))
        self.store.db.commit()

    @staticmethod
    def gesundheit(store) -> list[dict]:
        """Zustand aller Quellen — für die Ansicht *Quellen*."""
        store.db.executescript(QUELLE_SCHEMA)
        jetzt = time.time()
        raus = []
        for z in store.db.execute("SELECT * FROM quelle ORDER BY name"):
            alter = (jetzt - z["letzter_erfolg"]) if z["letzter_erfolg"] else None
            if z["fehler"]:
                zustand = "FEHLER"
            elif alter is None:
                zustand = "NIE"
            elif alter > FRISCHE_ALARM:
                zustand = "VERALTET"
            elif alter > FRISCHE_WARNUNG:
                zustand = "ALT"
            else:
                zustand = "OK"
            raus.append({
                "name": z["name"], "art": z["art"], "zustand": zustand,
                "alter_tage": round(alter / 86400, 1) if alter else None,
                "datensaetze": z["datensaetze"], "stand": z["stand"],
                "fehler": z["fehler"], "lizenz": z["lizenz"],
                "lokal": bool(z["lokal"]), "endpunkt": z["endpunkt"]})
        return raus

    # ------------------------------------------------------------- Abrufen
    def _lade_zeilen(self, quelle: str | Path, grenze: int | None = None):
        """Liest einen Entitätenstrom (eine JSON-Zeile je Datensatz).

        Akzeptiert lokale Datei oder URL. Der Download ist ein bewusster,
        einmaliger Vorgang — nicht eine Abfrage je Entität.
        """
        pfad = str(quelle)
        self.endpunkt = pfad
        if pfad.startswith(("http://", "https://")):
            with urllib.request.urlopen(pfad, timeout=120) as antwort:
                for n, zeile in enumerate(antwort):
                    if grenze and n >= grenze:
                        break
                    zeile = zeile.strip()
                    if zeile:
                        yield json.loads(zeile)
        else:
            with open(pfad, encoding="utf-8") as f:
                for n, zeile in enumerate(f):
                    if grenze and n >= grenze:
                        break
                    zeile = zeile.strip()
                    if zeile:
                        yield json.loads(zeile)

    # --------------------------------------------------------- Schnittstelle
    def holen(self, *a, **kw) -> dict:
        raise NotImplementedError

    def abgleichen(self, pod, **kw) -> list[Treffer]:
        raise NotImplementedError


def treffer_uebernehmen(pod, treffer: list[Treffer], *, quelle_name: str,
                        titel: str, stufe, erfasst_von: str,
                        tripel: list) -> dict:
    """Übernimmt geprüfte Treffer als Aussagen — nach menschlicher Freigabe.

    Getrennt vom Abgleich, weil ein Treffer ein Fund ist und keine
    Behauptung. Wer das automatisiert, holt sich fremde Fehler als eigene
    Fakten ins Haus.
    """
    from ingest import importiere_tripel
    return importiere_tripel(
        pod, tripel, titel=titel, quelle=quelle_name, stufe=stufe,
        erfasst_von=erfasst_von,
        kennung=f"{quelle_name}|{titel}|{len(tripel)}").als_dict()
