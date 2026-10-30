# <MODULE> — Test Execution Record
## Campaign <YYYY-MM-DD> · <label>

**Executed by:** <name or CI job>
**Against:** `<MODULE>_<Layer>_Test_Spec_v<n>.md`
**Build under test:** <commit sha> · <build id> · <config bundle hash>
**Environment:** <OS, version> · <shell> · <CPU> · <build type>

> **This is the only artifact in the set that carries status** (`R-REQ-6`). No
> requirement document and no test specification has a `Status` column. Read
> *"what is left"* from here; never from a specification.

---

## 0. How to read this record

### 0.1 Status vocabulary

| Status | Means | Who investigates |
|---|---|---|
| `Not Run` | Not attempted this campaign. | — |
| `Pass` | Every case's PASS criterion observed. | — |
| `Fail` | A PASS criterion was contradicted. | The component owner |
| `Blocked` | Could not execute — fixture missing, dependency down, threshold `⊘`. | The blocker's owner |

**`Blocked` is not `Fail`.** They send different people to investigate, which is
the whole reason for four values rather than three. A campaign that collapses
them loses the distinction between *"the product is wrong"* and *"we could not
find out"*.

### 0.2 One row per **case**, never per test requirement

A test requirement with three cases is three rows. Rolling them into one row
loses which case failed, which is the only part of the record anybody acts on.

**Generate the skeleton; do not type it.** A real set is hundreds of rows, and
the `Serves` column must agree with the specifications rather than with
somebody's memory of them:

```
python py/trace_check.py --exec-rows                   # every declared layer
```

Every generated row starts `Not Run` with an empty comment — **the generator
never invents a verdict.** Fill status, date, evidence and comments by hand as
the campaign runs; that half is the human record and is the reason this file
exists.

### 0.3 Evidence

Every `Pass` and every `Fail` cites an artifact — a log, a screenshot, a diff,
a measurement. **A status with no evidence is an opinion.** For `D`-method
tests this is mandatory and is the entire difference between a demonstration
and *"we tried it"*.

Evidence lives in `<module>/logs/` (gitignored) and is referenced by path.

---

## 1. Summary

**Generated — do not hand-edit.** Emitted by the trace checker from §2.

| | Not Run | Pass | Fail | Blocked | Total |
|---|---|---|---|---|---|
| `<PREFIX>-*` | | | | | |
| **Total** | | | | | |

Requirement coverage this campaign: <n> of <m> requirements had ≥1 case
executed. **Coverage is not a pass rate** — report both, never one.

---

## 2. Results

| Case | Serves | Status | Date | Evidence | Comments |
|---|---|---|---|---|---|
| `<test-id>.c1` | `<REQ-UID>` | `Pass` | <YYYY-MM-DD> | `logs/<file>` | |
| `<test-id>.c2` | `<REQ-UID>` | `Fail` | <YYYY-MM-DD> | `logs/<file>` | <what was observed, against what bound> |
| `<test-id>.c1` | `<REQ-UID>` | `Blocked` | <YYYY-MM-DD> | — | <what blocked it, and whose it is> |

**Comments are for the observation, not the verdict.** *"peak 340 MB against a
250 MB bound"* is a comment; *"looks fine"* is not. A `Fail` row whose comment
does not say what was observed cannot be acted on without re-running it.

---

## 3. Failures requiring disposition

Each failure is dispositioned before the campaign closes. **An undispositioned
failure silently becomes an accepted one** — that is how a suite arrives at
green-except-the-ones-we-know-about.

| Case | Disposition | Owner | Reference |
|---|---|---|---|
| `<test-id>.cN` | `defect` · `spec-wrong` · `test-wrong` · `waived` | <who> | <ticket / commit / waiver reason> |

| Disposition | Means | Consequence |
|---|---|---|
| `defect` | The product is wrong. | A ticket. The case stays `Fail`. |
| `spec-wrong` | The requirement is wrong. | Edit the requirement, re-derive the test. |
| `test-wrong` | The test is wrong. | Edit the test specification. **Never** loosen an `Accept` clause to make a test pass. |
| `waived` | Accepted for this release, with a written reason and an expiry. | Recorded here **and** in the release notes. A waiver with no expiry is a deleted requirement. |

---

## 4. Environment deviations

Anything that differed from the declared environment, and why. A measurement
taken on a loaded machine is not comparable to one taken on an idle one, and a
record that does not say which is a number nobody can reuse.
