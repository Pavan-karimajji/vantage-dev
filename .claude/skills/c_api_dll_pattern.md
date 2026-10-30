# Skill: c_api_dll_pattern

The SIL delivery pattern (decided 2026-07-05, plan.md §5.6). Enforces `R-SIL-1`.
Backing doc: `docs/df_sil_dll.md`. Promoted to root from `df` — this is the
platform-wide delivery shape, not a df-specific detail.

The primary SIL artifact of a component is a **host-agnostic shared library**
built from `src/platform/<name>_sil/`. Every simulator/middleware (sim host,
CARLA, ROS2) is a thin binding on this one DLL. **Never put algorithm code in a
binding.**

> **Target shape changing (plan.md item 25, not yet implemented).** The
> positional `Exec(handle, dtS, in…, out…)` signature below grows a parameter
> pair per function — `dfApiVersion()` already went 1 → 2 when BSD landed, and
> `docs/df_sil_dll.md` rule 11 predicted exactly this. `R-SIM-4` replaces it
> with a **named port set** (`adasExec(handle, dtS, const AdasPortSet* in,
> AdasPortSet* out)`) plus a per-component manifest generated from
> `ENABLED_FUNCTIONS`, so a new function adds a manifest line rather than an ABI
> break. Everything else on this page — the pure-C header, the ReqBuf/ProBuf
> wire form, caller-owned output memory, the version check, the `try/catch(...)`
> wrapper — is unchanged. See `modules/sim/docs/v1/sim_sil_contract.md` (**retired 2026-08-31 to a stub, evidence only** — the live contract is `rules/sim.md` R-SIM-4/R-SIM-22 and `modules/sim/docs/v2/`) and
> `skills/sil_python_binding.md`. Until that lands, the shape below is what
> exists; do not add a *third* function's parameters to it without reading that
> doc first.

## The API shape (example: `df_sil/df_interface_c.h`)

```c
typedef struct { const uint8_t* data; size_t len; double ageS; int valid; } ReqBuf;
typedef struct { uint8_t* data; size_t cap; size_t len; int updated; } ProBuf;

int   ApiVersion(void);              /* bump on any signature/semantics change */
void* Init(const char* configPath);  /* NULL on error */
int   Exec(void* handle, double dtS, const ReqBuf* /*in ports*/, ProBuf* /*out ports*/);
void  Shutdown(void* handle);
```

## Rules

1. **Serialized protobuf across the boundary, always** (R-ARCH-3). One contract;
   Python bindings come free via ctypes + protobuf.
2. **Host owns time.** The DLL never reads a clock — `dtS` and per-port `ageS`
   come from the caller (only the host knows receive/sim time).
3. **Composition root lives inside the DLL** (`<name>_interface_c.cpp`), guarded
   per function: `#ifdef ADAS_FN_<NAME>_ENABLED` (R-VAR-5).
4. **No crashes across the boundary:** `Init` returns NULL on bad config;
   `Exec` returns non-zero on malformed buffers.
5. **Adding a function's ports extends `Exec`'s parameters** → bump
   `ApiVersion()`; bindings check it at load.
6. The DLL **links no simulator/middleware libraries** — verify with
   `dumpbin /dependents` (see `docs/df_swr_tests.md` BCT-05).

## Design rationale

SIL is always "the algorithm as a bindable library" (a `RequiredData`/
`ProvidedData` set + exec pattern), never a middleware node — this keeps
the DLL boundary free of threading/clock/file-I/O concerns (R-ARCH-2), so
the same binary can be driven by a synthetic test harness, a live
simulator, or a production host without changing.
