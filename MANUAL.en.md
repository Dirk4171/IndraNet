# IndraNet — Manual

Version 1.0 · For reporters, researchers and newsroom technologists

---

## What this tool does

IndraNet manages what your research **claims**, and where every claim comes
from. It answers questions about your holdings, shows the evidence beside
the answer, keeps track of what is multiply sourced and what is contested,
and lets you match against other newsrooms without them learning what you
are working on.

It is not a document search tool. It manages the assertions you have drawn
out of documents. The documents themselves stay in your encrypted
filesystem; IndraNet holds the reference and the checksum.

---

## 1. Setup

Requires Python 3.11 or newer.

```bash
pip install cryptography numpy
cd indranet
python3 test_indranet.py     # 62 tests, all should pass
python3 demo.py              # walkthrough of the workflow
```

Start the interface:

```bash
python3 cli.py --lang en serve ./my-investigation.db --open
```

The server binds **to 127.0.0.1 only**. That is deliberate: a tool handling
source material does not belong on a network unless someone decides so
explicitly. To run it on the newsroom network, set `--host` — and secure
access yourself.

---

## 2. The six views

### Ask

Answer on the left, evidence on the right. That is not a layout whim: answer
and evidence come from two separate routes through the system, and you
should see both at once.

Question forms the parser understands (examples):

| Question | Finds |
|---|---|
| Who owns *X*? | beneficial owners |
| Who is director of *X*? | directors |
| Who holds shares in *X*? | shareholders |
| What is registered in *X*? | companies registered there |
| Who operates *X*? | operator of a vessel |

If the parser recognises no predicate it says so — and issues **no** query.
A guessed question produces a correctly retrieved but wrong answer; that is
the more dangerous failure.

Click a fact to load its evidence on the right.

### Verify

Four worklists. This view is the actual workplace before publication:

- **Contested** — two sources say incompatible things. Resolve before
  publishing.
- **Single-sourced** — rests on one source. Corroborate.
- **Retracted** — the basis has been withdrawn.
- **Corroborated** — at least two independent sources.

At the top sits the share of corroborated facts. That is the most honest
single number about the state of an investigation.

### Entities

Merge suggestions. "Mueller Handels GmbH" and "Müller Handels GmbH" are
probably the same company — but **probably** is not enough. IndraNet merges
nothing on its own.

Every decision requires a reason. It goes into the log, and when someone
reviews the investigation that is exactly where you will be asked.

Watch for the red warning on differing legal forms: "Nordkap Shipping AS" is
Norwegian, "AB" is Swedish. Two companies.

### Network

Connections between two entities. Under each path stands the **weakest
link** — a path across a single-sourced edge is only as load-bearing as that
edge.

### Sources

All documents with their protection level and the number of assertions drawn
from them. Before any retraction you see here how many facts are affected
and how many fall **with no substitute**, meaning they have no second source.

A retraction cannot be undone and requires a reason.

### Import

Paste CSV content, give the mapping, choose the protection level. Every row
becomes an assertion with a locator. Facts without evidence do not arise
here.

---

## 3. Importing data

### Mapping

One line per rule, of the form `subject:predicate:object`:

```
owner:beneficial_owner_of:company
director:director_of:company
company:registered_in:seat
```

Columns may be composed:

```
owner:beneficial_owner_of:{company} {legal_form}
```

This is nearly always necessary. Registries keep company name and legal form
in separate columns; without joining them you get "Mare Liberum" and "Mare
Liberum Ltd." as two entities.

### Predicates

| Predicate | Meaning | One value per subject? |
|---|---|---|
| `beneficial_owner_of` | is beneficial owner of | no |
| `registered_in` | is registered in | **yes** |
| `holds_shares_in` | holds shares in | no |
| `director_of` | is director of | no |
| `listed_in` | is listed in | no |
| `operates_vessel` | operates | no |

The last column decides when a contradiction is reported. A company has
several directors — that is an enumeration. It has one seat — two entries
are a contradiction.

### From the command line

```bash
python3 cli.py --lang en import ./investigation.db registry.csv \
  --map 'owner:beneficial_owner_of:{company} {legal_form}' \
  --map '{company} {legal_form}:registered_in:seat' \
  --titel "Company registry Q3" \
  --quelle "Oslo registry" \
  --stufe OEFFENTLICH \
  --von s.kern@newsroom
```

