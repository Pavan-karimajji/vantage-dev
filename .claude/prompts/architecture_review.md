# Prompt: architecture_review

Review lens for boundary/architecture integrity. Rules: `rules/architecture.md`
(R-ARCH-*), `rules/interfaces.md` (R-IFACE-*).

## Focus areas

- Does the component depend **only on interfaces**, never on another component's
  internals? (R-ARCH-1)
- Is `src/component/**` middleware-free? Any threads/clocks/I/O/middleware
  belong in `src/platform/`. (R-ARCH-2)
- Does protobuf appear **only** at boundaries, with `mathlib`/plain types inside?
  (R-ARCH-3)
- Ports/`exec(dtS)` shape correct; translation at `ReqPort`/`ProPort`? (R-ARCH-4)
- Contracts defined only in `modules/interfaces`; folder-vs-package axes and
  provenance respected? (R-IFACE-2/3)

## Validation criteria

- Component builds against interfaces alone (no cross-component include).
- No duplicated architecture explanation — decisions cite rule IDs, one source.

## Risks to check

- Hidden coupling via a shared header outside `interfaces`.
- Algorithm logic leaking into an adapter or the DLL binding.
