# Diagnosis Log
# FAIL and SOFT FAIL entries from evaluation pipeline runs.
# Pattern grouping is done manually during review.

## Failures

---

## User-flagged bad responses

## Q2 [FAIL]

**Q:** How is a State Machine defined in FPP and integrated into a component?

**TUI Response:** (NO_RESPONSE)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: TUI returned no usable response

**V2:** INCORRECT — NO_RESPONSE

---

## Q3 [FAIL]

**Q:** Describe the protocol for command dispatching and response in F´.

**TUI Response:** (NO_RESPONSE)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: TUI returned no usable response

**V2:** INCORRECT — NO_RESPONSE

---

## Q4 [FAIL]

**Q:** How do you verify that a specific event was emitted with correct arguments in a GTest unit test?

**TUI Response:** (NO_RESPONSE)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: TUI returned no usable response

**V2:** INCORRECT — NO_RESPONSE

---

## Q5 [FAIL]

**Q:** What is the purpose of `Fw::Buffer` and how is it managed via `Svc::BufferManager`?

**TUI Response:** (NO_RESPONSE)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: TUI returned no usable response

**V2:** INCORRECT — NO_RESPONSE

---

## 1 [FAIL]

**Q:** What are the fundamental differences between Active, Passive, and Queued components in F´?

**TUI Response:** In F', components are categorized into **Active**, **Passive**, and **Queued** based on how they interact with events and messages. Here's a breakdown of their fundamental differences:

---

### **1. Active Components**
- **Behavior**: 
  - Can **initiate actions** (e.g., send events, update state).
  - Have a **main function** that runs when the component is activated.
  - Actively process data or control hardware.
- **Use Case**: 
  - Controllers, data processors, or systems that need to **drive behavior** (e.g., a flight computer that calculates trajectory).
- **Analogy**: 
  - Like a robot...

**V1:** INCORRECT — Per TUI/rag/raw/fprime/Fw/Comp/ActiveComponentBase.hpp line 22 and TUI/rag/raw/fprime/Fw/Comp/QueuedComponentBase.hpp line 39: ActiveComponentBase inherits from QueuedComponentBase, which contains 'Os::Queue m_queue'.
  Discrepancies: TUI summary table explicitly states Active components have 'No queue', which is a fundamental error; Active components require a queue for asynchronous port dispatch., TUI response misses the defining characteristic of Queued components: they have a queue but NO internal thread and require manual dispatch via a synchronous port call (e.g., RateGroup)., TUI's claim that Active components 'initiate actions' while others do not is misleading; Passive components can also initiate port calls when invoked by an external source (like a RateGroup)., TUI uses the term 'Main Function' for Active components instead of the technically correct 'internal execution thread'.

**V2:** INCORRECT — Per FPrimeSampleProject/fprime/docs/user-manual/overview/03-port-comp-top.md section 'A Quick Look at Component Types': Active Components are explicitly defined as having both a Queue (Yes) and a Thread (Yes). Also, Fw/Comp/ActiveComponentBase.hpp inherits from QueuedComponentBase, which contains the Os::Queue m_queue member.
  Discrepancies: The TUI response states in its 'Key Differences Summary' table that Active components have 'No queue', which contradicts F' architecture where Active components must have a queue to process asynchronous port calls., The TUI fails to identify that the fundamental difference between Active and Queued components is the presence of an internal thread; it correctly identifies the queue for Queued components but misses the lack of a thread., The TUI implies Passive components cannot initiate actions, which is misleading as any component can invoke output ports; the real distinction is the execution context (Active has its own thread).

---

## 3 [FAIL]

**Q:** Describe the protocol for command dispatching and response in F´.

**TUI Response:** In F' (F Prime), **command dispatching and response** follow a structured, reliable protocol designed for flight software. Here's a conceptual breakdown:

---

### **1. Command Reception**
- **Source**: Commands are received via a **port** (e.g., `CommandPort`) from external systems (e.g., ground stations or other flight software components).
- **Protocol**: The command is transmitted using the **C/T (Command/Telemetry) protocol**, which ensures reliable, ordered delivery over communication channels (e.g., serial, CAN, or network).

---

### **2. Command Validation**
- **Command Interpreter**:...

**V1:** INCORRECT — Per Svc/CmdDispatcher/docs/sdd.md and Fw/Cmd/Cmd.fpp: Commands are received as Fw::Com buffers, dispatched via Fw::Cmd ports, and responded to via Fw::CmdResponse ports (e.g., cmdResponse_out).
  Discrepancies: The TUI response incorrectly states that command responses are sent via the 'Telemetry Port'. In F', command responses and telemetry are distinct systems., The TUI uses non-standard terms like 'CommandPort', 'C/T protocol', and 'Command Interpreter' which do not reflect the authoritative Svc::CmdDispatcher architecture., The TUI lists status codes like 'SUCCESS' and 'TIMEOUT' which do not match the actual Fw::CmdResponse enum (OK, VALIDATION_ERROR, EXECUTION_ERROR, etc.).

