# Self-Improving RAG Training Pipeline — Design Spec

**Date:** 2026-03-15
**Branch:** `rag_implementation`
**Status:** Design approved, pending implementation

---

## Problem Statement

The TUI's F' responses improve only when a human manually evaluates them and tunes the RAG system. The current evaluation pipeline (Gemini generates Q&A pairs → Gemini evaluates TUI responses) has a ~45% error rate in verdicts because Gemini hallucinates both expected answers and evaluation judgments. There is no mechanism for the TUI to retain knowledge from its own correct responses.

**Goals:**
1. Build an autonomous overnight training pipeline that reliably evaluates TUI responses against authoritative F' source files
2. Curate validated Q&A pairs into a store the TUI can reference via RAG (compound learning)
3. Accumulate a fine-tuning dataset for future model improvement
4. Add `/good` and `/bad` commands for live human feedback during normal TUI usage

**Constraints:**
- Claude has limited token budget — acts as master/orchestrator only
- Gemini has large token budget — runs as evaluator and verification agents
- Must handle rate limits gracefully with backoff and checkpointing
- Must run overnight unattended
- Verification agents must compare against actual source files, not memory

---

## Prerequisites

### External Dependencies
1. **FPrimeSampleProject/** — Contains the flight-ready F' codebase and the training question list (`docs/fprime_training.md`). This directory is gitignored. To obtain it, clone the F' sample project into the repo root: `git clone <fprime-sample-url> FPrimeSampleProject/`. The training pipeline will not function without this directory.
2. **CMUX** — A custom tmux wrapper used in this project for multi-pane terminal orchestration. See `ClaudesLogs/sessions/` reference docs for usage. Agents interact with TUI and each other via CMUX panes — each agent runs in its own tmux pane, and the Master Agent reads/writes to panes using tmux capture-pane and send-keys commands.
3. **Ollama** — Must be running locally (`ollama serve`) with `qwen3:8b` and `nomic-embed-text` models pulled.
4. **Gemini CLI** — Must be installed and authenticated for spawning evaluator and verification agents.

### Directory Setup
The following directories must exist before running the pipeline. The Master Agent creates them at session start if missing:
```
docs/training/
docs/training/scripts/
```

### Implementation Prerequisite: Structured Chat History
The existing `app.py` stores `self.chat_history` as a flat concatenated string. The `/good` and `/bad` commands need to extract the last question/response exchange, which requires `chat_history` to be a structured list of `(role, text)` tuples. This refactoring must be completed before implementing `/good` and `/bad`. Specifically:
- Change `self.chat_history` from `str` to `list[tuple[str, str]]` where each entry is `("user", text)` or `("assistant", text)`
- Update `_add_to_chat_history()` to append tuples
- Update any code that reads `chat_history` as a string (e.g., display rendering)
- The `/good` command then simply reads `chat_history[-2]` (user) and `chat_history[-1]` (assistant)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  MASTER WORKSPACE (Claude)                              │
│  - Monitors all panes via CMUX                          │
│  - Enforces plan / prevents regression                  │
│  - Spawns verification agents, collects verdicts        │
│  - Applies consensus matrix, writes curated store       │
│  - Tracks progress, handles rate limits                 │
└─────────────────────────────────────────────────────────┘
         │ controls via CMUX
┌─────────────────────────────────────────────────────────┐
│  WORKING WORKSPACE                                      │
│  ┌──────────────┐  ┌────────┐  ┌──────────────────────┐│
│  │ Gemini       │  │  TUI   │  │ Gemini Verifier(s)   ││
│  │ Evaluator    │  │ (pane) │  │ (spawned fresh per   ││
│  │ (persistent) │  │        │  │  question, 2 at a    ││
│  │              │  │        │  │  time + V3 tiebreak) ││
│  └──────────────┘  └────────┘  └──────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Agent Roles

| Agent | Runtime | Platform | Responsibility |
|-------|---------|----------|----------------|
| **Master** | Entire session | Claude | Orchestrate, consensus, write outputs, rate limit management |
| **Evaluator** | Entire session | Gemini | Drive TUI: send questions, capture responses, relay to Master |
| **Verifier** | Per-question (fresh spawn) | Gemini | Compare TUI response to source files, return structured verdict |

### Why Fresh Spawn Per Verification

Context contamination is the primary hallucination driver in evaluation tasks. When a verification agent sees previous Q&A pairs, it pattern-matches to prior answers instead of the source file. Fresh spawn guarantees:
- Zero cross-question contamination
- Minimal context (question + response + lookup table + source file only)
- Spawn overhead (~3-5s) is hidden inside the TUI's generation wait time via pipelining

---

## Section 1: The Lookup Table

**File:** `docs/training/fprime_concept_map.md`

A flat keyword → file path mapping that verification agents grep to find authoritative source files. Optimized for agent consumption (grep-able, not table-based).

**Format:**
```markdown
# F' Concept Lookup Table
# Usage: grep keywords from the question, read the listed files

## Components & Architecture
active component, thread, queue, ActiveComponentBase → Fw/Comp/ActiveComponentBase.hpp, Fw/Comp/docs/sdd.md
passive component, PassiveComponentBase → Fw/Comp/PassiveComponentBase.hpp, Fw/Comp/docs/sdd.md
queued component, doDispatch → Fw/Comp/QueuedComponentBase.hpp, Fw/Comp/docs/sdd.md
component types, active vs passive vs queued → docs/user-manual/overview/03-port-comp-top.md
topology, instances.fpp, port connections → docs/user-manual/framework/building-topology.md, Ref/Top/instances.fpp, Ref/Top/topology.fpp

## Ports
port definition, port kinds, sync, guarded, async → Fw/Port/docs/sdd.md, docs/user-manual/overview/03-port-comp-top.md
port patterns, get port, callback port → docs/user-manual/design-patterns/common-port-patterns.md
serialized port, cross-process → Fw/Com/docs/sdd.md

## Commands
command dispatching, opcode, CmdDispatcher → Svc/CmdDispatcher/docs/sdd.md, Fw/Cmd/Cmd.fpp
command response, CmdResponse → Fw/Cmd/docs/sdd.md
command registration, CmdReg → Fw/Cmd/docs/sdd.md
command sequencer, sequence files → Svc/CmdSequencer/docs/sdd.md

## Telemetry
telemetry channel, TlmChan → Svc/TlmChan/docs/sdd.md, Fw/Tlm/Tlm.fpp
TlmBuffer, TlmPacket, telemetry serialization → Fw/Tlm/docs/sdd.md
telemetry packetizer → Svc/TlmPacketizer/docs/sdd.md

## Events & Logging
event severity, FATAL, WARNING_HI, WARNING_LO, ACTIVITY_HI, ACTIVITY_LO, DIAGNOSTIC → Fw/Log/docs/sdd.md, Fw/Log/Log.fpp
text logging, LogText, EVR → Fw/Log/docs/sdd.md
event manager → Svc/EventManager/docs/sdd.md
console text logger → Svc/PassiveConsoleTextLogger/docs/sdd.md

## Parameters
parameter get, parameter set, PrmGet, PrmSet → Fw/Prm/docs/sdd.md, Fw/Prm/Prm.fpp
parameter database, PrmDb, persistence → Svc/PrmDb/docs/sdd.md

## Types & Serialization
basic types, U8, U16, U32, U64, I8, I16, I32, I64, F32, F64 → Fw/Types/docs/sdd.md, Fw/FPrimeBasicTypes.hpp
serializable, serialize, deserialize, endianness → Fw/Types/Serializable.hpp
type definitions, enums, structs, arrays → Fw/Types/Types.fpp
JSON dictionary format → docs/reference/fpp-json-dict.md

## Buffers
Fw::Buffer, buffer pointer, buffer size → Fw/Buffer/docs/sdd.md, Fw/Buffer/Buffer.fpp
BufferGet, BufferSend, buffer lifecycle → Fw/Buffer/docs/sdd.md
BufferManager, buffer pools, bin-based allocation → Svc/BufferManager/docs/sdd.md

## Data Products
data products, containers, records → Fw/Dp/docs/sdd.md, Fw/Dp/Dp.fpp
DpGet, DpRequest, DpResponse, DpSend → Fw/Dp/docs/sdd.md
DpManager, DpWriter, DpCatalog → Svc/DpManager/docs/sdd.md, Svc/DpWriter/docs/sdd.md, Svc/DpCatalog/docs/sdd.md
data products design → docs/user-manual/framework/data-products.md

## Object System
ObjBase, object names, FW_OBJECT_NAMES → Fw/Obj/docs/sdd.md, Fw/Obj/ObjBase.hpp
object registry, FW_OBJECT_REGISTRATION → Fw/Obj/docs/sdd.md

## Time
Fw::Time, time seconds, time microseconds, time base → Fw/Time/docs/sdd.md, Fw/Time/Time.fpp
TimeGet port → Fw/Time/docs/sdd.md

## Rate Groups & Scheduling
rate group driver, system tick, dividers → Svc/RateGroupDriver/docs/sdd.md, Svc/RateGroupDriver/RateGroupDriver.fpp
active rate group, async scheduling → Svc/ActiveRateGroup/docs/sdd.md
passive rate group, synchronous scheduling → Svc/PassiveRateGroup/docs/sdd.md
rate group design patterns → docs/user-manual/design-patterns/rate-group.md
scheduler port, Svc::Sched → Svc/Sched/docs/sdd.md

## Health & Monitoring
health monitor, ping, timeout, watchdog → Svc/Health/docs/sdd.md, Svc/Health/Health.fpp
health checking pattern → docs/user-manual/design-patterns/health-checking.md
system resources, CPU, memory monitoring → Svc/SystemResources/docs/sdd.md

## File Operations
file manager, file commands → Svc/FileManager/docs/sdd.md
file uplink, receive files from ground → Svc/FileUplink/docs/sdd.md
file downlink, send files to ground, chunking → Svc/FileDownlink/docs/sdd.md
file packet types → Fw/FilePacket/docs/sdd.md

## Communication & Framing
framing protocol, frame headers → Svc/FprimeFramer/docs/sdd.md, Svc/FramingProtocol/docs/sdd.md
deframing, parse incoming data → Svc/FprimeDeframer/docs/sdd.md
CCSDS framing, TM framer → Svc/Ccsds/TmFramer/docs/sdd.md
custom framing → docs/how-to/custom-framing.md
router, packet routing → Svc/FprimeRouter/docs/sdd.md

## OSAL (Operating System Abstraction)
Os::Task, task creation, task priority, threading → Os/Task.hpp
Os::Mutex, mutual exclusion, lock, unlock → Os/Mutex.hpp
Os::Queue, message passing, priority queue → Os/Queue.hpp, Os/Generic/docs/sdd.md
Os::File, file I/O → Os/File.hpp
Os::FileSystem, directory operations → Os/FileSystem.hpp
Os::Console, stdout → Os/Console.hpp
Os::RawTime, system time → Os/RawTime.hpp
platform implementations, Linux, Darwin, POSIX → Os/Linux/, Os/Darwin/, Os/Posix/

## Drivers
byte stream driver, data flow → Drv/Interfaces/ByteStreamDriver.fpp
GPIO driver, digital I/O, pin control → Drv/LinuxGpioDriver/docs/sdd.md, Drv/Interfaces/Gpio.fpp
I2C driver, I2C bus → Drv/LinuxI2cDriver/docs/sdd.md, Drv/Interfaces/I2c.fpp
SPI driver, SPI bus → Drv/LinuxSpiDriver/docs/sdd.md, Drv/Interfaces/Spi.fpp
UART driver, serial communication → Drv/LinuxUartDriver/docs/sdd.md
TCP client, TCP socket → Drv/TcpClient/docs/sdd.md
TCP server, accept connections → Drv/TcpServer/docs/sdd.md
UDP, datagram → Drv/Udp/docs/sdd.md
IP address, socket → Drv/Ip/IpAddress.hpp
develop device driver → docs/how-to/develop-device-driver.md

## FPP Language
FPP component definition → docs/user-manual/overview/03-port-comp-top.md
FPP type definitions → Fw/Types/Types.fpp
FPP topology → Ref/Top/instances.fpp, Ref/Top/topology.fpp
interface definitions → Fw/Interfaces/Event.fpp, Fw/Interfaces/Channel.fpp, Fw/Interfaces/Command.fpp
state machine, signal, initial, on enter → docs/user-manual/framework/state-machines.md, Fw/Sm/
define state machines → docs/how-to/define-state-machines.md

## Build System
CMake, CMakeLists.txt, register_fprime_module → docs/user-manual/build-system/01-cmake-intro.md
CMake API, add_fprime_subdirectory → docs/user-manual/build-system/cmake-api.md
toolchains, cross-compilation → docs/user-manual/build-system/cmake-toolchains.md, cmake/platform/
platform definitions → docs/user-manual/build-system/cmake-platforms.md
project dependencies, project.cmake → docs/user-manual/overview/proj-dep.md

## Configuration
FpConfig.h, FW_OBJECT_NAMES, FW_ASSERT_LEVEL, FW_SERIALIZATION_TYPE_ID → default/config/FpConfig.h, default/config/FpConfig.hpp
configuring fprime → docs/user-manual/framework/configuring-fprime.md

## GDS (Ground Data System)
GDS overview, telemetry display, command sending → docs/user-manual/overview/gds-introduction.md
GDS dictionary, JSON dictionary → docs/reference/fpp-json-dict.md
GDS plugins, custom plugins → docs/user-manual/how-to/develop-gds-plugins.md, docs/reference/gds-plugins/
communication adapter → docs/reference/communication-adapter-interface.md

## Design Patterns
manager/worker pattern → docs/user-manual/design-patterns/manager-worker.md
hub pattern, broadcast → docs/user-manual/design-patterns/hub-pattern.md
subtopologies, reusable component groups → docs/user-manual/design-patterns/subtopologies.md
common port patterns → docs/user-manual/design-patterns/common-port-patterns.md

## Framework Features
assertions, FW_ASSERT → docs/user-manual/framework/assert.md
autocoded functions, auto-generated base classes → docs/user-manual/framework/autocoded-functions.md
building topology → docs/user-manual/framework/building-topology.md
supported platforms → docs/user-manual/framework/supported-platforms.md
baremetal, multicore → docs/user-manual/framework/baremetal-multicore.md
dynamic memory, malloc alternatives → docs/user-manual/framework/dynamic-memory.md
ground interface → docs/user-manual/framework/ground-interface.md

## Architecture
F' architecture overview → docs/user-manual/overview/02-fprime-architecture.md
source tree tour → docs/user-manual/overview/source-tree.md
cmd, evt, chn, prm overview → docs/user-manual/overview/04-cmd-evt-chn-prm.md

## Standard Ports
Fw::Signal → Fw/Ports/Signal/Signal.fpp
Fw::Success, Fw::SuccessCondition → Fw/Ports/CompletionStatus/CompletionStatus.fpp

## Data Structures
containers, array, map, set, stack, FIFO → Fw/DataStructures/docs/
hash map, red-black tree → Fw/DataStructures/docs/RedBlackTreeMap.md
```

**How it is built:** Once, by Claude scanning the flight-ready F' repository. Maintained manually as F' evolves.

**How verification agents use it:**
1. Extract keywords/concepts from the question text
2. Grep the lookup table for matching entries
3. Read only the listed 1-3 source files — nothing else

---

## Section 2: Agent Scripts

### 2a. Evaluator Agent Script

**File:** `docs/training/scripts/evaluator_agent.md`

```
# Evaluator Agent Script

You are the Evaluator Agent. You drive the TUI and coordinate
with the Master Agent. Follow this process EXACTLY for each
question. Do not deviate.

## Setup
1. You have access to: the TUI pane (via CMUX), the question
   list, and the verification results log.
2. Load the question list from:
   FPrimeSampleProject/docs/fprime_training.md

## Per-Question Process
1. SEND the question text to the TUI input
2. WAIT 15 seconds
3. READ the TUI response from the pane using CMUX capture-pane.
   The raw capture will contain ANSI escape codes from the Textual
   UI — strip these before processing. Look for the response text
   between the last "Mission Control:" label and the input prompt.
4. If the response appears incomplete (ends mid-sentence, or the
   TUI's spinner/progress indicator is visible in the captured pane),
   WAIT 10 more seconds and READ again. Repeat up to 3 times.
5. CAPTURE the full response text
6. SIGNAL the Master Agent with:
   { question_id, question_text, tui_response, expected_answer }
7. WAIT for the Master Agent to return the consensus verdict
8. SEND '/clear' to the TUI
9. MOVE to the next question

## Rules
- Do NOT evaluate the response yourself. That is the verifiers'
  job.
- Do NOT modify the question text.
- Do NOT skip questions unless the Master Agent instructs you to.
- If the TUI errors or crashes, SIGNAL the Master Agent
  immediately.
```

### 2b. Verification Agent Script

**File:** `docs/training/scripts/verification_agent.md`

```
# Verification Agent Script

You are a Verification Agent. You compare a TUI response against
authoritative F' source files. Follow this process EXACTLY.

## You will receive
- question_text: the question that was asked
- tui_response: the TUI's actual response
- expected_answer: the original expected answer (treat as
  ADVISORY, not authoritative — it may contain errors)

## Process
1. READ the question and identify the core F' concepts
   (e.g., "active component", "command dispatching", "Os::Task")
2. GREP the lookup table at docs/training/fprime_concept_map.md
   for those concepts
3. READ the source file(s) listed in the matching lookup entry.
   Read the ACTUAL file content — do not rely on memory.
4. COMPARE the tui_response to the source file content:
   - Are the API names correct? (class names, method names,
     port names)
   - Are the behaviors accurately described?
   - Are the relationships between components correct?
   - Is the FPP syntax correct (if applicable)?
5. RETURN your verdict in this EXACT format:

   {
     "question_id": "Q42",
     "verdict": "CORRECT | PARTIAL | INCORRECT",
     "citation": "Per Fw/Comp/ActiveComponentBase.hpp line 87: ...",
     "discrepancies": ["listed each factual error, if any"],
     "concepts_verified": ["active component", "threading"]
   }

## Rules
- The SOURCE FILE is the authority. Not the expected_answer.
  Not your training data.
- If the source file contradicts the expected_answer, note this
  in discrepancies.
- CORRECT: response accurately reflects the source files
- PARTIAL: core concept is right but missing important details
  or has minor inaccuracies
- INCORRECT: response contains wrong API names, wrong behavior,
  wrong syntax, or describes the wrong F' concept entirely
- Do NOT suggest improvements. Only verify.
- Do NOT carry context from previous questions. Each question
  is independent.
```

### 2c. Master Agent Role (Claude)

```
Claude monitors the full operation via CMUX:

1. Spawns the Evaluator Agent (once, persistent for session)
2. For each question, receives the (Q, R, Expected) tuple
   from the Evaluator
3. Spawns 2 Verification Agents with 3-second gap between
   spawns, each with the same inputs
4. Collects both verdicts, applies the consensus matrix
5. If DISPUTED (CORRECT vs INCORRECT): spawns V3 tiebreaker
   after 5-second cooldown
6. Writes results to the appropriate output file
7. Tracks progress via checkpoint file
8. Handles rate limits via backoff protocol
9. Can pause/abort if failure rate exceeds threshold
```

### 2d. Rate Limit Protocol

```
## Master Agent Responsibilities
- Track token/request usage across all agents
- Maintain a REQUEST_LOG with timestamps for each agent call
- Enforce minimum intervals between spawns:
  - Gemini agents: configurable, default 5s between spawns
  - Claude verification calls: respect API rate limits
- If any agent returns a rate limit error (429/ResourceExhausted):
  1. LOG the error with timestamp
  2. PAUSE all agent spawning for BACKOFF_INTERVAL
     (default: 60s, doubles each consecutive 429, max 10min)
  3. RESUME with the same question (do not skip)
  4. Reset backoff after 3 consecutive successes

## Evaluator Agent Rate Awareness
- After sending each question to the TUI, the 15-second wait
  already provides natural throttling for the local LLM
- If the TUI's Ollama backend returns a rate/resource error:
  1. WAIT 30 seconds
  2. RETRY the same question (up to 3 retries)
  3. If still failing, SIGNAL Master with error

## Verification Agent Spawning Cadence
- Master spawns V1 and V2 sequentially with a 3-second gap
  (not simultaneously) to avoid burst rate limits
- V3 tiebreaker (if needed) spawns after a 5-second cooldown
- If overnight run has N questions, Master estimates total
  runtime as: N x (TUI_wait + verify_time + cooldown)
  and logs this at the start

## Session Budget Guard
- At run start, Master calculates estimated token budget:
  - Per question: ~2K tokens (V1) + ~2K tokens (V2) +
    ~500 tokens (Master overhead)
  - Total: N x ~4.5K tokens + buffer
- If projected usage exceeds available budget, Master:
  1. Warns the user with the estimate
  2. Suggests running a subset (e.g., first 50 questions)
  3. Waits for approval before starting

## Progress Checkpointing
- Master writes progress to docs/training/eval_checkpoint.json
  after every 10 questions:
  { "last_completed": "Q42", "pass": 28, "fail": 10,
    "partial": 4, "timestamp": "..." }
- If the run is interrupted (crash, rate limit exhaustion,
  manual stop), it can resume from the checkpoint
- On resume, Master reads the checkpoint and skips
  already-completed questions
```

---

## Section 3: Consensus System

### Consensus Matrix (V1 x V2)

| V1 | V2 | Outcome | Action |
|----|----|---------|--------|
| CORRECT | CORRECT | **PASS** | → curated store |
| CORRECT | PARTIAL | **SOFT PASS** | → curated store, flagged |
| PARTIAL | CORRECT | **SOFT PASS** | → curated store, flagged |
| PARTIAL | PARTIAL | **PARTIAL** | → human review queue (*) |
| PARTIAL | INCORRECT | **SOFT FAIL** | → discard + diagnosis log |
| INCORRECT | PARTIAL | **SOFT FAIL** | → discard + diagnosis log |
| INCORRECT | INCORRECT | **FAIL** | → discard + diagnosis log |
| CORRECT | INCORRECT | **DISPUTED** | → spawn V3 tiebreaker |
| INCORRECT | CORRECT | **DISPUTED** | → spawn V3 tiebreaker |

### V3 Tiebreaker (DISPUTED cases only)

| V3 | Final | Action |
|----|-------|--------|
| CORRECT | 2:1 CORRECT → **PASS** | → curated store, flagged as disputed |
| INCORRECT | 2:1 INCORRECT → **FAIL** | → discard + diagnosis log |
| PARTIAL | 3-way split → **PARTIAL** | → human review queue |

(*) **Why PARTIAL+PARTIAL goes to review, not curated store:** Two PARTIAL verdicts mean both verifiers agree the response has merit but also has gaps. Unlike CORRECT+PARTIAL (where one verifier found it fully correct), two PARTIALs indicate consistent incompleteness — the response needs human judgment on whether the gaps matter. This is intentionally more conservative than SOFT PASS.

### Inter-Agent Communication

Agents communicate via **shared files**, not sockets or pipes:

1. **Evaluator → Master:** Evaluator writes to `docs/training/eval_exchange.json`:
   ```json
   {"status": "ready", "question_id": "Q42", "question_text": "...",
    "tui_response": "...", "expected_answer": "..."}
   ```
   Master polls this file (1-second intervals) for `"status": "ready"`.

2. **Master → Verifier:** Master writes verifier input to `docs/training/verify_input.json` and spawns the verifier agent with instructions to read it.

3. **Verifier → Master:** Verifier writes verdict to `docs/training/verify_output_v1.json` (or `_v2.json`, `_v3.json`). Master polls for file existence after spawning.

4. **Master → Evaluator:** Master writes `{"status": "done", "verdict": "PASS"}` to `docs/training/eval_exchange.json`. Evaluator polls for `"status": "done"` before proceeding to next question.

All exchange files are ephemeral — overwritten each question cycle.

### Verifier Response Validation

When the Master reads a verifier's output, it validates the JSON:
1. Parse JSON — if malformed, log error and re-spawn the verifier (up to 2 retries)
2. Check required fields: `question_id`, `verdict`, `citation`, `discrepancies`, `concepts_verified`
3. Validate `verdict` is one of: `CORRECT`, `PARTIAL`, `INCORRECT` — if not, treat as PARTIAL and log a warning
4. If a verifier fails validation after 2 retries, treat its verdict as `PARTIAL` and note "verifier_error" in the output

### Lookup Table Miss Handling

If a verification agent greps the lookup table and finds no matching entry for the question's concepts:
1. Return verdict with `"concepts_verified": []` and `"citation": "NO_LOOKUP_MATCH"`
2. Master treats a NO_LOOKUP_MATCH verdict as PARTIAL regardless of the stated verdict
3. Master logs the unmapped concept to `docs/training/unmapped_concepts.log` for lookup table expansion

---

## Section 4: Output Formats & Curated Store

### 4a. Curated Q&A File

**File:** `TUI/rag/curated_qa.md`

Lives inside `TUI/rag/` so it gets indexed into the RAG vector DB when `python -m rag.indexer` runs. The retriever's source-category boosting (from v0.03 RAG accuracy design) should map this file to a new `curated_knowledge` category with a 1.15 boost — high enough to be useful but not so high that it overrides authoritative source files.

**Circular feedback risk:** Since curated entries are TUI responses verified against source files, there is a risk of amplifying errors that slipped through verification. Mitigation: curated entries include their verification metadata (source files, verdicts), so a future audit pass can re-verify entries whose source files have changed.

```markdown
# Curated F' Knowledge Base
# Auto-generated by evaluation pipeline. Human-verified entries
# marked with [H]. Agent-verified entries marked with [A].

---

## Q1 — Active/Passive/Queued Components
**Verified:** 2026-03-15 [A] (V1: CORRECT, V2: CORRECT)
**Source:** Fw/Comp/ActiveComponentBase.hpp, Fw/Comp/docs/sdd.md

Active components have their own thread and message queue. They
process async port invocations and commands on their own thread
via a dispatch loop. Passive components execute on the caller's
thread — they have no queue and no thread. Queued components have
a message queue but no thread; an external caller must invoke
doDispatch() to process queued messages.

---
```

The **TUI response** is stored (not the original expected answer) — this is what the TUI actually generated and was verified correct against source files.

### 4b. Fine-Tuning Dataset

**File:** `docs/training/fine_tuning.jsonl`

```json
{"question": "What are the differences between Active, Passive, and Queued components?", "answer": "Active components have their own thread...", "source_files": ["Fw/Comp/ActiveComponentBase.hpp"], "rag_sources": ["Fw/Comp/docs/sdd.md"], "verified_by": "agent", "date": "2026-03-15"}
```

Both agent-verified and human-verified (`/good`) entries use the same JSONL schema. For human entries, `source_files` is empty and `rag_sources` contains whatever RAG sources were retrieved for that query.

**Note on `expected_answer`:** The original Gemini-generated expected answers are passed to verification agents as advisory context only. They are NOT stored in the curated output. Over successive pipeline runs, as the curated store grows, the `expected_answer` field becomes less important — the source files and the verification agents' own comparison are what matter.

### 4c. Human Review Queue

**File:** `docs/training/review_queue.md`

PARTIAL verdicts land here for manual review.

```markdown
## Q3 — Command dispatching and response protocol
**Verdict:** PARTIAL (V1: CORRECT, V2: PARTIAL)
**V2 discrepancy:** "Missing cmdResponse_out() return call and
  Fw::CmdResponse enum values"
**TUI Response:** [full response text]
**Source:** Svc/CmdDispatcher/docs/sdd.md
**Action needed:** Review and either /good or /bad
```

### 4d. Diagnosis Log

**File:** `docs/training/diagnosis_log.md`

FAIL and SOFT FAIL entries. The Master Agent appends each failure as a flat entry with its verifier discrepancies. Pattern grouping (e.g., "Wrong framework", "Invented FPP syntax") is done by a human during review — the Master does not attempt to classify failure patterns automatically.

```markdown
## Failures

### Q4 — GTest event verification
**Verdict:** FAIL (V1: INCORRECT, V2: INCORRECT)
**Discrepancies:** ["Described Python fprime_test_api instead of C++ GTest macros"]
**Source:** Fw/Log/docs/sdd.md

### Q2 — State Machine in FPP
**Verdict:** FAIL (V1: INCORRECT, V2: INCORRECT)
**Discrepancies:** ["Used capitalized StateMachine — FPP uses lowercase state machine"]
**Source:** docs/user-manual/framework/state-machines.md

---

## User-flagged bad responses
- [responses flagged via /bad command, with optional reason]
```

---

## Section 5: /good and /bad TUI Commands

### Command Behavior

```
/good
  - Captures the LAST question/response exchange from chat history
  - Appends to TUI/rag/curated_qa.md with [H] tag (human-verified)
  - Appends to docs/training/fine_tuning.jsonl
  - Displays confirmation in chat

/bad
  - Captures the LAST question/response exchange from chat history
  - Appends to docs/training/diagnosis_log.md under
    "User-flagged bad responses"
  - Does NOT add to curated store
  - Displays confirmation in chat
  - Optional reason: /bad wrong FPP syntax
```

### Implementation Location

Both commands register in `TUI/command_definitions.py` alongside existing slash commands. Available in MISSION_CONTROL mode only — RAG is not active in ACADEMY mode, so there are no RAG-sourced responses to validate.

Handler logic lives in `app.py` — the commands need access to `self.chat_history` to capture the last exchange.

### Agent Compatibility

The Evaluator Agent can use `/good` and `/bad` the same way a human does — typing into the TUI input pane. However, in the overnight pipeline, the Master Agent handles curation directly based on consensus verdicts. The `/good` and `/bad` commands are primarily for:

1. Human users during normal TUI usage
2. Manual review sessions — reviewing `review_queue.md` items
3. Future: agents doing targeted re-evaluation of specific questions

### Data Format for /good Captures

```python
{
    "question": last_user_message,
    "answer": last_assistant_message,
    "verified_by": "human",
    "date": "2026-03-15",
    "source_files": [],             # empty for human verification
    "rag_sources": last_rag_sources  # which RAG docs were retrieved
}
```

The `source_files` field is empty for human `/good` — the human asserts correctness based on their own expertise. Agent-verified entries from the pipeline populate this field.

---

## File Summary

| File | Purpose | Location |
|------|---------|----------|
| `fprime_concept_map.md` | Concept → source file lookup table | `docs/training/` |
| `evaluator_agent.md` | Evaluator agent script | `docs/training/scripts/` |
| `verification_agent.md` | Verification agent script | `docs/training/scripts/` |
| `curated_qa.md` | Golden validated Q&A pairs (RAG-indexed) | `TUI/rag/` |
| `fine_tuning.jsonl` | Accumulated fine-tuning dataset | `docs/training/` |
| `review_queue.md` | PARTIAL verdicts for human review | `docs/training/` |
| `diagnosis_log.md` | FAIL patterns for RAG improvement | `docs/training/` |
| `eval_checkpoint.json` | Progress checkpoint for resume | `docs/training/` |
| `eval_exchange.json` | Evaluator ↔ Master communication (ephemeral) | `docs/training/` |
| `verify_input.json` | Master → Verifier input (ephemeral) | `docs/training/` |
| `verify_output_v[N].json` | Verifier → Master output (ephemeral) | `docs/training/` |
| `unmapped_concepts.log` | Concepts missing from lookup table | `docs/training/` |

### Growth & Maintenance

- `curated_qa.md` will grow over time. When it exceeds ~200 entries, split into topic-based files (e.g., `curated_qa_commands.md`, `curated_qa_components.md`) to keep RAG chunk quality high.
- Re-indexing after curation is manual: run `PYTHONPATH=./TUI python -m rag.indexer` after a pipeline session.
- Entries verified against an older F' version remain valid unless the underlying source file changes. A future audit pass can re-verify by comparing `source_files` timestamps.
