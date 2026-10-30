# Rules — Build Machinery Commonality (R-BUILD)

Normative index. Detail: `docs/conanfile_commonality_plan.md`,
`docs/sw_build_architecture.md`, `docs/KT/how_to_add_a_component.md`,
`docs/clang_format_consistency_plan.md`. Deep pattern:
`skills/conanfile_commonality.md`.

Two distribution mechanisms, and the split is load-bearing.
**`conanfile.py` is *referenced*** — one implementation in
`modules/toolchain`, imported via `python_requires` (R-BUILD-1).
**Everything else here is *copied*** — build.bat/.sh, `scripts/build.py`,
`scripts/build_gui.py`, `.clang-format` — because a component must run
`build.bat` **before** any `conan install` has happened, so those files
cannot themselves arrive through Conan. The copies are held identical by
`CPY-1` in `scripts/check_invariants.py`, not by hand
(`modules/toolchain/docs/toolchain_plan.md` §3).

| ID | Rule |
|---|---|
| R-BUILD-1 | **`conanfile.py` is a 6-line `python_requires` stub; the recipe body lives once in `modules/toolchain`** (`base_recipe.py`'s `AdasComponent`, package `adas-toolchain/X.Y.Z`). All per-component difference lives in that component's `conf/build.yml`, never in the recipe. A new component declares `python_requires = "adas-toolchain/X.Y.Z"` + `python_requires_extend = "adas-toolchain.AdasComponent"` and writes no recipe logic at all. **Superseded the byte-identical-copy target of 2026-07-22 (item 20 Option A):** copies were held by `diff -q`, which detects drift only *after* it lands and can be overridden file-by-file; a versioned import cannot drift, and Conan enforces the version match. Bumping the pin is a deliberate per-component step, so a shared-recipe change can no longer break every component at once. **Rolled out to all 8 components + `modules/sim/vantage` on 2026-09-04.** |
| R-BUILD-2 | **The component-level `scripts/build.py` is byte-identical across every component** — the single build-mechanics implementation and the sole authority on how a module builds. The root `scripts/build.py` dispatcher only delegates to it. **Superseded 2026-09-08 (`modules/toolchain/docs/imp_design.md`):** "byte-identical" is now true only of the *bootstrap stub* — a ~150-line file whose only job is to find/create a `.venv`, install a pinned version of `adas_build_tools`, and exec into it, forwarding argv/exit-code untouched. The actual build-mechanics implementation (`load_conf()`, `_build()`, the `conan install`/cmake invocation, etc.) moved to `adas_build_tools`, an installable Python package published from `modules/toolchain` and pinned per component via `conf/build_tools.version` (not copy-distributed, and deliberately *allowed* to differ between components — that's the version-pin mechanism, same shape R-BUILD-1 already established for `conanfile.py`). The stub itself stays byte-identical and `CPY-1`-checked exactly as this rule always required; only *where the logic underneath it lives* changed. **Rolled out to all 8 components + `modules/sim/vantage` on 2026-09-08**; the pin each carries has moved independently since (`R-REQ-6`-style — do not treat any specific version number here as current, read each component's own `conf/build.yml`... `conf/build_tools.version`). **Extended 2026-09-09 (`imp_design.md` §10):** the pin's own shape now selects *which* install mechanism runs — a `vX.Y.Z` git tag installs via `pip install git+<toolchain-url>@<tag>` (§4, the original mechanism); a bare `X.Y.Z` installs via Conan (`conan download`/`cache path`/`pip install`, reusing `adas-local`, the same remote every component's C++ deps already need). Both are permanent, coexisting options — a component's pin is not required to migrate. Verified end-to-end in a formal clean-room (fresh clone, isolated empty `CONAN_HOME`, no sibling checkout, no pre-registered remote) — `imp_design.md` §10.6a. |
| R-BUILD-3 | **`build.bat` / `build.sh` are one-line launchers, byte-identical everywhere** — find a Python interpreter, forward every argument untouched to `scripts/build.py`. No real logic in them (the item-10 mistake). |
| R-BUILD-4 | **`scripts/build_gui.py` is byte-identical everywhere.** Component dev-ops GUIs live in `modules/<name>/scripts/`; root `scripts/` is cross-component only. |
| R-BUILD-5 | **`.clang-format` is a single shared config**, identical across repos. Formatting-only changes land in dedicated commits (no logic touched; build+tests verified after). |
| R-BUILD-6 | A change to a **copy-distributed** machinery file (R-BUILD-2..5) is a **cross-submodule change** — edit `modules/toolchain/copy_files/`, run `modules/toolchain/scripts/sync_copy_files.py`, and land it in **all** component repos in the same pass, or it is broken. `CPY-1` fails otherwise. **R-BUILD-1 is the exception**: the recipe body changes in one place (`modules/toolchain`), and each component adopts it by bumping its own pin — that staging is the point, not an omission. See `workflows/change_build_machinery.md`. |
| R-BUILD-7 | **A build never changes an existing lock (WP-13, `cache_first_no_server_plan.md` LK-D3) — with one narrow exception, `LK-D10`.** Before an existing lock is used, every **first-party** pin (name starts with `adas-`) whose same name/version has a *newer, different* revision in this machine's Conan cache makes the build re-resolve that lock through the `--update-lock` path and print one line: `lock: <comp>-<target>: adas-interfaces/1.0.0 refreshed <old8> -> <new8> (newer first-party revision in the local cache)`. `setup.py --prepare <module>` applies the same rule in place to **every** existing lock of that module (all targets, platforms, projects, and its aggregates), so it leaves none stale. **Reason:** first-party packages are produced on the same machine from the sibling checkout, so a newer same-version revision means new source was pulled — a version bump is not needed and a stale pin would compile against the old schema. **Third-party pins never trigger or take part in it**; third-party drift keeps the strict behaviour, a pinned revision *missing* from the cache with nothing newer is still refused (`LK-D6`), and `--update-lock` is unchanged. Implementation: `adas_build_tools/lockfiles.py` (`stale_first_party`, `LockSession.refusal`, `refresh_stale_first_party`). |

See also: `rules/variant.md`, `workflows/add_component.md`,
`modules/toolchain/docs/toolchain_plan.md` (the mechanism),
`modules/toolchain/docs/build_files_removal_plan.md` (retired — evidence
only, the Option-A gaps it tracked are since closed), `modules/toolchain/
docs/imp_design.md` (the `build.py` bootstrap-stub redesign R-BUILD-2's
supersession note records — the `adas_build_tools` package, its two
permanent, coexisting install mechanisms and the formal clean-room
verification of both, §3).
