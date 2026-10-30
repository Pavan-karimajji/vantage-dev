# Prompt: system_audit_and_replan (METHOD — module-agnostic)

Full-scope orchestration audit for a module under active development: walk its
**master requirements register**, traverse its design and plan documents in
order, find where reality has drifted from what was actually asked for, and
land every finding **in the document and the stage that must change** — never
in a side list.

**This file is the METHOD and names no module.** It is invoked through a
module's own instantiation file, which names that module's document triad, its
ID families and its exact commands:

| Module | Instantiation |
|---|---|
| `sim` | `modules/sim/.claude/prompts/sim_audit.md` |

*(A module without an instantiation file is not auditable by this prompt yet —
writing one is a ~60-line job, see `sim_audit.md` as the worked example.)*

**How to invoke:** point a session at the module's instantiation file, e.g.
*"Read and execute `modules/sim/.claude/prompts/sim_audit.md`."* Run under
Opus at high reasoning effort — this is a large, judgment-heavy synthesis job,
not a mechanical one.

Rules: `rules/*` (all of it — this audit is cross-cutting by nature).
Related: `docs/ai_operational_layer_spec.md` (governs the operational layer
itself, in scope per angle 5), `workflows/submodule_commit_order.md` (fixes
that touch submodule content still follow R-GIT-1).

---

## MISSION

You are taking ownership of a multi-session AI-assisted implementation effort.
Implementation has been proceeding against a written plan and has landed a
number of stages. **Your job is not to implement forward.** It is to audit what
landed against what was asked, and to leave the planning documents in a state
where the next session opens one file, reads one resume marker, and continues
correctly with no archaeology.

Two failure modes this prompt exists to prevent, both observed here:

- **A finding recorded where nobody will act on it.** A punch-list at the end
  of a five-thousand-line document is a graveyard. Findings live in the stage
  queue; the ledger only indexes them.
- **A finding recorded instead of fixed at its source.** If a requirement or a
  design document is wrong, correcting it *in the audit log* leaves the master
  document wrong and makes the log a second source of truth. That is the exact
  defect this repo refuses everywhere else.

---

## THE TRAVERSAL — top-down, once, in this order

Do not start where the code is interesting. Start where the intent is
recorded, and walk down. Each level's findings constrain the next.

```
1. REQUIREMENTS   the register: what was actually asked for
      |
2. DESIGN         architecture + the binding satellite/contract docs
      |
3. PLAN           the checkbox-tracked stage list and its build order
      |
4. CODE           what is actually written, built and passing
```

Read down; propagate down. A finding at level *n* is not finished until you
have asked, **explicitly and in writing**, what it does to every level below —
including when the answer is "nothing".

---

## THE PROPAGATION RULE — the core of this audit

**Every finding is classified by its `origin level` (1–4 above), and every
finding must state its downstream consequence at each lower level.** Record the
answer even when it is *"no change"*; an unrecorded "no" is indistinguishable
from a question nobody asked.

| Origin | Must answer |
|---|---|
| **1 · Requirement** | Does the design/contract change? → Does the stage list or its order change? → Does code change? |
| **2 · Design/contract** | Does the stage list or its order change? → Does code change? *(and: is the requirement still satisfied, or did the design quietly drift from it?)* |
| **3 · Plan/sequence** | Does code change? *(and: does the requirement or design need correcting too, or was only the sequencing wrong?)* |
| **4 · Code** | Fix location only — but confirm the plan's stage still describes what the code should do. |

**The upward check is not optional.** A code-level fix that contradicts the
design doc is a design finding as well; a design finding that contradicts the
register is a requirements finding as well. Escalate rather than patching the
lowest level.

### The rule that makes this real

> **A finding whose origin is level 1 or 2 is not closable until the master
> document at that level has been edited.** The ledger records *that the edit
> happened and where*; it never carries the correction itself.

Concretely: correcting a requirements defect means editing the requirements
register. The ledger row then names the document and the section. A ledger row
that describes a correction no master document contains is the failure this
whole rule exists to prevent — and if the module ships a ledger check, that is
what it enforces.

