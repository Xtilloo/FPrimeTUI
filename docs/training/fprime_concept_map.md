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