**`--quelle` matters more than `--titel`.** IndraNet uses that field to
decide whether two pieces of evidence are independent. Two extracts from the
same registry should carry the same source, otherwise the tool shows a
corroboration that is not one.

---

## 4. Reading the evidential state

| Mark | Meaning | What to do |
|---|---|---|
| **Corroborated** | two or more independent sources | load-bearing |
| **Single-sourced** | one source | corroborate before publishing |
| **Contested** | sources contradict each other | resolve |
| **Retracted** | basis withdrawn | do not use |

The tally marks beside the label count independent sources — one notch per
source, as in a notebook.

---

## 5. Protection levels and roles

| Level | For | Evidence visible from role |
|---|---|---|
| `OEFFENTLICH` | registries, filings, court records | Guest |
| `INTERN` | own unpublished research | Journalist |
| `VERTRAULICH` | background interview, source known | Editor |
| `WHISTLEBLOWER` | leak, insider, anonymous handover | Admin |

A fact is always as protected as its most protected piece of evidence — even
if the same fact is publicly recorded elsewhere.

**Withheld evidence appears as a black bar.** It does not disappear. You see
that further evidence exists and at which level; on click the reason, never
the content. Hiding its existence would give a false picture of the
evidential state.

Whistleblower material never leaves the pod automatically. Releasing it into
a shared space requires the Admin role **and** two people.

---

## 6. Retracting a document

If a source turns out to be unusable — forged, withdrawn, misattributed:

1. Open **Sources**.
2. The document shows how many facts are affected and how many fall with no
   substitute.
3. Enter a reason, retract.

Afterwards every assertion derived from it is invalid. Facts resting only on
that document show **Retracted**. Edges that ran only through it disappear
from all paths — a connection that existed only via a withdrawn source is
not a connection.

---

## 7. Working with other newsrooms

### Signal

You ask whether another newsroom holds anything on an entity. What travels
is **not the name** but a blinded curve point. The far side answers without
learning what you asked.

The reply names a class — `open`, `editorial`, `confidential`,
`whistleblower_high` — and whether they are open to talking. No name, no
fact, no document.

**What the far side does learn:** that you asked, and how often. That is the
price of rate limiting, which prevents anyone from working through name
lists.

### Clearing

If both sides agree, they open an ephemeral shared space. What travels is
not the document but the assertion, with its evidential state and checksum.
Afterwards the space is destroyed; an evidence chain signed by both sides
remains.

---

## 8. Command line

```bash
python3 cli.py --lang en serve    ./db --open
python3 cli.py --lang en import   ./db file.csv --map … --titel … --quelle … --von …
python3 cli.py --lang en ask      ./db "Who owns X?"
python3 cli.py --lang en verify   ./db
python3 cli.py --lang en evidence ./db <fact_id> --rolle ADMIN
python3 cli.py --lang en path     ./db "A" "B"
python3 cli.py --lang en review   ./db
python3 cli.py --lang en stats    ./db
python3 cli.py demo
```

---

## 9. Security notes

**The container is encrypted, memory is not.** While the pod is open the
plaintext sits in RAM.
IndraNet protects against a curious language model and against the
federation — not against someone who walks off with your laptop.

**The navigator must run locally.** Your question reveals the research
target and necessarily crosses to the untrusted side. A cloud model here
defeats source protection entirely, however clean everything beneath it is.

**Nothing loads from elsewhere.** The interface uses no external fonts,
scripts or images. If you see network traffic when opening it, something is
wrong.

**A retraction is final.** There is no undo.

**Check the resolver fingerprint before the first exchange.** If it differs
between two pods, IndraNet refuses the connection. That is correct:
differing normalisation produces silent misses nobody notices.

---

## 10. When something does not work

**"No predicate recognised"** — The parser does not understand the question
form. Phrase it closer to the examples in section 2, or use the **Network**
view.

**Answer is `NO_MATCH` although the fact is there** — Almost always a
spelling variant. Check **Entities** for an open merge suggestion.

**Two pieces of evidence but "single-sourced"** — Both carry the same
`--quelle`. Independence is decided by that field, not by the title.

