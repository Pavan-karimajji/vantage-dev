# Workflow: add_gtest

Add a unit test. Skill: `skills/gtest_patterns.md`. Template:
`templates/gtest_template.cpp`.

## Steps

1. **Place it in `tests/unit/`** mirroring the `src/component/` file under test 1:1.
2. **Test pure logic** — build `ReqPorts` by hand, call `exec(dtS)`, assert on
   `ProPorts`. No middleware, no disk; allocation-light fixtures; header block.
3. **Register + guard** — add to `tests/CMakeLists.txt`; for a function, wrap in
   the same `if("<fn>" IN_LIST ENABLED_FUNCTIONS)` guard as its source (R-VAR-5).

## Validation

- `build.bat -t gtest -p vs2026` → `ctest --preset gtest-vs2026` green,
  including the new test.
- Disabling the function cleanly drops the test (no build break).

## Failure cases

- Test reaches into disk/middleware → test the component, not the platform layer.
