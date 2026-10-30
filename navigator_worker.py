"""
IndraNetz — Navigator-Worker
=============================

Eigenstaendiger Einstiegspunkt fuer den Navigator-Prozess.

Warum ein eigenes Modul und kein multiprocessing.Process:

  1. KEIN PICKLE UEBER DIE GRENZE
     multiprocessing.Pipe serialisiert mit pickle. Wer die nicht
     vertrauenswuerdige Seite kontrolliert, kann damit beliebigen Code im
     vertrauenswuerdigen Prozess ausfuehren — die Firewall waere wertlos.
     Hier laeuft ausschliesslich zeilenweises JSON ueber stdin/stdout.
     JSON kennt keine Objekte, keine Klassen, keine Reduktionsfunktionen.

  2. SAUBERES __main__
     Bei multiprocessing mit "spawn" importiert das Kind das __main__-Modul
     des Elternprozesses neu. Damit landet der gesamte Core-Code im
     Navigator-Adressraum. Dieses Modul importiert nur firewall und
     navigator — faktenkern und numpy kommen nie vor.

Aufruf erfolgt durch pod.py, nicht von Hand.
"""

from __future__ import annotations

import json
import os
import sys
import uuid

from navigator import (LLM_REGISTRY, UNKNOWN_PREDICATE, UNSUPPORTED_DIRECTION,
                       adapter_a, adapter_b)


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _recv() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)


def _diagnose() -> dict:
    """Selbstauskunft fuer den Isolationsnachweis."""
    import gc
    return {
        "phase": "diagnose",
        "pid": os.getpid(),
        "kern_importiert": "faktenkern" in sys.modules,
        "numpy_importiert": "numpy" in sys.modules,
        "core_instanzen": sum(1 for o in gc.get_objects()
                              if type(o).__name__ == "Faktenkern"),
        "module": sorted(m for m in sys.modules
                         if m in {"faktenkern", "numpy", "pickle", "firewall",
                                  "navigator", "json"}),
    }


def main() -> None:
    # Zweite Absicherung: Die Umgebungsvariable wirkt in der gepackten
    # Anwendung nicht immer. Beide Kanaele deshalb ausdruecklich auf UTF-8
    # stellen — die Grenze fuehrt JSON mit Umlauten in beide Richtungen.
    for kanal in (sys.stdin, sys.stdout):
        try:
            kanal.reconfigure(encoding="utf-8", errors="strict")
        except (AttributeError, ValueError):
            pass

    while True:
        msg = _recv()
        if msg is None or msg.get("cmd") == "stop":
            return
        if msg.get("cmd") == "diagnose":
            _send(_diagnose())
            continue

        extraktion = adapter_a(msg["question"])
        if isinstance(extraktion, str):
            _send({"phase": "extract_failed", "reason": extraktion})
            continue

        _send({"phase": "lookup", "request": {
            "v": 1,
            "req_id": uuid.uuid4().hex[:16],
            "predicate_id": extraktion["predicate_id"],
            "object": extraktion["object"],
        }, "lang": extraktion.get("lang", "de")})

        antwort = _recv()
        if antwort is None:
            return
        resp = antwort["response"]
        text, warnungen = adapter_b(
            resp["status"], resp["subject"],
            extraktion["predicate_id"], extraktion["object"],
            llm=LLM_REGISTRY.get(msg.get("llm_mode")),
            lang=extraktion.get("lang", "de"),
        )
        _send({"phase": "answer", "answer": text, "warnings": warnungen})


if __name__ == "__main__":
    main()
