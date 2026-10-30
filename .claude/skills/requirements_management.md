# Requirements Management — V-Model Authoring (R-REQ)

The procedure behind `rules/requirements.md`. Read this before allocating a UID,
deriving a test requirement, or opening a traceability matrix.
Templates: `templates/requirements/`. Step-by-step:
`workflows/write_requirements.md`. Worked example: **`modules/df/docs/ldw/`**
(small and complete); `modules/sim/docs/v2/` is the same shape at the scale
`R-REQ-13`/`R-REQ-14` exist to prevent.

---

## 0. Declare the layer set before writing anything

`R-REQ-12`. One file, `layers.yaml`, beside the documents. It is the only
place the shape of the set is stated, and the checker is driven entirely by it.

```yaml
module: LDW
component: DF
function: ldw
layers:
  - {id: SYS, name: System,   doc: LDW_System_Requirements.md,   tests: [SYT, INSP], budget: 16, requires_binds: true}
  - {id: SW,  name: Software, doc: LDW_Software_Requirements.md, tests: [UT, IT, ANL], budget: 24, requires_item: true}
budget_basis: {unit: work_item, count: 6, per_unit: 8, total: 48}
limits: {requirement_words: 60, headline_chars: 90, commentary_lines_per_requirement: 6}
```

**Declare only the layers you are going to populate.** A set with `[SYS, SW]`
is complete and passes; a set with `[STK, SYS, SW, IMP]` where `IMP` is empty is
a *finding*, because you said you would write it and did not.

**The top declared layer is unparented by definition.** It carries `Trace. —`
and that is correct, not a gap. This is what replaces a hand-edited
`KNOWN_UNPARENTED` set — an exception list is a checker printing PASS around a
hardcoded lie.

**Do not declare `IMP` for a single-function component.** The implementation
design is the code plus the plan. A fourth layer there generates trace links
between two documents one person wrote in the same hour.

### 0a. Starting at a middle layer, with nothing above it

This is the normal case, not a special one: the work in front of you is
software-level and no concept or system document exists yet.

1. Declare **only** `SW` in `layers.yaml`. It is now the top layer.
2. Write the `SW` requirements with `Trace. —`, and their `UT`/`IT`/`ANL` tests.
3. Run the checker. It passes. You have a complete, checked, self-consistent
   set — just a narrow one.

When `SYS` is written later, add it to `layers.yaml` **above** `SW`. The checker
then emits one `C-PARENT` finding per `SW` requirement — *"no SYS parent"* —
which is your re-point worklist, enumerated by name. Work down it, and the run
goes green again.

**Never invent the layer above just to have something to trace to.** An
invented parent is the worst failure in the set because it looks traced, and
the checker cannot see it. Silence about a layer is honest; a fabricated `STK`
row is not.

### 0a1. When a stakeholder requirement has no system-level content

`R-REQ-12`. The V is a shape, not a conveyor belt. Some obligations genuinely
have nothing to say at the boundary between the stakeholder and the software:

> *"the warning shall be given at 2 s"* — a number inside one timer.
> *"activation requires both A and B"* — a condition inside one item.

Neither crosses a component boundary, occupies a port contract, or spends a
timing budget the vehicle owns. Write a `SYS` row for one anyway and you get a
**bridge row**: the parent restated one font-size larger, so that the chain
looks continuous. That is one obligation in two places (`R-REQ-1`) and it is
**worse than a gap**, because a gap is visible and a bridge row reads as
decomposition.

So a layer may declare that it traces **past** the layer above it:

```yaml
  - id: SW
    ...
    may_skip_from: [STK]      # only layers strictly above the parent
```

and the row says why, in its own `Trace`:

```markdown
**Verify.** T · `UT-belt-01`   **Trace.** `SYS-0001`, `STK-0005` (skips SYS: the
whole obligation sits inside one software item and states no vehicle-level
boundary behaviour of its own)
```

Three things, and none is decoration. The **layer** declares it, so an accident
still fails (`C-PARENT`). The **row** justifies it, so the reader of that row
alone can judge it (`C-SKIPWHY`; the reason is checked for existence and length,
never for content — no checker can grade a reason). And **every skip is printed
on every run**, exactly like the budget ratio: one skip is a judgement, thirty
skips are a `SYS` layer nobody wrote, and only a count makes the difference
visible.

**Before skipping, ask what the boundary would say.** If the answer names more
than one component, a port, a rate or a vehicle-level timing budget, there is a
`SYS` requirement there and you are about to lose it. If the honest answer is
*"nothing the software row does not already say"*, skip — and write that down.

