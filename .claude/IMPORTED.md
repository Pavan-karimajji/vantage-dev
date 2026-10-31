# What this `.claude/` is

A **pinned snapshot** of selected files from 1v-superproject's `.claude/`, so that
every session started in vantage-dev follows the same house rules.

- **Source:** 1v-superproject, commit `d191172`, copied 2026-10-30.
- **Changes flow one way, deliberately.** A later change in 1v is pulled in only
  on purpose and recorded below. A change made here is recorded below and
  **back-ported to 1v at migration** (gate G5 in `VANTAGE_DEV_PLAN.md`).
- **Paths inside these files** (`modules/df/docs/ldw/`, `modules/sim/docs/v2/`,
  `docs/KT/...`) point into **1v-superproject** unless they exist here.

## Imported

| Folder | Files |
|---|---|
| `rules/` | architecture, build, coordinates, git, interfaces, naming, requirements, sil, sim, style, testing, variant |
| `skills/` | build_grammar, c_api_dll_pattern, cmake_patterns, conanfile_commonality, gtest_patterns, naming_conventions, protobuf_patterns, realtime_constraints, requirements_management, sim_scene_layers, sim_visualization_patterns |
| `templates/` | `requirements/` (checker, templates, worked example), file_header.cpp/.proto/.py, gtest_template.cpp, component_cmakelists.txt, proto_template.proto, interface_template.hpp |
| `workflows/` | add_component, add_gtest, add_interface, add_proto, change_build_machinery, native_windows_verification, new_component, repo_bootstrap, submodule_commit_order, write_requirements |
| `prompts/` | architecture_review, dependency_review, realtime_review, system_audit_and_replan |
| `agents/` | low-effort-worker |

## Deliberately not imported

- Rules and skills for DF driving functions (`algorithm_structure`, `math`,
  `math_usage`, `bsd_zone_patterns`, DF code templates): no driving function lives here.
- Adapter, ROS 2, CARLA and SIL-Python skills and workflows: not needed until
  gate C3; imported then if needed.
- `sim_layer_provider.py`: Python layer providers are prototyping only.
- `settings*.json`, `worktrees/`, locks: machine- and user-specific.

## Local changes (back-port at migration)

| Date | File | Change | Back-port |
|---|---|---|---|
| 2026-10-30 | `rules/sim.md` | Override note at the top: R-SIM-18's base-grid parts superseded by the event-driven scheduler (D10) | amend R-SIM-18 in 1v at migration |
| 2026-10-30 | `routing.md` | Written new for this workspace (only rows for imported files) | none (workspace-specific) |
| 2026-10-30 | `agents/vantage-planner.md`, `agents/vantage-builder.md`, `agents/vantage-mechanic.md` | New: the program's three worker types, each with its model and effort (`program/VANTAGE_PROGRAM.md` §1) | none (workspace-specific) |
| 2026-10-31 | `agents/threat-screening.md`, `agents/ip-provenance-scan.md` | Removed: screening runs from 1v-superproject, not from this workspace (owner decision) | none (1v keeps them) |
| 2026-10-31 | `rules/sim.md` | Second override note: R-SIM-14's two recording clocks superseded by one clock (D22, RCT C6) | amend R-SIM-14 in 1v at migration |
