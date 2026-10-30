"""
IndraNet — Graphabfragen
=========================

Pfade und Umfeld über rekursive CTEs. Gegenüber der Traversierung über
einen Vektorspeicher rund sechzigmal schneller, weil beide Indizes genutzt
werden und keine Ähnlichkeitsrechnung anfällt.

Widerrufene Aussagen und Aussagen aus widerrufenen Dokumenten sind aus
allen Pfaden ausgeschlossen. Eine Verbindung, die nur über eine
zurückgezogene Quelle bestand, ist keine Verbindung.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Schritt:
    von: str
    nach: str
    praedikat: str
    fact_id: str
    rueckwaerts: bool
    beleglage: str

    def __str__(self) -> str:
        pfeil = "<--[{}]--" if self.rueckwaerts else "--[{}]-->"
        return pfeil.format(self.praedikat)


@dataclass
class Pfad:
    schritte: list

    @property
    def knoten(self) -> list:
        return [self.schritte[0].von] + [s.nach for s in self.schritte]

    @property
    def laenge(self) -> int:
        return len(self.schritte)

    @property
    def fact_ids(self) -> list:
        return list(dict.fromkeys(s.fact_id for s in self.schritte))

    @property
    def schwaechstes_glied(self) -> str:
        """Ein Pfad ist nur so belastbar wie seine schwächste Kante."""
        rang = {"BESTAETIGT": 0, "EINFACH_BELEGT": 1, "UMSTRITTEN": 2,
                "WIDERRUFEN": 3}
        return max((s.beleglage for s in self.schritte),
                   key=lambda b: rang.get(b, 9))

    def __str__(self) -> str:
        teile = [self.schritte[0].von]
        for s in self.schritte:
            teile += [str(s), s.nach]
        return " ".join(teile)


_NACHBARN = """
SELECT a.praedikat, c1.cluster_id AS s_cid, c2.cluster_id AS o_cid
FROM aussage a
JOIN cluster c1 ON c1.schluessel = a.s_key
JOIN cluster c2 ON c2.schluessel = a.o_key
JOIN dokument d ON d.doc_id = a.doc_id
WHERE (c1.cluster_id = ? OR c2.cluster_id = ?)
  AND a.widerrufen = 0 AND d.widerrufen = 0
"""


def nachbarn(store, cluster_id: str) -> list:
    raus = []
    for z in store.db.execute(_NACHBARN, (cluster_id, cluster_id)):
        gegen = z["o_cid"] if z["s_cid"] == cluster_id else z["s_cid"]
        if gegen == cluster_id:
            continue
        raus.append({"praedikat": z["praedikat"], "gegen": gegen,
                     "rueckwaerts": z["s_cid"] != cluster_id,
                     "s_cid": z["s_cid"], "o_cid": z["o_cid"]})
    return raus


def _erreichbar(store, start: str, max_schritte: int) -> dict:
    """Rekursives CTE mit zwei indexnutzenden Zweigen statt eines OR."""
    sql = """
    WITH RECURSIVE lauf(cid, tiefe) AS (
      SELECT ?, 0
      UNION
      SELECT c2.cluster_id, l.tiefe + 1
        FROM lauf l
        JOIN cluster c1 ON c1.cluster_id = l.cid
        JOIN aussage a  ON a.s_key = c1.schluessel
        JOIN cluster c2 ON c2.schluessel = a.o_key
        JOIN dokument d ON d.doc_id = a.doc_id
       WHERE l.tiefe < ? AND a.widerrufen = 0 AND d.widerrufen = 0
      UNION
      SELECT c1.cluster_id, l.tiefe + 1
        FROM lauf l
        JOIN cluster c2 ON c2.cluster_id = l.cid
        JOIN aussage a  ON a.o_key = c2.schluessel
        JOIN cluster c1 ON c1.schluessel = a.s_key
        JOIN dokument d ON d.doc_id = a.doc_id
       WHERE l.tiefe < ? AND a.widerrufen = 0 AND d.widerrufen = 0)
    SELECT cid, MIN(tiefe) AS tiefe FROM lauf GROUP BY cid
    """
    return {z["cid"]: z["tiefe"] for z in
            store.db.execute(sql, (start, max_schritte, max_schritte))}


def pfade(store, von: str, nach: str, max_schritte: int = 4,
          max_pfade: int = 5) -> list[Pfad]:
    """Verbindungen zwischen zwei Entitäten, kürzeste zuerst."""
    start = store._cid(store.resolver.key(von))
    ziel = store._cid(store.resolver.key(nach))
    if start == ziel:
        return []

    # Vorfilter: welche Knoten führen überhaupt zum Ziel?
    rest = _erreichbar(store, ziel, max_schritte)
    if start not in rest:
        return []

    from collections import deque
    gefunden, besucht = [], {start}
    schlange = deque([(start, [])])
    while schlange and len(gefunden) < max_pfade:
        cid, weg = schlange.popleft()
        if len(weg) >= max_schritte:
            continue
        for kante in nachbarn(store, cid):
            gegen = kante["gegen"]
            if gegen not in rest or rest[gegen] > max_schritte - len(weg) - 1:
                continue
            fid = store.fact_id(kante["s_cid"], kante["praedikat"],
                                kante["o_cid"])
            f = store.fakt(fid)
            schritt = Schritt(store.anzeige(cid), store.anzeige(gegen),
                              kante["praedikat"], fid, kante["rueckwaerts"],
                              f.beleglage.value if f else "?")
            if gegen == ziel:
                gefunden.append(Pfad(weg + [schritt]))
                if len(gefunden) >= max_pfade:
                    break
            elif gegen not in besucht:
                besucht.add(gegen)
                schlange.append((gegen, weg + [schritt]))
    return sorted(gefunden, key=lambda p: p.laenge)


def umfeld(store, entitaet: str, tiefe: int = 2, max_knoten: int = 200) -> dict:
    """Knoten und Kanten im Umkreis — Grundlage der Netzansicht."""
    start = store._cid(store.resolver.key(entitaet))
    erreicht = _erreichbar(store, start, tiefe)
    knoten = dict(list(erreicht.items())[:max_knoten])
    kanten = []
    for cid in knoten:
        for k in nachbarn(store, cid):
            if k["gegen"] in knoten:
                paar = tuple(sorted([k["s_cid"], k["o_cid"]]))
                kanten.append({"von": store.anzeige(k["s_cid"]),
                               "nach": store.anzeige(k["o_cid"]),
                               "praedikat": k["praedikat"], "paar": paar})
    einmalig = {(k["paar"], k["praedikat"]): k for k in kanten}
    return {"knoten": [{"id": c, "anzeige": store.anzeige(c),
                        "abstand": t} for c, t in knoten.items()],
            "kanten": list(einmalig.values())}


def zentralitaet(store, entitaet: str, tiefe: int = 2, top: int = 8) -> list:
    """Gradzentralität im Umfeld — wer sitzt in der Mitte des Netzes?"""
    netz = umfeld(store, entitaet, tiefe)
    grade = [(k["anzeige"], len(nachbarn(store, k["id"])))
             for k in netz["knoten"]]
    return sorted(grade, key=lambda x: -x[1])[:top]