Worked example: `templates/requirements/example`, `SW-0001` → `STK-0005`.

### 0b. The budget, and why it is a ratio

`R-REQ-13`. Pick the unit of buildable work you already have — a work item, a
work package, a declared port — count them, and multiply. The check fails over
the cap.

> The number that indicts a requirement set is never its total. It is its total
> **per unit of work**. `modules/sim` at ~1,437 requirements over 43 work
> packages is 33 per package; that is indefensible at any scale, because a work
> package is already "one chunk of buildable work".

A ratio is what makes this scale-honest: a complex module earns a bigger set by
having more work items, and nobody negotiates a number.

### 0b1. Stakeholder requirements, and their two categories

`R-REQ-16`. The top layer is the **master set** — what the stakeholder asked
for. It splits into two declared categories:

| Category | Answers | Example |
|---|---|---|
| `feature` | *What must it do?* | "shall warn before an unintended lane departure" |
| `kpi` | *How well, measurably?* | "lead time ≥ `⊘` s on every run of the acceptance corpus" |

**Declare only the categories the module actually has.**

```yaml
categories: [feature, kpi]   # an algorithm feature — both
categories: [feature]        # cyber-security, embedded housekeeping — no KPI
```

A module declaring `[feature]` is **never asked for a KPI**. A module declaring
`kpi` and writing none gets `C-CATEGORY-EMPTY` — so the escape is a decision on
the record, not a silence. Both directions are checked, which is what makes it
graceful rather than merely permissive.

**A `kpi` row's `Accept` must state a number or `⊘`.** The checker rejects one
that states neither: *"shall be rare"*, *"shall be acceptable"* is a motivation
wearing a KPI's clothes, and it is the row most likely to be declared met
without ever being measured.

### 0c. What earns a UID at all

Before writing a row, ask: **would breaking this be caught by a test failing?**
If yes, the test is the record and no UID is needed. A requirement is for a
*decision that is expensive to reverse* — where getting it wrong costs a
redesign, not a bug fix. Most of what feels requirement-shaped is behaviour, and
behaviour belongs in a named test.

Related habit, worth doing and not worth a rule: **write the executable check
first**, then the requirement as a one-line headline over it. If you cannot
write a check, you have a wish (`R-REQ-3`).

## 1. Which layer does this belong to?

The commonest authoring error is writing a requirement one layer away from where
it belongs — usually a *design decision* smuggled into a system requirement, or
a *motivation* carried as a requirement. Two tests settle it.

**The boundary test.** Ask *who could observe this being false?*

| Observer | Layer |
|---|---|
| The stakeholder — someone using or buying the product | Stakeholder `STK` |
| Anyone at the system's external boundary, with no source access | System `SYS` |
| A developer holding one software item, collaborators stubbed | Software `SW` |
| A reviewer holding the file | Design `IMP` |

**The falsifiability test** (`R-REQ-3`). Write the `Accept` clause first. If no
observation could contradict it — *"the tool shall be maintainable"*, *"the
design shall be clean"* — it is a motivation. Demote it to prose, or replace it
with the checklist it is really asking for and verify by `I` against that
checklist by name.

> A requirement nobody can fail is a requirement that will be declared
> satisfied. That is not a pedantic point: it is how a set of 300 requirements
> comes to be "met" while the product does not work.

## 2. Allocating a UID

1. Find the highest existing UID **for that layer across the whole module** —
   not the highest in the section you are editing. `grep -ohE '\bSYS-[0-9]{4}\b' *.md | sort -u | tail -1`
2. Allocate the next. Append the requirement at the end of its **section**; the
   UID does not have to be in document order and never will be after the first
   edit. That is the point of having two numbers (`R-REQ-2`).
3. Never renumber to close a gap. A gap is free; a renumber invalidates every
   trace link ever written against the old number, including ones in code
   comments and test names you cannot see.
4. Retiring: move the row to the disposition section with its replacement UID.
   A reader following a dead link must land on an explanation.

## 3. Writing the requirement

```
**`SYS-0042`** · `P0` · `R1` — Short headline, no verb games
**Shall.** The system shall <one obligation>.
**Accept.** <the observation that decides pass or fail>
**Verify.** T · `SYT-INP-07`   **Trace.** CN-0078, CN-0085
```

