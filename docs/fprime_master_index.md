# F' Core Master Index
**Goal:** Minimize context window usage while maximizing repo awareness.
**Usage:** Consult this "Map" when navigating the F' core source code or looking for specific functionality.

## 1. Framework Core (Fw)
Fundamental classes and interfaces used across the entire framework.

| Component / Port | Key Files | Role | Usage |
| :--- | :--- | :--- | :--- |
| **Fw/Port** | `Fw/Port/Port.fpp`, `PortBase.cpp/hpp` | Base class for all F' ports. | Inherited by every port in the system. |
| **Fw/Obj** | `Fw/Obj/Obj.fpp`, `ObjBase.cpp/hpp` | Base class for all F' objects/components. | Provides identification and structural hierarchy. |
| **Fw/Cmd** | `Fw/Cmd/Cmd.fpp`, `CmdPort.fpp` | Ports and data for commands. | Enables components to receive and execute commands. |
| **Fw/Tlm** | `Fw/Tlm/Tlm.fpp`, `TlmPort.fpp` | Ports and data for telemetry. | Enables components to publish telemetry channels. |
| **Fw/Evr** | `Fw/Log/Log.fpp`, `LogPort.fpp` | Ports and data for events. | Enables components to report events (logs). |

## 2. Standard Services (Svc)
Common reusable services provided by F' for mission-critical functions.

| Component | Key Files | Role | Usage |
| :--- | :--- | :--- | :--- |
| **Svc/CmdDispatcher** | `Svc/CmdDispatcher/CmdDispatcher.fpp`, `CommandDispatcherImpl.cpp/hpp` | Central hub for routing commands from the ground. | Routes commands to components based on OpCodes. |
| **Svc/TlmChan** | `Svc/TlmChan/TlmChan.fpp`, `TlmChan.cpp/hpp` | Manages the telemetry database. | Stores and updates telemetry values for downlink. |
| **Svc/EventManager** | `Svc/EventManager/EventManager.fpp`, `EventManagerImpl.cpp/hpp` | Central hub for collecting and routing events. | Receives events and sends them to the ground logger. |
| **Svc/ActiveRateGroup** | `Svc/ActiveRateGroup/ActiveRateGroup.fpp` | Periodically triggers components in a group. | Used to schedule cyclic execution of components. |
| **Svc/Health** | `Svc/Health/Health.fpp`, `HealthImpl.cpp/hpp` | Monitors component heartbeats. | Detects hung components or system failures. |

## 3. Operating System Layer (Os)
OS-specific abstractions for portability.

| Module | Key Files | Role | Usage |
| :--- | :--- | :--- | :--- |
| **Os/Task** | `Os/Task.hpp`, `Os/Posix/Task.cpp` | Abstraction for OS threads. | Used by active components to run their internal loops. |
| **Os/Mutex** | `Os/Mutex.hpp`, `Os/Posix/Mutex.cpp` | Mutual exclusion primitives. | Used to protect shared resources in multi-threaded code. |
| **Os/File** | `Os/File.hpp`, `Os/Posix/File.cpp` | OS-independent file I/O. | Used by loggers and file managers. |
| **Os/Memory** | `Os/Memory.hpp` | Memory management abstractions. | Interface for framework-safe memory operations. |

## 4. Drivers (Drv)
Hardware-specific driver abstractions.

| Driver | Key Files | Role | Usage |
| :--- | :--- | :--- | :--- |
| **Drv/TcpClient** | `Drv/TcpClient/TcpClient.fpp`, `TcpClientImpl.cpp/hpp` | TCP network communication. | Often used for connecting to a ground station socket. |
| **Drv/Serial** | `Drv/Serial/Serial.fpp`, `SerialImpl.cpp/hpp` | UART serial communication. | Standard link for embedded hardware. |
