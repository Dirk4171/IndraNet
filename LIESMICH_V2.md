# IndraNet 2 — Offenes Recherchesystem

IndraNet 2 ist ein Open-Source-Werkzeug für Recherchen in öffentlichen Daten:
Personen, Firmen, Schiffe, Geldflüsse, Verflechtungen. Eine KI recherchiert im
Netz und in offenen Registern, ein Mensch prüft, was davon trägt, und das
Ergebnis wächst zu einem Netz auf Karte und Graph. Recherche-Netzwerke
verbinden Journalistinnen weltweit über Tor, ohne Server.

Der Kern aus Version 1 bleibt unverändert: Die **Aussage** ist das primäre
Objekt, jeder Fakt hat eine **Beleglage** (bestätigt, einfach belegt,
umstritten, widerrufen), das Projekt liegt **verschlüsselt** auf der Platte.

---

## Starten

**Mit der Windows-Version:** `IndraNet.exe` doppelklicken. Der Browser öffnet
sich unter `http://127.0.0.1:8710`. Das schwarze Fenster ist der Server —
schließen beendet IndraNet und sichert das Projekt.

**Aus dem Quelltext:**

```
python -m pip install -r requirements.txt
python indranet.py
```

Optionen: `--port 8720`, `--kein-browser`, `--daten E:\IndraNet` (eigener
Datenordner, z. B. auf einem verschlüsselten USB-Stick).

Ohne KI-Schlüssel ausprobieren: Projekt anlegen, dann auf der Lage-Seite
**„Fiktive Beispieldaten ausprobieren"**. Zwei erfundene Befunde landen im
Prüfkorb.

---

## Arbeitsablauf

1. **Projekt** anlegen oder öffnen. Name, Zweck, Passphrase (mind. 10
   Zeichen, keine Wiederherstellung). Der Zweck hält fest, wozu recherchiert
   wird — das ist Ihre Rechenschaft nach DSGVO und Pressekodex.
2. **Suchen** im Feld oben, wie in einer Suchmaschine:
   - **WEB** — die KI recherchiert im Netz, ruft Seiten ab und befragt
     Register (GLEIF, ICIJ Offshore Leaks, OpenSanctions, Wikidata,
     Wikipedia, GDELT).
   - **REGISTER** — ein Register direkt abfragen, ohne KI.
   - **BESTAND** — Frage an die eigenen, geprüften Daten → Lagebild.
   - **Datei** ins Fenster ziehen oder ⇪ klicken: Word, Excel, PowerPoint,
     OpenDocument, PDF, E-Mail, CSV, JSON, HTML, Text. Scans und Bilder liest
     Claude direkt. Die Datei wird verschlüsselt abgelegt, die KI analysiert sie.
3. **Prüfkorb**: Jeder Befund zeigt Aussagen mit Quelle und Zitat,
   Entitäten, Orte, offene Fragen. Sie haken an, was trägt, korrigieren
   Schreibweisen und Beziehungen und übernehmen. Dabei wird jede Quellseite
   abgerufen und verschlüsselt mitgespeichert — die Seite kann morgen anders
   aussehen, Ihr Beleg nicht.
