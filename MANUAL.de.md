# IndraNet — Handbuch

Version 1.0 · Für Redakteurinnen, Rechercheure und Redaktionstechnik

---

## Was dieses Werkzeug tut

IndraNet verwaltet, was Ihre Recherche **behauptet**, und woher jede
Behauptung stammt. Es beantwortet Fragen an Ihren Bestand, zeigt daneben die
Belege, führt Buch darüber, was mehrfach belegt und was umstritten ist, und
erlaubt den Abgleich mit anderen Redaktionen, ohne dass die erfahren, woran
Sie arbeiten.

Es ist kein Suchwerkzeug für Dokumente. Es verwaltet die Aussagen, die Sie
aus Dokumenten gewonnen haben. Die Dokumente selbst bleiben in Ihrem
verschlüsselten Dateisystem; IndraNet hält Verweis und Prüfsumme.

---

## 1. Einrichtung

Voraussetzung ist Python 3.11 oder neuer.

```bash
pip install cryptography numpy
cd indranet
python3 test_indranet.py     # 62 Tests, sollten alle grün sein
python3 demo.py              # Vorführung des Ablaufs
```

Oberfläche starten:

```bash
python3 cli.py serve ./meine-recherche.db --open
```

Der Server bindet **nur an 127.0.0.1**. Das ist Absicht: Ein Werkzeug, das
mit Quellenmaterial arbeitet, gehört nicht ins Netz, solange das nicht
jemand ausdrücklich entscheidet. Wollen Sie es im Redaktionsnetz betreiben,
setzen Sie `--host` — und sichern Sie den Zugang selbst ab.

---

## 2. Die sechs Ansichten

### Fragen

Links die Antwort, rechts die Belege. Das ist keine Layoutlaune: Antwort und
Beleg kommen aus zwei getrennten Wegen durch das System, und Sie sollen
beides gleichzeitig sehen.

Verstandene Frageformen (Beispiele):

| Frage | Findet |
|---|---|
| Wem gehört *X*? | wirtschaftlich Berechtigte |
| Wer ist Direktor von *X*? | Direktoren |
| Wer hält Anteile an *X*? | Anteilseigner |
| Was ist in *X* registriert? | dort registrierte Gesellschaften |
| Wer betreibt *X*? | Betreiber eines Schiffs |

Erkennt der Parser kein Prädikat, sagt er das — und stellt **keine** Abfrage.
Eine geratene Frage liefert eine korrekt abgerufene, aber falsche Antwort;
das ist der gefährlichere Fehler.

Klicken Sie auf einen Fakt, um rechts seine Belege zu laden.

### Prüfen

Vier Arbeitslisten. Diese Ansicht ist der eigentliche Arbeitsplatz vor einer
Veröffentlichung:

- **Umstritten** — zwei Quellen sagen Unvereinbares. Vor der
  Veröffentlichung zu klären.
- **Einfach belegt** — hängt an einer Quelle. Nachlegen.
- **Widerrufen** — die Grundlage wurde zurückgezogen.
- **Bestätigt** — mindestens zwei unabhängige Quellen.

Oben steht der Anteil bestätigter Fakten. Das ist die ehrlichste Kennzahl
über den Stand einer Recherche.

### Entitäten

Verschmelzungsvorschläge. „Mueller Handels GmbH" und „Müller Handels GmbH"
sind wahrscheinlich dieselbe Firma — aber **wahrscheinlich** reicht nicht.
IndraNet verschmilzt nichts von selbst.

Jede Entscheidung braucht eine Begründung. Die steht später im Protokoll,
und wenn jemand die Recherche prüft, ist genau das die Stelle, an der Sie
gefragt werden.

Achten Sie auf die rote Warnung bei abweichender Rechtsform: „Nordkap
Shipping AS" ist norwegisch, „AB" schwedisch. Zwei Gesellschaften.

### Netz

Verbindungen zwischen zwei Entitäten. Unter jedem Pfad steht das
**schwächste Glied** — ein Pfad über eine einfach belegte Kante ist nur so
belastbar wie diese Kante.

