# vantage-dev

Development workspace for **Vantage**, the simulation tool of the ADAS platform.
Vantage is built and proven here on generated lab components, then migrated into
1v-superproject, where it replaces `sim`.

| Start here | For |
|---|---|
| `VANTAGE_DEV_PLAN.md` | what is built, decisions, where every file lives, gates |
| `program/VANTAGE_PROGRAM.md` | how the work is run (orchestrator, prompts, reviews) |
| `CLAUDE.md`, `.claude/routing.md` | AI sessions in this workspace |

## Modules

| Module | Repo | Branch | Role |
|---|---|---|---|
| `modules/interfaces` | interfaces | `vantage` | data contracts, incl. the resim contract |
| `modules/toolchain` | toolchain | `main` | shared build machinery |
| `modules/shared_config` | shared_config | `main` | vehicle parameters for config bundles |
| `modules/vantage` | vantage (fork of sim) | `main` | the simulation tool |
| `modules/vantage-lab` | vantage-lab | `main` | generator, fake car, topology catalogue |

The module list is created by Plan B (`program/WORKSPACE_Plan.md`). Until then
this repo holds only the plan and the program documents.

## Clone and build

Filled in by Plan B, once the submodules and root build scripts exist.
