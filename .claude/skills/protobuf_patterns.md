# Skill: protobuf_patterns

Contract/proto conventions. Enforces `R-IFACE-*`, `R-NAME-4`. Backing docs:
`docs/KT/architecture_overview.md` §3, `docs/interfaces_types_migration.md`.

## Where protos live

Only in `modules/interfaces` (R-IFACE-1). Consumers link
`AdasInterfaces::AdasInterfaces` and never define contracts locally.

## Two independent axes: folder vs. package

- **Folder = producer/organization.** Producer folders sit as siblings under
  `proto/`: `PerceptionCore__Outputs/`, `VehSigProvider__Outputs/`,
  `Aeb__Outputs/`, plus shared `common/`, `perception/`, `isp/`.
- **`package` = data domain**, chosen for logical correctness regardless of
  folder (`adas.perception`, `adas.common`, `adas.df`). Example: `CompState`
  lives physically in `common/` but is packaged `adas.df`.

## Naming (R-NAME-4)

- files snake_case, messages PascalCase, fields **always** snake_case
  (`ttc_s`, `critical_obj_id`, `contributing_sensors`) — no exceptions, no
  verbatim-naming carve-out. Real-world domain knowledge informs *which*
  fields exist and *what they mean*, never how they're spelled.

## Provenance (R-IFACE-3)

Only types checked for field-set completeness against real-world domain requirements (`DfObj`,
`DfObjList`, `VehDyn`, `AebOutputs`, `SignalHeader`, `CompState`) get
a producer folder — checked for field-set completeness, not naming.
Everything else is original-design and carries a `PROVENANCE:` comment
marking it unverified. Never blur the line.

## Boundary discipline

Protobuf is for **crossing** boundaries only (R-ARCH-3). Unpack to `mathlib`
types at `ReqPort`, compute, pack back at `ProPort`. Every file gets the proto
header block (R-STYLE-1, `COMPONENT: INTERFACES`).
