"""
IndraNet — Speicher
====================

Die Umkehrung gegenüber der Vorgängerarchitektur: Nicht der FAKT ist das
primäre Objekt, sondern die AUSSAGE.

    Aussage = Dokument D behauptet (Subjekt, Prädikat, Objekt),
              extrahiert von Person P am Tag T.

Ein Fakt ist daraus abgeleitet: das Bündel aller Aussagen mit gleichem
(Subjekt-Cluster, Prädikat, Objekt-Cluster). Sein Status ergibt sich aus
der Beleglage, nicht aus einer Speichereigenschaft.

WARUM DIESE UMKEHRUNG
---------------------
Quellen widersprechen sich.    "Quelle A sagt X gehört Y, Quelle B sagt Z
                               gehört Y" ist der Normalfall investigativer
                               Arbeit. Mit Fakten als Primärobjekt lässt
                               sich das nicht darstellen.

Dokumente werden widerrufen.   Stellt sich ein Dokument als gefälscht
                               heraus, muss jede daraus abgeleitete Aussage
                               und jede darauf gestützte Schlussfolgerung
                               auffindbar sein. Das ist hier eine Abfrage.

Mehrfachbelegung zählt.        "Dreifach unabhängig belegt" gegen
                               "Einzelquelle" ist die wichtigste
                               epistemische Unterscheidung, die eine
                               Redaktion trifft.

ENTITY RESOLUTION OHNE NEUINDIZIERUNG
-------------------------------------
Jeder Schlüssel zeigt auf einen Cluster. Eine bestätigte Verschmelzung ist
ein UPDATE auf den Cluster-Zeiger — kein Neuaufbau des Speichers.

DETERMINISMUS
-------------
Kein Sprachmodell ist am Abruf beteiligt. Der Determinismus kommt daher und
nicht aus der Darstellung; eine B-Tree-Suche ist so deterministisch wie
jede Vektorüberlagerung, nur schneller und ohne Kapazitätsgrenze.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from resolver import (INVERSE, INVERSE_OF, PREDICATE_SCHEMA, EntityResolver,
                      ist_umkehr, typen_fuer)

SCHEMA_VERSION = "indranet-1"

# Prädikate, bei denen ein Subjekt genau EIN Objekt haben kann. Nur dort
# bedeutet "zwei verschiedene Werte" einen Widerspruch statt einer
# Aufzählung: Eine Gesellschaft hat mehrere Direktoren, aber einen Sitz.
#
# Achtung auf die Richtung: Der Widerspruch zeigt sich in der Frage
# "wo ist X registriert" (Gegenrichtung), nicht in "was ist in Panama
# registriert" (Hinrichtung) — dort sind viele Treffer normal.
EIN_OBJEKT_JE_SUBJEKT = {
    # Genau ein Wert je Subjekt -> zwei Angaben sind ein Widerspruch
    "registered_in":   True,    # eine Gesellschaft, ein Sitz
    "resident_in":     True,
    "parent_of":       False,   # eine Mutter je Tochter, aber mehrere Töchter
    "subsidiary_of":   True,
    "holds_office":    True,    # ein Amt zur Zeit
    "amount_of":       True,
    "dated":           True,
    "identified_by":   False,   # mehrere Kennungen sind normal
    # Mehrere Werte sind der Normalfall -> Aufzählung, kein Widerspruch
    "beneficial_owner_of": False,
    "holds_shares_in":     False,
    "controls":            False,
    "director_of":         False,
    "employed_by":         False,
    "advisor_to":          False,
    "address_of":          False,
    "national_of":         False,
    "family_of":           False,
    "associate_of":        False,
    "paid_to":             False,
    "contracted_with":     False,
    "listed_in":           False,
    "operates_vessel":     False,
    "sanctioned_by":       False,
}


class Beleglage(str, Enum):
    """Epistemischer Status eines Fakts. Ergibt sich aus den Aussagen."""
    BESTAETIGT = "BESTAETIGT"          # >= 2 unabhängige Quellen
    EINFACH_BELEGT = "EINFACH_BELEGT"  # genau eine Quelle
    UMSTRITTEN = "UMSTRITTEN"          # funktionales Prädikat, Quellen uneins
    WIDERRUFEN = "WIDERRUFEN"          # alle tragenden Aussagen zurückgezogen


@dataclass
class Fakt:
    """Abgeleitetes Bündel von Aussagen."""
    fact_id: str
    subjekt: str
    praedikat: str
    objekt: str
    s_cluster: str
    o_cluster: str
    beleglage: Beleglage
    quellen: list = field(default_factory=list)     # unabhängige Quellen
    aussagen: int = 0
    widersprueche: list = field(default_factory=list)
    umkehr: bool = False

    @property
    def unabhaengige_quellen(self) -> int:
        return len(self.quellen)

    @property
    def antwort(self) -> str:
        """Die gesuchte Seite — je nach Fragerichtung Subjekt oder Objekt."""
        return self.objekt if self.umkehr else self.subjekt

    @property
    def gefragt(self) -> str:
        return self.subjekt if self.umkehr else self.objekt


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
  schluessel TEXT PRIMARY KEY, wert TEXT);

CREATE TABLE IF NOT EXISTS dokument (
  doc_id      TEXT PRIMARY KEY,
  titel       TEXT NOT NULL,
  quelle      TEXT NOT NULL,
  stufe       INTEGER NOT NULL,
  sha256      TEXT NOT NULL,
  pfad        TEXT,
  erfasst_von TEXT,
  ts          REAL,
  widerrufen  INTEGER DEFAULT 0,
  widerruf_grund TEXT);

CREATE TABLE IF NOT EXISTS aussage (
  aussage_id  TEXT PRIMARY KEY,
  doc_id      TEXT NOT NULL REFERENCES dokument(doc_id),
  s_key       TEXT NOT NULL,
  praedikat   TEXT NOT NULL,
  o_key       TEXT NOT NULL,
  s_anzeige   TEXT NOT NULL,
  o_anzeige   TEXT NOT NULL,
  fundstelle  TEXT,
  zitat       TEXT,
  erfasst_von TEXT,
  ts          REAL,
  konfidenz   REAL DEFAULT 1.0,
  widerrufen  INTEGER DEFAULT 0,
  widerruf_grund TEXT);

-- Entity Resolution: Schluessel -> Cluster. Verschmelzen ist ein UPDATE.
CREATE TABLE IF NOT EXISTS cluster (
  schluessel  TEXT PRIMARY KEY,
  cluster_id  TEXT NOT NULL,
  anzeige     TEXT NOT NULL,
  typ         TEXT);

CREATE TABLE IF NOT EXISTS er_protokoll (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  art TEXT, a TEXT, b TEXT, pruefer TEXT, begruendung TEXT, ts REAL);

-- Korrekturprotokoll. Auch eine geloeschte Aussage hinterlaesst hier eine
-- Spur: Der Inhalt ist weg, die Tatsache der Loeschung nicht.
CREATE TABLE IF NOT EXISTS korrektur (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  aussage_id TEXT, art TEXT, doc_id TEXT,
  vorher TEXT, nachher TEXT, pruefer TEXT, begruendung TEXT, ts REAL);

CREATE TABLE IF NOT EXISTS pruefung (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fact_id TEXT, ergebnis TEXT, pruefer TEXT, notiz TEXT, ts REAL);

CREATE INDEX IF NOT EXISTS i_aussage_po  ON aussage(praedikat, o_key);
CREATE INDEX IF NOT EXISTS i_aussage_sp  ON aussage(s_key, praedikat);
CREATE INDEX IF NOT EXISTS i_aussage_s   ON aussage(s_key);
CREATE INDEX IF NOT EXISTS i_aussage_o   ON aussage(o_key);
CREATE INDEX IF NOT EXISTS i_aussage_doc ON aussage(doc_id);
CREATE INDEX IF NOT EXISTS i_cluster_cid ON cluster(cluster_id);
"""


