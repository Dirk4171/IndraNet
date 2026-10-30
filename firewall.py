"""
IndraNetz — Firewall-Schnittstelle
==================================

Die einzige Verbindung zwischen dem Navigator (Sprachmodell, nicht
vertrauenswuerdig) und dem Faktenspeicher (vertrauenswuerdig).

Whitepaper v0.1 beschreibt die Firewall als Diagramm. Hier ist sie eine
durchgesetzte Grenze mit vier Eigenschaften:

  1. ECHTE PROZESSGRENZE
     Der Navigator laeuft in einem eigenen Interpreter (spawn). Er besitzt
     keine Referenz auf den Core, keinen gemeinsamen Speicher, kein Handle
     auf die Speicherdatei. Er hat ausschliesslich ein Pipe-Ende.

  2. GESCHLOSSENES SCHEMA IN BEIDE RICHTUNGEN
     Nur exakt die unten definierten Felder mit exakt diesen Typen passieren.
     Alles andere loest FirewallViolation aus. Listen, Arrays, bytes, dicts
     und verschachtelte Strukturen scheitern schon an der Typpruefung — damit
     kann kein Vektor die Grenze passieren, auch nicht getarnt.

  3. KEINE NUMERISCHEN SCORES NACH AUSSEN
     Neu gegenueber v0.1: Die Kosinus-Aehnlichkeit darf die Grenze NICHT
     passieren. Sie ist ein Seitenkanal — wer mit gewaehlten Objekten sondiert
     und die Antwortmuster mitliest, kann Rueckschluesse auf den Bestand
     ziehen. Nach aussen geht nur der diskrete Status.

  4. MANIPULATIONSSICHERES PROTOKOLL
     Jede Grenzueberschreitung wird in eine Hash-Kette geschrieben. Ein
     nachtraeglich veraenderter oder geloeschter Eintrag bricht die Kette.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field

MAX_OBJECT_LEN = 256
MAX_SUBJECT_LEN = 512
MAX_QUESTION_LEN = 512
MAX_ANSWER_LEN = 1024

VALID_STATUS = {"MATCH", "NO_MATCH", "AMBIGUOUS"}
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_REQ_ID = re.compile(r"\A[0-9a-f]{8,64}\Z")

# Geschlossenes Praedikatsvokabular. Der Navigator kennt die IDs und Labels —
# aber kein einziges Subjekt und kein einziges Objekt des Speichers.
# Geschlossenes Praedikatsvokabular. Der Navigator kennt IDs und Labels —
# aber kein einziges Subjekt und kein einziges Objekt des Speichers.
#
# Abgeleitet aus resolver.PREDICATE_SCHEMA, damit beide nicht auseinander
# laufen koennen: Ein Praedikat, das der Speicher kennt und die Firewall
# nicht, waere ein stiller Ausfall.
def _vokabular() -> dict:
    from resolver import INVERSE
    raus = {}
    for i, p in enumerate(sorted(INVERSE), start=1):
        raus[i] = p                       # Hinrichtung   1..n
        raus[100 + i] = INVERSE[p]        # Gegenrichtung 101..
    return raus


PREDICATES: dict[int, str] = _vokabular()
PREDICATE_IDS: dict[str, int] = {v: k for k, v in PREDICATES.items()}


class FirewallViolation(Exception):
    """Wird ausgeloest, sobald etwas die Grenze passieren will, das nicht darf."""


# ------------------------------------------------------------------ Validierung
def _check_text(value, field_name: str, max_len: int) -> str:
    if type(value) is not str:                       # bewusst type(), nicht isinstance:
        raise FirewallViolation(                      # str-Subklassen koennen Logik tragen
            f"{field_name}: erwartet str, erhalten {type(value).__name__}")
    if len(value) > max_len:
        raise FirewallViolation(f"{field_name}: {len(value)} Zeichen > Limit {max_len}")
    if _CONTROL.search(value):
        raise FirewallViolation(f"{field_name}: Steuerzeichen nicht erlaubt")
    return value


def validate_request(msg) -> dict:
    """Navigator -> Core. Nur Praedikat-ID und Objekt-String."""
    if type(msg) is not dict:
        raise FirewallViolation(f"Anfrage muss dict sein, war {type(msg).__name__}")
    expected = {"v", "req_id", "predicate_id", "object"}
    if set(msg) != expected:
        extra, missing = set(msg) - expected, expected - set(msg)
        raise FirewallViolation(f"Feldsatz falsch (zuviel: {extra or '-'}, fehlt: {missing or '-'})")
    if type(msg["v"]) is not int or msg["v"] != 1:
        raise FirewallViolation("v: Protokollversion muss int 1 sein")
    if type(msg["predicate_id"]) is not int:
        raise FirewallViolation("predicate_id: erwartet int")
    if msg["predicate_id"] not in PREDICATES:
        raise FirewallViolation(f"predicate_id {msg['predicate_id']} nicht im Vokabular")
    _check_text(msg["req_id"], "req_id", 64)
    if not _REQ_ID.match(msg["req_id"]):
        raise FirewallViolation("req_id: nur hexadezimal, 8-64 Zeichen")
    _check_text(msg["object"], "object", MAX_OBJECT_LEN)
    if not msg["object"].strip():
        raise FirewallViolation("object: leer")
    return dict(msg)


def validate_response(msg) -> dict:
    """Core -> Navigator. Nur Status und ggf. Subjekt-String. Kein Score."""
    if type(msg) is not dict:
        raise FirewallViolation(f"Antwort muss dict sein, war {type(msg).__name__}")
    expected = {"v", "req_id", "status", "subject"}
    if set(msg) != expected:
        extra = set(msg) - expected
        raise FirewallViolation(
            f"Feldsatz falsch (zuviel: {extra or '-'}). "
            "Aehnlichkeitswerte duerfen die Grenze nicht passieren."
        )
    if type(msg["v"]) is not int or msg["v"] != 1:
        raise FirewallViolation("v: Protokollversion muss int 1 sein")
    _check_text(msg["req_id"], "req_id", 64)
    if type(msg["status"]) is not str or msg["status"] not in VALID_STATUS:
        raise FirewallViolation(f"status: {msg['status']!r} nicht zulaessig")
    if msg["status"] == "MATCH":
        _check_text(msg["subject"], "subject", MAX_SUBJECT_LEN)
    elif msg["subject"] is not None:
        # Auch AMBIGUOUS traegt kein Subjekt: Der "beste Kandidat" waere ein
        # Fakt, fuer den der Core nicht einstehen kann.
        raise FirewallViolation(f"{msg['status']} darf kein Subjekt tragen")
    return dict(msg)


def validate_question(text) -> str:
    """UI -> Navigator. Die Frage selbst ist sensibel: Sie verraet das
    Rechercheziel. Deshalb muss der Navigator lokal laufen — ein Cloud-Modell
    an dieser Stelle hebt den gesamten Quellenschutz auf."""
    return _check_text(text, "question", MAX_QUESTION_LEN)


def validate_answer(text) -> str:
    """Navigator -> UI."""
    return _check_text(text, "answer", MAX_ANSWER_LEN)


# ------------------------------------------------------------------- Audit-Log
@dataclass
class AuditLog:
    """Hash-verkettetes Protokoll aller Grenzueberschreitungen.

    Objekt- und Subjekt-Strings werden per Vorgabe nur als Hash abgelegt: Das
    Protokoll soll beweisen, DASS und in welcher Reihenfolge etwas passiert
    ist, nicht das Rechercheziel bei einer Beschlagnahme preisgeben.
    """
    entries: list = field(default_factory=list)
    plaintext: bool = False
    _head: bytes = b"\x00" * 32

    def _digest(self, value: str | None) -> str | None:
        if value is None:
            return None
        if self.plaintext:
            return value
        return "sha256:" + hashlib.sha256(value.encode()).hexdigest()[:16]

    def record(self, direction: str, kind: str, *, predicate_id=None,
               obj=None, status=None, subject=None, note=None) -> None:
        body = {
            "n": len(self.entries),
            "ts": round(time.time(), 3),
            "direction": direction,          # "N->C" oder "C->N"
            "kind": kind,
            "predicate": PREDICATES.get(predicate_id) if predicate_id else None,
            "object": self._digest(obj),
            "status": status,
            "subject": self._digest(subject),
            "note": note,
        }
        raw = json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
        self._head = hashlib.sha256(self._head + raw).digest()
        self.entries.append({**body, "chain": self._head.hex()[:16]})

    def verify(self) -> bool:
        head = b"\x00" * 32
        for e in self.entries:
            body = {k: v for k, v in e.items() if k != "chain"}
            raw = json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
            head = hashlib.sha256(head + raw).digest()
            if head.hex()[:16] != e["chain"]:
                return False
        return True

    def dump(self, last: int = 12) -> str:
        out = []
        for e in self.entries[-last:]:
            arrow = "N->C" if e["direction"] == "N->C" else "C->N"
            detail = e["status"] or e["predicate"] or e["kind"]
            out.append(f"    #{e['n']:<3} {arrow}  {e['kind']:<16} {detail or '':<22} "
                       f"{e['chain']}")
        return "\n".join(out)
