# Rules — Coordinates & Signals (R-COORD)

Normative index. Detail: `docs/ego_params.md`, `docs/project_scoped_params.md`.

| ID | Rule |
|---|---|
| R-COORD-1 | **Ego-fixed frame**, origin at rear-axle center, **+x forward, +y left**; object coordinates are ego-relative. |
| R-COORD-2 | Ego-state signals frozen (2026-07-14): `vx`/`ax`/`yaw_rate`/`ay` are real; **`ay` is a passthrough** (not `vx*yaw_rate`); **there is no `vy` field — use `side_slip_angle`**. |

`ay` as a passthrough and the absence of `vy` are deliberate, frozen
decisions (2026-07-14) — do not "fix" these back to a different convention.

See also: `skills/bsd_zone_patterns` (mirrored-coordinate and entry/exit-
polygon idioms for a left/right-symmetric zone); `rules/sim.md` (R-SIM-2 — every
Scene primitive carries an explicit frame, `ego` by default, and is expressed in
metres; the renderer, never the producer, converts to pixels).
