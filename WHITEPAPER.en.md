# IndraNet

**A federated research network for investigative journalism**
Architecture whitepaper · Version 1.0 · July 2026

---

## Summary

IndraNet lets newsrooms match scattered datasets for hidden connections
without exchanging raw data. Three properties set it apart from centralised
analysis platforms:

**Source protection is technically enforced, not organisationally promised.**
The language model runs in its own process and reaches the fact store only
through an interface with a closed schema. It cannot invent facts because it
knows none — and whatever it phrases is checked against its own input.

**The assertion is the primary object, not the fact.** A fact is derived: the
bundle of all assertions carrying the same claim. This makes representable
what investigative work actually consists of and what fact-centric systems
cannot express — contradicting sources, corroboration, and the retraction of
a document together with everything that rested on it.

**Federated matching does not reveal the research target.** What travels
across the wire is a blinded curve point. The far side answers the query
without learning what was asked.

---

## 1. The problem

Palantir Gotham and comparable platforms pool data into central data lakes.
That may work for government agencies; for investigative journalism it is
unusable. Whistleblower material, confidential background notes and
unpublished newsroom research must not converge into an infrastructure a
single entity controls.

At the same time newsrooms need exactly the capability such platforms
provide: recognising that a name has already surfaced in another house.
IndraNet resolves that contradiction.

## 2. The counter-image

In Buddhist cosmology an infinite net hangs above the palace of the god
Indra. At every knot sits a jewel reflecting all the others — their light,
not their substance. There is no centre.

Every pod is a jewel: an autonomous, local holding. Every signal is a
reflection: confirming a connection without surrendering the source.

## 3. Design principles

1. **Data stays with its owner**, physically and legally.
2. **No language model reaches facts.** The boundary is a process, not a
   diagram.
3. **No assertion without evidence.** Facts without a locator never arise.
4. **Contradiction is a result, not an error.**
5. **Humans decide, machines suggest** — for every entity merge.
6. **Nothing loads from elsewhere.** The tool works locally, without
   external resources.

## 4. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Indra node (pod)                     │
│                                                          │
│   Web interface ──┬──────────────────┬── Command line    │
│                   │                  │                   │
│   ┌───────────────▼──────┐    ┌──────▼────────────────┐  │
│   │  Navigator (process) │    │  Indra jewel (policy) │  │
│   │  parser + templates  │    │  levels, releases     │  │
│   └───────────┬──────────┘    └──────┬────────────────┘  │
│               │ FIREWALL              │                   │
│   ┌───────────▼───────────────────────▼────────────────┐  │
│   │  Store: assertions over SQLite                     │  │
│   │  Verification · entity resolution · graph          │  │
│   └────────────────────────┬───────────────────────────┘  │
│   ┌────────────────────────▼───────────────────────────┐  │
│   │  Federation: Indra signal (PSI) · Axon (transport) │  │
│   └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

The two exits are strictly separated:

```
Question ─► Navigator ─[FIREWALL]─► Store ─► status + answer ─► text
                                      │
                                   fact_id  (never crosses the firewall)
                                      │
Interface ────[Indra jewel]───────────┴──► evidence, locator, checksum
```

## 5. The assertion model

The central design decision.

```
Assertion = document D claims (subject, predicate, object),
            recorded by person P on day T, at locator F.
```

A **fact** is derived from these: the bundle of all assertions sharing
(subject cluster, predicate, object cluster). Its **evidential state**
follows from the assertions that carry it:

| State | Condition |
|---|---|
| `BESTAETIGT` (corroborated) | two or more independent sources |
| `EINFACH_BELEGT` (single-sourced) | exactly one source |
| `UMSTRITTEN` (contested) | predicate allows one value per subject, sources disagree |
| `WIDERRUFEN` (retracted) | every carrying assertion withdrawn |

Independence is determined by the document's `source` field. Two extracts
from the same registry count as one source.

### Why this inversion

**Sources contradict each other.** "Oslo registry says British Virgin
Islands, Orbis says Panama" is the normal case. A fact-centric system cannot
represent it — it reports ambiguity and leaves open whether the sources
disagree or the store is noisy. IndraNet distinguishes the two:
`registered_in` allows one seat per company, so that is a contradiction.
`director_of` allows several, so that is an enumeration.

