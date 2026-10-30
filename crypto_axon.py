"""
IndraNetz — Axon-Transport
===========================

Whitepaper v0.1 nennt in Abschnitt 10 die richtigen Bausteine (Ed25519,
X25519, AES-256-GCM), lässt aber drei Dinge offen, die den Unterschied
zwischen Verschlüsselung und Sicherheit ausmachen:

  Replay-Schutz     Eine abgefangene Signalantwort ließe sich beliebig oft
                    einspielen. Jeder Umschlag trägt einen streng
                    monotonen Zähler je Kanal.

  Vorwärtsgeheimnis Langlebige Schlüssel allein bedeuten: Wer den Schlüssel
                    später erbeutet, entschlüsselt allen mitgeschnittenen
                    Verkehr rückwirkend. Bei Journalisten ist das der
                    Regelfall, nicht der Sonderfall. Deshalb je Sitzung
                    flüchtige X25519-Schlüssel, signiert mit der
                    langlebigen Ed25519-Identität.

  Verkehrsanalyse   Wer wann mit wem spricht, ist bei Recherchen selbst die
                    Information. Der Broadcast läuft deshalb NICHT über
                    einen Koordinator, der alles sieht, sondern als
                    identische Zustellung an jede Gegenstelle einzeln,
                    mit gleich großen Umschlägen (Padding auf Blockgröße).

Die Zustellung läuft dateibasiert über eine Inbox je Pod. Für das MVP
genügt das; die Umschlagsebene ist transportunabhängig.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

UMSCHLAG_BLOCK = 512      # Padding-Raster gegen Längenanalyse


def _roh(k) -> bytes:
    return k.public_bytes(serialization.Encoding.Raw,
                          serialization.PublicFormat.Raw)


class AxonFehler(Exception):
    pass


# ------------------------------------------------------------- Identität
@dataclass
class Identitaet:
    """Langlebige Pod-Identität. Der Pod-Name folgt aus dem Schlüssel."""

    name: str
    _sk: ed25519.Ed25519PrivateKey = field(
        default_factory=ed25519.Ed25519PrivateKey.generate)

    @property
    def pod_id(self) -> str:
        return "pod:" + _roh(self._sk.public_key()).hex()[:16]

    @property
    def pubkey(self) -> ed25519.Ed25519PublicKey:
        return self._sk.public_key()

    def signieren(self, daten: bytes) -> bytes:
        return self._sk.sign(daten)

    def export(self) -> dict:
        return {"name": self.name, "pod_id": self.pod_id,
                "ed25519_pub": _roh(self.pubkey).hex()}

    def speichern(self, pfad: str | Path) -> None:
        Path(pfad).write_bytes(self._sk.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
            serialization.NoEncryption()))

    @classmethod
    def laden(cls, name: str, pfad: str | Path) -> "Identitaet":
        return cls(name, ed25519.Ed25519PrivateKey.from_private_bytes(
            Path(pfad).read_bytes()))


# ----------------------------------------------------------- Web of Trust
@dataclass
class WebOfTrust:
    """Neue Pods kommen durch Einladung und Bürgschaft hinein.

    Es gibt keine Zertifizierungsstelle. Ein Pod wird aufgenommen, wenn
    genug bereits vertraute Pods für ihn bürgen — bei Journalisten ist das
    die realistische Vertrauensform.
    """

    eigen: Identitaet
    noetige_buergschaften: int = 2
    bekannte: dict[str, dict] = field(default_factory=dict)
    buergschaften: dict[str, set] = field(default_factory=dict)

    def __post_init__(self):
        self.bekannte[self.eigen.pod_id] = {
            **self.eigen.export(), "vertraut": True, "resolver": None}

    def _pub(self, pod_id: str) -> ed25519.Ed25519PublicKey:
        eintrag = self.bekannte.get(pod_id)
        if not eintrag:
            raise AxonFehler(f"unbekannter Pod {pod_id}")
        return ed25519.Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(eintrag["ed25519_pub"]))

    def vorstellen(self, steckbrief: dict) -> None:
        self.bekannte.setdefault(steckbrief["pod_id"],
                                 {**steckbrief, "vertraut": False})

    def buergen(self, pod_id: str) -> bytes:
        """Bürgschaft ausstellen — signiert, damit sie weitergereicht werden
        kann, ohne dass der Empfänger dem Boten trauen muss."""
        return self.eigen.signieren(f"BUERGSCHAFT|{pod_id}".encode())

    def buergschaft_annehmen(self, pod_id: str, buerge_id: str,
                             signatur: bytes) -> bool:
        if not self.bekannte.get(buerge_id, {}).get("vertraut"):
            raise AxonFehler(f"Bürge {buerge_id} ist selbst nicht vertraut")
        try:
            self._pub(buerge_id).verify(signatur,
                                        f"BUERGSCHAFT|{pod_id}".encode())
        except InvalidSignature:
            raise AxonFehler("Bürgschaftssignatur ungültig")
        self.buergschaften.setdefault(pod_id, set()).add(buerge_id)
        if len(self.buergschaften[pod_id]) >= self.noetige_buergschaften:
            self.bekannte[pod_id]["vertraut"] = True
        return self.bekannte[pod_id]["vertraut"]

    def vertraut(self, pod_id: str) -> bool:
        return bool(self.bekannte.get(pod_id, {}).get("vertraut"))

    def resolver_pruefen(self, pod_id: str, eigener_fingerprint: str) -> None:
        """Föderationssperre: Wer anders normalisiert, findet still nichts.
        Lieber laut ablehnen als leise danebenliegen."""
        fremd = self.bekannte.get(pod_id, {}).get("resolver")
        if fremd is None:
            raise AxonFehler(f"{pod_id} hat keinen Resolver-Fingerabdruck genannt")
        if fremd != eigener_fingerprint:
            raise AxonFehler(
                f"Resolver-Fingerabdruck weicht ab ({fremd} vs. "
                f"{eigener_fingerprint}) — Abgleich abgelehnt")


# ---------------------------------------------------------------- Kanal
@dataclass
class Kanal:
    """Authentisierter Kanal mit Vorwärtsgeheimnis und Replay-Schutz."""

    eigen: Identitaet
    wot: WebOfTrust
    gegenstelle: str
    _eph: x25519.X25519PrivateKey = field(
        default_factory=x25519.X25519PrivateKey.generate)
    _sitzungsschluessel: bytes | None = None
    _sende_zaehler: int = 0
    _empfangs_zaehler: int = -1

    # -- Handschlag --------------------------------------------------
    def angebot(self) -> dict:
        pub = _roh(self._eph.public_key())
        return {"typ": "axon_hello", "von": self.eigen.pod_id,
                "an": self.gegenstelle, "eph": pub.hex(),
                "sig": self.eigen.signieren(
                    b"AXON-HELLO|" + pub + self.gegenstelle.encode()).hex()}

    def antwort(self, angebot: dict) -> dict:
        if angebot["an"] != self.eigen.pod_id:
            raise AxonFehler("Handschlag nicht an diesen Pod gerichtet")
        gegen = angebot["von"]
        if not self.wot.vertraut(gegen):
            raise AxonFehler(f"{gegen} ist im Web of Trust nicht vertraut")
        fremd_eph = bytes.fromhex(angebot["eph"])
        try:
            self.wot._pub(gegen).verify(
                bytes.fromhex(angebot["sig"]),
                b"AXON-HELLO|" + fremd_eph + self.eigen.pod_id.encode())
        except InvalidSignature:
            raise AxonFehler("Handschlagsignatur ungültig")

        self.gegenstelle = gegen
        self._ableiten(fremd_eph)
        pub = _roh(self._eph.public_key())
        return {"typ": "axon_hello_ack", "von": self.eigen.pod_id, "an": gegen,
                "eph": pub.hex(),
                "sig": self.eigen.signieren(
                    b"AXON-ACK|" + pub + fremd_eph).hex()}

    def abschliessen(self, ack: dict) -> None:
        fremd_eph = bytes.fromhex(ack["eph"])
        try:
            self.wot._pub(ack["von"]).verify(
                bytes.fromhex(ack["sig"]),
                b"AXON-ACK|" + fremd_eph + _roh(self._eph.public_key()))
        except InvalidSignature:
            raise AxonFehler("Bestätigungssignatur ungültig")
        self._ableiten(fremd_eph)

    def _ableiten(self, fremd_eph: bytes) -> None:
        gemeinsam = self._eph.exchange(
            x25519.X25519PublicKey.from_public_bytes(fremd_eph))
        paar = sorted([_roh(self._eph.public_key()).hex(), fremd_eph.hex()])
        self._sitzungsschluessel = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None,
            info=("IndraNetz-Axon-1|" + "|".join(paar)).encode(),
        ).derive(gemeinsam)

    @property
    def bereit(self) -> bool:
        return self._sitzungsschluessel is not None

    # -- Umschläge ---------------------------------------------------
    def verschliessen(self, nutzlast: dict) -> dict:
        if not self.bereit:
            raise AxonFehler("Kanal nicht ausgehandelt")
        self._sende_zaehler += 1
        klar = json.dumps({"seq": self._sende_zaehler,
                           "ts": round(time.time(), 3),
                           "payload": nutzlast}, ensure_ascii=False).encode()
        # Gleich große Umschläge: die Nachrichtenlänge verrät sonst den Typ.
        rest = (-len(klar) - 4) % UMSCHLAG_BLOCK
        klar = len(klar).to_bytes(4, "big") + klar + b"\x00" * rest
        nonce = os.urandom(12)
        aad = f"{self.eigen.pod_id}>{self.gegenstelle}".encode()
        chiffre = AESGCM(self._sitzungsschluessel).encrypt(nonce, klar, aad)
        return {"typ": "axon_umschlag", "von": self.eigen.pod_id,
                "an": self.gegenstelle, "nonce": nonce.hex(),
                "encrypted_payload": chiffre.hex(),
                "firewall_token": None}

    def oeffnen(self, umschlag: dict) -> dict:
        if not self.bereit:
            raise AxonFehler("Kanal nicht ausgehandelt")
        aad = f"{umschlag['von']}>{umschlag['an']}".encode()
        klar = AESGCM(self._sitzungsschluessel).decrypt(
            bytes.fromhex(umschlag["nonce"]),
            bytes.fromhex(umschlag["encrypted_payload"]), aad)
        laenge = int.from_bytes(klar[:4], "big")
        inhalt = json.loads(klar[4:4 + laenge].decode())
        if inhalt["seq"] <= self._empfangs_zaehler:
            raise AxonFehler(
                f"Replay erkannt: seq {inhalt['seq']} <= "
                f"{self._empfangs_zaehler}")
        self._empfangs_zaehler = inhalt["seq"]
        return inhalt["payload"]


# ---------------------------------------------------------------- Inbox
class Inbox:
    """Dateibasierte Zustellung. Ein Verzeichnis je Pod."""

    def __init__(self, wurzel: str | Path):
        self.wurzel = Path(wurzel)
        self.wurzel.mkdir(parents=True, exist_ok=True)

    def _fach(self, pod_id: str) -> Path:
        p = self.wurzel / pod_id.replace(":", "_")
        p.mkdir(exist_ok=True)
        return p

    def zustellen(self, an: str, nachricht: dict) -> str:
        name = f"{time.time_ns()}_{os.urandom(4).hex()}.json"
        ziel = self._fach(an) / name
        ziel.write_text(json.dumps(nachricht, ensure_ascii=False))
        return str(ziel)

    def abholen(self, pod_id: str) -> list[dict]:
        fach = self._fach(pod_id)
        raus = []
        for f in sorted(fach.glob("*.json")):
            raus.append(json.loads(f.read_text()))
            f.unlink()
        return raus

    def broadcast(self, an: list[str], nachrichten: dict[str, dict]) -> int:
        """Kein Koordinator: identische Einzelzustellung an jede Gegenstelle.
        Niemand sieht den vollständigen Verkehrsgraphen."""
        for pod_id in an:
            self.zustellen(pod_id, nachrichten[pod_id])
        return len(an)
