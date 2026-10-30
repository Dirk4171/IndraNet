"""
IndraNet — Navigator (nicht vertrauenswuerdige Seite der Firewall)
===================================================================

Laeuft in einem eigenen Prozess. Kennt das Praedikatsvokabular und sonst
nichts vom Speicher.

WARUM KEIN FEINABGESTIMMTES MODELL
----------------------------------
Eine fruehere Architektur sah zwei feinabgestimmte Adapter vor. Beide sind
entbehrlich:

  Adapter B faellt weg.   Durch die Ableitbarkeitspruefung darf die Antwort
                          ohnehin nur Woerter aus ihrer Eingabe enthalten.
                          Eine Vorlage leistet dasselbe bei null Risiko —
                          ein Sprachmodell an dieser Stelle traegt Gefahr
                          ohne Gegenwert.

  Adapter A wird zum
  eingeschraenkten Parser. Die Aufgabe ist semantisches Parsen in ein
                          geschlossenes Vokabular. Das leistet ein lokales
                          Modell mit Grammar-Constrained Decoding ohne
                          jedes Feintuning — und zwar STRUKTURELL
                          garantiert statt antrainiert: Was die Grammatik
                          nicht zulaesst, kann nicht ausgegeben werden.

Damit entfaellt die gesamte Zweiphasen-Trainingsarbeit. Die Mustertabelle
unten ist der Prototyp-Ersatz; `PARSER` ist der Steckplatz fuer den
eingeschraenkten Decoder.

DIE ABLEITBARKEITSPRUEFUNG BLEIBT
---------------------------------
Die Firewall verhindert, dass der Navigator Fakten KENNT. Sie verhindert
nicht, dass er welche ERFINDET. Jeder Inhaltsbegriff der Antwort wird
deshalb dagegen geprueft, ob er aus Subjekt, Objekt, Praedikat-Label oder
dem freigegebenen Lexikon ableitbar ist.

Das ist bewusst streng. Fluessigkeit und Nachpruefbarkeit stehen in
direktem Widerspruch; fuer ein gerichtsfestes System ist Strenge die
richtige Seite davon.
"""

from __future__ import annotations

import re
import uuid

from firewall import PREDICATE_IDS, PREDICATES

# --------------------------------------------------------------- Adapter A
UNKNOWN_PREDICATE = "UNKNOWN_PREDICATE"
UNSUPPORTED_DIRECTION = "UNSUPPORTED_DIRECTION"

