Your role: read .claude/agents/vantage-mechanic.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-09c-R1 — gate G3: the jump case's "can fail" check corrected, three gaps closed (jump completeness, repeated counters, `SYT-THR-01` logging times); then the boxes (`IMP-0043`, vantage `c1`)

The rework of `VNT-WP-09c`. Its new file `modules/vantage/tests/system/test_vnt_gate_g3.py` is in
the working copy, untracked: **build on it, never revert it.** It failed one case,
`SYT-EQO-01.c1` on `running_example/base/jump`, on a check the orchestrator's prompt added and the
spec does not have: "each simulated stage must still have a compared message at or after the
jump". `B` and `D` have memory, so after a jump every run of theirs is badged `KIND_WARMING_UP` to
the end (`D28 (4)`, `SYT-STP-05.c1`), and `SYS-0042`'s Accept leaves those outputs out. No output
differed.

The edits do two things. **G1–G8** correct that check: every simulated stage has a compared
message (before the jump counts), and some stage has one at or after the jump. **G9–G14** close
three ways the gate could pass while wrong, found in the orchestrator's second review:
- the jump case had no completeness check, so a dropped run before or after the jump passed —
  now its reproduced counters before the jump must be the recording's first ones, and those
  compared after it the recording's from the first of them on;
- pairing by counter keeps the first recorded message of a counter, so a repeated counter could
  pair a run with the wrong one — now a repeated recorded counter is a difference (none repeats in
  today's 25 exact cases);
- `SYT-THR-01` compared each topic's messages in order but never their logging times, while
  `SYS-0039`'s Shall says "every port of every step" — now both recordings must log the same topics
  at the same times in the same file order.

The orchestrator dry-ran all fourteen edits on a copy of the file: 66 passed (31 s). It also
planted a dropped `A.out` run after the jump and a dropped `E.out` run before it: each was
reported. Every judgment is made here; three parts, in order: **A** the edits; **B** the runs;
**C** the boxes.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- Run every command from native Windows (PowerShell or cmd), not WSL.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.
- `program/prompts/VNT-WP-09c.md` Part C is the box rule this prompt's Part C repeats.

## Allowed changes
- `modules/vantage/tests/system/test_vnt_gate_g3.py`: Part A's edits only.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md`: Part C's boxes and sentences only.
- Everything else is read-only.

## Part A — the edits (exact)
Each anchor and each new text is the exact content of a fenced block (the fence lines themselves
excluded). Apply G1–G14 in order to `modules/vantage/tests/system/test_vnt_gate_g3.py`, each by
exact-string replacement, keeping its LF line endings. If an anchor is not found exactly once,
stop and report it; never adjust the text.

**G1** · replace the anchor with the new text.

Anchor:
````
  a stage's reproduced messages logged at a step where the tap shows its `KIND_WARMING_UP` count grow are left out, and
  each simulated stage must still have a compared message at or after the jump;
````
New text:
````
  a stage's reproduced messages logged at a step where the tap shows its `KIND_WARMING_UP` count grow are left out;
  each simulated stage must have a compared message, and some stage one at or after the jump. A stage with memory
  stays warming up to the end after a jump (`D28 (4)`, `SYT-STP-05.c1`), so all its post-jump outputs are left out;
````

**G2** · replace the anchor with the new text.

Anchor:
````
def _differences(case: LabCase, produced: Recording, recorded: Recording, tapped=None) -> tuple[list[str], dict[str, int]]:
    """`(differences, compared per stage)` of a run against the recording: each as `topology/scenario/case: stage port
    step N: why`. `tapped` is the jump case's tap run."""
````
New text:
````
def _differences(case: LabCase, produced: Recording, recorded: Recording,
                 tapped=None) -> tuple[list[str], dict[str, int], dict[str, int]]:
    """`(differences, compared per stage, compared at or after the jump per stage)` of a run against the recording:
    each difference as `topology/scenario/case: stage port step N: why`. `tapped` is the jump case's tap run."""
````

**G3** · replace the anchor with the new text.

Anchor:
````
    compared: dict[str, int] = {}
````
New text:
````
    compared: dict[str, int] = {}
    after_jump: dict[str, int] = {}
````

**G4** · replace the anchor with the new text.

Anchor:
````
                if t >= jump_to_ns or tapped is None:
                    compared[name] += 1
````
New text:
````
                compared[name] += 1
                if tapped is not None and t >= jump_to_ns:
                    after_jump[name] = after_jump.get(name, 0) + 1
````

**G5** · replace the anchor with the new text.

Anchor:
````
    return found, compared
````
New text:
````
    return found, compared, after_jump
````

**G6** · replace the anchor with the new text.

Anchor:
````
    found, compared = _differences(case, produced, Recording(case.recording), tapped)
    assert compared,
````
New text:
````
    found, compared, after_jump = _differences(case, produced, Recording(case.recording), tapped)
    assert compared,
````

**G7** · replace the anchor with the new text.

Anchor:
````
        f"not fail: {compared}")
    assert not found,
