# <MODULE> — Traceability Matrix

<!-- GENERATED — DO NOT HAND-EDIT.
     Emitted by: python docs/py/trace_check.py --matrix > <this file>
     Hand-editing this file makes it a second stored copy of the trace links,
     which is exactly the drift R-REQ-7 exists to prevent. Fix the documents. -->

**Generated:** <YYYY-MM-DD> from `<MODULE>_*_v<n>.md`
**Regenerate:** `python docs/py/trace_check.py --matrix`

> **This is a report, not a document** (`R-REQ-7`). It is committed only so it
> can be read without running Python. Every number and every row is derived; if
> a row is wrong, the requirement documents are wrong and are edited there.

---

## 1. Findings

The six defects this report exists to find. **A clean run is six zeroes** —
anything else is a finding with an owner, not a note.

| Finding | Count | Means |
|---|---|---|
| **Orphan** — requirement with no test | <n> | Unverifiable as written. Derive the test, or admit it is a motivation and demote it. |
| **Widow** — test serving no requirement | <n> | Invented scope, or a requirement was retired without its test. |
| **Unparented** — requirement with no `Trace`, below the top declared layer | <n> | Written at the wrong layer, or the layer above is incomplete. The top declared layer is never reported here (`R-REQ-12`). |
| **Dangling** — trace to a UID that does not exist | <n> | A renumber happened, or a retirement skipped the disposition section. |
| **One-way** — the two ends of a link disagree | <n> | A test's `Serves` names a requirement that cites a different test, or vice versa (`R-REQ-11`). **The most dangerous row here** — both documents are individually correct, so only a checker finds it. |
| **Duplicate** — one test id claimed twice | <n> | Allocated from the highest id in a section rather than across the module. The second claimant is silently unverified. |

### 1.1 Orphans
<one line per requirement: UID, headline, section>

### 1.2 Widows
<one line per test: ID, where cited>

### 1.3 Unparented
<one line per requirement>

### 1.4 Dangling
<one line per link: from UID → missing UID>

### 1.5 One-way
<one line per link: test id, what it claims, what cites it>

### 1.6 Duplicates
<one line per id: test id, the requirements claiming it>

---

## 2. Coverage

**Coverage is not a pass rate.** This section says what is *specified*; the
execution record says what *passed*. Reporting one as the other is the single
most common way a requirement set is declared satisfied while the product does
not work.

| Layer | Requirements | With ≥1 test | Tests | Serving ≥1 req |
|---|---|---|---|---|
| Stakeholder `STK` | | | | |
| System `SYS` | | | | |
| Software `SW` | | | | |
| Design `IMP` | | | | |

By verification method:

| Method | Requirements | Notes |
|---|---|---|
| `T` test | | |
| `D` demonstration | | |
| `A` analysis | | planted-violation cases: <n> of <n> |
| `I` inspection | | named checklists: <n> of <n> |

---

## 3. The chain

One row per leaf, showing the full V. A gap in any column is a finding in §1.

| Concept | System | Software | Design | Verified by |
|---|---|---|---|---|
| `STK-nnnn` | `SYS-nnnn` | `SW-nnnn` | `IMP-nnnn` | `UT-…`, `SYT-…`, `CT-…` |

---

## 4. Reverse index — test → requirements

For answering *"if this test fails, what is at risk?"* — which is the question
asked at 2 a.m. when a nightly campaign goes red.

| Test | Serves | Layer |
|---|---|---|
