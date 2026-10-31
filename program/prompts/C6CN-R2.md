# C6CN-R2 — §8.1 and §18.2 of register §4.1, row by row

Same rules and files as `C6CN-R1`; the register is the only file you change. The `C-RANGE`
findings are right and the checker stays as it is: a section row covers a **whole section of
one fate** (`D15`), so it never skips a UID. Once `CN-0083`, `CN-0084` and `CN-0222` have
their own fate, §8.1 and §18.2 are listed row by row, as §16 already is.

1. Delete the §8.1 section row (`SIM:CN-0078..0082, SIM:CN-0085..0086, SIM:CN-0302..0303`).
   Add one `carried` / `VNT` row for each of `CN-0078`, `0079`, `0080`, `0081`, `0082`,
   `0085`, `0086`, `0302`, `0303`, each with a Why specific to that row, read from
   `modules/vantage/docs/v2/SIM_Concept_Document_v0.3.1.md` §8.1 (one short clause, never a
   copy of the row's text). If one of them contradicts a rule or a decision, give it its own
   word instead and list it under open questions.
2. Delete the §18.2 section row (`SIM:CN-0214..0221, SIM:CN-0223`). Add one row for each of
   `CN-0214` … `CN-0221` and `CN-0223`, the same way, from §18.2.
3. Keep the rows for `CN-0083`, `CN-0084`, `CN-0222` exactly as they are. Keep row order by
   first UID.

Never run `git checkout`, `git stash`, `git reset`, `pkill` or `kill`.

Exit check: `check_migration_register.py | grep SIM:CN` → no output; `--selftest` → 11
caught; print the new rows with `grep -n -E '^\| SIM:CN-0(07[89]|08[0-6]|21[4-9]|22[0-3])|^\| SIM:CN-030[23] '`.
Report: done / not done, the rows, the exit check with seconds, open questions.
