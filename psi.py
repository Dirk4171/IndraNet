"""
IndraNetz — Private Set Intersection für das Indra-Signal
=========================================================

Whitepaper v0.1 verschickt in Schritt 2 den Klartext:

    "query": "Svensson Family Trust"

per Broadcast an alle Pods. Damit erfährt jeder Teilnehmer — auch der
kompromittierte, auch die Konkurrenz — das Rechercheziel, Wochen vor der
Veröffentlichung. Das Rechercheziel ist selbst hochsensibles Metadatum;
`privacy_budget: "signal_only"` beschreibt eine Eigenschaft, die das
Protokoll nicht hat.

Hashen genügt nicht: Namenswörterbücher sind trivial durchprobierbar.

DAS PROTOKOLL
-------------
Ein Oblivious PRF über P-256, dazu ein Bloom-Index. Bob hält einen
langlebigen PSI-Schlüssel b.

  1. Alice: P = hash_to_curve(entität), zufälliges r
             sendet r·P
  2. Bob:   antwortet b·(r·P)                        <- lernt nichts über P
  3. Alice: rechnet r⁻¹·(b·r·P) = b·P                <- Bobs PRF-Wert
             prüft b·P gegen Bobs Bloom-Index

Bob sieht ein zufälliges Gruppenelement. Alice erfährt nur, ob ihr Element
in Bobs Bestand liegt — nichts über die übrigen. Vorbild ist das MS-PSI aus
DatashareNetwork (EPFL SPRING Lab + ICIJ, USENIX Security 2020), das für
genau diesen Anwendungsfall entworfen und dessen Sicherheit bewiesen wurde.

WARUM HASH-TO-CURVE UND NICHT hash·G
------------------------------------
Der bequeme Weg P = H(x)·G ist ein Totalbruch: Alice fragt Bob einmal mit
H(x)=1, erhält b·G und kann danach für JEDE Entität b·H(x)·G selbst
ausrechnen — Wörterbuchangriff auf Bobs gesamten Bestand, ohne ihn nochmals
zu fragen. Deshalb Try-and-Increment auf der x-Koordinate: der diskrete
Logarithmus des Ergebnisses ist niemandem bekannt.

RATENBEGRENZUNG
---------------
Jede Anfrage kostet Bob eine Mitwirkung. Ohne Begrenzung könnte Alice
Namenslisten durchprobieren. Der Zähler je Gegenstelle ist deshalb Teil des
Protokolls, nicht der Betriebsanleitung.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric import ec

CURVE = ec.SECP256R1()

# p ergibt sich aus der Kurvendefinition und wird gerechnet, nicht gesetzt.
P = 2**256 - 2**224 + 2**192 + 2**96 - 1
A = P - 3
# Gruppenordnung von P-256. Wird unten rechnerisch gegengeprüft.
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def _leite_b_ab() -> int:
    """Weierstraß-Koeffizient b aus einem frisch erzeugten Punkt ableiten,
    statt ihn aus dem Gedächtnis zu setzen: b = y² - x³ - a·x  (mod p)."""
    pn = ec.generate_private_key(CURVE).public_key().public_numbers()
    return (pn.y * pn.y - pn.x**3 - A * pn.x) % P


B = _leite_b_ab()


def _punkt(x: int, y: int) -> ec.EllipticCurvePublicKey:
    return ec.EllipticCurvePublicNumbers(x, y, CURVE).public_key()


def hash_to_curve(wert: str) -> ec.EllipticCurvePublicKey:
    """Deterministischer Kurvenpunkt mit unbekanntem diskreten Logarithmus.

    Try-and-Increment: Zähler anhängen, bis x³+ax+b ein quadratischer Rest
    ist. Erwartungswert zwei Versuche.
    """
    for zaehler in range(256):
        h = hashlib.sha256(f"IndraNetz-PSI-1|{zaehler}|{wert}".encode()).digest()
        x = int.from_bytes(h, "big") % P
        rhs = (pow(x, 3, P) + A * x + B) % P
        y = pow(rhs, (P + 1) // 4, P)          # p ≡ 3 (mod 4)
        if pow(y, 2, P) == rhs:
            return _punkt(x, min(y, P - y))    # kanonisch: kleineres y
    raise RuntimeError("kein Kurvenpunkt gefunden")


def _skalarmult(skalar: int, punkt: ec.EllipticCurvePublicKey) -> bytes:
    """skalar · punkt, Ergebnis als x-Koordinate.

    Die x-Koordinate ist gegenüber Negation invariant, deshalb bleibt die
    Kette auch dann konsistent, wenn zwischendurch kanonisiert wird.
    """
    priv = ec.derive_private_key(skalar, CURVE)
    return priv.exchange(ec.ECDH(), punkt)


def _als_punkt(x_bytes: bytes) -> ec.EllipticCurvePublicKey:
    x = int.from_bytes(x_bytes, "big")
    rhs = (pow(x, 3, P) + A * x + B) % P
    y = pow(rhs, (P + 1) // 4, P)
    if pow(y, 2, P) != rhs:
        raise ValueError("Punkt liegt nicht auf der Kurve")
    return _punkt(x, min(y, P - y))


# ----------------------------------------------------------------- Bloom
class BloomIndex:
    """Kompakter Mitgliedschaftsindex über die PRF-Werte eines Pods."""

    def __init__(self, kapazitaet: int, fehlerrate: float = 1e-6):
        import math
        self.kapazitaet = max(kapazitaet, 1)
        self.m = max(64, int(-self.kapazitaet * math.log(fehlerrate) / math.log(2) ** 2))
        self.m += (-self.m) % 8
        self.k = max(1, round(self.m / self.kapazitaet * math.log(2)))
        self.bits = bytearray(self.m // 8)
        self.n = 0

    def _positionen(self, wert: bytes):
        h = hashlib.sha256(wert).digest()
        a = int.from_bytes(h[:16], "big")
        b = int.from_bytes(h[16:], "big") | 1
        for i in range(self.k):
            yield (a + i * b) % self.m

    def add(self, wert: bytes) -> None:
        for pos in self._positionen(wert):
            self.bits[pos // 8] |= 1 << (pos % 8)
        self.n += 1

    def __contains__(self, wert: bytes) -> bool:
        return all(self.bits[pos // 8] >> (pos % 8) & 1
                   for pos in self._positionen(wert))

    def export(self) -> dict:
        return {"m": self.m, "k": self.k, "n": self.n,
                "bits": self.bits.hex()}

    @classmethod
    def laden(cls, d: dict) -> "BloomIndex":
        idx = cls.__new__(cls)
        idx.m, idx.k, idx.n = d["m"], d["k"], d["n"]
        idx.bits = bytearray.fromhex(d["bits"])
        idx.kapazitaet = max(idx.n, 1)
        return idx

    @property
    def bytes_(self) -> int:
        return len(self.bits)


# ------------------------------------------------------------ Teilnehmer
@dataclass
class PSIServer:
    """Die antwortende Seite. Hält den langlebigen PSI-Schlüssel."""

    pod_id: str
    schluessel: int = field(default_factory=lambda: secrets.randbelow(N - 2) + 2)
    # Anfragen je Gegenstelle und Zeitfenster
    limit: int = 60
    fenster_s: int = 3600
    _zaehler: dict[str, list] = field(default_factory=dict)
    index: BloomIndex | None = None

    def indizieren(self, entitaeten: list[str], fehlerrate: float = 1e-6) -> BloomIndex:
        """Einmalige Vorberechnung. Der Index ist gegenüber autorisierten
        Gegenstellen veröffentlichbar: Er enthält PRF-Werte, keine Namen."""
        idx = BloomIndex(len(entitaeten), fehlerrate)
        for e in entitaeten:
            idx.add(_skalarmult(self.schluessel, hash_to_curve(e)))
        self.index = idx
        return idx

    def auswerten(self, gegenstelle: str, geblendet_hex: str) -> str:
        """Beantwortet eine geblendete Anfrage. Lernt dabei nichts."""
        jetzt = time.time()
        fenster = [t for t in self._zaehler.get(gegenstelle, [])
                   if jetzt - t < self.fenster_s]
        if len(fenster) >= self.limit:
            raise PermissionError(
                f"Ratenbegrenzung: {self.limit} Anfragen je "
                f"{self.fenster_s // 60} Minuten erschöpft")
        fenster.append(jetzt)
        self._zaehler[gegenstelle] = fenster

        punkt = _als_punkt(bytes.fromhex(geblendet_hex))
        return _skalarmult(self.schluessel, punkt).hex()


@dataclass
class PSIClient:
    """Die fragende Seite."""

    pod_id: str

    def blenden(self, entitaet: str) -> tuple[str, int]:
        r = secrets.randbelow(N - 2) + 2
        return _skalarmult(r, hash_to_curve(entitaet)).hex(), r

    def entblenden(self, antwort_hex: str, r: int) -> bytes:
        r_inv = pow(r, -1, N)
        return _skalarmult(r_inv, _als_punkt(bytes.fromhex(antwort_hex)))

    def pruefen(self, prf_wert: bytes, index: BloomIndex) -> bool:
        return prf_wert in index


def selbsttest() -> None:
    """Prüft die Kurvenkonstanten rechnerisch, statt ihnen zu vertrauen."""
    pn = ec.generate_private_key(CURVE).public_key().public_numbers()
    assert (pn.y**2 - pn.x**3 - A * pn.x - B) % P == 0, "b falsch abgeleitet"

    p_pt = hash_to_curve("Probe")
    r = secrets.randbelow(N - 2) + 2
    zwischen = _als_punkt(_skalarmult(r, p_pt))
    zurueck = _skalarmult(pow(r, -1, N), zwischen)
    assert zurueck == p_pt.public_numbers().x.to_bytes(32, "big"), (
        "Gruppenordnung N falsch")

    s = PSIServer("bob")
    idx = s.indizieren(["Mare Liberum Ltd.", "Nordkap Shipping AS"])
    c = PSIClient("alice")
    for wert, erwartet in [("Mare Liberum Ltd.", True), ("Helios Inc.", False)]:
        gb, r = c.blenden(wert)
        prf = c.entblenden(s.auswerten("alice", gb), r)
        assert c.pruefen(prf, idx) is erwartet, f"PSI falsch fuer {wert}"


if __name__ == "__main__":
    import time as _t
    selbsttest()
    print("PSI-Selbsttest bestanden.")
    print(f"  Kurve      P-256, b rechnerisch abgeleitet: {hex(B)[:18]}...")
    s = PSIServer("bob")
    t0 = _t.time()
    idx = s.indizieren([f"Entitaet_{i}" for i in range(500)])
    print(f"  Index      500 Entitaeten in {_t.time()-t0:.2f} s, "
          f"{idx.bytes_/1024:.1f} KB, k={idx.k}")
    c = PSIClient("alice")
    t0 = _t.time()
    for i in range(50):
        gb, r = c.blenden(f"Entitaet_{i}")
        c.entblenden(s.auswerten("alice", gb), r)
    print(f"  Abfrage    {(_t.time()-t0)/50*1000:.1f} ms je Anfrage (3 Skalarmult.)")
