"""
IndraNet — KI-Rechercheur
==========================

Die KI recherchiert, liest Dateien und schreibt Lagebilder. Was sie findet,
ist ein BEFUND, kein Fakt: Er landet im Prüfkorb, und erst ein Mensch macht
daraus Aussagen im Bestand. Diese Grenze ist der Kern des Entwurfs — eine
KI, die selbst in den Bestand schreibt, erzeugt veröffentlichungsreif
aussehende Behauptungen, die niemand geprüft hat.

ANBIETER
--------
claude   Anthropic-API mit serverseitiger Websuche und Seitenabruf. Dazu
         eigene Werkzeuge für Register (GLEIF, Offshore Leaks, Wikidata …),
         die lokal über den Netzweg laufen.
chat     Brücke zu claude.ai für Abo-Nutzer ohne API-Guthaben: Aufträge
         zum Kopieren, Antworten zum Einfügen (bruecke.py). Kein Aufruf aus
         diesem Modul.
ollama   Lokales Modell. Hat keine eigene Websuche: IndraNet sammelt
         Suchtreffer und Registerauszüge selbst und legt sie dem Modell vor.
         Schwächer, aber nichts verlässt den Rechner außer den Abrufen.

DER BEFUND
----------
Ein festes Schema (BEFUND_SCHEMA): Entitäten, Aussagen im geschlossenen
Prädikatsvokabular, Orte mit Koordinaten, Quellen, offene Fragen, nächste
Schritte. Jede Aussage nennt ihren Beleg — eine Adresse oder eine
Fundstelle im Dokument. Aussagen ohne Beleg verwirft die Normalisierung.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field

import i18n
import quellen_offen
from resolver import INVERSE, PREDICATE_SCHEMA

BASIS_PRAEDIKATE = list(INVERSE.keys())
ENTITAETSTYPEN = ["PERSON", "ORG", "PLACE", "VESSEL", "ADRESSE", "AMT",
                  "KENNUNG", "BETRAG", "DATUM", "REGISTER"]
QUELLENARTEN = ["register", "behoerde", "gericht", "presse", "wissen",
                "unternehmen", "ngo", "leak", "sozial", "datei", "sonstige"]

MODELLE = [
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5 — gründlich (Vorgabe)"},
    {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5 — schneller, günstiger"},
    {"id": "claude-haiku-5-5", "name": "Claude Haiku 5.5 — sehr günstig, flacher"},
]


class KIFehler(Exception):
    pass


def _praedikat_liste() -> str:
    lab = i18n.praedikate("de")
    return "\n".join(f"  {p}: {lab.get(p, p)}  ({PREDICATE_SCHEMA[p][0]} → "
                     f"{PREDICATE_SCHEMA[p][1]})" for p in BASIS_PRAEDIKATE)


def _str(beschreibung: str) -> dict:
    return {"type": "string", "description": beschreibung}


def _liste(items: dict) -> dict:
    return {"type": "array", "items": items}


def _obj(eigenschaften: dict) -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": list(eigenschaften), "properties": eigenschaften}


BEFUND_SCHEMA = _obj({
    "zusammenfassung": _str("Was wurde gefunden, in 3–8 Sätzen, nüchtern. "
                            "Vorwürfe als Vorwürfe kennzeichnen."),
    "entitaeten": _liste(_obj({
        "name": _str("Vollständiger Name, wie in der Quelle"),
        "typ": {"type": "string", "enum": ENTITAETSTYPEN},
        "beschreibung": _str("Wer/was ist das, 1–2 Sätze"),
        "aliase": _liste({"type": "string"}),
    })),
    "aussagen": _liste(_obj({
        "subjekt": _str("Name der Subjekt-Entität"),
        "praedikat": {"type": "string", "enum": BASIS_PRAEDIKATE},
        "objekt": _str("Name der Objekt-Entität bzw. Wert"),
        "beleg": _str("Web: exakte URL der Quelle. Datei: Fundstelle "
                      "(z. B. 'S. 4' oder 'Blatt X, Zeile 12')"),
        "zitat": _str("Wörtliche Stelle, die die Aussage trägt (max. 300 "
                      "Zeichen), sonst leer"),
        "datum": _str("Stand/Datum der Angabe (JJJJ-MM-TT), sonst leer"),
        "sicherheit": {"type": "string", "enum": ["hoch", "mittel", "niedrig"]},
    })),
    "orte": _liste(_obj({
        "name": _str("Ortsname genau wie in den Aussagen verwendet"),
        "lat": {"type": "number"},
        "lon": {"type": "number"},
        "land_iso": _str("ISO-3166-Alpha-2"),
        "genauigkeit": {"type": "string",
                        "enum": ["land", "region", "stadt", "adresse"]},
    })),
    "quellen": _liste(_obj({
        "url": _str("Adresse bzw. Dateiname"),
        "titel": _str("Titel der Seite/des Dokuments"),
        "herausgeber": _str("Wer veröffentlicht das (Register, Medium, Behörde)"),
        "art": {"type": "string", "enum": QUELLENARTEN},
        "datum": _str("Veröffentlichungsdatum, sonst leer"),
    })),
    "offene_fragen": _liste({"type": "string"}),
    "naechste_schritte": _liste(_str("Konkrete Folgerecherche als Suchauftrag, "
                                     "z. B. 'Nordkap Shipping AS Registerauszug "
                                     "Brønnøysund'")),
})

GRUNDREGELN = f"""Du arbeitest als Rechercheassistenz für investigative Journalistinnen und
Journalisten in der Software IndraNet. Grundlage sind ausschließlich öffentlich
zugängliche Quellen. Deine Befunde prüft danach ein Mensch.