**A fact suddenly reads "Contested"** — A second source gives a different
value for a predicate that allows one value per subject. Look at both pieces
of evidence; that is exactly what the mark is for.
---

## 11. External sources

The **External** view checks your holdings against public datasets —
sanctions lists, politically exposed persons, news streams.

### Matching runs on your device

This is the key point. IndraNet downloads the third-party dataset and
compares locally. **Your name list does not leave the pod.** Sending
individual names to a screening service instead reveals the research target
— at exactly the point where it is cheapest to lose.

### Fetch the corpus

```bash
# Sanctions and PEPs (OpenSanctions bulk data, no key required)
python3 cli.py --lang en fetch ./investigation.db opensanctions

# News or event stream
python3 cli.py --lang en fetch ./investigation.db events --von <URL-or-file> \
  --name "World Monitor" --profil worldmonitor
```

The first OpenSanctions fetch takes several minutes; the dataset holds
several hundred thousand entities. One fetch per day is enough.

### Screen

```bash
python3 cli.py --lang en screen ./investigation.db opensanctions --von <file>
```

Output:

```
Anders Holm  ←  Anders Holm  [OpenSanctions] politisch exponiert  (1.00)
Nordkap Shipping AS  ←  Nordkap Shipping AS  [OpenSanctions] sanktioniert  (1.00)
```

### Source health

```bash
python3 cli.py --lang en sources ./investigation.db
```

| State | Meaning |
|---|---|
| `OK` | less than a week old |
| `ALT` | more than a week old |
| `VERALTET` | more than a month old — refetch before publishing |
| `FEHLER` | last fetch failed, reason shown |
| `NIE` | never fetched successfully |

An investigation resting on a `VERALTET` dataset is not wrong, but you
should know it before someone else notices.

### Findings are not facts

A sanctions hit appears in the list. It does **not** automatically become an
assertion in your base. Adoption is a separate step requiring your decision
— otherwise you import other people's errors as your own facts, and your
evidence chain points at a list instead of a document.

### Licensing

OpenSanctions data is CC-BY-NC: free for editorial use, attribution
required, commercial use requires a licence. For event sources, check the
respective operator's terms.
---

## 12. Creating a pod, accounts, passphrase

### Creating

```bash
python3 cli.py --lang en init ./investigation.vault --benutzer s.kern \
  --anzeige "Sabine Kern"
```

You will be asked for a passphrase (at least twelve characters) and a
password for the first account. The first account is always ADMIN.

**There is no recovery.** Without the passphrase the pod cannot be read —
that is the point. Note it somewhere that is not next to the computer.

For two-factor, add a key file:

```bash
python3 cli.py --lang en init ./investigation.vault --benutzer s.kern \
  --neue-schluesseldatei /media/stick/indranet.key
```

Every subsequent access then needs `--schluesseldatei
/media/stick/indranet.key`. Keep the stick away from the computer,
otherwise the separation is pointless.

### Accounts

```bash
python3 cli.py --lang en user ./investigation.vault list
python3 cli.py --lang en user ./investigation.vault add --benutzer j.weber \
  --rolle JOURNALIST
python3 cli.py --lang en user ./investigation.vault role --benutzer j.weber \
  --rolle LEITUNG
python3 cli.py --lang en user ./investigation.vault passwd --benutzer j.weber
```

Only ADMIN may create accounts and change roles. The last ADMIN cannot
demote themselves — the pod would become unusable.

### Changing the passphrase

```bash
python3 cli.py --lang en vault ./investigation.vault passwd
python3 cli.py --lang en vault ./investigation.vault info   # no passphrase
```

**Older copies of the container remain readable with the old passphrase.**
A change protects only the current state; destroy old backups.

### Signing in

After `serve` a sign-in form appears. Your role determines which evidence
you see — it is no longer a dropdown but comes from your session. A session
expires after eight hours.

After five failed attempts the account is locked for five minutes. All
attempts are logged; repeated failures are the first sign of an access
attempt.

### A pod without accounts

If you create no account, the pod runs as a single workstation with full
rights. That is intentional: whoever holds the file and the passphrase owns
the pod anyway. Once the first account exists, sign-in applies to everyone.

Conversely: **the account layer does not protect against someone who has
the container and the passphrase.** It governs collaboration among several
people. For separate trust domains you need separate pods.
---

