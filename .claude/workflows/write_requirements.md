# Workflow — Writing a requirement set (R-REQ)

Covers a full pass **and** the far commoner case: one layer, mid-stack, with
nothing above it yet. Rules: `rules/requirements.md` (R-REQ-1..15). Procedure:
`skills/requirements_management.md`. Reference: `modules/df/docs/ldw/`.

## 0. Set up — once per module

```
mkdir -p modules/<name>/docs/<set>
cp .claude/templates/requirements/layers.yaml             modules/<name>/docs/<set>/
cp .claude/templates/requirements/selftest_mutations.yaml modules/<name>/docs/<set>/
```

**The checker is not copied.** It is module-agnostic and driven entirely by
`layers.yaml`, so one file serves every set:

```
python .claude/templates/requirements/trace_check.py --set modules/<name>/docs/<set>
```

A copy per set is a copy free to drift, which is the failure `R-BUILD-6` exists
to prevent, and it is the reason a **small** set — a fix folder carrying one
implementation design and nothing else — costs a `layers.yaml` and no tooling
at all. Copy it into `<set>/py/` only when the set is large enough to earn its
own entry point; then it runs with no `--set` and must stay byte-identical to
the template (`modules/df/docs/ldw/py/trace_check.py` is the one such copy).

Edit `layers.yaml`. **Declare only the layers you will populate** (`R-REQ-12`)
and, on the `STK` layer, **only the categories this module has** (`R-REQ-16`) —
`[feature, kpi]` for an algorithm feature, `[feature]` alone for a
cyber-security or embedded item with no performance target of its own.
Everything module-specific lives in the two YAML files; the checker holds none
of it.

## 0a. Which supporting documents? (`R-REQ-17`)

Ask before writing rows, and record the answer in `layers.yaml`'s `context:`
block. If this set belongs to a new component the question was already put at
`workflows/add_component.md` **Step 0** — carry that answer through rather than
asking twice.

A supporting document is where the *thinking* goes so the specification carries
only the result. It allocates no UIDs, defines no requirement rows, is exempt
from the commentary cap, and must be cited by something in the set or the
checker reports it as unreferenced. Four kinds, closed: `concept`,
`architecture`, `register`, `reference`.

**Omitting the block is a fine answer** — a set whose reasoning fits in its own
preambles needs none.

## 1. Which layers?

| Situation | Declare |
|---|---|
| Full pass, a real external stakeholder | `[STK, SYS, SW]` |
| A component with ports, no separate stakeholder set | `[SYS, SW]` |
| A kernel or library — no system boundary of its own | `[STK, SW]` or `[SW]` |
| **Only software requirements this session** | `[SW]` — see §4 |
| A single-function component, behaviour already obvious from the code | `[STK, SYS, SW]` — the design *is* the code plus the plan |
| **A component whose file-and-symbol layout is a real decision** | `[STK, SYS, SW, IMP]` with `row_style: table` — one row per `SW`, naming which file, which symbol, in what order. Worked example: `modules/sim/docs/v2/parity` |

A `row_style: table` layer in a set that also declares `plan:` carries a
leading `Box` column: `| Box | UID | Serves | WP | Change | Artifact — Design |
Tests |`. That box is the **only** progress state anyone types (`R-REQ-6a`) —
the work-package boxes in the plan are recomputed from it and `C-WPROLL` fails
if they disagree. Tick the row; re-run the checker; fix the package box it
names. **The box is always the first column**, in every design table in the set.

A **delivery design** — one document per surface the function is built into
(viz, sim, CarMaker, CARLA), each with its own packages and row ids and no UID
of its own — is a `context:` document declaring `rollup: true`:

```yaml
context:
  - kind: architecture
    doc: <MODULE>_Viz_Imp_Design.md
    rollup: true
```

```
- [ ] **WP-V02** — headline · why it sits here
| Box | ID | WP | Change | Artifact — design |
| `[ ]` | `VZ-02` | `WP-V02` | `NEW` | path::symbol — what it does |
```

Same three checks, plus a line in `--status`. Declare it on a prose document
with no boxed row and `C-ROLLUP-EMPTY` fires: a rollup that rolls nothing up
reads as coverage.

Adding a layer later is cheap and mechanical (§4). Declaring one you do not
fill is a finding.

## 2. Write, top declared layer first

1. **Budget before content.** Set `budget_basis` from a unit of work you
   already have (`R-REQ-13`). It is an **expectation that gets reported**, not
   a cap that fails the build — write what the set needs and let the number
   move, because a budget that binds while you write makes you merge two
   obligations into one row, and the reader cannot see that happen.
2. **Top layer, all of it**, before the layer below it. Deriving from an
   incomplete parent is what produces back-filled invented parents.
