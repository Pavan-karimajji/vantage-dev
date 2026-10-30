"""
scripts/build_gui.py

Superproject master Build GUI - the one entry point that drives the root
build.py's three cross-module modes, which no single-component build_gui.py can
reach (plan.md items 16/17): delegate (one module), aggregate (--with/--with-all,
the in-tree super-build), and fan-out (all / --modules, the CI batch). It is a
pure launcher over `python scripts/build.py` (docs/build_grammar.md) - every button just
shells out; nothing here reimplements build/Conan/CMake logic.

Every axis - project, module, target, platform - is read from `build.py config`
(the frozen grammar's own discovery output, docs/build_grammar.md §7), never
hardcoded and never a private re-parse of any conf/build.yml. Subprocess output
is NOT captured into the GUI: it inherits this app's own console (the cmd window
gui.bat opened), so there's no in-app log panel; the Build button just shows
run/done state, and the central conan_workarea/logs/ holds the real log.

Speaks the frozen grammar exactly (docs/build_grammar.md):
    python scripts/build.py <module> -t <target> -p <platform> [-P <project>]
        [--with ... | --with-all]                     (aggregate)
    python scripts/build.py all|--modules a,b -t <target> -p <platform> [-P <project>]
                                                      (fan-out)

For a single component's own build+publish, use that module's
scripts/build_gui.py (launched by its own gui.bat) - this master GUI has no
publish section, since publishing is inherently one-component-at-a-time.

Run:
    gui.bat            (superproject root)
    (or: py scripts/build_gui.py)
"""

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

# ── paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))   # scripts/
ROOT = os.path.dirname(_THIS_DIR)                          # superproject root
BUILD_PY = os.path.join(_THIS_DIR, "build.py")            # dispatcher now lives in scripts/ alongside this GUI


# ── dependency ticking rule (AB-12) ───────────────────────────────────────────
# Pure functions, no Tk: unit-tested in scripts/tests/test_build_gui_rules.py.

def parse_deps_line(line):
    """One `build.py deps <m> --rebuild-users` line -> (name, is_data, users).
    The `users:` part is optional, so the default (users-less) output parses too."""
    head, _, tail = line.partition("users:")
    words = head.split()
    return words[0], "[data]" in head, tail.split()


def dep_selection(explicit, users_map):
    """AB-12: (ticked, locked) for the aggregate dependency checkboxes.
    `explicit` = deps the user ticked; `users_map` = {dep: [modules it forces]}
    straight from `build.py deps --rebuild-users` (the same rule AB-05 enforces -
    never re-derived here). `ticked` = explicit plus every forced module;
    `locked` = {forced module: sorted deps that need it}. A forced module is
    released only when no ticked dep still needs it, and keeps its own tick if
    the user had ticked it themselves."""
    locked = {}
    for dep in explicit:
        for user in users_map.get(dep, ()):
            locked.setdefault(user, set()).add(dep)
    ticked = set(explicit) | set(locked)
    return ticked, {user: sorted(deps) for user, deps in locked.items()}


# ── build matrix (dropdowns) ──────────────────────────────────────────────────

def _read_build_matrix():
    """{project: {module: {target: [platform, ...]}}} for the whole
    superproject, parsed from `build.py config` - the single source of truth
    the frozen grammar already prints (docs/build_grammar.md §7). Every config
    line is fully specified (`<module> -t <target> -p <platform> -P <project>`),
    so target and platform lists are read per (project, module, target), never
    hardcoded. Returns {} if config can't be run, and the GUI comes up with
    empty dropdowns rather than failing to open."""
    return _read_config()[0]


def parse_config(stdout):
    """(matrix, not_checked_out) from `build.py config` output. The second is
    the `not checked out: a b` line - modules a fresh clone has but cannot
    describe yet (their targets live in their own conf/build.yml)."""
    matrix, not_checked_out = {}, []
    for line in stdout.splitlines():
        if line.startswith("not checked out:"):
            not_checked_out = line.split(":", 1)[1].split()
            continue
        match = re.search(r"build\.py\s+(\S+)\s+-t\s+(\S+)\s+-p\s+(\S+)\s+-P\s+(\S+)", line)
        if not match:
            continue
        module, target, platform, project = match.groups()
        platforms = matrix.setdefault(project, {}).setdefault(module, {}).setdefault(target, [])
        if platform not in platforms:
            platforms.append(platform)
    return matrix, not_checked_out


