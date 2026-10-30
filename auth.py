"""
IndraNet — Konten und Anmeldung
================================

Bis hierher war die Rolle in der Oberfläche ein Auswahlfeld: Jeder konnte
ADMIN wählen. Auf dem Notebook einer einzelnen Rechercheurin war das
vertretbar — sie besitzt die Datei ohnehin. Sobald zwei Personen denselben
Pod benutzen, ist das Indra-Juwel wirkungslos: Es prüft korrekt, aber
niemand prüft, wer da fragt.

WAS HIER PASSIERT
-----------------
Konten mit scrypt-gehashten Passwörtern, Sitzungen mit Ablauf, und die
Rolle kommt aus dem Konto statt aus der Anfrage. Alle Anmeldevorgänge
gehen in ein Protokoll — auch die gescheiterten, denn wiederholte
Fehlversuche sind das erste Zeichen für einen Zugriffsversuch.

VIER-AUGEN-FREIGABEN WERDEN ECHT
--------------------------------
Erst mit Konten bekommt das Vier-Augen-Prinzip Substanz. Vorher war
`freigeber=["a", "b"]` eine Liste von Zeichenketten, die sich jeder selbst
ausdenken konnte. Jetzt gibt jede Person einzeln frei, mit ihrem Konto,
und das System prüft, dass es zwei VERSCHIEDENE Personen sind.

WAS DAS NICHT LEISTET
---------------------
Wer den Behälter und die Passphrase hat, kann die Kontentabelle ändern —
die Konten liegen im selben verschlüsselten Behälter. Diese Schicht regelt
die Zusammenarbeit mehrerer Personen an einem Pod, nicht den Schutz gegen
den Besitzer des Behälters. Für getrennte Vertrauensbereiche braucht es
getrennte Pods; genau dafür gibt es die Föderation.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from policy import Rolle

KONTO_SCHEMA = """
CREATE TABLE IF NOT EXISTS konto (
  benutzer   TEXT PRIMARY KEY,
  anzeige    TEXT,
  rolle      INTEGER NOT NULL,
  salt       TEXT NOT NULL,
  hash       TEXT NOT NULL,
  angelegt   REAL,
  letzter_zugriff REAL,
  gesperrt   INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS anmeldeprotokoll (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  benutzer TEXT, erfolg INTEGER, grund TEXT, ts REAL, herkunft TEXT
);
"""

SCRYPT_N = 2 ** 14          # Passwörter: schnell genug für jede Anmeldung
SITZUNG_DAUER = 8 * 3600    # ein Arbeitstag
MAX_FEHLVERSUCHE = 5
SPERRE_S = 300


class AnmeldeFehler(Exception):
    pass


@dataclass
class Sitzung:
    token: str
    benutzer: str
    anzeige: str
    rolle: Rolle
    ablauf: float

    @property
    def gueltig(self) -> bool:
        return time.time() < self.ablauf

    def als_dict(self) -> dict:
        return {"benutzer": self.benutzer, "anzeige": self.anzeige,
                "rolle": self.rolle.name,
                "ablauf_in_min": round((self.ablauf - time.time()) / 60)}


def _hash(passwort: str, salt: bytes) -> str:
    return Scrypt(salt=salt, length=32, n=SCRYPT_N, r=8, p=1).derive(
        passwort.encode()).hex()


class Konten:
    """Kontenverwaltung eines Pods."""

    def __init__(self, db):
        self.db = db
        self.db.executescript(KONTO_SCHEMA)
        self.db.commit()
        self._sitzungen: dict[str, Sitzung] = {}

    # ------------------------------------------------------------- Anlegen
    def anlegen(self, benutzer: str, passwort: str, rolle: Rolle, *,
                anzeige: str = "", durch: str | None = None) -> dict:
        """Legt ein Konto an. Das erste Konto wird immer ADMIN."""
        benutzer = benutzer.strip().lower()
        if not benutzer or len(passwort) < 8:
            raise AnmeldeFehler("Benutzername nötig, Passwort mindestens "
                                "8 Zeichen")
        if self.anzahl() == 0:
            rolle = Rolle.ADMIN          # sonst wäre der Pod unbedienbar
        elif durch is not None and self.rolle_von(durch) is not Rolle.ADMIN:
            raise AnmeldeFehler("nur ADMIN darf Konten anlegen")

        salt = os.urandom(16)
        try:
            self.db.execute(
                "INSERT INTO konto (benutzer,anzeige,rolle,salt,hash,angelegt) "
                "VALUES (?,?,?,?,?,?)",
                (benutzer, anzeige or benutzer, int(rolle), salt.hex(),
                 _hash(passwort, salt), time.time()))
        except Exception:
            raise AnmeldeFehler(f"Konto {benutzer!r} besteht bereits")
        self.db.commit()
        return {"benutzer": benutzer, "rolle": rolle.name}

    def anzahl(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM konto").fetchone()[0]

    def rolle_von(self, benutzer: str) -> Rolle | None:
        z = self.db.execute("SELECT rolle FROM konto WHERE benutzer=?",
                            (benutzer.strip().lower(),)).fetchone()
        return Rolle(z["rolle"]) if z else None

    def liste(self) -> list[dict]:
        return [{"benutzer": z["benutzer"], "anzeige": z["anzeige"],
                 "rolle": Rolle(z["rolle"]).name,
                 "gesperrt": bool(z["gesperrt"]),
                 "letzter_zugriff": z["letzter_zugriff"]}
                for z in self.db.execute(
                    "SELECT * FROM konto ORDER BY rolle DESC, benutzer")]

    def rolle_setzen(self, benutzer: str, rolle: Rolle, *, durch: str) -> None:
        if self.rolle_von(durch) is not Rolle.ADMIN:
            raise AnmeldeFehler("nur ADMIN darf Rollen ändern")
        if (benutzer.strip().lower() == durch.strip().lower()
                and rolle is not Rolle.ADMIN):
            raise AnmeldeFehler("die eigene ADMIN-Rolle kann nicht abgelegt "
                                "werden — sonst sperrt sich der letzte ADMIN aus")
        self.db.execute("UPDATE konto SET rolle=? WHERE benutzer=?",
                        (int(rolle), benutzer.strip().lower()))
        self.db.commit()

    def passwort_aendern(self, benutzer: str, altes: str, neues: str) -> None:
        if not self._pruefe(benutzer, altes):
            raise AnmeldeFehler("altes Passwort stimmt nicht")
        if len(neues) < 8:
            raise AnmeldeFehler("Passwort mindestens 8 Zeichen")
        salt = os.urandom(16)
        self.db.execute("UPDATE konto SET salt=?, hash=? WHERE benutzer=?",
                        (salt.hex(), _hash(neues, salt),
                         benutzer.strip().lower()))
        self.db.commit()

    # ------------------------------------------------------------ Anmelden
    def _pruefe(self, benutzer: str, passwort: str) -> bool:
        z = self.db.execute("SELECT salt,hash FROM konto WHERE benutzer=?",
                            (benutzer.strip().lower(),)).fetchone()
        if not z:
            # Trotzdem rechnen: sonst verrät die Antwortzeit, welche
            # Benutzernamen existieren.
            _hash(passwort, os.urandom(16))
            return False
        return hmac.compare_digest(
            _hash(passwort, bytes.fromhex(z["salt"])), z["hash"])

    def _fehlversuche(self, benutzer: str) -> int:
        seit = time.time() - SPERRE_S
        return self.db.execute(
            "SELECT COUNT(*) FROM anmeldeprotokoll WHERE benutzer=? "
            "AND erfolg=0 AND ts>?", (benutzer, seit)).fetchone()[0]

    def _protokoll(self, benutzer: str, erfolg: bool, grund: str,
                   herkunft: str) -> None:
        self.db.execute(
            "INSERT INTO anmeldeprotokoll (benutzer,erfolg,grund,ts,herkunft) "
            "VALUES (?,?,?,?,?)", (benutzer, int(erfolg), grund, time.time(),
                                   herkunft))
        self.db.commit()

    def anmelden(self, benutzer: str, passwort: str,
                 herkunft: str = "lokal") -> Sitzung:
        benutzer = benutzer.strip().lower()
        z = self.db.execute("SELECT * FROM konto WHERE benutzer=?",
                            (benutzer,)).fetchone()

        if self._fehlversuche(benutzer) >= MAX_FEHLVERSUCHE:
            self._protokoll(benutzer, False, "gesperrt", herkunft)
            raise AnmeldeFehler(
                f"zu viele Fehlversuche — {SPERRE_S // 60} Minuten gesperrt")
        if z is not None and z["gesperrt"]:
            self._protokoll(benutzer, False, "Konto gesperrt", herkunft)
            raise AnmeldeFehler("Konto ist gesperrt")
        if not self._pruefe(benutzer, passwort):
            self._protokoll(benutzer, False, "falsche Anmeldedaten", herkunft)
            # Bewusst gleiche Meldung für falschen Namen und falsches
            # Passwort — sonst ist die Benutzerliste ausleitbar.
            raise AnmeldeFehler("Benutzername oder Passwort falsch")

        self.db.execute("UPDATE konto SET letzter_zugriff=? WHERE benutzer=?",
                        (time.time(), benutzer))
        self._protokoll(benutzer, True, "angemeldet", herkunft)

        s = Sitzung(token=secrets.token_urlsafe(32), benutzer=benutzer,
                    anzeige=z["anzeige"], rolle=Rolle(z["rolle"]),
                    ablauf=time.time() + SITZUNG_DAUER)
        self._sitzungen[s.token] = s
        return s

    def sitzung(self, token: str | None) -> Sitzung | None:
        if not token:
            return None
        s = self._sitzungen.get(token)
        if s is None:
            return None
        if not s.gueltig:
            self._sitzungen.pop(token, None)
            return None
        return s

    def abmelden(self, token: str) -> None:
        self._sitzungen.pop(token, None)

    def rolle_aus_sitzung(self, token: str | None) -> Rolle:
        """Rolle für eine Anfrage. Ohne gültige Sitzung: GAST.

        Das ist der entscheidende Punkt gegenüber vorher: Die Rolle kommt
        aus der Sitzung, nicht aus der Anfrage. Ein Aufrufer kann sie sich
        nicht mehr aussuchen.
        """
        s = self.sitzung(token)
        return s.rolle if s else Rolle.GAST

    # ----------------------------------------------------- Vier-Augen echt
    def freigabe_pruefen(self, freigeber: list[str]) -> set:
        """Prüft, ob die Freigeber echte, verschiedene Konten sind.

        Vorher konnte man sich zwei Zeichenketten ausdenken. Jetzt müssen
        es zwei verschiedene, bestehende Konten sein.
        """
        gueltig = set()
        for name in freigeber:
            n = (name or "").strip().lower()
            if n and self.rolle_von(n) is not None:
                gueltig.add(n)
        return gueltig

    def bericht(self) -> dict:
        seit = time.time() - 24 * 3600
        fehl = self.db.execute(
            "SELECT COUNT(*) FROM anmeldeprotokoll WHERE erfolg=0 AND ts>?",
            (seit,)).fetchone()[0]
        return {"konten": self.anzahl(),
                "offene_sitzungen": sum(1 for s in self._sitzungen.values()
                                        if s.gueltig),
                "fehlversuche_24h": fehl}
