# DEC-3 — `CycleStamp` takes its start count; the lab sets it by calibration key (IMP-0013)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never commit, and never run `git checkout`,
  `git stash`, `git reset`, `pkill` or `kill`: if a step seems to need one, stop and report.
  Another worker is writing `modules/vantage/docs/` (the new Vantage set, 6a §1/§2.3 and the
  register); of that folder you may touch only the lab design rows named below.
- Owner decision (2026-10-31): `CycleStamp` takes the own count **before the first run** in its
  constructor (production 0); a lab component passes its calibration key `LAB_<C>_START_COUNT`;
  the harness stops writing the count into the component's memory. A design-row edit of
  `RCT:IMP-0013`, not a contract change.
- `modules/interfaces/include/adas/cycle_stamp.hpp`, `tests/unit/test_component_kit.cpp`;
  `RCT_Implementation_Design.md` row `IMP-0013`; `RCT_Test_Spec.md` `SYT-HDR-03`
- `modules/vantage-lab/template/lab_component.hpp.in` (where `CycleStamp` is constructed),
  `src/lab_tools/generate.py` (how `LAB_<C>_MAX_AGE_US`/`RECOVERY_RUNS` reach a component, the
  `calibration_key` helper), `tests/harness/lab_harness.py` (`seed_cycle_count`, the memory
  search), `tests/harness/test_contract_harness.py` (`SYT-HDR-03`), the bundle-variant mechanism
  the lab already has (`LAB-WP-05`)
- `modules/vantage/docs/VANTAGE_Lab_Design.md` §3 (the description file and its keys), §4.1
  (the template), §9 row `LAB-22`
- `.claude/rules/naming.md` (R-NAME-3), `.claude/rules/build.md`, `.claude/rules/testing.md`,
  `program/VANTAGE_PROGRAM.md` §5 (the package-build rule)

## Goal
`CycleStamp(std::uint32_t startCount = 0)`; every lab component reads `LAB_<C>_START_COUNT`
from its bundle (0 by default) and passes it; `SYT-HDR-03.c2` starts `B` at `0xFFFFFFFF`
through that key, with no write into memory; the rows say so.

## Allowed changes
- `modules/interfaces`: `include/adas/cycle_stamp.hpp` (the constructor), `tests/unit/test_component_kit.cpp`
  (a test for the start count, and the wrap from `0xFFFFFFFF`), `docs/resim_contract/RCT_Implementation_Design.md`
  (row `IMP-0013`: its Artifact text and box only).
- `modules/vantage-lab`: `template/lab_component.hpp.in`, `src/lab_tools/generate.py` (the key in
  each component's `default.yaml`, value 0; it is not a provisional value, so the generator does
  **not** refuse a component without it), `tests/harness/lab_harness.py` (remove the memory
  write), `tests/harness/test_contract_harness.py` (`SYT-HDR-03.c2` through a bundle variant).
- `modules/vantage/docs/VANTAGE_Lab_Design.md`: one sentence in §3 naming the key and its default,
  one in §4.1 where the template constructs `CycleStamp`, and `LAB-22`'s text if it names the
  memory write. No new row.
- Everything else is read-only.

## Steps
1. The constructor stores the start count; `begin` still adds 1 and wraps; no other behaviour
   changes. A unit test: start 0 → first stamp 1; start `0xFFFFFFFF` → first stamp 0.
2. `IMP-0013` becomes: `include/adas/cycle_stamp.hpp::adas::common::CycleStamp(std::uint32_t startCount = 0)`,
   `begin(const CycleControl&)`, `stamp(uint32_t sigStatus, SignalHeader*)` — the constructor
   takes the own count before the first run (production 0; a lab component passes its calibration
   key `LAB_<C>_START_COUNT`); `begin` adds 1 (wrapping); `stamp` copies counter and time from the
   control and writes own count and sticker. Box `[~]`, closed by `SYT-HDR-03.c2` passing through
   the key; `[x]` at step 6.
3. The lab: the generator writes `LAB_<C>_START_COUNT: 0` per component; the template reads it
   and constructs `CycleStamp` with it.
4. The harness: `SYT-HDR-03.c2` builds or selects a bundle variant of `B` with the key set to
   `0xFFFFFFFF`; `seed_cycle_count` and the memory search it uses are removed.
5. Builds (`VANTAGE_PROGRAM.md` §5): the real `interfaces` package build (the kit header ships),
   the `interfaces` C++ unit tests through the standard build's test target, then the real lab
   build with `--update-lock` (the newer `interfaces` revision, R-BUILD-7).
6. The lab's whole suite and `interfaces` `tests/python`; tick `IMP-0013` `[x]` when
   `SYT-HDR-03.c2` passes through the key.

## Exit check (run all, report output and seconds)
- `interfaces` package build; `interfaces` C++ unit tests (count); lab build with `--update-lock`.
- Lab suite and `interfaces` `tests/python` on Windows Python (counts, seconds); name the test that
  proves `.c2` through the key.
- `grep -rn 'seed_cycle_count' modules/vantage-lab` → nothing.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  and `--status` → PASS.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean.
- `git status --short` in `modules/interfaces`, `modules/vantage-lab`, `modules/vantage` → only
  the allowed files (in `modules/vantage`, other files may be the other worker's: list them,
  don't touch them).

## Must not
- commit, push, or change files outside "Allowed changes"
- change any other behaviour of `CycleStamp` or any contract row other than `IMP-0013`
- leave a half-built package revision in the Conan cache: if a package build fails, report the
  revision it left and stop

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids).
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