def _read_config():
    try:
        result = subprocess.run(
            [sys.executable, BUILD_PY, "config"],
            capture_output=True, text=True, timeout=30, cwd=ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return {}, []
    return parse_config(result.stdout)


# ── hover tooltips (Tkinter has no built-in widget for this) ──────────────────

class _Tooltip:
    """Small hover tooltip - binds <Enter>/<Leave> on a widget to show/hide a
    borderless Toplevel with a text label near the cursor."""

    def __init__(self, widget, text):
        self._widget = widget
        self._text = text
        self._tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        if self._tip is not None:
            return
        x = self._widget.winfo_rootx() + 10
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=self._text, justify="left", wraplength=360,
                 background="#ffffe0", relief="solid", borderwidth=1,
                 font=("Segoe UI", 8)).pack(ipadx=4, ipady=2)

    def _hide(self, _event=None):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


# ── subprocess runner ─────────────────────────────────────────────────────────

class _ProcessRunner:
    """Runs a command on a background thread so the UI stays responsive. Output
    is NOT captured - the command inherits this app's own console, same window
    the user launched gui.bat from. Stops early if stop() is called."""

    def __init__(self, cmd, cwd, on_done=None):
        self._cmd = cmd
        self._cwd = cwd
        self._on_done = on_done
        self._proc = None
        self._stopped = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _run(self):
        try:
            self._proc = subprocess.Popen(self._cmd, cwd=self._cwd)
            rc = self._proc.wait()
        except OSError:
            rc = -1
        if self._on_done:
            self._on_done(rc)


# ── main app ──────────────────────────────────────────────────────────────────

