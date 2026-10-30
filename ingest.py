"""
IndraNet — Datenimport
=======================

Jede importierte Zeile wird zu einer AUSSAGE: Dieses Dokument behauptet an
dieser Fundstelle dieses Tripel. Ein Fakt ohne Aussage entsteht auf diesem
Weg gar nicht erst.

Spaltenangaben dürfen Vorlagen sein — "{firma} {rechtsform}" setzt die
Entität aus mehreren Spalten zusammen. Reale Register führen Firma und
Rechtsform fast immer getrennt; ohne Zusammenführung entstehen zwei
Entitäten, die erst die Prüfliste wieder zusammenbringt.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from policy import Stufe
from provenance import Dokument


@dataclass
class Zuordnung:
    subjekt_spalte: str
    praedikat: str
    objekt_spalte: str

    @staticmethod
    def _wert(spec: str, zeile: dict) -> str:
        if "{" in spec:
            try:
                return " ".join(spec.format(**zeile).split())
            except KeyError:
                return ""
        return (zeile.get(spec) or "").strip()

    def subjekt(self, zeile: dict) -> str:
        return self._wert(self.subjekt_spalte, zeile)

    def objekt(self, zeile: dict) -> str:
        return self._wert(self.objekt_spalte, zeile)

    def gilt(self, zeile: dict) -> bool:
        return bool(self.subjekt(zeile) and self.objekt(zeile))

    @classmethod
    def aus_text(cls, spec: str) -> "Zuordnung":
        teile = spec.split(":")
        if len(teile) != 3:
            raise ValueError(
                f"erwartet subjekt:praedikat:objekt, erhalten {spec!r}")
        return cls(*teile)


@dataclass
class Importbericht:
    zeilen: int = 0
    aussagen: int = 0
    uebersprungen: int = 0
    dokument: str = ""
    fehler: list = field(default_factory=list)
    vorschlaege: int = 0

    def __str__(self) -> str:
        z = (f"{self.zeilen} Zeilen gelesen, {self.aussagen} Aussagen erfasst, "
             f"{self.uebersprungen} übersprungen")
        if self.fehler:
            z += f", {len(self.fehler)} Fehler"
        if self.vorschlaege:
            z += f"; {self.vorschlaege} Entitäten zur Prüfung vorgemerkt"
        return z

    def als_dict(self) -> dict:
        return {"zeilen": self.zeilen, "aussagen": self.aussagen,
                "uebersprungen": self.uebersprungen, "dokument": self.dokument,
                "fehler": self.fehler[:10], "vorschlaege": self.vorschlaege}


def _verarbeite(pod, zeilen, zuordnungen, dok, erfasst_von, bericht) -> None:
    for nr, zeile in enumerate(zeilen, start=2):        # Zeile 1 = Kopfzeile
        bericht.zeilen += 1
        for z in zuordnungen:
            if not z.gilt(zeile):
                bericht.uebersprungen += 1
                continue
            subj, obj = z.subjekt(zeile), z.objekt(zeile)
            try:
                pod.store.behaupten(
                    dok.doc_id, subj, z.praedikat, obj,
                    fundstelle=f"Zeile {nr}, Spalte "
                               f"{z.subjekt_spalte}/{z.objekt_spalte}",
                    zitat=f"{subj} → {obj}", erfasst_von=erfasst_von)
                bericht.aussagen += 1
            except Exception as e:                       # noqa: BLE001
                bericht.fehler.append(f"Zeile {nr}: {e}")


def importiere_csv(pod, pfad, zuordnungen, *, titel: str, quelle: str,
                   stufe: Stufe, erfasst_von: str,
                   trennzeichen: str = ",") -> Importbericht:
    pfad = Path(pfad)
    dok = Dokument.aus_datei(pfad, titel=titel, quelle=quelle, stufe=stufe,
                             erfasst_von=erfasst_von)
    pod.store.dokument_aufnehmen(dok)
    bericht = Importbericht(dokument=dok.doc_id)
    with pfad.open(newline="", encoding="utf-8") as f:
        _verarbeite(pod, csv.DictReader(f, delimiter=trennzeichen),
                    zuordnungen, dok, erfasst_von, bericht)
    bericht.vorschlaege = len(pod.vorschlaege())
    return bericht


def importiere_json(pod, pfad, zuordnungen, *, titel: str, quelle: str,
                    stufe: Stufe, erfasst_von: str,
                    wurzel: str | None = None) -> Importbericht:
    pfad = Path(pfad)
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    if wurzel:
        daten = daten[wurzel]
    if not isinstance(daten, list):
        raise ValueError("erwartet wird eine Liste von Objekten")
    dok = Dokument.aus_datei(pfad, titel=titel, quelle=quelle, stufe=stufe,
                             erfasst_von=erfasst_von)
    pod.store.dokument_aufnehmen(dok)
    bericht = Importbericht(dokument=dok.doc_id)
    _verarbeite(pod, ({k: str(v) for k, v in d.items()} for d in daten),
                zuordnungen, dok, erfasst_von, bericht)
    bericht.vorschlaege = len(pod.vorschlaege())
    return bericht


def importiere_tripel(pod, tripel, *, titel: str, quelle: str, stufe: Stufe,
                      erfasst_von: str, kennung: str | None = None
                      ) -> Importbericht:
    """Direkter Import ohne Datei — API-Abzug, Datenbankzeile, Handeingabe."""
    dok = Dokument.virtuell(kennung or f"{quelle}|{titel}", titel=titel,
                            quelle=quelle, stufe=stufe, erfasst_von=erfasst_von)
    pod.store.dokument_aufnehmen(dok)
    bericht = Importbericht(dokument=dok.doc_id)
    for nr, (s, p, o) in enumerate(tripel, start=1):
        bericht.zeilen += 1
        try:
            pod.store.behaupten(dok.doc_id, s, p, o,
                                fundstelle=f"Eintrag {nr}",
                                zitat=f"{s} → {o}", erfasst_von=erfasst_von)
            bericht.aussagen += 1
        except Exception as e:                            # noqa: BLE001
            bericht.fehler.append(f"Eintrag {nr}: {e}")
    bericht.vorschlaege = len(pod.vorschlaege())
    return bericht
