Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# ENV-2a — `adas_build_tools` learns test extras; the baseline carries the test tools (no release)

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (platform `vs2026`). Shells: PowerShell or
  Git Bash. Never run `git checkout`, `git switch`, `git stash`, `git reset`, `git rm`, `git add`,
  `git commit`, `git push`, or change any git or Conan configuration (remotes stay as they are).
- `VANTAGE_DEV_PLAN.md` §2 `D25` (the owner's decision) and `program/ORCHESTRATION_LEDGER.md`, the
  entry `2026-10-31 · ENV-1 · verdict` (why the environments cannot carry test tools today).
- `.claude/rules/build.md` (R-BUILD-2, R-BUILD-6), `.claude/rules/testing.md` (R-TEST-1..5).
- `modules/toolchain` is on a new local branch **`vantage`** at `f061dfd` (= 1v's `main`, release
  `1.0.47`). 1v's `main` is never touched; everything here lands on `vantage`.
- Code to read: `modules/toolchain/adas_build_tools/config.py` (the one `python_envs:` parser),
  `python_envs.py` (how an env is installed), `python_baseline.txt`; the superproject's
  `scripts/lock_python_env.py`, `scripts/make_python_baseline.py`, `scripts/python_baseline.py`,
  and `PYB-1` in `scripts/check_invariants.py`.
- Interpreters: `py -3.12` is the platform Python. `py -3` (3.14) carries an editable install of
  another checkout — never install into it, never use it to run vantage or lab tests.

## Goal
A `python_envs:` entry can name extras of its `pyproject.toml` intent; the lock made for it
includes them; the shared baseline holds the test tools vantage's and vantage-lab's `dev` extras
need; the `adas-build-tools` version on `vantage` is `1.0.9001`. Nothing is released.

## Allowed changes
- `modules/toolchain`: `adas_build_tools/config.py`, `adas_build_tools/python_envs.py` (only if the
  env install must change), `adas_build_tools/python_baseline.txt` (regenerated, never by hand),
  `pyproject.toml` and `conan_package/conanfile.py` (version only), `tests/` (new or changed
  cases), and a doc under `docs/` only where it already lists the `python_envs` keys.
- Superproject: `scripts/lock_python_env.py`, `scripts/make_python_baseline.py`,
  `scripts/python_baseline.py` (only what extras need), and their tests under `scripts/tests/`.
- `modules/vantage-lab/pyproject.toml`: a `[project.optional-dependencies]` `dev` extra holding
  exactly what `tests/` imports beyond the runtime (at least `pytest`), so the baseline can see it.
- Everything else is read-only — in particular `modules/vantage` (`c1`), every `conf/build.yml`,
  every `conf/build_tools.version`, every `requirements.lock`, `modules/toolchain/VERSION`.

## Steps
1. Inventory (report it, five lines at most): where the keys are validated, how a lock is made
   from a `pyproject.toml` intent, how the env installs the lock and the package, how the
   baseline generator collects intents, how `PYB-1` reads the baseline.
2. One new optional key, `extras:` (a list of extra names), parsed and validated only in
   `config.py`: refused, naming the module and env, when the intent is not a `pyproject.toml`, an
   entry is not a plain name, or the extra is not declared in that `pyproject.toml`. No other new
   key, no default extras.
3. `lock_python_env.py` installs `<dir>[<extras>]` when the env declares extras, so the lock holds
   the extras' packages; `[project] dependencies` are untouched. If the env install
   (`--no-deps -r <lock>`, then the package) already gives the env everything in the lock, leave
   `python_envs.py` alone.
4. `make_python_baseline.py` resolves each env's declared extras with its intent. This step needs
   the extras declared, but no `conf/build.yml` may change here: run it with the extras supplied
   for `vantage:sim` (`dev`) and `vantage-lab:lab` (`dev`) through the generator's own interface
   if it has one; if it has none, add a command-line option for it (tested), never a hidden
   default. Regenerate `python_baseline.txt` on `py -3.12`. Lines of envs not checked out here
   (`df:*`, `viz:*`) may drop out. **If any line that stays changes version, stop before keeping
   the new file and report the lines** (restore the file with your own edit, not a git command).
5. Version `1.0.9001` in `pyproject.toml` and `conan_package/conanfile.py`. Nothing else names it.
6. Tests: the parser cases of step 2 (each refusal planted), the lock target with and without
   extras, the generator's extras input. R-TEST-1 while working.

## Exit check (run all, report output and seconds)
- `cd modules\toolchain && py -3.12 -m unittest discover -s tests` → pass (slow tests skipped with
  their printed reason).
- `py -3.12 -m unittest discover -s scripts\tests -p "test_lock_python_env.py"` and the same for
  each changed script's test file → pass.
- `py -3.12 scripts\check_invariants.py` → clean (report any finding verbatim).
- `git -C modules\toolchain diff --stat`, `git -C modules\vantage-lab diff --stat`, `git diff
  --stat` (superproject): only allowed files; no whole-file line-ending churn (`git diff
  --ignore-cr-at-eol --stat` gives the same counts).
- The baseline diff against `f061dfd`'s file, in full.

## Must not
- release, export or upload anything (`conan create`, `conan export`, `conan upload`, `pip
  install` into any environment but a scratch venv the generator makes) — that is `ENV-2b`
- bump any pin, regenerate any lock, recreate any module environment
- put a test tool in a package's `[project] dependencies`
- decide anything the steps leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked: none (this package has no design row).
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