### Quellen

Alle Dokumente mit ihrer Schutzstufe und der Zahl der daraus abgeleiteten
Aussagen. Vor jedem Widerruf sehen Sie hier, wie viele Fakten betroffen sind
und wie viele **ersatzlos** wegfallen, also keine zweite Quelle haben.

Ein Widerruf ist nicht rückgängig zu machen und verlangt eine Begründung.

### Import

CSV-Inhalt einfügen, Zuordnung angeben, Schutzstufe wählen. Jede Zeile wird
zu einer Aussage mit Fundstelle. Fakten ohne Beleg entstehen hier nicht.

---

## 3. Daten übernehmen

### Zuordnung

Eine Zeile je Regel, Form `subjekt:prädikat:objekt`:

```
eigentuemer:beneficial_owner_of:firma
direktor:director_of:firma
firma:registered_in:sitz
```

Spalten dürfen zusammengesetzt sein:

```
eigentuemer:beneficial_owner_of:{firma} {rechtsform}
```

Das ist fast immer nötig. Register führen Firma und Rechtsform getrennt;
ohne Zusammenführung entstehen „Mare Liberum" und „Mare Liberum Ltd." als
zwei Entitäten.

### Prädikate

| Prädikat | Bedeutung | Ein Wert je Subjekt? |
|---|---|---|
| `beneficial_owner_of` | ist wirtschaftlich berechtigt an | nein |
| `registered_in` | ist registriert in | **ja** |
| `holds_shares_in` | hält Anteile an | nein |
| `director_of` | ist Direktor von | nein |
| `listed_in` | ist geführt in | nein |
| `operates_vessel` | betreibt | nein |

Die letzte Spalte entscheidet, wann ein Widerspruch gemeldet wird. Eine
Gesellschaft hat mehrere Direktoren — das ist eine Aufzählung. Sie hat einen
Sitz — zwei Angaben sind ein Widerspruch.

### Über die Kommandozeile

```bash
python3 cli.py import ./recherche.db register.csv \
  --map 'eigentuemer:beneficial_owner_of:{firma} {rechtsform}' \
  --map '{firma} {rechtsform}:registered_in:sitz' \
  --titel "Handelsregister Q3" \
  --quelle "Register Oslo" \
  --stufe OEFFENTLICH \
  --von s.kern@redaktion
```

**`--quelle` ist wichtiger als `--titel`.** Über dieses Feld entscheidet
IndraNet, ob zwei Belege unabhängig sind. Zwei Auszüge aus demselben
Register sollten dieselbe Quelle tragen, sonst zeigt das Werkzeug eine
Bestätigung an, die keine ist.

---

## 4. Beleglage lesen

| Marke | Bedeutung | Was zu tun ist |
|---|---|---|
| **Bestätigt** | zwei oder mehr unabhängige Quellen | tragfähig |
| **Einfach belegt** | eine Quelle | vor Veröffentlichung nachlegen |
| **Umstritten** | Quellen widersprechen sich | klären |
| **Widerrufen** | Grundlage zurückgezogen | nicht verwenden |

Die Strichliste neben der Marke zählt unabhängige Quellen — eine Kerbe je
Quelle, wie im Notizbuch.

---

## 5. Schutzstufen und Rollen

| Stufe | Wofür | Beleg sichtbar ab Rolle |
|---|---|---|
| `OEFFENTLICH` | Register, Bilanzen, Gerichtsakten | Gast |
| `INTERN` | eigene Vorrecherche | Journalist |
| `VERTRAULICH` | Hintergrundgespräch, Quelle bekannt | Leitung |
| `WHISTLEBLOWER` | Leak, Insider, anonyme Übergabe | Admin |

Ein Fakt ist immer so schutzbedürftig wie sein schutzbedürftigster Beleg —
auch wenn dieselbe Tatsache anderswo öffentlich steht.

**Zurückgehaltene Belege erscheinen als schwarzer Balken.** Er verschwindet
nicht. Sie sehen, dass es einen weiteren Beleg gibt und auf welcher Stufe;
auf Klick den Grund, nie den Inhalt. Wer die Existenz verbirgt, erzeugt ein
falsches Bild der Beleglage.