## 13. Recording facts by hand

Most facts do not come from tables but from reading a document or after an
interview. That is what the **Record** tab is for.

The sequence is always the same: **evidence first, then the assertion.** No
fact arises without evidence — here as in the import.

### Creating evidence

On the right, three kinds:

**File** — for PDFs, spreadsheets, scans. You choose the file and the
browser computes its checksum. **The file is not uploaded** — it does not
even leave your machine towards your own server. The pod stores the
filename, the checksum and the storage location you enter.

Why only the checksum? A leak of millions of files belongs in your
encrypted filesystem, not in the fact store. The checksum is enough to
prove later that a document produced is the same one the investigation
rested on.

Enter under **Storage location** where the file lives — otherwise you will
not find it again in six months.

**Note** — for your own records: background interview, observation, phone
call. The note text itself is the evidence and is held via its checksum.
Change the note later and the identifier changes; the old evidence chain
then points nowhere instead of silently referring to altered text.

**Other** — anything without a file: a registry enquiry by phone, a web
page, an authority's statement.

### Recording the assertion

On the left, once evidence is selected:

| Field | Example |
|---|---|
| Subject | `Politiker Lindqvist` |
| Relation | `is beneficial owner of` |
| Object | `Svensson Family Trust` |
| Locator | `p. 14, line 7` |
| Quote | optional, the passage verbatim |

**The locator matters most.** "p. 14, line 7" is evidence; "somewhere in
the PDF" is not. When someone challenges you before publication, that is
exactly what they ask for.

After saving, the evidence stays selected — you can record several
assertions from the same document in a row. Below are the most recent ones
with their evidential state.

### Hand-recorded and imported facts mix

A fact recorded by hand and the same fact from a CSV import are the same
fact — if the **source** differs, it counts as multiply sourced. So you can
record a claim from a leak and have a registry import corroborate it later.

### What not to do

Do not invent a new source for every assertion. The **source** field
decides whether two pieces of evidence count as independent. Two pages from
the same leak are one source, not two.
---

## 14. Keeping evidence documents in the pod

A reference to `D:\Files\leak.pdf` is not protection, it is a note. If you
have no encrypted newsroom server — and most people do not — keep the
evidence **in the pod**.

### How

**Record** tab, evidence type **File**. The checkbox **"Store the document
in the pod (encrypted)"** is set by default. Choose the file, enter title
and source, **Create evidence**.

The file is encrypted into a folder next to your node:

    investigation.vault          the node itself
    investigation-belege\        the encrypted documents

They belong together. **Always back up both** — the node alone does not
contain the documents; the evidence folder alone is useless without node
and passphrase.

### What gets encrypted

Everything. Content, original filename and file type. The filenames in the
evidence folder are opaque strings. Anyone seeing the folder learns the
number of documents and their approximate size — nothing more.

The key is derived from your passphrase but is **not** the same as the
node's key. Two separate keys from one passphrase.

### Viewing a document again

Ask a question, click the fact, then **Open document** in the evidence
panel on the right. Access runs through the Indra jewel: whoever may not
see the evidence does not get the file either.

### When to reference instead

Uncheck the box. Sensible for:

- **Large corpora.** A leak of ten thousand files belongs on an encrypted
  drive, not in the evidence folder.
- **Existing newsroom infrastructure.** If an encrypted server exists, the
  documents should stay there.
- **Files over 300 MB.** The web interface is not made for that.

With "reference only" IndraNet stores the checksum and the storage
location. The checksum is enough to prove later that a document produced is
the same one — but you must keep the file safe yourself.

### Backups

The evidence folder grows with the number of documents. Because everything
is encrypted, you can back it up to a network drive or cloud storage —
without the passphrase it is worthless, including to the provider.

One warning: the passphrase is then the only protection for all of your
material. Lose it and everything is lost; pass it on and everything is
open.
---

## 15. Correcting mistakes

Typos, wrong field, source withdrawn — it happens. Each evidence entry
offers three options.

### Correct

For typos and wrongly entered fields. Empty fields stay unchanged. The
previous version goes into the correction log.

### Retract

When a **claim turns out to be wrong** or a source is withdrawn. The
assertion stays visible and counts as retracted.

This matters: removing a false claim without trace falsifies the evidential
record retroactively. A fact that briefly counted as corroborated and was
then withdrawn must show that.