---

## THE FINDINGS LEDGER

One ledger per module, at the location its instantiation file names. It is an
**index, not a container**.

- **IDs are stable and never reused.** Same discipline as every other ID in
  this repo (`R-*`, `FR-*`, stage ids, gates). A finding keeps its id across
  runs so a commit, a checkbox and a later audit can all cite it.
  **The id space is the ledger, not the repo.** A second module's ledger starts
  its own `AR-1`, and both ledgers may legitimately name root files, so a
  citation that leaves the module qualifies itself (`sim:AR-23`). Never
  renumber an existing id to buy global uniqueness — qualification is free and
  a renumber breaks every commit, checkbox and row that already cites it.
- **Every row carries:** id · origin level · one-line summary · the
  document(s) **and** stage(s) it landed in · state · the date it changed
  state.
- **The fix itself is a checkbox in the stage that will do it**, in the plan,
  in build order. The ledger points at that checkbox; it never restates the
  work. A finding with no owning stage and no owning document is not yet a
  finding — either place it or drop it.
- **States:** `OPEN` · `CLOSED` (fixed and re-verified, with evidence) ·
  `SUPERSEDED` (overtaken by a later decision — say by which) · `WONTFIX`
  (deliberate, with the reason and who decided).

### The ledger's own header is part of the method, not per-module prose

**When you create a ledger, create it with these four sections.** They are the
instructions a *later* session needs, and a later session will be reading the
ledger rather than this prompt — so a ledger without them is a list of problems
with no defined way to work it. Write them into the file at creation; do not
leave them to be hand-added after someone trips over the gap.

| Section | Must say |
|---|---|
| **Which file to start from** | ledger = index **by problem**; the plan = queue **by build order**; the module's audit prompt = re-audit. They are not alternatives, and a fix session still reads the owning stage first, because the stage carries the `Must not` constraints the ledger deliberately does not repeat. |
| **How to read a row** | every field: id · origin level · fix type · landed-in · state. |
| **How to work a row** | the loop: open the owner → **fix at the origin level** (level 1/2 means the master document is edited, not code that happens to satisfy the new reading) → re-verify with the evidence the row names → tick the owning stage's checkbox citing the id → move the row to closed with its landed-in and date → re-run the module's doc-check command → commit citing the id. Plus the discovery boundary: **a fix session may not go looking for new findings, but a finding that is the direct output of a row it was working belongs to that row and is recorded** (a "run this gate for the first time" row that fails has *produced* its result, not wandered off). It records without fixing — a newly found defect needs its own verification cycle. |
| **The level 1/2 rule and reconciliation** | stated in the ledger itself, not only here — they are what stop it becoming a second source of truth. |

If the module ships a ledger check, it verifies these sections are **present**.
That is a shape check, not a content check: it cannot tell whether the loop is
followed, only that a ledger was not created without one.

### Reconciliation comes first — before any new finding is written

**Every run of this audit begins by re-verifying the existing ledger, and that
pass is part of the deliverable.** For each `OPEN` row: re-run its evidence.
Fixed → `CLOSED` with the evidence and the date. Still open → leave it, and say
whether it moved. Overtaken → `SUPERSEDED`, naming what replaced it.

**An audit that only appends is noise by its third run.** If a re-run cannot
shrink the ledger, the ledger is not being worked — report that as a finding in
its own right, because it means the previous audit's output was ignored.

---

## THE REVIEW: FIVE ANGLES, DO ALL FIVE

