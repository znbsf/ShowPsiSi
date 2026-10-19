# Local DVB-I metadata API

The Qt/Web workspaces
consume these C++ JSONL/MCP methods through an independent local-document input
mode; see [DVB-I workbench](DVB_I_UI.md) for presentation and test boundaries.
Do not present this bounded metadata inspector as a completed DVB-I receiver.

## Baseline and supported projection

The explicit profile is `etsi-ts-103770-v1.2.1`, the published
[ETSI TS 103 770 V1.2.1 (2024-09)](https://www.etsi.org/deliver/etsi_ts/103700_103799/103770/01.02.01_60/ts_103770v010201p.pdf).
The recognized root is `ServiceList` in
`urn:dvb:metadata:servicediscovery:2024`; URI children belonging to the common
types schema use `urn:dvb:metadata:servicediscovery-types:2023`. Prefix spelling
is not identity. Older namespaces and newer draft namespaces are **raw-only**;
there is no automatic version upgrade.

The bounded projection covers list/service identifiers and multilingual names,
service instances and their alternatives, declared DVB triplets and DASH URIs,
regional LCN table assignments and nested region identities. Additional XML,
unknown extensions, other delivery details, applications, schedules and rights
remain available as raw XML elements without fabricated interpretation. Every
node is `announced_only`; metadata does not prove media reception. This is not
full XSD validation or edition-wide conformance. Broadcast triplets are never
joined to a TS service by name, channel number or partial identifiers.

Duplicate declared identities remain separate conflict nodes. Same-name
services are separate. Conflicting LCN assignments within a table remain
alternatives; regional tables do not overwrite each other. XML values and
original spelling remain inspectable when a projected integer/boolean is
invalid or outside the implementation's unsigned-64-bit numeric bound.

## Calls

- `import_dvbi`: required `path` and `profile`; optional
  `expected_document_revision`. A local regular UTF-8 XML file is parsed into a
  candidate document. Successful commit increments the independent document
  revision, including an identical reimport. A stale expected revision, read
  error, malformed XML, unsupported encoding or resource-limit error leaves
  the previous metadata document and the entire TS session/preview untouched.
  A well-formed unsupported namespace succeeds as an explicit raw-only
  document. No input bytes are written.
- `query_dvbi`: optional exact `document_revision`, `offset` (default 0) and
  `limit` (default 200, maximum 500). Returns document metadata, semantic nodes,
  accurate total counts and a continuation page. An empty page is not an empty
  document. Query has no implicit name-based filtering or association.
- `inspect_dvbi`: required `document_revision`; optional `element_id` (default
  `e0`), `source_offset` and `source_limit` (maximum 65,536). Returns one raw XML
  element, attributes, child IDs and a page of the authoritative original file
  bytes in hex. Source pagination is independent of element selection.
  `child_offset` and `child_limit` (default 200, maximum 500) page the additive
  `child_summaries` with names, paths, locations and `has_children`; `child_page`
  reports total and continuation. Original `element.children` IDs are retained.

`source` identifies `kind: local_dvbi_xml`, absolute local path, byte count,
UTF-8 encoding and SHA-256 of the exact bytes read, including BOM and line
endings. The parser version is included. `document_revision` is independent of
TS analysis revision and cutoff. Document replacement invalidates old locators;
query and inspect reject a mismatching requested revision.

## Evidence precision

Semantic evidence contains the document revision and hash, opaque `element_id`,
namespace-expanded path, precision (`element` or `attribute`) and line/column.
The line and column identify the **element start**, explicitly declared by
`line_precision: element_start`; an attribute path does not claim an exact
attribute character position. Paths include namespace URIs and occurrence
indices, while lookup uses the opaque element ID and revision.

`element.text` is XML-normalized UTF-8 character data. Entity references and
line endings may have been normalized by the XML parser; it is not the
original source. `original_source.data` is hex of original file bytes with
explicit byte offset/length/total. No transcoded display position is described
as an original byte offset. `original_byte_offset` is captured by Expat at each
start-element callback and checked against the original opening `<` byte. Both
elements and evidence explicitly label `byte_offset_precision: element_start`;
this does not claim an exact attribute span.

Original-source pages additionally expose exact `text` with `text_offset` and
`text_length` measured in original UTF-8 **bytes**. A page cutting a multi-byte
character omits only that partial character from its text view, adjusting these
explicit bounds; the existing hex `offset`/`length` remains unchanged. No U+FFFD
replacement is inserted. `text_start_line` identifies the first original line;
`element_start_character` is a separately labeled UTF-16 display cursor index
within this text, or null when the element start is outside the page. BOM,
comments, XML declaration and original line endings remain unchanged. The
original hex page supplies `next_offset` independently of its text-safe bounds. There are no invented PID, CRC, section bytes,
packet cutoffs, PAT/PMT associations or broadcast timestamps.

## Security and limits

Pinned Expat 2.9.0 is statically linked from unmodified official source. The
archive identity, per-file hashes and license are retained under
`third_party/expat`. TSDuck's configuration-oriented XML parser is deliberately
not used for this input: the SDK probe accepted case-mismatched closing tags,
unbound prefixes and invalid/unknown entity syntax.

- Regular-file handle validation; directories, FIFOs, devices and symlinks /
  Windows reparse points are refused. NUL paths, UNC/device namespaces and
  Windows mapped remote drives are refused before opening. Ordinary mounted
  filesystems still follow the OS filesystem contract; this is not a network
  sandbox. File size is checked before reading and
  each bounded chunk is checked again, including files that grow.
- Maximum original input 4 MiB, nesting 48, elements 20,000, total character
  data 2 MiB, per-element text 64 KiB, attributes 64 per element, attribute value
  64 KiB, expanded name 1,024 bytes and cumulative expanded paths 8 MiB.
- Up to 100 semantic diagnostics, with an explicit omitted count. Remaining raw
  evidence is preserved rather than converted into invented semantics.
- UTF-8 XML 1.0 only, optionally with UTF-8 BOM. Other encodings and NUL are
  explicitly refused. Expat validates names, encoding, namespace bindings,
  duplicate expanded attributes and well-formedness.
- Reject DTD at the start callback. Parameter entities are disabled and the
  external entity callback always fails. Entity and allocation amplification
  guards and reparse deferral are enabled and their setup results checked.
  XInclude, schema hints, `xml:base`, media, application and logo URLs are inert
  retained metadata. No XML-triggered network/file resolver exists.
- Two-second cooperative import deadline, checked during reads, parsing and
  projection. An operating-system stall on a regular-file read may delay that
  check; this is not a process sandbox or hard real-time termination guarantee.
  Import is a bounded FIFO request, with **no asynchronous cancel API yet**.
  `cancel_analysis` retains its existing TS-only behavior.

## Validation boundary

`tests/dvbi_fixture.py` consists of independently authored synthetic documents,
not copied standards examples. `tests/test_dvbi.py` exercises the actual compiled
core and MCP routes, namespace aliases/spoofs, hash/byte round trips, revisions,
failed replacements, TS preview retention, alternatives/conflicts, hostile XML,
limits, regular-file handling and a loopback no-fetch trap. Upstream source
manifest hashes are checked. No external sample, live service retrieval, playback,
or Windows desktop interaction is implied. UI validation is reported separately
in [DVB-I workbench](DVB_I_UI.md).

Run after building both real native targets:

```sh
SHOWPSISI_CORE="$PWD/build/bin/showpsisi-core" \
  python -m unittest discover -s tests -p test_dvbi.py -v
```

Static-dependency source and notice identities are pinned in the
[portable redistribution gate](PORTABLE_LICENSE_REVIEW.md#protocol-increment-static-expat-290-2026-10-19).
Expat MIT/per-file notices and source provenance are mandatory in the package.
Fresh exact-revision Windows packaging and runtime acceptance remain required.

Source-navigation tests cover UTF-8 byte boundaries, BOM/XML declarations,
exact source markers and bounded unknown-namespace child pages. Native file
handling has separate OS-specific tests: POSIX uses an owned FIFO with no writer;
Windows checks directory/DOS-device/alternate-stream refusal and an owned named
pipe. Results on one platform do not establish the other platform's behavior.