Whistleblower-Material verlässt den Pod nie automatisch. Eine Freigabe in
einen gemeinsamen Raum braucht die Rolle Admin **und** zwei Personen.

---

## 6. Ein Dokument widerrufen

Stellt sich eine Quelle als unbrauchbar heraus — gefälscht, zurückgezogen,
falsch zugeordnet:

1. **Quellen** öffnen.
2. Beim Dokument steht, wie viele Fakten betroffen sind und wie viele
   ersatzlos wegfallen.
3. Begründung eintragen, widerrufen.

Danach sind alle daraus abgeleiteten Aussagen ungültig. Fakten, die nur auf
diesem Dokument beruhten, stehen auf **Widerrufen**. Kanten, die nur darüber
liefen, verschwinden aus allen Pfaden — eine Verbindung, die nur über eine
zurückgezogene Quelle bestand, ist keine Verbindung.

---

## 7. Zusammenarbeit mit anderen Redaktionen

### Signal

Sie fragen, ob eine andere Redaktion zu einer Entität etwas hat. Über die
Leitung geht **nicht der Name**, sondern ein geblendeter Kurvenpunkt. Die
Gegenstelle antwortet, ohne zu erfahren, wonach Sie gefragt haben.

Die Antwort nennt eine Klasse — `open`, `editorial`, `confidential`,
`whistleblower_high` — und ob Gesprächsbereitschaft besteht. Keinen Namen,
keinen Fakt, kein Dokument.

**Was die Gegenstelle doch erfährt:** dass Sie gefragt haben, und wie oft.
Das ist der Preis der Ratenbegrenzung, die verhindert, dass jemand
Namenslisten durchprobiert.

### Lichtung

Sind sich beide Seiten einig, öffnen sie einen flüchtigen gemeinsamen Raum.
Es wandert nicht das Dokument, sondern die Aussage mit Beleglage und
Prüfsumme. Nach Abschluss wird der Raum vernichtet; es bleibt eine
beidseitig signierte Beweiskette.

---

## 8. Kommandozeile

```bash
python3 cli.py serve    ./db --open           # Oberfläche
python3 cli.py import   ./db datei.csv --map … --titel … --quelle … --von …
python3 cli.py ask      ./db "Wem gehört X?"
python3 cli.py verify   ./db                  # Prüflisten
python3 cli.py evidence ./db <fact_id> --rolle ADMIN
python3 cli.py path     ./db "A" "B"
python3 cli.py review   ./db                  # Verschmelzungsvorschläge
python3 cli.py stats    ./db
python3 cli.py demo
```

Mit `--lang en` sind alle Ausgaben englisch.

---

## 9. Sicherheitshinweise

**Der Behälter ist verschlüsselt, der Arbeitsspeicher nicht.** Während der
Pod offen ist, steht der Klartext im RAM. IndraNet schützt vor einem neugierigen
Sprachmodell und vor der Föderation — nicht vor jemandem, der Ihr Notebook
mitnimmt.

**Der Navigator muss lokal laufen.** Ihre Frage verrät das Rechercheziel und
geht zwangsläufig auf die nicht vertrauenswürdige Seite. Ein Cloud-Modell an
dieser Stelle hebt den gesamten Quellenschutz auf, egal wie sauber alles
darunter ist.

**Nichts wird nachgeladen.** Die Oberfläche verwendet keine externen
Schriften, Skripte oder Bilder. Wenn Sie beim Öffnen Netzverkehr sehen,
stimmt etwas nicht.

**Ein Widerruf ist endgültig.** Es gibt keine Rücknahme.

**Prüfen Sie vor dem ersten Abgleich den Resolver-Fingerabdruck.** Weicht er
zwischen zwei Pods ab, lehnt IndraNet die Verbindung ab. Das ist richtig so:
Unterschiedliche Normalisierung führt zu stillen Fehltreffern, die niemand
bemerkt.

---

## 10. Wenn etwas nicht funktioniert

