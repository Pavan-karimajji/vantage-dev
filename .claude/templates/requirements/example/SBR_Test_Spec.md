# SBR — Test Specification

**One file, all three layers.** A test's layer comes from its id prefix
(`STT`/`E2E` → `STK`, `SYT`/`INSP` → `SYS`, `UT`/`IT`/`ANL` → `SW`).

A test never restates an `Accept` clause — it cites it by UID (`R-REQ-4`), and
every case states its FAIL side (`R-REQ-5`).

## Fixture catalogue

| Fixture | What it is |
|---|---|
| `F-UNIT` | Direct item call, no recording, no library |
| `F-DRIVE-UNBELTED` | Scripted drive, seat occupied, belt unbuckled, `vx = 15 m/s` |
| `F-DRIVE-EMPTY` | `F-DRIVE-UNBELTED` with the seat unoccupied |
| `F-DRIVE-SLOW` | `F-DRIVE-UNBELTED` at `vx = 2 m/s` |
| `F-DRIVE-LONG` | `F-DRIVE-UNBELTED` run past `SBR_ESCALATE_AFTER_S` |
| `F-BUCKLE-MID` | `F-DRIVE-UNBELTED` with the belt buckled part-way through |
| `F-FLICKER` | A belted drive with a single-tick unbuckle injected |
| `F-NO-OCC` | `F-DRIVE-UNBELTED` with the occupancy input absent |
| `F-CORPUS` | The acceptance corpus — every recorded drive, with duration |
| `F-BUNDLE` | A resolved config bundle on disk, editable between runs |
| `F-SRC` | The item's source tree as checked in |

---

## 1. Stakeholder validation — `STT`

**`STT-01`** · T · fixture `F-DRIVE-UNBELTED` — An unbelted occupant is reminded
**Serves.** `STK-0001`
**Steps.** Run headless; scan every tick for a reminder.
- `.c1` **PASS:** a reminder is present, per `STK-0001` Accept. **FAIL:** no reminder on any tick.

**`STT-02`** · T · fixture `F-DRIVE-EMPTY` — An empty seat is left alone
**Serves.** `STK-0002`
**Steps.** Run headless; scan every tick for a reminder.
- `.c1` **PASS:** no reminder on any tick, per `STK-0002` Accept. **FAIL:** a reminder on any tick.

**`STT-03`** · T · fixture `F-DRIVE-LONG` — An unheeded reminder escalates
**Serves.** `STK-0003`
**Steps.** Run headless; record urgency at onset and after the dwell.
- `.c1` **PASS:** urgency after the dwell exceeds urgency at onset, per `STK-0003` Accept. **FAIL:** equal or lower.

**`STT-05`** · T · fixture `F-FLICKER` — A one-tick flicker changes nothing
**Serves.** `STK-0005`
**Steps.** Run headless with a single-tick unbuckle injected mid-drive; scan every tick for a reminder.
- `.c1` **PASS:** no reminder on any tick, per `STK-0005` Accept. **FAIL:** a reminder on any tick.

**`STT-04`** · D · fixture `F-CORPUS` — False reminders are rare
**Serves.** `STK-0004`
**Steps.** Replay the corpus; count reminders raised while every occupied seat is belted; divide by hours.
- `.c1` **PASS:** rate at or below the bound, per `STK-0004` Accept. **FAIL:** above it. **⊘ — blocked until the rate is supplied.**

## 2. System verification — `SYT`

**`SYT-SBR-01`** · T · fixture `F-DRIVE-UNBELTED` — Reminder appears on the output port
**Serves.** `SYS-0001`
**Steps.** Run headless; read `sbr.outputs.reminder` per tick against the three conditions.
- `.c1` **PASS:** true on the first tick where all three hold, per `SYS-0001` Accept. **FAIL:** later, or never.

**`SYT-SBR-02`** · T · fixture `F-DRIVE-EMPTY` — Output stays false for an unoccupied seat
**Serves.** `SYS-0002`
**Steps.** Run headless; read `sbr.outputs.reminder` per tick.
- `.c1` **PASS:** false on every tick, per `SYS-0002` Accept. **FAIL:** true on any tick.