**Documents get retracted.** If a handover turns out to be forged, every
assertion derived from it must become invalid — and before the retraction it
must be answerable what falls with no substitute. Both are queries here.

**Corroboration is the most important distinction a newsroom draws.** It
belongs in the model, not in the researcher's head.

### Why SQLite and not a vector store

An earlier version of this architecture stored facts as superposed random
vectors (binary spatter codes, D=20,000). At 40,000 facts:

| | Vector store | SQLite |
|---|---|---|
| Point query | 1.16 ms | 0.022 ms |
| Path across 6 hops | 6 ms | 0.1 ms |
| Disk | 116 MB | 14 MB |

On top of that: capacity limits, a threshold requiring calibration, and a
full reindex after every merge — none of which an ordinary table has. The
often-cited advantage that a superposed vector cannot be enumerated without
the right question does not survive implementation: fast queries require a
candidate list per shard, and the name store must hold plaintext anyway.
Encryption at rest protects better and is ten lines of code.

The determinism on which trust rests does not come from the representation.
It comes from no language model being involved in retrieval at all.

## 6. The firewall

The navigator runs as its own process with its own `__main__`. Transport is
line-delimited JSON over stdin/stdout — **no pickle**, because its
deserialisation is code execution, and a compromised navigator side could
use it to defeat the entire boundary.

The schema is closed in both directions:

```
inbound    { v, req_id, predicate_id (from a closed vocabulary), object }
outbound   { v, req_id, status, subject }
```

Everything else is rejected — arrays, lists, bytes, nested dicts, extra
fields. Three rules deserve mention:

**No similarity scores outbound.** Numeric scores are a side channel;
probing with chosen objects allows inferences about the holdings.

**No evidential state outbound.** The navigator phrases the answer; whether
it is single- or multiply-sourced concerns the interface, not the model.

**No subject on `NO_MATCH` or `AMBIGUOUS`.** A "best candidate" would be a
claim the store cannot stand behind.

### The navigator needs no fine-tuning

An earlier version specified two LoRA adapters. Both are dispensable. The
phrasing side may, thanks to the derivability check, only use words from its
own input — a template does the same at zero risk. The extraction side is
semantic parsing into a closed vocabulary; a local model with
grammar-constrained decoding handles that without training, and does so
structurally rather than by training: what the grammar disallows cannot be
emitted.

### Derivability check

The firewall stops the navigator from **knowing** facts. It does not stop it
from **inventing** them: from "Svensson Family Trust" a language model will
happily produce "the Swedish Svensson Family Trust, since 2016". Every
content word in the answer is therefore checked against whether it derives
from the subject, object, predicate label, or an approved lexicon. If not,
the template takes over and the incident is logged.

This is deliberately strict, and one consequence deserves stating plainly:
**fluency and verifiability are in direct tension.** Every additional
phrasing freedom reopens exactly the hallucination surface the firewall
exists to close.

## 7. The evidence path

Evidence never reaches the language model. It reaches the journalist by a
second route that runs entirely on the trusted side, governed by the Indra
jewel.

Withheld evidence is not concealed but redacted: the researcher sees **that**
further evidence exists, and at which protection level — not what it says.
Hiding its existence would produce a false picture of the evidential state.

The **evidence chain** is machine-readable and contains checksums, not
content. Anyone verifying it needs the original documents. That is the point.

## 8. Indra jewel: protection levels and roles

| Level | Example | Evidence visible from |
|---|---|---|
| `OEFFENTLICH` (public) | company registry, filings, court records | `GAST` |
| `INTERN` (internal) | own unpublished research | `JOURNALIST` |
| `VERTRAULICH` (confidential) | background interview, source known by name | `LEITUNG` |
| `WHISTLEBLOWER` | leak, insider, anonymous handover | `ADMIN` |

The fourth level is not an intensification of the third but a different
category: a person's physical safety is at stake. It never leaves the pod
automatically, and releasing it into a collaboration space requires `ADMIN`
**and** two people.

Every decision of the jewel is logged, including refusals.

## 9. Entity resolution

Two keys rather than one — because a single key forces an impossible choice:

**Strict key.** Conservative, deterministic, stateless. Unifies Unicode
form, case, whitespace, legal-form spelling and name order. Creates the
cluster.

