# IndraNet — Windows-Version bauen

Diese Anleitung richtet sich an die Person, die das Installationsprogramm
erzeugt. **Nutzer brauchen sie nicht** — für die genügt die fertige
`IndraNet-Setup-1.1.exe`.

---

## Warum das auf einem Windows-Rechner passieren muss

PyInstaller bündelt den Python-Interpreter und alle Bibliotheken **des
Systems, auf dem gebaut wird**. Eine Windows-`.exe` lässt sich unter Linux
nicht zuverlässig erzeugen: `cryptography` enthält kompilierte
Rust-Erweiterungen, die für die Zielplattform vorliegen müssen.

Der Bau ist deshalb ein Befehl auf einem Windows-Rechner. Ein
Gelegenheitsrechner reicht; es muss kein Entwicklungssystem sein.

---

## Schritt 1 — Python installieren

Von <https://www.python.org/downloads/> die aktuelle Version für Windows
holen (3.11 oder neuer).

**Wichtig:** Im Installationsfenster unten **„Add python.exe to PATH"**
ankreuzen. Ohne das findet das Bauskript Python nicht.

---

## Schritt 2 — Bibliotheken installieren (einmalig)

Eingabeaufforderung im Projektordner öffnen — im Explorer in die Adresszeile
`cmd` eintippen und Enter drücken — dann:

```
python -m pip install cryptography numpy pyinstaller
```

---

## Schritt 3 — Bauen

Entweder per Doppelklick auf `build_windows.bat`, oder direkt:

```
python -m PyInstaller IndraNet.spec --noconfirm --clean
```

Dauer: ein bis drei Minuten. Ergebnis: `dist\IndraNet\IndraNet.exe`

Zum Prüfen doppelklicken — der Einrichtungsassistent sollte sich im Browser
öffnen. Zusätzlich empfehlenswert:

```
python test_indranet.py
```

### Warum das Skript nichts installiert

Ein Skript, das Programmcode aus dem Internet nachlädt, Verzeichnisse
löscht und am Ende eine `.exe` erzeugt, entspricht Schritt für Schritt dem
Verhaltensmuster eines Schadprogramm-Laders. Virenscanner mit
Verhaltenserkennung schlagen darauf an — **Avast meldet `IDP.Generic` und
verschiebt die Datei in Quarantäne, bevor sie überhaupt läuft.** Das ist
ein Fehlalarm, aber ein nachvollziehbarer: Den Kontext kann der Scanner
nicht kennen.

Deshalb installiert das Skript nicht selbst, sondern prüft nur und weist
an. Wenn Sie die Befehle von Hand eingeben, gibt es kein Muster, das eine
Heuristik greifen könnte.

Falls Ihr Scanner die `.bat` trotzdem beanstandet: Sie ist reiner Text.
Rechtsklick → „Bearbeiten" zeigt jede Zeile. Alternativ die drei Befehle
oben direkt eingeben und die Datei ignorieren.

---

## Schritt 3 — Installationsprogramm erzeugen

1. **Inno Setup 6** installieren: <https://jrsoftware.org/isdl.php>
2. `installer.iss` mit Inno Setup öffnen
3. Auf **Compile** klicken

Ergebnis: `Ausgabe\IndraNet-Setup-1.1.exe` — eine einzelne Datei, die Sie
weitergeben können.

Das Installationsprogramm braucht **keine Administratorrechte**. Das ist
Absicht: Redaktionsrechner sind oft verwaltet, und ein Werkzeug für
Quellenmaterial sollte nicht zwingend durch die IT-Abteilung laufen müssen.

---

## Virenscanner — das ernsteste Verteilungsproblem

Mit PyInstaller gebaute Programme lösen bei Avast, Windows Defender und
anderen regelmäßig Fehlalarme aus. Bei unsignierten Programmen ist das die
Regel, nicht die Ausnahme.

**Für IndraNet ist das kein Schönheitsfehler.** Stellen Sie sich die Szene
vor: Eine Rechercheurin installiert das Werkzeug, ihr Virenscanner meldet
eine Bedrohung, und damit soll sie Whistleblower-Material verwalten. Diese
Installation findet nicht statt — und die Redaktion erzählt es weiter.

Drei Maßnahmen, in dieser Reihenfolge:

**1. Code-Signing-Zertifikat.** Die einzige wirksame Abhilfe. Ein
OV-Zertifikat kostet 200 bis 400 Euro im Jahr und behebt den Großteil der
Fälle; ein EV-Zertifikat baut zusätzlich sofort Reputation bei Microsoft
SmartScreen auf, ist aber teurer und an ein Hardware-Token gebunden.