**„Kein Prädikat erkannt"** — Der Parser versteht die Frageform nicht.
Formulieren Sie näher an den Beispielen in Abschnitt 2, oder fragen Sie über
die Ansicht **Netz**.

**Antwort ist `NO_MATCH`, obwohl der Fakt drinsteht** — Fast immer eine
Schreibweise. Sehen Sie unter **Entitäten** nach, ob ein
Verschmelzungsvorschlag offen ist.

**Zwei Belege, aber „Einfach belegt"** — Beide tragen dieselbe `--quelle`.
Unabhängigkeit entscheidet sich an diesem Feld, nicht am Titel.

**Ein Fakt ist plötzlich „Umstritten"** — Eine zweite Quelle nennt bei einem
Prädikat mit einem Wert je Subjekt etwas anderes. Sehen Sie sich beide
Belege an; genau dafür ist die Marke da.
---

## 11. Externe Quellen

Die Ansicht **Extern** prüft Ihren Bestand gegen öffentliche Datenbestände —
Sanktionslisten, politisch exponierte Personen, Nachrichtenströme.

### Der Abgleich läuft auf Ihrem Gerät

Das ist der wichtigste Punkt. IndraNet lädt den fremden Bestand herunter und
vergleicht lokal. **Ihre Namensliste verlässt den Pod nicht.** Wer stattdessen
einzelne Namen an einen Screening-Dienst schickt, verrät dabei das
Rechercheziel — und zwar an genau der Stelle, an der es am billigsten zu
verlieren ist.

### Korpus holen

```bash
# Sanktionen und PEPs (OpenSanctions, Massendaten, ohne Schlüssel)
python3 cli.py fetch ./recherche.db opensanctions

# Nachrichten- oder Ereignisstrom
python3 cli.py fetch ./recherche.db events --von <URL-oder-Datei> \
  --name "World Monitor" --profil worldmonitor
```

Beim ersten Mal dauert der OpenSanctions-Abruf einige Minuten; der Bestand
umfasst mehrere hunderttausend Entitäten. Ein Abruf pro Tag genügt.

### Prüfen

```bash
python3 cli.py screen ./recherche.db opensanctions --von <datei>
```

Ausgabe:

```
Anders Holm  ←  Anders Holm  [OpenSanctions] politisch exponiert  (1.00)
Nordkap Shipping AS  ←  Nordkap Shipping AS  [OpenSanctions] sanktioniert  (1.00)
```

### Zustand der Quellen

```bash
python3 cli.py sources ./recherche.db
```

| Zustand | Bedeutung |
|---|---|
| `OK` | jünger als eine Woche |
| `ALT` | älter als eine Woche |
| `VERALTET` | älter als einen Monat — vor Veröffentlichung neu holen |
| `FEHLER` | letzter Abruf gescheitert, Grund steht dabei |
| `NIE` | noch nie erfolgreich abgerufen |

Eine Recherche auf einem `VERALTET`-Bestand ist nicht falsch, aber Sie
sollten es wissen, bevor jemand anders es merkt.

### Funde sind keine Fakten

Ein Sanktionstreffer erscheint in der Liste. Er wird **nicht** automatisch
zu einer Aussage in Ihrem Bestand. Die Übernahme ist ein eigener Schritt und
braucht Ihre Entscheidung — sonst holen Sie sich fremde Fehler als eigene
Fakten ins Haus, und Ihre Belegkette zeigt auf eine Liste statt auf ein
Dokument.

### Lizenz

OpenSanctions-Daten stehen unter CC-BY-NC: frei für redaktionelle Nutzung,
Namensnennung erforderlich, kommerzielle Nutzung lizenzpflichtig. Bei
Ereignisquellen prüfen Sie die Bedingungen des jeweiligen Betreibers.
---

## 12. Pod anlegen, Konten, Passphrase

### Anlegen

```bash
python3 cli.py init ./recherche.vault --benutzer s.kern --anzeige "Sabine Kern"
```

Sie werden nach einer Passphrase gefragt (mindestens zwölf Zeichen) und
nach einem Passwort für das erste Konto. Das erste Konto ist immer ADMIN.