1. **REQUIREMENTS LEVEL — walk the master register row by row.** First,
   because the other four can all pass on a system that faithfully implements
   the wrong thing. **Enumerate, do not summarise** — extract every row
   mechanically (a script; by eye silently skips some). Per row:

   - **Is it actually satisfied today?** Not "is there a stage for it" — is the
     behaviour present in shipped code, and is the row honest about it? If the
     register's status vocabulary cannot express *"built and proven"*, say so:
     that is a finding about the register, at origin level 1.
   - **Does the cited verifier exist, and is it *about* this requirement?**
     Existence is mechanically checkable and probably already checked.
     **Aboutness is not, and is where the rot is** — open the test and read it.
     A row verified by a real test on a different subject passes every
     automated check and proves nothing.
   - **Is the priority order honoured by the build order?** A `P0` behind a
     `P2` is a plan defect, not a scheduling detail.
   - **Was a requirement quietly reinterpreted** — narrowed to what was
     convenient, or widened past the ask? Registers keep verbatim quotes
     precisely so this is checkable; use them.

   Report as a table. Parked/deferred rows are in scope only to confirm the
   parking is still right and still stated.

2. **DESIGN LEVEL** — do the design and contract documents still answer the
   requirements, and still cohere with each other? Look for: decisions that
   made sense in isolation but now contradict an earlier one, a contract
   specified on one side only, and rules the design claims to uphold that the
   code does not. Where two documents disagree — this happens — **decide which
   is right and say why**; do not just flag the conflict.

3. **PLAN / EVIDENCE LEVEL** — does the evidence support the claims? A ticked
   checkbox is only as good as the test behind it. Distinguish: (a) genuinely
   verified — tests exist, ran, pass; (b) claimed but unverified — e.g. code
   written but never compiled because the environment lacked a toolchain (a
   real, repeated failure mode: **check every shell available to you before
   accepting "no compiler here"**); (c) actually wrong. Also audit the
   **definitions** of the global gates, not just their results — a gate defined
   on the wrong quantity (a test *count* where a *pass* was meant) stays green
   on a broken build.

4. **ARCHITECTURE / CODE LEVEL** — as actually written, does the code respect
   the boundaries the rules describe (component/interface separation,
   middleware-free algorithm code, protobuf only at boundaries, a framework's
   component-agnosticism where that applies)? Flag drift even where it still
   works. Where a rule's stated scope and its enforced scope differ, that is a
   finding at whichever level is wrong — usually the rule.

5. **OPERATIONAL LAYER & CLEANUP — two levels, and both are in scope.** The
   **root** layer (`CLAUDE.md`, `.claude/rules`, `.claude/skills`,
   `.claude/templates`, `.claude/workflows`, `.claude/routing.md` and this
   prompt set) *as it governs the module under audit*; **and the module's own**
   `modules/<name>/CLAUDE.md` plus `modules/<name>/.claude/` — including the
   binding that invoked this audit. Do they still describe how the repo works
   today? **The module's two files are audited every run**: they are the half
   nobody else opens, and a binding that has drifted is invisible from root.

   Separately, catalogue dead ends: superseded docs, orphaned scaffolding,
   fixtures nothing references, workflow steps for a changed process. **Do not
   silently delete anything with repo-wide reach** (rule files, shared
   templates) — flag with a recommendation and let it be actioned deliberately.
   Genuinely local, unambiguous dead files may be noted for direct removal.

   **Placement is part of this angle.** Anything you add to the operational
   layer during the audit — and anything you find sitting in the wrong place —
   is placed by the four-step test in `.claude/README.md` (full version:
   `docs/ai_operational_layer_spec.md` §7). **Do not restate those four steps
   here or in a binding.** A third copy of the layer's own placement test,
   living inside the prompt whose job is to catch duplication, is the defect
   auditing itself; cite it instead.

   What this angle adds is the *checking*. **Step 3 is the one that gets
   skipped**, in both directions: a general method buried in one submodule (the
   next module forks it), or a root file stuffed with one module's specifics
   (everyone else reads around them). Two tells worth grepping for — *"for
   `<module>`, use …"* inside a root file, and a binding that has started
   explaining *how* rather than *which*. Report either as a finding at origin
   level 2. Applies to rules, skills, workflows and templates alike, not just
   prompts. And do not create a submodule `.claude/` speculatively: it exists
   when there is a real binding or a real local deviation to put in it.

   **The superproject's `docs/` is stratified — do not sweep it.** Two of these
   classes are module-independent and are therefore stated once, here; a
   module's binding names only its own two lists.

   | Class | In scope for a module audit? |
   |---|---|
   | **Normative** — a root `docs/` file cited by some `.claude/rules/*` file | **Only where a finding touches one.** They bind the platform, not this module's design. Do not audit them wholesale. |
   | **Completed-item records** — the write-up of a finished root `plan.md` item | **No**, unless a finding lands squarely inside one. |
   | **Module-adjacent** — the contracts this module consumes | **Yes.** The binding lists them. |
   | **Legacy this module replaces** | **Retirement inventory only** — what the module's own deletion stage removes. They are **not** design authority; do not "reconcile" the module's design against them. |

   The module's own entry in root `plan.md` is **always** in scope — it is the
   cross-cutting backlog's view of this module, and it drifts easily from the
   module's own documents.

