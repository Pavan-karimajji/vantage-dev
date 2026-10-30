# SBR — Stakeholder Requirements

**Layer:** `STK` (top declared layer). **Function:** `sbr`.
**Reader:** the person in the seat.

Why each row exists — the problem, and what is deliberately unsettled —
is `SBR_Concept.md` (`R-REQ-17`). It carries the reasoning and no obligation;
this document carries the obligation and no reasoning.

Calibration referenced below is read from the config bundle. `⊘` means nobody
has supplied the number yet (`R-REQ-10`) — never a plausible placeholder.

| Key | Value |
|---|---|
| `SBR_MIN_SPEED_MPS` | `5.0` |
| `SBR_ESCALATE_AFTER_S` | `30.0` |
| `SBR_FALSE_RATE_PER_100H` | **⊘** |

---

**`STK-0001`** · `P0` · `R1` — Remind an occupant who is not belted
**Shall.** The system shall remind an occupant of a seat who is not wearing the belt while the vehicle is moving.
**Accept.** With a seat occupied, its belt unbuckled and speed above `SBR_MIN_SPEED_MPS`, a reminder is present.
**Category.** `feature`
**Verify.** T · `STT-01`   **Trace.** —

**`STK-0002`** · `P0` · `R1` — Stay silent for an empty seat
**Shall.** The system shall not remind for a seat that is not occupied.
**Accept.** With a seat unoccupied and its belt unbuckled at any speed, no reminder is present on any tick.
**Category.** `feature`
**Verify.** T · `STT-02`   **Trace.** —

**`STK-0003`** · `P1` · `R1` — Become harder to ignore over time
**Shall.** An unheeded reminder shall escalate.
**Accept.** A reminder still unheeded after `SBR_ESCALATE_AFTER_S` reports a higher urgency level than at onset.
**Category.** `feature`
**Verify.** T · `STT-03`   **Trace.** —

**`STK-0004`** · `P1` · `R2` — Rarely remind someone who is already belted
**Shall.** False reminders shall be rare enough not to be ignored.
**Accept.** Over the acceptance corpus, reminders raised while every occupied seat is belted occur at most `⊘` times per 100 hours.
**Category.** `kpi`
**Verify.** D · `STT-04`   **Trace.** —

**`STK-0005`** · `P1` · `R1` — Ignore a momentary switch flicker
**Shall.** A buckle-switch transition too brief to be a real buckling shall not change the reminder.
**Accept.** A single-tick unbuckle inside a belted drive produces no reminder on any tick.
**Category.** `feature`
**Verify.** T · `STT-05`   **Trace.** —