**Es gibt keine Wiederherstellung.** Ohne Passphrase ist der Pod nicht
lesbar — das ist der Sinn der Sache. Notieren Sie sie an einem Ort, der
nicht neben dem Rechner liegt.

Für Zwei-Faktor zusätzlich eine Schlüsseldatei:

```bash
python3 cli.py init ./recherche.vault --benutzer s.kern \
  --neue-schluesseldatei /media/stick/indranet.key
```

Danach braucht jeder Zugriff `--schluesseldatei /media/stick/indranet.key`.
Bewahren Sie den Stick getrennt vom Rechner auf, sonst ist die Trennung
sinnlos.

### Konten

```bash
python3 cli.py user ./recherche.vault list
python3 cli.py user ./recherche.vault add --benutzer j.weber --rolle JOURNALIST
python3 cli.py user ./recherche.vault role --benutzer j.weber --rolle LEITUNG
python3 cli.py user ./recherche.vault passwd --benutzer j.weber
```

Nur ADMIN darf Konten anlegen und Rollen ändern. Der letzte ADMIN kann sich
nicht selbst herabstufen — sonst wäre der Pod unbedienbar.

### Passphrase wechseln

```bash
python3 cli.py vault ./recherche.vault passwd
python3 cli.py vault ./recherche.vault info      # ohne Passphrase
```

**Ältere Kopien des Behälters bleiben mit der alten Passphrase lesbar.**
Ein Wechsel schützt nur den aktuellen Stand; vernichten Sie alte
Sicherungen.

### Anmeldung in der Oberfläche

Nach `serve` erscheint eine Anmeldemaske. Die Rolle bestimmt, welche Belege
Sie sehen — sie ist kein Auswahlfeld mehr, sondern kommt aus Ihrer Sitzung.
Eine Sitzung läuft nach acht Stunden ab.

Nach fünf Fehlversuchen ist das Konto fünf Minuten gesperrt. Alle Versuche
werden protokolliert; wiederholte Fehlversuche sind das erste Zeichen für
einen Zugriffsversuch.

### Ein Pod ohne Konten

Legen Sie kein Konto an, läuft der Pod als Einzelplatz mit vollen Rechten.
Das ist beabsichtigt: Wer die Datei und die Passphrase besitzt, besitzt den
Pod ohnehin. Sobald das erste Konto besteht, gilt Anmeldepflicht für alle.

Umgekehrt heißt das: **Die Kontenschicht schützt nicht vor jemandem, der
den Behälter und die Passphrase hat.** Sie regelt die Zusammenarbeit
mehrerer Personen. Für getrennte Vertrauensbereiche brauchen Sie getrennte
Pods.
---

## 13. Fakten von Hand erfassen

Die meisten Fakten entstehen nicht aus Tabellen, sondern beim Lesen eines
Dokuments oder nach einem Gespräch. Dafür ist der Reiter **Erfassen**.

Der Ablauf ist immer derselbe: **zuerst der Beleg, dann die Aussage.** Ohne
Beleg entsteht kein Fakt — hier genauso wie beim Import.

### Beleg anlegen

Rechts, drei Arten:

**Datei** — für PDFs, Tabellen, Scans. Sie wählen die Datei aus, und der
Browser berechnet ihre Prüfsumme. **Die Datei wird nicht hochgeladen** —
sie verlässt Ihren Rechner nicht einmal in Richtung des eigenen Servers.
Der Pod speichert Dateinamen, Prüfsumme und den Ablageort, den Sie angeben.

Warum nur die Prüfsumme? Ein Leak mit Millionen Dateien gehört in Ihr
verschlüsseltes Dateisystem, nicht in den Faktenspeicher. Die Prüfsumme
genügt, um später zu beweisen, dass ein vorgelegtes Dokument dasselbe ist,
auf das sich die Recherche gestützt hat.

Tragen Sie unter **Ablageort** ein, wo die Datei liegt — sonst finden Sie
sie in einem halben Jahr nicht wieder.

