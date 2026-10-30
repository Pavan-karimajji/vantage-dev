# LAB-WP-02 — template, generator and the running example's libraries

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers may edit other files; touch only the allowed ones.
- `VANTAGE_DEV_PLAN.md` §2 (D14, D20)
- `modules/vantage/docs/VANTAGE_Lab_Design.md` (frozen): §2, §3 (description file and the
  loader's checks), §4 (template, arithmetic, generator, the one standard build, the
  protobuf duplicate-registration risk), §6.1 (the running example file, scenario `base`
  only), §7 (the two calibration keys), §8 (a path is a promise), §9 rows of package
  `LAB-WP-02`: `LAB-07`..`LAB-18` and `LAB-54`
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` rows `IMP-0013`..
  `IMP-0015`, `IMP-0042` (the component kit: `CycleStamp`, `RefSyncBuilder`, in
  `modules/interfaces/include/adas/`) and `IMP-0022`..`IMP-0028` (what the template lands)
- `modules/interfaces`: `adas_generate_sil_ports`, `adas_pack_config_bundle` (CMake),
  `scripts/gen_sil_ports.py`, `include/adas/adas_sil_abi.h`, `sig_status.hpp`
- `.claude/rules/architecture.md`, `style.md` (headers; `COMPONENT: VANTAGE_LAB`),
  `naming.md` (R-NAME-1..3), `sim.md` R-SIM-3a, R-SIM-4, R-SIM-22, `testing.md`
- What LAB-WP-01 left: `modules/vantage-lab` (stub, `conf/build.yml`, CMake with an empty
  `lab_add_topology`, `pyproject.toml`), and `adas.lab.LabSample` / `LabImage` in interfaces

## Goal
`build.bat -P base -t sil -p vs2026` in `modules/vantage-lab` generates the running example
at configure time and builds one shared library per component (`A`..`E`), each in its own
folder with its config bundle beside it and an `index.json` per topology; each library
loads and answers `adasAbiVersion` and `adasManifest` with the ports of §4.2, including
`control`, `refSync` and `compState`.

## Allowed changes
- In `modules/vantage-lab`: the files of rows `LAB-07`..`LAB-18` and `LAB-54`; unit tests for
  the loader and the generator under `tests/unit/` (the design names no file for them; keep
  them there, each test naming the row it checks); a minimal smoke test that loads each
  built library with `ctypes` and reads its manifest (under `tests/unit/`, skipped with a
  printed reason when the build tree is absent). `.gitignore` if needed.
- The boxes of `LAB-07`..`LAB-18`, `LAB-54` and `LAB-WP-02` in
  `modules/vantage/docs/VANTAGE_Lab_Design.md`, only after their checks pass.
- Everything else is read-only. No change to `interfaces`, the RCT documents, root
  scripts or any copied machinery file.

## Steps
1. `LAB-07` `topology.py`: load a topology file; every check of §3 raises `TopologyError`
   naming file and key. Unit tests: one per check, plus the running example loading clean.
2. `LAB-54` `catalogue/provisional.yaml` (calibration part only) and `LAB-15`/`LAB-16`
   `generate.py`: standard library and PyYAML only; writes the files of §4.2 per component;
   `write_default_yaml` refuses a component without its two keys (component and key named);
   the two `..._AFTER_RUNS` keys written as 0. Unit tests: input order = manifest order =
   `RefSyncBuilder` order for `B`; the refusal; byte-identical output for the same input.
3. `LAB-08`..`LAB-14` template: exactly the `exec` shape of §4.1 using the interfaces kit;
   no thread, clock, file, random value, unordered container or uninitialised member in
   `lab_component.hpp.in`; calibration load, hang and crash switches in `lab_sil.cpp.in`.
4. `LAB-17` `lab_components.cmake` and `LAB-18` `catalogue/running_example.yaml` (scenario
   `base` only): configure-time generation, one library and one bundle folder per
   component, compile definitions of §4.3, `index.json`.
5. Build; load every library of the topology into **one** Python process with `ctypes` and
   call `adasManifest` on each. If protobuf reports a duplicate registration, apply the
   standard fix the existing SIL libraries use and say which; if none applies, stop and
   report.
6. Tick only rows whose checks passed. The `RCT:IMP` rows are not yours to tick: they close
   when their `SYT` tests pass in `LAB-WP-03`.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && py -3.12 scripts\build.py -P base -t sil -p vs2026"` → builds 5 libraries; list each library path and bundle folder from `index.json`.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests\unit -q"` → all pass; report counts and the one-process load result.
- `grep -nE "std::(thread|chrono|random|unordered)|rand\(|time\(|fopen|ifstream" modules/vantage-lab/template/lab_component.hpp.in` → no output.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean.
- `git -C modules/vantage-lab status --short`; `git -C modules/interfaces status --short`
  (unchanged by you) → list.

## Must not
- commit, push, or change files outside "Allowed changes"
- write the harness, the car, the recorder or any other topology (later packages)
- put a threshold or default value in C++ or Python code; every value is a calibration key
- decide anything the design leaves open; report it

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
