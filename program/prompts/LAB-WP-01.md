# LAB-WP-01 — the lab repo in the standard build, and the lab messages in interfaces

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers may edit other files; touch only the allowed ones.
- `VANTAGE_DEV_PLAN.md` §2 (D4, D14, D20), §4 (the lab)
- `modules/vantage/docs/VANTAGE_Lab_Design.md` (frozen): §4.1, §4.3, §5.4 (message shapes),
  §8 (code layout: a path is a promise), §9 rows `LAB-01`..`LAB-06` (package `LAB-WP-01`)
- `.claude/workflows/add_component.md`; `.claude/rules/build.md` (R-BUILD-1..6),
  `variant.md`, `style.md` (file headers), `naming.md` (R-NAME-6: `COMPONENT: VANTAGE_LAB`
  for files in `vantage-lab`, `COMPONENT: INTERFACES` for files in `interfaces`),
  `interfaces.md` (R-IFACE-1, R-IFACE-4), `testing.md`
- Working examples of the standard component files: `modules/vantage/conanfile.py`,
  `conf/build.yml`, `conf/build_tools.version`, `CMakeLists.txt`, `pyproject.toml`
- `modules/toolchain/scripts/sync_copy_files.py` (`--dry-run` first)
- `modules/interfaces`: how `proto/**` is built and packaged, `scripts/check_signal_header.py`,
  `scripts/check_rct_schema.py`, the *Message fields* rows of `adas.lab.*` in
  `docs/resim_contract/RCT_Implementation_Design.md` (added by L7-1)

## Goal
`modules/vantage-lab` is a standard component that configures and builds (with no
topology yet) under the shared toolchain, its copied machinery passes `CPY-1`, and
`interfaces` builds and packages `adas.lab.LabSample` and `adas.lab.LabImage`, each
covered by `check_signal_header.py` and `check_rct_schema.py --fields`.

## Allowed changes
- `modules/vantage-lab/**`: the files of rows `LAB-01`..`LAB-04` and `LAB-06`, plus
  `src/platform/lab_sil/lab_components.cmake` holding only an empty `lab_add_topology`
  function that stops with `FATAL_ERROR "lab_add_topology: built by LAB-17"` if called
  (LAB-04 includes the file; `LAB-17` fills it). `.gitignore` for build outputs if needed.
- `modules/interfaces/proto/lab/lab_sample.proto`, `lab_image.proto` (row `LAB-05`), and
  `modules/interfaces/CMakeLists.txt` (the `adas_generate_protos` list only).
- `modules/vantage/docs/VANTAGE_Lab_Design.md`: the boxes of `LAB-01`..`LAB-06` and of
  `LAB-WP-01`, only after their exit check passes.
- Everything else is read-only. In particular no root `scripts/**`, no other component.

## Steps
1. `LAB-01`, `LAB-02`: the 6-line `conanfile.py` stub pinned to the same
   `adas-toolchain` version `modules/vantage/conanfile.py` pins; `conf/build.yml` with
   variant `base.sil`, `requires` on `adas-interfaces` at the version `vantage` uses,
   `build_subdir: src/platform/lab_sil`, a `recipe.type` that fits a package of generated
   shared libraries, `python_envs.lab`; `conf/build_tools.version` equal to `vantage`'s.
2. `LAB-03`: run `python3 modules/toolchain/scripts/sync_copy_files.py --dry-run`; it must
   name only `vantage-lab` files. Then run it for real. Never hand-write a copied file.
3. `LAB-04`: `CMakeLists.txt` and `src/platform/lab_sil/CMakeLists.txt` — find
   `AdasInterfaces`, include `lab_components.cmake`, call `lab_add_topology` once per
   `catalogue/*.yaml` (none exist yet, so no call happens).
4. `LAB-05`: the two proto files with the R-STYLE-1 proto header (`COMPONENT: INTERFACES`)
   and, in the brief, the words "lab-only, never a production port"; package `adas.lab`;
   field numbers and types exactly as the RCT *Message fields* rows give them; one
   `sig_header` of type `adas.common.SignalHeader` each. Add both files to
   `adas_generate_protos` in `modules/interfaces/CMakeLists.txt` the same way the
   `livemeas` and `common` protos were added (`RCT:IMP-0005`/`IMP-0040`). The package
   version stays `1.1.0`: it exists only on the unmerged `vantage` branch, so an additive
   message needs no bump (R-BUILD-7 refreshes the same-version revision).
5. `LAB-06`: `pyproject.toml` declaring the `lab_tools` package (under `src/`) and its
   runtime dependencies (PyYAML, protobuf, mcap); no source files yet beyond what the
   build needs to find the package (an empty `src/lab_tools/__init__.py` with its header
   is allowed).
6. Tick `LAB-01`..`LAB-06` and `LAB-WP-01` only for rows whose check below passed.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\interfaces && py -3.12 scripts\build.py -t gtest -p vs2026"` → build and ctest pass; report the count.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\interfaces && python scripts\check_signal_header.py --message adas.lab.LabSample --message adas.lab.LabImage"` → exit 0.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\interfaces && python scripts\check_rct_schema.py --fields"` → clean.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && py -3.12 scripts\build.py -t sil -p vs2026"` → configures and builds (nothing to compile is fine); report what it built.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean (CPY-1 names `vantage-lab`).
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` → PASS.
- `git -C modules/vantage-lab status --short`, `git -C modules/interfaces status --short`,
  `git -C modules/toolchain status --short` (must be empty) → list every file.

## Must not
- commit, push, or change files outside "Allowed changes"
- write any topology, template, generator or car code (later packages)
- add recipe logic to `conanfile.py`, or logic to a copied file
- decide anything the design leaves open; report it

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