**`SYT-SBR-03`** · T · fixture `F-DRIVE-LONG` — Urgency rises after the dwell
**Serves.** `SYS-0003`
**Steps.** Run headless; read `sbr.outputs.urgency` at onset and on the first tick past the dwell.
- `.c1` **PASS:** the later value is higher, per `SYS-0003` Accept. **FAIL:** equal or lower.

**`SYT-SBR-04`** · T · fixture `F-NO-OCC` — Unavailability is reported, not guessed
**Serves.** `SYS-0004`
**Steps.** Run headless; read `sbr.compState` and `sbr.outputs.reminder` per tick.
- `.c1` **PASS:** state reads degraded, per `SYS-0004` Accept. **FAIL:** state reads OK.
- `.c2` **PASS:** reminder stays false on every tick. **FAIL:** true on any tick.

**`SYT-SBR-05`** · T · fixture `F-BUCKLE-MID` — Reminder clears within one cycle
**Serves.** `SYS-0005`
**Steps.** Run headless; find the first buckled tick; read the reminder on the tick after it.
- `.c1` **PASS:** false on the following tick, per `SYS-0005` Accept. **FAIL:** still true.

## 3. Software verification — `UT`

**`UT-belt-01`** · T · fixture `F-UNIT` — Belt state is debounced
**Serves.** `SW-0001`
**Steps.** Drive the item with a one-tick flip, then a flip held for the debounce count.
- `.c1` **PASS:** the one-tick flip does not change the reported state, per `SW-0001` Accept. **FAIL:** it does.
- `.c2` **PASS:** the held flip does change it. **FAIL:** it does not.

**`UT-occ-01`** · T · fixture `F-UNIT` — Occupancy is debounced
**Serves.** `SW-0002`
**Steps.** Drive the item with a one-tick flip, then a flip held for the debounce count.
- `.c1` **PASS:** the one-tick flip does not change the reported state, per `SW-0002` Accept. **FAIL:** it does.
- `.c2` **PASS:** the held flip does change it. **FAIL:** it does not.

**`UT-gate-01`** · T · fixture `F-UNIT` — Speed gate is exclusive at the threshold
**Serves.** `SW-0003`
**Steps.** Call the item at the threshold and one increment above it.
- `.c1` **PASS:** not met at the threshold, met above it, per `SW-0003` Accept. **FAIL:** met at the threshold, or not met above it.

**`UT-gate-02`** · T · fixture `F-UNIT` — Missing input reports unavailable
**Serves.** `SW-0004`
**Steps.** Call the item with occupancy absent and the other inputs both valid and invalid.
- `.c1` **PASS:** unavailable in both cases, per `SW-0004` Accept. **FAIL:** available in either.

**`UT-esc-01`** · T · fixture `F-UNIT` — Dwell accumulates only across a continuous span
**Serves.** `SW-0005`
**Steps.** Drive the item with a continuous active span, then with one inactive tick inserted.
- `.c1` **PASS:** the dwell is reached in the continuous case, per `SW-0005` Accept. **FAIL:** not reached.
- `.c2` **PASS:** the interrupted case returns the accumulator to zero. **FAIL:** it carries over.

**`UT-state-01`** · T · fixture `F-UNIT` — Reminder is held then cleared
**Serves.** `SW-0006`
**Steps.** Drive the item across a qualifying span and one evaluation past its end.
- `.c1` **PASS:** set for the whole span, per `SW-0006` Accept. **FAIL:** clear on any tick within it.
- `.c2` **PASS:** clear on the evaluation after the span. **FAIL:** still set.

**`UT-calib-01`** · T · fixture `F-BUNDLE` — Thresholds come from the bundle
**Serves.** `SW-0007`
**Steps.** Run, edit the bundle threshold, re-run without rebuilding, compare onset ticks.
- `.c1` **PASS:** the onset tick moves, per `SW-0007` Accept. **FAIL:** unchanged, which means a literal.

## 4. Static analysis — `ANL`

**`ANL-01`** · A · fixture `F-SRC` — No threshold is a literal in source
**Serves.** `SW-0007`
**Steps.** Scan the item's source for numeric comparisons against a literal where a calibration key exists.
- `.c1` **PASS:** no literal threshold is found, per `SW-0007` Accept. **FAIL:** any literal comparison against a calibrated quantity.
- `.c2` **PASS:** the planted violation is reported — a copy of the source with one threshold inlined is flagged. **FAIL:** the scan passes it, which means the check is blind.
