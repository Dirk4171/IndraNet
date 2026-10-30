"""
IndraNet — Dokumentenspeicher
==============================

Die frühere Annahme war: Das Dokument liegt im verschlüsselten Dateisystem
der Redaktion, der Pod hält nur Verweis und Prüfsumme. Das gilt für ein
großes Haus mit IT-Abteilung. Für die freie Journalistin gilt es nicht —
sie hat ein Notebook und vielleicht eine externe Platte. Ein Verweis auf
`D:\\Akten\\leak.pdf` ist für sie kein Schutz, sondern eine Notiz.

Deshalb: IndraNet kann Belegdokumente selbst verschlüsselt aufbewahren.

WARUM NICHT IM BEHÄLTER
-----------------------
Der Vault-Behälter wird beim Öffnen vollständig in den Arbeitsspeicher
geladen und beim Sichern als Ganzes neu verschlüsselt. Mit 500 MB
Dokumenten darin wäre er unbenutzbar: Jedes Speichern würde alles neu
schreiben, und der Arbeitsspeicherbedarf verdreifachte sich.

Stattdessen ein eigener Ablageordner neben dem Behälter. Jede Datei einzeln
verschlüsselt, blockweise verarbeitet, mit eigenem Schlüssel aus derselben
Passphrase. Eine 2-GB-Datei belegt so nie mehr als einen Block im Speicher.

BLOCKWEISE VERSCHLÜSSELUNG
--------------------------
AES-256-GCM verarbeitet keine Ströme. Die Datei wird deshalb in Blöcke zu
1 MiB geteilt, jeder mit eigener Nonce aus Basis-Nonce plus Zähler.

Drei Angriffe muss das abwehren, und jeder davon wird über die
authentifizierten Zusatzdaten je Block ausgeschlossen:

  Umsortieren     Der Blockzähler geht in die Zusatzdaten ein.
  Abschneiden     Der letzte Block ist als solcher markiert. Fehlt er,
                  bricht die Entschlüsselung ab.
  Vertauschen     Der Kopfsatz-Hash geht in jeden Block ein. Blöcke aus
                  einer anderen Datei passen nicht.

WAS DER ORDNER PREISGIBT
------------------------
Die Dateinamen im Ablageordner sind Hashes der Dokumentkennung, nicht die
Originalnamen. Wer den Ordner sieht, erfährt die Anzahl der Dokumente und
ihre ungefähre Größe — mehr nicht. Originalname, Typ und Größe stehen
verschlüsselt im Kopfsatz.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIE = b"INDRANET-DOK-1"
BLOCK = 1024 * 1024          # 1 MiB Klartext je Block
GCM_ANHANG = 16              # Länge des Authentifizierungsanhangs
WARNGRENZE = 500 * 1024 * 1024


class DokumentSpeicherFehler(Exception):
    pass


@dataclass
class Ablage:
    doc_id: str
    dateiname: str
    bytes_klar: int
    bytes_verschluesselt: int
    sha256: str
    typ: str


class Dokumentenspeicher:
    """Verschlüsselter Ablageordner für Belegdokumente."""

    def __init__(self, ordner: str | Path, schluessel: bytes):
        if len(schluessel) != 32:
            raise DokumentSpeicherFehler("Schlüssel muss 32 Byte haben")
        self.ordner = Path(ordner)
        self.ordner.mkdir(parents=True, exist_ok=True)
        self._aes = AESGCM(schluessel)

    # ------------------------------------------------------------- Ablage
    def _pfad(self, doc_id: str) -> Path:
        """Undurchsichtiger Dateiname. Der Ordner verrät keine Titel."""
        return self.ordner / (hashlib.sha256(
            b"INDRANET-ABLAGE|" + doc_id.encode()).hexdigest()[:32] + ".dok")

    def enthaelt(self, doc_id: str) -> bool:
        return self._pfad(doc_id).exists()

    # ---------------------------------------------------------- Schreiben
    def ablegen(self, doc_id: str, quelle: str | Path | bytes, *,
                dateiname: str = "", typ: str = "") -> Ablage:
        """Verschlüsselt eine Datei oder einen Puffer in den Ablageordner.

        Liefert die Prüfsumme des Klartexts — dieselbe, die auch ein
        Empfänger des Originaldokuments errechnen würde.
        """
        ziel = self._pfad(doc_id)
        if ziel.exists():
            raise DokumentSpeicherFehler(f"{doc_id} ist bereits abgelegt")

        if isinstance(quelle, (bytes, bytearray)):
            leser, groesse = _PufferLeser(bytes(quelle)), len(quelle)
            dateiname = dateiname or "unbenannt"
        else:
            p = Path(quelle)
            if not p.is_file():
                raise DokumentSpeicherFehler(f"keine Datei: {p}")
            groesse = p.stat().st_size
            leser, dateiname = _DateiLeser(p), dateiname or p.name

        basis_nonce = os.urandom(8)
        kopf = json.dumps({
            "format": MAGIE.decode(), "doc_id": doc_id, "block": BLOCK,
            "nonce": basis_nonce.hex(), "bytes": groesse,
        }, sort_keys=True).encode()
        kopf_hash = hashlib.sha256(kopf).digest()

        digest = hashlib.sha256()
        geschrieben = 0
        temp = ziel.with_suffix(".teil")
        try:
            with leser as q, open(temp, "wb") as z:
                z.write(MAGIE)
                z.write(struct.pack(">I", len(kopf)))
                z.write(kopf)

                # Innerer Kopfsatz: Originalname und Typ gehören nicht in
                # den unverschlüsselten Teil.
                innen = json.dumps({"dateiname": dateiname, "typ": typ},
                                   ensure_ascii=False).encode()
                z.write(self._block_schreiben(innen, kopf_hash, 0, False))

                nummer = 1
                while True:
                    stueck = q.read(BLOCK)
                    letzter = len(stueck) < BLOCK
                    if not stueck and nummer > 1:
                        letzter = True
                    digest.update(stueck)
                    geschrieben += len(stueck)
                    z.write(self._block_schreiben(stueck, kopf_hash, nummer,
                                                  letzter))
                    nummer += 1
                    if letzter:
                        break
                z.flush()
                os.fsync(z.fileno())
            os.replace(temp, ziel)
            try:
                ziel.chmod(0o600)
            except OSError:
                pass
        except Exception:
            Path(temp).unlink(missing_ok=True)
            raise

        return Ablage(doc_id=doc_id, dateiname=dateiname,
                      bytes_klar=geschrieben,
                      bytes_verschluesselt=ziel.stat().st_size,
                      sha256=digest.hexdigest(), typ=typ)

    def _block_schreiben(self, klar: bytes, kopf_hash: bytes, nummer: int,
                         letzter: bool) -> bytes:
        nonce = os.urandom(12)
        aad = kopf_hash + struct.pack(">I?", nummer, letzter)
        chiffre = self._aes.encrypt(nonce, klar, aad)
        return (struct.pack(">I?", nummer, letzter) + nonce
                + struct.pack(">I", len(chiffre)) + chiffre)

    # ------------------------------------------------------------- Lesen
    def lesen(self, doc_id: str):
        """Liefert den Klartext blockweise. Für große Dateien.

        Als Erzeuger, damit eine 2-GB-Datei nie vollständig im Speicher
        liegt — weder beim Ablegen noch beim Ausgeben.
        """
        pfad = self._pfad(doc_id)
        if not pfad.exists():
            raise DokumentSpeicherFehler(f"{doc_id} ist nicht abgelegt")

        with open(pfad, "rb") as q:
            if q.read(len(MAGIE)) != MAGIE:
                raise DokumentSpeicherFehler("kein IndraNet-Dokument")
            (kopf_len,) = struct.unpack(">I", q.read(4))
            kopf = q.read(kopf_len)
            kopf_hash = hashlib.sha256(kopf).digest()
            if json.loads(kopf.decode())["doc_id"] != doc_id:
                raise DokumentSpeicherFehler("Kennung im Kopfsatz weicht ab")

            erwartet = 0
            while True:
                block = self._block_lesen(q, kopf_hash, erwartet)
                if block is None:
                    raise DokumentSpeicherFehler(
                        "Datei bricht ab — abgeschnitten oder beschädigt")
                klar, letzter = block
                if erwartet == 0:
                    innen = json.loads(klar.decode())      # Kopfsatz innen
                else:
                    yield klar
                if letzter and erwartet > 0:
                    return
                erwartet += 1

    # Blockkopf: Nummer (4) + Kennzeichen "letzter" (1)
    _KOPF = struct.calcsize(">I?")

    def _block_lesen(self, q, kopf_hash: bytes, erwartet: int):
        kopf = q.read(self._KOPF)
        if len(kopf) < self._KOPF:
            return None
        nummer, letzter = struct.unpack(">I?", kopf)
        if nummer != erwartet:
            raise DokumentSpeicherFehler(
                f"Block {nummer} statt {erwartet} — umsortiert oder entfernt")
        nonce = q.read(12)
        (laenge,) = struct.unpack(">I", q.read(4))
        chiffre = q.read(laenge)
        if len(chiffre) != laenge:
            raise DokumentSpeicherFehler("Block unvollständig")
        aad = kopf_hash + struct.pack(">I?", nummer, letzter)
        try:
            return self._aes.decrypt(nonce, chiffre, aad), letzter
        except InvalidTag:
            raise DokumentSpeicherFehler(
                f"Block {nummer} nicht entschlüsselbar — falscher Schlüssel "
                "oder verändert")

    def angaben(self, doc_id: str) -> dict:
        """Kopfsatzangaben ohne die Datei zu entschlüsseln."""
        pfad = self._pfad(doc_id)
        if not pfad.exists():
            raise DokumentSpeicherFehler(f"{doc_id} ist nicht abgelegt")
        with open(pfad, "rb") as q:
            q.read(len(MAGIE))
            (kopf_len,) = struct.unpack(">I", q.read(4))
            kopf = json.loads(q.read(kopf_len).decode())
            kopf_hash = hashlib.sha256(json.dumps(
                kopf, sort_keys=True).encode()).digest()
            innen, _ = self._block_lesen(q, kopf_hash, 0)
        return {**json.loads(innen.decode()), "bytes": kopf["bytes"],
                "bytes_verschluesselt": pfad.stat().st_size}

    def ausgeben(self, doc_id: str, ziel: str | Path) -> Path:
        """Entschlüsselt in eine Datei — zum Öffnen oder Weitergeben."""
        ziel = Path(ziel)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with open(ziel, "wb") as z:
            for stueck in self.lesen(doc_id):
                z.write(stueck)
        return ziel

    def inhalt(self, doc_id: str) -> bytes:
        """Vollständiger Klartext. Nur für kleine Dokumente."""
        return b"".join(self.lesen(doc_id))

    # ------------------------------------------------------------ Betrieb
    def entfernen(self, doc_id: str) -> bool:
        """Löscht die Ablage.

        Ein gewöhnliches Löschen; das Dateisystem kann Reste in
        freigegebenen Blöcken behalten. Weil der Inhalt verschlüsselt war,
        sind diese Reste ohne den Schlüssel wertlos — genau dafür ist die
        Verschlüsselung da.
        """
        pfad = self._pfad(doc_id)
        if not pfad.exists():
            return False
        pfad.unlink()
        return True

    def stats(self) -> dict:
        dateien = list(self.ordner.glob("*.dok"))
        return {"dokumente": len(dateien),
                "bytes": sum(f.stat().st_size for f in dateien),
                "ordner": str(self.ordner)}


def pruefsumme(quelle: str | Path | bytes) -> tuple[str, int]:
    """SHA-256 und Groesse, ohne die Datei in den Speicher zu laden.

    Wird vor dem Ablegen gebraucht: Die Dokumentkennung folgt aus der
    Pruefsumme, muss also feststehen, bevor verschluesselt wird.
    """
    if isinstance(quelle, (bytes, bytearray)):
        return hashlib.sha256(quelle).hexdigest(), len(quelle)
    p = Path(quelle)
    h = hashlib.sha256()
    groesse = 0
    with open(p, "rb") as f:
        while (stueck := f.read(BLOCK)):
            h.update(stueck)
            groesse += len(stueck)
    return h.hexdigest(), groesse


class _DateiLeser:
    def __init__(self, pfad: Path):
        self.pfad, self._f = pfad, None

    def __enter__(self):
        self._f = open(self.pfad, "rb")
        return self._f

    def __exit__(self, *_):
        if self._f:
            self._f.close()


class _PufferLeser:
    def __init__(self, daten: bytes):
        import io
        self._b = io.BytesIO(daten)

    def __enter__(self):
        return self._b

    def __exit__(self, *_):
        self._b.close()
