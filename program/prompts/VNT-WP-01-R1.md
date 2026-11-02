Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-01-R1 — C1: `impl` is `kind` + `path` only (`pattern`, `search` retired); engine ABI 4 (vantage branch `c1`)

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old path that can no longer pass is removed or corrected in the same
  change, and you name it.
- **The owner's decision (2026-11-02), final:** a run setup's `stages[].impl` carries `kind` and
  `path` only, as `VANTAGE_Architecture.md`'s mapping table says; library lookup happens before
  the setup is written. `pattern` and `search` are **removed completely**, not made optional:
  they become retired keys that `SYS-0046` refuses. The schema string stays
  `adas.sim.runspec/2.0` (`c1` is unmerged). **The lab needs no change.** And
  `SIMCORE_ABI_VERSION` goes 3 → 4 for `simEngineSetThreads` (`WP-07`).
- Orchestrator's check before this prompt: no stored fixture or recording in `modules/vantage`,
  `modules/vantage-lab` or `modules/interfaces` carries the two keys (only
  `run_spec.schema.json`); the tests that write them inline are
  `tests/integration/test_it09_record_policy.cpp`, `test_it10_graph_diff.cpp`,
  `test_it11_embed_host.cpp`, `test_ut_abi_checkpoint.cpp`, `test_ut_abi_writer_and_resolver.cpp`,
  `test_ut_exe_05_exit_codes.cpp`, `tests/unit/test_ut_bus_config.cpp`,
  `test_ut_runspec_load.cpp` — grep again for Python tests and anything else.
- Where they live today: `include/simcore/runspec.hpp` (`ImplRef::pattern`, `search`),
  `src/simcore/runspec/load.cpp` (~line 118), `src/simcore/diagnostics/graph_dump.cpp:38` (the only
  engine read: prints `pattern` when `path` is empty), `src/adas_sim/runspec/emit.py`
  (`_resolve_impl`, and the path-normalising key list near line 271),
  `src/adas_sim/engine/bridge.py` (~lines 232–242), `src/adas_sim/runspec/schema/run_spec.schema.json`.
- Rules: `.claude/rules/style.md` (minimal diffs), `testing.md`, `requirements.md` R-REQ-9.
- Python: vantage's own environment, `modules\vantage\.venv-sim-win32\Scripts\python.exe`.
  Never `py -3`. Root scripts: `py -3.12`.

## Part 1 — the documents (exact text; apply only this)
All under `modules/vantage/docs/`. Each anchor and each new text is the exact content of a fenced
block (fence lines excluded); apply by exact-string replacement, keeping line endings. If an
anchor is not found exactly once, stop and report it. The orchestrator dry-ran D1–D7 on a copy:
`trace_check` PASS, 109 requirements, 51 tests, no findings.

**D1 — `VANTAGE_System_Requirements.md`.** Replace

```
**Shall.** The engine shall refuse at load a run setup carrying `delay_steps`, `grid_step_ns`, `order` or any key its schema does not name.
```

with

```
**Shall.** The engine shall refuse at load a run setup carrying `delay_steps`, `grid_step_ns`, `order`, `impl.pattern`, `impl.search` or any key its schema does not name.
```

**D2 — `VANTAGE_Test_Spec.md`.** Replace

```
**Steps.** To copies of `running_example` `cut_c`'s setup add, one per copy, `delay_steps` to one input, `grid_step_ns` and `order` at the top level, and an unknown key `colour` to one stage; run each.
```

with

```
**Steps.** To copies of `running_example` `cut_c`'s setup add, one per copy, `delay_steps` to one input, `grid_step_ns` and `order` at the top level, `pattern` to one stage's `impl`, and an unknown key `colour` to one stage; run each.
```

**D3 — `VANTAGE_Test_Spec.md`.** Replace

```
- `.c2` **PASS:** `colour` gives a load error naming it and its stage. **FAIL:** a run starts, or the key is ignored.
```

with

```
- `.c2` **PASS:** `colour` gives a load error naming it and its stage. **FAIL:** a run starts, or the key is ignored.
- `.c3` **PASS:** `impl.pattern` gives a load error naming it and its stage. **FAIL:** a run starts, or the key is ignored.
```

**D4 — `VANTAGE_Implementation_Design.md`.** Replace

```
— a key the run setup schema does not name, `delay_steps`, `grid_step_ns` and `order` included, is a load error
```

with

```
— a key the run setup schema does not name, `delay_steps`, `grid_step_ns`, `order`, `impl.pattern` and `impl.search` included, is a load error
```

