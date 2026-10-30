# Rules — Delivery / SIL (R-SIL)

Normative index. Detail: `docs/df_sil_dll.md`,
`docs/sil_dependency_wiring_plan.md`, `docs/sil_integration_host.md`.

| ID | Rule |
|---|---|
| R-SIL-1 | SIL delivery is a **host-agnostic C-API DLL** (plan §5.6). ROS2 is an **optional SIL-only wrapper, last priority**; Adaptive AUTOSAR is for production. |
| R-SIL-2 | SIL dependency wiring: `perception-core` is **not** in `sil` (no real Conan package yet); the `--local` flag leaves editables registered. |

See also: `skills/c_api_dll_pattern.md`, `skills/ros2_adapter_patterns.md`,
`workflows/sil_integration.md`, `rules/sim.md` (R-SIM-4 — the **target** ABI
shape: named port sets replacing per-function positional growth, plan.md item
25, not yet implemented) and `skills/sil_python_binding.md`.
