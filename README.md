# vantage-dev

Development workspace for **Vantage**, the simulation tool of the ADAS platform.
Vantage is built and proven here on generated lab components, then migrated into
1v-superproject, where it replaces `sim`.

| Start here | For |
|---|---|
| `VANTAGE_DEV_PLAN.md` | what is built, decisions, where every file lives, gates |
| `program/VANTAGE_PROGRAM.md` | how the work is run (orchestrator, prompts, reviews) |
| `CLAUDE.md`, `.claude/routing.md` | AI sessions in this workspace |

## Modules

| Module | Repo | Branch | Role |
|---|---|---|---|
| `modules/interfaces` | interfaces | `vantage` | data contracts, incl. the resim contract |
| `modules/toolchain` | toolchain | `main` | shared build machinery |
| `modules/shared_config` | shared_config | `main` | vehicle parameters for config bundles |
| `modules/vantage` | vantage (fork of sim) | `main` | the simulation tool |
| `modules/vantage-lab` | vantage-lab | `main` | generator, fake car, topology catalogue |

The module list is created by Plan B (`program/WORKSPACE_Plan.md`). Until then
this repo holds only the plan and the program documents.

## Clone and build

```bash
git clone --recursive https://github.com/Pavan-karimajji/vantage-dev
cd vantage-dev
setup.bat                                   # prepares the machine; on Linux/WSL: python3 scripts/setup.py

# once per machine (and after interfaces changes): builds adas-interfaces/1.1.0
# into the Conan cache and creates vantage's Python environment
python scripts/setup.py --prepare vantage -t gtest -p vs2026 -P base --remotes on

# normal build: aggregate, every first-party module compiled in one tree
python scripts/build.py vantage -t sil -p vs2026 -P base --with-all

# tests: built and run by the component's own entry point (ctest runs at the end)
cd modules/vantage
python scripts/build.py -t gtest -p vs2026
python scripts/build.py -t sil -p vs2026    # also builds simengine, which some Python tests need
```

**Offline bundle.** The Python environments and, on Linux, pip itself come
from `misc/offline_bundle/` (gitignored, ~330 MB). Copy it from a
1v-superproject checkout (`misc/offline_bundle/`) — same toolchain and Python
locks. Without it, Windows needs `--remotes on` for `--prepare`, and Linux
cannot create the build tools' environment at all (Ubuntu's Python ships no pip
wheel).

**Linux / WSL.** Build from a clone on the Linux filesystem (`~/ws/vantage-dev`),
not from the Windows checkout under `/mnt/c`: a venv there cannot bootstrap pip.
Same commands with `python3` and `-p ubuntu_gcc`.

**Keeping 1v-superproject safe.** Both workspaces share one Conan cache.
vantage-dev never publishes a first-party package under a name and version
1v uses: `interfaces` here is `1.1.0` (1v uses `1.0.0`), and the tool is
`adas-vantage` (1v has `adas-sim`). Any change here to `toolchain` or
`shared_config` must bump that module's version first. Never use `--local`.

**Python tests** need the `dev` extra (pytest, pandas), which the locked
environment does not include: run them from any Python 3.12 environment with
`pip install -e "modules/vantage[dev]"` or the dependencies from its
`pyproject.toml`, with `PYTHONPATH=modules/vantage/src`.
