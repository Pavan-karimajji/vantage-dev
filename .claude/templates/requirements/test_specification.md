# <MODULE> — Test Specification

**One file for all declared layers.** A test's layer is read from its
identifier prefix, declared in `layers.yaml`. Separate per-layer test documents
would be several files to keep in agreement with each other; the prefix already
carries the layer.

> **The block format below is what `py/trace_check.py` parses.** Do not
> reformat it into a table — a table parses as zero tests, every requirement
> becomes an orphan, and the run fails with no obvious cause. Run the checker
> after the first entry, not after the hundredth.

**A test never restates an `Accept` clause** (`R-REQ-4`). Its expected value
*is* the served requirement's `Accept`, cited by UID. A test contributes only
what the requirement cannot know: `Serves`, `Fixture`, `Steps`, and its cases.

**Every case states its FAIL side** (`R-REQ-5`). A pass criterion with no stated
contradiction is where falsifiability leaks back out — at execution time the
operator decides what *"didn't really fail"* means.

## Anatomy

```
**`<test-id>`** · <T|D|A|I> · fixture `F-<NAME>`[, `F-<NAME>`] — headline
**Serves.** `<REQ-UID>`[, `<REQ-UID>`]
**Steps.** <imperative sequence, no expected values>
- `.c1` **PASS:** <falsifiable condition, per `<REQ-UID>` Accept> **FAIL:** <the observable that contradicts it>
```

One outcome → one case, stated inline. Enumerate separately only where the
outcomes are genuinely independent: a positive and its planted-violation twin,
a scenario with several post-conditions, or one case per rung of a ladder.

## Identifier prefixes

Substitute your declared layers' rows and delete the rest. The prefix→layer
mapping lives in `layers.yaml`, not here.

| Prefix | Level | Proves |
|---|---|---|
| `STT-nn` | Validation | One stakeholder requirement, as an acceptance criterion for the product |
| `E2E-nn` | End-to-end | One complete operational scenario, one user goal |
| `SYT-<area>-nn` | System | One capability of the assembled system, through its external interfaces |
| `UT-<item>-nn` | Unit | One software item through its own interface, collaborators stubbed |
| `IT-nn` | Integration | Two or more items across one named interface |
| `ANL-nn` | Analysis | A measurement or static check over code or artifacts |
| `INSP-nn` | Inspection | A checklist review, only where no execution is possible |

`<area>` and `<item>` tokens are declared once and never invented at the point
of use.

## Fixture catalogue

Named, never ad-hoc — an ad-hoc fixture is how two tests come to disagree about
what "a recording" means. A test needing a fixture not listed needs a row here
**first**. The checker fails on a fixture that is not in this table.

| Fixture | What it is |
|---|---|
| `F-<NAME>` | <what it is> |

---

## 1. <Layer> — `<PREFIX>`

**`<PREFIX>-01`** · T · fixture `F-<NAME>` — <headline>
**Serves.** `<REQ-UID>`
**Steps.** <imperative sequence>
- `.c1` **PASS:** <condition>, per `<REQ-UID>` Accept. **FAIL:** <contradiction>.

**`<PREFIX>-02`** · T · fixture `F-<NAME>` — <headline>
**Serves.** `<REQ-UID>`
**Steps.** <imperative sequence>
- `.c1` **PASS:** …, per `<REQ-UID>` Accept. **FAIL:** ….
- `.c2` **PASS:** …, per `<REQ-UID>` Accept. **FAIL:** ….

## 2. Analysis — `ANL`

The mechanised checks — the highest-leverage tests in the suite, because each
turns a rule that would otherwise be reviewed into a rule that fails a build.
**Every `A`-method entry ships its planted-violation case** (`R-REQ-9`); the
checker fails an `A` entry with fewer than two cases.

**`ANL-01`** · A · fixture `F-SRC` — <what it scans>
**Serves.** `<REQ-UID>`
**Steps.** <the scan>; then repeat against a copy carrying a planted violation.
- `.c1` **PASS:** no match in the real tree, per `<REQ-UID>` Accept. **FAIL:** any match.
- `.c2` **PASS:** the planted violation is reported, naming file and line. **FAIL:** the planted copy passes.

## 3. Thresholds not yet supplied

`⊘` means the harness is specified and buildable but the bound is the
customer's to set (`R-REQ-10`). Such a case is `Blocked` in the execution
record, never `Fail`, and never given a plausible number.

<list them, with the open question each waits on>

---

## What this document does not contain

- **Expected values** — they are the requirements' `Accept` clauses.
- **Verification status** — the execution record (`R-REQ-6`). The checker fails
  a `Status` field here.
- **Coverage counts** — emitted by `py/trace_check.py`; a number derivable from
  the document is a second copy, and a second copy drifts.
- **Test code** — `R-REQ-9` binds the identifier to the implementation.
