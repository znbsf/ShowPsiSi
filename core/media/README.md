# Read-only media wire readers

Source snapshots adapted from the user-owned NXTSA src/nxtsa files on 2026-10-26.
No runtime path/API dependency on that project. Namespace renamed, Teletext CLI,
file reading and JSON printing removed. ShowPsiSi owns input framing, revision,
capture bounds and page presentation. PES adaptation enforces direct TS payload
start (no PSI pointer-field heuristic), retains exact source fragments and bounds
consecutive duplicate payloads. Teletext remains an explicit partial Latin Level 1
interpretation; source semantics do not imply full page/receiver conformance.

Original SHA-256:
- pes_engine.h: `34043b5534ff3c4a08938a7cdc0b978d3a9d7c3dfd1364d43c7f32e3298762d7`
- pes_engine.cpp: `948a81fa59625b5eaece3aac6ecf6294ce32835cf56f301beb4a4129e1b78b2f`
- teletext.h: `37882a81de5271dc73213410946472b8685ccc0649ecaa6cff65e3ad52f38e1d`
- teletext.cpp: `e74e5e1f345f8a1006d6123e8f0fe0b47b4e0bdad99b47d5589a4402f9bb7015`
- teletext_render.h: `97bbc0e225b8695fdfb6e7b824f84f3626a2365bd87dcde01cdad9fc2594f14e`
- teletext_render.cpp: `653dc0417500754f563cef7ddb019dc5b2327a7bba1a7320f78a08da193c967a`
- teletext_body.h: `603465c927b0c9d12efecd81a9577e38218212bda55294cfa506e2cff275eff1`
- teletext_body.cpp: `7cd8b63963006f8b524da2f0e855fed7076991bd05f509608aa6fab72d36a66a`

ShowPsiSi display integration additionally tracks C4-cleared absent rows as
known display blanks with no received source, and resets decoder/page context
at transport gaps while retaining previously validated capture snapshots.

## Optional decoder and output

DecoderProcess.h executes a separately configured, hash-pinned external FFmpeg
without a shell. Windows Job ownership bounds memory, descendants, wall time
and output; cancellation belongs to the matching request. The binary is not
bundled and is not a new application-linked library. AudioPlayback.h owns only
its Windows PCM buffer/handle, never a system-wide device reset. See API decoder
pin and docs/NXTSA_UI_UX_PARITY.md for tested formats and derived preview timing.
