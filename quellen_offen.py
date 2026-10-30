"""
IndraNet — Offene Datenquellen
===============================

Anschlüsse an frei zugängliche Register und Datenbestände. Sie dienen
zweierlei: Die KI kann sie während einer Recherche gezielt befragen
(Werkzeug "register_abfragen"), und ohne Claude — mit einem lokalen Modell —
sind sie zusammen mit der Websuche die einzige Recherchegrundlage.

    gleif           Global Legal Entity Identifier: Firmen, Sitz,
                    Mutter- und Tochtergesellschaften (CC0)
    offshore_leaks  ICIJ Offshore Leaks: Panama, Paradise, Pandora Papers
                    (ODbL, Nennung ICIJ)
    opensanctions   Sanktionslisten, politisch exponierte Personen (PEP),
                    Fahndungen, organisierte Kriminalität — über 250 amtliche
                    Quellen (CC BY-NC 4.0, eigener Schlüssel nötig)
    flugzeug        Flugzeuge über ADS-B: aktuelle Position und Halter zu
                    einer Kennung (adsb.lol, offen, ohne Schlüssel)
    schiff          Schiffe über AIS und Register: Identität, Flagge, IMO,
                    Eigner (Global Fishing Watch, freier Token nötig)
    wikidata        Strukturierte Angaben zu Personen und Organisationen,
                    mit Koordinaten (CC0)
    wikipedia       Kurzfassungen deutsch und englisch (CC BY-SA)
    gdelt           Weltweite Presseberichterstattung, letzte Monate
    websuche        DuckDuckGo-Ergebnisliste (nur Titel, Adresse, Auszug)

Jeder Abruf geht über den Netzweg (netz.py), also bei Bedarf über Tor.
Jede Quelle führt Buch über ihren letzten Erfolg und ihren letzten Fehler —
eine Recherche, die auf einer seit Tagen gestörten Quelle steht, soll das
sehen können.
"""

from __future__ import annotations

import html
import re
import time
from urllib.parse import parse_qs, quote, unquote, urlparse

QUELLEN = {
    "gleif": "GLEIF – Rechtsträgerkennungen, Konzernverflechtungen",
    "offshore_leaks": "ICIJ Offshore Leaks – Briefkastenfirmen aus Leaks",
    "opensanctions": "OpenSanctions – Sanktionen, PEPs, Fahndungen",
    "flugzeug": "Flugzeuge – ADS-B-Position und Halter (adsb.lol)",
    "schiff": "Schiffe – AIS, Register, Eigner (Global Fishing Watch)",
    "wikidata": "Wikidata – strukturierte Angaben, Koordinaten",
    "wikipedia": "Wikipedia – Kurzfassungen",
    "gdelt": "GDELT – weltweite Presseberichte",
    "websuche": "Websuche (DuckDuckGo)",
}

# Wikimedia sperrt Abrufe ohne erkennbare Programmkennung (Robot Policy).
# Dort meldet sich IndraNet deshalb als das, was es ist — die Abfrage nach
# einem Lexikonartikel verrät wenig, der Rest bleibt unauffällig.
WIKIMEDIA_UA = {"User-Agent": "IndraNet/2.0 (Open-Source-Recherchewerkzeug; "
                              "+https://github.com/indranet)"}

_GESUNDHEIT: dict[str, dict] = {k: {"ok": None, "zuletzt": None,
                                     "fehler": None} for k in QUELLEN}


def gesundheit() -> list[dict]:
    return [{"quelle": k, "beschreibung": QUELLEN[k], **v}
            for k, v in _GESUNDHEIT.items()]


def _merken(name: str, ok: bool, fehler: str | None = None) -> None:
    g = _GESUNDHEIT.setdefault(name, {})
    g.update(ok=ok, zuletzt=time.time(), fehler=fehler if not ok else None)


