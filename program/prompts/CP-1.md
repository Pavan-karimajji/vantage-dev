# CP-1 — The concept page follows the frozen design (6a, D16–D18)

## Context (read these, nothing else unless a step needs it)
- The concept page: `/mnt/c/ws/lt_learning/sim/vantage_concept.html` (outside every
  repo, not under git; a backup exists, do not make another). It is a plain-English
  explainer for a beginner: overview first, the idea before any detail, short
  sentences, one fact in one place.
- `program/CONCEPT_PAGE_DIVERGENCES.md` — 11 rows plus two "also check" items: where
  the page differs from the design, and what the page must say instead.
- `VANTAGE_DEV_PLAN.md` §2, rows D13–D18 (the decisions the page must follow)
- `modules/vantage/docs/VANTAGE_Architecture.md` (frozen, 6a) — the design. Read §1,
  §2.2, §3, §5, §6, §7, §9 and §10; the rest only where a step needs it.
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md` §0, §2, §3, §4, §6 (the contract)

## Goal
Every row of the divergence file and every D16–D18 point below is true on the page,
and the divergence file lists only what is still open (nothing, if all are done).

## What the page must also say (beyond the divergence file)
1. **D16:** `cycle_counter` keeps counting through RESTART; results are compared as
   *equal outputs* (byte-identical except each header's `cycle_counter`).
2. **D17 (3):** a *counter reset* is `measurement_counter` and `cycle_counter` both
   going back (the sender restarted; counted in the event log, no badge);
   *identity broken* is `measurement_counter` going back or repeating with new
   content while `cycle_counter` keeps counting up (badge). Both compared
   wrap-aware, never with "smaller than".
3. **D18 (1):** a named sample that is not found falls back **by counter** (the newest
   sample whose `measurement_counter` is not after the wanted one), badged; the
   **time rule** ("newest not after my trigger time") is only for a stage with no
   recorded refSync, or beyond the counter fallback's maximum gap (a setting, value
   not yet decided).
4. **D18 (2):** a simulated output that does not copy its control's counter is a
   mistake of the component under test; it is logged and the engine run goes on.
5. **D18 (3):** the live measurement is written only by the writer library; when a
   worker dies, the supervisor's seal call writes the outcome and the status, and
   nothing else.
6. **D18 (5):** a *run* is one run of one component; the whole execution is an
   *engine run* (one outcome, one run id, one live measurement).
7. A recorded control is not handed over unchanged (D17 (1)): counter and time copied,
   own `cycle_counter`, sticker OK, RESTART on the first run and after a jump, else
   the recorded op mode. The readiness limit is reported in the live measurement;
   0 means never wait.

## Allowed changes
- `/mnt/c/ws/lt_learning/sim/vantage_concept.html`
- `program/CONCEPT_PAGE_DIVERGENCES.md` (delete each row as it is done)
- Nothing else. No other page in `/mnt/c/ws/lt_learning`.

## Steps
1. Read the page once, whole. Map each divergence row and each point above to the
   chapter that holds it.
2. Change the page chapter by chapter, keeping its structure, style, CSS and
   diagrams. Change a diagram only where it shows something now wrong (for example a
   pause control). Do not add chapters unless a point has no home; if you must, say why.
3. Keep beginner-first: say the idea in plain words first, then the rule. Use the
   design's names (orchestrator, runner, live measurement, writer, inspector,
   counter fallback, time rule, engine run) and define each once where it first
   appears.
4. Delete each done row from `program/CONCEPT_PAGE_DIVERGENCES.md`; keep the file's
   header. If every row is done, leave the header and one line: "None open."

## Exit check (run all, report output and seconds)
- `python3 -c "import html.parser,sys; p=html.parser.HTMLParser(); p.feed(open('/mnt/c/ws/lt_learning/sim/vantage_concept.html',encoding='utf-8').read()); print('parsed')"`
- `grep -n -i -E "samples missing|paused|pause|same place|every simulated sample equals|handed over unchanged|not matched to car inputs" /mnt/c/ws/lt_learning/sim/vantage_concept.html`
  → report every hit with one line on why it is right now.
- `grep -c -i -E "engine run|counter fallback|time rule|equal outputs|seal" /mnt/c/ws/lt_learning/sim/vantage_concept.html` → report the count.
- `cat program/CONCEPT_PAGE_DIVERGENCES.md`

## Must not
- change any file other than the two allowed
- add a claim the design does not make; where the design leaves a value open, the
  page says it is open
- name any company in new text

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each; for the page, one line per chapter touched.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation (include any place where the page
   and the design still differ and you could not fix it).
