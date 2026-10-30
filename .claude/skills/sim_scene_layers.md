# Skill: sim_scene_layers

> **Status 2026-10-08:** the Python provider API shown here (`adas_sim.scene`) was removed in `modules/sim` `7d4c626`; a function's picture is now a C++ layer in `modules/df/src/platform/df_viz/layers/` plus a `conf/viz.yaml` row. The design reasoning (frames, tokens, port binding) still applies; the Python code shapes do not run.

The Scene intermediate representation and the layer-provider pattern — how a
function contributes to every view at once without touching a renderer.
Enforces `R-SIM-1/2/3/7`. Spec: `modules/sim/docs/v2/` — the V-model baseline
(`SIM_System_Requirements_v0.1.md`, `SIM_Software_Requirements_v0.1.md`).
**`modules/sim/docs/v1/sim_architecture.md` and
`modules/sim/docs/v1/sim_visualization_spec.md` were
retired 2026-08-31 to stubs** and are evidence, never an authority; the Scene
primitive catalogue and the style-token taxonomy they held were extracted
unabridged to `modules/sim/docs/v1/FROZEN_DESIGN_ORIGINS.md`. Template:
`templates/sim_layer_provider.py`.

## The problem this exists to prevent

A renderer that knows function names grows one argument per function:

```python
# modules/df/tools/carla/replay/viz.py — the shape to never rebuild
def build_bev_frame(objects_msg, outputs, veh_dyn_msg=None,
                    bsd_outputs=None, bsd_calib=None): ...
```

AEB is positional; BSD was bolted on as two keywords under an explicit promise
that the AEB path stayed byte-identical. There is no third slot that isn't
another edit to a file every function shares. Seven functions make this
unreadable, and `perception-core` cannot contribute to it at all.

## The idea

Put one **intermediate representation** between "what happened" and "how it is
drawn". A layer provider turns a `Tick` into geometry; a renderer turns geometry
into pixels. Neither imports the other.

```
Tick ──► LayerProvider(s) ──► Scene ──► Renderer ──► pixels
         (per component)              (interactive | matplotlib | Foxglove | image)
```

This follows a proven pattern for layered draw APIs — group/subgroup-scoped
draw calls emitting a display list the host renders — made typed,
frame-explicit and serializable.

## Writing a provider

```python
@layer_provider(group="bsd", requires=["bsd.outputs", "objects"], level=1)
def bsd_zone(tick: Tick, ctx: LayerCtx) -> Iterable[Layer]:
    x_aft, x_fwd, u_in, u_out = zone_rect(ctx.model.calib)
    for side in (Side.LEFT, Side.RIGHT):
        yield Layer(
            id=f"bsd.zone.{side.name.lower()}",
            group="bsd", label=f"BSD zone ({side.name.lower()})",
            default_on=True, z=20,
            prims=(Polygon(points=mirrored_corners(x_aft, x_fwd, u_in, u_out, side),
                           frame="ego", style="bsd.zone.entry", filled=False),),
        )
```

Five things make this scale:

1. **Discovered by import, not registered centrally.** Same principle as
   `R-VAR-2` (no central module roster) and the same mechanism `bsdviz`'s
   `@figure` registry already uses. Adding LCA is one new C++ layer in
   `modules/df/src/platform/df_viz/layers/` (plus its `conf/viz.yaml` row); the Python
   `sim/layers/<fn>.py` form was retired (`7d4c626`).
2. **`requires` is checked against the pipeline's port manifests**, so a build
   with `bsd` disabled simply has no BSD layers — it does not fail, and it does
   not draw an empty zone.
3. **Metres in a named frame.** `frame="ego"` (`R-COORD-1`). The renderer owns
   the frame→pixel transform; the provider never sees a pixel. This is what
   lets the *same* prim be drawn in a BEV, projected onto a camera image, and
   emitted as a Foxglove scene entity.
4. **Semantic style tokens, never colours.** `style="bsd.zone.entry"`, not
   `(60, 200, 230)`. One theme table per medium resolves it, so a dark
   interactive view and a print figure are two tables over one scene rather than
   two drawings of one geometry.
5. **Pure.** Given the same `Tick` and `LayerCtx`, a provider returns the same
   layers. No clock, no disk, no state carried between calls. `ctx.history` is a
   **read-only window** over earlier ticks — that is how a trail, a track history
   or a velocity trace is drawn without a provider accumulating anything.
   `ctx.frames` gives the transforms (static ones from the model, `ego→world`
   from `tick.pose`). Purity is what makes scrubbing instant and golden Scene
   tests meaningful.