For each finding classify the **fix type** as well as the origin level:
**(a) code defect** · **(b) verification gap** — say what proof is missing and
how to get it · **(c) documentation drift** · **(d) plan defect** — sequencing
or scope itself was wrong · **(e) cleanup**. Origin level says *where it came
from*; fix type says *who acts*. Do not blur either.

---

## METHOD

Run the repo's own scripts (test suites, invariant and doc-consistency
checkers), grep and read across the tree, and **attempt real builds** — do not
take a stage's narrative at its word when you can generate independent
evidence. Prefer **extending the repo's mechanical checks** over eyeballing:
a check you leave behind stops the finding from recurring, which a report does
not. Deploy subagents in parallel for evidence gathering if it genuinely
helps, but **you** do the synthesis and the judgement calls.

---

## DELIVERABLE

1. **The reconciliation pass** over the existing ledger (above), first.
2. **Corrections landed at their origin level** — the requirements register,
   the design docs, the plan, the operational layer, each edited where it is
   wrong. Never weaken or delete a requirement to match what got built: an
   unmet requirement is a finding, and the register is the one place that must
   keep saying so.
3. **Every actionable fix as a checkbox in its owning stage**, in build order,
   with the finding id cited.
4. **The ledger updated** — new rows with stable ids, states, and the
   document/stage each landed in.
5. **One unambiguous resume marker**, following the module's existing
   convention, naming exactly which stage to pick up and in what order.
6. **Human decisions recorded explicitly at that marker** rather than silently
   answered.

7. **The run's edits landed at both levels.** An audit corrects the module's
   own documents *and*, routinely, root ones (a rule file, `plan.md`, the
   operational layer). If the run is committed — `R-GIT-2`, only when asked —
   that is **two commits, submodule first**
   (`workflows/submodule_commit_order.md`). A root commit whose submodule
   pointer was never bumped leaves the finding half-landed.

Correct prematurely-ticked checkboxes. Do not renumber stable stage ids even
if you resequence the build order.

---

## STOP AND ASK — do not decide these alone

These are not the audit's calls to make. Record the question at the resume
marker (DELIVERABLE 6) and stop on it:

- **Two design documents contradict each other and both read as
  authoritative.** Angle 2 asks you to decide which is right, and that holds
  for a drift you can trace to a date or a stage. Where both readings are
  deliberate, it is a requirements question, not an editorial one.
- **A test cannot pass without widening a tolerance, relaxing a gate, or
  adding an exemption.** Each of those is a written decision with a stated
  reason; weakening one to turn a build green inverts what the gate exists for.
- **You cannot run the real build. Say so.** Do not substitute a hand-rolled
  compiler command for the project's own build entry point. That has produced
  stages reported green whose build was red, and it is the most expensive
  mistake made under this prompt.

A module's binding may **extend** this list with its own; it never shortens it.

---

## WORKING WITH THE USER

The user owns the requirements and the intent; they are not tracking
implementation at code level. Ask in plain terms, tied to a concrete decision,
never a code-level question they cannot evaluate. Keep the list short and
high-leverage — do not ask what you can resolve by reading or running.