# Muster fuer den Prototyp. Im Zielsystem ersetzt ein eingeschraenkter
# Decoder (Grammar-Constrained Decoding) diese Tabelle — die Signatur (Frage -> ID + Objekt) bleibt identisch, ebenso die
# Pflicht, bei Unsicherheit UNKNOWN_PREDICATE zu liefern.
# Muster fuer den Prototyp. Im Zielsystem ersetzt ein eingeschraenkter
# Decoder (Grammar-Constrained Decoding) diese Tabelle — die Signatur
# (Frage -> Praedikat + Objekt, bei Unsicherheit UNKNOWN_PREDICATE) bleibt.
#
# Die Praedikat-ID wird ueber den Namen aufgeloest, nicht hart verdrahtet:
# Eine Vokabularerweiterung darf hier nichts kaputtmachen.
_ROH: list[tuple[str, str, str]] = [
    # --- Deutsch ---------------------------------------------------------
    (r"wem\s+geh(ö|oe)rt\s+(?P<obj>.+?)\s*\??$", "beneficial_owner_of", "de"),
    (r"wer\s+ist\s+wirtschaftlich\s+berechtigt\s+an\s+(?P<obj>.+?)\s*\??$",
     "beneficial_owner_of", "de"),
    (r"wer\s+h(ä|ae)lt\s+anteile\s+an\s+(?P<obj>.+?)\s*\??$",
     "holds_shares_in", "de"),
    (r"wer\s+kontrolliert\s+(?P<obj>.+?)\s*\??$", "controls", "de"),
    (r"wer\s+ist\s+(die\s+)?mutter(gesellschaft)?\s+von\s+(?P<obj>.+?)\s*\??$",
     "parent_of", "de"),
    (r"wer\s+(ist|sind)\s+(der\s+|die\s+)?direktor(en)?\s+(von|der|des)\s+"
     r"(?P<obj>.+?)\s*\??$", "director_of", "de"),
    (r"wer\s+leitet\s+(?P<obj>.+?)\s*\??$", "director_of", "de"),
    (r"wer\s+arbeitet\s+(bei|f(ü|ue)r)\s+(?P<obj>.+?)\s*\??$",
     "employed_by", "de"),
    (r"wer\s+ber(ä|ae)t\s+(?P<obj>.+?)\s*\??$", "advisor_to", "de"),
    (r"wer\s+bekleidet\s+(das\s+amt\s+)?(?P<obj>.+?)\s*\??$",
     "holds_office", "de"),
    (r"(was|wer)\s+ist\s+in\s+(?P<obj>.+?)\s+registriert\s*\??$",
     "registered_in", "de"),
    (r"wer\s+wohnt\s+in\s+(?P<obj>.+?)\s*\??$", "resident_in", "de"),
    (r"wer\s+sitzt\s+(unter|an)\s+(der\s+)?(anschrift\s+)?(?P<obj>.+?)\s*\??$",
     "address_of", "de"),
    (r"wer\s+hat\s+die\s+(kennung|nummer)\s+(?P<obj>.+?)\s*\??$",
     "identified_by", "de"),
    (r"wer\s+ist\s+verwandt\s+mit\s+(?P<obj>.+?)\s*\??$", "family_of", "de"),
    (r"wer\s+ist\s+assoziiert\s+mit\s+(?P<obj>.+?)\s*\??$",
     "associate_of", "de"),
    (r"wer\s+(hat\s+)?(be)?zahlt(e)?\s+an\s+(?P<obj>.+?)\s*\??$",
     "paid_to", "de"),
    (r"wer\s+hat\s+einen\s+vertrag\s+mit\s+(?P<obj>.+?)\s*\??$",
     "contracted_with", "de"),
    (r"wer\s+ist\s+sanktioniert\s+(von|durch)\s+(?P<obj>.+?)\s*\??$",
     "sanctioned_by", "de"),
    (r"wer\s+steht\s+im\s+(?P<obj>.+?)\s*\??$", "listed_in", "de"),
    (r"wer\s+betreibt\s+(?P<obj>.+?)\s*\??$", "operates_vessel", "de"),

    # --- English ---------------------------------------------------------
    (r"who\s+owns\s+(?P<obj>.+?)\s*\??$", "beneficial_owner_of", "en"),
    (r"who\s+is\s+(the\s+)?beneficial\s+owner\s+of\s+(?P<obj>.+?)\s*\??$",
     "beneficial_owner_of", "en"),
    (r"who\s+holds\s+shares\s+in\s+(?P<obj>.+?)\s*\??$",
     "holds_shares_in", "en"),
    (r"who\s+controls\s+(?P<obj>.+?)\s*\??$", "controls", "en"),
    (r"who\s+is\s+(the\s+)?parent\s+(company\s+)?of\s+(?P<obj>.+?)\s*\??$",
     "parent_of", "en"),
    (r"who\s+(is|are)\s+(the\s+)?directors?\s+of\s+(?P<obj>.+?)\s*\??$",
     "director_of", "en"),
    (r"who\s+runs\s+(?P<obj>.+?)\s*\??$", "director_of", "en"),
    (r"who\s+works\s+(for|at)\s+(?P<obj>.+?)\s*\??$", "employed_by", "en"),
    (r"who\s+advises\s+(?P<obj>.+?)\s*\??$", "advisor_to", "en"),
    (r"who\s+holds\s+(the\s+)?office\s+(of\s+)?(?P<obj>.+?)\s*\??$",
     "holds_office", "en"),
    (r"what\s+is\s+registered\s+in\s+(?P<obj>.+?)\s*\??$",
     "registered_in", "en"),
    (r"who\s+resides\s+in\s+(?P<obj>.+?)\s*\??$", "resident_in", "en"),
    (r"who\s+is\s+at\s+(the\s+)?(address\s+)?(?P<obj>.+?)\s*\??$",
     "address_of", "en"),
    (r"who\s+is\s+identified\s+by\s+(?P<obj>.+?)\s*\??$",
     "identified_by", "en"),
    (r"who\s+is\s+related\s+to\s+(?P<obj>.+?)\s*\??$", "family_of", "en"),
    (r"who\s+is\s+associated\s+with\s+(?P<obj>.+?)\s*\??$",
     "associate_of", "en"),
    (r"who\s+paid\s+(?P<obj>.+?)\s*\??$", "paid_to", "en"),
    (r"who\s+contracted\s+with\s+(?P<obj>.+?)\s*\??$",
     "contracted_with", "en"),
    (r"who\s+is\s+sanctioned\s+by\s+(?P<obj>.+?)\s*\??$",
     "sanctioned_by", "en"),
    (r"who\s+is\s+listed\s+in\s+(?P<obj>.+?)\s*\??$", "listed_in", "en"),
    (r"who\s+operates\s+(?P<obj>.+?)\s*\??$", "operates_vessel", "en"),
]