| Field | The mistake to avoid |
|---|---|
| **Shall** | Two obligations joined by "and". Split them. A test cannot half-pass. |
| **Accept** | Restating the `Shall` in different words. `Shall` is the obligation; `Accept` is the *measurement*. If they read the same, no measurement has been specified. |
| **Verify** | Naming a method without an identifier. The identifier is what makes the link greppable (`R-REQ-9`). |
| **Trace** | Empty **below the top declared layer**. At the top declared layer `—` is correct, not a gap (`R-REQ-12`). Below it, empty means the layer above is incomplete or this was written at the wrong level. A row that traces past a layer carries its reason in this field — `` `STK-0007` (skips SYS: …)`` — and only where the layer declares `may_skip_from` (§0a1). |
| **Binds** | *(layers with `requires_binds`)* Missing, or naming a port that neither `conf/ports.yaml` nor `ports.proposed:` declares. A boundary requirement binding to nothing is scope creep (`R-REQ-15`). |
| **Item** | *(layers with `requires_item`)* Missing, or naming a software item invented at the point of use instead of taken from `layers.yaml`'s declared list. |

**Commentary is capped and checked; count and length are not** (`R-REQ-14`).
`Shall` + `Accept` ≤ 60 words and headline ≤ 90 characters are
**one-obligation detectors**, not length limits: a row over them carries more
than one obligation and is fixed by splitting it. There is **no cap on how many
requirements a set holds, and none on document length** — both punish
thoroughness, and a writer who has to fit a number merges two obligations into
one row, which the finished document cannot show.

What is capped is **commentary**: every line that is not a requirement field, a
headline, a heading or blank, at **6 per requirement**. Measured across this
repo on 2026-09-05 — readable documents run **1.6 to 4.3**; the two that became
unreadable run **81 and 990**. Length separated neither: `sim` v2's System
document is 2,689 lines and healthy by this measure.

**Implementation documents are exempt and expected to be dense.** A design row
names a file and a symbol per software requirement — 379 of them in `sim`'s own
set — and that is what "detailed enough to build from" looks like. What is
capped there is execution narration, which belongs in a Test Execution Record.
The test is tense: design says what *will* be true; narration says what
*happened*.

**Writing ahead of the code is normal**, and the ports it needs are declared
under `ports.proposed:` in `layers.yaml`. They are reported as `PROPOSED`, never
silently accepted, and the day the real `conf/ports.yaml` gains them any
disagreement between the two fails the check.

**Priority is assigned against the other requirements, never on its own
merits.** Rated individually, almost everything looks essential and the field
stops carrying information — a real set drifted to 60% `P0` this way. The
forcing question is comparative: *if this were missing on release day, would the
tool be unusable, or merely worse?*

## 4. Deriving test requirements

**One pass per requirement, in `Verify` order.** For each requirement ask the
three questions the requirement itself cannot answer:

1. **What must exist before the test can run?** → a `Fixture`, taken from the
   document's fixture catalogue. If none fits, add a catalogue row *first*. An
   ad-hoc fixture is how two tests come to disagree about what "a recording"
   means.
2. **What is the observable sequence?** → `Steps`. Imperative, no expected
   values — those live in the requirement.
3. **How many distinct ways can this fail?** → that is the case count.

**Never restate the `Accept` clause** (`R-REQ-4`). Cite it. If you find yourself
needing different words, the requirement is wrong and is edited — do not fix it
in the test, which produces two statements free to drift.

**Method selection** (`R-REQ-8`): reach for `T` first and drop only when it
genuinely cannot execute. `A` is not a weaker `T` — it is the right method for a
property over the *codebase or artifacts* rather than over a run (an import
direction, a symbol set, a hash, a budget). Every `A` check ships a planted
violation (`R-REQ-9`); a check nobody has seen fail is a check nobody believes.

**Coverage is bidirectional.** Every requirement has ≥1 test; every test serves
≥1 requirement. The second half catches invented tests, which are as
expensive as missing ones and much harder to notice.

## 5. Test cases and pass criteria

```
`SYT-INP-07` · serves `SYS-0042` · fixture `F-FOREIGN`
Steps: <imperative sequence>
  .c1  PASS: <falsifiable condition>   FAIL: <the observable that contradicts it>
  .c2  PASS: …                          FAIL: …
```

One outcome → one case, stated inline. Enumerate cases only where the outcomes
are genuinely independent: a positive and its planted-violation twin, a scenario
with several post-conditions, or one case per rung of a declared ladder.

**Write the FAIL side.** A pass criterion with no stated contradiction is where
falsifiability quietly leaks back out — at execution time the operator decides
what "didn't really fail" means, and the case becomes unfalsifiable in practice
even though it looked rigorous on the page.