Regeln:
1. Jede Aussage braucht einen Beleg: die exakte URL, unter der du sie gesehen hast,
   bzw. die Fundstelle im Dokument. Erfinde keine Adressen. Was du nicht belegen
   kannst, gehört in "offene_fragen", nicht in "aussagen".
2. Primärquellen zuerst: Handels- und Unternehmensregister, GLEIF, amtliche
   Bekanntmachungen, Gerichtsentscheidungen, Sanktionslisten, Behörden. Danach
   seriöse Presse, ICIJ Offshore Leaks, OCCRP. Blogs und soziale Medien nur mit
   Sicherheit "niedrig".
3. Unschuldsvermutung. Eine Person ist nur dann verurteilt, wenn eine belastbare
   Quelle das Urteil nennt. Ermittlungen, Anklagen und Vorwürfe als solche
   bezeichnen. Keine Wertungen wie "kriminell" ohne Urteil.
4. Namensgleichheit ist die häufigste Fehlerquelle. Prüfe, ob Treffer wirklich
   dieselbe Person/Firma meinen (Geburtsdatum, Ort, Funktion, Registernummer).
   Zweifel gehören in "offene_fragen".
5. Öffentliches Interesse: Erfasse, was zur Recherche gehört — Funktionen,
   Beteiligungen, Geldflüsse, Verfahren, öffentliche Ämter. Keine Angaben zu
   Gesundheit, Sexualleben, Religion oder zu unbeteiligten Angehörigen; keine
   Privatadressen von Privatpersonen.
6. Prädikate nur aus dieser geschlossenen Liste (Subjekttyp → Objekttyp):
{_praedikat_liste()}
   Für Geldflüsse: paid_to (Zahler → Empfänger), amount_of (Vorgang → Betrag),
   dated (Vorgang → Datum). Für Sitz: registered_in (Firma → Ort). Personen-Wohnort:
   resident_in nur mit Stadt/Land, nie Straße.
7. Orte: Für jeden Ort, der in einer Aussage vorkommt, einen Eintrag in "orte"
   mit Koordinaten (Stadtmitte bzw. Landesmitte).
8. Antworte auf Deutsch. Firmen- und Personennamen in Originalschreibweise."""

RECHERCHE_AUFTRAG = """Recherchiere im Web zum folgenden Auftrag. Nutze die Websuche, rufe
ergiebige Seiten mit dem Seitenabruf auf und befrage bei Firmen und Personen
gezielt die Register über das Werkzeug "register_abfragen" (GLEIF für
Konzernverflechtungen, offshore_leaks für Briefkastenfirmen, wikidata für
Eckdaten). Arbeite gründlich, aber zielgerichtet.

