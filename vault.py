"""
IndraNet — Verschlüsselter Behälter (Vault)
============================================

Bis hierher lag die Pod-Datei im Klartext. Wer das Gerät mitnahm, hatte
alles. Für ein Werkzeug, das Whistleblower-Material verwaltet, ist das der
schwerwiegendste verbleibende Mangel.

WIE ES ARBEITET
---------------
Die Datenbank lebt vollständig im Arbeitsspeicher. Auf die Platte gelangt
nur ein verschlüsselter Behälter:

    Öffnen:      Behälter lesen → entschlüsseln → in :memory: laden
    Arbeiten:    alles im Speicher, kein Journal, keine temporäre Datei
    Sichern:     serialisieren → verschlüsseln → atomar schreiben

Damit berührt der Klartext niemals ein Dateisystem — auch nicht als
WAL-Datei, Journal oder Auslagerung durch SQLite selbst. Das ist der
Unterschied zu „Datei nachträglich verschlüsseln": dort liegt der Klartext
zwischenzeitlich auf der Platte und überlebt das Löschen im Zweifel in
freigegebenen Blöcken.

SCHLÜSSEL
---------
scrypt (N=2^17, r=8, p=1) über die Passphrase, dazu ein zufälliger Salt je
Behälter. Die Ableitung dauert bewusst rund eine Sekunde — das macht das
Durchprobieren von Passphrasen teuer. Verschlüsselt wird mit AES-256-GCM;
Kopfdaten gehen als zusätzlich authentifizierte Daten ein, sodass auch eine
Manipulation an Version oder Salt auffällt.

Wahlweise statt einer Passphrase eine Schlüsseldatei — für einen Schlüssel
auf einem Hardware-Token oder einem getrennt aufbewahrten Datenträger.

WAS DAS NICHT LEISTET
---------------------
Während der Pod offen ist, steht der Klartext im Arbeitsspeicher. Gegen
einen Angreifer mit Zugriff auf das laufende System hilft das nicht, und
Python kann nicht garantieren, dass nichts in die Auslagerungsdatei
gerät. Für Material, bei dem das zählt, gehört der Pod auf ein System mit
verschlüsseltem Swap.
"""

from __future__ import annotations

import json
import os
import sqlite3
import struct
import tempfile
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIE = b"INDRANET-VAULT-1"
SCRYPT_N = 2 ** 17
SCRYPT_R = 8
SCRYPT_P = 1


class VaultFehler(Exception):
    pass


class FalschePassphrase(VaultFehler):
    pass


def _schluessel(passphrase: bytes, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R,
                  p=SCRYPT_P).derive(passphrase)


def schluesseldatei_erzeugen(pfad: str | Path) -> bytes:
    """Erzeugt eine Schlüsseldatei mit 256 Bit Zufall.

    Bewahren Sie sie getrennt vom Pod auf — auf einem Token, einem Stick im
    Safe, nicht im selben Ordner. Der Sinn der Trennung geht sonst verloren.
    """
    p = Path(pfad)
    geheim = os.urandom(32)
    p.write_bytes(geheim)
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return geheim