**Notiz** — für eigene Aufzeichnungen: Hintergrundgespräch, Beobachtung,
Telefonat. Der Notiztext selbst ist der Beleg und wird über seine
Prüfsumme festgehalten. Ändern Sie die Notiz später, ergibt sich eine
andere Kennung; die alte Belegkette zeigt dann ins Leere, statt still auf
einen veränderten Text zu verweisen.

**Sonstige** — alles ohne Datei: telefonische Registerauskunft, Webseite,
Behördenauskunft.

### Aussage erfassen

Links, sobald ein Beleg gewählt ist:

| Feld | Beispiel |
|---|---|
| Subjekt | `Politiker Lindqvist` |
| Beziehung | `ist wirtschaftlich berechtigt an` |
| Objekt | `Svensson Family Trust` |
| Fundstelle | `S. 14, Zeile 7` |
| Zitat | optional, die Belegstelle im Wortlaut |

**Die Fundstelle ist das Wichtigste.** „S. 14, Zeile 7" ist ein Beleg,
„irgendwo im PDF" ist keiner. Bei einer Nachfrage vor der Veröffentlichung
ist genau das die Angabe, nach der gefragt wird.

Nach dem Speichern bleibt der Beleg ausgewählt — Sie können mehrere
Aussagen aus demselben Dokument hintereinander erfassen. Unten stehen die
zuletzt erfassten mit ihrer Beleglage.

### Handerfassung und Import mischen sich

Ein von Hand erfasster Fakt und derselbe Fakt aus einem CSV-Import sind
derselbe Fakt — wenn die **Quelle** verschieden ist, gilt er als
mehrfach belegt. Sie können also eine Behauptung aus einem Leak erfassen
und später durch einen Registerimport bestätigen lassen.

### Was Sie nicht tun sollten

Vergeben Sie nicht für jede Aussage eine neue Quelle. Am Feld **Quelle**
entscheidet sich, ob zwei Belege als unabhängig gelten. Zwei Seiten aus
demselben Leak sind eine Quelle, nicht zwei.
---

## 14. Belegdokumente im Pod aufbewahren

Ein Verweis auf `D:\Akten\leak.pdf` ist kein Schutz, sondern eine Notiz.
Wer keinen verschlüsselten Redaktionsserver hat — und das sind die
meisten —, sollte die Belege **im Pod** ablegen.

### So geht es

Reiter **Erfassen**, Beleg-Art **Datei**. Der Haken **„Dokument im Pod
ablegen (verschlüsselt)"** ist standardmäßig gesetzt. Datei auswählen,
Titel und Quelle eintragen, **Beleg anlegen**.

Die Datei wird verschlüsselt in einen Ordner neben Ihrem Knoten gelegt:

    recherche.vault          der Knoten selbst
    recherche-belege\        die verschlüsselten Dokumente

Beide gehören zusammen. **Sichern Sie immer beide** — der Knoten allein
enthält die Dokumente nicht, der Belegordner allein ist ohne Knoten und
Passphrase nutzlos.

### Was verschlüsselt wird

Alles. Inhalt, Originalname und Dateityp. Die Dateinamen im Belegordner
sind undurchsichtige Zeichenketten. Wer den Ordner sieht, erfährt die
Anzahl der Dokumente und ihre ungefähre Größe — mehr nicht.

Der Schlüssel wird aus Ihrer Passphrase abgeleitet, ist aber **nicht**
derselbe wie der des Knotens. Zwei getrennte Schlüssel aus einer
Passphrase.

### Dokument wieder ansehen

Eine Frage stellen, den Fakt anklicken, rechts bei den Belegen auf
**Dokument öffnen**. Der Zugriff läuft über das Indra-Juwel: Wer den Beleg
nicht einsehen darf, bekommt auch die Datei nicht.

### Wann Sie stattdessen nur verweisen sollten

Haken entfernen. Sinnvoll bei:

- **Großen Beständen.** Ein Leak mit zehntausend Dateien gehört auf ein
  verschlüsseltes Laufwerk, nicht in den Belegordner.
- **Vorhandener Redaktionsinfrastruktur.** Wenn ein verschlüsselter Server
  existiert, sollen die Dokumente dort bleiben.