Wenn du fertig bist, rufe GENAU EINMAL das Werkzeug "befund_melden" mit allen
belegten Ergebnissen auf. Schreibe danach nichts mehr."""

REGISTER_WERKZEUG = {
    "name": "register_abfragen",
    "description": ("Fragt ein offenes Register bzw. einen Datenbestand ab. "
                    "gleif: Firmen mit LEI, Sitz, Mutter/oberste Mutter. "
                    "offshore_leaks: ICIJ-Datenbank (Panama/Paradise/Pandora "
                    "Papers). opensanctions: Sanktionslisten, politisch "
                    "exponierte Personen (PEP), Fahndungen und organisierte "
                    "Kriminalität aus über 250 amtlichen Quellen (nur mit "
                    "hinterlegtem Schlüssel). flugzeug: aktuelle Position und "
                    "Halter eines Flugzeugs über seine Kennung "
                    "(Luftfahrzeugkennzeichen, ICAO-Hex oder Rufzeichen; "
                    "ADS-B). schiff: Identität, Flagge, IMO, Eigner eines "
                    "Schiffs über Name, IMO oder MMSI (nur mit hinterlegtem "
                    "Token). flugzeug und schiff suchen OBJEKTE über ihre "
                    "Kennung, keine Personen. wikidata: Eckdaten zu "
                    "Personen/Organisationen. wikipedia: Kurzfassung. gdelt: "
                    "aktuelle Presseberichte weltweit."),
    "strict": True,
    "input_schema": _obj({
        "quelle": {"type": "string",
                   "enum": ["gleif", "offshore_leaks", "opensanctions",
                            "flugzeug", "schiff", "wikidata", "wikipedia",
                            "gdelt"]},
        "suchbegriff": _str("Name/Firma/Person, bzw. bei flugzeug und schiff "
                            "die Kennung (Kennzeichen, Hex, Rufzeichen, IMO, "
                            "MMSI)"),
    }),
}

BEFUND_WERKZEUG = {
    "name": "befund_melden",
    "description": ("Meldet die Befunde der Recherche an IndraNet. Einmal am "
                    "Ende aufrufen."),
    "strict": True,
    "input_schema": BEFUND_SCHEMA,
}

ANALYSE_SCHEMA = _obj({
    "titel": _str("Kurzer Titel des Lagebilds"),
    "lage": _str("Lagebild in Markdown: Was wissen wir, wie gut ist es belegt, "
                 "welche Muster zeigen sich. Mit Zwischenüberschriften (##). "
                 "Bei jeder Kernaussage die Beleglage nennen."),
    "kernaussagen": _liste(_obj({
        "aussage": {"type": "string"},
        "beleglage": {"type": "string",
                      "enum": ["bestaetigt", "einfach", "umstritten",
                               "schlussfolgerung"]},
    })),
    "schluesselfiguren": _liste(_obj({
        "name": _str("Genau wie im Bestand geschrieben"),
        "rolle": _str("Rolle im Geflecht, 1 Satz"),
    })),
    "geldfluesse": _liste(_obj({
        "von": {"type": "string"}, "an": {"type": "string"},
        "betrag": _str("Betrag mit Währung, sonst leer"),
        "beleglage": {"type": "string"},
    })),
    "zeitleiste": _liste(_obj({
        "datum": _str("JJJJ-MM-TT oder JJJJ"),
        "ereignis": {"type": "string"},
    })),
    "luecken": _liste(_str("Was fehlt, um eine Aussage zu tragen")),
    "warnsignale": _liste(_str("Auffälligkeiten, die auf Verschleierung, "
                               "Interessenkonflikte oder Rechtsverstöße "
                               "hindeuten können — als Hinweis, nicht als "
                               "Urteil")),
    "naechste_schritte": _liste({"type": "string"}),
})

VORSCHLAG_SCHEMA = _obj({
    "recherchen": _liste(_obj({
        "auftrag": _str("Suchauftrag, so konkret wie möglich"),
        "grund": _str("Warum lohnt sich das, 1 Satz"),
    })),
    "verbindungen": _liste(_obj({
        "a": {"type": "string"}, "b": {"type": "string"},
        "vermutung": _str("Welche Verbindung könnte bestehen"),
    })),
})


# ------------------------------------------------------------------ Befund
@dataclass
class Befund:
    daten: dict
    modell: str = ""
    suchen: list = field(default_factory=list)       # was die KI gesucht hat
    kosten: dict = field(default_factory=dict)

    def als_dict(self) -> dict:
        return {**self.daten, "_modell": self.modell, "_suchen": self.suchen,
                "_kosten": self.kosten}


def normalisieren(roh: dict, *, datei: bool = False) -> dict:
    """Bringt einen Befund in sichere Form: bekannte Felder, bekannte
    Prädikate, Aussagen nur mit Beleg, Koordinaten im gültigen Bereich."""
    def s(x, n=2000):
        return str(x or "").strip()[:n]

    raus = {"zusammenfassung": s(roh.get("zusammenfassung"), 4000),
            "entitaeten": [], "aussagen": [], "orte": [], "quellen": [],
            "offene_fragen": [s(x, 500) for x in roh.get("offene_fragen", [])
                              if s(x)][:20],
            "naechste_schritte": [s(x, 300) for x in
                                  roh.get("naechste_schritte", []) if s(x)][:12]}
    for e in roh.get("entitaeten", [])[:200]:
        if s(e.get("name")):
            raus["entitaeten"].append({
                "name": s(e["name"], 200),
                "typ": e.get("typ") if e.get("typ") in ENTITAETSTYPEN else "ORG",
                "beschreibung": s(e.get("beschreibung"), 600),
                "aliase": [s(a, 200) for a in e.get("aliase", []) if s(a)][:10]})
    for a in roh.get("aussagen", [])[:400]:
        p = a.get("praedikat")
        if p not in BASIS_PRAEDIKATE or not s(a.get("subjekt")) \
                or not s(a.get("objekt")) or not s(a.get("beleg")):
            continue
        if not datei and not s(a.get("beleg")).lower().startswith("http"):
            continue
        raus["aussagen"].append({
            "subjekt": s(a["subjekt"], 200), "praedikat": p,
            "objekt": s(a["objekt"], 200), "beleg": s(a["beleg"], 800),
            "zitat": s(a.get("zitat"), 400), "datum": s(a.get("datum"), 20),
            "sicherheit": (a.get("sicherheit")
                           if a.get("sicherheit") in ("hoch", "mittel",
                                                      "niedrig")
                           else "mittel")})
    for o in roh.get("orte", [])[:100]:
        try:
            lat, lon = float(o.get("lat")), float(o.get("lon"))
        except (TypeError, ValueError):
            continue
        if s(o.get("name")) and -90 <= lat <= 90 and -180 <= lon <= 180:
            raus["orte"].append({"name": s(o["name"], 200), "lat": lat,
                                 "lon": lon, "land_iso": s(o.get("land_iso"), 2),
                                 "genauigkeit": s(o.get("genauigkeit"), 20)
                                 or "stadt"})
    for q in roh.get("quellen", [])[:80]:
        if s(q.get("url")):
            raus["quellen"].append({
                "url": s(q["url"], 800), "titel": s(q.get("titel"), 300),
                "herausgeber": s(q.get("herausgeber"), 200),
                "art": q.get("art") if q.get("art") in QUELLENARTEN
                else "sonstige", "datum": s(q.get("datum"), 20)})
    # Jede Beleg-URL muss als Quelle auftauchen — sonst fehlt der Titel
    bekannt = {q["url"] for q in raus["quellen"]}
    for a in raus["aussagen"]:
        if a["beleg"].startswith("http") and a["beleg"] not in bekannt:
            from netz import domain_von
            raus["quellen"].append({"url": a["beleg"], "titel": a["beleg"],
                                    "herausgeber": domain_von(a["beleg"]),
                                    "art": "sonstige", "datum": ""})
            bekannt.add(a["beleg"])
    return raus


# --------------------------------------------------------------------- KI
class KI:
    def __init__(self, einstellungen, netzweg):
        self.einst = einstellungen
        self.netz = netzweg

    # ----------------------------------------------------------- Zustand
    @property
    def anbieter(self) -> str:
        return self.einst.get("ki_anbieter") or "claude"

    def zustand(self) -> dict:
        a = self.anbieter
        if a == "aus":
            return {"anbieter": a, "bereit": False,
                    "grund": "KI ist ausgeschaltet."}
        if a == "chat":
            # Bereit für Aufträge, aber nichts im Hintergrund: Jeder Schritt
            # braucht die Rechercheurin am Chat.
            return {"anbieter": a, "bereit": True, "modell": "claude.ai",
                    "websuche": True, "bruecke": True, "hintergrund": False,
                    "hinweis": "Brücke zu claude.ai: Auftrag kopieren, im "
                               "Chat ausführen, Antwort einfügen."}
        if a == "claude":
            if not self.einst.get("claude_schluessel"):
                return {"anbieter": a, "bereit": False,
                        "grund": "Kein Claude-API-Schlüssel hinterlegt "
                                 "(Einstellungen)."}
            return {"anbieter": a, "bereit": True,
                    "modell": self.einst.get("claude_modell"),
                    "websuche": True}
        return {"anbieter": a, "bereit": True,
                "modell": self.einst.get("ollama_modell"), "websuche": False,
                "hinweis": "Lokales Modell: IndraNet sammelt Suchtreffer und "
                           "Registerauszüge selbst."}

    def _claude(self):
        import anthropic
        from anthropic import DefaultHttpxClient
        if self.anbieter != "claude":
            raise KIFehler("Die Claude-API ist nicht als KI gewählt.")
        schluessel = self.einst.get("claude_schluessel")
        if not schluessel:
            raise KIFehler("Kein Claude-API-Schlüssel hinterlegt.")
        proxy = self.netz.ki_proxy()
        return anthropic.Anthropic(
            api_key=schluessel, max_retries=2, timeout=900,
            http_client=DefaultHttpxClient(proxy=proxy) if proxy else None)

    def _claude_aufruf(self, client, fortschritt, **params):
        """Ein gestreamter Aufruf. Meldet Websuchen und Seitenabrufe live."""
        import anthropic
        params.setdefault("model", self.einst.get("claude_modell")
                          or "claude-opus-5-5")
        params.setdefault("max_tokens", 48000)
        # Serverseitiger Ersatz bei Ablehnung durch Schutzfilter: Die API
        # wiederholt dieselbe Anfrage auf einem passenden Modell. Haiku hat
        # keinen solchen Ersatz.
        if "haiku" not in params["model"]:
            params.setdefault("betas", ["server-side-fallback-2026-07-01"])
            params.setdefault("fallbacks", "default")
        try:
            with client.beta.messages.stream(**params) as strom:
                for ev in strom:
                    if ev.type != "content_block_stop" or fortschritt is None:
                        continue
                    blk = strom.current_message_snapshot.content[ev.index]
                    if blk.type == "server_tool_use":
                        e = blk.input or {}
                        if blk.name == "web_search":
                            fortschritt(f"Websuche: {e.get('query', '')}")
                        elif blk.name == "web_fetch":
                            fortschritt(f"Seite: {e.get('url', '')}")
                return strom.get_final_message()
        except anthropic.AuthenticationError:
            raise KIFehler("Claude lehnt den API-Schlüssel ab.")
        except anthropic.PermissionDeniedError as e:
            raise KIFehler(f"Keine Berechtigung: {e.message}")
        except anthropic.RateLimitError:
            raise KIFehler("Claude-Ratenlimit erreicht — bitte kurz warten.")
        except anthropic.APIConnectionError as e:
            raise KIFehler("Keine Verbindung zu Claude"
                           + (" über den eingestellten Netzweg (Tor/Proxy). "
                              "Ggf. 'KI-Anfragen über Proxy' abschalten."
                              if self.netz.ki_proxy() else ".")
                           + f" ({e.__class__.__name__})")
        except anthropic.APIStatusError as e:
            if "credit balance" in str(e.message):
                raise KIFehler("Das Claude-Konto hat kein Guthaben. Unter "
                               "console.anthropic.com → Plans & Billing "
                               "aufladen; der Schlüssel selbst ist gültig.")
            raise KIFehler(f"Claude-Fehler {e.status_code}: {e.message}")

    @staticmethod
    def _kosten(antwort, summe: dict) -> None:
        u = getattr(antwort, "usage", None)
        if u is None:
            return
        summe["eingabe"] = summe.get("eingabe", 0) + (u.input_tokens or 0)
        summe["ausgabe"] = summe.get("ausgabe", 0) + (u.output_tokens or 0)
        stu = getattr(u, "server_tool_use", None)
        if stu is not None:
            summe["websuchen"] = summe.get("websuchen", 0) + (
                getattr(stu, "web_search_requests", 0) or 0)

    @staticmethod
    def _ablehnung(antwort) -> None:
        if antwort.stop_reason == "refusal":
            d = getattr(antwort, "stop_details", None)
            raise KIFehler("Die KI hat diese Anfrage abgelehnt"
                           + (f" ({d.category})" if d and d.category else "")
                           + ". Formulieren Sie den Auftrag sachlicher oder "
                             "enger.")

    # ------------------------------------------------------ Kontext
    @staticmethod
    def _kontext(kontext: dict) -> str:
        teile = []
        if kontext.get("zweck"):
            teile.append(f"Zweck der Recherche: {kontext['zweck']}")
        if kontext.get("entitaeten"):
            teile.append("Bereits im Bestand (nicht erneut belegen, aber "
                         "Verbindungen dazu suchen): "
                         + "; ".join(kontext["entitaeten"][:80]))
        if kontext.get("fokus"):
            teile.append(f"Schwerpunkt: {kontext['fokus']}")
        return "\n".join(teile)

    # ------------------------------------------------------- Recherche
    def recherche(self, auftrag: str, kontext: dict | None = None,
                  fortschritt=None) -> Befund:
        kontext = kontext or {}
        if self.anbieter == "ollama":
            return self._recherche_lokal(auftrag, kontext, fortschritt)
        if self.anbieter != "claude":
            raise KIFehler("KI ist ausgeschaltet.")
        client = self._claude()
        tools = [
            {"type": "web_search_20260209", "name": "web_search",
             "max_uses": 15},
            {"type": "web_fetch_20260209", "name": "web_fetch",
             "max_uses": 10, "max_content_tokens": 30000},
            REGISTER_WERKZEUG,
            BEFUND_WERKZEUG,
        ]
        nutzer = (f"{RECHERCHE_AUFTRAG}\n\n{self._kontext(kontext)}\n\n"
                  f"AUFTRAG: {auftrag}")
        nachrichten = [{"role": "user", "content": nutzer}]
        kosten, suchen = {}, []
        modell = self.einst.get("claude_modell") or "claude-opus-5-5"

        def melde(text):
            suchen.append(text)
            if fortschritt:
                fortschritt(text)

        for runde in range(12):
            antwort = self._claude_aufruf(
                client, melde, system=GRUNDREGELN, tools=tools,
                messages=nachrichten, output_config={"effort": "medium"})
            self._kosten(antwort, kosten)
            self._ablehnung(antwort)

            befund = next((b for b in antwort.content if b.type == "tool_use"
                           and b.name == "befund_melden"), None)
            if befund is not None:
                return Befund(normalisieren(dict(befund.input)),
                              modell=antwort.model, suchen=suchen,
                              kosten=kosten)

            nachrichten.append({"role": "assistant", "content": antwort.content})
            if antwort.stop_reason == "pause_turn":
                continue                    # Server setzt die Suche fort
            register = [b for b in antwort.content if b.type == "tool_use"
                        and b.name == "register_abfragen"]
            if register:
                ergebnisse = []
                for b in register:
                    q, begriff = b.input.get("quelle"), b.input.get(
                        "suchbegriff", "")
                    melde(f"Register {q}: {begriff}")
                    r = quellen_offen.abfragen(self.netz, q, begriff)
                    ergebnisse.append({"type": "tool_result",
                                       "tool_use_id": b.id,
                                       "content": r["text"][:30000]})
                nachrichten.append({"role": "user", "content": ergebnisse})
                continue
            if antwort.stop_reason == "max_tokens":
                raise KIFehler("Antwort zu lang — Auftrag bitte enger fassen.")
            # Fertig, aber ohne Meldung: einmal ausdrücklich nachfordern
            nachrichten.append({"role": "user", "content":
                                "Bitte melde deine Ergebnisse jetzt über das "
                                "Werkzeug befund_melden."})
        raise KIFehler(f"Recherche nach {runde + 1} Runden ohne Befund "
                       "abgebrochen.")

    def _recherche_lokal(self, auftrag: str, kontext: dict,
                         fortschritt=None) -> Befund:
        """Ohne eigene Websuche: Treffer sammeln, Seiten lesen, vorlegen."""
        material, suchen = [], []

        def melde(text):
            suchen.append(text)
            if fortschritt:
                fortschritt(text)

        for q in ("websuche", "wikipedia", "wikidata", "gleif",
                  "offshore_leaks", "gdelt"):
            melde(f"Quelle {q}: {auftrag}")
            r = quellen_offen.abfragen(self.netz, q, auftrag)
            material.append(r["text"])
            if q == "websuche":
                for t in r["treffer"][:4]:
                    try:
                        melde(f"Seite: {t['url']}")
                        s = quellen_offen.seitentext(self.netz, t["url"],
                                                     max_zeichen=6000)
                        material.append(f"SEITE {s['url']} — {s['titel']}\n"
                                        f"{s['text']}")
                    except Exception:                       # noqa: BLE001
                        continue
        prompt = (f"{self._kontext(kontext)}\n\nAUFTRAG: {auftrag}\n\n"
                  "Unten steht gesammeltes Material mit Quelladressen. Werte "
                  "es aus und antworte als JSON nach Schema. Belege nur mit "
                  "Adressen, die im Material vorkommen.\n\n"
                  + "\n\n".join(material)[:60000])
        daten = self._ollama_json(prompt, BEFUND_SCHEMA, melde)
        return Befund(normalisieren(daten), modell=self.einst.get(
            "ollama_modell"), suchen=suchen)

    def _ollama_json(self, prompt: str, schema: dict, fortschritt=None) -> dict:
        import httpx2 as httpx
        url = (self.einst.get("ollama_url") or "http://127.0.0.1:11434"
               ).rstrip("/")
        if fortschritt:
            fortschritt(f"Lokales Modell {self.einst.get('ollama_modell')} "
                        "wertet aus …")
        try:
            r = httpx.post(f"{url}/api/chat", timeout=900, json={
                "model": self.einst.get("ollama_modell"), "stream": False,
                "format": schema, "options": {"temperature": 0.1,
                                              "num_ctx": 32768},
                "messages": [{"role": "system", "content": GRUNDREGELN},
                             {"role": "user", "content": prompt}]})
            r.raise_for_status()
            return json.loads(r.json()["message"]["content"])
        except httpx.ConnectError:
            raise KIFehler(f"Ollama unter {url} nicht erreichbar. Läuft "
                           "Ollama?")
        except (KeyError, json.JSONDecodeError, httpx.HTTPStatusError) as e:
            raise KIFehler(f"Ollama lieferte keine verwertbare Antwort ({e})")

    # ---------------------------------------------------- Dateianalyse
    def datei_analysieren(self, dateiname: str, abschnitte: list[dict],
                          kontext: dict | None = None, *, roh: bytes = b"",
                          medientyp: str = "", fortschritt=None) -> Befund:
        """`abschnitte` = [{"fundstelle", "text"}]. Ohne Text (Scan, Bild)
        bekommt Claude die Datei selbst zu sehen."""
        kontext = kontext or {}
        auftrag = (f"Analysiere die Datei '{dateiname}' für die Recherche. "
                   "Erfasse Personen, Firmen, Orte, Beteiligungen, Zahlungen, "
                   "Beträge, Daten und Funktionen als Aussagen. Als Beleg die "
                   "Fundstelle angeben (steht in eckigen Klammern vor jedem "
                   "Abschnitt). Als Quelle die Datei selbst mit Art 'datei'.")
        texte = [f"[{a['fundstelle']}] {a['text']}" for a in abschnitte
                 if a.get("text", "").strip()]
        bloecke = []
        if texte:
            stueck, laenge = [], 0
            for t in texte:
                if laenge + len(t) > 180000 and stueck:
                    bloecke.append("\n".join(stueck))
                    stueck, laenge = [], 0
                stueck.append(t)
                laenge += len(t)
            bloecke.append("\n".join(stueck))

        if self.anbieter == "ollama":
            if not bloecke:
                raise KIFehler("Die Datei enthält keinen lesbaren Text. Das "
                               "lokale Modell kann Scans und Bilder nicht "
                               "lesen.")
            ergebnisse = [self._ollama_json(
                f"{self._kontext(kontext)}\n\n{auftrag}\n\n{b[:60000]}",
                BEFUND_SCHEMA, fortschritt) for b in bloecke]
            return Befund(_zusammenfuehren(
                [normalisieren(e, datei=True) for e in ergebnisse]),
                modell=self.einst.get("ollama_modell"))

        client = self._claude()
        kosten = {}
        teilbefunde = []
        inhalte = []
        if bloecke:
            for i, b in enumerate(bloecke, 1):
                inhalte.append([{"type": "text", "text":
                                 f"DATEI {dateiname} (Teil {i}/{len(bloecke)})"
                                 f":\n{b}"}])
        elif roh and medientyp == "application/pdf" and len(roh) < 30_000_000:
            inhalte.append([{"type": "document", "source": {
                "type": "base64", "media_type": "application/pdf",
                "data": base64.standard_b64encode(roh).decode()}}])
        elif roh and medientyp in ("image/jpeg", "image/png", "image/gif",
                                   "image/webp") and len(roh) < 5_000_000:
            inhalte.append([{"type": "image", "source": {
                "type": "base64", "media_type": medientyp,
                "data": base64.standard_b64encode(roh).decode()}}])
        else:
            raise KIFehler("Die Datei enthält keinen lesbaren Text und ist "
                           "weder PDF noch Bild.")

        for i, inhalt in enumerate(inhalte, 1):
            if fortschritt:
                fortschritt(f"Lese {dateiname} — Teil {i}/{len(inhalte)}")
            nachrichten = [{"role": "user", "content": inhalt + [
                {"type": "text", "text":
                 f"{self._kontext(kontext)}\n\n{auftrag}\n\nMelde das "
                 "Ergebnis über das Werkzeug befund_melden."}]}]
            for _ in range(3):
                antwort = self._claude_aufruf(
                    client, fortschritt, system=GRUNDREGELN,
                    tools=[BEFUND_WERKZEUG], messages=nachrichten,
                    output_config={"effort": "medium"})
                self._kosten(antwort, kosten)
                self._ablehnung(antwort)
                b = next((x for x in antwort.content if x.type == "tool_use"),
                         None)
                if b is not None:
                    teilbefunde.append(normalisieren(dict(b.input), datei=True))
                    break
                nachrichten += [{"role": "assistant",
                                 "content": antwort.content},
                                {"role": "user", "content":
                                 "Bitte jetzt befund_melden aufrufen."}]
        return Befund(_zusammenfuehren(teilbefunde),
                      modell=self.einst.get("claude_modell"), kosten=kosten)

    # ---------------------------------------------------------- Analyse
    def analysieren(self, frage: str, bestand: str, kontext: dict | None = None,
                    fortschritt=None) -> dict:
        kontext = kontext or {}
        prompt = (f"{self._kontext(kontext)}\n\nFRAGE: "
                  f"{frage or 'Gesamtlage: Was zeigt das Geflecht?'}\n\n"
                  "Unten steht der geprüfte Bestand der Recherche: Fakten mit "
                  "Beleglage (BESTAETIGT = mind. zwei unabhängige Quellen, "
                  "EINFACH_BELEGT = eine Quelle, UMSTRITTEN = Quellen "
                  "widersprechen sich). Schreibe ein qualifiziertes Lagebild. "
                  "Trenne strikt zwischen belegten Fakten und deinen "
                  "Schlussfolgerungen. Nenne Namen exakt wie im Bestand.\n\n"
                  f"{bestand[:400000]}")
        if fortschritt:
            fortschritt("Lagebild wird erstellt …")
        if self.anbieter == "ollama":
            return self._ollama_json(prompt, ANALYSE_SCHEMA, fortschritt)
        client = self._claude()
        antwort = self._claude_aufruf(
            client, None, system=GRUNDREGELN,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "high",
                           "format": {"type": "json_schema",
                                      "schema": ANALYSE_SCHEMA}})
        self._ablehnung(antwort)
        text = next((b.text for b in antwort.content if b.type == "text"), "")
        try:
            daten = json.loads(text)
        except json.JSONDecodeError:
            raise KIFehler("Lagebild nicht lesbar zurückgekommen.")
        daten["_modell"] = antwort.model
        return daten

    # ------------------------------------------------------- Vorschläge
    def vorschlagen(self, bestand: str, kontext: dict | None = None) -> dict:
        """Folgerecherchen und vermutete Verbindungen — läuft im Hintergrund
        nach jeder Übernahme in den Bestand."""
        prompt = (f"{self._kontext(kontext or {})}\n\nHier ist der aktuelle "
                  "Bestand einer Recherche. Schlage bis zu 5 Folgerecherchen "
                  "vor, die das Geflecht am wahrscheinlichsten erweitern "
                  "(Eigentümer hinter Firmen, Geldflüsse, Gegenparteien, "
                  "Verfahren), und bis zu 5 vermutete, noch unbelegte "
                  "Verbindungen zwischen vorhandenen Entitäten.\n\n"
                  f"{bestand[:150000]}")
        if self.anbieter == "ollama":
            return self._ollama_json(prompt, VORSCHLAG_SCHEMA)
        client = self._claude()
        antwort = self._claude_aufruf(
            client, None, system=GRUNDREGELN, max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low",
                           "format": {"type": "json_schema",
                                      "schema": VORSCHLAG_SCHEMA}})
        self._ablehnung(antwort)
        text = next((b.text for b in antwort.content if b.type == "text"), "{}")
        return json.loads(text)


def _zusammenfuehren(teile: list[dict]) -> dict:
    if len(teile) == 1:
        return teile[0]
    raus = {"zusammenfassung": "\n\n".join(t["zusammenfassung"] for t in teile
                                            if t["zusammenfassung"]),
            "entitaeten": [], "aussagen": [], "orte": [], "quellen": [],
            "offene_fragen": [], "naechste_schritte": []}
    gesehen = set()
    for t in teile:
        for e in t["entitaeten"]:
            k = (e["name"].lower(), e["typ"])
            if k not in gesehen:
                gesehen.add(k)
                raus["entitaeten"].append(e)
        raus["aussagen"] += t["aussagen"]
        raus["orte"] += [o for o in t["orte"]
                         if o["name"] not in {x["name"] for x in raus["orte"]}]
        raus["quellen"] += [q for q in t["quellen"]
                            if q["url"] not in {x["url"]
                                                for x in raus["quellen"]}]
        raus["offene_fragen"] += t["offene_fragen"]
        raus["naechste_schritte"] += t["naechste_schritte"]
    return raus
