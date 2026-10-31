# LAB-WP-08 part 1, rework 1 — stale test, no_ref_sync counting, a renumber drill that breaks identity

## Allowed changes (in addition to part 1's)
- `modules/vantage-lab/tests/test_car_scenarios.py`: the refused pairs of
  `test_lab31_lab32_the_car_refuses_verbs_it_does_not_have` become `({"teleport": ["A"]}, {})`
  and `({}, {"drop_run": "all"})` (two still-unknown keys).
- `modules/vantage-lab/src/lab_tools/reference.py`, `ReferenceResim._plan` only: with
  `use_ref_sync=False` a missing `refSync` topic is allowed and only the ports present are
  compared; with `use_ref_sync=True` a missing `refSync` stays an error.
- **Orchestrator design-row edit (fixture fix, no new verb):** in
  `modules/vantage/docs/VANTAGE_Lab_Design.md` §6.2's drill table, replace the `renumber` row's
  cells with: Scenario `renumber`; Block `car: {counter_jump: [{source: X, at_counter: 10, by: 1000}], renumber: [T]}`
  **in `data_triggered`**; Resim case adds `by_data`; Expected "identity broken on `T`'s
  output". Then add one sentence under the table: "`renumber` acts only where a component's
  trigger counter differs from its own run count, so its drill uses an input-triggered
  component after a counter jump." Move the scenario from `running_example.yaml` to
  `data_triggered.yaml` accordingly, and update `tests/unit/test_topology.py` /
  `tests/test_car_drills.py` to match.

## Steps
1. Apply the three changes.
2. In `tests/test_car_drills.py`: count `no_ref_sync`'s mismatches with `use_ref_sync=False`
   (assert above 0, never a fixed number; `expect: diverges`); the `renumber` drill shows `T`'s
   output `measurement_counter` differs from its control's in every run after the jump, and
   the reference re-run by refSync reports it (equal outputs fail or the identity check
   fires — say which).

## Exit check
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests -q"` → all pass.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` → PASS.
- `git -C modules/vantage-lab status --short`; `git -C modules/vantage diff --stat` → list.

## Must not
- commit, push; add a verb; change any other design row; weaken a test so it passes.

## Report back
Done / not done; files changed; exit check output with seconds; boxes; deviations; open questions.