## 6. Status: where it lives, and why not here

`R-REQ-6` keeps every specification status-free. Status lives in a **Test
Execution Record**, one per campaign, from
`templates/requirements/test_execution_record.md`:

| Case | Status | Date | Operator | Evidence | Comments |
|---|---|---|---|---|---|
| `SYT-INP-07.c1` | Pass | 2026-08-13 | — | `logs/syt-inp-07.txt` | |
| `SYT-INP-07.c2` | Fail | 2026-08-13 | — | `logs/…` | peak 340 MB against a 250 MB bound |

`Not Run` · `Pass` · `Fail` · `Blocked`. **`Blocked` is not `Fail`** — they send
different people to investigate, which is the entire reason for having four
values rather than three.

**Generate the rows, fill the status.** A real campaign is hundreds of cases and
the `Serves` column has to agree with the specifications, so the skeleton comes
from the checker and only the human half is typed:

```
python py/trace_check.py --exec-rows        # every declared layer, one row per case
```

Every row lands as `Not Run` with no comment — the generator never invents a
verdict, which is the same discipline as `unknown`-never-a-default one layer
down.

Reading the record is how you answer *"what is left to **verify**"*. Reading the
specification never is, and a hand-kept `Status:` column added to a
specification will be `frozen` on two-thirds of its rows within a quarter —
measured, in this repo, on a real register.

### 6a. *"Where did I stop?"* is a different question, and it has a different answer

`R-REQ-6a`. The execution record answers *"what has been verified"*. It cannot
answer *"what has been built"*, and a session resuming tomorrow asks the second:
in a suite, **a test that has never run and a test for code nobody has written
look identical**, and telling them apart is the whole job.

So implementation progress is carried **in** the requirement documents, as a
generated `**Built.**` line — under two conditions that are what separate it
from the column above:

| Condition | Why it is the load-bearing half |
|---|---|
| **One hand-maintained source** — the plan's per-work-item checkboxes; every higher layer rolled up, never written | Four hand-kept marks is four things to forget. One is one |
| **The ordinary check run recomputes and fails on disagreement** | v1's column failed because *nothing checked it*. A derived mark that is not verified is the same defect with extra steps |

```
python py/trace_check.py --status         # per layer, and the next work package
python py/trace_check.py --write-status   # regenerate the marks (idempotent)
python py/trace_check.py                  # ordinary run: verifies them, fails on drift
```

> **`--write-status` is `modules/sim`'s own checker**, which writes `**Built.**`
> lines back into `SYS`/`SW`. The template `trace_check.py` does not write into
> requirement documents at all — it reports (`--status`) and checks. Both carry
> the rollup.

**The hand-maintained unit is the design row, not the work package.** A design
row is one buildable artifact — one file, one symbol — so its box is simply
true or false. A package is a *bag* of rows, so a package-level box can only
say *some of this happened*, which is why `modules/sim/docs/v2` moved to a box
per `IMP` id in 2026-08-27 after its resume pointer reported `WP-01` unchanged
from 20% to 79% complete. The template checker took the same shape on
2026-09-06: a `row_style: table` design layer carries a leading `Box` column,
and a package's box is **recomputed** from the rows it lands.

| Rows it lands | Package box |
|---|---|
| all `[x]` | `[x]` |
| all `[ ]` | `[ ]` |
| anything between | `[~]` |

| Check | Fires on |
|---|---|
| `C-ROWBOX` | a design row with no box, in a set that declares a `plan:` |
| `C-ROWMARK` | a design row `[~]` that does not say `closed by <what>` |
| `C-WPROLL` | a package box that disagrees with its rows' rollup |
| `C-ROLLUP-EMPTY` | `rollup: true` on a document carrying no boxed row |

Only tick the row. The package box is a *reported* value you keep in agreement
by re-running the checker, never a second thing to remember. **The box is the
first column**, in every design table — one rule, so nobody counts cells to find
the state.

**Delivery designs are counted too.** A supporting document that carries its own
build order — the viz layers, the sim fixtures, the CarMaker roads — declares
`rollup: true` beside its `context:` entry and gets the same checks plus a line
in `--status`. Its ids are scoped to itself (`VZ-`/`SM-`/`CM-`/`CA-`,
`WP-V`/`WP-S`/`WP-C`/`WP-K`) and it allocates no UID, so `C-CONTEXT-UID` is
untouched: a build order is not an obligation. Leave them out and *"the
algorithm is done"* gets read as *"the function is done"* while nothing can yet
draw it or drive it — which is the whole reason the declaration exists.