**Block key.** Aggressive: diacritics, digraphs, legal form and order are
flattened. **Never** creates a cluster, only candidate pairs for human
review.

So "Müller" and "Mueller" collide in the suggestion list without "Goethe"
and "Gothe" silently becoming one company. Legal forms are **unified, not
stripped**: "Nordkap Shipping AS" (Norway) and "Nordkap Shipping AB"
(Sweden) are different companies, and the suggestion carries a warning to
that effect.

Confirmed merges are an `UPDATE` on a cluster pointer. No reindexing, no
rebuild, effective immediately.

**Federation lock.** All pods must normalise identically, otherwise matching
fails silently. `fingerprint()` hashes every rule table; two pods compare it
before the first exchange and refuse on mismatch. A loud failure beats
half-working hits.

## 10. Indra signal

An earlier version broadcast the search term in the clear. That tells every
participant — including a compromised one — the research target, weeks
before publication. Hashing is not enough; name dictionaries are trivially
enumerable.

Instead, an oblivious PRF over P-256:

```
1. Alice:  P = hash_to_curve(entity), random r
           sends r·P
2. Bob:    replies b·(r·P)              ← learns nothing about P
3. Alice:  computes r⁻¹·(b·r·P) = b·P
           checks b·P against Bob's Bloom index
```

**Hash-to-curve is necessary.** The convenient route `P = H(x)·G` is a total
break: Alice asks once with `H(x)=1`, receives `b·G`, and can then compute
`b·H(x)·G` for any entity herself — a dictionary attack on Bob's entire
holdings without asking him again. Hence try-and-increment on the
x-coordinate, where the discrete logarithm is known to nobody.

**Classification without a follow-up question.** A signal should report how
sensitive the far side's material is — but Bob does not know what was asked.
The resolution: **one Bloom index per protection level.** Alice checks her
PRF value against all of them and reads the level off the hit. Levels the
policy blocks are never indexed at all; for the federation they do not
exist.

**Rate limiting** is part of the protocol, not the operating manual. Without
it Alice could work through name lists.

Measured: 1.3 ms per query, index over 500 entities in 0.31 s and 1.8 KB.

## 11. Indra clearing

An ephemeral, isolated space for two newsrooms working together. It holds
only what both sides have explicitly released.

What travels is not the fact but the **assertion** — with document
reference, evidential state and checksum, without the document content. The
far side therefore sees what a claim rests on and how well it holds, without
receiving the source material.

On closing, the store is discarded. What remains is an evidence chain signed
by both sides with Ed25519 and carrying no raw data — verifiable even if one
side later denies having taken part.

## 12. Axon transport

Ed25519 as long-lived identity, X25519 per session, AES-256-GCM for payload,
HKDF for derivation. Three points separate encryption from security:

**Replay protection.** Every envelope carries a strictly monotonic counter.

**Forward secrecy.** Ephemeral session keys signed by the long-lived
identity. Seizing the identity key later does not retroactively decrypt
captured traffic — for journalists that is the standard case, not the
exception.

**Traffic analysis.** No coordinator that sees everything. Individual
delivery to each peer, envelopes padded to a 512-byte grid so message length
does not reveal message type.

New pods join through vouching in a web of trust: no certificate authority,
but the form of trust that applies among journalists anyway.

## 13. Verification as a workflow

Palantir's product is not the database but what investigators do with it
eight hours a day. The journalistic counterpart is verification, not
retrieval. IndraNet maintains four worklists:

- **Contested** — sources disagree
- **Single-sourced** — corroborate before publishing
- **Retracted** — basis withdrawn
- **Corroborated** — carried independently more than once

Plus the dependency question: *which facts fall if this document falls, and
which fall with no substitute?* That question must be asked before every
retraction and is practically unanswerable in a fact-centric model.

## 14. What has been measured

62 tests across all modules, among them:

- Evidential state: one source → `EINFACH_BELEGT`, two independent →
  `BESTAETIGT`, the same source twice does not count double
- Contradiction only for predicates allowing one value per subject, and only
  in the query direction where it shows
- Retraction covers all derived assertions and removes the edges from all
  paths