## Layers, groups and levels

- `id` is unique and stable — it is what a persisted user layer-selection keys
  on.
- `group` is the panel's top-level node (`aeb`, `bsd`, `perception`,
  `ground_truth`, `world`, `measure`) and the solo/mute unit.
- `default_on` is the initial visibility. Put debug detail at `default_on=False`
  rather than not writing it.
- `level` 1/2/3 is verbosity — 1 is what you always want, 3 is internal debug.
  One control raises a whole group instead of ticking fifteen boxes.

## Inspector fields are declared, not dumped; signals are addressed, not re-declared

```python
# Fields ride on the prim that was drawn - the provider already has the raw
# entity in hand, so it formats them in the same pass. (`@inspector_fields`
# existed once and was removed: it registered names with no way to resolve
# values, and its key could silently diverge from the wrapped function.)
Box(..., pick_id=f"object:{obj.general.local_id}",
    fields=(("id", str(obj.general.local_id)),
            ("dist_y", f"{obj.kinematic.dist_y:.2f} m"),
            ("in zone", "yes" if ... else "no")))

# Raw port fields need NO registration - the manifest declares the port, so
# `self.bsd.outputs.left.warning` is already addressable by the timeline, plots
# and expectations alike. Register only COMPUTED signals - and declare their
# inputs, or the evidence chain (R-SIM-25) ends at your signal, invisibly:
@signal("derived.bsd_gap_m", unit="m", requires=["self.bsd.outputs"])
def _(ctx): ...
```

A full recursive proto dump was tried and rejected on sight during the original
viewer work (`df_carla_viz_plan.md` §5.1c) — `DfObj` has ~42 fields and
`VehDyn` ~50, and five chosen fields beat all of them. A "show all" toggle
exists for the rare case; the declared list is the default.

## The re-derivation trap (`R-SIM-7`)

Draw what the SUT produced. If `BsdOutputs.left.warning` says `NORMAL`, draw
`NORMAL` — never recompute the warning condition in Python. The failure mode is
subtle and expensive: the picture agrees with your understanding of the
algorithm rather than with the algorithm.

Where the algorithm genuinely exposes nothing — today's BSD zone rectangle and
unobservable region are reconstructed in Python from calibration because no
debug ProPort exists — the layer is **marked**:

```python
Layer(id="bsd.zone.left", label="BSD zone (left) — derived", derived=True, ...)
```

`derived=True` picks a distinct style variant and appends `(derived)` in the
layer panel, so nobody mistakes a reconstruction for the truth. The real fix is
a SIL-only `<fn>.debug` output port, which costs one manifest line once ports
are named (`skills/sil_python_binding.md`).

**Mark the prim, not only the layer** (`R-SIM-25`, `OD-6`). A layer legitimately
*mixes* — the SUT's own warning state drawn beside a zone polygon reconstructed
from calibration — and a per-layer flag makes the honest answer impossible for
exactly that case. So `Prim(derived=True)` on the reconstructed prims, and
`Layer(derived=True)` because it contains some. The two are bound and cannot
disagree: a `Layer(derived=False)` holding a derived prim raises. The layer flag
still drives the panel badge; the prim flag is what the evidence panel and
`sim explain` read when someone clicks the shape and asks *"did the algorithm
say this, or did we draw it?"*

## Checklist before committing a provider

- [ ] no `cv2`/`matplotlib`/Qt/`foxglove` import, no `px` arithmetic beyond
      `width_px`/`offset_px`
- [ ] every prim has an explicit `frame`
- [ ] every `style` is a token that exists in the theme table
- [ ] nothing physical is a module constant — it came from `ctx.model`
- [ ] history is read via `ctx.history`, never accumulated in the provider
- [ ] nothing the SUT already produces is recomputed, or it is `derived=True` —
      on the **prim** as well as the layer
- [ ] no bulk array is inlined in a prim; a point cloud, image or grid is a
      `BulkRef` into the recording (`NR-SIM-43`)
- [ ] every `@signal` declares its inputs, or the evidence chain ends there
- [ ] `requires` lists every port read, so a disabled function degrades cleanly
- [ ] the provider is pure — same inputs, same layers
