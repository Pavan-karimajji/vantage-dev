Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-08-R1 — C1: the source-check findings decided; `IsUnknownMeasurementCounter`; `ANL-03`'s test; the checks in the CI gate (vantage branch `c1`)

**Relay after `VNT-WP-07` is accepted** — both change `src/simcore/runner/cycle_loop.cpp`.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite.
- **The owner's decisions (2026-11-02), already final — apply, never re-open:**
  1. `SYS-0017` is a rule, not two exceptions: decisions read only signal headers and the two
     contract messages that exist to drive them — the recorded `refSync` (RCT C3) for selection,
     the recorded control (RCT C2) for RESTART. The check allows parsing exactly those two message
     types (`adas::common::RefSync`, `adas::common::CycleControl`) and nothing else. **No per-line
     markers.**
  2. `SYS-0031`: the unknown test is `bus::IsUnknownMeasurementCounter`, beside
     `bus::MeasurementCounterDistance` (`IMP-0053`), because 0 = unknown holds for
     `measurement_counter` only; `cycle_counter` uses 0 as a real value. The check accepts that
     helper; **a bare comparison with 0 on either counter stays a finding.**
- What exists (`VNT-WP-06-08`): `scripts/check_engine_decisions.py`, `scripts/check_counter_compare.py`,
  their tests `tests/unit/test_wp08_check_engine_decisions.py`, `test_wp08_check_counter_compare.py`;
  the findings: `ANL-01` — `control.cpp` parses `CycleControl`, `select_inputs.cpp` parses
  `RefSync`; `ANL-02` — `cycle_loop.cpp` `header.measurement_counter != 0`, `select_inputs.cpp`
  `header.measurement_counter == 0` and `entry->measurement_counter() == 0`.
  `tests/unit/test_a1_check_time_units.py` (its planted case cites `ANL-SW-14` and plants
  `hold_age_s`); `scripts/ci_gate.py` (how `check_time_units.py` is listed there).
- Rules: `.claude/rules/style.md` (minimal diffs), `naming.md`, `requirements.md` R-REQ-9 (a test
  id appears verbatim in the check or test that implements it).
- Python: vantage's own environment, `modules\vantage\.venv-sim-win32\Scripts\python.exe`.
  Never `py -3`. Root scripts: `py -3.12`.

## Part 1 — the documents (exact text; apply only this)
All under `modules/vantage/docs/`. Each anchor and each new text is the exact content of a fenced
block (fence lines excluded); apply by exact-string replacement, keeping line endings. If an
anchor is not found exactly once, stop and report it. The orchestrator dry-ran D1–D12 on a copy:
`trace_check` PASS, 108 requirements, 51 tests, no findings, `WP-08` `[x]` 4/4. **Apply D12 and
the `[x]` of `IMP-0057` and of `WP-08` (D10, D11) only if Part 2 ends with both checks clean over
the tree and every planted case caught**; otherwise leave those rows `[~]`, each ending
"Closed by <what is left>.", and report.

**D1 — `VANTAGE_System_Requirements.md`.** Replace

```
**`SYS-0017`** · `P0` · `R1` — Decisions come from the run setup and the headers alone
**Shall.** The orchestrator and input selection shall decide from the run setup and the samples' `sig_header` only, reading no clock, thread id, execution time or other payload field.
**Accept.** The source check over their files finds no clock, thread-id or timer call and no payload parse except `ReadSignalHeader`; with one such call planted, it fails.
```

with

```
**`SYS-0017`** · `P0` · `R1` — Decisions come from the run setup, the headers and the two messages that drive them
**Shall.** The orchestrator and input selection shall decide only from the run setup, `sig_header`s and the two contract messages that drive them: the recorded `refSync` (C3) for selection, the recorded control (C2) for RESTART.
**Accept.** Their source check finds no clock, thread-id or timer call and parses no type but `RefSync` and `CycleControl` besides `ReadSignalHeader`; a planted call or parse fails.
```

**D2 — `VANTAGE_System_Requirements.md`.** Replace

```
**`SYS-0031`** · `P1` · `R1` — Counters are compared only by `counterDistance`
**Shall.** The engine shall compare `measurement_counter` and `cycle_counter` values only through `counterDistance` (`RCT:SYS-0005`).
**Accept.** The source check over the engine finds no `==`, `!=`, `<`, `>`, `<=` or `>=` applied to either counter; with one planted comparison, it fails.
```

