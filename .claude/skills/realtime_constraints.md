# Skill: realtime_constraints

Keeping algorithm code real-time-safe and middleware-free. Enforces `R-ARCH-2`.

## `src/component/**` is a clean room

Algorithm code must be free of:

- **threads / concurrency primitives** — the host drives cycles via `exec(dtS)`.
- **clocks** — never read wall/sim time; `dtS` and per-port `ageS` are passed in
  (the host owns time).
- **file / disk / network I/O** — configuration arrives already loaded; disk I/O
  belongs in the platform layer (`src/platform/<target>/`).
- **middleware** — no ROS2, AUTOSAR, sockets, shared-memory calls.
- **heap allocation in hot paths** — use `mathlib`'s no-heap containers
  (`CVector<T,N>`, fixed arrays), not `std::vector`/`std::string` in the loop.

## Why

The same `component/` code must compile unchanged into a SIL DLL, an AUTOSAR
runnable, and a test harness. Anything host-specific there breaks that
portability and the certification story (deterministic, statically-analyzable).

## Where the forbidden things go instead

`src/platform/<target>/` — the composition root. It loads config from disk,
owns time, talks to the middleware/simulator, serializes protobuf at the
boundary, and calls `exec(dtS)` on the pure component code.

Review lens: `prompts/realtime_review.md`.
