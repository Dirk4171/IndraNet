# IndraNet

**Ein föderiertes Recherchenetz für investigativen Journalismus**
Architektur-Whitepaper · Version 1.0 · Juli 2026

---

## Zusammenfassung

IndraNet erlaubt Redaktionen, verstreute Datenbestände auf verborgene
Verbindungen abzugleichen, ohne Rohdaten auszutauschen. Drei Eigenschaften
unterscheiden es von zentralen Analyseplattformen:

**Quellenschutz ist technisch erzwungen, nicht organisatorisch versprochen.**
Das Sprachmodell läuft in einem eigenen Prozess und erreicht den
Faktenspeicher über eine Schnittstelle mit geschlossenem Schema. Es kann
keine Fakten erfinden, weil es keine kennt — und was es formuliert, wird
gegen seine eigene Eingabe geprüft.

**Die Aussage ist das primäre Objekt, nicht der Fakt.** Ein Fakt ist
abgeleitet: das Bündel aller Aussagen, die dieselbe Behauptung tragen. Damit
lassen sich Dinge darstellen, die investigative Arbeit ausmachen und die
faktenzentrierte Systeme nicht abbilden können — widersprechende Quellen,
Mehrfachbelegung, und der Widerruf eines Dokuments samt allem, was daran
hing.

**Der föderierte Abgleich verrät das Rechercheziel nicht.** Über die Leitung
geht ein geblendeter Kurvenpunkt. Die Gegenstelle beantwortet die Anfrage,
ohne zu erfahren, wonach gefragt wurde.

---

## 1. Das Problem

Palantir Gotham und vergleichbare Plattformen bündeln Daten in zentralen
Data Lakes. Für Behörden mag das funktionieren; für investigativen
Journalismus ist es unbrauchbar. Whistleblower-Material, vertrauliche
Gesprächsprotokolle und redaktionelle Vorrecherchen dürfen nicht in einer
Infrastruktur zusammenfließen, über die eine einzige Instanz verfügt.

Gleichzeitig brauchen Redaktionen genau die Fähigkeit, die solche
Plattformen bieten: zu erkennen, dass ein Name in einem anderen Haus schon
einmal aufgetaucht ist. Diesen Widerspruch löst IndraNet.

## 2. Das Gegenbild

In der buddhistischen Kosmologie hängt über dem Palast des Gottes Indra ein
unendliches Netz. An jedem Knoten sitzt ein Juwel, das alle anderen
spiegelt — ihr Licht, nicht ihre Substanz. Es gibt kein Zentrum.

Jeder Pod ist ein Juwel: ein autonomer, lokaler Bestand. Jedes Signal ist
eine Spiegelung: die Bestätigung einer Verbindung ohne Preisgabe der Quelle.

## 3. Designprinzipien

1. **Daten bleiben beim Besitzer**, physisch und juristisch.
2. **Kein Sprachmodell erreicht Fakten.** Die Grenze ist ein Prozess, kein
   Diagramm.
3. **Keine Aussage ohne Beleg.** Fakten ohne Fundstelle entstehen gar nicht
   erst.
4. **Widerspruch ist ein Ergebnis, kein Fehler.**
5. **Mensch entscheidet, Maschine schlägt vor** — bei jeder Verschmelzung
   zweier Entitäten.
6. **Kein Nachladen.** Das Werkzeug arbeitet lokal und ohne externe
   Ressourcen.

## 4. Architektur

```
┌─────────────────────────────────────────────────────────┐
│                    Indra-Knoten (Pod)                    │
│                                                          │
│   Weboberfläche ──┬──────────────────┬── Kommandozeile   │
│                   │                  │                   │
│   ┌───────────────▼──────┐    ┌──────▼────────────────┐  │
│   │  Navigator (Prozess) │    │  Indra-Juwel (Policy) │  │
│   │  Parser + Vorlagen   │    │  Stufen, Freigaben    │  │
│   └───────────┬──────────┘    └──────┬────────────────┘  │
│               │ FIREWALL              │                   │
│   ┌───────────▼───────────────────────▼────────────────┐  │
│   │  Speicher: Aussagen über SQLite                    │  │
│   │  Verifikation · Entity Resolution · Graph          │  │
│   └────────────────────────┬───────────────────────────┘  │
│   ┌────────────────────────▼───────────────────────────┐  │
│   │  Föderation: Indra-Signal (PSI) · Axon (Transport) │  │
│   └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

Die beiden Ausgänge sind streng getrennt:

```
Frage ──► Navigator ──[Firewall]──► Speicher ──► Status + Antwort ──► Text
                                       │
                                    fact_id  (passiert die Firewall nicht)
                                       │