- Merging takes effect immediately without reindexing
- The firewall rejects arrays, extra fields, `doc_id`, `fact_id`, evidential
  state, and a subject on `NO_MATCH`
- PSI: curve constants derived computationally and cross-checked, hits and
  misses correct, rate limiting effective
- Axon: replay rejected, federation lock effective
- Interface: no external resources, evidence role-dependent, whistleblower
  material delivered redacted

## 15. Limits

**The extraction parser is a pattern table.** The interface is in place;
constrained decoding is not wired up.

**Anonymity towards the far side.** Bob does not learn *what* Alice asks —
but *that* she asks. That is the price of rate limiting. The way out is
anonymous credentials over a mixnet path.

**Alias divergence between pods.** If pod A merges "Mueller" into "Müller"
and pod B does not, the two miss each other when matching. The three ways
out — send aliases along, share aliases, accept misses — all have costs, and
none has been chosen.

**Memory during operation.** The container on disk is encrypted (section
17), but while the pod is open the plaintext sits in memory. Python cannot
guarantee nothing reaches the swap file. For material where this matters,
the pod belongs on a system with encrypted swap.

**Entity resolution handles names only.** In practice registration number,
address and date of birth are the stronger signals.

**The clearing discards its store** but cannot guarantee nothing remains in
memory. Real protection requires a process with locked memory and encrypted
swap.

## 16. Connecting public datasets

IndraNet is deliberately the other half of a problem whose first half
others solve well. **World Monitor** aggregates the public state of the
world in real time and states itself that it has no private ontology for
internal data. **OpenSanctions** maintains sanctions lists and politically
exposed persons in the FollowTheMoney model. IndraNet holds what your
investigation claims, and how well it is evidenced.

Three rules govern every connector.

### Fetch the corpus, match locally

A screening query to a third-party service reveals whom you are checking.
In a live investigation **the name list is the research target** — exactly
the quantity we protect in the federation with an oblivious PRF. Giving it
away one layer down would be self-defeating.

So: download the corpus once, match on the device. OpenSanctions makes its
bulk data available without login or API key, and the matching service
`yente` is MIT-licensed and self-hostable. Where a service can only be
queried online, matching must be explicitly enabled and is logged.

### Sources age, and that belongs on screen

An investigation resting on a six-month-old registry extract should say so.
Every source records last fetch, last success, data vintage and errors; the
**External** view shows this as `OK`, `ALT`, `VERALTET`, `FEHLER` or `NIE`.

The idea is borrowed from World Monitor, which publishes the state of all
its data contracts — including the broken ones. That is the right posture:
showing only the working sources produces a false picture of where things
stand.

### Findings are not assertions

A sanctions hit is a finding, not a claim. It is displayed and can be
adopted — but a human must adopt it. Automating that imports other people's
errors as your own facts and loses the evidence chain exactly where it
matters most.

The same applies to pulling relationships: by default **both ends** must be
known in the pod. Otherwise a politically exposed person with forty
mandates drags in forty companies nobody asked for.

### Licensing note

The OpenSanctions codebase is MIT-licensed; **the data is not** — it is
CC-BY-NC. For a newsroom that is unproblematic. Anyone selling IndraNet
with a pre-filled dataset needs a data licence. This distinction is easy to
miss and expensive.

## 17. Access control and encryption

Three gaps that would have shown immediately in operation are closed.

### Encrypted vault

The pod file previously sat in the clear. For a tool handling
whistleblower material that was the most serious remaining defect.

The database now lives entirely in memory; only an encrypted container
reaches the disk. Opening decrypts into an in-memory database; saving
serialises, encrypts and writes atomically.

The difference from "encrypt the file afterwards" is decisive: there the
plaintext exists on disk in the meantime — as a file, a WAL journal, a
temporary copy — and survives deletion in freed blocks. Here it never
touches a filesystem.

Key derivation with scrypt (N = 2¹⁷), encryption with AES-256-GCM, header
as additionally authenticated data. Derivation deliberately takes about a
second, making passphrase guessing expensive. Optionally a key file in
addition — knowledge and possession together.

### Accounts instead of a dropdown

The role was a dropdown in the interface: anyone could pick ADMIN. On a
single workstation that was tenable; as soon as two people share a pod the
Indra jewel was toothless — it checked correctly, but nobody checked who
was asking.

