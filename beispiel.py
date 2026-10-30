"""
IndraNet — Beispielbefunde
===========================

Zwei fiktive Befunde zum Ausprobieren ohne KI-Schlüssel: eine
Briefkastenfirma in Panama, ein Trust auf Jersey, eine Reederei in Oslo,
ein Zahlungskreislauf über Estland. Alle Namen, Firmen und Adressen sind
erfunden; die Quelladressen liegen unter der reservierten Endung .example
und führen nirgendwohin.

Die Befunde durchlaufen den normalen Weg: Prüfkorb → Übernahme → Bestand.
Zusammen ergeben sie bestätigte Fakten (zwei unabhängige Quellen), einen
Widerspruch (zwei Sitze) und einen Geldkreislauf.
"""

from __future__ import annotations

HINWEIS = "BEISPIELDATEN — vollständig erfunden."

_QUELLEN_1 = [
    {"url": "https://register.panama.example/sociedad/155694123",
     "titel": "Registro Público: Mare Liberum Ltd.", "herausgeber":
     "Registro Público (fiktiv)", "art": "register", "datum": "2026-03-02"},
    {"url": "https://zeitung.example/2026/04/offshore-reederei",
     "titel": "Die Spur führt nach Panama", "herausgeber":
     "Nordkurier (fiktiv)", "art": "presse", "datum": "2026-04-18"},
    {"url": "https://jersey-fsc.example/trusts/svensson",
     "titel": "Trust register extract", "herausgeber":
     "Jersey FSC (fiktiv)", "art": "register", "datum": "2026-02-11"},
]

BEFUND_1 = {
    "zusammenfassung": (
        f"{HINWEIS} Die Mare Liberum Ltd. ist laut Handelsregister in Panama "
        "eingetragen; Direktor ist der Hamburger Kaufmann Anders Holm. "
        "Wirtschaftlich berechtigt ist der Svensson Family Trust mit Sitz auf "
        "Jersey. Ein Pressebericht beschreibt Zahlungen der Mare Liberum an "
        "die Osloer Reederei Nordkap Shipping AS. Der Bericht spricht von "
        "einem Verdacht auf Sanktionsumgehung — ein Verfahren ist nicht "
        "bekannt."),
    "entitaeten": [
        {"name": "Mare Liberum Ltd.", "typ": "ORG", "aliase": [],
         "beschreibung": "Gesellschaft mit Sitz in Panama, ohne erkennbaren "
                         "Geschäftsbetrieb"},
        {"name": "Anders Holm", "typ": "PERSON", "aliase": ["A. Holm"],
         "beschreibung": "Kaufmann aus Hamburg, Direktor mehrerer "
                         "Auslandsgesellschaften"},
        {"name": "Svensson Family Trust", "typ": "ORG", "aliase": [],
         "beschreibung": "Familientrust auf Jersey"},
        {"name": "Nordkap Shipping AS", "typ": "ORG", "aliase": [],
         "beschreibung": "Reederei in Oslo"},
    ],
    "aussagen": [
        {"subjekt": "Mare Liberum Ltd.", "praedikat": "registered_in",
         "objekt": "Panama", "beleg": _QUELLEN_1[0]["url"],
         "zitat": "Sociedad inscrita … domicilio: Ciudad de Panamá",
         "datum": "2026-03-02", "sicherheit": "hoch"},
        {"subjekt": "Anders Holm", "praedikat": "director_of",
         "objekt": "Mare Liberum Ltd.", "beleg": _QUELLEN_1[0]["url"],
         "zitat": "Director: HOLM, Anders", "datum": "2026-03-02",
         "sicherheit": "hoch"},
        {"subjekt": "Svensson Family Trust",
         "praedikat": "beneficial_owner_of", "objekt": "Mare Liberum Ltd.",
         "beleg": _QUELLEN_1[2]["url"], "zitat": "beneficial owner: "
         "Svensson Family Trust", "datum": "2026-02-11", "sicherheit": "hoch"},
        {"subjekt": "Svensson Family Trust", "praedikat": "registered_in",
         "objekt": "Jersey", "beleg": _QUELLEN_1[2]["url"], "zitat": "",
         "datum": "", "sicherheit": "hoch"},
        {"subjekt": "Mare Liberum Ltd.", "praedikat": "paid_to",
         "objekt": "Nordkap Shipping AS", "beleg": _QUELLEN_1[1]["url"],
         "zitat": "… mehrere Überweisungen an die Osloer Reederei …",
         "datum": "2026-04-18", "sicherheit": "mittel"},
        {"subjekt": "Anders Holm", "praedikat": "resident_in",
         "objekt": "Hamburg", "beleg": _QUELLEN_1[1]["url"], "zitat": "",
         "datum": "", "sicherheit": "mittel"},
        {"subjekt": "Nordkap Shipping AS", "praedikat": "registered_in",
         "objekt": "Oslo", "beleg": _QUELLEN_1[1]["url"], "zitat": "",
         "datum": "", "sicherheit": "mittel"},
    ],
    "orte": [
        {"name": "Panama", "lat": 8.98, "lon": -79.52, "land_iso": "PA",
         "genauigkeit": "land"},
        {"name": "Jersey", "lat": 49.19, "lon": -2.11, "land_iso": "JE",
         "genauigkeit": "land"},
        {"name": "Hamburg", "lat": 53.55, "lon": 9.99, "land_iso": "DE",
         "genauigkeit": "stadt"},
        {"name": "Oslo", "lat": 59.91, "lon": 10.75, "land_iso": "NO",
         "genauigkeit": "stadt"},
    ],
    "quellen": _QUELLEN_1,
    "offene_fragen": ["Ist Anders Holm aus dem Register derselbe wie der "
                      "Hamburger Kaufmann im Pressebericht?",
                      "Wofür wurden die Zahlungen an Nordkap geleistet?"],
    "naechste_schritte": ["Nordkap Shipping AS Eigentümer Brønnøysund",
                          "Svensson Family Trust Begünstigte"],
}

