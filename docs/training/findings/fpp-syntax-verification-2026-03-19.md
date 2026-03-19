# FPP Syntax Verification Findings — 2026-03-19

## What Was Done

The FPP Syntax Agent (fprime-tui-agent-fpp) evaluated 25 FPP code blocks from the v0.03
response analysis run. Two verdicts were incorrect — the agent flagged constructs as invalid
that are in fact valid FPP, confirmed by direct search of FPrimeSampleProject source files.
This document records all verdicts, each backed by file evidence.

---

## Errors Found in Original Analysis

### Q14 — `telemetry port` falsely flagged as invalid

**TUI code:** `telemetry port MyTelemetryPort : int32;`
**Original verdict:** "telemetry port is not valid FPP; port declarations use 'port \<name\>: \<Type\>'"
**Correct verdict:** `telemetry port` IS valid FPP.

**Evidence from FPrimeSampleProject:**
- `fprime/Fw/Interfaces/Channel.fpp:4` — `telemetry port tlmOut`
- `fprime/Drv/LinuxSpiDriver/LinuxSpiDriver.fpp:17` — `telemetry port Tlm`
- `fprime/Drv/LinuxUartDriver/LinuxUartDriver.fpp:26` — `telemetry port Tlm`
- `fprime/Ref/RecvBuffApp/RecvBuffApp.fpp:50` — `telemetry port Tlm`
- ...and 20+ more components

**Actual error in TUI code:** `int32` is a C type, not an FPP type. The type suffix is
not used on `telemetry port` declarations (the port type is implicit for special ports).
Trailing semicolon is also incorrect — FPP does not use semicolons on port declarations.

---

### Q522 — `import Subtopology` falsely flagged as invalid

**TUI code:** `import ComCcsds.Subtopology`
**Original verdict:** "FPP does not have an 'import' keyword for subtopologies"
**Correct verdict:** `import <Name>.Subtopology` IS valid FPP.

**Evidence from FPrimeSampleProject:**
- `fprime/Ref/Top/topology.fpp:19-22`:
  ```
  import CdhCore.Subtopology
  import ComCcsds.Subtopology
  import FileHandling.Subtopology
  import DataProducts.Subtopology
  ```
- `fprime/Svc/Subtopologies/ComCcsds/ComCcsds.fpp:187` — `import FramingSubtopology`
- `fprime/Drv/TcpServer/TcpServer.fpp:4` — `import ByteStreamDriver`

**The TUI's response was correct.** Verdict changed from `major` to `ok`.

---

### Q45 — Correction text was wrong (verdict direction correct)

**TUI code:** `connect GroundCommandPort to FlightCommandPort`
**Original verdict:** "FPP connections require 'connect \<instance\>.\<port\> to \<instance\>.\<port\>'" (MINOR)
**Issue:** The fix itself was wrong. FPP uses `->` arrow syntax, not a `connect ... to ...` keyword.

**Evidence from FPrimeSampleProject:**
- `fprime/Svc/Subtopologies/ComCcsds/ComCcsds.fpp:143`:
  ```
  connections Downlink {
      comQueue.dataOut -> spacePacketFramer.dataIn
      spacePacketFramer.dataReturnOut -> comQueue.dataReturnIn
  ```

**Corrected fix:** Connections use `instance.port -> instance.port` inside a
`connections <Name> { }` block. The standalone port names without instance prefixes
are still the real error, so the MINOR severity remains correct.

---

## Confirmed Correct Verdicts (with File Evidence)

| Q# | Issue | File Evidence |
|----|-------|---------------|
| Q10 | `BaseID = 100` invalid | `Ref/Top/instances.fpp:29`: `instance blockDrv: ... base id 0x10000000` |
| Q21 | `internal port` with type/direction fields invalid | `Svc/ActivePhaser/ActivePhaser.fpp:16`: `internal port Tick drop` |
| Q27 | `telemetry_port` (underscored) invalid | No such form exists; real form is `telemetry port Tlm` (LinuxSpiDriver.fpp:17) |
| Q28 | `DATA PRODUCT { ... }` invalid | `Ref/SignalGen/SignalGen.fpp:54`: `product record DataRecord: SignalInfo id 0` |
| Q35 | `Command { Guarded { ... } }` block invalid | `Svc/SystemResources/SystemResources.fpp:40`: `guarded command ENABLE(` |
| Q40 | `alias = struct { ... }` inline struct invalid | `Ref/DpDemo/DpDemo.fpp:16`: `type StringAlias = string` |
| Q41 | `@big` endianness annotation invalid | No such annotation exists in any FPrimeSampleProject .fpp file |
| Q49 | `Telemetry("...", delta=True)` is Python GDS, not FPP | `Ref/RecvBuffApp/RecvBuffApp.fpp:115`: `telemetry Parameter1: U32 id 3 update on change` |
| Q71 | Standalone `port MyPort[3]` invalid | `FppTest/interfaces/typed_ports_async.fpp:3`: `async input port noArgsAsync: [2] NoArgs` |
| Q85 | Inline guard expression `if (someVariable == 5)` invalid | `state_machine/.../BasicGuardU32.fppi`: `on s if g do { a } enter T` (named guard `g`) |
| Q98 | `parameters { stack_size }` block inside component invalid | `Ref/Top/instances.fpp:31`: `stack size Default.STACK_SIZE` (on instance, not component) |
| Q107 | `state { choice { ... } }` nesting wrong, `exit`/`default` wrong | `state_machine/.../choice/include/Basic.fppi`: `choice C { if g do { a } enter S2 else ... }` |
| Q110 | Uppercase `Port` keyword invalid | All FPP files use lowercase `port` throughout |
| Q349 | `ExternalArray<const int>` is C++ not FPP | `Ref/DpDemo/DpDemo.fpp:179`: `product record U32ArrayRecord: U32Array id 6` |

---

## Updated Totals

| Severity | Original | Corrected |
|----------|----------|-----------|
| ok | 9 | 10 |
| minor | 4 | 4 |
| major | 13 | 12 |

**Net change:** Q522 moved from major → ok. Q14 remains major (different reason).

---

## Impact on RAG Improvement

- **Q14 (telemetry port type):** The TUI correctly used `telemetry port` syntax but used a
  C type. This is a type-system gap — the TUI needs to learn FPP primitive types (U8, U32,
  F32, etc.) vs C types (int32, uint32_t). Not a structural FPP gap.

- **Q522 (import subtopology):** The TUI's answer was correct. The expected answer may need
  review — the evaluator may have penalized the response incorrectly if it flagged the import.

- **Q107, Q85 (state machine syntax):** Real state machine syntax is quite different from
  what the TUI generated. The FPP state machine files in `FppTestProject/FppTest/state_machine/`
  are a strong candidate for indexing in the RAG knowledge base.
