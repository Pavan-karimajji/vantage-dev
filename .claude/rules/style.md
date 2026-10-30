# Rules — Style & Headers (R-STYLE)

Normative index. Detail: `docs/file_header_template.md`. Headers:
`templates/file_header.cpp` / `.py` / `.proto`.

| ID | Rule |
|---|---|
| R-STYLE-1 | Every new `.cpp/.hpp/.h/.py/.proto` gets the **file header block** (`Copyright … / Proprietary / COMPONENT: <X> / @file / @brief / @author`). `COMPONENT:` per R-NAME-6. |
| R-STYLE-2 | **Minimal diffs** — add new logic, don't rewrite whole functions. Unchanged code re-emitted inside a rewritten block reads as new and invites pushback. |

Formatting is enforced by the shared `.clang-format` (R-BUILD-5).
