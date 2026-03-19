# F' TUI Response Analysis Report — 2026-03-17

## 1. Accuracy Scorecard

| Category | Total | PASS | PARTIAL | FAIL |
|----------|-------|------|---------|------|
| Architecture | 61 | 22 (36%) | 27 (44%) | 12 (19%) |
| Build System | 30 | 9 (30%) | 11 (36%) | 10 (33%) |
| Coding Standards | 10 | 3 (30%) | 1 (10%) | 6 (60%) |
| Configuration | 2 | 0 (0%) | 1 (50%) | 1 (50%) |
| Deployment | 2 | 0 (0%) | 2 (100%) | 0 (0%) |
| Framework Services | 24 | 8 (33%) | 6 (25%) | 10 (41%) |
| GDS | 55 | 10 (18%) | 16 (29%) | 29 (52%) |
| Implementation | 166 | 32 (19%) | 46 (27%) | 88 (53%) |
| Modeling | 71 | 24 (33%) | 18 (25%) | 29 (40%) |
| OSAL | 11 | 7 (63%) | 4 (36%) | 0 (0%) |
| Testing | 28 | 1 (3%) | 8 (28%) | 19 (67%) |
| Tooling | 24 | 5 (20%) | 11 (45%) | 8 (33%) |
| Troubleshooting | 8 | 3 (37%) | 3 (37%) | 2 (25%) |
| Workflow | 25 | 0 (0%) | 13 (52%) | 12 (48%) |
| **Total** | 517 | 124 (23%) | 167 (32%) | 226 (43%) |

## 2. Knowledge Gap Index

Top missing topics (by frequency):

- [1×] FW_OPTIONAL_NAME macro definition and usage (Implementation)
- [1×] SmHarness::History template for state machine testing (Testing)
- [1×] SOCK_FAILED_TO_READ_BACK_PORT error code (Implementation)
- [1×] ActivePhaser contextType COUNT vs SEQUENTIAL task scheduling (Architecture)
- [1×] GDS Dictionary Loading error causes and recovery steps (GDS)
- [1×] fprime-util new --component wizard Active/Passive/Queued distinction (Modeling)

## 3. FPP Issue Summary

- ok: 10
- minor: 4
- major: 12

**Major issue examples:**

**Q10** — Describe the use of "Base IDs" in an F´ Topology.
  - Uses 'BaseID = 100' — correct FPP syntax is 'base id 100' (lowercase, space-separated), as seen in FPrimeSampleProject/fprime/Ref/Top/instances.fpp: 'instance blockDrv: Ref.BlockDriver base id 0x10000000'

**Q14** — How do you define a port that returns a value in FPP?
  - 'telemetry port MyTelemetryPort : int32;' — 'telemetry port' IS valid FPP (confirmed: Fw/Interfaces/Channel.fpp:4 uses 'telemetry port tlmOut', same pattern in LinuxSpiDriver.fpp, LinuxUartDriver.fpp, and many others). The error is 'int32': this is a C type not an FPP type. The port declaration should omit the type suffix, e.g. 'telemetry port Tlm' — the port type is implicit for special ports. Also, FPP port declarations do not use a trailing semicolon.

**Q21** — How are "Internal Interfaces" used in FPP?
  - 'internal port SensorDataPort { type = SensorData direction = input }' — internal ports in FPP use simple syntax with no type or direction fields. Confirmed from FPrimeSampleProject/fprime/Svc/ActivePhaser/ActivePhaser.fpp:16: 'internal port Tick drop'. The 'type' and 'direction' fields are not valid in FPP internal port declarations.

**Q27** — How do you create a custom GDS Dashboard?
  - 'telemetry_port MyTelemetryPort;' and 'command_port MyCommandPort;' — these use underscores and are not valid FPP syntax. FPP uses two-word forms without underscores (e.g., 'telemetry port Tlm' as in LinuxSpiDriver.fpp:17). GDS dashboard configurations are defined in XML, not FPP.

**Q28** — What are "Array Records" in F´ Data Products?
  - 'DATA PRODUCT MyArrayRecord { scalar_field: ScalarType, ... }' — 'DATA PRODUCT' with uppercase keywords and C-struct-style fields is not valid FPP. Confirmed from FPrimeSampleProject/fprime/Ref/SignalGen/SignalGen.fpp:54: correct syntax is 'product record DataRecord: SignalInfo id 0' (lowercase, colon-separated type, explicit id).

## 4. Source Citation Quality

| Category | With Sources | Relevant | Irrelevant |
|----------|-------------|----------|------------|
| Architecture | 73 | 55 (75%) | 18 (24%) |
| Build System | 24 | 16 (66%) | 8 (33%) |
| Coding Standards | 5 | 0 (0%) | 5 (100%) |
| Configuration | 2 | 0 (0%) | 2 (100%) |
| Deployment | 2 | 0 (0%) | 2 (100%) |
| Error Handling | 3 | 3 (100%) | 0 (0%) |
| Framework Services | 29 | 26 (89%) | 3 (10%) |
| GDS | 41 | 22 (53%) | 19 (46%) |
| Implementation | 213 | 132 (61%) | 81 (38%) |
| Modeling | 67 | 44 (65%) | 23 (34%) |
| OSAL | 7 | 5 (71%) | 2 (28%) |
| Testing | 36 | 8 (22%) | 28 (77%) |
| Tooling | 22 | 10 (45%) | 12 (54%) |
| Troubleshooting | 3 | 2 (66%) | 1 (33%) |
| Workflow | 12 | 9 (75%) | 3 (25%) |

## 5. Command Validity Summary

No tool call attempts detected.