class Store:
    """SQLite-Ablage im Aussage-Modell."""

    def __init__(self, pfad: str | Path = ":memory:",
                 resolver: EntityResolver | None = None,
                 db: sqlite3.Connection | None = None):
        """`db` uebernimmt eine bestehende Verbindung — so kann der Speicher
        in einer entschluesselten In-Memory-Datenbank leben, ohne dass je
        Klartext auf die Platte gelangt."""
        self.pfad = str(pfad)
        self.db = db if db is not None else sqlite3.connect(
            self.pfad, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)
        self.resolver = resolver or EntityResolver()
        self.db.execute(
            "INSERT OR REPLACE INTO meta VALUES ('schema', ?)", (SCHEMA_VERSION,))
        self.db.execute(
            "INSERT OR REPLACE INTO meta VALUES ('resolver', ?)",
            (self.resolver.fingerprint(),))
        self.db.commit()

    # ------------------------------------------------------------ Cluster
    def cluster_von(self, roh: str, typ: str = "AUTO") -> str:
        """Kanonischer Cluster einer Entität. Legt ihn bei Bedarf an."""
        k = self.resolver.register(roh, typ)
        zeile = self.db.execute(
            "SELECT cluster_id FROM cluster WHERE schluessel=?", (k,)).fetchone()
        if zeile:
            return zeile["cluster_id"]
        self.db.execute(
            "INSERT INTO cluster VALUES (?,?,?,?)", (k, k, roh.strip(), typ))
        return k

    def anzeige(self, cluster_id: str) -> str:
        z = self.db.execute(
            "SELECT anzeige FROM cluster WHERE cluster_id=? ORDER BY schluessel "
            "LIMIT 1", (cluster_id,)).fetchone()
        return z["anzeige"] if z else cluster_id

    def verschmelzen(self, von_key: str, nach_key: str, *, pruefer: str,
                     begruendung: str) -> dict:
        """Bestätigte Verschmelzung. Ein UPDATE, keine Neuindizierung."""
        ziel = self.db.execute(
            "SELECT cluster_id FROM cluster WHERE schluessel=?",
            (nach_key,)).fetchone()
        quelle = self.db.execute(
            "SELECT cluster_id FROM cluster WHERE schluessel=?",
            (von_key,)).fetchone()
        if not ziel or not quelle:
            raise KeyError("unbekannter Schlüssel")
        n = self.db.execute(
            "UPDATE cluster SET cluster_id=? WHERE cluster_id=?",
            (ziel["cluster_id"], quelle["cluster_id"])).rowcount
        self.db.execute(
            "INSERT INTO er_protokoll (art,a,b,pruefer,begruendung,ts) "
            "VALUES ('verschmolzen',?,?,?,?,?)",
            (von_key, nach_key, pruefer, begruendung, time.time()))
        self.db.commit()
        return {"verschoben": n, "cluster": ziel["cluster_id"]}

    def trennen_festhalten(self, a: str, b: str, *, pruefer: str,
                           begruendung: str) -> None:
        """Hält fest, dass zwei ähnliche Entitäten NICHT dieselbe sind."""
        self.db.execute(
            "INSERT INTO er_protokoll (art,a,b,pruefer,begruendung,ts) "
            "VALUES ('getrennt',?,?,?,?,?)", (a, b, pruefer, begruendung,
                                              time.time()))
        self.db.commit()

    def getrennt_erklaert(self) -> set:
        return {(z["a"], z["b"]) for z in self.db.execute(
            "SELECT a,b FROM er_protokoll WHERE art='getrennt'")}

    # ----------------------------------------------------------- Dokumente
    def dokument_aufnehmen(self, dok) -> str:
        self.db.execute(
            "INSERT OR REPLACE INTO dokument (doc_id,titel,quelle,stufe,sha256,"
            "pfad,erfasst_von,ts,widerrufen) VALUES (?,?,?,?,?,?,?,?,0)",
            (dok.doc_id, dok.titel, dok.quelle, int(dok.stufe), dok.sha256,
             dok.pfad, dok.erfasst_von, dok.ts))
        self.db.commit()
        return dok.doc_id

    def dokument_widerrufen(self, doc_id: str, grund: str) -> dict:
        """Zieht ein Dokument samt aller daraus abgeleiteten Aussagen zurück.

        Das ist der Fall, der im Fakten-zentrierten Modell praktisch nicht
        auszuführen war: eine gefälschte Übergabe, eine zurückgezogene
        Registerauskunft, ein widerrufenes Hintergrundgespräch.
        """
        betroffen = [z["aussage_id"] for z in self.db.execute(
            "SELECT aussage_id FROM aussage WHERE doc_id=?", (doc_id,))]
        self.db.execute(
            "UPDATE dokument SET widerrufen=1, widerruf_grund=? WHERE doc_id=?",
            (grund, doc_id))
        self.db.execute(
            "UPDATE aussage SET widerrufen=1, widerruf_grund=? WHERE doc_id=?",
            (f"Dokument widerrufen: {grund}", doc_id))
        self.db.commit()
        return {"doc_id": doc_id, "aussagen": len(betroffen),
                "fakten": len({self._fact_id_von_aussage(a) for a in betroffen})}

    def _fact_id_von_aussage(self, aussage_id: str) -> str:
        z = self.db.execute(
            "SELECT s_key,praedikat,o_key FROM aussage WHERE aussage_id=?",
            (aussage_id,)).fetchone()
        return self.fact_id(self._cid(z["s_key"]), z["praedikat"],
                            self._cid(z["o_key"]))

    def _cid(self, key: str) -> str:
        z = self.db.execute(
            "SELECT cluster_id FROM cluster WHERE schluessel=?", (key,)).fetchone()
        return z["cluster_id"] if z else key

    # ------------------------------------------------------------ Aussagen
    @staticmethod
    def fact_id(s_cluster: str, praedikat: str, o_cluster: str) -> str:
        """Richtungsunabhängige Faktenkennung über Cluster."""
        if ist_umkehr(praedikat):
            s_cluster, praedikat, o_cluster = (o_cluster,
                                               INVERSE_OF[praedikat], s_cluster)
        return "f:" + hashlib.sha256(
            f"{s_cluster}|{praedikat}|{o_cluster}".encode()).hexdigest()[:22]

    def behaupten(self, doc_id: str, subjekt: str, praedikat: str, objekt: str,
                  *, fundstelle: str = "", zitat: str | None = None,
                  erfasst_von: str = "", konfidenz: float = 1.0) -> str:
        """Legt eine Aussage ab und liefert die abgeleitete Faktenkennung.

        Gespiegelte Tripel sind nicht nötig — die Gegenrichtung ist eine
        Abfrage über den anderen Index.
        """
        if ist_umkehr(praedikat):
            subjekt, praedikat, objekt = objekt, INVERSE_OF[praedikat], subjekt
        st, ot = typen_fuer(praedikat)
        s_key = self.resolver.register(subjekt, st)
        o_key = self.resolver.register(objekt, ot)
        self.cluster_von(subjekt, st)
        self.cluster_von(objekt, ot)

        aid = "a:" + hashlib.sha256(
            f"{doc_id}|{s_key}|{praedikat}|{o_key}|{fundstelle}".encode()
        ).hexdigest()[:22]
        self.db.execute(
            "INSERT OR REPLACE INTO aussage (aussage_id,doc_id,s_key,praedikat,"
            "o_key,s_anzeige,o_anzeige,fundstelle,zitat,erfasst_von,ts,"
            "konfidenz,widerrufen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (aid, doc_id, s_key, praedikat, o_key, subjekt.strip(),
             objekt.strip(), fundstelle, zitat, erfasst_von, time.time(),
             konfidenz))
        self.db.commit()
        return self.fact_id(self._cid(s_key), praedikat, self._cid(o_key))

    def aussage_widerrufen(self, aussage_id: str, grund: str,
                           pruefer: str = "") -> dict:
        """Nimmt eine Aussage inhaltlich zurueck.

        Die Aussage bleibt sichtbar und zaehlt als WIDERRUFEN. Das ist der
        richtige Weg, wenn sich eine Behauptung als falsch herausstellt —
        wer sie spurlos entfernte, verfaelschte die Beleglage rueckwirkend.
        """
        z = self._aussage(aussage_id)
        self.db.execute(
            "UPDATE aussage SET widerrufen=1, widerruf_grund=? WHERE aussage_id=?",
            (grund, aussage_id))
        self._korrektur("widerrufen", aussage_id, z, None, pruefer, grund)
        self.db.commit()
        return {"aussage_id": aussage_id, "art": "widerrufen"}

    def _aussage(self, aussage_id: str):
        z = self.db.execute("SELECT * FROM aussage WHERE aussage_id=?",
                            (aussage_id,)).fetchone()
        if z is None:
            raise KeyError(f"unbekannte Aussage {aussage_id}")
        return z

    @staticmethod
    def _kurz(z) -> str:
        if z is None:
            return ""
        return (f"{z['s_anzeige']} · {z['praedikat']} · {z['o_anzeige']}"
                f"  [{z['fundstelle'] or '—'}]")

    def _korrektur(self, art: str, aussage_id: str, vorher, nachher,
                   pruefer: str, begruendung: str) -> None:
        self.db.execute(
            "INSERT INTO korrektur (aussage_id,art,doc_id,vorher,nachher,"
            "pruefer,begruendung,ts) VALUES (?,?,?,?,?,?,?,?)",
            (aussage_id, art, vorher["doc_id"] if vorher is not None else None,
             self._kurz(vorher), self._kurz(nachher), pruefer, begruendung,
             time.time()))

    def aussage_verwerfen(self, aussage_id: str, grund: str,
                          pruefer: str = "") -> dict:
        """Entfernt eine irrtuemlich erfasste Aussage vollstaendig.

        Fuer Tippfehler und Fehlgriffe — nicht fuer inhaltliche Ruecknahmen.
        Der Inhalt verschwindet, die Tatsache der Loeschung bleibt im
        Korrekturprotokoll stehen. Ohne diese Spur waere die Belegkette
        nachtraeglich frisierbar.
        """
        z = self._aussage(aussage_id)
        self._korrektur("verworfen", aussage_id, z, None, pruefer, grund)
        self.db.execute("DELETE FROM aussage WHERE aussage_id=?", (aussage_id,))
        self.db.commit()
        return {"aussage_id": aussage_id, "art": "verworfen"}

    def aussage_aendern(self, aussage_id: str, *, subjekt: str | None = None,
                        praedikat: str | None = None, objekt: str | None = None,
                        fundstelle: str | None = None, zitat: str | None = None,
                        grund: str = "", pruefer: str = "") -> dict:
        """Korrigiert eine Aussage. Die alte Fassung steht im Protokoll.

        Weil die Kennung aus Dokument, Schluesseln und Fundstelle folgt,
        entsteht technisch eine neue Aussage; die alte wird entfernt.
        """
        z = self._aussage(aussage_id)
        neu_s = (subjekt if subjekt is not None else z["s_anzeige"]).strip()
        neu_p = praedikat if praedikat is not None else z["praedikat"]
        neu_o = (objekt if objekt is not None else z["o_anzeige"]).strip()
        neu_f = fundstelle if fundstelle is not None else z["fundstelle"]
        neu_z = zitat if zitat is not None else z["zitat"]
        if not neu_s or not neu_o:
            raise ValueError("Subjekt und Objekt dürfen nicht leer sein")
        if neu_p not in PREDICATE_SCHEMA:
            raise ValueError(f"unbekanntes Prädikat {neu_p}")

        self.db.execute("DELETE FROM aussage WHERE aussage_id=?", (aussage_id,))
        fid = self.behaupten(z["doc_id"], neu_s, neu_p, neu_o,
                             fundstelle=neu_f or "", zitat=neu_z,
                             erfasst_von=z["erfasst_von"],
                             konfidenz=z["konfidenz"])
        nachher = self.db.execute(
            "SELECT * FROM aussage WHERE doc_id=? ORDER BY ts DESC LIMIT 1",
            (z["doc_id"],)).fetchone()
        self._korrektur("geaendert", aussage_id, z, nachher, pruefer, grund)
        self.db.commit()
        return {"vorher": aussage_id, "fact_id": fid,
                "aussage": self._kurz(nachher), "art": "geaendert"}

    def korrekturen(self, grenze: int = 50) -> list[dict]:
        return [dict(z) for z in self.db.execute(
            "SELECT * FROM korrektur ORDER BY ts DESC LIMIT ?", (grenze,))]

    # ------------------------------------------------------------- Abfrage
    _BASIS = """
        SELECT a.*, c1.cluster_id AS s_cid, c2.cluster_id AS o_cid,
               d.quelle AS quelle, d.stufe AS stufe, d.widerrufen AS doc_weg
        FROM aussage a
        JOIN cluster c1 ON c1.schluessel = a.s_key
        JOIN cluster c2 ON c2.schluessel = a.o_key
        JOIN dokument d ON d.doc_id = a.doc_id
    """

    def frage(self, praedikat: str, objekt: str) -> list[Fakt]:
        """Alle Fakten zu (Prädikat, Objekt). Beide Richtungen möglich.

        Liefert eine Liste — Mehrdeutigkeit ist hier keine Schwäche des
        Speichers, sondern eine Eigenschaft der Welt.
        """
        umkehr = ist_umkehr(praedikat)
        basis = INVERSE_OF[praedikat] if umkehr else praedikat
        _, ot = typen_fuer(praedikat)
        cid = self._cid(self.resolver.key(objekt, ot))
        spalte = "s_cid" if umkehr else "o_cid"

        zeilen = self.db.execute(
            f"{self._BASIS} WHERE a.praedikat=? AND {spalte}=?",
            (basis, cid)).fetchall()
        return self._buendeln(zeilen, basis, umkehr)

    def _buendeln(self, zeilen, praedikat: str, umkehr: bool) -> list[Fakt]:
        gruppen: dict[tuple, list] = {}
        for z in zeilen:
            gruppen.setdefault((z["s_cid"], z["o_cid"]), []).append(z)

        fakten = []
        for (s_cid, o_cid), gruppe in gruppen.items():
            aktiv = [z for z in gruppe if not z["widerrufen"] and not z["doc_weg"]]
            quellen = sorted({z["quelle"] for z in aktiv})
            if not aktiv:
                lage = Beleglage.WIDERRUFEN
            elif len(quellen) >= 2:
                lage = Beleglage.BESTAETIGT
            else:
                lage = Beleglage.EINFACH_BELEGT

            f = Fakt(fact_id=self.fact_id(s_cid, praedikat, o_cid),
                     subjekt=self.anzeige(s_cid), praedikat=praedikat,
                     objekt=self.anzeige(o_cid), s_cluster=s_cid,
                     o_cluster=o_cid, beleglage=lage, quellen=quellen,
                     aussagen=len(gruppe), umkehr=umkehr)
            fakten.append(f)

        # Widerspruch nur, wenn das Prädikat je Subjekt einen Wert erlaubt
        # UND wir in dieser Richtung fragen.
        if EIN_OBJEKT_JE_SUBJEKT.get(praedikat) and umkehr:
            lebend = [f for f in fakten if f.beleglage is not Beleglage.WIDERRUFEN]
            if len(lebend) > 1:
                for f in lebend:
                    f.beleglage = Beleglage.UMSTRITTEN
                    f.widersprueche = [g.antwort for g in lebend
                                       if g.fact_id != f.fact_id]
        rang = {Beleglage.BESTAETIGT: 0, Beleglage.UMSTRITTEN: 1,
                Beleglage.EINFACH_BELEGT: 2, Beleglage.WIDERRUFEN: 3}
        return sorted(fakten, key=lambda f: (rang[f.beleglage], -f.aussagen))

    def fakt(self, fact_id: str) -> Fakt | None:
        for z in self.db.execute(f"{self._BASIS}"):
            f_id = self.fact_id(z["s_cid"], z["praedikat"], z["o_cid"])
            if f_id == fact_id:
                return self._buendeln(
                    [x for x in self.db.execute(
                        f"{self._BASIS} WHERE a.praedikat=?", (z["praedikat"],))
                     if self.fact_id(x["s_cid"], x["praedikat"],
                                     x["o_cid"]) == fact_id],
                    z["praedikat"], False)[0]
        return None

    def aussagen_zu(self, fact_id: str) -> list[sqlite3.Row]:
        raus = []
        for z in self.db.execute(self._BASIS):
            if self.fact_id(z["s_cid"], z["praedikat"], z["o_cid"]) == fact_id:
                raus.append(z)
        return raus

    def kanten(self, cluster_id: str) -> list[sqlite3.Row]:
        """Alle Aussagen an einem Cluster, in beide Richtungen."""
        return self.db.execute(
            f"{self._BASIS} WHERE (c1.cluster_id=? OR c2.cluster_id=?) "
            "AND a.widerrufen=0 AND d.widerrufen=0",
            (cluster_id, cluster_id)).fetchall()

    # ------------------------------------------------------------- Bestand
    def entitaeten(self) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT cluster_id, MIN(anzeige) AS anzeige, COUNT(*) AS teile, "
            "MIN(typ) AS typ FROM cluster GROUP BY cluster_id "
            "ORDER BY anzeige").fetchall()

    def stats(self) -> dict:
        g = lambda q: self.db.execute(q).fetchone()[0]
        return {
            "dokumente": g("SELECT COUNT(*) FROM dokument"),
            "widerrufene_dokumente": g(
                "SELECT COUNT(*) FROM dokument WHERE widerrufen=1"),
            "aussagen": g("SELECT COUNT(*) FROM aussage"),
            "aktive_aussagen": g(
                "SELECT COUNT(*) FROM aussage a JOIN dokument d USING(doc_id) "
                "WHERE a.widerrufen=0 AND d.widerrufen=0"),
            "entitaeten": g("SELECT COUNT(DISTINCT cluster_id) FROM cluster"),
            "schluessel": g("SELECT COUNT(*) FROM cluster"),
            "verschmelzungen": g(
                "SELECT COUNT(*) FROM er_protokoll WHERE art='verschmolzen'"),
            "resolver": self.resolver.fingerprint(),
            "schema": SCHEMA_VERSION,
        }

    def sichern(self, ziel: str | Path) -> dict:
        ziel = Path(ziel)
        andere = sqlite3.connect(ziel)
        self.db.backup(andere)
        andere.close()
        roh = ziel.read_bytes()
        return {"datei": str(ziel), "bytes": len(roh),
                "sha256": hashlib.sha256(roh).hexdigest()}

    def close(self) -> None:
        self.db.close()