**V2:** INCORRECT — Per Svc/CmdDispatcher/docs/sdd.md and Fw/Cmd/Cmd.fpp, F' uses Svc::CmdDispatcher to route commands, which are received as Fw::Com packets and dispatched to components via the CmdDisp port. Responses are sent via the CmdResponse port, not a 'Telemetry Port' as claimed by the TUI.
  Discrepancies: Hallucinated 'Command Interpreter' component and 'Command package'; F' uses Svc::CmdDispatcher., Incorrectly stated command responses are sent via 'Telemetry Port'; they are sent via the 'CmdResponse' port., Used generic 'C/T protocol' terminology instead of F' specific 'Fw::Com' packets and framing protocols.

---

## 4 [FAIL]

**Q:** How do you verify that a specific event was emitted with correct arguments in a GTest unit test?

**TUI Response:** In F' (F Prime), verifying that an event was emitted with correct arguments in a GTest unit test involves **mocking the event handler** and using GTest's assertion macros to validate the call. Here's how it works:

---

### **1. Understand the Event Handler**
- Events in F' are handled via **event handlers** (e.g., `event_handler_t` in C++).
- When an event is triggered (e.g., via `emit_event`), the handler is invoked with the event's arguments.

---

### **2. Mock the Event Handler**
- Replace the actual handler with a **mock object** in your test.
- The mock will record the arguments passed ...

**V1:** INCORRECT — Standard F' unit testing uses auto-generated Tester classes that capture events via the from_Log port. Verification is done using ASSERT_EVENTS_* macros as shown in Svc/PrmDb/test/ut/PrmDbTester.cpp. The TUI's manual mocking of an 'event handler' is not how F' components handle event verification.
  Discrepancies: TUI response suggests manual mocking of a non-existent event handler instead of using the Tester pattern., TUI misses the auto-generated ASSERT_EVENTS_* macros., TUI uses generic GTest mocking which bypasses the F' port-based event system.

**V2:** INCORRECT — Per F' unit testing patterns and Svc/Health/test/ut/HealthTester.cpp: Event verification in F' uses the generated Tester harness (inheriting from GTestBase). The harness connects to the component's 'Log' port (this->component.set_Log_OutputPort(0, this->get_from_Log(0))) and captures events in a history. Verification is done using generated macros like ASSERT_EVENTS_SIZE(n) and ASSERT_EVENTS_EventName(index, args...).
  Discrepancies: The TUI response suggests manual mocking of event handlers using GTest's MOCK_METHOD, which is not the standard F' practice., It fails to mention the generated Tester class and GTestBase which provide the infrastructure for testing., It misses the specific generated macros (ASSERT_EVENTS_SIZE, ASSERT_EVENTS_EventName) mentioned in the expected answer and verified in the codebase.

---

## ID [FAIL]

**Q:** Question (Prompt)

**TUI Response:** Please ask a specific question about F' (F Prime), its architecture, flight software concepts, or how it's used in space missions. For example:
- "What is the purpose of the F' architecture?"
- "How do components communicate in F'?"
- "Why is F' important for flight software?"

I'm here to explain concepts, analogies, and guide you through F' principles! 🚀

**V1:** INCORRECT — NO_LOOKUP_MATCH

**V2:** CORRECT — NO_LOOKUP_MATCH

---

## 5 [FAIL]

**Q:** What is the purpose of `Fw::Buffer` and how is it managed via `Svc::BufferManager`?

**TUI Response:** The question seems incomplete. Could you clarify which specific component, system, or concept you're asking about? For example, are you referring to the **Command and Telemetry (C&T)** system, **Event Manager**, **Scheduler**, or another F' architecture element? 

For instance:
- If you're asking about **C&T**, its purpose is to manage communication between the spacecraft and ground systems (like receiving commands and sending telemetry), and it's managed via F' components like `CommandInterface` and `TelemetryInterface`.
- If you're asking about **Events**, they are used to log critical syste...

**V1:** INCORRECT — Per Fw/Buffer/docs/sdd.md and Svc/BufferManager/docs/sdd.md
  Discrepancies: The TUI response completely failed to answer the question and instead asked for clarification on unrelated F' concepts.

**V2:** INCORRECT — Per Fw/Buffer/docs/sdd.md, Fw/Buffer/Buffer.fpp, and Svc/BufferManager/docs/sdd.md
  Discrepancies: The TUI response did not address the specific F' concepts `Fw::Buffer` and `Svc::BufferManager` at all, instead suggesting unrelated topics.

---

## 7 [FAIL]

**Q:** What is the difference between an FPP `struct` and an FPP `serializable`?

**TUI Response:** In F Prime (FPP), a **`struct`** is a fundamental data container used to group related fields (like a "Lego block" for data). It defines the shape of data but does not inherently support serialization or communication. 

A **`serializable`** is a **trait** (a marker interface) that you apply to a struct to enable it to be **serialized** into a byte stream (e.g., for telemetry, command packets, or storage). Think of it as giving the struct a "special sticker" that lets it communicate with other systems (like a "USB connector" for data transfer).