Oberfläche ─────[Indra-Juwel]──────────┴──► Beleg, Fundstelle, Prüfsumme
```

## 5. Das Aussage-Modell

Die zentrale Entwurfsentscheidung.

```
Aussage = Dokument D behauptet (Subjekt, Prädikat, Objekt),
          erfasst von Person P am Tag T, an Fundstelle F.
```

Ein **Fakt** ist daraus abgeleitet: das Bündel aller Aussagen mit gleichem
(Subjekt-Cluster, Prädikat, Objekt-Cluster). Seine **Beleglage** ergibt sich
aus den tragenden Aussagen:

| Beleglage | Bedingung |
|---|---|
| `BESTAETIGT` | zwei oder mehr unabhängige Quellen |
| `EINFACH_BELEGT` | genau eine Quelle |
| `UMSTRITTEN` | Prädikat erlaubt je Subjekt einen Wert, Quellen uneins |
| `WIDERRUFEN` | alle tragenden Aussagen zurückgezogen |

Unabhängigkeit wird über das Feld `quelle` des Dokuments bestimmt. Zwei
Auszüge desselben Registers zählen als eine Quelle.

### Warum diese Umkehrung

**Quellen widersprechen sich.** „Register Oslo sagt British Virgin Islands,
Orbis sagt Panama" ist der Normalfall. Ein faktenzentriertes System kann das
nicht darstellen — es meldet Mehrdeutigkeit und lässt offen, ob die Quellen
uneins sind oder der Speicher rauscht. IndraNet unterscheidet beides:
`registered_in` erlaubt je Gesellschaft einen Sitz, also ist das ein
Widerspruch. `director_of` erlaubt mehrere, also ist es eine Aufzählung.

**Dokumente werden widerrufen.** Stellt sich eine Übergabe als Fälschung
heraus, muss jede daraus abgeleitete Aussage ungültig werden — und vor dem
Widerruf beantwortbar sein, was ersatzlos wegfällt. Beides ist hier eine
Abfrage.

**Mehrfachbelegung ist die wichtigste Unterscheidung, die eine Redaktion
trifft.** Sie muss im Modell stehen, nicht im Kopf der Rechercheurin.

### Warum SQLite und nicht ein Vektorspeicher

Eine frühere Fassung dieser Architektur legte Fakten als überlagerte
Zufallsvektoren (Binary Spatter Codes, D=20.000) ab. Der Vergleich bei
40.000 Fakten:

| | Vektorspeicher | SQLite |
|---|---|---|
| Punktabfrage | 1,16 ms | 0,022 ms |
| Pfad über 6 Schritte | 6 ms | 0,1 ms |
| Plattenbedarf | 116 MB | 14 MB |

Dazu Kapazitätsgrenzen, ein zu kalibrierender Schwellwert und eine
Neuindizierung nach jeder Verschmelzung — alles Eigenschaften, die eine
gewöhnliche Tabelle nicht hat. Der oft genannte Vorteil, ein überlagerter
Vektor sei ohne die richtige Frage nicht aufzählbar, hält der
Implementierung nicht stand: Für schnelle Abfragen braucht jeder Shard eine
Kandidatenliste, und der Namensspeicher muss ohnehin Klartext halten.
Verschlüsselung at rest schützt besser und ist zehn Zeilen Code.

Der Determinismus, auf dem das Vertrauen ruht, kommt nicht aus der
Darstellung. Er kommt daher, dass am Abruf kein Sprachmodell beteiligt ist.

## 6. Die Firewall

Der Navigator läuft als eigener Prozess mit eigenem `__main__`. Der
Transport ist zeilenweises JSON über stdin/stdout — **kein Pickle**, weil
dessen Deserialisierung Codeausführung ist und eine kompromittierte
Navigatorseite damit die gesamte Grenze aushebeln könnte.

Das Schema ist in beide Richtungen geschlossen:

```
hinein   { v, req_id, predicate_id (aus geschlossenem Vokabular), object }
hinaus   { v, req_id, status, subject }
```

Alles andere wird abgewiesen — Arrays, Listen, bytes, verschachtelte dicts,
Zusatzfelder. Drei Regeln verdienen Erwähnung:

**Keine Ähnlichkeitswerte nach außen.** Numerische Scores sind ein
Seitenkanal; wer mit gewählten Objekten sondiert, zieht Rückschlüsse auf den
Bestand.

**Keine Beleglage nach außen.** Der Navigator formuliert die Antwort; ob sie
einfach oder mehrfach belegt ist, geht die Oberfläche an, nicht ihn.

**Kein Subjekt bei `NO_MATCH` oder `AMBIGUOUS`.** Ein „bester Kandidat" wäre
eine Behauptung, für die der Speicher nicht einsteht.

### Der Navigator braucht kein Feintuning

Eine frühere Fassung sah zwei LoRA-Adapter vor. Beide sind entbehrlich. Die
Formulierungsseite darf durch die Ableitbarkeitsprüfung ohnehin nur Wörter
aus ihrer Eingabe verwenden — eine Vorlage leistet dasselbe bei null Risiko.
Die Extraktionsseite ist semantisches Parsen in ein geschlossenes
Vokabular; das leistet ein lokales Modell mit Grammar-Constrained Decoding
ohne Training, und zwar strukturell garantiert statt antrainiert: Was die
Grammatik nicht zulässt, kann nicht ausgegeben werden.

### Ableitbarkeitsprüfung

Die Firewall verhindert, dass der Navigator Fakten **kennt**. Sie verhindert
nicht, dass er welche **erfindet**: Aus „Svensson Family Trust" macht ein
Sprachmodell jederzeit „der schwedische Svensson Family Trust, seit 2016".
Jeder Inhaltsbegriff der Antwort wird deshalb dagegen geprüft, ob er aus
Subjekt, Objekt, Prädikat-Label oder einem freigegebenen Lexikon ableitbar
ist. Ist er es nicht, greift die Vorlage, und der Vorfall geht ins Protokoll.

Das ist bewusst streng, und daraus folgt ein Satz, den man aussprechen
sollte: **Flüssigkeit und Nachprüfbarkeit stehen in direktem Widerspruch.**
Jede zusätzliche Formulierungsfreiheit öffnet die Halluzinationsfläche
wieder, die die Firewall schließen soll.

## 7. Der Belegpfad

Belege erreichen das Sprachmodell nie. Sie erreichen die Journalistin über
einen zweiten, vollständig auf der vertrauenswürdigen Seite verlaufenden
Weg, kontrolliert vom Indra-Juwel.

Zurückgehaltene Belege werden nicht verschwiegen, sondern geschwärzt: Die
Rechercheurin sieht, **dass** es einen weiteren Beleg gibt, und auf welcher
Schutzstufe — nicht, was darin steht. Wer die Existenz verbirgt, erzeugt ein
falsches Bild der Beleglage.

Die **Beweiskette** ist maschinenlesbar und enthält Prüfsummen, keine
Inhalte. Wer sie prüft, braucht die Originaldokumente. Genau so soll es sein.

## 8. Indra-Juwel: Schutzstufen und Rollen

| Stufe | Beispiel | Beleg sichtbar ab |
|---|---|---|
| `OEFFENTLICH` | Handelsregister, Bilanz, Gerichtsakte | `GAST` |
| `INTERN` | eigene Vorrecherche, unveröffentlicht | `JOURNALIST` |
| `VERTRAULICH` | Hintergrundgespräch, Quelle namentlich bekannt | `LEITUNG` |
| `WHISTLEBLOWER` | Leak, Insider, anonyme Übergabe | `ADMIN` |

Die vierte Stufe ist keine Steigerung der dritten, sondern eine andere
Kategorie: Bei ihr steht die körperliche Sicherheit eines Menschen im
Spiel. Sie verlässt den Pod unter keinen Umständen automatisch, und ihre
Freigabe in einen Kollaborationsraum braucht `ADMIN` **und** zwei Personen.

Jede Entscheidung des Juwels wird protokolliert, auch die verweigerten.

## 9. Entity Resolution

Zwei Schlüssel statt einem — weil ein einziger zu einer unmöglichen Wahl
zwingt:

**Strikter Schlüssel.** Konservativ, deterministisch, zustandslos.
Vereinheitlicht Unicode-Form, Groß-/Kleinschreibung, Leerraum,
Rechtsformschreibweise und Namensreihenfolge. Erzeugt den Cluster.

**Blockschlüssel.** Aggressiv: Diakritika, Digraphen, Rechtsform und
Reihenfolge werden eingeebnet. Erzeugt **niemals** einen Cluster, sondern
ausschließlich Kandidatenpaare für die menschliche Prüfung.

So kollidieren „Müller" und „Mueller" im Vorschlag, ohne dass „Goethe" und
„Gothe" stillschweigend eine Firma werden. Rechtsformen werden
**vereinheitlicht, nicht entfernt**: „Nordkap Shipping AS" (Norwegen) und
„Nordkap Shipping AB" (Schweden) sind verschiedene Gesellschaften, und der
Vorschlag trägt eine entsprechende Warnung.

Bestätigte Verschmelzungen sind ein `UPDATE` auf einen Cluster-Zeiger. Keine
Neuindizierung, kein Neuaufbau, sofort wirksam.

**Föderationssperre.** Alle Pods müssen identisch normalisieren, sonst
scheitert der Abgleich still. `fingerprint()` hasht sämtliche Regeltabellen;
zwei Pods vergleichen ihn vor dem ersten Abgleich und lehnen bei Abweichung
ab. Ein lauter Fehler ist besser als halb funktionierende Treffer.

## 10. Indra-Signal

Eine frühere Fassung verschickte die Suchanfrage im Klartext per Broadcast.
Damit erfährt jeder Teilnehmer — auch der kompromittierte — das
Rechercheziel, Wochen vor der Veröffentlichung. Hashen genügt nicht;
Namenswörterbücher sind trivial durchprobierbar.

Stattdessen ein Oblivious PRF über P-256:

```
1. Alice:  P = hash_to_curve(Entität), zufälliges r
           sendet r·P
