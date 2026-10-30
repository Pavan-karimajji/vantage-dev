# SBR — System Requirements

**Layer:** `SYS`. **Parent layer:** `STK`. **Reader:** anyone at the external
boundary, with no source access. Every port below is `PROPOSED` — declared in
`layers.yaml`, not yet in a real `conf/ports.yaml`, and reported as such.

Ports, decomposition and the order `exec()` runs in: `SBR_Architecture.md`
(`R-REQ-17`).

---

**`SYS-0001`** · `P0` · `R1` — Raise the reminder on the output port
**Shall.** The component shall set the reminder output true when an occupied seat's belt is unbuckled above `SBR_MIN_SPEED_MPS`.
**Accept.** `sbr.outputs.reminder` is true on the first tick where all three conditions hold together.
**Binds.** `beltState`, `occupancy`, `egoDyn`, `sbr.outputs`
**Verify.** T · `SYT-SBR-01`   **Trace.** `STK-0001`

**`SYS-0002`** · `P0` · `R1` — Never raise it for an unoccupied seat
**Shall.** The component shall hold the reminder output false while the seat is unoccupied.
**Accept.** `sbr.outputs.reminder` is false on every tick of a run with occupancy false and the belt unbuckled.
**Binds.** `occupancy`, `sbr.outputs`
**Verify.** T · `SYT-SBR-02`   **Trace.** `STK-0002`

**`SYS-0003`** · `P1` · `R1` — Report a higher urgency after the dwell time
**Shall.** The component shall raise the reported urgency once the reminder has been continuously active for `SBR_ESCALATE_AFTER_S`.
**Accept.** `sbr.outputs.urgency` reads a higher value on the first tick after the calibrated dwell than it did at onset.
**Binds.** `sbr.outputs`
**Verify.** T · `SYT-SBR-03`   **Trace.** `STK-0003`

**`SYS-0004`** · `P0` · `R1` — Say when an input is unavailable rather than guessing
**Shall.** The component shall report degraded state when a required input is unavailable, and shall not raise a reminder.
**Accept.** With occupancy absent, `sbr.compState` reads degraded and `sbr.outputs.reminder` stays false.
**Binds.** `occupancy`, `sbr.compState`, `sbr.outputs`
**Verify.** T · `SYT-SBR-04`   **Trace.** `STK-0002`, `STK-0004`

**`SYS-0005`** · `P0` · `R1` — Clear promptly when the belt is fastened
**Shall.** The component shall clear the reminder within one cycle of the belt becoming buckled.
**Accept.** `sbr.outputs.reminder` is false on the tick following the one where `beltState` first reads buckled.
**Binds.** `beltState`, `sbr.outputs`
**Verify.** T · `SYT-SBR-05`   **Trace.** `STK-0001`, `STK-0004`