### Key Differences:
| Feature              | `s...

**V1:** INCORRECT — Per FPrimeSampleProject/build-fprime-automatic-native/F-Prime/Fw/Time/TimeValueSerializableAc.hpp, an FPP struct (Fw::TimeValue) generates a C++ class that inherits from Fw::Serializable and includes serializeTo/deserializeFrom methods.
  Discrepancies: TUI states FPP `struct` does not inherently support serialization, but it does by generating a `Fw::Serializable` C++ class., TUI states `serializable` is a trait applied to a struct, but in modern FPP, the `struct` keyword itself implies serializability, generating a `Fw::Serializable` C++ class., TUI incorrectly states FPP structs generate 'No special code' for serialization/deserialization; they generate C++ classes with serializeTo/deserializeFrom methods., TUI incorrectly implies explicit trait application is required in FPP for serializability, which is not the case for modern FPP structs.

**V2:** INCORRECT — Per docs/training/fprime_training.md entry 7 and Fw/Types/Serializable.hpp. In modern FPP, 'struct' itself defines a serializable data structure, and the generated C++ class inherits from Fw::Serializable.
  Discrepancies: The TUI states that FPP `struct` does not inherently support serialization and that `serializable` is a trait applied to a struct. This is incorrect for modern FPP, where `struct` implicitly defines a serializable data structure., The TUI's claim that FPP `struct` generates 'No special code' is misleading; it generates a C++ class with data members, and implicitly, serialization methods., The TUI's FPP example `serializable struct MyData` is likely outdated syntax, as `struct` alone implies serializability in modern FPP, making `serializable` redundant as a prefix.

---

## 10 [FAIL]

**Q:** Describe the use of "Base IDs" in an F´ Topology.

**TUI Response:** In an F' (F Prime) topology, **Base IDs** are fundamental to uniquely identifying **ports** within a component. Here's a conceptual breakdown:

### 1. **What is a Base ID?**
   - A **Base ID** is a numeric value assigned to a port in a component's `.fpp` file (e.g., `Component/component.fpp`).
   - It serves as the **"base"** for generating unique **message IDs** (e.g., `MSG_ID`) when the component sends or receives data.

### 2. **Why are Base IDs Important?**
   - **Uniqueness**: Each port must have a unique Base ID to avoid message ID collisions across the system.
   - **Scalability**: Base...

**V1:** INCORRECT — Per Svc/Subtopologies/DataProducts/DataProducts.fpp (L7, L20, L25, L39) and Svc/Subtopologies/DataProducts/DataProductsConfig/DataProductsConfig.fpp (L3), 'base id' is assigned to component instances, not ports. It ensures global uniqueness for all internal IDs (commands, telemetry, events, parameters) within a component.
  Discrepancies: TUI response incorrectly states that 'Base ID' is assigned to a port in a component's .fpp file; actual usage shows it's assigned to component instances., TUI response incorrectly states that 'Each port must have a unique Base ID'; actual usage shows each component instance has a base ID, which is then used for relative IDs within the component., TUI response provides an incorrect FPP syntax example where 'base_id' is declared within a port definition; actual FPP syntax uses 'base id' during component instance declaration.

**V2:** INCORRECT — Based on FPrimeSampleProject/Deployments/*/Top/instances.fpp, fprime/Fw/Dp/docs/sdd.md, and docs/training/fprime_training.md entries for 'base id'.
  Discrepancies: The tui_response incorrectly states that Base IDs are assigned to 'ports' within a component's .fpp file. F' documentation and examples show Base IDs are assigned to 'component instances' in a topology., The tui_response provides an incorrect FPP syntax example: `port DataIn { base_id = 100; }`. This syntax for port definitions is not found in F' sources; Base IDs are assigned to component instances (e.g., `instance myInstance: MyComponent base id 0x100;`)., The tui_response inaccurately describes Base IDs as 'uniquely identifying ports' and contributing to 'message IDs' of ports directly. In F', the component instance's Base ID acts as an offset to create globally unique IDs for the component's internal commands, telemetry channels, events, and parameters (CEPs), not for ports themselves in this direct manner. Ports are the communication interfaces, while Base IDs resolve unique IDs for the data items (CEPs) transmitted through them or processed by the component.

---

## 14 [FAIL]

**Q:** How do you define a port that returns a value in FPP?

**TUI Response:** In F Prime (FPP), a **telemetry port** is used to return values from a component to other parts of the system. Telemetry ports are defined in the component's `.fpp` file and are implemented in the corresponding `.cpp` file. Here's how to define one:

### 1. **Declare the Telemetry Port in `.fpp`**
In the component's `.fpp` file (e.g., `MyComponent.fpp`), add:
```cpp
TelemetryPort<uint32_t> myTelemetryPort; // Replace uint32_t with your data type
```
This declares a telemetry port named `myTelemetryPort` that sends `uint32_t` values.

### 2. **Implement the Telemetry in `.cpp`**
In the componen...

**V1:** INCORRECT — Per docs/training/fprime_training.md line 20: 'Use the arrow syntax in the port definition: `port GetData(arg1: U32) -> F32`. Ports with return values must be instantiated as `sync` or `guarded` on the input side because they execute in the caller's context to return the value immediately. They cannot be `async` because the message queue mechanism does not support immediate functional return.'
  Discrepancies: The tui_response incorrectly states that 'a telemetry port is used to return values'. Telemetry ports are for sending data, not for returning values in a functional call. Ports that return values are synchronous and use specific FPP syntax., The tui_response provides examples using `TelemetryPort` and `setValue`, which are mechanisms for asynchronous data broadcasting (telemetry), not for synchronous port return values., The tui_response's explanation of 'unidirectional (send-only)' for telemetry ports, while accurate for telemetry, is irrelevant to the question of a port that 'returns a value', which implies a bidirectional, synchronous interaction.

**V2:** INCORRECT — Per FPrimeSampleProject/fprime/Svc/Ccsds/Ports/Ports.fpp (L5) and FPrimeSampleProject/fprime/FppTestProject/FppTest/component/active/port_types.fpp (L47, and others).
  Discrepancies: The TUI response incorrectly states that a 'telemetry port' is used to return values in FPP. FPP uses a dedicated syntax 'port Name (...) -> Type' for ports with return values, as shown in the cited FPP files., The TUI response mischaracterizes telemetry ports as the mechanism for returning values. Telemetry ports are typically unidirectional (send-only) for emitting data, not for functional return values., The TUI response provides C++ syntax for instantiating a telemetry port ('TelemetryPort<uint32_t> myTelemetryPort;') rather than the FPP definition syntax for a port with a return value., The TUI response completely omits the critical FPP concept that ports with return values must be 'sync' or 'guarded' (not 'async') because they execute in the caller's context for an immediate return, a key detail mentioned in the expected answer and implicit in the nature of return values.

---

## 20 [FAIL]

**Q:** What is the role of `Svc::TlmChan` in the telemetry system?

**TUI Response:** In F' (F Prime), `Svc::TlmChan` is a **telemetry channel service** that plays a critical role in the spacecraft's telemetry system. Its primary purpose is to **manage the transmission of telemetry data** from the spacecraft to the ground via a defined communication channel (e.g., a radio link).

### Key Responsibilities:
1. **Data Transmission**:  
   `Svc::TlmChan` handles the actual sending of telemetry packets over the communication link. It abstracts the low-level details of the transmission protocol (e.g., CCSDS) so higher-level components (like sensors or subsystems) don’t need to manage...

**V1:** INCORRECT — Based on FPrimeSampleProject/fprime/Svc/TlmChan/docs/sdd.md and FPrimeSampleProject/fprime/Svc/TlmChan/TlmChan.fpp
  Discrepancies: TUI response incorrectly states that Svc::TlmChan 'handles the actual sending of telemetry packets over the communication link'. The documentation indicates it outputs packets via a PktSend port, which another component would then transmit., TUI response mentions Svc::TlmChan 'may include logic for managing transmission errors, retransmissions, or packet prioritization', which is not supported by the provided sdd.md., TUI response mentions 'Svc::TlmChan::SendTelemetry()' as an interface, while the FPP and SDD describe the TlmRecv port as the primary input for telemetry updates.

**V2:** INCORRECT — Per FPrimeSampleProject/fprime/Svc/TlmChan/docs/sdd.md, sections 1 and 3.2, and the Ports table.
  Discrepancies: The TUI response incorrectly states that `Svc::TlmChan` directly 'manages the transmission of telemetry data' and 'handles the actual sending of telemetry packets over the communication link,' and 'abstracts the low-level details of the transmission protocol (e.g., CCSDS).' The documentation indicates it stores values and pushes packets to *another* component for transport out of the system, not that it performs the final transmission or protocol handling itself., The TUI suggests `Svc::TlmChan` may include logic for 'error handling and retransmissions,' which is not mentioned in its System Design Document., The TUI mentions `Svc::TlmGen`, which is not referenced within the `Svc::TlmChan` documentation in relation to its direct function.

---

## 27 [FAIL]

**Q:** How do you create a custom GDS Dashboard?

**TUI Response:** Creating a custom GDS (Ground Data System) Dashboard involves integrating real-time telemetry, command, and status data from your spacecraft with a user-friendly interface. Here's a conceptual breakdown of the process, using analogies to flight software architecture:

---

### **1. Understand the GDS Role**
The GDS acts as the "control center" for your spacecraft, similar to a cockpit dashboard in an airplane. It displays telemetry (e.g., battery levels, sensor data) and allows operators to send commands (e.g., adjust thrusters).

**Analogy:**  
Think of the GDS as a dashboard that connects to...

**V1:** INCORRECT — Per training/fprime_training.md line 33
  Discrepancies: The tui_response describes a general conceptual process for building a dashboard, focusing on UI design, data integration, and visualization using generic tools (JavaScript, Python, WebSockets, MQTT)., It completely omits the F' specific method of defining custom GDS Dashboards using an XML specification, including structural tags (dashboard-box, dashboard-row), functional components (command-input, event-list, channel-table), and properties (filter-text, fields, items-shown), as described in training/fprime_training.md and the expected_answer.

**V2:** INCORRECT — NO_LOOKUP_MATCH
  Discrepancies: The tui_response provides a high-level conceptual overview of GDS dashboards, but it completely misses the F' GDS specific implementation details, such as the use of XML for dashboard definition and specific F' GDS components (e.g., command-input, event-list, channel-table)., The expected_answer correctly points to XML specification for custom dashboards and mentions specific components and structural tags which are characteristic of F' GDS dashboard definitions, although direct verification of all specific component tags like `command-input`, `event-list`, `channel-table`, and `dashboard-row` within the provided F' venv was not possible via grep.

---

## 35 [FAIL]

**Q:** How do you define a "Guarded" command in FPP?

**TUI Response:** In F Prime (FPP), a **"Guarded" command** is defined by adding one or more `guard` blocks to a command's declaration. These guards are conditions that must evaluate to `true` for the command to be valid and executable. Guards are part of the command's **validation logic** and are checked before the command is processed.

### Syntax Example:
```fpp
command MyGuardedCommand {
    param1: int
    guard MyGuard {
        condition: mode == ACTIVE
    }
    guard AnotherGuard {
        condition: counter < MAX_COUNT
    }
}
```

### Key Concepts:
1. **`guard` Block**:  
   Each `guard` block has a ...

**V1:** INCORRECT — Per fprime/Svc/Version/Version.fpp (for 'guarded command' FPP syntax) and FPrimeSampleProject/build-fprime-automatic-native/F-Prime/Svc/Version/VersionComponentAc.cpp (for lock()/unLock() around command handlers).
  Discrepancies: The TUI response uses an incorrect FPP syntax example for defining guarded commands (it depicts `guard` blocks with `condition:` within a command declaration, which is not standard FPP for guarded commands)., The TUI response misidentifies the primary purpose of a 'Guarded' command, stating it's for pre-condition validation, whereas the F' framework uses 'guarded command' to ensure thread-safe execution of the command handler via mutex protection.

**V2:** INCORRECT — FPrimeSampleProject/fprime/docs/user-manual/overview/03-port-comp-top.md, FPrimeSampleProject/fprime/docs/user-manual/framework/autocoded-functions.md
  Discrepancies: The TUI response incorrectly describes FPP syntax for 'Guarded' commands using `guard` blocks. The F' documentation (FPrimeSampleProject/fprime/docs/user-manual/overview/03-port-comp-top.md) indicates that 'guarded' applies to *ports* (specifically `guarded_input` ports), where a component-wide mutex is acquired before the port handler executes. There is no FPP syntax for `guard` blocks directly within a command declaration. The expected answer's reference to autocoder-generated mutex protection for command handlers aligns more closely with the framework's approach to thread safety, likely by using mechanisms similar to guarded ports for command processing.

---

## 59 [FAIL]

**Q:** What are "Internal Interfaces" in an F´ component?

**TUI Response:** Internal Interfaces in an F' component are like **private communication channels** that allow components to interact with other components within the same system. They are used when two or more components need to exchange data **without exposing that communication to external systems**. 

### Key Concepts:
1. **Internal vs. External Interfaces**:
   - **Internal Interfaces** are used for communication **within a system** (e.g., between a main component and its subcomponents).
   - **External Interfaces** are used for communication **outside the system** (e.g., with ground systems or other spac...

**V1:** INCORRECT — Per FPrimeSampleProject/fprime/docs/user-manual/framework/autocoded-functions.md, under 'Internal Interfaces' section. Also FPrimeSampleProject/docs/fprime_training.md (questions 21, 59, 645).
  Discrepancies: The tui_response incorrectly states that Internal Interfaces are 'private communication channels' allowing components to interact with *other components* within the same system. The F' documentation specifies that Internal Interfaces are a mechanism for a component to send an asynchronous message to *itself* (self-dispatch) to defer work to its own message loop., The tui_response incorrectly implies that Internal Interfaces are explicitly declared in the `topology.fpp` file to establish *inter-component* communication paths. The `topology.fpp` defines connections between ports of *different* components. Internal interfaces are part of a component's FPP definition and generate invoke/handler functions for *self-messaging*, not direct inter-component connection in the topology file.

**V2:** INCORRECT — Per docs/fprime_training.md (Q59 and Q21) and FPrimeSampleProject/fprime/docs/user-manual/framework/autocoded-functions.md, internal interfaces are a mechanism for a component to send a message to itself asynchronously, queuing work for deferred processing. Also FPrimeSampleProject/fprime/Svc/ActiveTextLogger/ActiveTextLogger.fpp L9: `@ Internal interface to send log text messages to component thread`.
  Discrepancies: The tui_response incorrectly states that Internal Interfaces are used for communication between 'other components within the same system' and for 'two or more components to exchange data'., The tui_response's analogy of 'internal connectors between blocks in the same structure' is misleading as it implies inter-component communication rather than self-communication., The tui_response implies that 'topology.fpp' explicitly declares internal interfaces to establish internal communication paths, which is not their primary purpose or how they are connected; internal ports (`internal port`) are for self-messaging.

---

## 66 [FAIL]

**Q:** What is the purpose of the "Orb" in the GDS GUI?

**TUI Response:** (TIMEOUT)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: Evaluator reported no TUI response

**V2:** INCORRECT — NO_RESPONSE

---

## 71 [FAIL]

**Q:** How do you define a port array in FPP?

**TUI Response:** In F Prime (FPP), a **port array** is defined using the `array` keyword to declare multiple ports of the same type. This is useful for components that need to handle multiple instances of a port (e.g., for dynamic or variable numbers of messages).

### Syntax Example:
```fpp
array of PortType myPortArray[10]
```

### Breakdown:
1. **`array of PortType`**: Specifies that this is a port array, where `PortType` is the data type of the port (e.g., `Message` or `Command`).
2. **`myPortArray[10]`**: Names the array and defines its size (e.g., 10 ports in this case).

### Directionality:
- Use `direc...