```
python py/trace_check.py --status
    ...the function's own packages and design rows...
    Delivery designs (R-REQ-17 context documents, own build order):
    [ ] delivery/viz/LDW_Viz_Imp_Design.md      4 pkg  rows 0/10
```

**Three box states, because two cannot express a resumable position.**

| Box | Means |
|---|---|
| `- [x]` | Done **and its test passes** |
| `- [ ]` | Not started |
| `- [~]` | Started — and the box **must** say `closed by <command or condition>` |

A `[~]` without that clause records that somebody was unsure rather than where
to resume, so the checker treats it as a finding. Do not infer the caveat by
looking for "extra text": a generated box already carries an artifact hint, so a
length test accepts a bare `[~]` on a long row and rejects a terse caveat on a
short one. Require the token.

**Two marks that are not progress, and must never be coloured as such:**
`◌ deferred` — no work package, deferred with its parent — and `⚠ unknowable` —
**no child requirement decomposes this one**, so there is nothing beneath it to
tick. The second is a finding about the decomposition, and rolling status up the
chain is how you find them: it surfaced two on its first run in `modules/sim`.

Reference implementation: `modules/sim/docs/v2/py/trace_check.py`, with the
rollup stated in that module's plan §0.5 and the field's contract in SysReq
§0.3a. **`Built.` is work; the execution record is verification.** Neither
substitutes for the other.

## 7. The matrix

Generated (`R-REQ-7`). It is not a document you maintain; it is a **report that
finds defects**. The trace-level findings are:

| Finding | Means |
|---|---|
| **Orphan** — requirement with no test | Unverifiable as written. Either derive the test or admit the requirement is a motivation. |
| **Widow** — test serving no requirement | Invented scope, or a requirement was retired without its test. |
| **Unparented** — requirement with no `Trace`, **below the top declared layer** | Written at the wrong layer, or the layer above is incomplete. The top declared layer is unparented by definition and is never reported. |
| **Undeclared skip** — trace to a layer that is not the one directly above | Either the link is wrong, or the layer needs `may_skip_from` (§0a1). Reported as `C-PARENT`, with the declaration named in the message so the choice is in front of you. |
| **Unjustified skip** — a declared skip with no reason in the row | `C-SKIPWHY`. The declaration says the layer *may*; the row still has to say why *this* obligation does. |
| **Dangling** — trace to a UID that does not exist | A renumber happened, or a retirement skipped the disposition section. |
| **One-way** — the two ends of a link disagree | A test's `Serves` names a requirement that cites a different test, or vice versa (`R-REQ-11`). **The most dangerous of the five**, because each document is individually correct and only the pair is wrong — so review never finds it and the matrix is confidently false. |
| **Duplicate** — one test id claimed by two requirements | Someone allocated from the highest id *in their section* instead of across the module (§2). Whichever requirement was written second is silently unverified. |

The template checker adds structural findings on top of these — budget, size
caps, port/item binding, fixtures, missing cases, a `Status` field in a
specification. Run it before every commit that touches a requirement document:
a matrix generated only at review time finds everything at once, at the worst
moment.

## 8. Onboarding a new module

1. Copy `templates/requirements/layers.yaml`, `trace_check.py` and
   `selftest_mutations.yaml` into `modules/<name>/docs/<set>/`. The checker is
   module-agnostic — every module-specific string lives in the two YAML files.
2. Edit `layers.yaml`: module, component, function, **which layers you are
   actually populating**, the budget basis, the port source, the item list.
3. Set the module's UID namespace (`R-REQ-2`) — bare inside, `<MODULE>:` when
   crossing.
4. **Write the top declared layer first, all of it, before the layer below.**
   Deriving from an incomplete parent produces unparented rows that get
   back-filled with invented parents. If you are starting mid-stack, §0a — do
   not manufacture a parent layer to satisfy the tool.
5. Run `python py/trace_check.py` and `--selftest` before the first commit.

**Reference implementation: `modules/df/docs/ldw/`** — a complete **four-layer**
set (stakeholder → system → software → implementation design) with tests. Read
it before writing a new set; it is deliberately small enough to read in full.
`python py/trace_check.py --stats` prints its size — the number is computed, so
it is never quoted here.

---

**These rules are working if:** the matrix is empty of orphans, "what is left"
is answered from an execution record in seconds, and nobody has had to ask what
a requirement meant because its `Accept` clause said so — and the set is still small enough
that somebody new reads all of it rather than grepping it.
