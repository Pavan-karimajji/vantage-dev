# Workflow: add_interface

Add a shared C++ interface header. Enforces R-IFACE-1, R-ARCH-1/4. Template:
`templates/interface_template.hpp`. For proto contracts, see
`workflows/add_proto.md`.

## Steps

1. **Place it in `modules/interfaces/cpp/`** — interfaces are the only place a
   cross-component boundary is defined (R-IFACE-1). Header block
   `COMPONENT: INTERFACES`.
2. **Pure abstract only** — virtual dtor, abstract methods (`exec(dtS)` shape per
   R-ARCH-4), no state, no I/O, no implementation.
3. **Export** via the interfaces CMake target so consumers link
   `AdasInterfaces::AdasInterfaces` and depend on the interface, not each other.

## Validation

- `interfaces` builds; a consumer depending on the header still builds.
- Cross-repo → `workflows/submodule_commit_order.md` (interfaces first).

## Failure cases

- Any concrete logic in the header → interfaces are contracts only.
