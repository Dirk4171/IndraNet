"""
IndraNet — Brücke zu claude.ai
================================

Für alle, die Claude im Abo nutzen (Pro, Max) und kein API-Guthaben haben.
Das Abo gilt nur in Anthropics eigenen Programmen; ein fremdes Programm darf
die Anmeldung nicht verwenden. Also geht der Weg über den Menschen:

  1. IndraNet schreibt den Rechercheauftrag — mit den Grundregeln, dem
     geschlossenen Prädikatsvokabular, einer Antwortvorlage und den
     Registerauszügen, die es selbst schon abgefragt hat.
  2. Die Rechercheurin kopiert ihn in ihren Chat auf claude.ai (Websuche
     an) und kopiert die Antwort zurück.
  3. IndraNet liest den JSON-Block aus der Antwort, prüft ihn wie jeden
     KI-Befund (normalisieren) und legt ihn in den Prüfkorb.

Nichts davon umgeht eine Regel: Die Rechercheurin bedient claude.ai selbst.
Im Hintergrund kann die Brücke deshalb nichts — keine Vorschläge nach der
Übernahme, kein Autopilot.

Die Vorlage wird aus denselben Schemata erzeugt wie bei der API
(BEFUND_SCHEMA, ANALYSE_SCHEMA). Ändert sich ein Schema, ändert sich der
Auftrag mit.
"""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, wait

import quellen_offen
from ki import ANALYSE_SCHEMA, BEFUND_SCHEMA, GRUNDREGELN, KI, normalisieren

HERKUNFT = "claude.ai (Chat)"
REGISTER = ("gleif", "offshore_leaks", "wikidata", "wikipedia")
REGISTER_WARTEN = 45          # Sekunden für alle Registerabfragen zusammen
MAX_DATEITEXT = 150_000       # mehr passt nicht sinnvoll in eine Nachricht

AUSGABE = """AUSGABE
Antworte am Ende mit GENAU EINEM JSON-Codeblock (```json … ```) nach der
Vorlage unten — direkt im Chat, nicht als Artefakt oder Datei. Kein Kommentar
im JSON. Bei Feldern mit „a | b | c“ genau einen der Werte eintragen. Leere
Listen sind erlaubt, erfundene Angaben nicht. Text vor dem Block ist erlaubt,
IndraNet übernimmt aber nur den Block."""


class BrueckeFehler(Exception):
    pass


# ----------------------------------------------------------------- Vorlage
def vorlage(schema: dict):
    """Beispielgerüst aus einem JSON-Schema: Felder mit ihrer Beschreibung."""
    if "enum" in schema:
        werte = schema["enum"]
        return (" | ".join(werte) if len(werte) <= 12
                else "ein Prädikat aus der Liste in Regel 6")
    typ = schema.get("type")
    if typ == "object":
        return {k: vorlage(v) for k, v in schema["properties"].items()}
    if typ == "array":
        return [vorlage(schema["items"])]
    if typ == "number":
        return 0.0
    return schema.get("description", "…")


