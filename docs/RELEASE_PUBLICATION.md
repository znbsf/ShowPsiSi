# Verified release publication

The normal main/PR CI workflow builds and validates candidates; it cannot publish.
The separate `release.yml` workflow needs an explicit release request. Its sole
job grants `contents: write` (tag, draft/release, asset upload) and `actions: read`
(exact CI/artifact inspection); other permissions are disabled. It uses only the
job's short-lived GitHub token, never a PAT, new credential or saved local token.

## Request v0.1.0

After the reviewed PR is merged, wait for the **new main-push** `ci.yml` run for
that exact current main SHA. All five jobs and the Windows distribution/acceptance
steps must succeed. PR merge-test artifacts cannot be published. Recoverable CI
reruns are supported: the publisher reconstructs each named job's latest result
from the run's per-attempt API responses. Previously successful jobs may be
retained when only failed jobs are rerun; a later failure cannot reuse an earlier
pass. Up to 100 attempts are boundedly inspected. A run attempt changing during
publication stops the operation.

Actions artifact metadata identifies the run, not its individual attempt. The
publisher does not claim otherwise: it requires one unique artifact of each
expected name, all from the exact run/source, and cross-checks the entire bundle's
portable manifest, every file, setup hash, prerequisite provenance, installer
acceptance hashes and common checksums. Duplicate or incompatible mixed artifacts
fail. No dummy source commit is needed merely to recover a failed job.

The connector-compatible path is:

1. Record the verified current `main` SHA and that successful main-push CI run ID.
2. Create `release-publish/v0.1.0` from that exact SHA. Do not replace an unrelated
   existing branch or force-push unknown history.
3. Make exactly **one commit**, with current main as its sole parent, adding only
   `.github/release-request.json` (no workflow, script or other changes):

   ```json
   {
     "schema_version": 1,
     "version": "0.1.0",
     "source_sha": "REPLACE_WITH_EXACT_40_CHARACTER_MAIN_SHA",
     "ci_run_id": 123456789
   }
   ```

The file must be at most 2 KiB, with exactly these four keys. The workflow trigger
is limited to this path on `release-publish/**`; the publisher also requires the exact
`release-publish/v<canonical-version>` ref. The publisher verifies the
commit parent and changed-file list through GitHub, then fetches the bounded
request as data. It always checks out and executes trusted **main**, with checkout
credentials disabled; it never executes the request branch or artifact code.
The `workflow_dispatch` alternative is restricted to current main and accepts
only source SHA and CI run ID. Version comes from canonical CMake in that exact
checkout; the request must agree. A matching `docs/releases/v<version>.md` must
already be reviewed in main. Changing CMake alone does not publish anything.
Future releases need their own explicit authorized request and exact CI evidence.

## Fail-closed validation and publication

Before any write, the publisher verifies:

- Fixed repository name and numeric ID, current main SHA, official main-push CI
  workflow identity, successful completion, all five exact jobs and Windows gates.
- Exactly one of each required artifact from that same run/repository/source.
  The API-reported archive SHA-256 and exact size are checked while downloading.
- Downloads start at constructed fixed-repository GitHub API endpoints. Redirect
  destinations allow only GitHub release CDNs and the Actions
  `productionresultssa<number>.blob.core.windows.net` artifact namespace. Every
  redirected request drops Authorization. HTTP, userinfo, arbitrary Azure hosts,
  nonstandard ports, host changes between CDNs and excessive redirects fail.
  No signed download URL or token is logged or persisted. API writes do not follow
  redirects and are never automatically retried after an uncertain result.
- Extraction has compressed/file/count/expanded-size bounds, rejects traversal,
  Windows reserved/alternate-stream names, links/devices, encryption and duplicate
  or case-colliding paths. No package executable, PowerShell, CMD or module runs.
- Exact versioned setup and portable filenames, identical common two-entry
  SHA256SUMS, setup/ZIP hashes, all portable manifest file sizes/hashes, build and
  source/version identity, portable marker, exact redistribution/source/notice
  inventory, runtime minimum and manifest-bound validation.
- Portable prerequisite preflight cases; installer build/prerequisite provenance;
  exact setup/manifest-bound lifecycle acceptance, shortcut/settings/payload
  cleanup, process mutex and expected positive/negative installer exit results.
  A blocked distribution record fails. Clean-machine, native-dialog and actual
  missing-runtime-bootstrap flags stay explicitly false rather than becoming
  inferred passes.
  Prerequisite provenance is compared in full. Its UTC retrieval timestamp may
  differ only by insignificant fractional trailing zeros introduced by JSON
  serialization (for example, `.5633900Z` and `.56339Z`). Calendar/time syntax is
  validated, no fractional precision is rounded away, and all other fields must
  remain equal. Original archive/file bytes and hashes are never rewritten.

Only then can it create the fixed-version tag at the exact source and a draft
release. It uploads only the versioned setup, versioned ZIP, common SHA256SUMS
and minimal `release-provenance.json`. Reviewed release notes disclose unsigned
installer status, Windows 10 1809+/11 x64 support, first-install Internet/UAC,
manual portable ZIP replacement and unverified acceptance boundaries.

All assets are checked for exact name/size/GitHub SHA-256 and independently
redownloaded to compare actual bytes. Main/CI/tag/metadata are checked again
before clearing draft status. A final read verifies public release metadata,
tag target and every asset's downloaded bytes. A green compile or successful
upload alone is not reported as publication.

## Interrupted attempts and conflicts

Rerun the same publication workflow to reconcile a transient failure. Matching
partial drafts can gain only missing exact approved assets. An already published
exact match is verified without mutations. Unknown, duplicate, starter/incomplete,
changed or extra assets; changed release text/target; or a mismatched existing
tag stop the process. The publisher never deletes assets, overwrites bytes,
replaces a tag or silently repairs a mismatched published release. A conflict
needs explicit review before any separate corrective action.

An interruption after tag/draft creation may leave that exact tag and a private
draft. An uncertain API response may have succeeded server-side. Inspect or rerun
the same request; do not blindly recreate or clean it up. If main advances during
validation, publication stops (possibly leaving an exact draft) and needs a new
reviewed source/CI request. The workflow's non-cancelling concurrency group avoids
two publisher jobs racing; it cannot stop a separately authorized maintainer from
changing repository state, which the repeated checks detect where observable.

## Local contract tests and references

`python -m unittest discover -s tests -p test_release_publisher.py -v`
uses fake network/API state and fake payload bytes; it performs no release writes
or artifact execution. These tests do not replace hosted Windows or release API
validation.

- [GitHub Actions artifact REST API](https://docs.github.com/en/rest/actions/artifacts)
- [GitHub workflow jobs API](https://docs.github.com/en/rest/actions/workflow-jobs)
- [GitHub releases API](https://docs.github.com/en/rest/releases/releases)
- [GitHub release assets API](https://docs.github.com/en/rest/releases/assets)
- [GitHub toolkit artifact downloader](https://github.com/actions/toolkit/blob/main/packages/artifact/src/internal/download/download-artifact.ts)
- [Runtime and installer boundaries](WINDOWS_INSTALLER.md)
- [Application update trust contract](UPDATES.md)
