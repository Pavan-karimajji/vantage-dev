# Workflow: add_proto

Add a `.proto` contract. Enforces R-IFACE-*, R-NAME-4. Skill:
`skills/protobuf_patterns.md`. Template: `templates/proto_template.proto`.

## Steps

1. **Place the file** under `modules/interfaces/proto/` — in a producer folder
   (`<Producer>__Outputs/`) or a shared domain folder (`common/`, `perception/`,
   `isp/`). Folder = producer, `package` = data domain (R-IFACE-2).
2. **Name it** — file snake_case, message PascalCase, fields always
   snake_case, no exceptions (R-NAME-4). Add the proto header block
   (`COMPONENT: INTERFACES`).
3. **Mark provenance** — if the type is not yet checked for field-set
   completeness against real-world domain requirements, add a `PROVENANCE:` comment marking it unverified (R-IFACE-3).
4. **Register** in `modules/interfaces/CMakeLists.txt`
   (`adas_generate_protos(adas-interfaces FILES …)`).
5. **Rebuild** `adas-interfaces` (`protoc` runs); consumers pick up the generated
   `.pb.h/.pb.cc` via `AdasInterfaces::AdasInterfaces`.

## Validation

- `interfaces` builds; a consumer that includes the new header still builds.
- Cross-repo change → follow `workflows/submodule_commit_order.md`
  (interfaces first).

## Failure cases

- Defining a contract inside a component → contracts live only in `interfaces`
  (R-IFACE-1).