_QUELLEN_2 = [
    {"url": "https://brreg.example/enhet/923456781",
     "titel": "Enhetsregisteret: Nordkap Shipping AS", "herausgeber":
     "Brønnøysundregistrene (fiktiv)", "art": "register",
     "datum": "2026-05-06"},
    {"url": "https://bvi-leaks.example/node/88123",
     "titel": "Leak-Datensatz Mare Liberum", "herausgeber":
     "Leak-Datenbank (fiktiv)", "art": "leak", "datum": "2025-11-30"},
    {"url": "https://ariregister.example/14512377",
     "titel": "Äriregister: Baltic Bunker OÜ", "herausgeber":
     "e-Äriregister (fiktiv)", "art": "register", "datum": "2026-05-09"},
]

BEFUND_2 = {
    "zusammenfassung": (
        f"{HINWEIS} Nordkap Shipping AS ist in Oslo registriert; Direktor ist "
        "Erik Svensson, der Name deutet auf eine Verbindung zum Svensson "
        "Family Trust. Nordkap hält Anteile an der Baltic Bunker OÜ in "
        "Tallinn, die ihrerseits an Mare Liberum gezahlt hat — ein "
        "Zahlungskreislauf. Ein Leak-Datensatz führt Mare Liberum mit Sitz "
        "auf den Britischen Jungferninseln, was dem Register in Panama "
        "widerspricht."),
    "entitaeten": [
        {"name": "Erik Svensson", "typ": "PERSON", "aliase": [],
         "beschreibung": "Direktor der Nordkap Shipping AS"},
        {"name": "Baltic Bunker OÜ", "typ": "ORG", "aliase": [],
         "beschreibung": "Bunkerhändler in Tallinn"},
        {"name": "MV Polarstern", "typ": "VESSEL", "aliase": [],
         "beschreibung": "Tanker, betrieben von Nordkap Shipping"},
    ],
    "aussagen": [
        {"subjekt": "Nordkap Shipping AS", "praedikat": "registered_in",
         "objekt": "Oslo", "beleg": _QUELLEN_2[0]["url"],
         "zitat": "Forretningsadresse: Oslo", "datum": "2026-05-06",
         "sicherheit": "hoch"},
        {"subjekt": "Erik Svensson", "praedikat": "director_of",
         "objekt": "Nordkap Shipping AS", "beleg": _QUELLEN_2[0]["url"],
         "zitat": "Daglig leder: Erik Svensson", "datum": "2026-05-06",
         "sicherheit": "hoch"},
        {"subjekt": "Nordkap Shipping AS", "praedikat": "holds_shares_in",
         "objekt": "Baltic Bunker OÜ", "beleg": _QUELLEN_2[2]["url"],
         "zitat": "osanik: Nordkap Shipping AS (60 %)", "datum": "2026-05-09",
         "sicherheit": "hoch"},
        {"subjekt": "Baltic Bunker OÜ", "praedikat": "registered_in",
         "objekt": "Tallinn", "beleg": _QUELLEN_2[2]["url"], "zitat": "",
         "datum": "", "sicherheit": "hoch"},
        {"subjekt": "Baltic Bunker OÜ", "praedikat": "paid_to",
         "objekt": "Mare Liberum Ltd.", "beleg": _QUELLEN_2[1]["url"],
         "zitat": "invoice settlement … Mare Liberum", "datum": "2025-11-30",
         "sicherheit": "mittel"},
        {"subjekt": "Mare Liberum Ltd.", "praedikat": "registered_in",
         "objekt": "Britische Jungferninseln", "beleg": _QUELLEN_2[1]["url"],
         "zitat": "jurisdiction: BVI", "datum": "2025-11-30",
         "sicherheit": "mittel"},
        {"subjekt": "Anders Holm", "praedikat": "director_of",
         "objekt": "Mare Liberum Ltd.", "beleg": _QUELLEN_2[1]["url"],
         "zitat": "officer: Anders Holm", "datum": "2025-11-30",
         "sicherheit": "mittel"},
        {"subjekt": "Nordkap Shipping AS", "praedikat": "operates_vessel",
         "objekt": "MV Polarstern", "beleg": _QUELLEN_2[0]["url"],
         "zitat": "", "datum": "", "sicherheit": "niedrig"},
    ],
    "orte": [
        {"name": "Tallinn", "lat": 59.44, "lon": 24.75, "land_iso": "EE",
         "genauigkeit": "stadt"},
        {"name": "Britische Jungferninseln", "lat": 18.42, "lon": -64.64,
         "land_iso": "VG", "genauigkeit": "land"},
    ],
    "quellen": _QUELLEN_2,
    "offene_fragen": ["Ist Erik Svensson Begünstigter des Svensson Family "
                      "Trust?", "Welcher Sitz der Mare Liberum stimmt?"],
    "naechste_schritte": ["Erik Svensson Svensson Family Trust",
                          "MV Polarstern IMO Flaggenstaat"],
}


def laden(projekt) -> list[str]:
    ids = []
    for anfrage, befund in (("Mare Liberum Ltd.", BEFUND_1),
                            ("Nordkap Shipping AS", BEFUND_2)):
        ids.append(projekt.fund_anlegen(
            art="web", anfrage=anfrage, befund={**befund, "_suchen": [
                "Beispiel: keine echte Recherche"]},
            herkunft="Beispieldaten", titel=f"{anfrage} (Beispiel)"))
    projekt.verlauf_eintragen("beispiel", "Beispielbefunde geladen")
    return ids