with

```
**`SYS-0031`** · `P1` · `R1` — Counters are compared only by `counterDistance`; unknown is tested by one helper
**Shall.** The engine shall compare `measurement_counter` and `cycle_counter` values only through `counterDistance` (`RCT:SYS-0005`), and test a `measurement_counter` for unknown (0) only through `bus::IsUnknownMeasurementCounter`.
**Accept.** The source check over the engine finds no `==`, `!=`, `<`, `>`, `<=` or `>=` applied to either counter, a comparison with 0 included; with one planted comparison, it fails.
```

**D3 — `VANTAGE_Test_Spec.md`.** Replace

```
**`ANL-01`** · A · fixture `F-SRC` — Decisions read no clock and no payload
```

with

```
**`ANL-01`** · A · fixture `F-SRC` — Decisions read no clock and no other payload
```

**D4 — `VANTAGE_Test_Spec.md`.** Replace

```
and over a copy with a planted `ParseFromArray` in `src/simcore/runner/select_inputs.cpp`.
```

with

```
and over a copy with a planted `ParseFromArray` on an `adas::common::VehDyn` in `src/simcore/runner/select_inputs.cpp`.
```

**D5 — `VANTAGE_Test_Spec.md`.** Replace

```
and over a copy with a planted `a.measurement_counter == b.measurement_counter` in `src/simcore/orchestrator/orchestrator.cpp`.
```

with

```
over a copy with a planted `a.measurement_counter == b.measurement_counter` in `src/simcore/orchestrator/orchestrator.cpp`, and over a copy with a planted `header.cycle_counter != 0` in `src/simcore/runner/run_stage.cpp`.
```

**D6 — `VANTAGE_Test_Spec.md`.** Replace

```
- `.c3` **PASS:** the planted `==` is reported with file and line. **FAIL:** the copy passes.
```

with

```
- `.c3` **PASS:** the planted `==` is reported with file and line. **FAIL:** the copy passes.
- `.c4` **PASS:** the planted comparison with 0 is reported with file and line. **FAIL:** the copy passes.
```

**D7 — `VANTAGE_Implementation_Design.md`.** Replace

```
for every sample entering a buffer; the only payload read behind a decision. Closed by
```

with

```
for every sample entering a buffer; besides the recorded `refSync` and control (`SYS-0017`), the only payload read behind a decision. Closed by
```

**D8 — `VANTAGE_Implementation_Design.md`.** Replace

```
for clock, thread-id and timer calls and for payload parses other than `ReadSignalHeader`; one line per finding, exit 1 on any; `--selftest` plants one of each. Closed by the two parses it finds in the tree (`control.cpp` `op_mode`, `select_inputs.cpp` `refSync`) being decided, and `ANL-01` passing (`WP-09`).
```

with

```
for clock, thread-id and timer calls and for a parse of any message type but `RefSync` and `CycleControl` (`ReadSignalHeader` aside); one line per finding, exit 1 on any; `--selftest` plants `ANL-01` `.c2`, `.c3`; `ci_gate.py` runs it.
```

**D9 — `VANTAGE_Implementation_Design.md`.** Replace

```
with an operand naming `measurement_counter` or `cycle_counter`; one line per finding, exit 1 on any; `--selftest` plants one. Closed by the three comparisons with 0 it finds in the tree (`cycle_loop.cpp`, `select_inputs.cpp` twice) being decided, and `ANL-02` passing (`WP-09`).
```

with

```
with an operand naming `measurement_counter` or `cycle_counter`, a comparison with 0 included; a `counterDistance(…)` or `MeasurementCounterDistance(…)` result is a distance, not a counter; one line per finding, exit 1 on any; `--selftest` plants `ANL-02` `.c2`..`.c4`; `ci_gate.py` runs it.
```

**D10 — `VANTAGE_Implementation_Design.md`.** Replace

```
- [~] **WP-08** — Source checks · Scan the code `WP-02` to `WP-05` write. Closed by the findings of `IMP-0037` and `IMP-0038` being decided, and `ANL-01`, `ANL-02` passing (`WP-09`).
```

