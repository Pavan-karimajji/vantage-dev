# DEC-4 — lab bundles carry the real ego parameters from `shared_config`

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never commit, and never run `git checkout`,
  `git stash`, `git reset`, `pkill` or `kill`: if a step seems to need one, stop and report.
  Another worker edits `modules/interfaces` now; touch nothing there.
- Owner decision (2026-10-31): `EGO_PARAMS_YAML` stays required in the standard bundle step
  (`R-SIM-3a`); a lab component's bundle carries the **real** `shared_config` ego file of the
  `base` project, not an empty one.
- `.claude/rules/sim.md` R-SIM-3a; `.claude/rules/build.md` (R-BUILD-1, R-BUILD-7 — locks),
  `.claude/rules/variant.md` (R-VAR-3, R-VAR-4)
- `modules/vantage-lab/conf/build.yml`, `src/lab_tools/generate.py` (`_write_ego_params`),
  `src/platform/lab_sil/lab_components.cmake` (`adas_pack_config_bundle`), the lab's tests that
  touch bundles
- `modules/shared_config/conf/build.yml` and `CMakeLists.txt` (package `adas-shared-config`,
  version in `VERSION`; `projects/` is installed as a resource directory)
- `modules/interfaces/cmake/config_bundle_pack.cmake` (read only)

## Goal
Every lab library's config bundle packs `shared_config`'s `projects/base/vehicle/ego_params.yaml`,
taken from the `adas-shared-config` package the lab now requires; the generator writes no ego
file; the lab builds and its tests pass.

## Allowed changes
- `modules/vantage-lab/conf/build.yml` (the `requires` list), the lab's lock files as the
  standard build regenerates them (`--update-lock`, R-BUILD-7)
- `modules/vantage-lab/src/lab_tools/generate.py` (remove `_write_ego_params` and its call),
  `modules/vantage-lab/src/platform/lab_sil/lab_components.cmake` (the `EGO_PARAMS_YAML` path)
- the lab's tests that assert an empty ego file, if any
- Everything else is read-only (`modules/interfaces` included).

## Steps
1. Add `adas-shared-config/<its VERSION>` to the lab's `requires`. If the package is not in the
   local Conan cache, prepare it the standard way (`python scripts/setup.py --prepare shared_config`
   at the superproject root) — never a private build structure.
2. Point `EGO_PARAMS_YAML` at the package's `projects/base/vehicle/ego_params.yaml`, found through
   the package's resource directory as Conan exposes it to CMake — no path into the sibling
   checkout (`R-SIM-11`: a consumer needs no sibling checkout).
3. Remove the empty-file writer from `generate.py`.
4. Build the lab's `sil` target on vs2026 with the standard build, then run the lab's unit suite.
   Show one built bundle's `vehicle/ego_params.yaml` equals the `shared_config` file byte for
   byte.

## Exit check (run all, report output and seconds)
- The standard build of `vantage-lab` `-t sil -p vs2026` (the command you ran, its result, seconds).
- The lab's unit suite (Windows Python): pass count, seconds.
- One bundle's ego file compared with `modules/shared_config/projects/base/vehicle/ego_params.yaml`
  (`cmp` or a hash).
- `git -C modules/vantage-lab status --short` → only the allowed files.

## Must not
- commit, push, or change files outside "Allowed changes"
- add a private conanfile, preset or work area (`R-BUILD`)
- add features, options or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