2. Bob:    antwortet b·(r·P)            ← lernt nichts über P
3. Alice:  rechnet r⁻¹·(b·r·P) = b·P
           prüft b·P gegen Bobs Bloom-Index
```

**Hash-to-Curve ist notwendig.** Der bequeme Weg `P = H(x)·G` ist ein
Totalbruch: Alice fragt einmal mit `H(x)=1`, erhält `b·G` und rechnet danach
für jede Entität `b·H(x)·G` selbst aus — ein Wörterbuchangriff auf Bobs
gesamten Bestand ohne weitere Anfrage. Deshalb Try-and-Increment auf der
x-Koordinate, wo der diskrete Logarithmus niemandem bekannt ist.

**Klassifikation ohne Rückfrage.** Ein Signal soll melden, wie heikel das
Material der Gegenstelle ist — aber Bob weiß nicht, wonach gefragt wurde.
Auflösung: **ein Bloom-Index je Schutzstufe.** Alice prüft ihren PRF-Wert
gegen alle und liest die Stufe am Treffer ab. Stufen, die die Policy sperrt,
werden gar nicht erst indiziert; für die Föderation existieren sie nicht.

**Ratenbegrenzung** ist Teil des Protokolls, nicht der Betriebsanleitung.
Ohne sie könnte Alice Namenslisten durchprobieren.

Gemessen: 1,3 ms je Anfrage, Index über 500 Entitäten in 0,31 s und 1,8 KB.

## 11. Indra-Lichtung

Ein flüchtiger, isolierter Raum für die Zusammenarbeit zweier Redaktionen.
Er enthält ausschließlich, was beide Seiten ausdrücklich freigegeben haben.

Es wandert nicht der Fakt, sondern die **Aussage** — mit Dokumentbezug,
Beleglage und Prüfsumme, ohne den Dokumentinhalt. Die Gegenseite sieht
also, worauf eine Behauptung beruht und wie gut sie trägt, ohne das
Quellmaterial zu bekommen.

Beim Schließen wird die Ablage verworfen. Was bleibt, ist eine beidseitig
mit Ed25519 signierte Beweiskette ohne Rohdaten — prüfbar auch dann, wenn
später eine Seite bestreitet, beteiligt gewesen zu sein.

## 12. Axon-Transport

Ed25519 als langlebige Identität, X25519 je Sitzung, AES-256-GCM als
Nutzlastverschlüsselung, HKDF zur Ableitung. Drei Punkte, die den
Unterschied zwischen Verschlüsselung und Sicherheit ausmachen:

**Replay-Schutz.** Jeder Umschlag trägt einen streng monotonen Zähler.

**Vorwärtsgeheimnis.** Flüchtige Sitzungsschlüssel, signiert mit der
langlebigen Identität. Wer den Identitätsschlüssel später erbeutet,
entschlüsselt mitgeschnittenen Verkehr nicht rückwirkend — bei Journalisten
ist genau das der Regelfall.

**Verkehrsanalyse.** Kein Koordinator, der alles sieht. Einzelzustellung an
jede Gegenstelle, Umschläge auf ein 512-Byte-Raster aufgefüllt, damit die
Nachrichtenlänge den Typ nicht verrät.

Aufnahme neuer Pods über Bürgschaften im Web of Trust: keine
Zertifizierungsstelle, sondern die Vertrauensform, die bei Journalisten
ohnehin gilt.

## 13. Verifikation als Arbeitsablauf

Palantirs Produkt ist nicht die Datenbank, sondern das, was Ermittler acht
Stunden am Tag damit tun. Das journalistische Gegenstück ist Prüfung, nicht
Abruf. IndraNet führt vier Arbeitslisten:

- **Umstritten** — Quellen widersprechen sich
- **Einfach belegt** — vor Veröffentlichung nachlegen
- **Widerrufen** — Grundlage zurückgezogen
- **Bestätigt** — mehrfach unabhängig getragen

Dazu die Abhängigkeitsfrage: *Welche Fakten fallen, wenn dieses Dokument
fällt, und welche fallen ersatzlos?* Diese Frage ist vor jedem Widerruf zu
stellen und im faktenzentrierten Modell praktisch nicht zu beantworten.

## 14. Was gemessen ist

62 Tests über alle Module. Darunter:

- Beleglage: eine Quelle → `EINFACH_BELEGT`, zwei unabhängige →
  `BESTAETIGT`, dieselbe Quelle zweimal zählt nicht doppelt
- Widerspruch nur bei Prädikaten mit einem Wert je Subjekt, und nur in der
  Frage­richtung, in der er sich zeigt
- Widerruf erfasst alle abgeleiteten Aussagen und entfernt die Kanten aus
  allen Pfaden
- Verschmelzung wirkt sofort ohne Neuindizierung
- Firewall weist Arrays, Zusatzfelder, `doc_id`, `fact_id`, Beleglage und
  Subjekt bei `NO_MATCH` ab
- PSI: Kurvenkonstanten rechnerisch abgeleitet und gegengeprüft, Treffer und
  Nichttreffer korrekt, Ratenbegrenzung greift
- Axon: Replay abgewiesen, Föderationssperre greift
- Oberfläche: keine externen Ressourcen, Belege rollenabhängig,
  Whistleblower-Material geschwärzt ausgeliefert

## 15. Grenzen

**Der Extraktionsparser ist eine Mustertabelle.** Die Schnittstelle steht,
das Constrained Decoding ist nicht angebunden.

**Anonymität gegenüber der Gegenstelle.** Bob erfährt nicht, *wonach* Alice
fragt — aber *dass* sie fragt. Das ist der Preis der Ratenbegrenzung. Der
Ausweg sind anonyme Zugangsnachweise über einen Mixnet-Pfad.

**Alias-Divergenz zwischen Pods.** Verschmilzt Pod A „Mueller" auf „Müller"
und Pod B nicht, verfehlen sich beide beim Abgleich. Die drei Auswege —
Aliase mitsenden, Aliase teilen, Fehltreffer hinnehmen — haben alle Kosten,
keiner ist gewählt.

**Speicher im laufenden Betrieb.** Der Behälter auf der Platte ist
verschlüsselt (Abschnitt 17), aber während der Pod offen ist, steht der
Klartext im Arbeitsspeicher. Python kann nicht garantieren, dass nichts in
die Auslagerungsdatei gerät. Für Material, bei dem das zählt, gehört der Pod
auf ein System mit verschlüsseltem Swap.

**Entity Resolution behandelt nur Namen.** In der Praxis sind
Registernummer, Adresse und Geburtsdatum die stärkeren Signale.

**Die Lichtung verwirft ihre Ablage**, garantiert aber nicht, dass nichts im
Speicher zurückbleibt. Für echten Schutz gehört sie in einen Prozess mit
gesperrtem Speicher und verschlüsseltem Swap.

## 16. Anschluss an öffentliche Datenbestände

IndraNet ist bewusst die andere Hälfte eines Problems, dessen erste Hälfte
andere gut lösen. **World Monitor** bündelt den öffentlichen Weltzustand in
Echtzeit und schreibt selbst, es habe keine private Ontologie für interne
Daten. **OpenSanctions** pflegt Sanktionslisten und politisch exponierte
Personen im FollowTheMoney-Modell. IndraNet hält, was Ihre Recherche
behauptet, und wie gut es belegt ist.

Drei Regeln bestimmen jeden Anschluss.

### Korpus holen, lokal abgleichen

Eine Screening-Anfrage an einen fremden Dienst verrät, wen Sie prüfen. Bei
einer laufenden Recherche **ist die Namensliste das Rechercheziel** — genau
die Größe, die wir in der Föderation mit einem Oblivious PRF schützen. Es
wäre widersinnig, sie eine Ebene tiefer preiszugeben.

Also: Korpus einmal herunterladen, Abgleich auf dem Gerät. OpenSanctions
stellt seine Massendaten ohne Login und ohne API-Schlüssel bereit, und der
Matching-Dienst `yente` steht unter MIT-Lizenz und lässt sich selbst
betreiben. Wo ein Dienst nur online abfragbar ist, muss der Abgleich
ausdrücklich freigegeben werden und wird protokolliert.

### Quellen altern, und das gehört angezeigt

Eine Recherche auf einem sechs Monate alten Registerauszug sollte das
ausweisen. Jede Quelle führt Buch über letzten Abruf, letzten Erfolg,
Datenstand und Fehler; die Ansicht **Extern** zeigt es als `OK`, `ALT`,
`VERALTET`, `FEHLER` oder `NIE`.

Die Idee ist bei World Monitor abgeschaut, das den Zustand aller seiner
Datenzulieferungen öffentlich ausweist — die fehlerhaften eingeschlossen.
Das ist die richtige Haltung: Wer nur die funktionierenden Quellen zeigt,
erzeugt ein falsches Bild vom Stand der Dinge.

### Funde sind keine Aussagen

Ein Sanktionstreffer ist ein Fund, keine Behauptung. Er wird angezeigt und
kann übernommen werden — aber übernehmen muss ein Mensch. Wer das
automatisiert, holt sich fremde Fehler als eigene Fakten ins Haus und
verliert die Belegkette an der Stelle, an der sie am meisten zählt.

Ebenso gilt beim Ziehen von Beziehungen: Voreingestellt müssen **beide
Enden** einer Beziehung im Pod bekannt sein. Sonst wandern über eine
politisch exponierte Person mit vierzig Mandaten vierzig Gesellschaften
mit, die niemand angefordert hat.

### Lizenzhinweis

Der Programmcode von OpenSanctions ist MIT-lizenziert; **die Daten sind es
nicht** — sie stehen unter CC-BY-NC. Für eine Redaktion ist das
unproblematisch. Wer IndraNet mit vorbefülltem Bestand verkauft, braucht
eine Datenlizenz. Diese Unterscheidung ist leicht zu übersehen und teuer.

## 17. Zugriffskontrolle und Verschlüsselung

Drei Lücken, die im Betrieb sofort aufgefallen wären, sind geschlossen.

### Verschlüsselter Behälter

Die Pod-Datei lag zuvor im Klartext. Für ein Werkzeug, das
Whistleblower-Material verwaltet, war das der schwerwiegendste
verbleibende Mangel.

Die Datenbank lebt jetzt vollständig im Arbeitsspeicher; auf die Platte
gelangt nur ein verschlüsselter Behälter. Beim Öffnen wird entschlüsselt
und in eine In-Memory-Datenbank geladen, beim Sichern serialisiert,
verschlüsselt und atomar geschrieben.

Der Unterschied zu „Datei nachträglich verschlüsseln" ist entscheidend:
Dort liegt der Klartext zwischenzeitlich auf der Platte — als Datei, als
WAL-Journal, als temporäre Kopie — und überlebt das Löschen im Zweifel in
freigegebenen Blöcken. Hier berührt er nie ein Dateisystem.

Schlüsselableitung mit scrypt (N = 2¹⁷), Verschlüsselung mit AES-256-GCM,
Kopfdaten als zusätzlich authentifizierte Daten. Die Ableitung dauert
bewusst rund eine Sekunde: Das macht das Durchprobieren von Passphrasen
teuer. Wahlweise zusätzlich eine Schlüsseldatei — Wissen und Besitz
zusammen.

### Konten statt Auswahlfeld

Die Rolle war in der Oberfläche ein Auswahlfeld: Jeder konnte ADMIN
wählen. Auf einem Einzelplatz war das vertretbar, sobald zwei Personen
denselben Pod benutzen, war das Indra-Juwel wirkungslos — es prüfte
korrekt, aber niemand prüfte, wer fragte.

Jetzt kommt die Rolle aus der Sitzung, nicht aus der Anfrage. Passwörter
mit scrypt gehasht, Sitzungen mit Ablauf, Sperre nach fünf Fehlversuchen,
gleiche Fehlermeldung für falschen Namen und falsches Passwort, damit die
Benutzerliste nicht ausleitbar ist. Schreibende Vorgänge verlangen
mindestens JOURNALIST, ein Widerruf mindestens LEITUNG.

Erst damit bekommt das Vier-Augen-Prinzip Substanz: Vorher war
`freigeber=["a", "b"]` eine Liste ausgedachter Zeichenketten. Jetzt müssen
es zwei verschiedene, bestehende Konten sein.

Ein Pod ohne Konten läuft weiterhin als Einzelplatz mit vollen Rechten —
wer die Datei und die Passphrase hat, besitzt ihn ohnehin. Sobald das
erste Konto besteht, gilt Anmeldepflicht.

**Grenze:** Diese Schicht regelt die Zusammenarbeit mehrerer Personen an
einem Pod, nicht den Schutz gegen den Besitzer des Behälters — die Konten
liegen im selben Behälter. Für getrennte Vertrauensbereiche braucht es
getrennte Pods; dafür gibt es die Föderation.

### Erweitertes Prädikatsvokabular

Sechs Prädikate deckten Firmenstrukturen ab, aber keine Anschriften,
Registernummern, Zahlungen, Ämter oder Verwandtschaften. Jetzt sind es
22 Grundprädikate, mit Gegenrichtung 44, in fünf Gruppen: Eigentum und
Beteiligung, Ämter und Funktionen, Ort und Identität, Beziehungen zwischen
Personen, Geld und Vorgänge.

Firewall-Vokabular und Speicherschema werden aus derselben Tabelle
abgeleitet — ein Prädikat, das der Speicher kennt und die Firewall nicht,
wäre ein stiller Ausfall. Ein Test prüft die Deckungsgleichheit.

Für jedes Prädikat ist festgelegt, ob es je Subjekt einen Wert erlaubt.
Nur dort ist eine zweite Angabe ein Widerspruch: eine Gesellschaft hat
mehrere Direktoren, aber einen Sitz.

**Achtung:** Eine Vokabularerweiterung ändert den Resolver-Fingerabdruck.
Alle Pods eines Verbundes müssen gleichzeitig aktualisieren, sonst lehnt
die Föderationssperre den Abgleich ab — laut und richtig.

## 18. Belegdokumente

Die Vorgängerfassung hielt Verweis und Prüfsumme, nicht das Dokument. Die
Begründung — ein Leak mit Millionen Dateien gehöre in das verschlüsselte
Dateisystem der Redaktion — gilt für ein großes Haus mit IT-Abteilung. Für
die freie Journalistin gilt sie nicht: Sie hat ein Notebook und vielleicht
eine externe Platte. Ein Verweis auf `D:\Akten\leak.pdf` ist für sie kein
Schutz, sondern eine Notiz.

IndraNet bewahrt Belegdokumente deshalb wahlweise selbst auf.

### Warum nicht im Behälter

Der Behälter wird beim Öffnen vollständig in den Arbeitsspeicher geladen
und beim Sichern als Ganzes neu verschlüsselt (Abschnitt 17). Mit 500 MB
Dokumenten darin wäre er unbenutzbar: Jedes Speichern schriebe alles neu,
und der Speicherbedarf verdreifachte sich.

Stattdessen ein eigener Ablageordner daneben. Jede Datei einzeln
verschlüsselt, blockweise verarbeitet — eine 2-GB-Datei belegt nie mehr als
einen Block im Arbeitsspeicher. Der Behälter bleibt klein und schnell; ein
gemessenes Beispiel: 8 KB Behälter neben 292 KB Dokument.

### Blockweise Verschlüsselung

AES-256-GCM verarbeitet keine Ströme. Die Datei wird in Blöcke zu 1 MiB
geteilt, jeder mit eigener Nonce. Drei Angriffe muss das abwehren, und
jeder wird über die authentifizierten Zusatzdaten je Block ausgeschlossen:

| Angriff | Abwehr |
|---|---|
| Blöcke umsortieren | Blockzähler geht in die Zusatzdaten ein |
| Datei abschneiden | letzter Block ist markiert; fehlt er, bricht die Entschlüsselung ab |
| Blöcke vertauschen | Kopfsatz-Hash geht in jeden Block ein |

Alle drei sind durch Tests abgedeckt.

### Zwei Schlüssel aus einer Passphrase

Der Dokumentschlüssel wird per HKDF aus dem Behälterschlüssel abgeleitet,
ist aber nicht derselbe. Wer je an den Dokumentschlüssel käme, könnte damit
den Behälter nicht öffnen.

### Was der Ablageordner preisgibt

Die Dateinamen sind Hashes der Dokumentkennung. Originalname, Typ und
Größe stehen verschlüsselt im inneren Kopfsatz. Wer den Ordner sieht,
erfährt die Anzahl der Dokumente und ihre ungefähre Größe — mehr nicht.

### Der Verweismodus bleibt

Für große Bestände und für Häuser mit eigener Infrastruktur ist die
Aufbewahrung im Pod falsch. Beide Wege stehen deshalb je Dokument zur
Wahl; die Aufbewahrung ist die Vorgabe, weil sie für die Mehrheit der
Zielgruppe die richtige ist.

### Grenze

Die Passphrase wird damit zum einzigen Schutz für das gesamte Material.
Das ist eine Verschiebung: Vorher konnte ein verlorener Behälter nur die
Faktenlage preisgeben, jetzt auch die Quelldokumente. Dem steht gegenüber,
dass die Alternative für diese Zielgruppe kein Schutz war, sondern gar
keiner.

## 19. Governance

Die Technologie ist quelloffen und auditierbar. Ein Betrieb ohne
Patent-Grant ist für Stiftungen und Redaktionen nicht tragfähig; die
Lizenzierung sollte eine ausdrückliche Patentklausel enthalten
(Apache-2.0-Muster oder ein Defensive-Patent-Pledge).

Die Koordinationsinfrastruktur — Web of Trust, Aufnahmeregeln,
Sicherheitsaudits — gehört in eine gemeinnützige Trägerschaft. Die Pods
gehören den Redaktionen.

## 20. Herkunft

Das Signalprotokoll folgt dem Entwurf von **DatashareNetwork** (EPFL SPRING
Lab und ICIJ, USENIX Security 2020) — begutachtet, mit Sicherheitsbeweis und
für genau diesen Anwendungsfall entworfen.

Für die Entity Resolution ist das **Follow-the-Money-Modell von OCCRP
Aleph** der richtige nächste Schritt.

---

*IndraNet ist ein Werkzeug für die vierte Gewalt. Es erreicht die
Ermittlungsfähigkeit zentraler Plattformen, ohne deren Kontrollstruktur zu
übernehmen.*
