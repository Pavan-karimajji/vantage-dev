# Vantage program — how the work is run

For the **orchestrator**: the session that plans, writes worker prompts and
reviews results. What is built, and in which order, is in `VANTAGE_DEV_PLAN.md`;
this file says **how** each step is carried out. It holds no status: progress is
read from the plan documents' checkboxes (§3), the history from
`ORCHESTRATION_LEDGER.md`.

## 1. Roles

| Role | Who | Does | Never does |
|---|---|---|---|
| **Owner** | the user | decides; approves commits, pushes, scope and contract changes | — |
| **Orchestrator** | Opus, high effort | picks the next work package, writes one prompt for it, reviews the result, records the verdict | edits code or documents itself, except to fix a ledger entry |
| **Worker** | one of the three worker agents below | carries out exactly one work package from one prompt and reports back | widens scope, commits, pushes, or decides an open question |

**Which worker.** The orchestrator picks the agent type by the kind of work and
launches it by `subagent_type` alone. It never passes `model` or `effort`: each
agent's model and effort are set once, in its file under `.claude/agents/`, and
a value passed at launch would override that one place.

| Kind of work package | Agent type |
|---|---|
| planning: requirement sets, design rows, test specs, architecture documents, contract changes (step 8 included) | `vantage-planner` (Opus, high) |
| migration-register rows (6c-6e); the orchestrator checks every disposition and range against the frozen architecture (6a) before accepting | `vantage-builder` (Sonnet, high) |
| building with judgment: code, debugging a failing build or test | `vantage-builder` (Sonnet, high) |
| mechanical: an exact edit, a rename, wiring a build list, running a fixed command list | `vantage-mechanic` (Sonnet, medium) |

The model and effort in brackets are for reading; each agent's file under `.claude/agents/` is the one place they are set (D19).

A package that mixes kinds is split before it is prompted (§4). The imported agent
`low-effort-worker` is not a program worker.

## 2. Start of every orchestrator session

1. Read `VANTAGE_DEV_PLAN.md` (decisions §2, gates §5), this file, and the last
   ten entries of `ORCHESTRATION_LEDGER.md`.
2. Read the current status (§3).
3. Pick the **first work package whose gate is green and whose box is `[ ]` or
   `[~]`** in the writing order (plan §6) or build order (each plan's work
   packages). A `[~]` row resumes by its own `closed by` condition.
4. If nothing is pickable, or the next step needs a decision, **ask the owner**
   (§7) instead of inventing work.

## 3. Where status comes from

| Plan | Status command |
|---|---|
| Plan B (workspace) | the boxes in `program/WORKSPACE_Plan.md` |
| Plan A (contract) | `python .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract --status` |
| Plan C (Vantage) | `python .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status` |

Status is **computed, never typed** (R-REQ-6a). A box is ticked by the worker in
the same change that does the work, and only after its exit check passes.

## 4. One work package, one prompt

A work package is small enough to finish and verify in one worker session:
one module, an explicit file list, one exit check. If it is not, the
orchestrator splits it **before** prompting, and the split is recorded in the
plan document (a new row), not only in the prompt.

### 4.1 Prompt template (every prompt has exactly these sections)

```
# <WP id> — <one-line title>

## Context (read these, nothing else unless a step needs it)
- VANTAGE_DEV_PLAN.md §<n>
- <the plan/design rows this WP lands, by id>
- <rules/skills from .claude/routing.md for this task>

## Goal
<one or two sentences: what is true when this is done>

## Allowed changes
- <exact files or folders that may be created or edited>
- Everything else is read-only.

## Steps
1. ...

## Exit check (run all, report output and seconds)
- <commands: build, tests per R-TEST-1, trace_check where relevant>

## Must not
- commit, push, or change files outside "Allowed changes"
- decide anything listed under "Open" — report it instead
- add features, abstractions or error handling not asked for

## Report back in this shape
<the report shape, §4.2>
```

The prompt is **self-contained**: the worker starts with no memory of earlier
sessions. Everything it needs is either in the prompt or in a file the prompt
names.

### 4.2 What the worker returns

1. **Done / not done**, in one line.
2. **Files changed**, one line each with what changed.
3. **Exit check output**: each command, pass/fail, seconds (R-TEST-7).
4. **Boxes ticked** (row ids) and any `[~]` with its `closed by` condition.
5. **Deviations** from the prompt, each with the reason.
6. **Open questions**, each with the worker's recommendation.

## 5. Review checklist

The orchestrator checks every result against this list before accepting it.

**Scope and process**
- [ ] Only files under "Allowed changes" were touched.
- [ ] Every exit-check command was run and passed, with output shown.
- [ ] Boxes were ticked only for rows whose exit check passed; every `[~]` says what closes it.
- [ ] Nothing was committed or pushed.

**House rules** (`.claude/rules/`)
- [ ] R-STYLE: file header on every new source file; minimal diff (no rewritten blocks around a small change).
- [ ] R-NAME: naming vocabulary, unit suffixes, ALL_CAPS calibration keys, snake_case proto fields.
- [ ] R-ARCH / R-IFACE: components depend only on interfaces; protobuf only across boundaries; `sig_header` rules.
- [ ] R-BUILD: standard component build only; no private conanfile, presets or work area.
- [ ] R-TEST: scoped tests while working; the full gate only before a commit.
- [ ] R-SIM (with the vantage-dev override): no grid assumptions; inputs picked by number.

**Requirement and design documents** (when the work package writes them)
- [ ] Each row has the fixed anatomy: one obligation, a falsifiable Accept, Verify, Trace (R-REQ-3).
- [ ] Every threshold nobody supplied is `⊘`, never a plausible number (R-REQ-10).
- [ ] Design rows are in the present or future tense; no narration of what happened (R-REQ-14).
- [ ] `trace_check.py --set <dir>` is clean.

**Content**
- [ ] No company names except L&T EPS where code requires it; no reference-tool names or local reference paths.
- [ ] Nothing contradicts a decision in `VANTAGE_DEV_PLAN.md` §2. If it must, it is escalated, not merged.

## 6. Verdicts

| Verdict | When | Next step |
|---|---|---|
| **Accept** | every applicable checklist item holds | record in the ledger; propose the commit to the owner (§8) |
| **Rework** | a fixable miss | a follow-up prompt naming only what to fix; **two reworks on one package → escalate** |
| **Escalate** | a decision is needed, the plan is wrong, or rework failed twice | ask the owner (§7) with options and a recommendation |

## 7. When to stop and ask the owner

- Any change to the resim contract after its gate (G1) is green.
- Any change to a decision in `VANTAGE_DEV_PLAN.md` §2, or to a gate.
- Any amendment of a frozen requirement or of a `.claude` rule.
- Creating a remote repo, pushing, or committing.
- A worker's open question that changes scope, a contract or a public name.
- Anything that would touch 1v-superproject.

Ask with: the question in one sentence, two or three options, the
recommendation, and what each option costs.

## 8. Commits

The owner approves every commit. The orchestrator proposes:
- which repo(s), **submodule first, then the superproject pointer** (R-GIT-1);
- the commit message;
- the exit-check evidence the commit rests on (from the accepted report).

Decisions the owner makes while answering an escalation are added to
`VANTAGE_DEV_PLAN.md` §2 (dated) in the next accepted change.

## 9. The ledger

Every prompt and every verdict gets one entry in `ORCHESTRATION_LEDGER.md`,
newest at the bottom, in the format given there. The ledger is history: it
records what happened and is never used as the source of status.
