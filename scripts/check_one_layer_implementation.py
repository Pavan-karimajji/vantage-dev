#!/usr/bin/env python3
# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# @author Pavan Karimajji

"""`ANL-SM-03` -- exactly one implementation of "what a layer is" exists
across the repo set (`SYNC:SM-12`, `D-6`, `SIM:CN-0287`), specified in
`modules/viz/docs/VIZ_Sync_Plan_v0.1.md` section 5's Tests table.

Two independent "how a component's layer providers become known to the
system" mechanisms have coexisted since the `viz` extraction began:

- **Python** (`modules/sim/src/adas_sim/scene/registry.py`) -- the retiring
  `SI-19` implementation. `@layer_provider` registers a `LayerProviderEntry`
  by import, dynamically, no central roster (`R-VAR-2` extended).
- **C++** (e.g. `modules/df/src/platform/df_viz/layers/layer_registry.hpp`)
  -- the real replacement (`VIZ:SW-0062`). A component's own
  `kLayerProviders[]`-shaped array of `LayerProvider` structs, compile-time,
  validated against `conf/viz.yaml` at generation time.

`SM-12`'s own final box deletes the Python one once `G-7` closes; this check
is the mechanical proof that the deletion actually leaves exactly one. Per
`R-REQ-9` ("a check nobody has seen fail is a check nobody should believe"),
it must be shown to fail *before* the deletion (today's real state -- both
mechanisms are live) and to pass when only one is present -- `.c2` and `.c1`
below.

    python scripts/check_one_layer_implementation.py             # real repo
    python scripts/check_one_layer_implementation.py --root DIR  # a fixture

`--root` exists only so this check's own two cases (`.c1`/`.c2`) can be
demonstrated against a controlled tree, mirroring `check_invariants.py`'s
own `root: Path = ROOT` default-argument shape -- not a real deployment
option, since the real check always means the actual repo tree.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The Python registry's own real marker -- the class this module's own
# docstring describes, not just "a file named registry.py exists" (a
# retired stub left behind with the same filename must not read as "still
# live").
_PYTHON_REGISTRY_PATH = Path("modules/sim/src/adas_sim/scene/registry.py")
_PYTHON_REGISTRY_MARKER = re.compile(r"class\s+LayerProviderEntry\b")

# A C++ registry: any layers/*.hpp under a *_viz platform tree declaring a
# real kFooProviders[] array of LayerProvider structs -- the shape
# layer_registry.hpp's own docstring names, generic across components
# rather than hardcoded to "df" (SM-12's own row is about df today, but a
# second component could carry the same file tomorrow).
_CPP_LAYER_REGISTRY_GLOB = "modules/*/src/platform/*/layers/*.hpp"
_CPP_REGISTRY_MARKER = re.compile(r"struct\s+LayerProvider\s*\{")
_CPP_TABLE_MARKER = re.compile(r"\bk\w*Providers\[\]")


def find_python_registry(root: Path) -> Path | None:
    """The live Python registry, or None if absent/retired."""
    path = root / _PYTHON_REGISTRY_PATH
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not _PYTHON_REGISTRY_MARKER.search(text):
        return None
    return path


def find_cpp_registries(root: Path) -> list[Path]:
    """Every live C++ compile-time layer table found under the repo set."""
    found: list[Path] = []
    for path in sorted(root.glob(_CPP_LAYER_REGISTRY_GLOB)):
        if any(p == "build" or p.startswith("build-") for p in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _CPP_REGISTRY_MARKER.search(text) and _CPP_TABLE_MARKER.search(text):
            found.append(path)
    return found


def run_all(root: Path = ROOT) -> list[str]:
    """`ANL-SM-03`'s own findings list -- empty means exactly one
    implementation was found."""
    findings: list[str] = []
    py = find_python_registry(root)
    cpp = find_cpp_registries(root)

    count = (1 if py else 0) + len(cpp)
    if count == 1:
        return findings

    if count == 0:
        findings.append(
            "ANL-SM-03: no live layer-provider-registration implementation "
            "found at all (neither the Python registry nor any C++ "
            "layer_registry.hpp-shaped table) -- this is not the 'exactly "
            "one' this check exists to prove, it's zero"
        )
        return findings

    parts = []
    if py:
        parts.append(f"Python: {py}")
    parts.extend(f"C++: {p}" for p in cpp)
    findings.append(
        "ANL-SM-03: more than one layer-provider-registration implementation "
        f"is live ({count} found) -- " + "; ".join(parts)
    )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repo root to check (default: the real superproject root) -- "
        "only for demonstrating .c1/.c2 against a fixture tree",
    )
    args = parser.parse_args(argv)

    findings = run_all(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} finding(s)")
        return 1
    print("ANL-SM-03: exactly one layer-provider-registration implementation found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
