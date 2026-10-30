# Workflow: Multi-Repo Commit Sequencing (decided 2026-07-05, plan.md §5.8)

Changes spanning submodules MUST land in dependency order. Never leave the superproject pointing at an `interfaces` commit its consumers can't build against.

## Order

1. **`modules/interfaces`** — contract changes (protos, headers, CMake registration). Commit + push in the interfaces repo first.
2. **Consumer modules** (`perception-core`, `df`, `vdy`, `planning`, …) — ripple fixes against the new contracts. Each module's own build (sil + gtest via its `build.bat`) must be green before its commit. Commit + push each module repo.
3. **Superproject last, one commit** — submodule pointer bumps for everything above + any superproject-level edits (variant YAMLs, docs, plan.md). This commit is the atomic "the platform builds at these refs" statement.

## Rules

- A submodule commit that breaks that module's own standalone build never gets pushed — fix forward inside the module first.
- Pointer bumps for related changes travel together in ONE superproject commit (partial bumps = unbuildable checkout for anyone cloning `--recursive`).
- Check for detached HEAD in the submodule before committing (`git -C modules/<m> status`); checkout the module's branch first.
- Contract renames (like `TrackList`→`DfObjList`) follow the same order, with step 2 gated on: every consumer green again before step 3 (see plan.md §5.7 step 1 done-when).