A fact only shows as retracted once **all** assertions carrying it are
retracted. As long as one independent source stands, the fact stands.

### Discard

Only for misfires: wrong evidence selected, entered twice, nonsense typed.
The content disappears entirely.

The correction log records **that** a deletion happened, by whom and why.
Without that trace the evidence chain could be doctored after the fact —
exactly what a tool for evidence must not allow.

All three require a reason.

---

## 16. Backing up

The status bar shows how long ago the last backup was. Clicking **back up
now** packs node and evidence folder into a dated file:

    investigation-sicherung-2026-08-28_1430.zip

It contains the vault, all evidence documents, a manifest with checksums
and restore instructions.

**The content is encrypted.** The file may go to a network drive, an
external disk or cloud storage — without the passphrase it is worthless,
including to the provider.

From the command line:

```bash
python3 cli.py --lang en backup ./investigation.vault
python3 cli.py --lang en backup ./investigation.vault --ziel E:\Backup\
```

IndraNet does not delete old backups. A tool that removes research states
on its own is not one — tidying up is your job.

---

## 17. Exporting the evidence chain

Click **Export chain** in the evidence panel. You receive a readable
document with:

- the assertion and its evidential state
- all independent sources
- per item: source, locator, protection level, recorder, SHA-256
- the verification log
- a checksum over the whole chain

This is what you hand to legal counsel or the editor-in-chief.

**The export follows your role.** As a journalist, whistleblower evidence
appears as *"Withheld evidence"* with a note that it exists. As an admin it
is open. So choose deliberately who gets which export.

**Document contents are not included**, only checksums. Anyone verifying
the chain needs the originals — that is the point.

Several facts in one document, from the command line:

```bash
python3 cli.py --lang en export ./investigation.vault f:abc... f:def... \
  --rolle ADMIN --ziel dossier.md
```

Output is Markdown. To hand it on as PDF, open it in an editor like Typora
or convert it with Pandoc.
---

## 18. Which files IndraNet handles

**IndraNet can store any file** — encrypted, regardless of format. It can
**read** the following:

| Group | Formats |
|---|---|
| Text | txt, md, log, rst, ini, yaml, srt, vtt |
| Tables | csv, tsv, **xlsx**, **ods** |
| Documents | **docx**, **odt**, rtf, html, xml, json |
| Presentations | **pptx**, **odp** |
| Email | eml, mbox |
| PDF | pdf (with a text layer) |

Everything except PDF works without extra software — the modern Office
formats are ZIP archives containing XML.

### What is not read

**Legacy binary formats** (.doc, .xls, .ppt before Office 2007) and
**Outlook .msg**. Open them once in LibreOffice and save as .docx or .xlsx.

**Scanned pages without a text layer.** A PDF from a scanner contains
images, not text. IndraNet says so when storing it — it does not pretend
the document is empty. Such cases would need OCR, which is not built in.

In both cases the file **is still stored encrypted** and can be opened. You
just cannot search it.

### Locators, not blobs of text

That is the actual point. Every text section found carries its position:

| Format | Locator |
|---|---|
| PDF | `S. 14` |
| Spreadsheet | `Blatt "Beteiligungen", Zeile 42` |
| Word, ODT | `Absatz 17` |
| Presentation | `Folie 8` |
| Email | `Nachricht 3, Text` |
| JSON | `$.firma.eigentuemer` |

When you search a piece of evidence for a name, you get the locator plus
the surrounding sentence — and can take both into the record with one
click. "p. 14, line 7" is evidence; "somewhere in the PDF" is not.

---

## 19. Network view

**Network** tab, **Network view**. Enter an entity, choose a depth, click
**Draw**.

This is the digital pinboard with red threads. The **edge colour shows the
evidential state**: green corroborated, amber single-sourced, red
contested, grey dashed retracted.

You see at a glance which parts of your network hold and which hang on a
single source. A node further out is only as load-bearing as the edges
leading to it.

Clicking a node makes it the new centre — that is how you work through the
web.

The graph is drawn without any third-party library and loads nothing. Above
roughly two hundred nodes the display gets crowded; reduce the depth then.

---

*IndraNet is open source. The architecture is described in the whitepaper,
including what it does not do.*