- **Dateien über 300 MB.** Der Weg über die Oberfläche ist dafür nicht
  gedacht.

Bei „nur Verweis" speichert IndraNet Prüfsumme und Ablageort. Die Prüfsumme
genügt, um später zu beweisen, dass ein vorgelegtes Dokument dasselbe ist —
aber die Datei müssen Sie selbst sicher aufbewahren.

### Sicherungskopien

Der Belegordner wächst mit der Zahl der Dokumente. Weil alles verschlüsselt
ist, können Sie ihn auf ein Netzlaufwerk oder in einen Cloudspeicher
sichern — ohne Passphrase ist er wertlos, auch für den Anbieter.

Ein Warnhinweis: Die Passphrase ist damit der einzige Schutz für Ihr
gesamtes Material. Verlieren Sie sie, ist alles verloren; gibt jemand sie
weiter, ist alles offen.
---

## 15. Fehler korrigieren

Vertippt, falsches Feld erwischt, Quelle zurückgezogen — das passiert. In
der Belegspalte steht bei jedem Beleg eine Zeile mit drei Möglichkeiten.

### Korrigieren

Für Tippfehler und falsch eingetragene Felder. Leere Felder bleiben
unverändert. Die alte Fassung geht ins Korrekturprotokoll.

### Widerrufen

Wenn sich eine **Behauptung als falsch herausstellt** oder eine Quelle
zurückgezogen wird. Die Aussage bleibt sichtbar und zählt als widerrufen.

Das ist wichtig: Wer eine falsche Behauptung spurlos entfernt, verfälscht
die Beleglage rückwirkend. Ein Fakt, der zeitweise als bestätigt galt und
dann zurückgenommen wurde, muss das zeigen.

Ein Fakt wird erst als widerrufen angezeigt, wenn **alle** ihn tragenden
Aussagen widerrufen sind. Solange eine unabhängige Quelle steht, steht der
Fakt.

### Verwerfen

Nur für Fehlgriffe: falscher Beleg gewählt, doppelt erfasst, Unsinn
eingetippt. Der Inhalt verschwindet vollständig.

Im Korrekturprotokoll bleibt stehen, **dass** gelöscht wurde, von wem und
warum. Ohne diese Spur wäre die Belegkette nachträglich frisierbar — und
genau das darf ein Werkzeug für Beweisführung nicht zulassen.

Jede der drei Aktionen verlangt eine Begründung.

---

## 16. Sichern

In der Statusleiste oben steht, wie lange die letzte Sicherung her ist. Ein
Klick auf **jetzt sichern** packt Knoten und Belegordner in eine datierte
Datei:

    recherche-sicherung-2026-08-28_1430.zip

Darin: der Behälter, alle Belegdokumente, ein Manifest mit Prüfsummen und
eine Anleitung zum Wiederherstellen.

**Der Inhalt ist verschlüsselt.** Die Datei darf auf ein Netzlaufwerk, eine
externe Platte oder in einen Cloudspeicher — ohne Passphrase ist sie
wertlos, auch für den Anbieter.

Über die Kommandozeile:

```bash
python3 cli.py backup ./recherche.vault
python3 cli.py backup ./recherche.vault --ziel E:\Sicherung\
```

IndraNet löscht keine alten Sicherungen. Ein Werkzeug, das
Recherchestände von sich aus entfernt, ist keins — aufräumen müssen Sie
selbst.

---

## 17. Beweiskette exportieren

In der Belegspalte auf **Kette exportieren**. Sie erhalten ein lesbares
Dokument mit:

- der Aussage und ihrer Beleglage
- allen unabhängigen Quellen
- je Beleg: Quelle, Fundstelle, Schutzstufe, Erfasser, SHA-256
- den Prüfvermerken
- einer Prüfsumme über die gesamte Kette

Das ist, was Sie dem Justiziar oder der Chefredaktion vorlegen.

