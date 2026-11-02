Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# ENV-2a-R1 — regenerate the baseline holding every version it already has

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). Never run `git checkout`,
  `git switch`, `git stash`, `git reset`, `git rm`, `git add`, `git commit`, `git push`, or change
  any git or Conan configuration.
- `program/prompts/ENV-2a.md` — the package this reworks. Its uncommitted changes are in place
  (toolchain `vantage` branch: `config.py` `extras:` + `extras_problem()`, tests, version
  `1.0.9001`; superproject: `lock_python_env.py`, `make_python_baseline.py` with `--extras`, their
  tests; `modules/vantage-lab/pyproject.toml` `dev` extra). Keep all of them.
- Why: `ENV-2a` stopped at step 4 because the generator resolves unpinned, so PyPI's newest
  versions moved five lines that stay: `mcap` 1.5.0 → 1.6.0, `mcap-protobuf-support` 0.5.4 →
  0.6.0, `numpy` 2.5.3 → 2.5.4, `playwright` 1.63.0 → 1.64.1, `pyee` 13.0.1 → 14.0.0.
  **Orchestrator's answer: hold them.** No version already in the baseline moves.

## Goal
`python_baseline.txt` on the toolchain `vantage` branch is regenerated so every line kept from
`f061dfd`'s file keeps its version; it gains only the test tools (and what they need that is not
already there) and loses only lines of envs not checked out here.

## Allowed changes
- `scripts/make_python_baseline.py` and `scripts/tests/test_python_baseline.py`.
- `modules/toolchain/adas_build_tools/python_baseline.txt` (regenerated, never by hand).
- Everything else is read-only.

## Steps
1. One new flag, `--hold`, explicit, never a default: the current `python_baseline.txt`'s
   `name==version` lines are passed as pip `-c` constraints to the one resolve, so a package
   already in the baseline keeps its version and a package that only the new requirements bring is
   resolved freely. If pip cannot resolve under the hold, refuse with pip's conflict in the reason
   and write nothing. With `--hold`, the header's `# regenerate:` line names the flags actually
   used.
2. Tests: the constraints reach the resolve with `--hold` and not without; a resolve failure
   under the hold writes nothing; the header names the flags.
3. Regenerate on `py -3.12`:
   `py -3.12 scripts\make_python_baseline.py --hold --extras vantage:sim=dev --extras vantage-lab:lab=dev`.
   PyPI downloads only into the generator's own throwaway environment; if pip fails on HTTPS,
   stop and report — no certificate packages, no `--trusted-host`, no proxy settings.
4. Compare with `f061dfd`'s file. **If any line present in both differs in version, stop**,
   restore the file with your own edit, and report the lines.

## Exit check (run all, report output and seconds)
- `py -3.12 -m unittest discover -s scripts\tests -p "test_python_baseline.py"` → pass.
- `py -3.12 -m unittest discover -s scripts\tests -p "test_lock_python_env.py"` → pass.
- `cd modules\toolchain && py -3.12 -m unittest discover -s tests` → pass.
- `py -3.12 scripts\check_invariants.py` → clean (findings verbatim).
- `git -C modules\toolchain diff f061dfd -- adas_build_tools/python_baseline.txt`, in full,
  with three lists: lines added, lines removed, lines whose version changed (must be empty).
- `git diff --stat` and `git -C modules\toolchain diff --stat`, each also with
  `--ignore-cr-at-eol`: only allowed files, same counts.

## Must not
- release, export or upload anything; bump a pin; regenerate a lock; recreate an environment
- make holding the default, or change what a bare run does
- decide anything the steps leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked: none.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
