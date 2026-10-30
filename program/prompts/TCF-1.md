# TCF-1 — neutral first line in the QNX toolchain file

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers edit other files now; touch only the allowed one.
- `toolchains/aarch64_qcc_qnx.cmake` (superproject root)

## Goal
Line 1 of the toolchain file names no platform product: it reads exactly
`# ARM64 QNX cross-compile toolchain`. Nothing else in the file changes.

## Allowed changes
- `toolchains/aarch64_qcc_qnx.cmake`, line 1 only. Everything else is read-only.

## Steps
1. Replace line 1 with `# ARM64 QNX cross-compile toolchain`. Keep the file's line
   endings as they are.

## Exit check (run all, report output and seconds)
- `head -1 toolchains/aarch64_qcc_qnx.cmake` → `# ARM64 QNX cross-compile toolchain`
- `git diff --stat toolchains/aarch64_qcc_qnx.cmake` → 1 file, 1 insertion, 1 deletion
- `git grep` in `toolchains/` for the old first-line platform word (given in the launch message) → no output

## Must not
- commit, push, or change files outside "Allowed changes"
- change any other line

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
