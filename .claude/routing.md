# Context Routing (vantage-dev)

What to load for a task. Load only what the task needs. Start from the `rules/`
file (normative), add the `skills/` file only when producing code. Program-level
documents come first: `VANTAGE_DEV_PLAN.md`, then `program/VANTAGE_PROGRAM.md`.

| Task | Load |
|---|---|
| **Anything in this workspace** | `VANTAGE_DEV_PLAN.md` (decisions, placement, gates) |
| **Orchestrating: writing a worker prompt or reviewing a result** | `program/VANTAGE_PROGRAM.md` (protocols + checklist), `program/ORCHESTRATION_LEDGER.md` |
| **Any code change** | `rules/style.md`, `rules/naming.md` + `skills/naming_conventions`, `rules/architecture.md` |
| **Workspace / repo / submodules** | `program/WORKSPACE_Plan.md`, `rules/git.md`, `workflows/repo_bootstrap.md`, `workflows/submodule_commit_order.md` |
| **New component (vantage, lab)** | `workflows/new_component.md`, `workflows/add_component.md`, `rules/build.md`, `rules/variant.md` |
| **Build / Conan / CMake** | `rules/build.md`, `skills/build_grammar`, `skills/conanfile_commonality`, `skills/cmake_patterns`; shared machinery: `workflows/change_build_machinery.md` |
| **Resim contract (Plan A) / protos** | `modules/interfaces/docs/resim_contract/`, `rules/interfaces.md`, `rules/naming.md` (R-NAME-4), `skills/protobuf_patterns`, `workflows/add_proto.md`, `workflows/add_interface.md` |
| **Vantage engine, orchestrator, live measurement writer and inspector (Plan C)** | `modules/vantage/docs/`, `rules/sim.md` (read its override note first), `rules/sil.md`, `skills/c_api_dll_pattern`, `skills/realtime_constraints` |
| **Live measurement layout: what a reader needs from it** | `modules/interfaces/docs/resim_contract/`, `skills/sim_scene_layers`, `skills/sim_visualization_patterns` (what viz draws today; viz itself is out of this workspace, D13) |
| **Lab (generator, fake car, catalogue)** | `modules/vantage/docs/VANTAGE_Lab_Design.md`, `rules/sim.md`, `skills/c_api_dll_pattern` |
| **Requirements, test specs, traceability** | `rules/requirements.md`, `skills/requirements_management.md`, `workflows/write_requirements.md`, `templates/requirements/` (checker: `python .claude/templates/requirements/trace_check.py --set <dir>`) |
| **Tests and when to run them** | `rules/testing.md` (R-TEST-1..7), `skills/gtest_patterns`, `templates/gtest_template.cpp`, `workflows/add_gtest.md` |
| **Native Windows verification** | `workflows/native_windows_verification.md` |
| **Reviews** | `prompts/architecture_review.md`, `prompts/dependency_review.md`, `prompts/realtime_review.md`, `prompts/system_audit_and_replan.md` |
| **Before any push** | `agents/threat-screening.md`, `agents/ip-provenance-scan.md` |
