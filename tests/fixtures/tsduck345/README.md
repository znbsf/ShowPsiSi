# TSDuck 3.45-4798 protocol fixtures

These are small synthetic signalization vectors, not captured broadcast samples
or independently certified conformance vectors. Every XML file was validated and
compiled by the official release's actual `tstabcomp` against its installed
`share/tsduck/tsduck.tables.model.xml`. `manifest.json` records the compiler
identity, exact flags, expected PID/context, XML SHA-256 (LF-normalized for
portable Windows checkouts), section SHA-256 and full
CRC-correct binary bytes. Ordinary tests need only the JSON; no binary fixture
files or SDK files are checked in.

Reproduce without changing the manifest:

```sh
python tests/fixtures/tsduck345/reproduce.py --compiler /path/to/tstabcomp
```

Configure the compiler's usual runtime library path for an extracted SDK. The
script rejects a different compiler version, compiles each source in a temporary
directory, and checks every output byte. To validate application behavior, build
the current core and run:

```sh
python -m unittest discover -s tests -p test_protocol_coverage.py -v
```

The application tests packetize these sections and assert actual JSONL native
trees, fields and raw section bytes. Compiling XML alone is not an application
pass. Most added tables need their recorded `extra_pids`; AMT also tests discovery
of its fixed PID 0x002E. PID values here are intentional synthetic choices.

## Context and provenance

- `--china` selects DTMB only. The SDT separately requests UTF-8, and the bytes
  contain the explicit 0x15 selectors; no GB2312/GB18030 default or UTC+8 is assumed.
- ATSC multiple-string and fixed UTF-16 channel-name fields test Chinese, Greek
  and accented BMP text. The fixture set does not establish supplementary-plane
  broadcast-text fidelity. UTF-8 filesystem paths are a separate engine test.
- DVB context is explicit for DSM-CC name/CRC descriptors. Their upstream
  registration is table-specific DVB, even though the enclosing DII is MPEG.
  The app protects unknown contexts from presenting CRC tag 0x05 as an MPEG
  registration descriptor. The XML and raw bytes remain reproducible.
- ISDB advanced cable's official SDK header warns that its syntax was rebuilt
  from a JCTEA block diagram and still needs real-stream verification. This tests
  that implementation, not independent conformance. Extension 1 is padded by the
  compiler to 88 bytes; the tests assert the padding too.
- VANC covers program-to-component registration inheritance. AVS3's explicit
  `AVSV` registration fixture accepts only correct AVS3 fields or guarded generic
  bytes with a warning (the observed Linux result). The real-PDS fixture strictly
  asserts fields and sibling/session isolation. Codec decoding and RF reception
  are outside scope.
- DSM-CC block data, font URIs, compression wrappers, license data and FEC bytes
  remain data. No fixture triggers a download, license request, decompression,
  decryption, FEC recovery or carousel-file extraction.

Pinned upstream references:

- [Release v3.45-4798](https://github.com/tsduck/tsduck/releases/tag/v3.45-4798)
- [DSM-CC DII implementation](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/tables/mpeg/tsDSMCCUserToNetworkMessage.cpp)
- [DSM-CC name descriptor registration](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/dvb/tsDSMCCNameDescriptor.cpp)
- [DSM-CC CRC descriptor registration](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/dvb/tsDSMCCCRC32Descriptor.cpp)
- [AVS3 video registration](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/avs/tsAVS3VideoDescriptor.cpp)
- [SMPTE ancillary-data registration](https://github.com/tsduck/tsduck/blob/v3.45-4798/src/libtsduck/dtv/descriptors/smpte/tsSMPTEAncDataDescriptor.cpp)

The complete tested/SDK-only distinction is in
[`docs/PROTOCOL_COVERAGE.md`](../../../docs/PROTOCOL_COVERAGE.md).