**Der Export folgt Ihrer Rolle.** Als Journalist erscheinen
Whistleblower-Belege als *„Zurückgehaltener Beleg"* mit dem Hinweis, dass
es sie gibt. Als Admin stehen sie offen. Wählen Sie also bewusst, wem Sie
welchen Export geben.

**Dokumentinhalte sind nicht enthalten**, nur Prüfsummen. Wer die Kette
prüft, braucht die Originale — genau so soll es sein.

Mehrere Fakten in einem Dokument, über die Kommandozeile:

```bash
python3 cli.py export ./recherche.vault f:abc... f:def... --rolle ADMIN \
  --ziel dossier.md
```

Die Ausgabe ist Markdown. Zum Weitergeben als PDF öffnen Sie sie in einem
Editor wie Typora oder wandeln sie mit Pandoc um.
---

## 18. Welche Dateien IndraNet verarbeitet

**Ablegen kann IndraNet jede Datei** — verschlüsselt, unabhängig vom
Format. **Lesen** kann es die folgenden:

| Gruppe | Formate |
|---|---|
| Text | txt, md, log, rst, ini, yaml, srt, vtt |
| Tabellen | csv, tsv, **xlsx**, **ods** |
| Dokumente | **docx**, **odt**, rtf, html, xml, json |
| Präsentationen | **pptx**, **odp** |
| E-Mail | eml, mbox |
| PDF | pdf (mit Textebene) |

Alles außer PDF kommt ohne Zusatzsoftware aus — die modernen
Office-Formate sind ZIP-Archive mit XML darin.

### Was nicht gelesen wird

**Alte Binärformate** (.doc, .xls, .ppt vor Office 2007) und **Outlook
.msg**. Öffnen Sie sie einmal in LibreOffice und speichern Sie als .docx
oder .xlsx.

**Gescannte Seiten ohne Textebene.** Ein PDF aus dem Scanner enthält Bilder,
keinen Text. IndraNet meldet das beim Ablegen — es tut nicht so, als wäre
das Dokument leer. Für solche Fälle bräuchte es eine Texterkennung (OCR),
die derzeit nicht eingebaut ist.

In beiden Fällen wird die Datei **trotzdem verschlüsselt abgelegt** und
lässt sich öffnen. Nur durchsuchen können Sie sie nicht.

### Fundstellen statt Textklumpen

Das ist der eigentliche Punkt. Jeder gefundene Textabschnitt trägt seine
Position:

| Format | Fundstelle |
|---|---|
| PDF | `S. 14` |
| Tabelle | `Blatt "Beteiligungen", Zeile 42` |
| Word, ODT | `Absatz 17` |
| Präsentation | `Folie 8` |
| E-Mail | `Nachricht 3, Text` |
| JSON | `$.firma.eigentuemer` |

Wenn Sie im Beleg nach einem Namen suchen, bekommen Sie die Fundstelle mit
dem umgebenden Satz — und können beides mit einem Klick in die Erfassung
übernehmen. „S. 14, Zeile 7" ist ein Beleg; „irgendwo im PDF" ist keiner.

---

## 19. Netzansicht

Reiter **Netz**, Unterreiter **Netzansicht**. Entität eintragen, Tiefe
wählen, **Zeichnen**.

Das ist die digitale Pinnwand mit den roten Fäden. Die **Kantenfarbe zeigt
die Beleglage**: grün bestätigt, gelb einfach belegt, rot umstritten, grau
gestrichelt widerrufen.

Damit sehen Sie auf einen Blick, welche Teile Ihres Netzes tragen und
welche an einer einzigen Quelle hängen. Ein Knoten weiter draußen ist nur
so belastbar wie die Kanten dorthin.

Ein Klick auf einen Knoten macht ihn zum neuen Mittelpunkt — so arbeiten
Sie sich durch das Geflecht.

Der Graph wird ohne Fremdbibliothek gezeichnet und lädt nichts nach. Bei
mehr als etwa zweihundert Knoten wird die Darstellung unübersichtlich;
verringern Sie dann die Tiefe.

---

*IndraNet ist quelloffen. Die Architektur ist im Whitepaper beschrieben,
einschließlich dessen, was sie nicht leistet.*