**2. Fehlalarme melden.** Beide großen Anbieter haben Formulare:
Microsoft über das Security Intelligence Portal, Avast über
`https://www.avast.com/false-positive-file-form.php`. Nach der Meldung
dauert es typischerweise ein bis drei Tage.

**3. Reputation aufbauen.** SmartScreen bewertet eine Datei auch danach,
wie oft sie heruntergeladen und ohne Zwischenfall ausgeführt wurde. Eine
stabile Download-Adresse und unveränderte Dateien zwischen Versionen
helfen; jede Neusignierung setzt den Zähler teilweise zurück.

Als Zwischenlösung für einen Pilotbetrieb: Prüfsumme der
`IndraNet-Setup-1.1.exe` veröffentlichen (`certutil -hashfile datei SHA256`)
und der Pilotredaktion vorab mitteilen, dass die Warnung kommt und warum.
Ein angekündigter Fehlalarm ist deutlich weniger schädlich als ein
überraschender. Ein OV-Zertifikat kostet etwa 200 bis
400 Euro im Jahr; ein EV-Zertifikat baut zusätzlich sofort Reputation bei
Microsoft SmartScreen auf. Ohne Signatur zeigt Windows beim ersten Start
eine Warnung, die Nutzer wegklicken müssen — bei einem Werkzeug, das
Vertrauen verlangt, ist das ein schlechter erster Eindruck.

Signieren nach dem Bau:

```
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 ^
  /f zertifikat.pfx /p KENNWORT dist\IndraNet\IndraNet.exe
```

Und ebenso die fertige `IndraNet-Setup-1.1.exe`.

---

## Was in der gepackten Anwendung anders ist

**Der Navigator-Unterprozess.** In der Anwendung gibt es kein `python`, das
ein Skript starten könnte. Deshalb startet der Pod die eigene Programmdatei
erneut mit `INDRANET_ROLE=navigator`; `indranet_app.py` fängt das ganz oben
ab. Die Prozessgrenze der Firewall bleibt damit auch gepackt eine echte —
der Navigator-Prozess lädt nachweislich nur `firewall`, `json` und
`navigator`, keinen Speicher und keine Faktendaten.

**Ordner statt Einzeldatei.** `--onefile` entpackt sich bei jedem Start nach
`%TEMP%` und lässt den Programmcode dort bei einem Absturz liegen. Für ein
Werkzeug, das mit Quellenmaterial arbeitet, ist der Ordnermodus die richtige
Voreinstellung — und er startet schneller.

**Das Konsolenfenster bleibt.** Es ist die Bedienoberfläche des Servers: Es
zeigt, dass IndraNet läuft und unter welcher Adresse, und sein Schließen
beendet die Anwendung sauber mit Sicherung des Behälters. Ohne Fenster liefe
der Prozess unsichtbar weiter.

---

## Größe

Etwa 35 MB entpackt, rund 15 MB als Installationsprogramm. Der größte
Posten ist `cryptography` mit seinen Rust-Erweiterungen — er ist nicht
verzichtbar, daran hängt die gesamte Verschlüsselung.

Wer die externen Anschlüsse (OpenSanctions, Ereignisquellen) nicht braucht,
kann in `IndraNet.spec` bei `excludes` zusätzlich `"numpy"` eintragen; das
spart etwa 15 MB, deaktiviert aber `connect_*`.

---

## Bekannte Plattformunterschiede

**Zeichenkodierung unter Windows.** Ein Unterprozess verwendet dort
standardmäßig die Konsolen-Codepage (meist cp1252), nicht UTF-8. Da die
Firewall JSON mit deutschen Umlauten in beide Richtungen führt, kam die
Frage beim Navigator verstümmelt an — der Parser fand sein Muster nicht und
meldete korrekt `UNKNOWN_PREDICATE`. Unter Linux fällt das nicht auf, weil
dort UTF-8 Vorgabe ist.

Behoben an beiden Enden: Der Pod setzt `PYTHONIOENCODING=utf-8` für den
Unterprozess, und `navigator_worker.py` stellt seine Kanäle zusätzlich
selbst um — die Umgebungsvariable wirkt in der gepackten Anwendung nicht
immer. Ein Test sichert das ab („Umlaute passieren die Prozessgrenze
unversehrt").

---

## macOS und Linux

Dieselbe Beschreibung funktioniert dort:

```
python3 -m PyInstaller IndraNet.spec --noconfirm
```

Für macOS gilt zusätzlich die Notarisierung durch Apple, sonst verweigert
Gatekeeper den Start. Für Linux ist eine `.tar.gz` des `dist/IndraNet`-
Ordners meist ausreichend.
