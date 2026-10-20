# Responsive analysis validation

Local verification date: 2026-10-20. This report describes a cloud Linux
environment, not the user's mechanical disk or a native Windows desktop.
The behavioral contract and remaining limits are in
[RESPONSIVE_ANALYSIS.md](RESPONSIVE_ANALYSIS.md).

## Reproducible transport comparison

Baseline: PR #27 commit `e80dabb692ca055eaf735d170976ab6787f624c5`,
legacy response mode. Candidate: compact responses followed by complete
hydration of all eight collections, using `scripts/benchmark_analysis.py`.

Both used the same 8,388,560-byte synthetic file containing 44,620 packets and
5,000 unique empty EIT sections. It has **zero EPG events**: this is a table
cardinality/transport stress test, not realistic programme decoding.

Input SHA256:
`26ed0884df2cbc3900dadf07727e2210acbeeeeae3b0aafbd43e72c49b42ec9e`.

| Measurement | Legacy | Compact + all pages |
| --- | ---: | ---: |
| Fully consumed wall time, round 1 | 17,230.1 ms | 1,577.4 ms |
| Fully consumed wall time, round 2 | 5,070.1 ms | 2,240.2 ms |
| Fully consumed wall time, round 3 | 4,736.1 ms | 897.2 ms |
| Largest individual JSON message | 29,830,769 bytes | 223,761 bytes |
| Largest progress message across rounds | 29,790,647 bytes | 1,492 bytes |
| Tables / logical groups / table-history rows | 5,000 / 5,000 / 5,000 | 5,000 / 5,000 / 5,000 |

Execution order was legacy 1, compact 1, compact 2, legacy 2, legacy 3,
compact 3, without concurrent application builds or test suites. Startup and
Python client decoding are included; cache effects are uncontrolled. The wide
timing variation is retained rather than selecting the best run. These results
do not establish a universal speedup or HDD throughput.

Binary SHA256:

- Baseline core:
  `39cf5bea488df8b05b4285fe66bce6f3d9630a7a9b237250a357f0a781922e0a`.
- Candidate core:
  `7a4947da1a680bda003d3395952c1f0956f7a71ab530dc38305b45cf0385c823`.
- Candidate core source:
  `f4f36c181ef0e24731f09e09c85a91f62893436ee4c750a6f4db2d066288a574`.

## Functional and interaction evidence

- Strict engine aggregate: 28 suites, 634 discovered tests, 633 executed,
  zero failures/errors. One existing optional real-recording test was skipped
  because its separately sourced recording was absent.
- Real-engine Chromium workbench: 76/76 tests passed; shared scan/search helpers: 3/3.
- A retained isolated Qt run passed 11 tests / 16 timed subflows, with GUI
  heartbeat gaps of 106–300 ms and complete 5,000-row collections. This is
  historical intermediate evidence, **not final Qt acceptance**.
- The final local versioned Qt aggregate finished 137 tests: **135 passed,
  2 failed, zero errors/skips**, with unchanged source/binary identities. Both
  failures were 25-second missing-report timeouts in legacy backend-death and
  graceful-close/layout flows. The 10 new analysis tests and the remaining
  topology, DVB-I and protocol suites passed. An earlier aggregate also exposed
  legacy-response projection ordering, corrected with targeted regressions.
- PR #28 hosted CI run `39418321685` tested merge checkout
  `ee598433734b2bcf77f1292cb28d0cd2d7d0629f` (tree
  `46bd5386f6e1b74427710ecf272a32b795136838`). Linux Qt passed **137/137**.
  Windows Qt had **136 passes and 1 cleanup error**: deleting
  `analysis-responsive.log` raised WinError 32 after a completed test. The direct
  Qt process was reaped, but an inherited log handle could still be held by a
  descendant; the exact holder was not identified. A tests-only owned-tree
  teardown correction and an inherited-log regression are pending fresh CI.
  Windows packaging steps were skipped in that failed run, not passed.
- A frozen 18-flow SDK comparison on the optimized source still failed timing
  in 4/9 Qt 6.7.3 flows and 3/9 Qt 6.8.3 flows. All non-timing semantic checks
  passed. Qt 6.7.3 remains pinned; a runtime upgrade is not represented as a fix.
- Later diagnostic experiments also observed approximately 0.5–2.1 s GUI gaps.
  Native JavaScript page-conversion and lazy hidden-tooltip experiments were
  excluded from the delivery snapshot because neither established a full fix.
- Fresh hosted acceptance of the cleanup correction and final production-binary
  large-file desktop smoke are **pending**. No failed threshold is relaxed,
  skipped or converted into a success claim by this document.

## Remaining responsiveness limitation

Compact progress and bounded result pages reduce transport pressure, but do not
make every GUI operation asynchronous or bound the full JavaScript heap.
Results retain complete collections for search and derived views. Diagnostic
profiles support runtime allocation/garbage-collection work before some JavaScript
callbacks; startup/first-frame work is a separate unresolved contributor. These
observations do not establish a single cause for every stall or a final remedy.
Qt derived-view publication is staged and remains busy until presentation
completion. Legacy full responses retain their synchronous projection contract.

The Qt implementation keeps complete result models for global search; paging
does not establish bounded total memory. Individual occurrence lists are paged,
and hidden inspector views defer expensive content until selected.

Native Windows Qt, Tauri/WebView2, the user's particular recordings, and actual
mechanical-disk performance still require their own measurements. Cloud native
interaction and offscreen automation must not be relabelled as Windows testing.
