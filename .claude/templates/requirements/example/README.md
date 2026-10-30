# Example — a complete requirement set built from these templates

**What this is.** A working instantiation of `../`, kept so the claim *"copy
the template into any module and it works"* is something you can run rather
than something you have to believe.

Subject: a **seat-belt reminder** (`SBR`). Deliberately not an ADAS function —
everyone already knows what it does, so you can look past the subject at the
shape. It is fictional; nothing here is project scope.

## Run it

```
cd .claude/templates/requirements/example
python py/trace_check.py                       # every check; exit 1 on findings
python py/trace_check.py --stats               # counts, budget, commentary
python py/trace_check.py --selftest            # 26 planted violations, all caught
python py/trace_check.py --matrix              # generated traceability matrix
python py/trace_check.py --exec-rows           # execution-record skeleton
python py/test_checker_additions.py            # the R-REQ-13/14 evidence
python py/test_checker_additions.py --plant    # prove those checks can fail
```

## What it holds

| File | Lines | What |
|---|---:|---|
| `layers.yaml` | 108 | The one declaration — layers, categories, budget, limits, ports, items, one declared layer skip |
| `SBR_Stakeholder_Requirements.md` | 49 | `STK` — 5 rows, 4 `feature` + 1 `kpi` |
| `SBR_System_Requirements.md` | 40 | `SYS` — 5 rows, each binding declared ports |
| `SBR_Software_Requirements.md` | 49 | `SW` — 7 rows, each naming a declared item; one traces past `SYS` |
| `SBR_Test_Spec.md` | 129 | 18 tests, 24 cases, one fixture catalogue, all layers |
| `selftest_mutations.yaml` | 307 | 26 planted violations, as data |
| `py/` | — | Byte-identical copies of the parent template's checker and evidence file |

**17 requirements, 18 tests, 24 cases** across the three requirement
documents plus the test spec. `--stats` prints the counts; a size retyped into
prose is one more thing to drift.

## What it demonstrates

**Three layers, complete and traced both ways.** Every requirement names its
tests, every test names its requirements, and the checker fails when the two
halves disagree (`R-REQ-11`).

**Commentary is what is capped, not size** (`R-REQ-14`). This set reports
1.2–2.4 commentary lines per requirement against a cap of 6 — worth noting
because a *small* document is the hard case for that ratio: a fixed preamble
divides by few requirements. It still fits comfortably.

**An unsupplied threshold is marked, never guessed** (`R-REQ-10`). `STK-0004`'s
false-reminder rate is `⊘`, and `STT-04.c1` is explicitly blocked on it. A
requirement nobody can fail will be declared satisfied.

**An `A`-method check ships a planted-violation case** (`R-REQ-9`). `ANL-01.c2`
exists because a static check nobody has seen fail is a static check nobody
should believe.

**A stakeholder obligation with no system-level content traces straight to
software** (`R-REQ-12`). `STK-0005` — ignore a one-tick switch flicker — lands
entirely inside the `belt` item and states no vehicle-level boundary behaviour,
so `SW-0001` traces to it directly and says why in the row. A `SYS` row written
to bridge them could only restate the parent one font-size larger: one
obligation in two places (`R-REQ-1`), and worse than a gap because it reads as
decomposition. The escape is declared on the layer (`may_skip_from: [STK]`),
justified in the row (`C-SKIPWHY`), and **counted on every run** — one skip is a
judgement, a set full of them is a `SYS` layer nobody wrote.

**Ports are `PROPOSED`, and reported as such** (`R-REQ-15`). There is no real
`conf/ports.yaml` behind a fictional module, so every run says so rather than
silently accepting the names.

## Why it earns its place

Building it found a real defect in the tooling on its first run:
`test_checker_additions.py` shrank a layer's budget to a hardcoded `4` to prove
that going over produces a note rather than a failure — and this set's top
layer expectation **is** 4, so the substitution was a no-op and the check
tested nothing. Fixed in all four copies.

That is the argument for keeping an instantiation around: a template that has
only ever been exercised by the set it was extracted from has not been tested,
only remembered.