_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(muster, re.I), PREDICATE_IDS[name], lang)
    for muster, name, lang in _ROH if name in PREDICATE_IDS
]

# Fragen in der Gegenrichtung (Subjekt bekannt, Objekt gesucht). Der
# Abruf aus dem Faktenspeicher ist unidirektional: Er loest (Praedikat, Objekt) -> Subjekt.
# Die Umkehrung braucht entweder gespiegelte Tripel oder eine zweite,
# gespiegelte Abfrage. Bis dahin: ehrliche Fehlermeldung.
_REVERSE = re.compile(
    r"^wo\s+ist\s+.+\s+registriert|^welche\s+.+\s+h(ä|ae)lt\s+"
    r"|^where\s+is\s+.+\s+registered|^which\s+.+\s+does\s+.+\s+hold",
    re.I)


def adapter_a(question: str):
    """Frage -> {'predicate_id': int, 'object': str} oder Fehlerkennung (str)."""
    q = " ".join(question.strip().split())
    if _REVERSE.match(q):
        return UNSUPPORTED_DIRECTION
    for pattern, pid, lang in _PATTERNS:
        m = pattern.search(q)
        if m:
            obj = m.group("obj").strip(" .,")
            for lead in ("der ", "die ", "das ", "den ", "dem ", "the "):
                if obj.lower().startswith(lead):
                    obj = obj[len(lead):]
            return {"predicate_id": pid, "object": obj, "lang": lang}
    return UNKNOWN_PREDICATE


# --------------------------------------------------------------- Adapter B
_TEMPLATES_EN = {
    1: "{subj} is beneficial owner of {obj}.",
    2: "{subj} is registered in {obj}.",
    3: "{subj} holds shares in {obj}.",
    4: "{subj} is director of {obj}.",
    5: "{subj} is listed in {obj}.",
    6: "{subj} operates {obj}.",
}
_NO_MATCH_EN = "No fact on {obj} for predicate {pred} in this pod."
_AMBIGUOUS_EN = ("Several subjects relate to {obj} via {pred}. "
                 "No single answer is possible.")
_LEXIKON_EN = {"beneficial", "owner", "of", "registered", "in", "holds",
               "shares", "director", "listed", "operates", "no", "fact", "on",
               "for", "predicate", "this", "pod", "several", "subjects",
               "relate", "via", "single", "answer", "possible", "is", "are"}
_FUNKTIONSWOERTER_EN = {"the", "a", "an", "and", "or", "to", "from", "with",
                        "by", "as", "it", "its", "was", "were", "be"}

_TEMPLATES = {
    1: "Wirtschaftlich berechtigt an {obj} ist {subj}.",
    2: "In {obj} registriert ist {subj}.",
    3: "Anteile an {obj} hält {subj}.",
    4: "Direktor von {obj} ist {subj}.",
    5: "Im {obj} geführt wird {subj}.",
    6: "Betreiber von {obj} ist {subj}.",
}

_NO_MATCH_TPL = ("Zu {obj} liegt in diesem Pod kein Fakt zum Prädikat "
                 "{pred} vor.")
_AMBIGUOUS_TPL = ("Zu {obj} liegen mehrere Subjekte zum Prädikat {pred} vor. "
                  "Eine eindeutige Antwort ist nicht möglich.")

# Freigegebenes Lexikon: Woerter, die eine Antwort enthalten darf, ohne aus
# Subjekt oder Objekt zu stammen. Jede Erweiterung ist eine bewusste
# Vergroesserung der Angriffsflaeche und gehoert ins Review.
_LEXIKON = {
    "wirtschaftlich", "berechtigt", "registriert", "anteile", "hält", "direktor",
    "geführt", "betreiber", "liegt", "liegen", "pod", "diesem", "kein", "fakt",
    "prädikat", "vor", "mehrere", "subjekte", "eindeutige", "antwort", "nicht",
    "möglich", "ist", "hat",
}

