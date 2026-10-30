"""
IndraNet — Anschluss OpenSanctions
===================================

OpenSanctions veröffentlicht Sanktionslisten, politisch exponierte Personen
und verbundene Entitäten im FollowTheMoney-Modell. Die Massendaten sind
ohne Login und ohne API-Schlüssel abrufbar; der Matching-Dienst `yente`
steht unter MIT-Lizenz und lässt sich selbst betreiben.

WARUM MASSENDATEN UND NICHT DIE ABFRAGE-API
-------------------------------------------
Eine Screening-Anfrage verrät, wen Sie prüfen. Bei einer laufenden
Recherche ist die Namensliste das Rechercheziel — dieselbe Größe, die wir
in der Föderation mit einem Oblivious PRF schützen. Also: Korpus einmal
herunterladen, Abgleich lokal.

LIZENZ — WICHTIG
----------------
Die Daten stehen unter CC-BY-NC (Namensnennung, nicht kommerziell). Für
eine Redaktion ist das unproblematisch. Wer IndraNet mit vorbefülltem
OpenSanctions-Bestand VERKAUFT, braucht eine Datenlizenz von
OpenSanctions. Der Programmcode dort ist MIT-lizenziert; die Daten sind es
nicht. Diese Unterscheidung ist leicht zu übersehen und teuer.

DATENFORMAT
-----------
Entitätenstrom: eine JSON-Zeile je Entität, Felder `id`, `schema`,
`properties` (alle Werte mehrwertig). Entitäten sind nicht nur Personen und
Firmen — auch Sanktionen, Beteiligungen und Ämter sind Entitäten und
bilden damit einen Graphen.

Beziehungsentitäten lassen sich direkt auf IndraNet-Prädikate abbilden:

    Ownership     owner       →  asset          beneficial_owner_of
    Directorship  director    →  organization   director_of
    Company       jurisdiction                  registered_in

IDENTITÄTEN ÄNDERN SICH
-----------------------
OpenSanctions führt Entitäten zusammen; dabei entstehen neue Cluster-IDs.
Deshalb wird neben der ID auch die `referents`-Liste geführt, sonst
verliert man beim nächsten Abgleich die Zuordnung.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from resolver import block_key, strict_key
from sources import Quelle, Treffer

# Merkmale, die OpenSanctions in `topics` führt und die für eine Recherche
# den Unterschied machen.
INTERESSANTE_TOPICS = {
    "sanction": "sanktioniert",
    "sanction.linked": "sanktionsnah",
    "role.pep": "politisch exponiert",
    "role.rca": "Angehöriger einer PEP",
    "crime": "Straftatvorwurf",
    "crime.fin": "Finanzdelikt",
    "crime.fraud": "Betrugsvorwurf",
    "poi": "Person von Interesse",
    "wanted": "zur Fahndung ausgeschrieben",
    "export.control": "Ausfuhrkontrolle",
}

BEZIEHUNGEN = {
    "Ownership":     ("owner", "asset", "beneficial_owner_of"),
    "Directorship":  ("director", "organization", "director_of"),
    "UnknownLink":   ("subject", "object", None),
}


class OpenSanctions(Quelle):
    art = "opensanctions"
    lizenz = "CC-BY-NC (Daten) · MIT (Code)"
    lokal = True

    # Standardsammlung; Datumsangabe im Pfad liefert historische Stände.
    STANDARD = ("https://data.opensanctions.org/datasets/latest/default/"
                "entities.ftm.json")

    def __init__(self, store=None, name: str = "OpenSanctions"):
        super().__init__(name, store)
        self.entitaeten: dict[str, dict] = {}      # id -> Rohdatensatz
        self.namensindex: dict[str, list] = {}     # block_key -> [id, ...]
        self.referenzen: dict[str, str] = {}       # alte id -> aktuelle id

    # ------------------------------------------------------------- Abrufen
    def holen(self, quelle: str | Path | None = None,
              grenze: int | None = None) -> dict:
        """Lädt den Entitätenstrom und baut den lokalen Namensindex."""
        quelle = quelle or self.STANDARD
        self.entitaeten.clear()
        self.namensindex.clear()
        self.referenzen.clear()
        try:
            for e in self._lade_zeilen(quelle, grenze):
                self._aufnehmen(e)
            self.datensaetze = len(self.entitaeten)
            self.stand = time.strftime("%Y-%m-%d")
            self.melde(True)
        except Exception as e:                                # noqa: BLE001
            self.melde(False, f"{type(e).__name__}: {e}")
            raise
        return {"entitaeten": len(self.entitaeten),
                "namen": len(self.namensindex),
                "stand": self.stand, "quelle": str(quelle)}

    def _aufnehmen(self, e: dict) -> None:
        eid = e.get("id")
        if not eid:
            return
        self.entitaeten[eid] = e
        for alt in e.get("referents", []):
            self.referenzen[alt] = eid
        props = e.get("properties", {})
        typ = "PERSON" if e.get("schema") == "Person" else "ORG"
        for feld in ("name", "alias", "previousName", "weakAlias"):
            for n in props.get(feld, []):
                bk = block_key(n, typ)
                if bk:
                    self.namensindex.setdefault(bk, []).append(eid)

    # ------------------------------------------------------------ Abgleich
    def abgleichen(self, pod, schwelle: float = 0.0) -> list[Treffer]:
        """Prüft die Entitäten des Pods gegen den lokalen Korpus.

        Es verlässt nichts das Gerät. Die Namensliste des Pods wird nirgends
        hingeschickt.
        """
        if not self.namensindex:
            raise RuntimeError("Zuerst holen() aufrufen")

        treffer: list[Treffer] = []
        for z in pod.store.entitaeten():
            anzeige = z["anzeige"]
            typ = z["typ"] or "AUTO"
            bk = block_key(anzeige, "PERSON" if typ == "PERSON" else "ORG")
            for eid in self.namensindex.get(bk, []):
                e = self.entitaeten[eid]
                props = e.get("properties", {})
                topics = props.get("topics", [])
                merkmale = [INTERESSANTE_TOPICS[t] for t in topics
                            if t in INTERESSANTE_TOPICS]
                art = ("sanktion" if any(t.startswith("sanction")
                                         for t in topics)
                       else "pep" if any(t.startswith("role.") for t in topics)
                       else "erwaehnung")
                fremd = (props.get("name") or [e.get("caption", eid)])[0]
                treffer.append(Treffer(
                    entitaet=anzeige, cluster_id=z["cluster_id"],
                    quelle=self.name, fremd_id=eid, fremd_name=fremd,
                    art=art, merkmale=merkmale or ["gelistet"],
                    score=1.0 if strict_key(anzeige) == strict_key(fremd)
                    else 0.85,
                    zusatz={"schema": e.get("schema"),
                            "laender": props.get("country", []),
                            "datensaetze": e.get("datasets", []),
                            "topics": topics}))
        treffer.sort(key=lambda t: (-t.score, t.entitaet))
        return treffer

    # -------------------------------------------------- Beziehungen ziehen
    def beziehungen(self, nur_zu: set | None = None,
                    beide_seiten: bool = True) -> list[tuple]:
        """Wandelt Beziehungsentitäten in IndraNet-Tripel.

        `nur_zu` beschränkt auf Entitäten, die im Pod vorkommen — sonst
        holen Sie sich den halben Weltkonzern-Graphen ins Haus.

        `beide_seiten=True` (Vorgabe) verlangt, dass BEIDE Enden der
        Beziehung bekannt sind. Sonst wandern über eine bekannte Person
        beliebig viele unbekannte Gesellschaften mit — bei einer PEP mit
        vierzig Mandaten sind das vierzig neue Entitäten, die niemand
        angefordert hat. Mit `False` erhalten Sie bewusst die
        Nachbarschaft, etwa zur Erweiterung einer Recherche.
        """
        raus = []
        for e in self.entitaeten.values():
            regel = BEZIEHUNGEN.get(e.get("schema"))
            if not regel:
                continue
            von_feld, nach_feld, praedikat = regel
            if praedikat is None:
                continue
            props = e.get("properties", {})
            for a in props.get(von_feld, []):
                for b in props.get(nach_feld, []):
                    na, nb = self._namen(a), self._namen(b)
                    if not na or not nb:
                        continue
                    if nur_zu:
                        a_da, b_da = block_key(na) in nur_zu, block_key(nb) in nur_zu
                        if beide_seiten and not (a_da and b_da):
                            continue
                        if not beide_seiten and not (a_da or b_da):
                            continue
                    raus.append((na, praedikat, nb))

        # Sitzland aus Company-Entitäten
        for e in self.entitaeten.values():
            if e.get("schema") not in ("Company", "Organization"):
                continue
            props = e.get("properties", {})
            namen = props.get("name", [])
            if not namen:
                continue
            if nur_zu and block_key(namen[0]) not in nur_zu:
                continue
            for j in props.get("jurisdiction", []):
                raus.append((namen[0], "registered_in", j.upper()))
        return list(dict.fromkeys(raus))

    def _namen(self, verweis) -> str | None:
        """Löst eine Entitätsreferenz zum Namen auf.

        Die API liefert teils verschachtelte Objekte, die Massendaten
        blosse IDs — beides wird akzeptiert.
        """
        if isinstance(verweis, dict):
            props = verweis.get("properties", {})
            namen = props.get("name") or [verweis.get("caption")]
            return namen[0] if namen and namen[0] else None
        eid = self.referenzen.get(verweis, verweis)
        e = self.entitaeten.get(eid)
        if not e:
            return None
        props = e.get("properties", {})
        namen = props.get("name") or [e.get("caption")]
        return namen[0] if namen and namen[0] else None

    # ----------------------------------------------------------- Bericht
    @staticmethod
    def bericht(treffer: list[Treffer]) -> dict:
        nach_art: dict[str, int] = {}
        for t in treffer:
            nach_art[t.art] = nach_art.get(t.art, 0) + 1
        return {"treffer": len(treffer), "nach_art": nach_art,
                "entitaeten": len({t.cluster_id for t in treffer}),
                "sanktioniert": sorted({t.entitaet for t in treffer
                                        if t.art == "sanktion"}),
                "politisch_exponiert": sorted({t.entitaet for t in treffer
                                               if t.art == "pep"})}