with

```
- [x] **WP-08** — Source checks · Scan the code `WP-02` to `WP-05` write.
```

**D11 — `VANTAGE_Implementation_Design.md`.** Directly after the line that starts with

```
| `[~]` | `IMP-0056` |
```

insert (no blank line):

```
| `[x]` | `IMP-0057` | `SYS-0031` | `WP-08` | `EXTEND` | `include/simcore/bus.hpp`, `src/simcore/bus/identity.cpp::IsUnknownMeasurementCounter` — true for a `measurement_counter` of 0 (unknown, `RCT:SYS-0004`), beside `MeasurementCounterDistance` (`IMP-0053`); `cycle_loop.cpp` (the control counter) and `select_inputs.cpp` (`RecordedRefSync`, an entry the car read nothing for) test for unknown only through it. `cycle_counter` has none: its 0 is a real value. | `ANL-02` |
```

**D12 — `VANTAGE_Implementation_Design.md`, boxes.** In the rows of `IMP-0037` and `IMP-0038`, replace the box `[~]` with `[x]`.
## Part 2 — the code
1. `IMP-0057`: `bool IsUnknownMeasurementCounter(std::uint32_t counter)` declared in
   `include/simcore/bus.hpp` next to `MeasurementCounterDistance`, defined in
   `src/simcore/bus/identity.cpp`; the three sites above call it. Behaviour unchanged.
   gtest: 0 is unknown, 1 and `0xFFFFFFFF` are not.
2. `check_engine_decisions.py`: a parse (`ParseFromArray`, `ParseFromString`, `ParseFromIstream`,
   … whatever the script already matches) is allowed exactly when the object parsed is declared
   in the same file as `adas::common::RefSync` or `adas::common::CycleControl`; any other type,
   or a type it cannot tell, is a finding. No per-line marker. `--selftest` plants `ANL-01` `.c2`
   (clock call) and `.c3` (`adas::common::VehDyn ego; ego.ParseFromArray(…)` in
   `select_inputs.cpp`), and also shows a planted parse of an allowed type is **not** reported.
3. `check_counter_compare.py`: a call to `IsUnknownMeasurementCounter(…)` is not a comparison;
   a bare comparison with 0 on either counter is still a finding. `--selftest` plants `ANL-02`
   `.c2`, `.c3` and `.c4` (`header.cycle_counter != 0` in `src/simcore/runner/run_stage.cpp`).
4. Both scripts' tests updated to the new cases, citing `ANL-01` / `ANL-02` and the case ids
   verbatim.
5. `ANL-03`: add to `tests/unit/test_a1_check_time_units.py` a test that plants
   `double step_time = 0;` in a copy of `src/simcore/orchestrator/event_queue.cpp` and asserts it
   is reported, citing `ANL-03` `.c2` verbatim. Keep the existing `ANL-SW-14` test as it is.
6. `scripts/ci_gate.py`: run `check_engine_decisions.py` and `check_counter_compare.py` the way it
   runs `check_time_units.py` (same list, an output file each). Show the gate's own tests, if any,
   still pass.
7. Run both scripts over the real tree: exit 0, no finding.

## Builds, suites (once, at the end)
8. `build.bat -t sil -p vs2026`, `-t gtest` (C++ suite; the count `VNT-WP-07` leaves), `-t package`
   in `modules\vantage`; Python `tests/unit tests/system` in its own environment (the count
   `VNT-WP-07` leaves); `py -3.12 scripts\check_invariants.py` at the root;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.

## Exit check (run all, report output and seconds)
- Each build command: pass/fail, seconds; C++ and Python counts before and after.
- Each script: the run over the tree (output, exit code) and `--selftest` output.
- `ci_gate.py`'s two new entries (the lines) and its tests.
- `check_invariants.py` clean; `trace_check` PASS, the `WP-08` line.
- `git -C modules/vantage status --short`; `git diff --stat` equal with and without
  `--ignore-cr-at-eol`.

## Must not
- add a per-line marker or an exemption list to either check
- add an unknown helper for `cycle_counter`, or change `counterDistance`,
  `MeasurementCounterDistance` or anything under `modules/interfaces`
- change any document text beyond D1–D12
- decide anything left open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
