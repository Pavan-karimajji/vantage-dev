# Requirement & Test Templates

The V-model document set, instantiable for any module. Rules:
`../../rules/requirements.md` (`R-REQ-1..15`). Procedure:
`../../skills/requirements_management.md`. Step-by-step:
`../../workflows/write_requirements.md`.

**Reference implementation: `modules/df/docs/ldw/`** — a complete **four-layer**
set (stakeholder → system → software → implementation design) with tests,
checked green, and the worked example of `R-REQ-17`'s `context:` block *and* of
`R-REQ-6a`'s row-level progress rollup across five build orders. Read it before
instantiating these. **Its size is a computed number, so it is not written here**
— `python py/trace_check.py --stats` from that directory prints it, and a count
retyped into prose is one more thing to drift. `modules/sim/docs/v2/`
is the same shape at ~1,437 requirements. **Its requirement documents are not
what `R-REQ-13`/`R-REQ-14` were aimed at** — measured 2026-09-05, they run
9.7–9.8 lines and 1.6–2.4 commentary lines per requirement, which is healthier
than this reference set. They are large because they carry 652 requirements,
which is scope. Its *Concept* and *Implementation Design* documents are what
those rules exist for, at 990 and 81 commentary lines per requirement.

## The set

| Template | Instantiate as | Times |
|---|---|---|
| `requirement_document.md` | `<MODULE>_<Layer>_Requirements.md` | **once per layer declared in `layers.yaml`** |
| `test_specification.md` | `<MODULE>_Test_Spec.md` | **1** — all declared layers in one file; a test's layer is read from its id prefix |
| `test_execution_record.md` | `<MODULE>_Test_Execution_<YYYY-MM-DD>.md` | one **per campaign** |
| `traceability_matrix.md` | `<MODULE>_Traceability_Matrix.md` | **generated** — see `R-REQ-7` |
| **`layers.yaml`** | `layers.yaml`, beside the documents | **1** — the only declaration of the set's shape (`R-REQ-12..15`) |
| **`trace_check.py`** | `py/trace_check.py` | **1** — module-agnostic; `grep -ci <module>` over it returns 0 |
| **`selftest_mutations.yaml`** | `selftest_mutations.yaml`, beside `layers.yaml` | **1** — the planted violations, as data (`R-REQ-9`) |
| `implementation_design.md` | `<MODULE>_Implementation_Design.md` | **0 or 1** — the `IMP` layer, if declared. Also the template for a **delivery design** (`context: … rollup: true`), one per surface the function is built into |
| `concept_document.md` | `<MODULE>_Concept.md` | **0 or 1** — a supporting document (`R-REQ-17`), declared under `context:` |
| `architecture_document.md` | `<MODULE>_Architecture.md` | **0 or 1** — same |

**Supporting documents are optional and declared** (`R-REQ-17`). A `concept`,
`architecture`, `register` or `reference` entry under `layers.yaml`'s
`context:` block is where the *thinking* goes, so the specification carries
only the result. They allocate no UIDs, define no requirement rows, and are
**exempt from the commentary cap** — commentary is the point of them. Four
checks hold them honest: `C-CONTEXT-MISSING`, `C-CONTEXT-KIND`,
`C-CONTEXT-UNREF` (nothing in the set cites it, so it will go stale unnoticed)
and `C-CONTEXT-UID` (it allocates a requirement row instead of citing one).
All four are planted and caught in `example/`. Omitting the block entirely is
honest and common.

**The number of documents is not fixed.** `layers.yaml` declares which layers a
module populates (`R-REQ-12`); the requirement template is instantiated once per
*declared* layer. Two layers is a complete set. A layer declared and left empty
is a finding.

**Why one template per side.** The requirement layers are structurally
identical — same anatomy, same trace discipline, same falsifiability rule — and
differ only in a UID prefix, an observer and a test namespace. Near-identical
template files would be copies free to drift, which is `R-REQ-1` applied to the
templates themselves. The per-layer differences are a **substitution table**,
not a separate file.

## Instantiating

0. Copy `layers.yaml`, `selftest_mutations.yaml` and `py/trace_check.py`
   first, and **decide which layers you are populating** before writing a row.
1. Copy the document templates you need to `modules/<name>/docs/<set>/`.
2. Substitute per the table in the template's §0 — prefix, observer, test
   namespace, verification emphasis.
3. Declare the module's UID namespace once (`R-REQ-2`): bare inside, `<MODULE>:`
   qualified when a link crosses modules.
4. Declare the area/item tokens in §0, once. Never invent one at the point of use.
5. **Write the top declared layer completely before the layer below it.**
   Deriving from an incomplete parent produces unparented rows that get
   back-filled with invented parents — the worst failure in the set, because it
   looks traced. If you are starting mid-stack with nothing above, that layer
   *is* the top: write it with `Trace. —` and do not manufacture a parent
   (`R-REQ-12`, `skills/requirements_management.md` §0a).
6. Run `python py/trace_check.py` and `--selftest` before the first commit.

## The one thing not to change

**No specification in this set carries a `Status` column** (`R-REQ-6`). Status
lives in the execution record. If you are about to add one because it would be
convenient to see status beside the requirement — that is exactly the change
that produced a register reading `frozen` on 68 of 77 rows after twelve stages
had shipped, unable to answer *"what is left"*. Generate the matrix instead.

**The `Box` column is not that column, and the difference is the whole of
`R-REQ-6a`.** `Status` answers *has this been verified* — a judgement, in
words, that nothing can recompute; it belongs to a campaign. `Box` answers *has
this been built* — three states from a closed set, on a design row, recomputed
into the package above it and failed on when the two disagree. The test for
whether a new column is legitimate is not what it is called: it is whether the
ordinary check can derive every mark above it from one hand-typed source. A
words-in-cells status column fails that test by construction, which is why
`ldw_image_plan.md`'s `DONE` column was replaced by boxes on 2026-09-06 rather
than kept.