class Vault:
    """Verschlüsselter Behälter für eine SQLite-Datenbank."""

    def __init__(self, pfad: str | Path, passphrase: str | bytes | None = None,
                 schluesseldatei: str | Path | None = None):
        if passphrase is None and schluesseldatei is None:
            raise VaultFehler("Passphrase oder Schlüsseldatei erforderlich")
        self.pfad = Path(pfad)
        self._geheim = self._geheimnis(passphrase, schluesseldatei)
        self._salt: bytes | None = None
        self._key: bytes | None = None

    @staticmethod
    def _geheimnis(passphrase, schluesseldatei) -> bytes:
        teile = []
        if passphrase is not None:
            teile.append(passphrase.encode() if isinstance(passphrase, str)
                         else passphrase)
        if schluesseldatei is not None:
            p = Path(schluesseldatei)
            if not p.exists():
                raise VaultFehler(f"Schlüsseldatei fehlt: {p}")
            teile.append(p.read_bytes())
        # Beides zusammen ergibt Zwei-Faktor: Wissen und Besitz.
        return b"\x00".join(teile)

    # --------------------------------------------------------------- Lesen
    def existiert(self) -> bool:
        return self.pfad.exists() and self.pfad.stat().st_size > len(MAGIE)

    def kopf(self) -> dict:
        """Liest die unverschlüsselten Kopfdaten — ohne Passphrase."""
        roh = self.pfad.read_bytes()
        if not roh.startswith(MAGIE):
            raise VaultFehler("kein IndraNet-Behälter")
        pos = len(MAGIE)
        (kopf_len,) = struct.unpack_from(">I", roh, pos)
        return json.loads(roh[pos + 4:pos + 4 + kopf_len].decode())

    def oeffnen(self) -> sqlite3.Connection:
        """Entschlüsselt in eine Datenbank im Arbeitsspeicher."""
        if not self.existiert():
            raise VaultFehler(f"Behälter fehlt: {self.pfad}")
        roh = self.pfad.read_bytes()
        if not roh.startswith(MAGIE):
            raise VaultFehler("kein IndraNet-Behälter")

        pos = len(MAGIE)
        (kopf_len,) = struct.unpack_from(">I", roh, pos)
        pos += 4
        kopf_roh = roh[pos:pos + kopf_len]
        kopf = json.loads(kopf_roh.decode())
        pos += kopf_len
        nonce, chiffre = roh[pos:pos + 12], roh[pos + 12:]

        self._salt = bytes.fromhex(kopf["salt"])
        self._key = _schluessel(self._geheim, self._salt)
        try:
            klar = AESGCM(self._key).decrypt(nonce, chiffre, MAGIE + kopf_roh)
        except InvalidTag:
            raise FalschePassphrase(
                "Entschlüsselung fehlgeschlagen — falsche Passphrase, "
                "falsche Schlüsseldatei oder veränderter Behälter")

        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.deserialize(klar)
        return db

    # -------------------------------------------------------------- Anlegen
    def anlegen(self) -> sqlite3.Connection:
        """Legt einen neuen, leeren Behälter an."""
        if self.existiert():
            raise VaultFehler(f"Behälter besteht bereits: {self.pfad}")
        self._salt = os.urandom(16)
        self._key = _schluessel(self._geheim, self._salt)
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.execute("CREATE TABLE IF NOT EXISTS _vault (angelegt REAL)")
        db.execute("INSERT INTO _vault VALUES (?)", (time.time(),))
        db.commit()
        self.sichern(db)
        return db

    # -------------------------------------------------------------- Sichern
    def sichern(self, db: sqlite3.Connection) -> dict:
        """Verschlüsselt den aktuellen Stand und schreibt ihn atomar.

        Atomar heißt: erst in eine Nachbardatei, dann umbenennen. Ein
        Absturz während des Schreibens darf den vorigen Stand nicht
        zerstören — ein halb geschriebener Behälter wäre unlesbar.
        """
        if self._key is None:
            raise VaultFehler("Behälter nicht geöffnet")
        db.commit()
        klar = db.serialize()

        kopf_roh = json.dumps({
            "format": MAGIE.decode(), "salt": self._salt.hex(),
            "kdf": {"scrypt": {"n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P}},
            "chiffre": "AES-256-GCM", "gesichert": round(time.time(), 3),
            "bytes_klar": len(klar),
        }, sort_keys=True).encode()

        nonce = os.urandom(12)
        chiffre = AESGCM(self._key).encrypt(nonce, klar, MAGIE + kopf_roh)

        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=str(self.pfad.parent),
                                    prefix=".indranet-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(MAGIE)
                f.write(struct.pack(">I", len(kopf_roh)))
                f.write(kopf_roh)
                f.write(nonce)
                f.write(chiffre)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, self.pfad)
            try:
                self.pfad.chmod(0o600)
            except OSError:
                pass
        except Exception:
            Path(temp).unlink(missing_ok=True)
            raise
        return {"datei": str(self.pfad), "bytes": self.pfad.stat().st_size,
                "klartext_bytes": len(klar)}

    # ------------------------------------------------------ Passphrase neu
    def passphrase_aendern(self, db: sqlite3.Connection, *,
                           neue_passphrase: str | bytes | None = None,
                           neue_schluesseldatei: str | Path | None = None
                           ) -> dict:
        """Setzt Passphrase oder Schlüsseldatei neu.

        Salt und abgeleiteter Schlüssel werden erneuert, nicht nur die
        Passphrase — sonst bliebe der alte Schlüssel gültig für jeden, der
        eine ältere Kopie des Behälters besitzt.
        """
        self._geheim = self._geheimnis(neue_passphrase, neue_schluesseldatei)
        self._salt = os.urandom(16)
        self._key = _schluessel(self._geheim, self._salt)
        return self.sichern(db)

    def dokumentschluessel(self) -> bytes:
        """Getrennter Schluessel fuer den Dokumentenspeicher.

        Aus demselben Geheimnis abgeleitet, aber nicht derselbe Schluessel:
        Wer je an den Dokumentschluessel kaeme, koennte damit nicht den
        Behaelter oeffnen. Eine Passphrase, zwei getrennte Schluessel.
        """
        if self._key is None:
            raise VaultFehler("Behälter nicht geöffnet")
        from cryptography.hazmat.primitives import hashes as _h
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        return HKDF(algorithm=_h.SHA256(), length=32, salt=self._salt,
                    info=b"IndraNet-Dokumentenspeicher-1").derive(self._key)

    def schliessen(self) -> None:
        """Überschreibt den Schlüssel im Speicher.

        Python gibt keine Garantie, dass keine Kopie zurückbleibt; das ist
        die notwendige, nicht die hinreichende Maßnahme.
        """
        self._key = None
        self._geheim = b"\x00" * len(self._geheim)


def container_pruefen(pfad: str | Path) -> dict:
    """Prüft einen Behälter ohne Passphrase — für Diagnose und Sicherung."""
    p = Path(pfad)
    if not p.exists():
        return {"vorhanden": False}
    roh = p.read_bytes()
    if not roh.startswith(MAGIE):
        return {"vorhanden": True, "gueltig": False,
                "hinweis": "kein IndraNet-Behälter (evtl. unverschlüsselte "
                           "Alt-Datei)"}
    pos = len(MAGIE)
    (kopf_len,) = struct.unpack_from(">I", roh, pos)
    kopf = json.loads(roh[pos + 4:pos + 4 + kopf_len].decode())
    return {"vorhanden": True, "gueltig": True, "bytes": len(roh),
            "gesichert": kopf.get("gesichert"), "chiffre": kopf.get("chiffre"),
            "kdf": kopf.get("kdf")}