The role now comes from the session, not from the request. Passwords
hashed with scrypt, sessions with expiry, lockout after five failed
attempts, identical error message for wrong username and wrong password so
the user list cannot be enumerated. Write operations require at least
JOURNALIST, a retraction at least LEITUNG.

Only now does the four-eyes principle have substance: previously
`freigeber=["a", "b"]` was a list of invented strings. Now it must be two
different, existing accounts.

A pod without accounts still runs as a single workstation with full
rights — whoever holds the file and the passphrase owns it anyway. Once
the first account exists, sign-in is required.

**Limit:** This layer governs collaboration among several people on one
pod, not protection against the holder of the vault — the accounts live in
the same container. Separate trust domains require separate pods; that is
what the federation is for.

### Extended predicate vocabulary

Six predicates covered corporate structures but no addresses,
registration numbers, payments, offices or family ties. There are now 22
base predicates, 44 including inverses, in five groups: ownership and
holdings, offices and functions, place and identity, relations between
persons, money and transactions.

The firewall vocabulary and the store schema derive from the same table —
a predicate the store knows and the firewall does not would be a silent
failure. A test checks the correspondence.

For every predicate it is defined whether it allows one value per subject.
Only there is a second entry a contradiction: a company has several
directors, but one seat.

**Note:** Extending the vocabulary changes the resolver fingerprint. All
pods in a network must update simultaneously, otherwise the federation
lock refuses the exchange — loudly and correctly.

## 18. Evidence documents

The previous version held reference and checksum, not the document. The
reasoning — a leak of millions of files belongs in the newsroom's
encrypted filesystem — holds for a large organisation with an IT
department. It does not hold for the freelance journalist: she has a laptop
and perhaps an external drive. A reference to `D:\Files\leak.pdf` is not
protection for her, it is a note.

IndraNet therefore optionally keeps evidence documents itself.

### Why not in the vault

The vault is fully loaded into memory when opened and re-encrypted as a
whole when saved (section 17). With 500 MB of documents inside it would be
unusable: every save would rewrite everything, and memory demand would
triple.

Instead a separate storage folder alongside. Each file encrypted
individually, processed in blocks — a 2 GB file never occupies more than
one block in memory. The vault stays small and fast; a measured example:
8 KB vault next to a 292 KB document.

### Block-wise encryption

AES-256-GCM does not process streams. The file is split into 1 MiB blocks,
each with its own nonce. Three attacks must be defeated, and each is ruled
out via the authenticated additional data per block:

| Attack | Defence |
|---|---|
| Reorder blocks | block counter enters the additional data |
| Truncate file | last block is marked; if absent, decryption aborts |
| Swap blocks | header hash enters every block |

All three are covered by tests.

### Two keys from one passphrase

The document key is derived via HKDF from the vault key but is not the
same. Anyone obtaining the document key could not open the vault with it.

### What the storage folder reveals

Filenames are hashes of the document identifier. Original name, type and
size sit encrypted in the inner header. Anyone seeing the folder learns the
number of documents and their approximate size — nothing more.

### Reference mode remains

For large corpora and for organisations with their own infrastructure,
storing in the pod is wrong. Both routes are therefore available per
document; storing is the default because it is right for the majority of
the target group.

### Limit

The passphrase thereby becomes the sole protection for all material. That
is a shift: previously a lost vault could reveal only the factual picture,
now also the source documents. Against that stands the fact that for this
target group the alternative was not weaker protection but none at all.

## 19. Governance

The technology is open source and auditable. Operation without a patent
grant is not viable for foundations and newsrooms; licensing should include
an explicit patent clause (the Apache-2.0 pattern or a defensive patent
pledge).

The coordination infrastructure — web of trust, admission rules, security
audits — belongs with a non-profit steward. The pods belong to the
newsrooms.

## 20. Provenance

The signal protocol follows the design of **DatashareNetwork** (EPFL SPRING
Lab and ICIJ, USENIX Security 2020) — peer-reviewed, with a security proof,
and designed for exactly this use case.

For entity resolution, the **Follow the Money model of OCCRP Aleph** is the
right next step.

---

*IndraNet is a tool for the fourth estate. It reaches the investigative
capability of central platforms without adopting their control structure.*
