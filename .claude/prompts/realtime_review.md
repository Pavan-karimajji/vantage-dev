# Prompt: realtime_review

Review lens for real-time / middleware-freedom. Rule: `rules/architecture.md`
(R-ARCH-2). Skill: `skills/realtime_constraints.md`. Procedure:
`workflows/realtime_review.md`.

## Focus areas (everything under `src/component/**`)

- No threads / concurrency primitives.
- No clock reads — `dtS`/`ageS` passed in (host owns time).
- No file / network / disk I/O.
- No middleware (ROS2 / AUTOSAR / sockets / shared-memory).
- No heap allocation in hot paths — `mathlib` no-heap containers instead.

## Validation criteria

- The `component/` code would compile unchanged into SIL DLL, AUTOSAR runnable,
  and test harness.

## Risks to check

- `std::vector`/`std::string` churn inside `exec()`.
- A "temporary" log/file write in algorithm code.
