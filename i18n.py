"""
IndraNet — Sprachen / Languages
================================

Alle Oberflächentexte in Deutsch und Englisch. Die Fachbegriffe der
Architektur (Pod, Indra-Signal, Lichtung) bleiben in beiden Sprachen
gleich; übersetzt wird, was eine Journalistin liest, nicht was eine
Entwicklerin liest.

All interface strings in German and English. Architectural terms stay
identical in both languages; what gets translated is what a journalist
reads, not what a developer reads.
"""

SPRACHEN = ("de", "en")

T = {
    # -- Navigation ------------------------------------------------------
    "nav.ask":        ("Fragen", "Ask"),
    "nav.verify":     ("Prüfen", "Verify"),
    "nav.entities":   ("Entitäten", "Entities"),
    "nav.network":    ("Netz", "Network"),
    "nav.sources":    ("Quellen", "Sources"),
    "nav.record":     ("Erfassen", "Record"),
    "nav.external":   ("Extern", "External"),
    "nav.import":     ("Import", "Import"),

    # -- Fragen ----------------------------------------------------------
    "ask.title":      ("Frage an den Bestand", "Ask the fact base"),
    "ask.placeholder": ("Wem gehört Mare Liberum Ltd.?",
                        "Who owns Mare Liberum Ltd.?"),
    "ask.submit":     ("Fragen", "Ask"),
    "ask.empty":      ("Stellen Sie eine Frage. Der Bestand antwortet nur mit "
                       "dem, was belegt ist.",
                       "Ask a question. The fact base answers only with what "
                       "is documented."),
    "ask.no_predicate": ("Kein Prädikat erkannt — es wurde keine Abfrage "
                         "gestellt.",
                         "No predicate recognised — no query was made."),
    "ask.unsupported": ("Diese Frageform wird nicht unterstützt.",
                        "This question form is not supported."),
    "ask.nomatch":    ("Zu dieser Frage liegt kein Fakt im Bestand.",
                       "No fact in this base answers that question."),
    "ask.discarded":  ("Formulierung verworfen, unbelegte Begriffe:",
                       "Wording discarded, unsupported terms:"),

    # -- Beleglage -------------------------------------------------------
    "state.BESTAETIGT":     ("Bestätigt", "Corroborated"),
    "state.EINFACH_BELEGT": ("Einfach belegt", "Single-sourced"),
    "state.UMSTRITTEN":     ("Umstritten", "Contested"),
    "state.WIDERRUFEN":     ("Widerrufen", "Retracted"),
    "state.BESTAETIGT.hint": ("Zwei oder mehr unabhängige Quellen",
                              "Two or more independent sources"),
    "state.EINFACH_BELEGT.hint": ("Eine Quelle — vor Veröffentlichung nachlegen",
                                  "One source — corroborate before publishing"),
    "state.UMSTRITTEN.hint": ("Quellen widersprechen sich",
                              "Sources contradict each other"),
    "state.WIDERRUFEN.hint": ("Grundlage zurückgezogen",
                              "Underlying source withdrawn"),

    # -- Belege ----------------------------------------------------------
    "ev.title":       ("Belege", "Evidence"),
    "ev.none":        ("Wählen Sie einen Fakt, um seine Belege zu sehen.",
                       "Select a fact to see its evidence."),
    "ev.withheld":    ("Zurückgehalten", "Withheld"),
    "ev.withheld_why": ("Ihre Rolle reicht für diese Schutzstufe nicht aus. "
                        "Dass es diesen Beleg gibt, sehen Sie; was darin "
                        "steht, nicht.",
                        "Your role is insufficient for this protection level. "
                        "You can see that this evidence exists; not what it "
                        "says."),
    "ev.locator":     ("Fundstelle", "Locator"),
    "ev.source":      ("Quelle", "Source"),
    "ev.recorded":    ("Erfasst von", "Recorded by"),
    "ev.level":       ("Schutzstufe", "Protection level"),
    "ev.sources_n":   ("Unabhängige Quellen", "Independent sources"),
    "ev.chain":       ("Beweiskette", "Evidence chain"),
    "ev.copy":        ("Kette kopieren", "Copy chain"),
    "ev.role":        ("Rolle", "Role"),
    "ev.contradicts": ("Widerspricht", "Contradicts"),
    "ev.open_doc":    ("Dokument öffnen", "Open document"),
    "ev.export":      ("Kette exportieren", "Export chain"),

    # -- Korrektur -------------------------------------------------------
    "cor.edit":       ("Korrigieren", "Correct"),
    "cor.retract":    ("Widerrufen", "Retract"),
    "cor.discard":    ("Verwerfen", "Discard"),
    "cor.confirm":    ("Ausführen", "Apply"),
    "cor.edit_hint":  ("Leere Felder bleiben unverändert. Die alte Fassung "
                       "steht danach im Korrekturprotokoll.",
                       "Empty fields stay unchanged. The previous version "
                       "goes into the correction log."),
    "cor.retract_hint": ("Die Aussage bleibt sichtbar und zählt als "
                         "widerrufen. Richtig, wenn sich eine Behauptung als "
                         "falsch herausstellt.",
                         "The assertion stays visible and counts as "
                         "retracted. Right when a claim turns out to be "
                         "wrong."),
    "cor.discard_hint": ("Nur für Tippfehler und Fehlgriffe. Der Inhalt "
                         "verschwindet vollständig; im Korrekturprotokoll "
                         "bleibt stehen, dass gelöscht wurde.",
                         "Only for typos and misfires. The content "
                         "disappears entirely; the correction log records "
                         "that a deletion happened."),

    # -- Sicherung -------------------------------------------------------
    "bk.label":       ("Sicherung", "Backup"),
    "bk.never":       ("nie", "never"),
    "bk.now":         ("jetzt sichern", "back up now"),
    "bk.done":        ("Sicherung erstellt", "Backup created"),
    "bk.parts":       ("Teile", "parts"),

    # -- Prüfen ----------------------------------------------------------
    "vf.title":       ("Was vor der Veröffentlichung Arbeit braucht",
                       "What needs work before publication"),
    "vf.contested":   ("Umstritten", "Contested"),
    "vf.single":      ("Einfach belegt", "Single-sourced"),
    "vf.retracted":   ("Widerrufen", "Retracted"),
    "vf.confirmed":   ("Bestätigt", "Corroborated"),
    "vf.mark":        ("Geprüft", "Mark checked"),
    "vf.doubt":       ("Zweifelhaft", "Mark doubtful"),
    "vf.note":        ("Notiz", "Note"),
    "vf.clean":       ("Nichts offen. Alles im Bestand ist mehrfach belegt.",
                       "Nothing open. Everything here is multiply sourced."),
    "vf.share":       ("Anteil bestätigt", "Share corroborated"),

    # -- Entitäten -------------------------------------------------------
    "en.title":       ("Verschmelzungsvorschläge", "Merge suggestions"),
    "en.lead":        ("Nichts wird automatisch zusammengeführt. Diese Paare "
                       "sehen ähnlich aus — entscheiden müssen Sie.",
                       "Nothing is merged automatically. These pairs look "
                       "alike — you decide."),
    "en.merge":       ("Verschmelzen", "Merge"),
    "en.separate":    ("Getrennt lassen", "Keep separate"),
    "en.reason":      ("Begründung (verpflichtend)", "Reason (required)"),
    "en.clean":       ("Keine offenen Vorschläge.", "No open suggestions."),
    "en.warn":        ("Achtung", "Caution"),
    "en.count":       ("Entitäten im Bestand", "Entities in base"),

    # -- Netz ------------------------------------------------------------
    "nw.title":       ("Verbindungen zwischen zwei Entitäten",
                       "Connections between two entities"),
    "nw.from":        ("Von", "From"),
    "nw.to":          ("Nach", "To"),
    "nw.find":        ("Suchen", "Find"),
    "nw.none":        ("Keine Verbindung innerhalb der Suchtiefe gefunden.",
                       "No connection found within the search depth."),
    "nw.weakest":     ("Schwächstes Glied", "Weakest link"),
    "nw.graph":       ("Netzansicht", "Network view"),
    "nw.graph_title": ("Netz der Beziehungen", "Network of relations"),
    "nw.graph_hint":  ("Kantenfarbe zeigt die Beleglage. Ein Knoten weiter "
                       "draußen ist nur so belastbar wie die Kanten dorthin.",
                       "Edge colour shows the evidential state. A node "
                       "further out is only as load-bearing as the edges "
                       "leading to it."),
    "nw.paths":       ("Pfade", "Paths"),
    "nw.center":      ("Mittelpunkt", "Centre"),
    "nw.depth":       ("Tiefe", "Depth"),
    "nw.draw":        ("Zeichnen", "Draw"),
    "nw.nodes":       ("Knoten", "nodes"),
    "nw.edges":       ("Kanten", "edges"),
    "nw.legend":      ("Kantenfarbe = Beleglage", "Edge colour = evidential state"),
    "nw.click":       ("Knoten anklicken, um ihn zum Mittelpunkt zu machen",
                       "Click a node to make it the centre"),
    "nw.empty":       ("Keine Verbindungen zu dieser Entität.",
                       "No connections for this entity."),
    "nw.hint":        ("Ein Pfad ist nur so belastbar wie seine schwächste "
                       "Kante.",
                       "A path is only as strong as its weakest edge."),

    # -- Quellen ---------------------------------------------------------
    "src.title":      ("Dokumente", "Documents"),
    "src.retract":    ("Widerrufen", "Retract"),
    "src.retracted":  ("Widerrufen", "Retracted"),
    "src.depends":    ("Fakten, die daran hängen", "Facts depending on it"),
    "src.falls":      ("Fällt ersatzlos", "Falls with no substitute"),
    "src.confirm_retract": ("Dieses Dokument widerrufen? Alle daraus "
                            "abgeleiteten Aussagen werden ungültig.",
                            "Retract this document? Every assertion derived "
                            "from it becomes invalid."),

    # -- Statusleiste ----------------------------------------------------
    "st.pod":         ("Knoten", "Node"),
    "st.role":        ("Rolle", "Role"),
    "st.plain":       ("unverschlüsselt", "unencrypted"),
    "st.theme":       ("Darstellung", "Appearance"),

    # -- Anmeldung -------------------------------------------------------
    "auth.lead":      ("Dieser Pod verlangt eine Anmeldung. Ihre Rolle "
                       "bestimmt, welche Belege Sie sehen.",
                       "This pod requires sign-in. Your role determines which "
                       "evidence you can see."),
    "auth.user":      ("Benutzername", "Username"),
    "auth.pass":      ("Passwort", "Password"),
    "auth.login":     ("Anmelden", "Sign in"),
    "auth.logout":    ("Abmelden", "Sign out"),
    "auth.failed":    ("Anmeldung fehlgeschlagen.", "Sign-in failed."),
    "auth.note":      ("Nach fünf Fehlversuchen wird das Konto für fünf "
                       "Minuten gesperrt. Alle Versuche werden protokolliert.",
                       "After five failed attempts the account is locked for "
                       "five minutes. All attempts are logged."),
    "auth.encrypted": ("verschlüsselt", "encrypted"),

    # -- Handerfassung ---------------------------------------------------
    "rec.title":      ("Aussage von Hand erfassen", "Record an assertion"),
    "rec.lead":       ("Zuerst der Beleg, dann die Aussage. Ohne Beleg "
                       "entsteht kein Fakt — das gilt hier wie beim Import.",
                       "Evidence first, then the assertion. No fact arises "
                       "without evidence — here as in the import."),
    "rec.step1":      ("1 · Beleg", "1 · Evidence"),
    "rec.step2":      ("2 · Aussage", "2 · Assertion"),
    "rec.existing":   ("Vorhandener Beleg", "Existing evidence"),
    "rec.new":        ("neu anlegen", "create new"),
    "rec.file":       ("Datei", "File"),
    "rec.note":       ("Notiz", "Note"),
    "rec.source":     ("Sonstige", "Other"),
    "rec.file_pick":  ("Datei auswählen", "Choose a file"),
    "rec.file_hint":  ("Wählen Sie eine Datei.", "Choose a file."),
    "rec.keep":       ("Dokument im Pod ablegen (verschlüsselt)",
                       "Store the document in the pod (encrypted)"),
    "rec.keep_hint":  ("Empfohlen, wenn Sie keinen sicheren Ablageort "
                       "haben. Die Datei wird verschlüsselt neben dem "
                       "Knoten gespeichert und verlässt Ihren Rechner nicht.",
                       "Recommended if you have no secure storage. The file "
                       "is stored encrypted next to the node and does not "
                       "leave your machine."),
    "rec.ref_hint":   ("Nur Verweis und Prüfsumme. Für große Bestände auf "
                       "einem verschlüsselten Laufwerk — die Datei muss dann "
                       "dort bleiben.",
                       "Reference and checksum only. For large corpora on an "
                       "encrypted drive — the file must then stay there."),
    "rec.uploading":  ("Wird verschlüsselt und abgelegt…",
                       "Encrypting and storing…"),
    "rec.stored":     ("im Pod abgelegt", "stored in pod"),
    "rec.hashing":    ("Prüfsumme wird berechnet…", "Computing checksum…"),
    "rec.location":   ("Ablageort (zum Wiederfinden)",
                       "Storage location (to find it again)"),
    "rec.note_text":  ("Notiztext", "Note text"),
    "rec.note_ph":    ("Hintergrundgespräch 3.3.2026: Die Quelle bestätigt, "
                       "dass …",
                       "Background interview 3 Mar 2026: the source confirms "
                       "that …"),
    "rec.doc_title":  ("Titel des Belegs", "Evidence title"),
    "rec.doc_source": ("Quelle", "Source"),
    "rec.source_ph":  ("Register Oslo · Übergabe 2026-03 · eigene Recherche",
                       "Oslo registry · handover 2026-03 · own research"),
    "rec.create":     ("Beleg anlegen", "Create evidence"),
    "rec.pick_first": ("Legen Sie rechts zuerst einen Beleg an oder wählen "
                       "Sie einen vorhandenen.",
                       "Create or select evidence on the right first."),
    "rec.subject":    ("Subjekt (wer/was)", "Subject (who/what)"),
    "rec.object":     ("Objekt (wen/was)", "Object (whom/what)"),
    "rec.predicate":  ("Beziehung", "Relation"),
    "rec.locator":    ("Fundstelle", "Locator"),
    "rec.locator_ph": ("S. 14, Zeile 7", "p. 14, line 7"),
    "rec.quote":      ("Zitat (optional)", "Quote (optional)"),
    "rec.save":       ("Aussage erfassen", "Record assertion"),
    "rec.other_source": ("Beleg wechseln", "Change evidence"),
    "rec.recent":     ("Zuletzt erfasst", "Recently recorded"),
    "rec.need_title": ("Titel und Quelle sind Pflicht.",
                       "Title and source are required."),
    "rec.need_file":  ("Bitte eine Datei auswählen.", "Please choose a file."),
    "rec.need_note":  ("Notiztext fehlt.", "Note text is missing."),
    "rec.need_both":  ("Subjekt und Objekt sind Pflicht.",
                       "Subject and object are required."),
    "rec.privacy":    ("Der Pod speichert Verweis und Prüfsumme, nie das "
                       "Dokument selbst. Die Prüfsumme wird im Browser "
                       "berechnet — die Datei verlässt Ihren Rechner nicht.",
                       "The pod stores reference and checksum, never the "
                       "document itself. The checksum is computed in your "
                       "browser — the file does not leave your machine."),

    # -- Externe Quellen -------------------------------------------------
    "ex.title":       ("Externe Quellen", "External sources"),
    "ex.lead":        ("Der Abgleich läuft auf diesem Gerät. Ihre "
                       "Entitätsliste verlässt den Pod nicht.",
                       "Matching runs on this device. Your entity list does "
                       "not leave the pod."),
    "ex.health":      ("Zustand der Quellen", "Source health"),
    "ex.findings":    ("Funde", "Findings"),
    "ex.records":     ("Datensätze", "records"),
    "ex.days":        ("Tage alt", "days old"),
    "ex.never":       ("nie abgerufen", "never fetched"),
    "ex.local":       ("lokaler Abgleich", "local matching"),
    "ex.remote":      ("Abfrage nach außen", "outbound query"),
    "ex.nosources":   ("Keine externe Quelle angemeldet.",
                       "No external source registered."),
    "ex.nofindings":  ("Keine Funde.", "No findings."),
    "ex.note":        ("Ein Fund ist keine Aussage. Die Übernahme in den "
                       "Bestand ist ein eigener Schritt und braucht eine "
                       "menschliche Entscheidung.",
                       "A finding is not an assertion. Adopting it into the "
                       "base is a separate step and requires a human "
                       "decision."),

    # -- Import ----------------------------------------------------------
    "im.title":       ("Daten übernehmen", "Import data"),
    "im.lead":        ("Jede Zeile wird zu einer Aussage mit Fundstelle. "
                       "Fakten ohne Beleg entstehen hier nicht.",
                       "Every row becomes an assertion with a locator. Facts "
                       "without evidence do not arise here."),
    "im.csv":         ("CSV-Inhalt", "CSV content"),
    "im.mapping":     ("Zuordnung (subjekt:prädikat:objekt, eine je Zeile)",
                       "Mapping (subject:predicate:object, one per line)"),
    "im.doc_title":   ("Titel des Dokuments", "Document title"),
    "im.doc_source":  ("Quelle", "Source"),
    "im.level":       ("Schutzstufe", "Protection level"),
    "im.by":          ("Erfasst von", "Recorded by"),
    "im.run":         ("Übernehmen", "Import"),
    "im.done":        ("Übernommen", "Imported"),

    # -- Allgemein -------------------------------------------------------
    "app.tagline":    ("Föderierte Recherche. Die Daten bleiben, wo sie "
                       "hingehören.",
                       "Federated research. The data stays where it belongs."),
    "app.local":      ("Läuft lokal", "Running locally"),
    "gen.predicate":  ("Prädikat", "Predicate"),
    "gen.facts":      ("Fakten", "Facts"),
    "gen.assertions": ("Aussagen", "Assertions"),
    "gen.documents":  ("Dokumente", "Documents"),
    "gen.entities":   ("Entitäten", "Entities"),
    "gen.cancel":     ("Abbrechen", "Cancel"),
    "gen.error":      ("Fehler", "Error"),
    "gen.required":   ("Bitte ausfüllen.", "Please fill this in."),
}

