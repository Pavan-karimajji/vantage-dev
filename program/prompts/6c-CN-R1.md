# 6c-CN-R1 — two rows of register §4.1

Same rules, files and exit check as `6c-CN`. Change only these two rows of the §4.1 table:

1. `SIM:CN-0069` (the port model is versioned: optional field minor, removing or changing
   major): `RCT:SYS-0033` states only the 1.0.0 → 1.1.0 case, not the rule, so it is not a
   `moved` target. Make it `carried`, Target `VNT`, Why: the versioning rule of the port model
   stays; the contract states only its first instance (`RCT:SYS-0033`).
2. `SIM:CN-0359`: keep `retired`; the Why names the replacement wrongly. Why: evidence about
   the duplicate grid scheduler, which the event-driven orchestrator replaces (ARCH §11); the
   rule itself is `CN-0358`.

Never run `git checkout` (with or without `-p`), `git stash`, `git reset` or `pkill`/`kill`:
if a step seems to need one, stop and report it.

Report: the two rows as written, and the exit check of `6c-CN` with seconds.