def abfragen(netzweg, quelle: str, begriff: str, sprache: str = "de") -> dict:
    """Einheitlicher Einstieg. Liefert {quelle, treffer, text}; wirft nie —
    ein Fehler kommt als Text zurück, damit eine Recherche weiterläuft."""
    funktion = {"gleif": gleif, "offshore_leaks": offshore_leaks,
                "opensanctions": opensanctions,
                "flugzeug": flugzeug, "schiff": schiff,
                "wikidata": wikidata, "wikipedia": wikipedia,
                "gdelt": gdelt, "websuche": websuche}.get(quelle)
    if funktion is None:
        return {"quelle": quelle, "treffer": [],
                "text": f"Unbekannte Quelle {quelle}"}
    try:
        treffer = funktion(netzweg, begriff, sprache)
        _merken(quelle, True)
    except Exception as e:                                  # noqa: BLE001
        _merken(quelle, False, str(e)[:300])
        return {"quelle": quelle, "treffer": [],
                "text": f"{QUELLEN[quelle]}: Abruf fehlgeschlagen ({e})"}
    return {"quelle": quelle, "treffer": treffer,
            "text": _als_text(quelle, treffer)}


def _als_text(quelle: str, treffer: list[dict]) -> str:
    if not treffer:
        return f"{QUELLEN[quelle]}: keine Treffer."
    zeilen = [f"{QUELLEN[quelle]} — {len(treffer)} Treffer:"]
    for t in treffer:
        teile = [f"{k}: {v}" for k, v in t.items()
                 if v not in (None, "", [], {})]
        zeilen.append("- " + " | ".join(teile))
    return "\n".join(zeilen)


