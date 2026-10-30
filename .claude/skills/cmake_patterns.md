# Skill: cmake_patterns

CMake conventions. Enforces `R-BUILD-*`, `R-VAR-*`. Backing doc:
`docs/sw_build_architecture.md`.

## Presets

- Configure presets named `<target>-<platform>` (`sil-vs2026`, `gtest-vs2026`,
  `standalone-vs2026`). A hidden parent preset (`vs2026`) pins generator/arch/
  toolset/toolchain; per-target presets inherit it.
- The toolchain file is Conan-generated; never hardcode a path.
- Release configs only today — Debug is additive later (`build.bat` already
  derives config from a `_debug` platform suffix).

## Namespaced targets + ALIAS

Each component exports its library under its Conan target name via an `ALIAS`:

```cmake
add_library(AdasDf::AdasDf ALIAS df_sil)
```

Consumers link the namespaced name and guard the `find_package`:

```cmake
if(NOT TARGET AdasDf::AdasDf)
  find_package(AdasDf CONFIG REQUIRED)
endif()
target_link_libraries(<tgt> PRIVATE AdasDf::AdasDf)
```

This makes a consumer identical whether the dependency is in-tree source
(superbuild) or a downloaded/editable Conan package — zero branching.

## Protobuf generation

Driven from `interfaces` CMake (`adas_generate_protos(...)`); `protoc` chosen
deterministically (`protobuf_BUILD::protoc` preferred). Generated code is
build-local. Add new `.proto` files in `modules/interfaces/CMakeLists.txt`.

## Function selection (df)

`ENABLED_FUNCTIONS` is a CMake list cache var; `if("aeb" IN_LIST ...)` guards
each function's `add_subdirectory` + test sources + `ADAS_FN_AEB_ENABLED` define.
Not a runtime registry (R-VAR-5).