**V1:** INCORRECT — FPP Language Specification (general knowledge of FPP syntax)
  Discrepancies: The tui_response uses 'array of PortType myPortArray[10]' syntax, which is not valid FPP for defining port arrays., The tui_response incorrectly states that 'array' is a keyword for port arrays., The tui_response incorrectly applies 'direction input/output' after the array declaration with 'array of PortType'., The expected_answer correctly uses 'sync input port myPorts: [10] MyPortType' for FPP port array definition.

**V2:** INCORRECT — Based on FPP syntax observed in FPrimeSampleProject/fprime/Svc/CmdSplitter/CmdSplitter.fpp (L12, L15, L22, L25, L28), FPrimeSampleProject/fprime/Svc/ComQueue/ComQueue.fpp (L26, L29, L32), FPrimeSampleProject/fprime/Svc/BufferRepeater/BufferRepeater.fpp (L9), FPrimeSampleProject/fprime/Svc/GenericHub/GenericHub.fpp (L83, L91, L94, L173, L178, L181), FPrimeSampleProject/fprime/Svc/StaticMemory/StaticMemory.fpp (L7, L10), FPrimeSampleProject/fprime/Svc/ComSplitter/ComSplitter.fpp (L10), and FPrimeSampleProject/fprime/FppTestProject/FppTest/interfaces/typed_ports.fpp (L7, L9, L11, L13, L15, L17, L19, L21, L23, L25, L27, L29, L35, L37, L39, L41, L43, L45).
  Discrepancies: The tui_response provides the syntax `array of PortType myPortArray[10]`. This syntax (`array of <PortType>`) is not found in the actual FPP files for defining port arrays. The correct syntax uses square brackets `[<size>]` directly after the port name., The tui_response incorrectly places the array size `[10]` *after* the port name and *before* the port type. In FPP, the `[<size>]` directly follows the port name and precedes the `PortType` (e.g., `port myPorts: [10] MyPortType`)., The tui_response suggests `direction input` as a separate keyword and placement. In actual FPP syntax, the direction (`input` or `output`) is typically combined with the port `kind` (e.g., `sync input port`, `async input port`). The `direction` keyword is not directly used in the syntax for defining a port array., The correct FPP syntax for defining a port array is typically `<optional_kind> <optional_direction> port <name>: [<size>] <PortType>`.

