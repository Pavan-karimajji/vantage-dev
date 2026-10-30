# Concept page vs. Vantage architecture — divergences to fix

The concept page `C:\ws\lt_learning\sim\vantage_concept.html` (outside every repo)
follows the design. These are the places where it differs from
`modules/vantage/docs/VANTAGE_Architecture.md` (step 6a), as reported by the 6a
worker on 2026-10-30 and amended by the owner's decisions of the same day. Update
the concept page **after 6a is frozen**, then delete each row here as it is done.

| # | Concept page says | Design says (the page must follow) |
|---|---|---|
| 1 | The scheduler is one part | Two parts: the orchestrator, plus control writing. "Scheduler" stays only as the RCT role name (whoever writes control messages) |
| 2 | Ch. 14: the description says which plug-ins to load | Vantage writes no plug-in bundle: viz is out of this design (D13). `KIND_PLUGIN` stays unused |
| 3 | Ch. 13: a crash is marked "crash" in batch and "stop with stack" on the bench | The batch supervisor records crash and run-level timeout in the live measurement (the seal). On the developer face nobody writes an outcome after a crash; a reader reports "writer gone at step N" |
| 4 | Ch. 13: "not matched to car inputs" is a badge separate from per-port fallback | One kind for both: `KIND_FALLBACK` |
| 5 | Ch. 13: "N samples missing", "counter reset" and a stalled-trigger warning | No badge kinds for these. They are counted in the engine's event log; badges come only when a reader needs them (owner, 2026-10-30). **The page must not promise them yet** |
| 6 | Ch. 4: optional pacing and a "took 45 ms, budget 20 ms" report | Both parked |
| 7 | Ch. 5 and 14: pausing and a heartbeat while paused | No pause for now (owner, 2026-10-30) |
| 8 | Ch. 8: each input keeps the last few samples | Plus a read-ahead of the recording, because the car logs its refSync after its control. The buffer depth is ⊘ |
| 9 | Ch. 5: sources with no recording tick on a clock | Such a source is a `stubdll:` stage with `clock_period_ns`, not a source feature |
| 10 | Ch. 17: "every simulated sample equals the car's"; ch. 6 does not mention D16 | State D16: `cycle_counter` keeps counting through RESTART. Use *equal outputs* (byte-identical except each header's `cycle_counter`, RCT SYS preamble) |
| 11 | Ch. 14: the reader comes "from the same place" as the writer | The reader helpers (layout header, `tryCopySlot`, `checkAttach`) live in `interfaces`; the writer is a separate library in `adas-vantage` |

**Also check on the page** (from the owner's decisions of 2026-10-30, not from the
worker's list):
- *Warming up* means: a stage started mid-recording, until its outputs first equal
  the recorded outputs (only when the recording holds them). It does not mean
  "every input matched by refSync" — that is what `KIND_FALLBACK` reports.
- A recorded control is not handed over unchanged: Vantage copies its
  `measurement_counter` and `source_timestamp_us`, writes its own `cycle_counter`
  and sticker OK, forces RESTART on the first run and after a jump, and otherwise
  passes the recorded `op_mode` (so a restart the car sent is reproduced).