_FUNKTIONSWOERTER = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem",
    "einen", "und", "oder", "in", "an", "zu", "zum", "zur", "von", "vom", "für",
    "mit", "auf", "im", "am", "als", "ist", "sind", "war", "wird", "werden",
    "es", "sich", "auch", "nur", "wurde", "worden", "über", "vorhanden",
}

_TOKEN = re.compile(r"[\wÄÖÜäöüß]+", re.UNICODE)


def _inhaltsbegriffe(text: str, fkt: set | None = None) -> set[str]:
    # Zahlen werden bewusst MITgeprueft: Erfundene Jahreszahlen und Betraege
    # sind genau die Halluzinationen, auf die es hier ankommt.
    stop = _FUNKTIONSWOERTER if fkt is None else fkt
    return {t.lower() for t in _TOKEN.findall(text or "") if t.lower() not in stop}


def pruefe_ableitbar(antwort: str, *, subjekt: str | None, objekt: str,
                     praedikat: str, lang: str = "de") -> tuple[bool, set[str]]:
    """Jeder Inhaltsbegriff der Antwort muss aus der Eingabe oder dem
    freigegebenen Lexikon stammen. Liefert (ok, unbelegte Begriffe)."""
    lex = _LEXIKON_EN if lang == "en" else _LEXIKON
    fkt = _FUNKTIONSWOERTER_EN if lang == "en" else _FUNKTIONSWOERTER
    erlaubt = (_inhaltsbegriffe(subjekt or "", fkt) | _inhaltsbegriffe(objekt, fkt)
               | _inhaltsbegriffe(praedikat.replace("_", " "), fkt) | lex)
    unbelegt = _inhaltsbegriffe(antwort, fkt) - erlaubt
    return (not unbelegt), unbelegt


def adapter_b(status: str, subjekt: str | None, predicate_id: int, objekt: str,
              llm=None, lang: str = "de") -> tuple[str, list[str]]:
    """(Status, Subjekt) -> Antworttext. `llm` ist der austauschbare Slot fuer
    ein lokales Sprachmodell; ohne ihn greifen die Vorlagen.

    Liefert (Text, Warnungen)."""
    pred = PREDICATES[predicate_id]
    en = lang == "en"
    if status == "NO_MATCH":
        vorlage = (_NO_MATCH_EN if en else _NO_MATCH_TPL).format(
            obj=objekt, pred=pred)
    elif status == "AMBIGUOUS":
        vorlage = (_AMBIGUOUS_EN if en else _AMBIGUOUS_TPL).format(
            obj=objekt, pred=pred)
    else:
        from i18n import praedikate as _labels
        lab = _labels("en" if en else "de").get(pred, pred.replace("_", " "))
        vorlage = f"{subjekt} {lab} {objekt}."

    if llm is None:
        return vorlage, []

    kandidat = llm(status=status, subject=subjekt, predicate=pred, object=objekt)
    ok, unbelegt = pruefe_ableitbar(kandidat, subjekt=subjekt, objekt=objekt,
                                    praedikat=pred, lang=lang)
    if ok:
        return kandidat, []
    return vorlage, sorted(unbelegt)


# ---------------------------------------- Austauschbarer Sprachmodell-Slot
def _llm_brav(status, subject, predicate, object):
    """Formuliert ausschliesslich aus dem Uebergebenen — wie ein sauber
    trainierter Adapter B."""
    if status == "MATCH":
        return f"{subject} ist {predicate.replace('_', ' ')} {object}."
    return f"Kein Fakt zu {object} vorhanden."


def _llm_erfindend(status, subject, predicate, object):
    """Ein Modell, das ausschmueckt. Genau dieser Fall bleibt in Whitepaper
    v0.1 unentdeckt: Die Firewall haelt Fakten fern, nicht Erfindungen."""
    if status == "MATCH":
        return (f"Der schwedische {subject} kontrolliert {object} seit 2016 "
                f"über eine Kette von Briefkastenfirmen in Zypern.")
    return f"Zu {object} ist nichts bekannt, vermutlich ein Scheinunternehmen."


LLM_REGISTRY = {"brav": _llm_brav, "erfindend": _llm_erfindend}