4. **Im Hintergrund** schaut die KI nach jeder Übernahme auf den gewachsenen
   Bestand und schlägt Folgerecherchen und vermutete Verbindungen vor
   („Anschlussstellen"). Mit **Autopilot** startet sie die besten selbst —
   die Ergebnisse landen wieder im Prüfkorb.
5. **Lage, Netz, Karte**: Kennzahlen, Kraftgraph (Kanten nach Beleglage
   gefärbt, Geldflüsse animiert, Umstrittenes rot), Weltkarte oder Globus mit
   Orten und Verbindungsbögen. Klick auf eine Entität öffnet ihre Akte mit
   allen Fakten, Belegen, Notiz und Widerruf.
6. **Lagebilder**: Die KI schreibt über den geprüften Bestand ein Lagebild —
   Kernaussagen mit Beleglage, Schlüsselfiguren im Netzausschnitt,
   Geldflüsse, Zeitleiste, Lücken, Warnsignale, nächste Schritte. Eigene
   Schlussfolgerungen sind als solche gekennzeichnet. Export als Markdown.
7. **Bestand**: alle Fakten, filterbar; Dubletten zusammenführen (nur mit
   Begründung); Dossier exportieren; Fakten im Netzwerk freigeben.

---

## KI

| | Claude-API (Vorgabe) | claude.ai (Abo) | Ollama (lokal) |
|---|---|---|---|
| Websuche | eingebaut (serverseitig) | im Chat einschalten | IndraNet sammelt Treffer selbst |
| Register | als Werkzeug der KI | vorab abgefragt, im Auftrag | vorab abgefragt |
| Scans/Bilder | ja | ja (Datei im Chat anhängen) | nein |
| Ablauf | automatisch im Hintergrund | Kopieren → Chat → Einfügen | automatisch |
| Vorschläge, Autopilot | ja | nein | ja |
| Kosten | API-Guthaben, je Recherche ca. 0,05–1,50 € | im Abo enthalten | keine |
| Wer sieht die Anfrage | Anthropic | Anthropic (unter Ihrem Konto) | niemand außer den Quellen |

**Claude-API:** Den API-Schlüssel tragen Sie unter **System** ein. Unter
Windows wird er mit DPAPI an Ihr Benutzerkonto gebunden. Modell: Opus 5.5
(gründlich), Sonnet 5.5 (schneller), Haiku 5.5 (günstig). Bei Ablehnung durch
Schutzfilter wiederholt die API die Anfrage serverseitig auf einem passenden
Modell. Die API wird getrennt vom Claude-Abo abgerechnet (Guthaben in der
Console); ohne Guthaben meldet IndraNet „Das Claude-Konto hat kein
Guthaben".

### Claude im Abo — die Brücke zu claude.ai

Ein Claude-Abo (Pro, Max) gilt nur in Anthropics eigenen Programmen;
fremde Programme dürfen die Anmeldung nicht verwenden. Wer kein
API-Guthaben will, wählt unter **System → KI** „claude.ai (Abo)". Dann:

1. Suchauftrag eingeben wie gewohnt. IndraNet fragt GLEIF, Offshore Leaks,
   Wikidata und Wikipedia ab (höchstens 45 s) und schreibt den Auftrag: mit
   Grundregeln, geschlossenem Prädikatsvokabular, Antwortvorlage und den
   Registerauszügen.
2. Im Dialog **Auftrag kopieren**, **claude.ai öffnen**, neuen Chat
   beginnen, Websuche einschalten, einfügen, abschicken.
3. Claudes Antwort kopieren (am einfachsten über den Kopieren-Knopf am
   JSON-Block) und in IndraNet **einfügen** → Prüfkorb.

IndraNet prüft die Antwort wie jeden KI-Befund: Aussagen ohne Quelladresse
oder mit Prädikat außerhalb der Liste fallen weg, die Zahl wird gemeldet.
Dasselbe gilt für Dateien (Text steht im Auftrag; Scans und große Dateien im
Chat anhängen) und Lagebilder. Ein geschlossener Dialog lässt sich über die
Auftragsliste („Ihre Antwort") wieder öffnen, solange IndraNet läuft.
claude.ai läuft im normalen Browser, nicht über Tor.

Die KI schreibt **nie** selbst in den Bestand. Aussagen ohne Quelladresse
verwirft IndraNet schon vor dem Prüfkorb.

### Datenquellen

Fest eingebaut und ohne Zugang nutzbar: **GLEIF** (Firmen, LEI,
Konzernmütter), **ICIJ Offshore Leaks** (Briefkastenfirmen aus Leaks),
**Wikidata**, **Wikipedia**, **GDELT** (Presse) und die **Websuche**.

**OpenSanctions** (unter **System → Datenquellen**) bündelt amtliche
Sanktionslisten, politisch exponierte Personen (PEP), Fahndungen und
Einträge zu organisierter Kriminalität aus über 250 Quellen — die ergiebigste
offene Quelle für Kriegsverbrecher, Sanktionierte und Wirtschaftskriminelle.
Dafür ist ein eigener API-Schlüssel nötig, für journalistische und
gemeinnützige Arbeit kostenlos unter opensanctions.org/api. Der Schlüssel
wird wie der Claude-Schlüssel geschützt abgelegt (Windows: DPAPI). Ist er
hinterlegt, fragt auch die Brücke zu claude.ai ihn mit ab.

Die Daten stehen unter **CC BY-NC 4.0**: Quelle „OpenSanctions" nennen, nur
nicht-kommerziell. Kommerzielle Redaktionen brauchen eine Lizenz von
OpenSanctions. Und: Eine Listung ist ein Prüfhinweis, kein Urteil — warum
jemand gelistet ist, sagen die genannten Listen und Einstufungen; prüfen muss
es der Mensch.

**Flugzeuge und Schiffe** verfolgt IndraNet über ihre **Kennung** — nicht über
Personen. Gesucht wird ein Fahrzeug, verknüpft wird es mit seinem Halter.

- **Flugzeug** (ohne Zugang): aktuelle Position und Eckdaten zu einem
  Luftfahrzeugkennzeichen (D-ABCD), einer ICAO-Hex-Kennung (3c6444) oder
  einem Rufzeichen (DLH400). Quelle ist **adsb.lol**, ein offenes
  ADS-B-Empfängernetz — dieselben Daten, die ADS-B Exchange früher frei
  anbot und heute verkauft. Angezeigt werden Typ, Position, Höhe, Kurs,
  Halter (soweit bekannt) und ein Notfall-Transpondercode (7500/7600/7700).
  Es werden nur Flugzeuge gefunden, die gerade senden.
- **Schiff** (**System → Datenquellen**, Token nötig): Name, Flagge, IMO,
  MMSI, Rufzeichen, Typ und Eigner zu Name, IMO oder MMSI — aus über 40
  Schiffsregistern und den AIS-Selbstmeldungen. Quelle ist **Global Fishing
  Watch**, auf das Aufdecken von illegaler Fischerei, Umflaggung und
  Sanktionsumgehung ausgelegt. Der Token ist für Recherche und gemeinnützige
  Arbeit kostenlos unter globalfishingwatch.org/our-apis/tokens; Global
  Fishing Watch ist als Quelle zu nennen (nicht-kommerziell).

Einen freien, schlüssellosen AIS-Abruf gibt es nicht — AIS-Positionsdienste
sind sonst kommerziell.

---

## IP-Verschleierung

Unter **System → Netzweg**:

- **Direkt** — schnell, Ihre IP ist für Register und Webseiten sichtbar.
- **Tor** — IndraNet startet einen eigenen Tor-Prozess. In der Windows-Version mitgeliefert ist das
  Tor Expert Bundle im Ordner `tor` (`tor\tor\tor.exe`, Brückenprogramme in
  `tor\tor\pluggable_transports`, GeoIP-Daten in `tor\data`); ersatzweise
  wird ein installierter Tor Browser genutzt. Alle Abrufe laufen dann über
  Tor, auch die DNS-Auflösung.
- **Proxy** — eigener SOCKS5- oder HTTP-Proxy (z. B. vom VPN-Anbieter).

Ist Tor gewählt, aber nicht verbunden, **bricht jeder Abruf ab** — kein
stiller Rückfall auf die direkte Verbindung. „Verbindung prüfen" zeigt, unter
welcher Adresse Sie nach außen erscheinen.

### Brücken — wenn Tor bei 14 % hängen bleibt

Manche Virenscanner brechen jede verschlüsselte Verbindung auf, um sie zu
prüfen — etwa die HTTPS-Prüfung von **Avast** („Web-Schutz"), ähnlich
Kaspersky und ESET. Tor erkennt das am fremden Zertifikat („bad CERTS cell")
und verweigert die Verbindung. Dasselbe passiert in Netzen, die Tor sperren.

Abhilfe sind **Brücken**, deren Verkehr nicht nach TLS aussieht. Unter
System → Netzweg → Tor → **Brücken**:

| Wahl | Verhalten |
|---|---|
| Automatisch (Vorgabe) | erst direkt; hängt der Aufbau, nach etwa 15–45 s selbsttätig obfs4. Die Wahl wird für den nächsten Start gemerkt. |
| Keine | immer direkt |
| obfs4 / Snowflake / meek | immer über die eingebauten Brücken dieser Art |
| Eigene | Brückenzeilen von bridges.torproject.org einfügen |

Nach einer Änderung „Tor (neu) starten". Die Kopfzeile zeigt die aktive
Brücke an (`TOR · OBFS4`). Wer lieber direkt verbindet, kann in Avast für
`tor.exe` eine Ausnahme von der HTTPS-Prüfung eintragen — das ist eine
Entscheidung über die eigene Sicherheitssoftware, IndraNet ändert dort
nichts.

Test über das echte Tor-Netz (zwei Instanzen, Beitritt und Abgleich über
`.onion`, dauert einige Minuten): `python test_tor.py`

Achtung: Links, die Sie in der Oberfläche anklicken, öffnet Ihr normaler
Browser — nicht über Tor. IndraNet warnt davor; besser die Adresse im Tor
Browser öffnen.

---

## Recherche-Netzwerke

- **Gründen** → **Einladen**: Der Einladungscode (`INDRA1-…`) gilt einmal und
  48 Stunden. Über einen sicheren Kanal weitergeben (Signal, persönlich).
- **Beitreten**: Code einfügen. IndraNet meldet sich über Tor bei der
  einladenden Person.
- **Freigeben**: Im Bestand Fakten anhaken → „Im Netzwerk freigeben". Geteilt
  werden nur Fakten mit **öffentlichen** Belegen, mit Quelladresse, Zitat und
  Ihrer Signatur. Hochgeladene interne Dateien und Notizen verlassen das
  Projekt nicht.
- **Empfangen**: Freigaben der anderen erscheinen im Netzwerk; gelb markiert,
  wenn sie Entitäten aus Ihrem Bestand berühren. „In den Prüfkorb" — dort
  wird die Originalquelle selbst abgerufen, bevor etwas in Ihren Bestand geht.

Technik: Jede Installation ist als `.onion`-Adresse erreichbar. Mitgliedschaften
sind vom Einladenden signiert (Ed25519), Freigaben vom Autor; veränderte
Freigaben fallen bei der Prüfung durch. Abgleich alle drei Minuten, Antworten
mit dem Netzwerkschlüssel verschlüsselt (AES-256-GCM). Wer offline ist,
bekommt Freigaben über die anderen nachgereicht.

---

## Sicherheit und Grenzen

- Die Oberfläche bindet nur an `127.0.0.1`, prüft den Host-Kopf (gegen
  DNS-Rebinding) und verlangt eine Sitzungsmarke je Programmstart. Sie lädt
  nichts von außen nach — auch die Weltkarte ist mitgeliefert (Natural Earth),
  es gehen keine Kachelanfragen hinaus.
- Projekte: scrypt + AES-256-GCM, Klartext nur im Arbeitsspeicher.
- Abgelegte Webseiten werden in einer Sandbox ohne Skripte angezeigt.
- Nicht geschützt: der Arbeitsspeicher im laufenden Betrieb; ein Rechner,
  auf dem Schadsoftware läuft; was Anthropic bei Claude-Anfragen sieht.
- GDELT drosselt Abfragen je IP stark; bei Tor-Ausgängen verlangen manche
  Suchmaschinen eine Bestätigung. IndraNet meldet das unter „Quellen".

## Verantwortung

IndraNet verarbeitet öffentlich zugängliche Daten — auch über Menschen. Für
Journalistinnen gilt das Medienprivileg (Art. 85 DSGVO), für alle der
Pressekodex: Unschuldsvermutung, Verdachtsberichterstattung nur mit
Mindestbestand an Beweistatsachen, Schutz Unbeteiligter. Die KI ist
angewiesen, Vorwürfe als Vorwürfe zu kennzeichnen, Namensgleichheiten
offenzulegen und keine Gesundheits-, Religions- oder Privatadressdaten von
Privatpersonen zu erfassen. Ein Treffer in einem Leak oder Register ist kein
Beleg für eine Straftat.

Auch wenn die Daten öffentlich sind, gilt: Dass Sie recherchieren, und wen,
ist schützenswert — für Ihre Sicherheit und die Ihrer Kolleginnen. Dafür sind
Tor, die verschlüsselten Projekte und die signierten Netzwerke da.

---

## Module (neu in Version 2)

| Datei | Aufgabe |
|---|---|
| `indranet.py` | Startprogramm |
| `server.py` | Oberfläche und JSON-Schnittstelle |
| `projekt.py` | Projekte, Prüfkorb, Netz, Karte, Steckbriefe, Lagebilder |
| `ki.py` | Claude/Ollama: Recherche, Dateianalyse, Lagebild, Vorschläge |
| `bruecke.py` | Brücke zu claude.ai: Aufträge zum Kopieren, Antworten einlesen |
| `quellen_offen.py` | GLEIF, Offshore Leaks, Wikidata, Wikipedia, GDELT, Websuche |
| `auftraege.py` | Hintergrundaufträge und Abläufe |
| `netzwerk.py` | Recherche-Netzwerke: Einladung, Signatur, Abgleich |
| `netz.py` | Netzweg: direkt, Tor, Proxy — ohne stillen Rückfall |
| `tor.py` | eigener Tor-Prozess mit Onion-Dienst |
| `geo.py` | Ortstabelle (Staaten, Offshore-Rechtsordnungen), Geokodierung |
| `einstellungen.py` | Einstellungen, API-Schlüssel per DPAPI |
| `beispiel.py` | fiktive Beispielbefunde |
| `web/` | Oberfläche (HTML, CSS, JS; d3, topojson, Natural Earth) |

Tests: `python test_v2.py` (62 Prüfungen der neuen Teile, inklusive zweier
Installationen, die sich vernetzen) und `python test_indranet.py` (243
Prüfungen des Kerns aus Version 1).

Windows-Version bauen: `build_windows.bat`, danach `installer.iss` mit Inno
Setup. Siehe `BUILD.md`.