````
New text:
````
        f"not fail: {compared}")
    if tapped is not None:
        assert after_jump, (
            f"SYT-EQO-01.c1: {topology}/{scenario}/{name}: no stage compared at or after the jump, so the jump could not "
            f"fail: {compared}")
    assert not found,
````

**G8** · replace the anchor with the new text.

Anchor:
````
    found, _compared = _differences(case, produced, Recording(case.recording), tapped)
````
New text:
````
    found, _compared, _after_jump = _differences(case, produced, Recording(case.recording), tapped)
````

**G9** · replace the anchor with the new text.

Anchor:
````
- every other case also requires each topic's reproduced counters to equal its recorded counters, in order;
````
New text:
````
- every other case also requires each topic's reproduced counters to equal its recorded counters, in order; in the
  jump case the reproduced counters before the jump are the recording's first ones, and those compared at or after it
  the recording's from the first of them on, none dropped;
- a topic whose recorded counters repeat is a difference, since pairing by counter could not hold;
- `SYT-THR-01` also requires both recordings to log the same topics at the same logging times in the same file order
  (`SYS-0039`: every port of every step);
````

**G10** · replace the anchor with the new text.

Anchor:
````
            theirs: dict[int, bytes] = {}
            for _i, _t, payload in recorded.of(topic):
````
New text:
````
            recorded_counters = recorded.counters(topic)
            if len(set(recorded_counters)) != len(recorded_counters):
                found.append(f"{where}: {name} {port}: a counter repeats in the recording, so pairing by counter cannot hold")
            theirs: dict[int, bytes] = {}
            for _i, _t, payload in recorded.of(topic):
````

**G11** · replace the anchor with the new text.

Anchor:
````
            counters = []
            for _i, t, payload in produced.of(topic):
````
New text:
````
            counters = []
            timed: list[tuple[int, int]] = []  # (logging time, counter) of each compared message
            for _i, t, payload in produced.of(topic):
````

**G12** · replace the anchor with the new text.

Anchor:
````
                counters.append(counter)
                step = _step(produced, t)
````
New text:
````
                counters.append(counter)
                timed.append((t, counter))
                step = _step(produced, t)
````

**G13** · replace the anchor with the new text.

Anchor:
````
                found.append(f"{where}: {name} {port}: reproduced counters {counters[:4]}... "
                             f"differ from recorded {recorded.counters(topic)[:4]}...")