PRAEDIKAT_LABEL = {
    "beneficial_owner_of":  ("ist wirtschaftlich berechtigt an",
                             "is beneficial owner of"),
    "holds_shares_in":      ("hält Anteile an", "holds shares in"),
    "controls":             ("kontrolliert", "controls"),
    "parent_of":            ("ist Muttergesellschaft von", "is parent of"),
    "director_of":          ("ist Direktor von", "is director of"),
    "employed_by":          ("ist beschäftigt bei", "is employed by"),
    "holds_office":         ("bekleidet das Amt", "holds office"),
    "advisor_to":           ("berät", "is advisor to"),
    "registered_in":        ("ist registriert in", "is registered in"),
    "resident_in":          ("ist ansässig in", "is resident in"),
    "address_of":           ("hat die Anschrift", "has address"),
    "identified_by":        ("hat die Kennung", "is identified by"),
    "national_of":          ("hat die Staatsangehörigkeit",
                             "is national of"),
    "family_of":            ("ist verwandt mit", "is family of"),
    "associate_of":         ("ist assoziiert mit", "is associate of"),
    "paid_to":              ("zahlte an", "paid to"),
    "contracted_with":      ("hat einen Vertrag mit", "contracted with"),
    "amount_of":            ("über den Betrag", "in the amount of"),
    "dated":                ("datiert auf", "dated"),
    "listed_in":            ("ist geführt in", "is listed in"),
    "operates_vessel":      ("betreibt", "operates"),
    "sanctioned_by":        ("ist sanktioniert von", "is sanctioned by"),

    # Gegenrichtung
    "beneficially_owned_by": ("gehört wirtschaftlich", "is owned by"),
    "shares_held_by":       ("Anteile gehalten von", "shares held by"),
    "controlled_by":        ("wird kontrolliert von", "is controlled by"),
    "subsidiary_of":        ("ist Tochter von", "is subsidiary of"),
    "has_director":         ("hat als Direktor", "has as director"),
    "employs":              ("beschäftigt", "employs"),
    "office_held_by":       ("Amt bekleidet von", "office held by"),
    "advised_by":           ("wird beraten von", "is advised by"),
    "registry_of":          ("ist Sitz von", "is registry of"),
    "residence_of":         ("ist Wohnsitz von", "is residence of"),
    "address_used_by":      ("Anschrift genutzt von", "address used by"),
    "identifies":           ("kennzeichnet", "identifies"),
    "nationals":            ("hat als Staatsangehörige", "has as nationals"),
    "family_reverse":       ("ist verwandt mit", "is family of"),
    "associate_reverse":    ("ist assoziiert mit", "is associate of"),
    "received_from":        ("erhielt von", "received from"),
    "contract_reverse":     ("hat einen Vertrag mit", "contracted with"),
    "amount_reverse":       ("ist Betrag von", "is amount of"),
    "date_of":              ("ist Datum von", "is date of"),
    "lists_entity":         ("führt", "lists"),
    "operated_by":          ("betrieben von", "operated by"),
    "sanctions":            ("sanktioniert", "sanctions"),
}


def t(schluessel: str, sprache: str = "de") -> str:
    i = 1 if sprache == "en" else 0
    eintrag = T.get(schluessel)
    return eintrag[i] if eintrag else schluessel


def als_dict(sprache: str = "de") -> dict:
    i = 1 if sprache == "en" else 0
    return {k: v[i] for k, v in T.items()}


def praedikate(sprache: str = "de") -> dict:
    i = 1 if sprache == "en" else 0
    return {k: v[i] for k, v in PRAEDIKAT_LABEL.items()}
