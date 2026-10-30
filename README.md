# IndraNet

**Offenes Recherchesystem für investigativen Journalismus**
*Open research system for investigative journalism — [English summary below](#english)*

IndraNet hilft Journalistinnen und Journalisten, in öffentlich zugänglichen
Daten Spuren zu verfolgen: Wem gehört eine Briefkastenfirma? Wer steht auf
einer Sanktionsliste? Wohin fließt Geld, welches Schiff gehört wem, welches
Flugzeug ist gerade wo unterwegs? Eine KI recherchiert im Netz und in offenen
Registern. Ein Mensch prüft jeden Fund, bevor er in den Bestand übernommen
wird. Aus den geprüften Fakten wächst ein Netz auf Graph und Weltkarte.

Alles läuft auf dem eigenen Rechner. Jedes Projekt liegt verschlüsselt auf der
Platte, Abrufe können über Tor laufen, und Recherche-Netzwerke verbinden
Kolleginnen ohne zentralen Server.

> Die Daten bleiben, wo sie hingehören.

---

## Was IndraNet anders macht

**Die Aussage ist das Grundobjekt.** Ein Fakt ist das Bündel aller Aussagen,
die dieselbe Behauptung tragen, jede mit Quelladresse und wörtlichem Zitat.
Daraus ergibt sich die **Beleglage**: bestätigt (zwei unabhängige Quellen),
einfach belegt, umstritten, widerrufen. Wird eine Quelle zurückgezogen, sieht
man sofort, was alles daran hing.

**Die KI schreibt nie selbst in den Bestand.** Sie liefert *Befunde* in einem
geschlossenen Vokabular von Beziehungen. Aussagen ohne Quelladresse verwirft
IndraNet schon vorher. Alles Übrige landet im **Prüfkorb**, wo ein Mensch
abhakt, korrigiert und übernimmt. Bei der Übernahme wird die Quellseite
abgerufen und verschlüsselt mitgespeichert: Die Seite kann sich morgen ändern,
der Beleg bleibt.

**Nur öffentliche Daten, nur rechtmäßige Wege.** IndraNet fragt offene
Register und Schnittstellen ab. Flugzeuge und Schiffe werden über ihre
Kennung gesucht, nie Personen über ihren Aufenthaltsort.

---

## Funktionen

- **Suchfeld wie eine Suchmaschine** mit drei Arten:
  **WEB** (KI recherchiert im Netz und in Registern),
  **REGISTER** (ein Register direkt, ohne KI),
  **BESTAND** (Frage an die eigenen geprüften Daten).
- **Dateien analysieren**: Word, Excel, PowerPoint, OpenDocument, PDF, E-Mail,
  CSV, JSON, HTML, Text; Scans und Bilder liest Claude direkt.
- **Prüfkorb** mit Aussagen, Quellen, Zitaten, Entitäten, Orten und offenen Fragen.
- **Netz**: Kraftgraph, Kanten nach Beleglage gefärbt, Geldflüsse sichtbar.
- **Karte**: Weltkarte oder Globus mit Orten und Verbindungen
  (Kartendaten mitgeliefert, keine Kachelabrufe nach außen).
- **Akten** je Person oder Firma mit allen Fakten, Belegen, Notizen und Widerruf.
- **Lagebilder**: Die KI fasst den geprüften Bestand zusammen, mit Beleglage,
  Schlüsselfiguren, Geldflüssen, Zeitleiste, Lücken und nächsten Schritten.
- **Vorschläge und Autopilot**: Nach jeder Übernahme schlägt die KI
  Folgerecherchen vor; auf Wunsch startet sie die besten selbst.
- **Recherche-Netzwerke über Tor**: Einladung per Einmalcode, Mitgliedschaften
  und Freigaben mit Ed25519 signiert, Abgleich verschlüsselt über `.onion`.
  Geteilt werden nur Fakten mit öffentlichen Belegen.
- **Fiktive Beispieldaten** zum Ausprobieren ohne KI-Schlüssel.

## Datenquellen

| Quelle | Inhalt | Zugang |
|---|---|---|
| GLEIF | Firmen, LEI, Konzernmütter | frei |
| ICIJ Offshore Leaks | Briefkastenfirmen aus Panama Papers u. a. | frei |
| Wikidata, Wikipedia | Personen, Organisationen, Ämter | frei |
| GDELT | weltweite Presse | frei |
| Websuche | über die KI | frei |
| OpenSanctions | Sanktionslisten, politisch exponierte Personen, Fahndungen | Schlüssel, für Journalismus kostenlos |
| adsb.lol | Flugzeuge über Kennzeichen, ICAO-Hex oder Rufzeichen | frei |
| Global Fishing Watch | Schiffe über Name, IMO oder MMSI, mit Flagge und Eigner | Token, für Recherche kostenlos |

Die Nutzungsbedingungen der Quellen gelten, siehe [LIZENZHINWEIS.md](LIZENZHINWEIS.md).
OpenSanctions- und Global-Fishing-Watch-Daten sind nur nicht-kommerziell frei.

## KI

| | Claude-API | claude.ai (Abo) | Ollama (lokal) |
|---|---|---|---|
| Ablauf | automatisch im Hintergrund | Auftrag kopieren → im Chat ausführen → Antwort einfügen | automatisch |
| Kosten | API-Guthaben | im Abo enthalten | keine |
| Wer sieht die Anfrage | Anthropic | Anthropic | nur die abgefragten Quellen |

Die Brücke zu claude.ai nutzt die eigene Anmeldung nicht maschinell: IndraNet
erzeugt einen Auftrag zum Kopieren, Sie führen ihn im eigenen Chat aus und
fügen die Antwort wieder ein. Sie wird geprüft wie jeder andere KI-Befund.
Ohne KI funktionieren Registerabfragen, Prüfkorb, Netz, Karte und Bestand
weiterhin.

---

## Installation

Voraussetzung: Python 3 (getestet mit 3.13) unter Windows. Linux und macOS
sind nicht erprobt; Tor und der Schlüsselschutz per DPAPI sind auf Windows
ausgelegt.

```bash
git clone https://github.com/Dirk4171/IndraNet.git
cd IndraNet
python -m pip install -r requirements.txt
python indranet.py
```

Der Browser öffnet sich unter `http://127.0.0.1:8710`. Optionen:
`--port 8720`, `--kein-browser`, `--daten E:\IndraNet` (eigener Datenordner,
etwa auf einem verschlüsselten USB-Stick).

**Tor (empfohlen):** Das *Tor Expert Bundle* für Windows von
[torproject.org/download/tor](https://www.torproject.org/download/tor/) laden
und so entpacken, dass `tor\tor\tor.exe` im Programmordner liegt. Ersatzweise
nutzt IndraNet einen installierten Tor Browser. Ist Tor gewählt, aber nicht
verbunden, bricht jeder Abruf ab; es gibt keinen stillen Rückfall auf die
direkte Verbindung. Für Netze oder Virenscanner, die Tor stören, sind
obfs4-, Snowflake- und meek-Brücken eingebaut.

**Windows-Version bauen:** `build_windows.bat`, danach `installer.iss` mit
Inno Setup 6. Siehe [BUILD.md](BUILD.md).

**Tests:**

```bash
python test_v2.py         # Version 2: Server, KI-Brücke, Quellen, Netzwerke
python test_indranet.py   # Kern: Aussagen, Beleglage, Verschlüsselung, Abgleich
python test_tor.py        # zwei Installationen über das echte Tor-Netz (dauert Minuten)
```

---

## Sicherheit

- Die Oberfläche bindet nur an `127.0.0.1`, prüft den Host-Kopf und verlangt
  eine Sitzungsmarke je Programmstart. Sie lädt nichts aus dem Netz nach.
- Projekte: scrypt + AES-256-GCM. Klartext gibt es nur im Arbeitsspeicher.
  **Ohne Passphrase gibt es keine Wiederherstellung.**
- API-Schlüssel werden unter Windows mit DPAPI an das Benutzerkonto gebunden.
- Abgelegte Webseiten werden in einer Sandbox ohne Skripte angezeigt.

**Grenzen:** Der Arbeitsspeicher im laufenden Betrieb ist nicht geschützt,
ebenso wenig ein Rechner mit Schadsoftware. Bei Claude-Anfragen sieht
Anthropic den Inhalt. Links, die Sie in der Oberfläche anklicken, öffnet der
normale Browser, nicht Tor.

## Verantwortung

IndraNet verarbeitet öffentlich zugängliche Daten, auch über Menschen. Für
Journalistinnen gilt das Medienprivileg (Art. 85 DSGVO), für alle der
Pressekodex: Unschuldsvermutung, Verdachtsberichterstattung nur mit einem
Mindestbestand an Beweistatsachen, Schutz Unbeteiligter. Ein Treffer in
einem Leak, einem Register oder auf einer Sanktionsliste ist ein Prüfhinweis
und kein Beleg für eine Straftat. Jedes Projekt hält deshalb seinen
**Zweck** fest.

Die Software ersetzt keine journalistische Sorgfalt und keine rechtliche
Prüfung vor einer Veröffentlichung.

---

## Dokumentation

| | |
|---|---|
| [LIESMICH_V2.md](LIESMICH_V2.md) | Bedienung von Version 2, ausführlich |
| [WHITEPAPER.de.md](WHITEPAPER.de.md) · [en](WHITEPAPER.en.md) | Architektur des Kerns |
| [MANUAL.de.md](MANUAL.de.md) · [en](MANUAL.en.md) | Handbuch des Kerns (Version 1) |
| [BUILD.md](BUILD.md) | Windows-Version bauen |
| [LIZENZHINWEIS.md](LIZENZHINWEIS.md) | Fremdbestandteile und Datenlizenzen |

## Herkunft

Das Abgleichprotokoll für Netzwerke folgt **DatashareNetwork** (EPFL SPRING
Lab · ICIJ, USENIX Security 2020).

## Lizenz

GNU Affero General Public License v3.0, siehe [LICENSE](LICENSE).
© 2026 VELVIUM Technologies UG (haftungsbeschränkt).

---

<a id="english"></a>
## English

IndraNet is an open-source research tool for investigative journalists. It
follows leads in publicly accessible data: shell companies, sanctions lists,
money flows, vessels and aircraft (searched by identifier, never people by
location). An AI researches the web and open registries (GLEIF, ICIJ Offshore
Leaks, OpenSanctions, Wikidata, Wikipedia, GDELT, adsb.lol, Global Fishing
Watch); a human reviews every finding before it enters the record. Every
assertion carries its source URL and a verbatim quote; facts are graded as
corroborated, single-sourced, disputed or retracted.

Everything runs locally. Projects are encrypted on disk (scrypt + AES-256-GCM),
network requests can be routed through Tor with no silent fallback, and
research networks connect colleagues over `.onion` addresses with signed
memberships and shares — no central server.

AI options: Claude API, a copy-and-paste bridge to a claude.ai subscription,
or a local Ollama model. The interface is in German.

```bash
python -m pip install -r requirements.txt
python indranet.py
```

Licensed under the GNU AGPL v3.0.