---

## 73 [FAIL]

**Q:** How do you check code coverage for F´ unit tests?

**TUI Response:** To check code coverage for F' unit tests, you need to integrate standard C++ coverage tools like **gcov** and **lcov** into your build process. Here's how it works:

---

### **1. Enable Coverage in the Build Configuration**
F' uses CMake for builds. Modify your `CMakeLists.txt` or build configuration to include coverage flags:
```cmake
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fprofile-arcs -ftest-coverage")
```
This instruments the code to collect coverage data during testing.

---

### **2. Generate Code and Build**
Use the `run_fprime_command` tool to generate and build your F' code:


> *[...

**V1:** INCORRECT — Per docs/fprime-docs/fprime_commands.md line 24 and docs/training/fprime_training.md line 79, the correct command for checking code coverage for F' unit tests is `fprime-util check --coverage`.
  Discrepancies: The tui_response suggests manual modification of CMakeLists.txt for coverage flags, which is not the idiomatic F' approach., The tui_response fails to mention the primary command `fprime-util check --coverage` for performing code coverage analysis within F'.

**V2:** INCORRECT — Multiple sdd.md files within FPrimeSampleProject/fprime/Svc and TUI/rag/raw/fprime/Svc, as well as FPrimeSampleProject/docs/fprime_training.md, explicitly state to 'Run `fprime-util check --coverage` to see unit test coverage.'
  Discrepancies: The tui_response suggests manually modifying `CMakeLists.txt` with `-fprofile-arcs -ftest-coverage` and then building, rather than using the `fprime-util check --coverage` command which provides the established, idiomatic method for checking code coverage in F' unit tests.

---

## 77 [FAIL]

**Q:** How can you list all available commands for a deployment using the CLI?

**TUI Response:** > *[Running fprime-util info... (PENDING)]*To resolve the "venv not found" error, ensure your F' environment is properly initialized. Follow these steps manually:

1. **Verify Python Installation**: Confirm Python is installed via `python --version`.
2. **Check Venv Directory**: Navigate to the F' project root and verify the `venv` folder exists.
3. **Create Venv (if missing)**: Run `python -m venv venv` to generate the virtual environment.
4. **Install Dependencies**: Activate the venv (`source venv/bin/activate` on Unix/Mac or `venv\Scripts\activate` on Windows) and install packages with `pi...

**V1:** INCORRECT — NO_LOOKUP_MATCH
  Discrepancies: The tui_response discusses a 'venv not found' error and environment setup, which is completely irrelevant to the question 'How can you list all available commands for a deployment using the CLI?'. The expected_answer provides the correct CLI command `fprime-cli command-send -l`.

**V2:** INCORRECT — The TUI response addresses a 'venv not found' error and general environment setup, which is not related to the question 'How can you list all available commands for a deployment using the CLI?'
  Discrepancies: The TUI response completely misunderstands the user's question, providing troubleshooting steps for an unrelated error instead of instructions on how to list commands., The provided source files (`docs/training/fprime_concept_map.md`, `docs/fprime-docs/fprime_commands.md`) do not confirm the existence or usage of 'fprime-cli command-send -l' as suggested by the 'expected_answer', nor do they validate the troubleshooting steps for a 'venv not found' error in the context of listing commands.

---

## 90 [FAIL]

**Q:** What are GDS "Functional Components"?

**TUI Response:** In F Prime (F'), **GDS "Functional Components"** are modular, task-specific units that form the building blocks of flight software systems. They are part of the **Generic Data Services (GDS)** architecture, which is designed to standardize how data and services are managed across different subsystems in a spacecraft or mission.

### Key Concepts:
1. **Modular Design**:
   - Each Functional Component (e.g., a sensor manager, actuator controller, or data processor) is self-contained and handles a specific function.
   - Think of them like **Lego blocks**—each has a defined role and can be combin...

**V1:** INCORRECT — NO_LOOKUP_MATCH: The referenced file 'docs/user-manual/overview/gds-introduction.md' could not be found. Therefore, direct verification against the source was not possible.
  Discrepancies: The TUI response describes GDS 'Functional Components' as general F' flight software components (modular design, communication via ports, etc.), while the expected answer defines them as specific UI widgets within GDS dashboards (command-input, event-list, channel-table). The TUI response appears to misinterpret the 'GDS' context of the question, providing a definition more applicable to F' components in general rather than GDS UI components.

**V2:** INCORRECT — Per docs/training/fprime_training.md line 96: 'They are the core UI widgets used in custom dashboards, including `command-input` (sending commands), `command-history` (viewing sent commands), `event-list` (real-time logs), and `channel-table` (latest telemetry values).'
  Discrepancies: The tui_response describes F' flight software components (modular design, ports, scalability, reliability, maintainability, reusability) which are general F' software components, not the specific GDS UI widgets referred to as 'GDS Functional Components' in the training data and expected answer.

---

## 106 [FAIL]

**Q:** Describe the `fprime-gds -g none` option.

**TUI Response:** The `fprime-gds -g none` option is used in the F' (F Prime) framework to control the code generation process. Here's a breakdown:

### What is `fprime-gds`?
`fprime-gds` (F Prime Generate Data Structures) is a tool that processes **FPP** (F Prime Processing) files to generate implementation code (e.g., C++, Python) for flight software components. It translates the high-level definitions in FPP files into executable code.

---

### What does `-g none` do?
The `-g none` flag tells `fprime-gds` to **disable all code generation**. This means:
- **No C++ or Python code** is generated from the FPP f...

**V1:** INCORRECT — FPrimeSampleProject/fprime/docs/user-manual/overview/gds-introduction.md, line 146
  Discrepancies: The tui_response incorrectly identifies `fprime-gds` as a tool for generating code from FPP files (F Prime Generate Data Structures). The documentation clearly states `fprime-gds` is the F' Ground Data System., The tui_response incorrectly states that `-g none` disables all code generation. The documentation states that `-g none` runs the GDS without the HTML/browser UI loading.

**V2:** INCORRECT — docs/training/fprime_training.md line 112
  Discrepancies: The tui_response incorrectly identifies `fprime-gds` as a tool for generating code from FPP files (F Prime Generate Data Structures). The documentation clearly states `fprime-gds` is the F' Ground Data System., The tui_response incorrectly states that `-g none` disables all code generation. The documentation states that `-g none` launches the GDS backend but suppresses the automatic opening of the browser-based GUI.

---

## 109 [FAIL]

**Q:** How are Subtopologies registered in CMake?

**TUI Response:** Subtopologies in F Prime are registered in their own `CMakeLists.txt` file, which is placed in the directory corresponding to the subtopology's name. Here's how it works:

1. **Component Registration**:  
   Each subtopology is treated as a separate component. In its directory, you create a `CMakeLists.txt` file that uses the `add_component` command to register the component. For example:
   ```cmake
   add_component(MySubtopology
       SOURCES MySubtopology.cpp
   )
   ```
   The component name (`MySubtopology`) must match the name used in the topology definition (e.g., `MySubtopology` in `T...

**V1:** INCORRECT — NO_LOOKUP_MATCH

**V2:** INCORRECT — Per FPrimeSampleProject/fprime/Svc/Subtopologies/CdhCore/CMakeLists.txt, subtopologies use `register_fprime_module` with the `INTERFACE` directive, not `add_component`.
  Discrepancies: The `tui_response` states that `add_component` is used to register a subtopology, but `register_fprime_module` with the `INTERFACE` directive is the correct method., The `tui_response` implies a subtopology is treated as a separate component using `add_component` for registration, which is not the specific F' idiom for subtopologies.

---

## 112 [FAIL]

**Q:** What is the `FW_OPTIONAL_NAME` macro?

**TUI Response:** The `FW_OPTIONAL_NAME` macro in F' is used to define **optional parameters** or **optional command telemetry (CTE)** items in the flight software. It allows developers to specify that a parameter is **not required** to be present in certain modes or configurations (e.g., during specific mission phases or hardware states).

### Key Concepts:
1. **Optional Parameters**:  
   When a parameter is marked as optional, the software can handle cases where the parameter is not provided (e.g., default values, skip validation, or conditional logic).

2. **Topology File Context**:  
   This macro is typic...

**V1:** INCORRECT — Per FPrimeSampleProject/fprime/docs/user-manual/framework/configuring-fprime.md lines 158-161 and FPrimeSampleProject/fprime/default/config/FpConfig.h lines 32-35
  Discrepancies: The tui_response states FW_OPTIONAL_NAME defines 'optional parameters' or 'optional command telemetry (CTE) items' for mission phases/hardware states, and is used in topology.fpp for declaring optional parameters with default values., The source files indicate that FW_OPTIONAL_NAME conditionally returns an object's name string or an empty string based on whether FW_OBJECT_NAMES is enabled. Its primary purpose is to allow stripping component names from code to reduce binary size/RAM footprint when FW_OBJECT_NAMES is disabled.

**V2:** INCORRECT — grep_search for 'FW_OPTIONAL_NAME' in 'FPrimeSampleProject/fprime' with '.fpp' files yielded no results.
  Discrepancies: The TUI response describes 'FW_OPTIONAL_NAME' as a macro for optional parameters in FPP topology, but this macro could not be found in the F' codebase under that name, specifically in .fpp files., The 'expected_answer' appears to be referring to the 'FW_OBJECT_NAMES' macro, which controls object naming functionality in C++ based on compile-time flags (as seen in FPrimeSampleProject/fprime/Fw/Obj/ObjBase.hpp), not 'FW_OPTIONAL_NAME' as stated in the question.

---

## 121 [FAIL]

**Q:** Describe "Matched Ports" in FPP.

**TUI Response:** (TIMEOUT)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: Evaluator reported no TUI response

**V2:** INCORRECT — NO_RESPONSE

---

## 122 [FAIL]

**Q:** What is the default LLM used by Mission Control?

**TUI Response:** (TIMEOUT)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: Evaluator reported no TUI response

**V2:** INCORRECT — NO_RESPONSE

---

## 123 [FAIL]

**Q:** How do you verify that a unit test handler data didn't go out of scope?

**TUI Response:** (TIMEOUT)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: Evaluator reported no TUI response

**V2:** INCORRECT — NO_RESPONSE

---

## 124 [FAIL]

**Q:** What is the role of `Svc::PassiveConsoleTextLogger`?

**TUI Response:** (TIMEOUT)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: Evaluator reported no TUI response

**V2:** INCORRECT — NO_RESPONSE

---

## 125 [FAIL]

**Q:** Define NASA Rule #7: "Check Returns & Parameters."

**TUI Response:** (TIMEOUT)

**V1:** INCORRECT — NO_RESPONSE
  Discrepancies: Evaluator reported no TUI response

**V2:** INCORRECT — NO_RESPONSE

---

## 126 [FAIL]

**Q:** Define NASA Rule #6: "Minimal Scope."

**TUI Response:** NASA Rule #6: **"Minimal Scope"** emphasizes that flight software should include **only the essential features and functionality** required to fulfill its mission. This means avoiding unnecessary complexity, extra components, or capabilities that are not directly tied to the core objectives of the spacecraft or mission.

### Why It Matters:
- **Reduces Risk**: Extra code increases the chance of bugs, security vulnerabilities, or failures. For example, adding a "feature" to calculate star positions for a Mars rover when it’s not needed could introduce errors in critical navigation code.
- **Sim...

**V1:** INCORRECT — Per docs/fprime-docs/fprime_conventions.md under 'NASA's 10 Rules for Safety-Critical Code', Rule #6
  Discrepancies: The TUI response defines 'Minimal Scope' in terms of overall system features and functionality, whereas the authoritative F' documentation defines it specifically for data objects and their scope.

**V2:** INCORRECT — NO_LOOKUP_MATCH
  Discrepancies: The tui_response defines 'Minimal Scope' as a mission-level principle for flight software, focusing on essential features, while the expected_answer defines 'Rule #6' as a programming principle related to data object scope. These definitions are contradictory., No authoritative F' source could be found in 'docs/training/fprime_concept_map.md' to verify either the tui_response or the expected_answer against.

---