3. Each row: `Shall` (one obligation) · `Accept` (falsifiable, measures rather
   than restates) · `Binds`/`Item` where the layer requires it · `Verify` ·
   `Trace`. ≤ 60 words for `Shall`+`Accept` (`R-REQ-14`).
4. **Before allocating a UID, ask what earns one** — if breaking it would be
   caught by a test failing, the test is the record. A requirement is for a
   decision expensive to *reverse*.
5. Then the layer below, tracing up. Then the tests.
6. **A row with nothing to say at the layer in between traces past it**
   (`R-REQ-12`). Ask what the boundary would state: if the answer names more
   than one component, a port, a rate or a vehicle-level timing budget, write
   the `SYS` row. If it is *"nothing the software row does not already say"* —
   *"warn at 2 s"*, *"activate only when A and B both hold"* — declare
   `may_skip_from: [STK]` on `SW` and write the reason into the row:
   `` **Trace.** `STK-0007` (skips SYS: one software item, no vehicle-level
   boundary behaviour of its own)``. A bridge row that restates its parent one
   font-size larger is worse than a gap: it is one obligation in two places
   (`R-REQ-1`) and it reads as decomposition. Undeclared is `C-PARENT`,
   unjustified is `C-SKIPWHY`, and every skip taken is printed on every run.

## 3. Check

```
cd modules/<name>/docs/<set>
python py/trace_check.py            # exit 1 on findings
python py/trace_check.py --stats    # counts against the derived budget
python py/trace_check.py --matrix   # the generated matrix (R-REQ-7)
python py/trace_check.py --selftest # prove each check catches a planted violation
python py/trace_check.py --next-uid  # next free UID per layer, and remaining budget
python py/trace_check.py --exec-rows > <MODULE>_Test_Execution_<date>.md
```

Run it **before every commit** touching a requirement document. A matrix
generated only at review time finds everything at once, at the worst moment.

## 4. Adding a layer above an existing set

The normal path when a session wrote only `SW`, or only `SYS`.

1. Add the new layer to `layers.yaml`, **above** the existing one.
2. Run the checker. It emits one `C-PARENT` finding per now-unparented
   requirement — **that is your worklist, enumerated by name.**
3. Write the new layer's rows, then add a `Trace` to each child — **except a
   child the new layer genuinely has nothing to say about**, which traces past
   it under `may_skip_from` with its reason in the row (§2.6). Adding `SYS`
   above `SW` is exactly when a bridge row gets written to make the chain look
   continuous; that is the moment to skip instead.
4. Re-run. Green.

**Never invent a parent to silence the tool.** An invented parent looks traced
and no check can see it. `C-LAYER-GONE` does the reverse case — removing a
layer — naming the re-point target for each broken link.

## 4a. Adding requirements to a finished set

Ordinary work, not a migration — nothing here is hand-maintained, so nothing
needs re-syncing.

1. `python py/trace_check.py --next-uid` — the next free UID per layer, and how
   much budget is left. Read it; never eyeball the highest number, which is how
   two requirements come to share a UID (`R-REQ-2`).
2. Write the row, its `Trace` (unless it is the top declared layer) and its
   test. The test names the requirement back (`R-REQ-11`).
3. Re-run the checker. The matrix, the coverage counts and the execution-record
   skeleton all regenerate; there is no matrix to update by hand.

**If the set runs over its expectation, the check says so and passes.** That
is a **scope** signal for you to judge, not something a checker should resolve
by making the writing smaller (`R-REQ-13`). Either the scope genuinely grew, or
raise `budget_basis` with a dated `budget_history:` entry — which is printed
on every run, so growth stays a decision with an author rather than a comment
nobody reads.

**What does fail is commentary** (`R-REQ-14`): more than 6 non-requirement
lines per requirement. Cut the prose, never the requirements.

**An implementation design or plan is the exception, and is expected to be
long.** Its rows name files and symbols, one per software requirement, and a
path in one is a promise about where the code goes. What is capped there is
**execution narration** — what was run, what was found, how long it took —
which belongs in a Test Execution Record or a commit message. The test is
tense: a design row says what *will* be true of the code; narration says what
*happened*. A row in the past tense is in the wrong document.

## 5. Recording results

Status lives **only** in the execution record (`R-REQ-6`); `C-STATUS` fails a
specification that grows one. Generate the rows, type only the human half.
`Blocked` is not `Fail` — they send different people to investigate. A `⊘`
threshold nobody supplied is `Blocked`, never a plausible number (`R-REQ-10`).

## Done when

- `trace_check.py` exits 0, and `--selftest` catches every planted violation.
- Every layer is inside its budget, and `--stats` says so.
- No orphans, no widows, no one-way links, no invented parents.
- The set is small enough that somebody new reads all of it.

See also: `rules/requirements.md`, `skills/requirements_management.md`,
`templates/requirements/`, `workflows/add_function.md`.
