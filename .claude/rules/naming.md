# Rules — Naming (R-NAME)

Normative index. **Full detail + naming provenance:
`skills/naming_conventions.md`** (the authored deep version — read it before
naming anything new). Non-negotiable vocabulary, chosen to match
established automotive-domain naming convention.

| ID | Rule |
|---|---|
| R-NAME-1 | Vocabulary: `DfObj`/`DfObjList` (never "track"), `VehDyn`/`egoDyn`, `CompState`, `AebOutputs`, `<Fn>ReqPorts`/`<Fn>ProPorts`, `exec()`, `<Fn>Qualifier`/`qualify<Fn>()`, `filters::`, `observers::`, `Refusal`, `Inhibit` (R-ALGO). **"qualify" means only the function-level may-I-act decision**; a per-object check is a filter. **No "fcw"/"FCW" in any form.** |
| R-NAME-2 | C++ style: camelCase members/locals, PascalCase types, **no Hungarian prefixes**, `p_` only for raw pointers, unit suffix (`ttcS`, `corridorHalfwidthM`). |
| R-NAME-3 | YAML calibration keys: **ALL_CAPS with domain prefix + unit suffix** (`AEB_TTC_BRAKE_THRESHOLD_S`, `EGO_WHEELBASE_M`) — every calibration file, new or existing. |
| R-NAME-4 | Protos: files snake_case, messages PascalCase, fields **always snake_case, no exceptions** — verification against real-world domain requirements governs field-set completeness only, never naming. |
| R-NAME-5 | New source files snake_case; legacy PascalCase files are not mass-renamed. |
| R-NAME-6 | `COMPONENT:` header token = repo name uppercased (`DF`, `INTERFACES`, `PERCEPTION_CORE`, …). |

See also: `skills/protobuf_patterns`, `templates/*`, `docs/file_header_template.md`.
