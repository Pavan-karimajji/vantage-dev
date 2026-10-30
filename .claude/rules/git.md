# Rules — Git / Submodule (R-GIT)

Normative index. Detail: `git_strategy.md`, `docs/partial_clone_workflow.md`.

| ID | Rule |
|---|---|
| R-GIT-1 | One repo per component; **git-submodule architecture**. Changes commit **inside the submodule first**, then the superproject pointer bumps. |
| R-GIT-2 | Commit/push **only when asked**; branch before committing on a default branch. |

See also: `workflows/submodule_commit_order.md`.