**D5 — `VANTAGE_Implementation_Design.md`.** Replace

```
`SIMCORE_ABI_VERSION` 3. Closed by
```

with

```
`SIMCORE_ABI_VERSION` 4 (3 until `WP-07` added `simEngineSetThreads`). Closed by
```

**D6 — `VANTAGE_Architecture.md`.** Replace

```
| `stages[].name`, `mode`, `impl`, `abi_version`, `config_bundle_sha256` | kept | as in `R-SIM-10`; become `MeasStage.name`, `mode`, `impl` |
```

with

```
| `stages[].name`, `mode`, `impl`, `abi_version`, `config_bundle_sha256` | kept | as in `R-SIM-10`; become `MeasStage.name`, `mode`, `impl` |
| `stages[].impl.pattern`, `impl.search` | gone | the library is found before the setup is written, so `impl` is `kind` and `path` only (§4); refused at load if present |
```

**D7 — `VANTAGE_Implementation_Design.md`.** Directly after the line that starts with

```
| `[~]` | `IMP-0049` |
```

insert (no blank line):

```
| `[ ]` | `IMP-0058` | `SYS-0046` | `WP-01` | `EXTEND` | `include/simcore/runspec.hpp::ImplRef`, `src/simcore/runspec/load.cpp::LoadRunSpec`, `src/simcore/diagnostics/graph_dump.cpp`, `src/adas_sim/runspec/emit.py`, `src/adas_sim/engine/bridge.py`, `run_spec.schema.json` — `impl` is `kind` and `path` only; `pattern` and `search` are retired keys, neither written nor read; `graph_dump` prints the kind when `path` is empty. | `SYT-RUN-09` |
```
## Part 2 — the code (`IMP-0058`, `IMP-0049`, `IMP-0031`)
1. `ImplRef` loses `pattern` and `search`. `load.cpp` accepts `impl` keys `kind` and `path`
   only; `pattern` or `search` present is a load error naming the key and its stage, in the same
   form as the other retired keys (`delay_steps`, `grid_step_ns`, `order`).
2. `graph_dump.cpp` prints the `kind` when `path` is empty.
3. `emit.py` and `bridge.py` write `impl` as `{kind, path}` only; `run_spec.schema.json` drops both
   properties and requires `kind` and `path`; `emit.py`'s path-normalising list drops `search`.
4. Every test that writes the two keys stops writing them; a test that asserted them is corrected,
   named in the report. New test: a setup with `impl.pattern` is refused naming the key and the
   stage (`SYT-RUN-09` `.c3`'s unit-level twin, beside the existing retired-key tests of
   `test_ut_runspec_load.cpp`); and one for `impl.search`.
5. `SIMCORE_ABI_VERSION` 4 in `include/simcore/abi/simcore.h`; `test_it11_embed_host.cpp`'s
   version assertion and any other reader of the number (grep C++ and Python) follow.
6. Evidence: the lab's own `running_example` `cut_c` and `all_simulated` setups, **unedited**, now
   load and run in `simengine` (`outputs.path` set if the setup leaves it empty — say how).
   Report exit code and step count. If the lab outputs are absent, make them with
   `lab_tools car` / `lab_tools setup` as `VNT-WP-07` did (gitignored).
7. Grep the whole `modules/vantage` tree (code, tests, docs outside `docs/v1`, `docs/v2`) for
   `"pattern"`, `"search"`, `impl.pattern`, `impl.search`: report what is left and why.

## Builds, suites (once, at the end)
8. `build.bat -t sil -p vs2026`, `-t gtest` (last 412/412), `-t package` in `modules\vantage`;
   Python `tests/unit tests/system` in its own environment (last 1151 passed, 87 skipped);
   `py -3.12 scripts\check_invariants.py` at the root;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
9. Boxes: `IMP-0058` `[~]`, the row gaining at its end, before the test column, "Closed by
   `SYT-RUN-09` passing (`WP-09`)."; every other box as it is.

## Exit check (run all, report output and seconds)
- Each build command: pass/fail, seconds; C++ and Python counts before and after, each test
  removed or corrected by name.
- Step 6's exit codes and step counts; step 7's grep result.
- `check_invariants.py` clean; `trace_check` PASS, the `WP-01` line.
- `git -C modules/vantage status --short`; `git diff --stat` equal with and without
  `--ignore-cr-at-eol`.

## Must not
- make `pattern`/`search` optional, keep a default for them, or change the schema string
- change anything in `modules/vantage-lab` or `modules/interfaces`
- change any document text beyond D1–D7
- decide anything left open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
