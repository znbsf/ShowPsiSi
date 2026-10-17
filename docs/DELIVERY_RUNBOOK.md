# Delivery and interruption recovery

Use this runbook for ShowPsiSi delivery work, alongside [cloud development](CLOUD_DEVELOPMENT.md), [native Tauri validation](NATIVE_TAURI_VALIDATION.md), and the [portable pipeline](PORTABLE_PACKAGE_PIPELINE.md). Preserve their platform and evidence boundaries.

## Continuous execution rule

- Local tests are an intermediate gate, not completion. Continue the authorized sequence: validate the intended changes → publish the reviewed branch → create/update the authorized PR → observe hosted CI → diagnose and fix failures → rerun validation → verify the requested acceptance outcome.
- Keep working through recoverable failures within scope. A queued/running CI job or unchanged status is still pending. Follow the relevant run until its outcome is known, checking newer runs when a commit supersedes it.
- Immediately report a real blocker, its impact, and the exact decision, permission or environment needed. Do not silently pause. Continue independent authorized work while dependent work is blocked.
- This runbook grants no new permissions. Respect user stop/cancel instructions and required approvals. Do not merge, release, install dependencies, change access, bypass security controls or switch to the owner's computer merely to finish a loop.
- A running session can continue work; background execution across session loss is not guaranteed. Save a resumable checkpoint, and state an interruption or unavailable monitoring honestly rather than promising unattended execution.

## Checkpoint before a handoff or interruption

Keep the latest checkpoint in the delivery report or relevant project validation record. Do not store credentials. Record:

- UTC timestamp, task outcome requested, authorized scope and remaining acceptance gates.
- Worktree, branch, full HEAD SHA, upstream and changed files, including staged and untracked files; identify work owned by another contributor.
- Exact tested SHA, commands, environment/platform, outcomes and evidence locations. If tests used uncommitted changes, state **HEAD plus dirty patch**, identify that patch and untracked inputs, and do not label the clean HEAD as tested. Retest the final published revision where needed.
- Publication state: intended remote branch, last verified remote SHA, push result or uncertainty, PR URL/head/base/state, and merge SHA if applicable.
- CI run URL/ID, source SHA (and PR merge/test SHA when different), job conclusions, artifacts and outstanding checks. Record “unknown” when unverified.
- Next concrete action, active blocker or approval request, and the completion condition. A checkpoint is a resume aid, not a completion claim.

## Resume by observing before writing

1. Read the checkpoint and current user instructions. Re-establish the worktree and local state. These Git checks are independent of a particular assistant/tool:

   ```sh
   git rev-parse --show-toplevel
   git branch --show-current
   git rev-parse HEAD
   git status --short --branch
   git diff --name-status
   git diff --cached --name-status
   git ls-files --others --exclude-standard
   git log -5 --oneline
   git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'
   ```

   An absent upstream is a fact to record, not permission to invent one. Do not reset, clean or overwrite another contributor's files.

2. Verify the remote branch against the intended destination before retrying a push:

   ```sh
   git ls-remote --heads origin "refs/heads/$(git branch --show-current)"
   ```

   Run this only after confirming `origin` and the branch are the intended target. If authentication or transport is unavailable, use the authorized repository service to read the same remote ref. Never copy tokens into the worktree. Local remote-tracking refs can be stale.

3. Read the live PR, CI runs and any requested release/artifact state through the repository service or its authenticated CLI. Match full SHAs; do not reuse a green result for an earlier revision. Before retrying an uncertain write, determine whether it already succeeded. Reuse an existing matching PR/run/publication rather than duplicating it. If state cannot be established safely, report that blocker.
4. Reconcile remote movement and concurrent edits with the checkpoint. Resume the first incomplete authorized step. Do not force-push or overwrite remote changes to restore an old checkpoint.

## ShowPsiSi verification route

Select tests for the actual changed components and retain the existing regression gates. See `tests/README.md`, `scripts/check.sh` and `.github/workflows/ci.yml` for the current full matrix. With the documented SDK/build environment already prepared, examples are:

```sh
python scripts/make_fixture.py
SHOWPSISI_CORE="$PWD/build/bin/showpsisi-core" \
SHOWPSISI_TEST_CORE="$PWD/build/bin/showpsisi-core-test" \
  python scripts/ci/windows_native_checks.py --artifacts artifacts/delivery-native --engine
python -m unittest discover -s tests -p test_portable_package.py -v
python -m unittest discover -s tests -p test_qt_resource_paths.py -v
git diff --check
```

These commands do not establish that dependencies are installed or that all platform gates passed. Use the Windows workflow for Windows staging/runtime/archive verification. Preserve the inventory-bound redistribution review and fail-closed ZIP gates; a license blocker must be reported, never changed to a passing flag for delivery convenience.

## Completion evidence

Report completion only against the user's requested outcome, with the verified branch/SHA, PR or publication link, relevant final CI conclusions, artifact availability and remaining limitations. If authorized merge is part of that outcome, verify the merge result and relevant post-merge checks. If only implementation or a draft was requested, do not expand that into publication or merge.

For a portable deliverable, distinguish a staged candidate, a validated ZIP, an uploaded downloadable artifact and a published release. Verify the requested artifact exists and corresponds to the accepted source/manifest; build success alone is insufficient. Qt offscreen checks, native compilation and process startup do not prove native Save/Cancel/overwrite dialogs, GPU behavior, a clean Windows machine, or Tauri/WebView2 interaction. Unverified acceptance gates remain explicit.