# ------------------------------------------------------------------- GLEIF
def gleif(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    basis = "https://api.gleif.org/api/v1"
    d = netzweg.json(f"{basis}/lei-records",
                     params={"filter[fulltext]": begriff, "page[size]": 5},
                     headers={"Accept": "application/vnd.api+json"})
    raus = []
    for rec in d.get("data", [])[:5]:
        a = rec.get("attributes", {})
        ent = a.get("entity", {})
        sitz = ent.get("legalAddress", {}) or {}
        hq = ent.get("headquartersAddress", {}) or {}
        lei = a.get("lei") or rec.get("id")
        eintrag = {
            "name": (ent.get("legalName") or {}).get("name"),
            "lei": lei,
            "rechtsordnung": ent.get("jurisdiction"),
            "rechtsform": (ent.get("legalForm") or {}).get("id"),
            "status": ent.get("status"),
            "sitz": ", ".join(x for x in [sitz.get("city"),
                                          sitz.get("country")] if x),
            "sitz_adresse": " ".join((sitz.get("addressLines") or [])
                                     + [sitz.get("postalCode") or "",
                                        sitz.get("city") or ""]).strip(),
            "hauptverwaltung": ", ".join(x for x in [hq.get("city"),
                                                     hq.get("country")] if x),
            "registernummer": ent.get("registeredAs"),
            "url": f"https://search.gleif.org/#/record/{lei}",
        }
        for art, feld in (("direct-parent", "direkte_mutter"),
                          ("ultimate-parent", "oberste_mutter")):
            try:
                p = netzweg.json(f"{basis}/lei-records/{lei}/{art}",
                                 headers={"Accept":
                                          "application/vnd.api+json"})
                pd = (p.get("data") or {})
                pent = (pd.get("attributes") or {}).get("entity") or {}
                if pent:
                    eintrag[feld] = (f"{(pent.get('legalName') or {}).get('name')}"
                                     f" (LEI {pd.get('id')}, "
                                     f"{pent.get('jurisdiction')})")
            except Exception:                               # noqa: BLE001
                pass        # 404 = keine Mutter gemeldet, das ist normal
        raus.append(eintrag)
    return raus


# ----------------------------------------------------------- Offshore Leaks
def offshore_leaks(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    with netzweg.client(timeout=40) as c:
        r = c.post("https://offshoreleaks.icij.org/api/v1/reconcile",
                   json={"query": begriff},
                   headers={"Accept": "application/json"})
        r.raise_for_status()
        d = r.json()
    # Einzelanfrage liefert {"result": [...]}, Stapelanfrage {"q0": {...}}
    ergebnisse = []
    if isinstance(d, dict):
        ergebnisse = d.get("result") or []
        if not ergebnisse:
            erstes = next(iter(d.values()), {})
            if isinstance(erstes, dict):
                ergebnisse = erstes.get("result", [])
    raus = []
    for e in ergebnisse[:8]:
        typen = ", ".join(t.get("name", "") for t in e.get("types", []))
        raus.append({"name": e.get("name"), "art": typen,
                     "uebereinstimmung": round(float(e.get("score", 0)), 1),
                     "url": f"https://offshoreleaks.icij.org/nodes/{e.get('id')}",
                     "hinweis": e.get("description")})
    return raus


# ------------------------------------------------------------ OpenSanctions
# OpenSanctions bündelt amtliche Sanktions-, PEP- und Fahndungslisten. Die
# Daten stehen unter CC BY-NC 4.0 (nicht-kommerziell); der Zugang verlangt
# einen eigenen API-Schlüssel, für Journalismus und gemeinnützige Arbeit
# kostenlos (opensanctions.org/api). Ein Treffer bedeutet: Die Person oder
# Firma steht auf einer dieser Listen — nicht mehr und nicht weniger. Warum,
# sagen die Themen und die nennende Liste; prüfen muss es der Mensch.
_OS_SCHEMA = {
    "Person": "Person", "Company": "Firma", "Organization": "Organisation",
    "LegalEntity": "Rechtsträger", "Vessel": "Schiff", "Airplane": "Flugzeug",
    "Position": "Amt", "CryptoWallet": "Krypto-Wallet", "Security": "Wertpapier",
}

_OS_THEMEN = {
    "sanction": "auf Sanktionsliste",
    "sanction.linked": "mit Sanktioniertem verbunden",
    "sanction.counter": "Gegensanktion",
    "role.pep": "politisch exponierte Person (PEP)",
    "role.rca": "Angehörige/r oder Vertraute/r eines PEP",
    "role.oligarch": "Oligarch",
    "role.spy": "Nachrichtendienst",
    "gov.soe": "Staatsunternehmen",
    "crime": "Kriminalität",
    "crime.fraud": "Betrug",
    "crime.cyber": "Cyberkriminalität",
    "crime.fin": "Finanzkriminalität",
    "crime.theft": "Diebstahl/Unterschlagung",
    "crime.war": "Kriegsverbrechen/-verbrecher",
    "crime.boss": "organisierte Kriminalität (Führung)",
    "crime.terror": "Terrorismus",
    "crime.traffick": "Schmuggel/Handel",
    "crime.trafficking.drug": "Drogenhandel",
    "crime.trafficking.human": "Menschenhandel",
    "wanted": "zur Fahndung ausgeschrieben",
    "debarment": "von öffentlichen Vergaben ausgeschlossen",
    "export.control": "Exportkontrolle",
    "export.risk": "Exportrisiko",
    "poi": "Person von Interesse",
}


def _os_feld(p: dict, name: str, n: int = 3) -> str:
    return "; ".join(str(x) for x in (p.get(name) or [])[:n])


def opensanctions(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    schluessel = ((getattr(netzweg, "einst", None)
                   and netzweg.einst.get("opensanctions_schluessel")) or "")
    schluessel = schluessel.strip()
    if not schluessel:
        raise RuntimeError(
            "Kein OpenSanctions-API-Schlüssel hinterlegt (System → "
            "Datenquellen). Für Journalismus und gemeinnützige Arbeit "
            "kostenlos: opensanctions.org/api")
    try:
        d = netzweg.json("https://api.opensanctions.org/search/default",
                         params={"q": begriff, "limit": 6},
                         headers={"Authorization": f"ApiKey {schluessel}"})
    except Exception as e:                                  # noqa: BLE001
        m = str(e)
        if "401" in m or "403" in m:
            raise RuntimeError("OpenSanctions lehnt den Schlüssel ab — bitte "
                               "prüfen (System → Datenquellen).")
        if "429" in m:
            raise RuntimeError("OpenSanctions-Kontingent erschöpft — bitte "
                               "später erneut versuchen.")
        raise
    raus = []
    for e in d.get("results", [])[:6]:
        p = e.get("properties", {}) or {}
        themen = [_OS_THEMEN.get(t, t) for t in p.get("topics", [])]
        raus.append({
            "name": e.get("caption"),
            "typ": _OS_SCHEMA.get(e.get("schema"), e.get("schema")),
            "einstufung": "; ".join(themen),
            "land": (_os_feld(p, "country") or _os_feld(p, "nationality")
                     or _os_feld(p, "jurisdiction")),
            "geburtsdatum": _os_feld(p, "birthDate", 1),
            "funktion": _os_feld(p, "position"),
            "gelistet_in": "; ".join((e.get("datasets") or [])[:6]),
            "seit": (e.get("first_seen") or "")[:10],
            "stand": (e.get("last_change") or e.get("last_seen") or "")[:10],
            "url": f"https://www.opensanctions.org/entities/{e.get('id')}/",
        })
    return raus


# ------------------------------------------------------------- Flugzeuge
# ADS-B ist der Funk, mit dem Flugzeuge laufend Kennung, Position, Höhe und
# Kurs aussenden — offen empfangbar. adsb.lol bündelt die Meldungen eines
# weltweiten Empfängernetzes und stellt sie ohne Schlüssel bereit. Gesucht
# wird ein OBJEKT über seine Kennung (Luftfahrzeugkennzeichen wie D-ABCD,
# ICAO-Hex wie 3c6444, oder Rufzeichen wie DLH400) — nicht eine Person.
# ADS-B Exchange, das denselben Dienst früher frei anbot, ist inzwischen
# kostenpflichtig; adsb.lol ist das offene Gegenstück.
_SQUAWK_NOT = {"7500": "Entführung (7500)", "7600": "Funkausfall (7600)",
               "7700": "Luftnotfall (7700)"}


def _flug_zeile(ac: dict) -> dict:
    lat, lon = ac.get("lat"), ac.get("lon")
    seen = ac.get("seen_pos")
    if seen is None:
        seen = ac.get("seen")
    hex_ = (ac.get("hex") or "").lower()
    alt = ac.get("alt_baro")
    zeile = {
        "name": (ac.get("r") or hex_ or "").strip(),
        "typ": "; ".join(x for x in [ac.get("desc"), ac.get("t")] if x),
        "kennung_hex": hex_,
        "rufzeichen": (ac.get("flight") or "").strip(),
        "position": (f"{lat:.4f},{lon:.4f}" if isinstance(lat, (int, float))
                     and isinstance(lon, (int, float)) else ""),
        "hoehe_ft": ("am Boden" if alt == "ground" else alt),
        "tempo_kn": ac.get("gs"),
        "kurs": ac.get("track"),
        "halter": ac.get("ownOp"),
        "militaer": "ja" if (ac.get("dbFlags") or 0) & 1 else "",
        "gesehen": ("gerade eben" if isinstance(seen, (int, float)) and seen < 15
                    else f"vor {int(seen)} s" if isinstance(seen, (int, float))
                    else ""),
        "url": f"https://globe.adsb.lol/?icao={hex_}" if hex_ else "",
    }
    not_ = _SQUAWK_NOT.get(str(ac.get("squawk") or ""))
    if not_:
        zeile["hinweis"] = not_
    return zeile


def flugzeug(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    q = (begriff or "").strip().upper().replace(" ", "")
    if len(q) < 2:
        raise RuntimeError("Bitte eine Kennung angeben: Kennzeichen (D-ABCD), "
                           "ICAO-Hex (3c6444) oder Rufzeichen (DLH400).")
    # Reihenfolge: eindeutige Hex zuerst, dann Kennzeichen, dann Rufzeichen.
    pfade = []
    if re.fullmatch(r"[0-9A-F]{6}", q):
        pfade.append(("hex", q))
    pfade.append(("registration", q.replace("-", "")))
    pfade.append(("callsign", q))
    treffer, gesehen = [], set()
    for i, (art, wert) in enumerate(pfade):
        if i:
            time.sleep(1.1)         # adsb.lol bittet um höchstens 1 Abruf/s
        try:
            d = netzweg.json(f"https://api.adsb.lol/v2/{art}/{quote(wert)}",
                             timeout=40)
        except Exception as e:                              # noqa: BLE001
            if "429" in str(e):
                raise RuntimeError("adsb.lol drosselt Abfragen (etwa eine je "
                                   "Sekunde) — bitte kurz warten.")
            raise
        for ac in (d.get("ac") or []):
            h = ac.get("hex")
            if h and h not in gesehen:
                gesehen.add(h)
                treffer.append(_flug_zeile(ac))
        if treffer:
            break
    return treffer[:8]


# --------------------------------------------------------------- Schiffe
# Schiffe funken über AIS: Kennung (MMSI), Name, Position, Kurs. Anders als
# bei ADS-B gibt es keinen offenen, schlüsselfreien Abruf — AIS-Dienste sind
# kommerziell. Global Fishing Watch ist die Ausnahme: für Recherche und
# gemeinnützige Arbeit frei (eigener Token), auf das Aufdecken von
# illegaler Fischerei, Umflaggung und Sanktionsumgehung ausgelegt. Gesucht
# wird ein OBJEKT über Name, IMO, MMSI oder Rufzeichen — nicht eine Person.
# GFW löst eine Kennung über mehr als 40 Schiffsregister und die AIS-
# Selbstmeldungen auf: Name, Flagge, IMO, Eigner, Typ.
def _gfw_erst(liste, feld):
    for e in liste or []:
        if e.get(feld):
            return e[feld]
    return None


def schiff(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    token = ((getattr(netzweg, "einst", None)
              and netzweg.einst.get("gfw_schluessel")) or "").strip()
    if not token:
        raise RuntimeError(
            "Kein Global-Fishing-Watch-Token hinterlegt (System → "
            "Datenquellen). Für Recherche und gemeinnützige Arbeit kostenlos: "
            "globalfishingwatch.org/our-apis/tokens")
    if len((begriff or "").strip()) < 3:
        raise RuntimeError("Bitte mindestens 3 Zeichen angeben (Name, IMO, "
                           "MMSI oder Rufzeichen).")
    try:
        d = netzweg.json(
            "https://gateway.api.globalfishingwatch.org/v3/vessels/search",
            params={"query": begriff.strip(), "limit": 6,
                    "datasets[0]": "public-global-vessel-identity:latest",
                    "includes[0]": "OWNERSHIP"},
            headers={"Authorization": f"Bearer {token}"})
    except Exception as e:                                  # noqa: BLE001
        m = str(e)
        if "401" in m or "403" in m:
            raise RuntimeError("Global Fishing Watch lehnt den Token ab — "
                               "bitte prüfen (System → Datenquellen).")
        if "429" in m:
            raise RuntimeError("Global-Fishing-Watch-Kontingent erschöpft — "
                               "bitte später erneut versuchen.")
        raise
    raus = []
    for e in (d.get("entries") or [])[:6]:
        reg, selbst = e.get("registryInfo") or [], e.get("selfReportedInfo") or []
        kombi = e.get("combinedSourcesInfo") or []
        typen = []
        for k in kombi:
            for st in (k.get("shiptypes") or []):
                name = st.get("name") if isinstance(st, dict) else st
                if name and name not in typen:
                    typen.append(name)
        eigner = e.get("registryOwners") or []
        vid = _gfw_erst(selbst, "id") or _gfw_erst(reg, "id")
        laenge = _gfw_erst(reg, "lengthM")
        tonnage = _gfw_erst(reg, "tonnageGt")
        letzte = max([x.get("transmissionDateTo") for x in selbst
                      if x.get("transmissionDateTo")] or [""])
        raus.append({
            "name": _gfw_erst(reg, "shipname") or _gfw_erst(selbst, "shipname"),
            "imo": _gfw_erst(reg, "imo") or _gfw_erst(selbst, "imo"),
            "mmsi": _gfw_erst(selbst, "ssvid") or _gfw_erst(reg, "ssvid"),
            "flagge": _gfw_erst(reg, "flag") or _gfw_erst(selbst, "flag"),
            "rufzeichen": _gfw_erst(reg, "callsign")
            or _gfw_erst(selbst, "callsign"),
            "typ": "; ".join(typen),
            "masse": "; ".join(x for x in [
                f"{laenge} m" if laenge else "",
                f"{tonnage} BRZ" if tonnage else ""] if x),
            "eigner": "; ".join(x for x in [
                f"{o.get('name')} ({o.get('flag')})" if o.get("flag")
                else o.get("name") for o in eigner[:3] if o.get("name")]),
            "letzte_meldung": (letzte or "")[:10],
            "url": (f"https://globalfishingwatch.org/vessel-viewer/{vid}"
                    if vid else ""),
        })
    return raus


# ---------------------------------------------------------------- Wikidata
_WD_EIGENSCHAFTEN = {
    "P31": "ist ein", "P17": "Staat", "P159": "Hauptsitz",
    "P27": "Staatsangehörigkeit", "P19": "Geburtsort", "P569": "geboren",
    "P570": "gestorben", "P39": "Amt", "P108": "Arbeitgeber",
    "P127": "Eigentümer", "P749": "Mutterorganisation",
    "P355": "Tochterorganisation", "P1830": "Eigentümer von",
    "P488": "Vorsitz", "P169": "Geschäftsführung", "P1278": "LEI",
    "P102": "Partei", "P463": "Mitglied von", "P551": "Wohnsitz",
    "P625": "Koordinaten", "P571": "gegründet", "P112": "Gründer",
    "P452": "Branche", "P2139": "Umsatz",
}


def wikidata(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    api = "https://www.wikidata.org/w/api.php"
    such = netzweg.json(api, params={"action": "wbsearchentities",
                                     "search": begriff, "language": sprache,
                                     "uselang": sprache, "format": "json",
                                     "limit": 3}, headers=WIKIMEDIA_UA)
    ids = [s["id"] for s in such.get("search", [])]
    if not ids:
        return []
    d = netzweg.json(api, params={"action": "wbgetentities",
                                  "ids": "|".join(ids), "format": "json",
                                  "props": "labels|descriptions|claims",
                                  "languages": f"{sprache}|en"},
                     headers=WIKIMEDIA_UA)
    entitaeten = d.get("entities", {})
    # Bezeichnungen für referenzierte Objekte in einem Rutsch holen
    bezug: set[str] = set()
    for e in entitaeten.values():
        for p in _WD_EIGENSCHAFTEN:
            for c in e.get("claims", {}).get(p, [])[:6]:
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(v, dict) and v.get("id"):
                    bezug.add(v["id"])
    namen = {}
    bezug_liste = sorted(bezug)
    for i in range(0, len(bezug_liste), 45):
        n = netzweg.json(api, params={"action": "wbgetentities",
                                      "ids": "|".join(bezug_liste[i:i + 45]),
                                      "format": "json", "props": "labels",
                                      "languages": f"{sprache}|en"},
                         headers=WIKIMEDIA_UA)
        for qid, e in n.get("entities", {}).items():
            lab = e.get("labels", {})
            namen[qid] = (lab.get(sprache) or lab.get("en") or {}).get(
                "value", qid)

    raus = []
    for qid in ids:
        e = entitaeten.get(qid, {})
        lab = e.get("labels", {})
        besch = e.get("descriptions", {})
        eintrag = {"name": (lab.get(sprache) or lab.get("en") or {}).get(
                       "value"),
                   "beschreibung": (besch.get(sprache) or besch.get("en")
                                    or {}).get("value"),
                   "url": f"https://www.wikidata.org/wiki/{qid}"}
        for p, label in _WD_EIGENSCHAFTEN.items():
            werte = []
            for c in e.get("claims", {}).get(p, [])[:6]:
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(v, dict) and "id" in v:
                    werte.append(namen.get(v["id"], v["id"]))
                elif isinstance(v, dict) and "latitude" in v:
                    werte.append(f"{v['latitude']:.4f},{v['longitude']:.4f}")
                elif isinstance(v, dict) and "time" in v:
                    werte.append(v["time"].lstrip("+")[:10])
                elif isinstance(v, dict) and "amount" in v:
                    werte.append(v["amount"].lstrip("+"))
                elif isinstance(v, str):
                    werte.append(v)
            if werte:
                eintrag[label] = "; ".join(werte)
        raus.append(eintrag)
    return raus


# --------------------------------------------------------------- Wikipedia
def wikipedia(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    raus = []
    for sp in dict.fromkeys([sprache, "en"]):
        d = netzweg.json(f"https://{sp}.wikipedia.org/w/api.php",
                         params={"action": "query", "list": "search",
                                 "srsearch": begriff, "format": "json",
                                 "srlimit": 2}, headers=WIKIMEDIA_UA)
        for s in d.get("query", {}).get("search", []):
            titel = s["title"]
            try:
                z = netzweg.json(f"https://{sp}.wikipedia.org/api/rest_v1/"
                                 f"page/summary/{quote(titel.replace(' ', '_'))}",
                                 headers=WIKIMEDIA_UA)
                auszug = z.get("extract", "")
                koord = z.get("coordinates") or {}
            except Exception:                               # noqa: BLE001
                auszug = re.sub(r"<[^>]+>", "", s.get("snippet", ""))
                koord = {}
            raus.append({"titel": titel, "sprache": sp, "auszug": auszug[:1200],
                         "koordinaten": (f"{koord['lat']},{koord['lon']}"
                                         if koord else None),
                         "url": f"https://{sp}.wikipedia.org/wiki/"
                                f"{quote(titel.replace(' ', '_'))}"})
    return raus


# ------------------------------------------------------------------- GDELT
def gdelt(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    # GDELT erlaubt eine Anfrage je fünf Sekunden — einmal warten und
    # wiederholen, dann aufgeben.
    for versuch in range(2):
        a = netzweg.abrufen("https://api.gdeltproject.org/api/v2/doc/doc",
                            params={"query": f'"{begriff}"', "mode": "artlist",
                                    "maxrecords": 15, "format": "json",
                                    "sort": "datedesc"}, timeout=40)
        if a.status != 429:
            break
        time.sleep(6)
    if a.status >= 400:
        raise RuntimeError(f"HTTP {a.status}"
                           + (" — GDELT drosselt Abfragen" if a.status == 429
                              else ""))
    import json as _json
    d = _json.loads(a.text) if a.text.strip().startswith("{") else {}
    return [{"titel": a.get("title"), "datum": (a.get("seendate") or "")[:8],
             "medium": a.get("domain"), "land": a.get("sourcecountry"),
             "sprache": a.get("language"), "url": a.get("url")}
            for a in d.get("articles", [])]


# ---------------------------------------------------------------- Websuche
_DDG_TREFFER = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
    r'(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>)?', re.S)


def websuche(netzweg, begriff: str, sprache: str = "de") -> list[dict]:
    # Als Formular abschicken wie der Browser — einfache GET-Abrufe hält
    # DuckDuckGo für Automaten und verlangt eine Bestätigung.
    with netzweg.client(timeout=30) as c:
        r = c.post("https://html.duckduckgo.com/html/",
                   data={"q": begriff,
                         "kl": "de-de" if sprache == "de" else "wt-wt"},
                   headers={"Referer": "https://html.duckduckgo.com/",
                            "Origin": "https://html.duckduckgo.com",
                            "Accept": "text/html,application/xhtml+xml"})
        status, text = r.status_code, r.text
    if status >= 400:
        raise RuntimeError(f"HTTP {status}")
    raus = []
    for href, titel, auszug in _DDG_TREFFER.findall(text):
        if href.startswith("//"):
            href = "https:" + href
        ziel = parse_qs(urlparse(href).query).get("uddg", [href])[0]
        if "duckduckgo.com/y.js" in ziel:
            continue                                    # Werbung
        raus.append({"titel": html.unescape(re.sub(r"<[^>]+>", "", titel)),
                     "url": unquote(ziel),
                     "auszug": html.unescape(re.sub(r"<[^>]+>", "",
                                                    auszug or ""))[:300]})
        if len(raus) >= 10:
            break
    if not raus and "anomaly" in text.lower():
        raise RuntimeError("Suchmaschine verlangt eine Bestätigung "
                           "(häufig bei Tor-Ausgängen)")
    return raus


# ------------------------------------------------------------ Seitentext
def seitentext(netzweg, url: str, max_zeichen: int = 15000) -> dict:
    """Holt eine Seite und liefert lesbaren Text samt Titel."""
    from extract import extrahieren
    a = netzweg.abrufen(url, timeout=40)
    name = urlparse(a.url).path.rsplit("/", 1)[-1] or "seite.html"
    if "html" in a.typ and not name.endswith((".html", ".htm")):
        name += ".html"
    titel = ""
    m = re.search(rb"<title[^>]*>(.*?)</title>", a.inhalt[:200000], re.S | re.I)
    if m:
        titel = html.unescape(m.group(1).decode("utf-8", "replace").strip())
    try:
        e = extrahieren(a.inhalt, name)
        text = e.text
    except Exception:                                       # noqa: BLE001
        text = re.sub(r"<[^>]+>", " ", a.text)
    text = re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", text)).strip()
    return {"url": a.url, "status": a.status, "titel": titel or a.domain,
            "domain": a.domain, "typ": a.typ, "text": text[:max_zeichen],
            "roh": a.inhalt}
