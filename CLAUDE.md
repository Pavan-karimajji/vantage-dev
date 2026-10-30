# vantage-dev — AI Bootstrap Context

## What this workspace is
A development superproject for **Vantage**, the simulation tool of the ADAS
platform (1v-superproject). Vantage is built and proven here, on generated lab
components, then migrated into 1v-superproject where it replaces `sim`.

Read first: `VANTAGE_DEV_PLAN.md` (decisions, file placement, gates). Then
`.claude/routing.md` for what to load per task.

## Core rules
- components depend ONLY on interfaces
- no middleware logic in algorithm code
- protobuf contracts across boundaries only
- the scheduler is **event-driven**: one recorded control message = one run, pick
  inputs by refSync (`.claude/rules/sim.md` override note)
- SIL delivery is a host-agnostic C-API DLL; no ROS2 work here
- one standard component build (shared toolchain), no private build structures

## Repository model
- git submodule architecture; same repos as 1v-superproject, on a `vantage`
  branch where they change; nothing copied
- `interfaces` is the central contract repo
- commit inside the submodule first, then bump the superproject pointer;
  commit and push only when asked

## Stack
C++17 · Python 3.10+ · Protobuf · Conan · CMake

## AI philosophy
Keep context lightweight: load the rule, skill or workflow a task needs, never
the whole tree. `.claude/` is a pinned import from 1v-superproject; see
`.claude/IMPORTED.md` before changing anything in it.