````
New text:
````
                found.append(f"{where}: {name} {port}: reproduced counters {counters[:4]}... "
                             f"differ from recorded {recorded.counters(topic)[:4]}...")
            if tapped is not None:
                before = [c for t, c in timed if t < jump_to_ns]
                after = [c for t, c in timed if t >= jump_to_ns]
                if before != recorded_counters[: len(before)]:
                    found.append(f"{where}: {name} {port}: reproduced counters before the jump {before[:4]}... are not "
                                 f"the recording's first {len(before)}")
                if after and (after[0] not in recorded_counters
                              or after != recorded_counters[recorded_counters.index(after[0]):]):
                    found.append(f"{where}: {name} {port}: reproduced counters after the jump {after[:4]}... are not "
                                 f"the recording's from counter {after[0]} on")
````

**G14** · replace the anchor with the new text.

Anchor:
````
    assert not diffs, (f"SYT-THR-01.c1: {topology}/{scenario}/{name} N={threads}: any difference ({len(diffs)}); first: "
                       f"{_first_difference_text(single, many, diffs)}")
````
New text:
````
    assert not diffs, (f"SYT-THR-01.c1: {topology}/{scenario}/{name} N={threads}: any difference ({len(diffs)}); first: "
                       f"{_first_difference_text(single, many, diffs)}")
    order = [(t, topic) for topic, t, _p in single.messages]
    other_order = [(t, topic) for topic, t, _p in many.messages]
    first = next((i for i, (x, y) in enumerate(zip(order, other_order)) if x != y), min(len(order), len(other_order)))
    assert order == other_order, (
        f"SYT-THR-01.c1: {topology}/{scenario}/{name} N={threads}: message {first} is logged at another step or on "
        f"another port: --threads 1 {order[first:first + 1]} / --threads {threads} {other_order[first:first + 1]}")
````

## Part B — the runs
1. `python.exe -m pytest -q -rs tests/system/test_vnt_gate_g3.py` in `modules\vantage`.
   Expected: 66 passed, 0 failed, 0 skipped. Any other result: stop, report it, do Part C not at all.
2. The full suite: `python.exe -m pytest -q -rs tests/unit tests/system` in `modules\vantage`
   (last 1553 passed, 1 failed, 62 skipped; expected 1554 passed, 0 failed, 62 skipped). Keep its
   skip list (`-rs`) for step 4.
3. Root: `py -3.12 scripts\check_invariants.py`;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
   Report the `PASS` line and the `packages:` line, with seconds.

## Part C — the boxes (only if steps 1–3 all pass)
4. In `modules/vantage/docs/VANTAGE_Implementation_Design.md`, for each of these rows:
   `IMP-0006`, `IMP-0008`, `IMP-0016`, `IMP-0019`, `IMP-0034`, `IMP-0035`, `IMP-0040`, `IMP-0043`,
   `IMP-0053`, `IMP-0056` — first check that none of the test ids its "Closed by" names appears in
   step 2's skip list, in either form (`SYT-SEL-12` or `test_syt_sel_12_…`; `ANL-02` or
   `test_anl_02_…`) (if one does, leave that row as it is and report it). Then set its box to
   `` `[x]` `` and delete its sentence from ` Closed by` (with the one space before it) through
   ``(`WP-09`).`` inclusive. `IMP-0043` has no such sentence: only its box changes.
5. Then the package lines `WP-02`, `WP-04`, `WP-07`, `WP-09`, `WP-11`: `- [~]` → `- [x]`, and
   delete from ` Closed by` (with the one space before it) to the end of the line. Touch no other
   line — `IMP-0052`'s old sentence included.
6. Rerun step 3's `trace_check --status`. Expected: `PASS -- 127 requirements, 56 tests, no
   findings.` and `packages: 13 done, 0 started, 0 open, of 13`. If not, report the output.
7. `git -C modules/vantage status --short`; `git -C modules/vantage diff --stat` equal with and
   without `--ignore-cr-at-eol`.

## Exit check (run all, report output and seconds)
- Steps 1, 2, 3, 6 and 7, each with its counts and seconds.

## Must not
- change anything outside "Allowed changes", or any text beyond G1–G14 and Part C
- add a skip, tolerance or exemption
- commit or push

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
