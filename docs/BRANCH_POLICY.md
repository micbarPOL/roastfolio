# Branch policy: roastfolio_ui_20

`roastfolio_ui_20` must not be merged into `dev`, `test` or `prod` until explicitly approved. Deploying it to `dev` or `test` for testing is allowed.

Enforced locally by hooks in `.githooks/` (enabled with `git config core.hooksPath .githooks`; each clone must run this once):

- `reference-transaction`: aborts any local update of `dev`/`test`/`prod` that brings in commits unique to `roastfolio_ui_20` (merge commits, fast-forwards, `reset`, `branch -f`).
- `pre-push`: refuses pushes that would put those commits on remote `dev`/`test`/`prod`.

Still allowed: committing on the branch, pushing it, and merging `dev`/`test`/`prod` into it to stay current.

Approved override: `ALLOW_BRANCH_MERGE=1 <git command>`.

Limits: hooks are client-side and bypassable (`--no-verify`, other clones). Server-side protection needs GitHub branch protection or rulesets.
