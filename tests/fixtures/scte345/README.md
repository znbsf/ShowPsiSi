# Synthetic SCTE section fixtures

These 11 XML inputs were compiled with official TSDuck **3.45-4798** and its
installed XML model. `manifest.json` retains the exact compiler identity/options,
LF-normalized XML SHA-256, binary SHA-256 and full CRC-correct section bytes.
No standard PDF, confidential specification or captured alert is included.
Names, IDs, audio filenames and alert text are deliberately synthetic.

Reproduce without changing checked-in bytes:

```sh
python tests/fixtures/scte345/reproduce.py --compiler /path/to/tstabcomp
python -m unittest discover -s tests -p test_scte_extensions.py -v
```

Set the SDK's runtime environment normally and point `SHOWPSISI_CORE` at the
built production engine. Runtime tests need only the manifest, not tstabcomp.
The compiler uses `--atsc` for the shared SCTE18/ATSC multiple-string context;
the application tests explicitly exercise `scte`, `atsc`, `auto` and isolation
from `dvb`. Compilation alone is not proof of application decoding.

Measured paths:

- SCTE18 EAS event/sequence IDs, timing, priority, English/French text, geography,
  both exception forms and three table-specific EAS descriptors. The synthetic
  audio filename/carousel IDs remain data; no audio is fetched or played.
- Explicit SCTE mode discovers EAS at the established PSIP PID 0x1FFB, matching
  auto/ATSC behavior. Unadvertised PIDs, including 0x1FFC captures, remain explicit
  `extra_pids`; accepting TS-framed bytes does not implement an OOB/CableCARD link.
- SCTE35-1 program/component/immediate/cancel splice inserts, program/component/
  cancel schedules, null/bandwidth/private commands, unspecified time signal,
  DTMF/audio/TAI time descriptors, wire PTS and separate adjustment.
- Corrupt CRCs remain invalid evidence. Encrypted and truncated-but-valid-CRC
  payloads retain generic bytes rather than claimed semantic decoding. Exact
  original bytes survive untouched valid-section export.

These are bounded synthetic application tests, **not** independently certified
conformance vectors, emergency receiver behavior, ad insertion/splicing,
encrypted-message decoding, SCTE35-2 event signaling or SCTE65 support. In
particular, the SDK's ATSC A/81 Satellite VCT is not SCTE65's short-form VCT.

Pinned upstream implementation references:

- [SCTE18 EAS registration and parser](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/tables/scte/tsCableEmergencyAlertTable.cpp)
- [SCTE35 table and encryption boundary](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/tables/scte/tsSpliceInformationTable.h)
- [SCTE18 audio descriptor context](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/scte/tsEASAudioFileDescriptor.h)

Official catalogs identify [SCTE18 2018](https://account.scte.org/standards/library/catalog/scte-18-emergency-alert-messaging-for-cable/)
and [SCTE35-1 2023r2](https://account.scte.org/standards/library/catalog/scte-35-1-digital-program-insertion-cueing-message-part-1-legacy-splice-based-and-time-based-signaling/).
Their search-indexed metadata was accessible during this work; direct catalog
retrieval returned 403, and complete normative text was not independently
reviewed. The fixtures test the pinned SDK representation, not an invented
interpretation of unavailable clauses.