class MasterBuildGuiApp:

    def __init__(self, root):
        self.root = root
        root.title("ADAS 1V - Master Build")
        root.minsize(720, 380)

        self._matrix, self._not_checked_out = _read_config()
        self._runner = None
        self._building = False

        self._build_section()

    # ── axis helpers (all derived from the config matrix, never hardcoded) ─────

    def _projects(self):
        return sorted(self._matrix) or ["base"]

    def _modules(self, project):
        return sorted(self._matrix.get(project, {}))

    def _targets(self, project, module, mode):
        """For delegate/aggregate: the targets that one module declares. For
        fan-out: the union across every module of the project, since fan-out
        skips modules that don't declare the chosen target anyway."""
        proj = self._matrix.get(project, {})
        if mode == "fanout":
            targets = set()
            for mod_targets in proj.values():
                targets.update(mod_targets)
            return sorted(targets) or ["sil"]
        return sorted(proj.get(module, {})) or ["sil"]

    def _platforms(self, project, module, target, mode):
        proj = self._matrix.get(project, {})
        if mode == "fanout":
            platforms = []
            for mod_targets in proj.values():
                for plat in mod_targets.get(target, []):
                    if plat not in platforms:
                        platforms.append(plat)
            return platforms or ["vs2026"]
        return proj.get(module, {}).get(target, []) or ["vs2026"]

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_section(self):
        frame = ttk.LabelFrame(self.root, text="BUILD (superproject scripts/build.py)", padding=8)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Mode
        mode_row = ttk.Frame(frame)
        mode_row.pack(fill="x")
        ttk.Label(mode_row, text="Mode:").pack(side="left")
        self._mode = tk.StringVar(value="delegate")
        for value, label, tip in (
            ("delegate", "Delegate (one module)",
             "python scripts/build.py <module> -t T -p P - builds just that module (package mode), output in conan_workarea/build-<t>-<p>-<proj>-<m>-pkg-solo/."),
            ("aggregate", "Aggregate (--with)",
             "python scripts/build.py <module> -t T -p P --with-all - one solution with the module and its\n"
             "first-party deps as in-tree source targets. The local multi-module dev loop."),
            ("fanout", "Fan-out (all)",
             "python scripts/build.py all -t T -p P - every module of the project, each built standalone in\n"
             "dependency order. The CI batch."),
        ):
            rb = ttk.Radiobutton(mode_row, text=label, value=value, variable=self._mode,
                                 command=self._on_mode_changed)
            rb.pack(side="left", padx=(8, 0))
            _Tooltip(rb, tip)

        # Project / Module
        row1 = ttk.Frame(frame)
        row1.pack(fill="x", pady=(8, 0))
        ttk.Label(row1, text="Project:").pack(side="left")
        projects = self._projects()
        self._project = tk.StringVar(value=projects[0])
        project_cb = ttk.Combobox(row1, textvariable=self._project, values=projects,
                                   state="readonly", width=12)
        project_cb.pack(side="left", padx=(4, 12))
        project_cb.bind("<<ComboboxSelected>>", self._on_project_changed)
        self._project_cb = project_cb

        self._module_label = ttk.Label(row1, text="Module:")
        self._module_label.pack(side="left")
        modules = self._modules(projects[0])
        self._module = tk.StringVar(value=modules[0] if modules else "")
        self._module_cb = ttk.Combobox(row1, textvariable=self._module, values=modules,
                                        state="readonly", width=14)
        self._module_cb.pack(side="left", padx=(4, 0))
        self._module_cb.bind("<<ComboboxSelected>>", self._on_module_changed)
        self._row1 = row1

        # Partial / fresh superproject clone: modules that are not checked out
        # declare no targets yet, so they cannot be in the dropdowns above.
        # Offered here by name; "Check out" runs `build.py checkout <m>` (which
        # also checks out toolchain) and reloads the dropdowns.
        self._checkout_row = ttk.Frame(frame)
        ttk.Label(self._checkout_row, text="Not checked out:").pack(side="left")
        self._checkout_mod = tk.StringVar()
        self._checkout_cb = ttk.Combobox(self._checkout_row, textvariable=self._checkout_mod,
                                         values=[], state="readonly", width=16)
        self._checkout_cb.pack(side="left", padx=(4, 6))
        self._checkout_btn = ttk.Button(self._checkout_row, text="⬇ Check out",
                                        command=self._run_checkout)
        self._checkout_btn.pack(side="left")
        _Tooltip(self._checkout_btn,
                 "git submodule update --init modules/<module> (and modules/toolchain).\n"
                 "Only that module - its dependencies come from the Conan cache.")
        self._checkout_row.pack(fill="x", pady=(4, 0), after=row1)
        self._refresh_checkout_row()

        # Target / Platform
        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(4, 0))
        ttk.Label(row2, text="Target:").pack(side="left")
        self._target = tk.StringVar()
        self._target_cb = ttk.Combobox(row2, textvariable=self._target, values=[],
                                        state="readonly", width=10)
        self._target_cb.pack(side="left", padx=(4, 12))
        self._target_cb.bind("<<ComboboxSelected>>", self._on_target_changed)

        ttk.Label(row2, text="Platform:").pack(side="left")
        self._platform = tk.StringVar()
        self._platform_cb = ttk.Combobox(row2, textvariable=self._platform, values=[],
                                          state="readonly", width=16)
        self._platform_cb.pack(side="left", padx=(4, 0))
        self._platform_cb.bind("<<ComboboxSelected>>", self._on_platform_changed)

        # Mode-specific options
        self._opts_frame = ttk.Frame(frame)
        self._opts_frame.pack(fill="x", pady=(8, 0))

        # Aggregate: which of the PRIMARY module's dependencies get pulled
        # in-tree. --with-all is the master "all" toggle; the individual deps are
        # checkboxes populated per selected primary from `build.py deps` (the
        # same closure run_aggregate_build validates against), so there is no
        # free-text list to type and the visible boxes ARE the resolved
        # dependency graph - a dep missing from a broken conf/build.yml simply
        # doesn't appear.
        self._with_all = tk.BooleanVar(value=True)
        self._with_all_cb = ttk.Checkbutton(
            self._opts_frame, text="all deps in-tree (--with-all)", variable=self._with_all,
            command=self._on_with_all_toggled)
        _Tooltip(self._with_all_cb,
                  "Pull the primary's whole first-party dependency closure in-tree.\n"
                  "Untick to choose a subset with the checkboxes. Aggregate with\n"
                  "nothing selected is just Delegate, so Build is blocked then.\n"
                  "\n"
                  "Pure-data modules (marked [data]) have nothing to compile, so\n"
                  "they are packaged from your checkout instead of built in-tree.\n"
                  "Same result: what you get is your checkout's version.")
        self._deps_label = ttk.Label(self._opts_frame, text="deps:")
        self._deps_frame = ttk.Frame(self._opts_frame)   # holds the dynamic checkboxes
        self._deps_hint = ttk.Label(self._opts_frame, text="", foreground="#888",
                                    font=("Segoe UI", 8))
        self._dep_vars = {}      # module name -> BooleanVar (checked = pull in-tree)
        self._dep_checks = {}    # module name -> Checkbutton widget
        self._deps_cache = {}    # (module, project) -> [(name, is_data), ...]
        self._deps_users = {}    # (module, project) -> {dep: [users]} (AB-12)
        self._explicit_deps = set()   # deps the user ticked themselves (AB-12)

        # Fan-out: which modules of the project get built, each standalone.
        # "Fan-out ALL" is the master "all" toggle; individual modules are
        # checkboxes populated per (project, target, platform) straight from the
        # config matrix already read at startup - no subprocess needed, unlike
        # aggregate's deps query, since qualification is just a dict lookup.
        # A module whose conf/build.yml doesn't declare the current
        # target/platform simply isn't shown (docs/dev_gui.md §3).
        self._fanout_all = tk.BooleanVar(value=True)
        self._fanout_all_cb = ttk.Checkbutton(
            self._opts_frame, text="Fan-out ALL", variable=self._fanout_all,
            command=self._on_fanout_all_toggled)
        _Tooltip(self._fanout_all_cb,
                  "Build every module of the project that declares this target/platform.\n"
                  "Untick to choose a subset with the checkboxes.")
        self._fanout_label = ttk.Label(self._opts_frame, text="modules:")
        self._fanout_frame = ttk.Frame(self._opts_frame)   # holds the dynamic checkboxes
        self._fanout_hint = ttk.Label(self._opts_frame, text="", foreground="#888",
                                       font=("Segoe UI", 8))
        self._fanout_mod_vars = {}      # module name -> BooleanVar (checked = build it)
        self._fanout_mod_checks = {}    # module name -> Checkbutton widget

        # Flags + run
        row3 = ttk.Frame(frame)
        row3.pack(fill="x", pady=(8, 0))
        self._clean = tk.BooleanVar(value=False)
        clean_cb = ttk.Checkbutton(row3, text="--clean", variable=self._clean,
                                   command=self._on_options_changed)
        clean_cb.pack(side="left")
        _Tooltip(clean_cb, "Remove the build directory first (wipes that build's conan_workarea/ folder).")
        self._no_log = tk.BooleanVar(value=False)
        nolog_cb = ttk.Checkbutton(row3, text="--no-log", variable=self._no_log,
                                   command=self._on_options_changed)
        nolog_cb.pack(side="left", padx=(8, 12))
        _Tooltip(nolog_cb, "Console output only - don't write the central conan_workarea/logs/ file for this build.")

        self._run_btn = ttk.Button(row3, text="▶ Build", command=self._run_build)
        self._run_btn.pack(side="left")
        self._stop_btn = ttk.Button(row3, text="■ Stop", command=self._stop_build, state="disabled")
        self._stop_btn.pack(side="left", padx=4)

        self._cmd_label = ttk.Label(frame, text="", foreground="#555", font=("Consolas", 8),
                                    wraplength=680, justify="left")
        self._cmd_label.pack(anchor="w", pady=(10, 0))
        self._status = ttk.Label(frame, text="idle", foreground="gray")
        self._status.pack(anchor="w")

        self._on_mode_changed()

    # ── reactive dropdown/preview updates ─────────────────────────────────────

    def _on_mode_changed(self):
        mode = self._mode.get()
        # In fan-out, the single Module dropdown is replaced entirely by the
        # per-module checkboxes below - it picks several modules at once, not one.
        if mode == "fanout":
            self._module_label.pack_forget()
            self._module_cb.pack_forget()
        else:
            self._module_label.pack(side="left")
            self._module_cb.pack(side="left", padx=(4, 0))

        for widget in (self._with_all_cb, self._deps_label, self._deps_frame,
                       self._deps_hint, self._fanout_all_cb, self._fanout_label,
                       self._fanout_frame, self._fanout_hint):
            widget.pack_forget()
        if mode == "aggregate":
            self._with_all_cb.pack(side="left")
            self._deps_label.pack(side="left", padx=(12, 2))
            self._deps_frame.pack(side="left")
            self._deps_hint.pack(side="left", padx=(6, 0))
        elif mode == "fanout":
            self._fanout_all_cb.pack(side="left")
            self._fanout_label.pack(side="left", padx=(12, 2))
            self._fanout_frame.pack(side="left")
            self._fanout_hint.pack(side="left", padx=(6, 0))
        self._refresh_axes()

    # ── aggregate dependency checkboxes ───────────────────────────────────────

    def _query_deps(self, module, project):
        """The primary's first-party dependency closure as [(name, is_data), ...],
        from `build.py deps <module> -P <project>` - the same authority
        run_aggregate_build validates --with against. Cached per (module,
        project); on any failure returns [] so the row just shows "no
        dependencies" rather than the GUI breaking."""
        key = (module, project)
        if key in self._deps_cache:
            return self._deps_cache[key]
        result = []
        if module:
            try:
                out = subprocess.run([sys.executable, BUILD_PY, "deps", module, "-P", project,
                                      "--rebuild-users"],
                                     capture_output=True, text=True, timeout=30, cwd=ROOT)
                users = {}
                for line in out.stdout.splitlines():
                    if line.strip():
                        name, is_data, dep_users = parse_deps_line(line)
                        result.append((name, is_data))
                        users[name] = dep_users
                self._deps_users[key] = users
            except (OSError, subprocess.SubprocessError):
                result = []
        self._deps_cache[key] = result
        return result

    def _populate_deps(self):
        """Rebuild the dependency checkbox row for the current primary+project.
        Preserves a box's ticked state across repopulation where the dep name
        still exists, so switching target (which also repopulates) doesn't reset
        the user's picks."""
        prev = {name: var.get() for name, var in self._dep_vars.items()}
        self._explicit_deps = {n for n in self._explicit_deps if n in prev}
        for child in self._deps_frame.winfo_children():
            child.destroy()
        self._dep_vars.clear()
        self._dep_checks.clear()

        deps = self._query_deps(self._module.get(), self._project.get())
        for name, is_data in deps:
            var = tk.BooleanVar(value=prev.get(name, self._with_all.get()))
            var.trace_add("write", lambda *_: self._update_preview())
            text = f"{name} [data]" if is_data else name
            cb = ttk.Checkbutton(self._deps_frame, text=text, variable=var,
                                 command=lambda n=name: self._on_dep_clicked(n))
            cb.pack(side="left", padx=(0, 6))
            if is_data:
                _Tooltip(cb, "Pure-data dependency: nothing to compile, so ticking it\n"
                             "packages it from your checkout instead of building it\n"
                             "in-tree. Untick it and the cached copy is used instead.\n"
                             "(Corrected 2026-09-25: this tip used to promise a Conan\n"
                             "editable override, which package mode removed.)")
            self._dep_vars[name] = var
            self._dep_checks[name] = cb

        if deps:
            self._deps_hint.config(text="")
            self._explicit_deps = {n for n, v in self._dep_vars.items() if v.get()}
        else:
            self._deps_hint.config(
                text=f"'{self._module.get()}' has no first-party dependencies — use Delegate.")
        self._apply_with_all_state()

    def _apply_with_all_state(self):
        """--with-all on ⇒ every dep is in-tree, so tick+disable all boxes; off
        ⇒ let the user choose. Keeps the checkboxes a faithful picture of what
        the emitted command actually does."""
        on = self._with_all.get()
        for name, var in self._dep_vars.items():
            if on:
                var.set(True)
            self._dep_checks[name].config(state="disabled" if on else "normal")
        if not on:
            self._apply_rebuild_rule()

    def _on_dep_clicked(self, name):
        """A box was clicked: record the user's own choice, then re-apply the
        rebuild rule (AB-12) so the users of a ticked dep are ticked + locked."""
        if self._dep_vars[name].get():
            self._explicit_deps.add(name)
        else:
            self._explicit_deps.discard(name)
        self._apply_rebuild_rule()
        self._update_preview()

    def _apply_rebuild_rule(self):
        """AB-12: tick + lock every module a ticked dep forces (`needed: uses X`,
        from build.py's own rule), release the ones nothing needs any more."""
        users_map = self._deps_users.get((self._module.get(), self._project.get()), {})
        ticked, locked = dep_selection(self._explicit_deps, users_map)
        for name, var in self._dep_vars.items():
            var.set(name in ticked)
            base = name + (" [data]" if name in self._data_deps() else "")
            if name in locked:
                self._dep_checks[name].config(state="disabled",
                                              text=f"{base} (needed: uses {', '.join(locked[name])})")
            else:
                self._dep_checks[name].config(state="normal", text=base)

    def _data_deps(self):
        return {n for n, is_data in self._deps_cache.get(
            (self._module.get(), self._project.get()), []) if is_data}

    def _on_with_all_toggled(self):
        self._apply_with_all_state()
        self._update_preview()

    def _with_deps(self):
        """The dep modules currently ticked - the --with subset."""
        return [name for name, var in self._dep_vars.items() if var.get()]

    def _aggregate_underspecified(self):
        """Aggregate that would emit no --with/--with-all is byte-for-byte the
        Delegate command - block it. Two distinct cases, both blocked: the
        primary has no dependencies at all (aggregate is meaningless), or it has
        some but none are ticked."""
        if self._mode.get() != "aggregate":
            return False
        if not self._dep_vars:
            return True
        return not self._with_all.get() and not self._with_deps()

    # ── fan-out module checkboxes ──────────────────────────────────────────────

    def _qualifying_fanout_modules(self, project, target, platform):
        """Modules of `project` whose own conf/build.yml declares this exact
        target/platform pair - a straight lookup against the matrix already read
        at startup (`build.py config`), the same source `_platforms`/`_targets`
        use, so a module that doesn't build this pair simply isn't offered
        rather than being offered and then silently skipped at build time."""
        proj = self._matrix.get(project, {})
        return sorted(mod for mod, targets in proj.items()
                      if platform in targets.get(target, []))

    def _populate_fanout_modules(self):
        """Rebuild the fan-out checkbox row for the current project/target/
        platform. Preserves a box's ticked state by module name across
        repopulation, so switching platform and back doesn't reset picks - a
        module that stops qualifying just disappears rather than being unticked."""
        prev = {name: var.get() for name, var in self._fanout_mod_vars.items()}
        for child in self._fanout_frame.winfo_children():
            child.destroy()
        self._fanout_mod_vars.clear()
        self._fanout_mod_checks.clear()

        mods = self._qualifying_fanout_modules(
            self._project.get(), self._target.get(), self._platform.get())
        for name in mods:
            var = tk.BooleanVar(value=prev.get(name, self._fanout_all.get()))
            var.trace_add("write", lambda *_: self._update_preview())
            cb = ttk.Checkbutton(self._fanout_frame, text=name, variable=var,
                                 command=self._update_preview)
            cb.pack(side="left", padx=(0, 6))
            self._fanout_mod_vars[name] = var
            self._fanout_mod_checks[name] = cb

        if mods:
            self._fanout_hint.config(text="")
        else:
            self._fanout_hint.config(
                text="no module declares this project/target/platform.")
        self._apply_fanout_all_state()

    def _apply_fanout_all_state(self):
        """Fan-out ALL on => every box ticked+disabled; off => let the user
        choose a subset. Keeps the checkboxes a faithful picture of what the
        emitted command actually does."""
        on = self._fanout_all.get()
        for name, var in self._fanout_mod_vars.items():
            if on:
                var.set(True)
            self._fanout_mod_checks[name].config(state="disabled" if on else "normal")

    def _on_fanout_all_toggled(self):
        self._apply_fanout_all_state()
        self._update_preview()

    def _fanout_modules_ticked(self):
        """The modules currently ticked - the --modules subset."""
        return [name for name, var in self._fanout_mod_vars.items() if var.get()]

    def _fanout_underspecified(self):
        """Fan-out that would emit no all/--modules is an ambiguous no-op -
        block it, same reasoning as _aggregate_underspecified: nothing
        qualifies at all, or some modules qualify but none are ticked."""
        if self._mode.get() != "fanout":
            return False
        if not self._fanout_mod_vars:
            return True
        return not self._fanout_all.get() and not self._fanout_modules_ticked()

    def _on_platform_changed(self, _=None):
        if self._mode.get() == "fanout":
            self._populate_fanout_modules()
        self._update_preview()

    def _on_project_changed(self, _=None):
        modules = self._modules(self._project.get())
        self._module_cb.config(values=modules)
        if self._module.get() not in modules:
            self._module.set(modules[0] if modules else "")
        self._refresh_axes()

    def _on_module_changed(self, _=None):
        self._refresh_axes()

    def _on_target_changed(self, _=None):
        self._refresh_platforms()
        if self._mode.get() == "fanout":
            self._populate_fanout_modules()
        self._update_preview()

    def _on_options_changed(self, _=None):
        self._update_preview()

    def _refresh_axes(self):
        mode = self._mode.get()
        targets = self._targets(self._project.get(), self._module.get(), mode)
        self._target_cb.config(values=targets)
        if self._target.get() not in targets:
            # Prefer the sil deliverable over whatever sorts first (gtest).
            self._target.set("sil" if "sil" in targets else targets[0])
        self._refresh_platforms()
        # The dep checkboxes depend on primary+project; repopulate whenever the
        # aggregate axes change (cached, so this is cheap).
        if mode == "aggregate":
            self._populate_deps()
        elif mode == "fanout":
            self._populate_fanout_modules()
        self._update_preview()

    def _refresh_platforms(self):
        platforms = self._platforms(self._project.get(), self._module.get(),
                                     self._target.get(), self._mode.get())
        self._platform_cb.config(values=platforms)
        if self._platform.get() not in platforms:
            self._platform.set(platforms[0])

    # ── command construction ──────────────────────────────────────────────────

    def _build_command(self):
        """The exact `python scripts/build.py ...` argv for the current selection,
        in the frozen grammar (docs/build_grammar.md). Returned as a list so
        the preview label and the runner use the identical command."""
        mode = self._mode.get()
        project, target, platform = self._project.get(), self._target.get(), self._platform.get()
        cmd = [sys.executable, BUILD_PY]

        if mode == "fanout":
            if self._fanout_all.get():
                cmd += ["all"]
            else:
                cmd += ["--modules", ",".join(self._fanout_modules_ticked())]
        else:
            cmd += [self._module.get()]

        cmd += ["-t", target, "-p", platform, "-P", project]

        if mode == "aggregate":
            if self._with_all.get():
                cmd += ["--with-all"]
            elif self._with_deps():
                cmd += ["--with"] + self._with_deps()
        if self._clean.get():
            cmd += ["--clean"]
        if self._no_log.get():
            cmd += ["--no-log"]
        return cmd

    def _preview_text(self, cmd):
        # Show the readable form ("python scripts/build.py ...") rather than the full
        # interpreter path, matching how the grammar documents commands.
        shown = ["python", "scripts/build.py"] + cmd[2:]
        return "$ " + " ".join(shown) + f"   (cwd: {ROOT})"

    def _update_preview(self):
        # _run_btn may not exist yet during the first construction pass, and must
        # never be re-enabled while a build is actually running.
        if self._aggregate_underspecified():
            # Don't show a command that would silently be a Delegate build; block
            # Build and say why - distinguishing "no deps to pick" from "deps
            # exist but none picked".
            if not self._dep_vars:
                msg = (f"# '{self._module.get()}' has no first-party dependencies "
                       "to pull in-tree - Aggregate is meaningless here; use Delegate.")
            else:
                msg = ("# Tick at least one dependency (or 'all deps in-tree') - "
                       "Aggregate with nothing selected is identical to Delegate.")
            self._cmd_label.config(text=msg)
            if hasattr(self, "_run_btn"):
                self._run_btn.config(state="disabled")
            return
        if self._fanout_underspecified():
            if not self._fanout_mod_vars:
                msg = ("# no module declares this project/target/platform - "
                       "pick a different target/platform.")
            else:
                msg = ("# Tick at least one module (or 'Fan-out ALL') - "
                       "fan-out with nothing selected would build nothing.")
            self._cmd_label.config(text=msg)
            if hasattr(self, "_run_btn"):
                self._run_btn.config(state="disabled")
            return
        self._cmd_label.config(text=self._preview_text(self._build_command()))
        if hasattr(self, "_run_btn") and not self._building:
            self._run_btn.config(state="normal")

    # ── run ────────────────────────────────────────────────────────────────────

    def _run_build(self):
        if self._mode.get() != "fanout" and not self._module.get():
            self._status.config(text="[error] no module is checked out - pick one under "
                                "'Not checked out' and press Check out", foreground="#c0392b")
            return
        if not self._target.get() or not self._platform.get():
            self._status.config(text="[error] no target/platform available", foreground="#c0392b")
            return
        if self._aggregate_underspecified():
            self._status.config(
                text="[error] Aggregate needs at least one dependency selected (else use Delegate).",
                foreground="#c0392b")
            return
        if self._fanout_underspecified():
            self._status.config(
                text="[error] Fan-out needs at least one module selected (or 'Fan-out ALL').",
                foreground="#c0392b")
            return
        cmd = self._build_command()
        self._building = True
        self._run_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._cmd_label.config(text=self._preview_text(cmd))
        self._status.config(text="running...", foreground="darkorange")
        self._runner = _ProcessRunner(cmd, ROOT, on_done=self._on_build_done)
        self._runner.start()

    # ── check out (fresh / partial superproject clone) ─────────────────────────

    def _refresh_checkout_row(self):
        mods = self._not_checked_out
        self._checkout_cb.config(values=mods)
        if self._checkout_mod.get() not in mods:
            self._checkout_mod.set(mods[0] if mods else "")
        if mods:
            self._checkout_row.pack(fill="x", pady=(4, 0), after=self._row1)
        else:
            self._checkout_row.pack_forget()

    def _run_checkout(self):
        mod = self._checkout_mod.get()
        if not mod or self._building:
            return
        cmd = [sys.executable, BUILD_PY, "checkout", mod]
        self._building = True
        self._run_btn.config(state="disabled")
        self._checkout_btn.config(state="disabled")
        self._cmd_label.config(text=self._preview_text(cmd))
        self._status.config(text=f"checking out {mod}...", foreground="darkorange")
        self._runner = _ProcessRunner(cmd, ROOT, on_done=self._on_checkout_done)
        self._runner.start()

    def _on_checkout_done(self, rc):
        self.root.after(0, self._checkout_done_ui, rc)

    def _checkout_done_ui(self, rc):
        self._building = False
        self._checkout_btn.config(state="normal")
        self._reload_config()
        ok = rc == 0
        self._status.config(text="checked out - pick target/platform and Build" if ok
                            else f"check out failed (rc={rc}) - see the console",
                            foreground="#2a9d2a" if ok else "#c0392b")

    def _reload_config(self):
        """Re-read `build.py config` after a checkout: the new module now
        declares its projects/targets, so every dropdown is rebuilt."""
        picked = self._checkout_mod.get()
        self._matrix, self._not_checked_out = _read_config()
        self._deps_cache.clear()
        projects = self._projects()
        self._project_cb.config(values=projects)
        if self._project.get() not in projects:
            self._project.set(projects[0])
        if picked in self._modules(self._project.get()):
            self._module.set(picked)
        self._refresh_checkout_row()
        self._on_project_changed()

    def _stop_build(self):
        if self._runner:
            self._runner.stop()

    def _on_build_done(self, rc):
        self.root.after(0, self._build_done_ui, rc)

    def _build_done_ui(self, rc):
        self._building = False
        self._stop_btn.config(state="disabled")
        # Re-enable Build unless the current selection is the blocked aggregate
        # state (in which case _update_preview keeps it disabled with its hint).
        self._update_preview()
        ok = rc == 0
        self._status.config(text=f"done (rc={rc})" if ok else f"exited rc={rc}",
                            foreground="#2a9d2a" if ok else "#c0392b")


def main():
    root = tk.Tk()
    MasterBuildGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
