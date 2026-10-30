# Rules — Architecture & Boundaries (R-ARCH)

Normative index. Rationale/detail: `docs/KT/architecture_overview.md`,
`docs/math_library_plan.md` §2.

| ID | Rule |
|---|---|
| R-ARCH-1 | Components depend **only on interfaces** — never on another component's internals. |
| R-ARCH-2 | **No middleware logic in algorithm code.** `src/component/**` is middleware-free: no threads, clocks, file I/O, ROS2, AUTOSAR, sockets. |
| R-ARCH-3 | **Protobuf crosses component boundaries only.** Inside a component use math/plain types. "Envelopes at the door, tools in the room." |
| R-ARCH-4 | **Ports:** each function exposes `<Fn>ReqPorts` (in) / `<Fn>ProPorts` (out); cyclic entry `exec(dtS)`. Translate protobuf→math at `ReqPort`, math→protobuf at `ProPort`. |
| R-ARCH-5 | **Platform code isolated** under `src/platform/<target>/`; the C-API DLL composition root (disk I/O, registration) lives there, not in `component/`. |

See also: `skills/realtime_constraints`, `skills/adapter_patterns`,
`skills/c_api_dll_pattern`.
