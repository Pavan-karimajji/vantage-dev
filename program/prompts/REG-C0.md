# REG-C0 — the owner's C0 answers in register §4.4

## Context
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never commit, and never run `git checkout`,
  `git stash`, `git reset`, `pkill` or `kill`. Touch only the allowed file.
- `modules/vantage/docs/VANTAGE_Migration_Register.md` §2.1 (the words), §4.4

## Goal
Eight rows of register §4.4 say what the owner decided at gate C0.

## Allowed changes
- `modules/vantage/docs/VANTAGE_Migration_Register.md`: the eight §4.4 rows below, each
  replaced in place. Nothing else.

## Steps
Replace each row (matched by its UID cell) with exactly:
- `| PARITY:SYS-0006 | superseded | ARCH §14 | two builds stepped in one process are parked (ARCH §14); comparing two builds is two engine runs over one recording, compared by port values (R-SIM-24) |`
- `| PARITY:SYS-0008 | superseded | ARCH §14 | a reference build staged for a side-by-side run is parked with it (ARCH §14); each build is its own engine run, compared by port values (R-SIM-24) |`
- `| PARITY:SYS-0023 | carried | VNT | the batch loop chooses which recordings to run by their tags; step 8 decides where the tags come from (recording metadata or later viewer marks) |`
- `| PARITY:SYS-0038 | superseded | ARCH §14 | both builds' outputs under one recording's topics belong to the parked side-by-side run (ARCH §14); each engine run writes its own recording (R-SIM-24) |`
- `| PARITY:SW-0013 | superseded | ARCH §14 | the setup's reference build identity belongs to the parked side-by-side run (ARCH §14) |`
- `| PARITY:SW-0016 | superseded | ARCH §14 | the manifest's reference build hash belongs to the parked side-by-side run (ARCH §14) |`
- `| PARITY:SW-0048 | superseded | ARCH §14 | one input set fed to two builds each step is the parked side-by-side run (ARCH §14); the retired `engine/refrun.py` was its Python form |`
- `| PARITY:SW-0050 | superseded | ARCH §14 | recording two builds' outputs side by side belongs to the parked side-by-side run (ARCH §14) |`

## Exit check (run all, report output and seconds)
- `python3 modules/vantage/scripts/check_migration_register.py | tail -3` → `0 findings`.
- `python3 modules/vantage/scripts/check_migration_register.py --selftest` → 11 caught.
- `grep -n -E '^\| PARITY:(SYS-00(06|08|23|38)|SW-00(13|16|48|50)) ' modules/vantage/docs/VANTAGE_Migration_Register.md`
  → the eight rows as written.
If a check fails because of a given text (for example an `IMP` row now inheriting two words),
change nothing more and report the finding.

## Report back
Done / not done; the exit check with seconds; any finding.
