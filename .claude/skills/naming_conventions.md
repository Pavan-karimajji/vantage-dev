# Naming Conventions (decided 2026-07-05, plan.md item 2)

Vocabulary matches established automotive-domain naming convention, checked
for correctness against real-world engineering practice. Non-negotiable.

## Vocabulary

| Concept | Use | Never |
|---|---|---|
| Detected/tracked things | `DfObj`, `DfObjList`, member `dfObjects`, topic `/objects` | "track", `TrackList`, `/tracks` |
| Ego vehicle dynamics | `VehDyn`, member `egoDyn`, topic `/veh_dyn` | "vehicle state" |
| Component health/opmode | `CompState`, member `compState`, topic `/comp_state` | "function status" |
| AEB warning/reaction | `AebOutputs`, member `outputs` (renamed 2026-07-08 from `AebHypReaction`/`hypReaction`) | **"fcw"/"FCW" in any form** — there is no separate FCW component; it's AEB's warning stage |
| Port structs | `<Fn>ReqPorts` / `<Fn>ProPorts` (e.g. `AebReqPorts`) | "inputs/outputs" |
| Cyclic entry point | `exec(dtS)` | `step()`, `run()`, `update()` |
| Algorithm building blocks (R-ALGO) | filter: `filters::existence(...)` returning `filters::Refusal`; observer: `observers::` / `EgoTurnObserver`, updated by `ObserverManager::updateAll(dtS)`; qualifier: `<fn>_qualifier.*`, `qualify<Fn>()`, `<Fn>Inhibit`. **"qualify" means only the function-level decision** | `qualify()` for a per-object check (use `filterTarget()`), a bare `bool` from a filter |

Pending alignment (do when first consumed by a function): `LaneModel`/`FreeSpace` → likely `roadModel` (matches established naming for this concept elsewhere in the domain).

## C++ style

- camelCase members and locals: `dfObjects`, `outputs`, `maxAgeObjectsS`
- PascalCase types: `AebFunction`, `ReqPort<T>`, `DfRunner`
- NO legacy-style Hungarian prefixes (`ui`/`t_`/`e`/`v_`/`f`); the type system does that job
- `p_` prefix ONLY for raw pointers (ports are value wrappers — rarely needed)
- Units as suffix: `ttcS`, `ageS`, `cycleTimeS`, `corridorHalfwidthM`

## File names

- New files in `modules/df`: **snake_case** — `aeb_function.cpp`, `df_runner.hpp`, `ports.hpp`
- `perception-core`'s legacy PascalCase files stay until touched for other reasons — do not mass-rename

## Runtime calibration/config keys (YAML — `projects/<name>/default.yaml`, `projects/<name>/ego_params.yaml`, etc.)

- **ALL_CAPS with a domain prefix** — `AEB_TTC_BRAKE_THRESHOLD_S`, `EGO_WHEELBASE_M`, `ACC_MIN_GAP_TIME_S` — decided 2026-07-06, matching established automotive-calibration `#define` convention, including the prefix even where the YAML file already nests the value under a same-named section (e.g. `aeb: { AEB_TTC_BRAKE_THRESHOLD_S: 1.2 }`) — the prefix makes a key self-describing even copy-pasted out of context, the same reasoning a flat C-macro namespace needs it for.
- Applies to every YAML calibration file, not just new ones — `projects/base/default.yaml`'s keys (formerly `config/default.yaml`, renamed 2026-07-06 — see `docs/project_scoped_params.md`) are the same category and use this convention too, not the C++ `camelCase` rule below (that's for code identifiers, not config data).
- Unit suffix still applies, same as the C++ rule (`_S`, `_M`, `_MPS`, `_MPSS`, `_N_PER_RAD`), just upper-cased.

## Protos

- proto files snake_case (`gen_object.proto`, `veh_dyn.proto`, `comp_state.proto`), messages PascalCase, fields **always snake_case, no exceptions** (`ttc_s`, `critical_obj_id`, `speed_mps`, `dist_x`, `contributing_sensors`) — the camelCase rule applies to C++ code, not proto fields
- Full mapping table + rationale: plan.md item 2 (naming-convention bullet)
- **Folder = producer/organization, package = data domain — independent axes.** New producer folders (`PerceptionCore__Outputs/`, `VehSigProvider__Outputs/`, `Aeb__Outputs/`) sit as siblings inside `proto/`; the protobuf `package` statement stays whatever's logically correct (`adas.perception`, `adas.common`, `adas.df`) regardless of which folder a file lives in. `CompState` is the standing example: physically in `proto/common/` (shared infra), packaged `adas.df` (semantic domain — renamed 2026-07-08 from `adas.functions`, matching the module's own `adas::df` C++ namespace instead of the generic "functions" word).
- **Verified vs. legacy types — do not blur the line.** Only types checked for field-set *completeness/correctness* against real-world domain knowledge (`DfObj`, `DfObjList`, `VehDyn`, `AebOutputs`, `SignalHeader`, `CompState`) get producer-owned folders — never for naming. Everything else is original-design, untouched, and carries a `PROVENANCE:` comment marking it unverified — see `docs/interfaces_types_migration.md` §0.

### Domain-informed additions (naming is always project-native)

When a field/structure is added to an **already-verified** proto message (`DfObj`, `DfObjList`, `VehDyn`, etc.) based on real-world domain knowledge, only the concept and field-set completeness matter — the identifier is always coined fresh in this project's own convention: snake_case, no Hungarian prefix, descriptive. There is no verbatim-naming exception, camelCase or otherwise; a field's presence may be informed by domain knowledge, but its name and casing never are.

Worked example — `DfObj`'s sensor-contribution field: the underlying
concept (a bitmask recording which sensor modalities confirmed an object —
camera, radar, or both) is a well-understood fusion pattern, not unique to
any one source. Applied here as `contributing_sensors`, a plain snake_case
`uint32` bitmask (`bit 0 = camera`, `bit 1 = radar`, both set = fused) —
project-specific bit layout, project-native name. See
`docs/df_obj_vehdyn_fusion_interfaces_plan.md` §4.6 for the full
field-by-field rationale.
