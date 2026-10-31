# 6c-SYS-R1 — two rows of register §4.1

Same rules, files and exit check as `6c-SYS`. Change only these two rows:

1. `SIM:SYS-0029` (every port value carries eight fields): `RCT:SYS-0001`..`0003` state only
   the header fields, not simulation time, producer, mode or the repeat indicator, so it is
   not a `moved` row (`moved` needs the target to state the whole obligation, as `CN-0069`).
   Make it `carried`, Target `VNT`, Why: the header fields are the contract's (`RCT:SYS-0001`..`0003`);
   simulation time, producer, mode and repeat stay Vantage's bookkeeping of each sample (ARCH §3.4);
   capture time is retired (D22).
2. `SIM:SYS-0058` (support hosting a module in a separate process): ARCH §9's isolated stage
   meets this obligation, it does not replace it. Make it `carried`, Target `VNT`, Why: the
   isolated stage hosts one stage in a second process (ARCH §9).

Never run `git checkout`, `git stash`, `git reset`, `pkill` or `kill`.

Report: the two rows as written, and the exit check of `6c-SYS` with seconds.
