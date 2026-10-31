# PKG-1 — the writer moves to `interfaces/src/adas_recording/`; WP-12 finished on real builds

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never commit, and never run `git checkout`,
  `git stash`, `git reset`, `pkill` or `kill`: if a step seems to need one, stop and report.
  Other workers edit `modules/vantage/docs/` (not the lab design) and `modules/vantage/scripts/`
  now; touch nothing there except the lab design rows named below.
- Why: the shared recipe (`modules/toolchain/base_recipe.py`, `exports_sources`) exports `src/*`
  and `scripts/*` but not `python/*`, so the `python/` folder added by `WP-11` breaks every real
  `-t package` build of `interfaces`. Owner decision (2026-10-31): the writer's **source** moves
  to `src/adas_recording/`; the install block installs it to `python/adas_recording/` in the
  package, so consumers keep finding `<package>/python`. No toolchain change, no release.
- The state `WP-12` left (uncommitted, read its files): `modules/vantage-lab` — `recorder.py`,
  `car.py`, `generate.py`, `abi.py`, `lab_components.cmake`, `tests/test_recording.py`,
  `tests/test_car_drills.py`; the lab's build-tree `index.json` files currently point at the
  sibling checkout (a stand-in the real build rewrites).
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` rows `IMP-0043`,
  `IMP-0046`, `IMP-0047`; `RCT_Architecture.md` §6a (the writer's location, two lines);
  `modules/vantage/docs/VANTAGE_Lab_Design.md` §5.6 and rows `LAB-55`, `LAB-56`, `LAB-WP-09`
- `.claude/rules/build.md` (R-BUILD-1, R-BUILD-7), `.claude/rules/testing.md`

## Goal
`interfaces` builds a real package that ships `python/adas_recording/`; the lab's standard build
finds it through `index.json`; `WP-11` and `WP-12` close on real builds; the rows say where the
code is.

## Allowed changes
- `modules/interfaces`: `git mv python/adas_recording src/adas_recording`; the install block in
  `CMakeLists.txt` (source `src/adas_recording/`, destination `python/adas_recording`, same
  `__pycache__`/`*.pyc` exclusions); `tests/python/test_recording_writer.py` (its import path);
  `RCT_Implementation_Design.md` (the Artifact text of `IMP-0043` and `IMP-0046`, the boxes of
  `IMP-0046`, `IMP-0047`, `WP-11`, `WP-12`); `RCT_Architecture.md` §6a (the two lines naming the
  writer's folder: source in `src/adas_recording/`, shipped as the package's `python/`).
- `modules/vantage-lab`: the files `WP-12` touched, only if the real build needs it; the lab's
  lock as the standard build refreshes it (`--update-lock`, R-BUILD-7).
- `modules/vantage/docs/VANTAGE_Lab_Design.md`: §5.6's sentence and `LAB-55`'s text if they name a
  source path; the boxes of `LAB-55`, `LAB-WP-09`.
- Everything else is read-only.

## Steps
1. Move the module and re-point the install block; fix the test's import path.
2. **Real package build of `interfaces`**: `build.bat -P base -t package -p vs2026` in
   `modules/interfaces` (the standard build). Show the new package revision contains
   `python/adas_recording/writer.py`.
3. **Real lab build**: `build.bat -P base -t sil -p vs2026 --update-lock` in `modules/vantage-lab`
   (the newer first-party revision refreshes the lock, R-BUILD-7). Show one `index.json` names the
   package's `python` folder (not the sibling checkout).
4. Run `interfaces` `tests/python` and the lab's whole suite on Windows Python.
5. Re-point `IMP-0043` (`src/adas_recording/writer.py::…`) and `IMP-0046` (install from
   `src/adas_recording/` to the package's `python/adas_recording/`); fix §6a's two lines and, if
   needed, `LAB-55` and §5.6. Then the boxes: `IMP-0046`, `IMP-0047`, `LAB-55` `[x]` only now that
   both real builds and the tests pass; let the checkers roll up `WP-11`, `WP-12`, `LAB-WP-09`.

## Exit check (run all, report output and seconds)
- The `interfaces` package build (command, result, seconds) and the listing of the shipped
  `python/adas_recording/`.
- The lab build with `--update-lock` (command, result, seconds) and the `index.json` entry.
- `interfaces` `tests/python` and the lab suite (Windows Python): counts, seconds.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  and `--status` → PASS; `WP-11` and `WP-12` as the boxes say.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean.
- `git -C modules/interfaces status --short`, `git -C modules/vantage-lab status --short` → only
  the allowed files.

## Must not
- commit, push, or change files outside "Allowed changes"; change `modules/toolchain`
- leave a binary-less or half-built package revision in the Conan cache: if a package build
  fails, report the revision it left and stop
- add features, options or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids).
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
