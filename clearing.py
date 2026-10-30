"""
IndraNet — Indra-Lichtung
==========================

Ein flüchtiger, isolierter Faktenraum für die Zusammenarbeit zweier
Redaktionen. Er enthält ausschließlich, was beide Seiten ausdrücklich
freigegeben haben, und wird danach vernichtet.

Im Aussage-Modell wandert nicht der Fakt, sondern die AUSSAGE — mit
Dokumentbezug und Prüfsumme, ohne den Dokumentinhalt. Damit sieht die
Gegenseite, worauf eine Behauptung beruht und wie gut sie belegt ist, ohne
das Quellmaterial zu bekommen.

  Eigene Ablage       In-Memory-Datenbank, kein Bezug zu den Heimatpods.
  Freigabe je Fakt    Nichts wandert automatisch. Das Indra-Juwel prüft
                      die Schutzstufe, ab VERTRAULICH braucht es zwei
                      Personen, bei WHISTLEBLOWER zusätzlich ADMIN.
  Löschung mit Beweis Beim Schließen wird die Ablage verworfen. Was bleibt,
                      ist eine beidseitig signierte Beweiskette ohne
                      Rohdaten.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field

from policy import Entscheidung, Rolle, Stufe
from provenance import Dokument
from store import Store


class LichtungGeschlossen(Exception):
    pass


@dataclass
class Freigabe:
    fact_id: str
    aussage: str
    von_pod: str
    stufe: Stufe
    beleglage: str
    quellen: list
    freigeber: list
    kette_sha256: str | None = None
    ts: float = field(default_factory=lambda: round(time.time(), 3))


class Lichtung:
    def __init__(self, teilnehmer: list):
        self.lichtung_id = "lichtung:" + secrets.token_hex(8)
        self.teilnehmer = list(teilnehmer)
        self.store = Store(":memory:")
        self.freigaben: list[Freigabe] = []
        self.abgelehnt: list[dict] = []
        self.eroeffnet = round(time.time(), 3)
        self.geschlossen: float | None = None
        self._kette: dict | None = None

    # ------------------------------------------------------------ Beitrag
    def einbringen(self, pod, fact_id: str, *, rolle: Rolle,
                   freigeber: list) -> Entscheidung:
        if self.geschlossen:
            raise LichtungGeschlossen("Lichtung ist bereits vernichtet")

        fakt = pod.store.fakt(fact_id)
        if fakt is None:
            return Entscheidung(False, f"Fakt {fact_id[:14]} unbekannt")

        stufe = pod.verifikation.stufe_von(fact_id)
        ent = pod.policy.in_lichtung_teilen(rolle, stufe, set(freigeber))
        if not ent:
            self.abgelehnt.append({
                "pod": pod.pod_id, "fact_id": fact_id,
                "aussage": f"{fakt.subjekt} · {fakt.praedikat} · {fakt.objekt}",
                "grund": ent.grund, "auflage": ent.auflage})
            return ent

        # Ein Sammeldokument je abgebendem Pod und Schutzstufe. Der Inhalt
        # bleibt zu Hause; hier steht nur, worauf sich die Aussage stützt.
        dok = Dokument.virtuell(
            f"{self.lichtung_id}|{pod.pod_id}|{stufe.name}",
            titel=f"Freigabe aus {pod.name}", quelle=f"{pod.name} ({stufe.name})",
            stufe=stufe, erfasst_von=",".join(sorted(freigeber)))
        self.store.dokument_aufnehmen(dok)
        self.store.behaupten(dok.doc_id, fakt.subjekt, fakt.praedikat,
                             fakt.objekt,
                             fundstelle=f"freigegeben aus {pod.name}",
                             erfasst_von=",".join(sorted(freigeber)))

        kette = pod.verifikation.beweiskette(fact_id, rolle)
        self.freigaben.append(Freigabe(
            fact_id=fact_id,
            aussage=f"{fakt.subjekt} · {fakt.praedikat} · {fakt.objekt}",
            von_pod=pod.pod_id, stufe=stufe, beleglage=fakt.beleglage.value,
            quellen=fakt.quellen, freigeber=sorted(freigeber),
            kette_sha256=kette["sha256"]))
        return ent

    # ------------------------------------------------------------ Nutzung
    def _lebt(self) -> None:
        if self.geschlossen:
            raise LichtungGeschlossen("Lichtung ist bereits vernichtet")

    def frage(self, praedikat: str, objekt: str):
        self._lebt()
        return self.store.frage(praedikat, objekt)

    def pfade(self, von: str, nach: str, max_schritte: int = 5):
        self._lebt()
        from graph import pfade
        return pfade(self.store, von, nach, max_schritte)

    def bestand(self) -> dict:
        je_pod: dict[str, int] = {}
        for f in self.freigaben:
            je_pod[f.von_pod] = je_pod.get(f.von_pod, 0) + 1
        return {"fakten": len(self.freigaben), "je_pod": je_pod,
                "abgelehnt": len(self.abgelehnt)}

    # ---------------------------------------------------------- Schließen
    def schliessen(self, signierer: dict) -> dict:
        if self.geschlossen:
            return self._kette

        kette = {
            "format": "indranet-lichtung-1",
            "lichtung_id": self.lichtung_id,
            "teilnehmer": self.teilnehmer,
            "eroeffnet": self.eroeffnet,
            "geschlossen": round(time.time(), 3),
            "freigaben": [
                {"fact_id": f.fact_id, "aussage": f.aussage,
                 "von_pod": f.von_pod, "stufe": f.stufe.name,
                 "beleglage": f.beleglage, "quellen": f.quellen,
                 "freigeber": f.freigeber, "kette_sha256": f.kette_sha256,
                 "ts": f.ts} for f in self.freigaben],
            "abgelehnt": self.abgelehnt,
        }
        rumpf = json.dumps(kette, sort_keys=True, ensure_ascii=False).encode()
        kette["sha256"] = hashlib.sha256(rumpf).hexdigest()
        kette["signaturen"] = {
            pod_id: ident.signieren(bytes.fromhex(kette["sha256"])).hex()
            for pod_id, ident in signierer.items()}

        self.store.close()
        self.store = None
        self.geschlossen = kette["geschlossen"]
        self._kette = kette
        return kette

    @staticmethod
    def kette_pruefen(kette: dict, pubkeys: dict) -> tuple[bool, str]:
        from cryptography.exceptions import InvalidSignature
        rumpf = {k: v for k, v in kette.items()
                 if k not in ("sha256", "signaturen")}
        soll = hashlib.sha256(json.dumps(
            rumpf, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if soll != kette["sha256"]:
            return False, "Prüfsumme stimmt nicht — Kette wurde verändert"
        for pod_id, sig in kette["signaturen"].items():
            pk = pubkeys.get(pod_id)
            if pk is None:
                return False, f"kein öffentlicher Schlüssel für {pod_id}"
            try:
                pk.verify(bytes.fromhex(sig), bytes.fromhex(kette["sha256"]))
            except InvalidSignature:
                return False, f"Signatur von {pod_id} ungültig"
        return True, f"{len(kette['signaturen'])} Signaturen gültig"