def _vorlage_text(schema: dict) -> str:
    return json.dumps(vorlage(schema), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- Aufträge
def _stand(quelle: str, r: dict) -> str:
    if r["treffer"]:
        return f"Register {quelle}: {len(r['treffer'])} Treffer"
    if "fehlgeschlagen" in r["text"]:
        return f"Register {quelle}: nicht erreichbar"
    return f"Register {quelle}: keine Treffer"


def registerauszuege(netzweg, begriff: str, melden=None) -> str:
    """Fragt die offenen Register parallel ab. Was nicht rechtzeitig kommt
    oder scheitert, wird vermerkt statt abzubrechen."""
    quellen = list(REGISTER)
    # OpenSanctions nur, wenn ein Schlüssel hinterlegt ist — sonst nur Lärm.
    if getattr(netzweg, "einst", None) and \
            netzweg.einst.get("opensanctions_schluessel"):
        quellen.insert(0, "opensanctions")
    pool = ThreadPoolExecutor(len(quellen))
    vorbei = threading.Event()      # Nachzügler nicht mehr melden
    laeufe = {}
    for q in quellen:
        laeufe[q] = pool.submit(quellen_offen.abfragen, netzweg, q, begriff)
        if melden:      # sofort melden, nicht erst wenn alle da sind
            laeufe[q].add_done_callback(
                lambda f, q=q: f.cancelled() or vorbei.is_set()
                or melden(_stand(q, f.result())))
    wait(laeufe.values(), timeout=REGISTER_WARTEN)
    vorbei.set()
    # Nicht auf Nachzügler warten — sie laufen im Hintergrund aus
    pool.shutdown(wait=False, cancel_futures=True)
    teile = []
    for q, f in laeufe.items():
        fertig = f.done() and not f.cancelled()
        if not fertig:
            teile.append(f"{quellen_offen.QUELLEN[q]}: keine Antwort in "
                         f"{REGISTER_WARTEN} s.")
        elif f.result()["treffer"]:
            teile.append(f.result()["text"][:5000])
        else:   # "keine Treffer" bzw. Fehler — eine Zeile genügt Claude
            teile.append(f.result()["text"].splitlines()[0][:200])
        if melden and not fertig:
            melden(f"Register {q}: keine Antwort in {REGISTER_WARTEN} s")
    return "\n\n".join(teile)


def auftrag_recherche(auftrag: str, kontext: dict, material: str = "") -> str:
    teile = [GRUNDREGELN, "",
             "AUFGABE\nRecherchiere im Web zum Auftrag unten. Nutze die "
             "Websuche und rufe ergiebige Seiten auf; Primärquellen zuerst. "
             "Jede Aussage braucht als Beleg die exakte Adresse (https://…), "
             "unter der du sie gesehen hast.", "", AUSGABE, "", "VORLAGE",
             _vorlage_text(BEFUND_SCHEMA), "", KI._kontext(kontext),
             f"AUFTRAG: {auftrag}"]
    if material:
        teile += ["", "REGISTERAUSZÜGE (von IndraNet bereits abgefragt — "
                  "als Ausgangspunkt nutzen, Adressen als Beleg zulässig)",
                  material]
    return "\n".join(t for t in teile if t is not None).strip()


def auftrag_datei(dateiname: str, abschnitte: list[dict],
                  kontext: dict) -> tuple[str, bool]:
    """Liefert (Auftrag, anhaengen). Ohne lesbaren Text oder bei sehr
    großen Dateien muss die Rechercheurin die Datei im Chat anhängen."""
    texte = [f"[{a['fundstelle']}] {a['text']}" for a in abschnitte
             if a.get("text", "").strip()]
    inhalt = "\n".join(texte)
    anhaengen = not inhalt or len(inhalt) > MAX_DATEITEXT
    aufgabe = (f"AUFGABE\nAnalysiere die Datei „{dateiname}“ für die "
               "Recherche. Erfasse Personen, Firmen, Orte, Beteiligungen, "
               "Zahlungen, Beträge, Daten und Funktionen als Aussagen. Als "
               "Beleg die Fundstelle angeben")
    if anhaengen:
        aufgabe += (" (Seite, Blatt/Zeile). Die Datei ist an diese Nachricht "
                    "angehängt.")
    else:
        aufgabe += (", die in eckigen Klammern vor jedem Abschnitt steht "
                    "(z. B. „Zeile 12“).")
    aufgabe += " Als Quelle die Datei selbst mit Art „datei“."
    teile = [GRUNDREGELN, "", aufgabe, "", AUSGABE, "", "VORLAGE",
             _vorlage_text(BEFUND_SCHEMA), "", KI._kontext(kontext)]
    if not anhaengen:
        teile += ["", f"DATEI {dateiname}:", inhalt]
    return "\n".join(teile).strip(), anhaengen


def auftrag_lagebild(frage: str, bestand: str, kontext: dict) -> str:
    return "\n".join([
        GRUNDREGELN, "",
        "AUFGABE\nUnten steht der geprüfte Bestand einer Recherche: Fakten "
        "mit Beleglage (BESTAETIGT = mind. zwei unabhängige Quellen, "
        "EINFACH_BELEGT = eine Quelle, UMSTRITTEN = Quellen widersprechen "
        "sich). Schreibe ein qualifiziertes Lagebild. Trenne strikt zwischen "
        "belegten Fakten und deinen Schlussfolgerungen. Nenne Namen exakt wie "
        "im Bestand. Keine Websuche nötig.", "",
        AUSGABE, "Das Feld „lage“ ist Markdown in einem JSON-Text — "
        "Zeilenumbrüche als \\n.", "", "VORLAGE",
        _vorlage_text(ANALYSE_SCHEMA), "", KI._kontext(kontext),
        f"FRAGE: {frage or 'Gesamtlage: Was zeigt das Geflecht?'}", "",
        bestand[:400000]]).strip()


# ----------------------------------------------------------------- Antwort
_BLOCK = re.compile(r"```[a-zA-Z]*\s*(.*?)```", re.S)


def json_lesen(text: str) -> dict:
    """Holt das JSON-Objekt aus einer eingefügten Chat-Antwort: aus einem
    Codeblock, sonst vom ersten „{“ bis zum letzten „}“."""
    text = (text or "").replace(" ", " ").replace("﻿", "").strip()
    if not text:
        raise BrueckeFehler("Die Antwort ist leer.")
    kandidaten = [b.strip() for b in _BLOCK.findall(text) if "{" in b]
    kandidaten.reverse()                     # der letzte Block ist meist das Ergebnis
    a, b = text.find("{"), text.rfind("}")
    if a != -1 and b > a:
        kandidaten.append(text[a:b + 1])
    for k in kandidaten:
        k = k[k.find("{"):k.rfind("}") + 1]
        for versuch in (k, re.sub(r",\s*([}\]])", r"\1", k)):
            try:
                daten = json.loads(versuch)
            except json.JSONDecodeError:
                continue
            if isinstance(daten, dict):
                return daten
    raise BrueckeFehler(
        "In der Antwort steht kein lesbarer JSON-Block. Bitte die ganze "
        "Antwort von Claude einfügen — am einfachsten über den "
        "Kopieren-Knopf am Codeblock. Ist die Antwort abgeschnitten, Claude "
        "um „den vollständigen JSON-Block“ bitten.")


def befund_lesen(text: str, *, datei: bool = False) -> tuple[dict, int]:
    """Befund aus der Antwort; zweiter Wert = verworfene Aussagen (ohne
    Beleg, unbekanntes Prädikat)."""
    roh = json_lesen(text)
    if not any(k in roh for k in ("aussagen", "entitaeten", "zusammenfassung")):
        raise BrueckeFehler("Das JSON ist kein Befund (es fehlen „aussagen“ "
                            "und „entitaeten“). Wurde der richtige Auftrag "
                            "verwendet?")
    d = normalisieren(roh, datei=datei)
    verworfen = len(roh.get("aussagen") or []) - len(d["aussagen"])
    return {**d, "_modell": HERKUNFT, "_suchen": [], "_kosten": {}}, verworfen


def lagebild_lesen(text: str) -> dict:
    roh = json_lesen(text)
    if not str(roh.get("lage") or "").strip():
        raise BrueckeFehler("Das JSON ist kein Lagebild (Feld „lage“ fehlt).")
    raus = {"titel": str(roh.get("titel") or "Lagebild")[:200],
            "lage": str(roh["lage"])[:60000]}
    for feld in ("kernaussagen", "schluesselfiguren", "geldfluesse",
                 "zeitleiste", "luecken", "warnsignale", "naechste_schritte"):
        werte = roh.get(feld)
        raus[feld] = werte[:100] if isinstance(werte, list) else []
    raus["kernaussagen"] = [k for k in raus["kernaussagen"]
                            if isinstance(k, dict) and k.get("aussage")]
    raus["_modell"] = HERKUNFT
    return raus
