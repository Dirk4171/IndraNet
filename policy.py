"""
IndraNetz — Indra-Juwel (Policy Engine)
========================================

Verwaltet Quellenschutzstufen, Zugriffsrechte und Freigaben.

Grundsatz: Die Firewall schützt den Faktenspeicher vor dem Sprachmodell.
Das Juwel schützt die QUELLE vor allem übrigen — vor Kolleginnen mit zu
weitem Zugriff, vor der Föderation, vor der Kollaboration, vor dem
Beschlagnahmefall.

Die vier Stufen bilden ab, was eine Redaktion tatsächlich unterscheidet:

  OEFFENTLICH    Handelsregister, Bilanzen, Gerichtsakten
  INTERN         eigene Recherche, noch unveröffentlicht
  VERTRAULICH    Hintergrundgespräch, Quelle namentlich bekannt
  WHISTLEBLOWER  Quelle gefährdet — Leak, Insider, anonyme Übergabe

Die vierte Stufe ist keine Abstufung der dritten, sondern eine andere
Kategorie: Bei ihr steht die körperliche Sicherheit eines Menschen im
Spiel. Sie verlässt den Pod unter keinen Umständen automatisch, und ihre
Freigabe braucht zwei Personen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum


class Stufe(IntEnum):
    OEFFENTLICH = 0
    INTERN = 1
    VERTRAULICH = 2
    WHISTLEBLOWER = 3

    @property
    def label(self) -> str:
        return self.name.capitalize()


class Rolle(IntEnum):
    GAST = 0
    JOURNALIST = 1
    LEITUNG = 2
    ADMIN = 3


@dataclass(frozen=True)
class Entscheidung:
    erlaubt: bool
    grund: str
    auflage: str | None = None      # z. B. "Vier-Augen-Freigabe nötig"

    def __bool__(self) -> bool:
        return self.erlaubt


# Wer darf Belege welcher Stufe einsehen.
_BELEG_MINDESTROLLE = {
    Stufe.OEFFENTLICH:   Rolle.GAST,
    Stufe.INTERN:        Rolle.JOURNALIST,
    Stufe.VERTRAULICH:   Rolle.LEITUNG,
    Stufe.WHISTLEBLOWER: Rolle.ADMIN,
}

# Was ein föderiertes Signal über einen Fakt dieser Stufe preisgeben darf.
_SIGNAL_KLASSE = {
    Stufe.OEFFENTLICH:   "open",
    Stufe.INTERN:        "editorial",
    Stufe.VERTRAULICH:   "confidential",
    Stufe.WHISTLEBLOWER: "whistleblower_high",
}


@dataclass
class PolicyEngine:
    """Regelwerk eines Pods. Jede Entscheidung wird protokolliert."""

    pod_id: str
    # Stufe, ab der eine Freigabe zwei Personen braucht.
    vier_augen_ab: Stufe = Stufe.VERTRAULICH
    # Stufe, ab der föderierte Signale ganz unterbleiben.
    signal_sperre_ab: Stufe | None = None
    protokoll: list[dict] = field(default_factory=list)

    def _log(self, aktion: str, e: Entscheidung, **kv) -> Entscheidung:
        self.protokoll.append({
            "ts": round(time.time(), 3), "pod": self.pod_id, "aktion": aktion,
            "erlaubt": e.erlaubt, "grund": e.grund, "auflage": e.auflage, **kv,
        })
        return e

    # ------------------------------------------------------------- Belege
    def beleg_einsehen(self, rolle: Rolle, stufe: Stufe) -> Entscheidung:
        noetig = _BELEG_MINDESTROLLE[stufe]
        if rolle >= noetig:
            e = Entscheidung(True, f"{rolle.name} erfüllt {noetig.name}")
        else:
            e = Entscheidung(False, f"{stufe.label} verlangt mindestens "
                                    f"{noetig.name}, vorhanden {rolle.name}")
        return self._log("beleg_einsehen", e, rolle=rolle.name, stufe=stufe.name)

    # -------------------------------------------------------- Föderation
    def signal_senden(self, stufe: Stufe) -> Entscheidung:
        """Darf über einen Fakt dieser Stufe überhaupt signalisiert werden?"""
        if self.signal_sperre_ab is not None and stufe >= self.signal_sperre_ab:
            e = Entscheidung(False, f"{stufe.label} ist für Signale gesperrt")
        else:
            e = Entscheidung(True, f"Signal zulässig, Klasse "
                                   f"{_SIGNAL_KLASSE[stufe]}")
        return self._log("signal_senden", e, stufe=stufe.name)

    @staticmethod
    def signal_klasse(stufe: Stufe) -> str:
        """Was das Signal preisgibt: eine Klassenbezeichnung, kein Fakt."""
        return _SIGNAL_KLASSE[stufe]

    # ------------------------------------------------------ Kollaboration
    def in_lichtung_teilen(self, rolle: Rolle, stufe: Stufe,
                           freigeber: set[str] | None = None) -> Entscheidung:
        """Darf dieser Fakt in einen Kollaborationsraum kopiert werden?"""
        freigeber = freigeber or set()
        if stufe is Stufe.WHISTLEBLOWER:
            if rolle < Rolle.ADMIN:
                e = Entscheidung(False, "Whistleblower-Material: nur ADMIN")
            elif len(freigeber) < 2:
                e = Entscheidung(False, "Whistleblower-Material: zwei "
                                        "Freigaben nötig",
                                 auflage=f"{len(freigeber)}/2 vorhanden")
            else:
                e = Entscheidung(True, "zwei Freigaben liegen vor")
        elif rolle < _BELEG_MINDESTROLLE[stufe]:
            e = Entscheidung(False, f"{stufe.label} verlangt mindestens "
                                    f"{_BELEG_MINDESTROLLE[stufe].name}")
        elif stufe >= self.vier_augen_ab and len(freigeber) < 2:
            e = Entscheidung(False, "Vier-Augen-Freigabe nötig",
                             auflage=f"{len(freigeber)}/2 vorhanden")
        else:
            e = Entscheidung(True, "Freigabe vollständig")
        return self._log("in_lichtung_teilen", e, rolle=rolle.name,
                         stufe=stufe.name, freigeber=sorted(freigeber))

    # ------------------------------------------------------------ Bericht
    def bericht(self) -> dict:
        verweigert = [p for p in self.protokoll if not p["erlaubt"]]
        return {
            "entscheidungen": len(self.protokoll),
            "verweigert": len(verweigert),
            "letzte_verweigerung": verweigert[-1]["grund"] if verweigert else None,
        }
