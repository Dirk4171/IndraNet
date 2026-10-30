"""
IndraNet — Dokumente
=====================

Der Pod haelt Referenz und Pruefsumme, nicht das Dokument. Ein Leak von
Millionen Dateien gehoert ins verschluesselte Dateisystem der Redaktion,
nicht in den Faktenspeicher.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from policy import Stufe


@dataclass
class Dokument:
    doc_id: str
    titel: str
    quelle: str
    stufe: Stufe
    sha256: str
    pfad: str | None = None
    erfasst_von: str = ""
    ts: float = field(default_factory=lambda: round(time.time(), 3))

    @staticmethod
    def aus_datei(pfad, *, titel, quelle, stufe, erfasst_von) -> "Dokument":
        p = Path(pfad)
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        return Dokument("doc:" + digest[:16], titel, quelle, stufe, digest,
                        str(p), erfasst_von)

    @staticmethod
    def virtuell(kennung, *, titel, quelle, stufe, erfasst_von) -> "Dokument":
        digest = hashlib.sha256(kennung.encode()).hexdigest()
        return Dokument("doc:" + digest[:16], titel, quelle, stufe, digest,
                        None, erfasst_von)

    @staticmethod
    def aus_pruefsumme(sha256: str, *, titel, quelle, stufe, erfasst_von,
                       ablageort: str | None = None) -> "Dokument":
        """Dokument mit extern berechneter Pruefsumme.

        Fuer Dateien, die der Pod nie zu sehen bekommt: Die Weboberflaeche
        berechnet den SHA-256 im Browser, die Datei verlaesst den Rechner
        nicht einmal in Richtung des eigenen Servers. Der Pod haelt Verweis
        und Pruefsumme — genug, um spaeter zu beweisen, dass ein vorgelegtes
        Dokument dasselbe ist, auf das sich die Recherche gestuetzt hat.
        """
        sha256 = sha256.strip().lower()
        if len(sha256) != 64 or not all(c in "0123456789abcdef" for c in sha256):
            raise ValueError("SHA-256 muss 64 hexadezimale Zeichen haben")
        return Dokument("doc:" + sha256[:16], titel, quelle, stufe, sha256,
                        ablageort, erfasst_von)

    @staticmethod
    def notiz(text: str, *, titel, quelle, stufe, erfasst_von) -> "Dokument":
        """Eigene Aufzeichnung als Beleg — Gespraechsnotiz, Beobachtung.

        Der Notiztext selbst ist der Beleg und wird ueber seine Pruefsumme
        festgehalten. Eine nachtraeglich geaenderte Notiz ergibt eine andere
        Kennung; die alte Belegkette zeigt dann ins Leere, statt still auf
        einen veraenderten Text zu verweisen.
        """
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return Dokument("doc:" + digest[:16], titel, quelle, stufe, digest,
                        None, erfasst_von)
