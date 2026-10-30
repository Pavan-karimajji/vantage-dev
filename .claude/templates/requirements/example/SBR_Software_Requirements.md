# SBR — Software Requirements

**Layer:** `SW`. **Parent layer:** `SYS`. **Reader:** a developer holding one
software item, with its collaborators stubbed. Every row names an item declared
in `layers.yaml`; a name invented here is a finding.

---

**`SW-0001`** · `P0` · `R1` — Debounce the belt switch
**Shall.** The `belt` item shall treat a buckle state as valid only after it has been stable for the debounce count.
**Accept.** A single-tick state flip does not change the reported buckle state; a flip held for the debounce count does.
**Item.** `belt`
**Verify.** T · `UT-belt-01`   **Trace.** `SYS-0001`, `SYS-0005`, `STK-0005` (skips SYS: the whole obligation sits inside one software item and states no vehicle-level boundary behaviour of its own)

**`SW-0002`** · `P0` · `R1` — Debounce the occupancy signal
**Shall.** The `occ` item shall treat an occupancy state as valid only after it has been stable for the debounce count.
**Accept.** A single-tick occupancy flip does not change the reported state; a flip held for the debounce count does.
**Item.** `occ`
**Verify.** T · `UT-occ-01`   **Trace.** `SYS-0002`

**`SW-0003`** · `P0` · `R1` — Gate on speed
**Shall.** The `gate` item shall report the speed condition as met only above `SBR_MIN_SPEED_MPS`.
**Accept.** At exactly the threshold the condition is not met; one increment above it, it is.
**Item.** `gate`
**Verify.** T · `UT-gate-01`   **Trace.** `SYS-0001`

**`SW-0004`** · `P0` · `R1` — Gate on input availability
**Shall.** The `gate` item shall report unavailable when any required input is missing.
**Accept.** With occupancy missing the item reports unavailable, regardless of the other inputs' values.
**Item.** `gate`
**Verify.** T · `UT-gate-02`   **Trace.** `SYS-0004`

**`SW-0005`** · `P1` · `R1` — Count the escalation dwell
**Shall.** The `esc` item shall accumulate active time and reset it whenever the reminder is inactive.
**Accept.** Accumulated time reaches the dwell only across a continuously active span; any inactive tick returns it to zero.
**Item.** `esc`
**Verify.** T · `UT-esc-01`   **Trace.** `SYS-0003`

**`SW-0006`** · `P0` · `R1` — Latch and clear the reminder
**Shall.** The `state` item shall hold the reminder while its conditions hold and clear it on the next evaluation once they do not.
**Accept.** The reminder stays set across the whole qualifying span and is clear on the evaluation after the span ends.
**Item.** `state`
**Verify.** T · `UT-state-01`   **Trace.** `SYS-0001`, `SYS-0005`

**`SW-0007`** · `P0` · `R1` — Read thresholds from the config bundle
**Shall.** The `calib` item shall read its thresholds from the resolved config bundle, never from a literal.
**Accept.** Editing the bundle value and re-running changes the tick at which the reminder is raised, with no rebuild.
**Item.** `calib`
**Verify.** T · `UT-calib-01` · A · `ANL-01`   **Trace.** `SYS-0001`, `SYS-0003`
