# BIOP wire reader

Adapted from the user-owned NXTSA reference project, src/nxtsa/biop_message.{h,cpp},
snapshot read on 2026-10-26. This is a source snapshot, with no runtime path or
API dependency on NXTSA. CLI/filesystem/JSON printing removed; namespace changed;
4096-object bound added. Complete module bytes and identity are owned by
ShowPsiSi's DSM-CC reconstruction, not this parser. Legacy IOR profiles remain
explicit compatibility evidence, not normative carousel identity.

Original SHA-256:
- biop_message.h: `d7be4abc72ff41e6d30a446f2ab908b5dd3b3b61b143adb48c362cbb805f5e28`
- biop_message.cpp: `b57c1be3dad412d6cbf40ce2106637134834dbc177e5504cd70157bdbb11eb64`

DSI reader adapted from the same snapshot; CLI/filesystem/printing removed:
- dsmcc_dsi.h: `22703c7c3530358c3c1fdb7966fb1272ba3d21ec3f72f11ec8bef1bceb810013`
- dsmcc_dsi.cpp: `3ca05b3f80f87da259fa53ce000f1d5ce35b970ff3d024d8455f9380b46a54c2`

Local validation additions: bound alternate IOR header before reading; verify File
objectInfo declared content size; partial BIOP target modules do not resolve
references as complete. These changes are covered by production-core tests.
