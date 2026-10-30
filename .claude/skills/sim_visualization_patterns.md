# Skill: sim_visualization_patterns

How the BEV viewer is put together — themes, viewport, transport, capture — and
the failure modes each pattern exists to avoid. Enforces `R-SIM-2/3/5`.
Spec: `modules/sim/docs/v1/sim_visualization_spec.md` (**retired 2026-08-31 to a stub** — its Scene primitive catalogue and style-token taxonomy were extracted unabridged to `modules/sim/docs/v1/FROZEN_DESIGN_ORIGINS.md`; the live baseline is `modules/sim/docs/v2/`). Companion:
`skills/sim_scene_layers.md` (what a function contributes).

## Semantic tokens, not colours

A layer writes `style="status.critical"`. One theme table per medium resolves a
token to colour + line style + hatch + marker.

```
frame.*    origin axis grid grid_label scale_legend
ego.*      body body_edge rear_axle mirror
object.*   default selected ghost assumed_geometry label classification.*
status.*   good warning serious critical inactive unknown
sensor.*   fov range_ring blind housing
truth.*    body track trace
<fn>.*     aeb.corridor  bsd.zone.entry  bsd.zone.exit  lca.zone
```

Four rules on top:

1. **`status.*` is reserved.** Never reused as "the fourth function's colour".
   BSD's `OFF`/`NORMAL`/`BLINKING` and AEB's pre-warning both map onto it, so a
   warning looks the same whichever function raised it.
2. **Never colour-alone.** Every `status.*` mark ships with a shape or label.
   `bsdviz/palette.py` already states this ("colour is semantic and never
   colour-only — every colour is paired with a hatch, marker or label"); it is
   now the framework contract.
3. **Colour follows the entity, never its rank.** Object 3 must not change
   colour because objects 1 and 2 left the scene.
4. **Dark mode is selected, not inverted.** `dark`, `light`, `print` and
   `forced` are four chosen tables over one token set, each validated against
   its own surface.

**Validate, don't eyeball.** Before a token table is frozen, run every
categorical set through the palette validator in both surfaces: lightness band,
chroma floor, adjacent-pair colour-vision-deficiency separation (ΔE ≥ 8 target,
6–8 only with a *named* secondary encoding), normal-vision floor, contrast. A
contrast warning obligates a visible label. This is computable, so compute it.

## Viewport — never three constants

The pattern to avoid, verbatim from today's viewer:

```python
CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX = 900, 700
PX_PER_METER = 10.0
ORIGIN_PX = (450, 620)
```

Fixed size, scale and anchor, chosen for AEB's forward geometry — which is why
the BSD zone ends up squeezed into the bottom strip while 88% of the canvas is
empty road ahead.

Instead: a `Viewport` (centre, scale, rotation, follow mode, size from the
widget) plus **named presets declared as data** so a function ships its own:

```yaml
# modules/df/sim/viewpoints.yaml
forward:     {centre: [40, 0],  span_m: 120, follow: ego_forward}
blindspot_l: {centre: [-4, 4],  span_m:  18, follow: ego_heading}
wide:        {centre: [0, 0],   span_m: 200, follow: world}
```

Follow modes: `ego_forward` (today), `ego_heading` (canvas rotates with ego —
stops the zone swinging on curves), `world` (ego moves through a fixed camera,
trail drawn), `locked:<pick_id>` (centre on a selected target).

Two small things that decide whether panning feels right: **zoom about the
cursor, not the centre**, and clamp scale to `[0.5, 200] px/m` with the current
value always in the scale legend, so a screenshot is self-describing.

## Two-pass session — why scrubbing works

Executing and drawing in one loop destroys the frame you are looking at, which
is why today's `--step` is forward-only and why `--export` exists at all (to
make *another tool* provide the scrub bar).

```
pass 1  resim:  stimuli ──► Pipeline.exec ──► Session = [Tick₀ … Tick_n]
pass 2  view:   Session[i] ──► providers ──► Scene ──► Renderer
```

Because pass 2 is pure and cached per tick:

- seek anywhere instantly, **both directions**;
- toggling a layer or changing theme re-renders **without re-executing** — this
  is what makes the layer panel feel like a tool rather than a re-run;
- an A/B diff of two SUT builds is two arrays indexed by the same `i`.

Live sim appends to the Session as ticks arrive; "live" is the tail, not a
different code path.

## Framework furniture — drawn by the framework, not by a provider

Origin dot, `+x fwd`/`+y left` triad, side captions, distance grid + scale
legend, `t = 12.35 s · tick 247/1200`, project/scenario/pipeline/build-id, ego
state line, and a **stale/invalid banner** when a port's `valid=0` or `ageS`
exceeds the consuming function's calibrated maximum.

`bsdviz.canvas.bev_axes()` already enforces exactly this discipline for figures
("a figure author cannot omit or move them"). Keep it: making the coordinate
convention visible on the canvas was a deliberate lesson learned on
2026-07-13, not decoration.

## Capture with provenance

`S` saves a PNG **plus a `.json` sidecar**: tick, `t_s`, project, scenario,
pipeline, component build hashes, viewport, active layers, theme. A PNG in a
ticket that cannot say which build produced it is a picture; one that can is
evidence, reproducible a month later by `sim render`.

## Selection

`Prim.pick_id` makes selection a scene concept, so the renderer hit-tests the
prims it actually drew. Today's `_hit_test_box()` re-derives the same geometry
the drawing code used — two copies of one rectangle, which will eventually
disagree. Selection persists across ticks by `pick_id`, so stepping keeps the
same target selected.

## Timeline strip

Signal lanes (numeric, **one scale per lane — never two y-axes in one lane**),
state lanes (coloured bands *with* their label), event markers at transitions —
which are exactly the edges the bridge already detects and prints
(`*** t=7.320s bsd_left warning OFF -> NORMAL`), promoted from scrollback to
clickable markers — and expectation windows drawn as translucent spans so a
pass/fail is visible rather than computed. A legend whenever a lane carries ≥ 2
series; up to four also direct-labelled at their last point.

## Failure cases seen before

- **Frame-tree stranding.** The dropped live-Foxglove design tagged video with
  `chase_camera` while the scene used `ego`, leaving every entity in an
  unconnected transform tree and rendering nothing. An explicitly frame-typed
  `Prim` plus a frame graph emitted once from the project model is what prevents
  this class of bug.
- **Two GUI event loops.** OpenCV's `waitKey` does not pump tkinter, so popups
  froze during a blocking `waitKey(0)`. One toolkit, one loop.
- **Per-cell rectangles for a heatmap.** The η coverage overlay currently emits
  one `cv2.rectangle` per 0.5 m cell in a nested loop. Use the `Heatmap` prim —
  one array, correct at any zoom.
