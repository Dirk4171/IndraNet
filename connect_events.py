"""
IndraNet — Anschluss Ereignisquellen (World Monitor u. a.)
===========================================================

IndraNet und World Monitor sitzen an entgegengesetzten Enden desselben
Problems. World Monitor bündelt den öffentlichen Weltzustand in Echtzeit —
Nachrichten, Konfliktzonen, Schiffsbewegungen, Sanktionsregime. IndraNet
hält, was Ihre Recherche behauptet, und wie gut es belegt ist. World
Monitor schreibt selbst, es habe keine private Ontologie für interne Daten;
genau die Lücke füllt IndraNet.

WAS DIESER ANSCHLUSS TUT
------------------------
Er zieht einen Ereignisstrom und prüft LOKAL, ob eine Entität aus Ihrem Pod
darin vorkommt. Ergebnis ist eine Beobachtungsliste:

    "Nordkap Shipping AS wurde gestern in einem Bericht über einen
     Schiffszwischenfall vor Zypern genannt."

WARUM ERST LOKAL ABGLEICHEN
---------------------------
Eine Beobachtungsliste ist das Rechercheziel. Wer sie einem fremden Dienst
zur Überwachung übergibt, hat den Quellenschutz an der Stelle aufgegeben,
an der er am billigsten zu verlieren ist. Also: Strom holen, lokal
abgleichen.

BEWUSST ALLGEMEIN GEHALTEN
--------------------------
Die Feldzuordnung ist einstellbar, damit derselbe Anschluss auch GDELT,
ACLED oder einen redaktionseigenen Feed bedienen kann. Das
World-Monitor-Profil unten ist nach der öffentlichen Beschreibung gebaut;
die genauen Routennamen sind gegen die laufende API zu prüfen, bevor
jemand sich darauf verlässt. `PROFILE` ist genau dafür der eine Ort, an dem
das anzupassen ist.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from resolver import block_key
from sources import Quelle, Treffer


@dataclass
class Feldzuordnung:
    """Wo im Datensatz stehen Kennung, Titel, Text, Zeit, Ort, Verweis?"""
    kennung: str = "id"
    titel: str = "title"
    text: str = "summary"
    zeit: str = "published_at"
    ort: str = "country"
    verweis: str = "url"
    kategorie: str = "category"
    entitaeten: str | None = "entities"   # falls die Quelle selbst extrahiert

    def hol(self, satz: dict, feld: str, standard=""):
        wert = satz.get(getattr(self, feld) or "", standard)
        if isinstance(wert, list):
            return ", ".join(str(x) for x in wert)
        return wert if wert is not None else standard


PROFILE = {
    # Nach der öffentlichen Beschreibung von World Monitor. Routennamen vor
    # dem Produktivbetrieb gegen die laufende API prüfen.
    "worldmonitor": Feldzuordnung(
        kennung="id", titel="title", text="summary", zeit="publishedAt",
        ort="country", verweis="url", kategorie="category",
        entitaeten="entities"),
    # GDELT-Ereignisexport
    "gdelt": Feldzuordnung(
        kennung="GLOBALEVENTID", titel="SOURCEURL", text="Actor1Name",
        zeit="SQLDATE", ort="ActionGeo_CountryCode", verweis="SOURCEURL",
        kategorie="EventCode", entitaeten=None),
    # Neutraler Rohfeed
    "generisch": Feldzuordnung(),
}

_WORT = re.compile(r"[\wÄÖÜäöüßÀ-ÿ&.\-]+", re.UNICODE)


class Ereignisquelle(Quelle):
    art = "ereignisse"
    lizenz = "je nach Betreiber prüfen"
    lokal = True

    def __init__(self, name: str = "World Monitor", store=None,
                 profil: str = "worldmonitor"):
        super().__init__(name, store)
        self.zuordnung = PROFILE.get(profil, PROFILE["generisch"])
        self.ereignisse: list[dict] = []

    # ------------------------------------------------------------- Abrufen
    def holen(self, quelle: str | Path, grenze: int | None = None,
              wurzel: str | None = None) -> dict:
        """Lädt einen Ereignisstrom. NDJSON oder JSON-Liste."""
        self.ereignisse.clear()
        try:
            pfad = str(quelle)
            self.endpunkt = pfad
            roh = self._roh_laden(pfad, wurzel)
            self.ereignisse = roh[:grenze] if grenze else roh
            self.datensaetze = len(self.ereignisse)
            self.stand = time.strftime("%Y-%m-%d %H:%M")
            self.melde(True)
        except Exception as e:                                # noqa: BLE001
            self.melde(False, f"{type(e).__name__}: {e}")
            raise
        return {"ereignisse": len(self.ereignisse), "stand": self.stand,
                "quelle": str(quelle)}

    def _roh_laden(self, pfad: str, wurzel: str | None) -> list:
        if pfad.startswith(("http://", "https://")):
            import urllib.request
            with urllib.request.urlopen(pfad, timeout=60) as a:
                inhalt = a.read().decode("utf-8")
        else:
            inhalt = Path(pfad).read_text(encoding="utf-8")
        inhalt = inhalt.strip()
        if inhalt.startswith("["):
            daten = json.loads(inhalt)
        elif inhalt.startswith("{") and "\n" not in inhalt.strip():
            daten = json.loads(inhalt)
        else:
            return [json.loads(z) for z in inhalt.splitlines() if z.strip()]
        if isinstance(daten, dict):
            daten = daten.get(wurzel or "results") or daten.get("data") or []
        return daten if isinstance(daten, list) else []

    # ------------------------------------------------------------ Abgleich
    def abgleichen(self, pod, mindestlaenge: int = 4) -> list[Treffer]:
        """Sucht Pod-Entitäten im Ereignisstrom — vollständig lokal."""
        # Index: Blockschlüssel der Pod-Entitäten -> Anzeigeform
        pod_index: dict[str, tuple] = {}
        for z in pod.store.entitaeten():
            bk = block_key(z["anzeige"])
            if bk and len(bk) >= mindestlaenge:
                pod_index[bk] = (z["anzeige"], z["cluster_id"])

        treffer: list[Treffer] = []
        for e in self.ereignisse:
            # Je Ereignis und Entitaet nur EIN Treffer. Die Wortfolgesuche
            # findet dieselbe Firma sonst mehrfach ("Nordkap Shipping AS."
            # und "Nordkap Shipping"), was eine Erwaehnung wie mehrere
            # aussehen laesst.
            gesehen: set = set()
            for bk, quelltext in self._kandidaten(e):
                if bk not in pod_index or bk in gesehen:
                    continue
                gesehen.add(bk)
                anzeige, cid = pod_index[bk]
                treffer.append(Treffer(
                    entitaet=anzeige, cluster_id=cid, quelle=self.name,
                    fremd_id=str(self.zuordnung.hol(e, "kennung")),
                    fremd_name=quelltext, art="erwaehnung",
                    merkmale=[self.zuordnung.hol(e, "kategorie", "Ereignis")],
                    score=0.9,
                    zusatz={"titel": self.zuordnung.hol(e, "titel"),
                            "zeit": self.zuordnung.hol(e, "zeit"),
                            "ort": self.zuordnung.hol(e, "ort"),
                            "verweis": self.zuordnung.hol(e, "verweis")}))
        treffer.sort(key=lambda t: str(t.zusatz.get("zeit")), reverse=True)
        return treffer

    def _kandidaten(self, e: dict) -> list[tuple]:
        """Erzeugt Blockschlüssel aus dem Ereignis.

        Liefert die Quelle bereits extrahierte Entitäten, werden nur diese
        verwendet — das ist genauer als eine Wortfolgesuche im Fließtext.
        """
        feld = self.zuordnung.entitaeten
        if feld and isinstance(e.get(feld), list) and e[feld]:
            raus = []
            for x in e[feld]:
                name = x.get("name") if isinstance(x, dict) else str(x)
                if name:
                    raus.append((block_key(name), name))
            return raus

        # Rückfall: Wortfolgen aus Titel und Text, zwei bis vier Wörter.
        text = f"{self.zuordnung.hol(e, 'titel')} {self.zuordnung.hol(e, 'text')}"
        woerter = _WORT.findall(text)
        raus = []
        for n in (4, 3, 2):
            for i in range(len(woerter) - n + 1):
                folge = " ".join(woerter[i:i + n])
                bk = block_key(folge)
                if bk:
                    raus.append((bk, folge))
        return raus

    # ------------------------------------------------------------- Bericht
    @staticmethod
    def bericht(treffer: list[Treffer]) -> dict:
        nach_entitaet: dict[str, int] = {}
        for t in treffer:
            nach_entitaet[t.entitaet] = nach_entitaet.get(t.entitaet, 0) + 1
        return {"erwaehnungen": len(treffer),
                "entitaeten": len(nach_entitaet),
                "haeufigste": sorted(nach_entitaet.items(),
                                     key=lambda x: -x[1])[:10]}
