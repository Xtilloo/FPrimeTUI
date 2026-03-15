from dataclasses import dataclass
from enum import Enum


class TUIMode(Enum):
    MISSION_CONTROL = "dev"
    ACADEMY = "academy"

@dataclass
class CommandMetadata:
    name: str
    description: str
    allowed_modes: set[TUIMode]

COMMANDS = [
    CommandMetadata("/clear", "Clear chat history", {TUIMode.MISSION_CONTROL, TUIMode.ACADEMY}),
    CommandMetadata("/help", "Show help documentation", {TUIMode.MISSION_CONTROL, TUIMode.ACADEMY}),
    CommandMetadata("/exit", "Exit Mission Control", {TUIMode.MISSION_CONTROL, TUIMode.ACADEMY}),
    CommandMetadata("/mode", "Switch TUI mode (/mode dev|academy)", {TUIMode.MISSION_CONTROL, TUIMode.ACADEMY}),
    CommandMetadata("/info", "Print contextual target and cache info", {TUIMode.MISSION_CONTROL, TUIMode.ACADEMY}),
    CommandMetadata("/version-check", "Print toolchain versions", {TUIMode.MISSION_CONTROL, TUIMode.ACADEMY}),

    # Mission Control Only Commands
    CommandMetadata("/build", "Build components, deployments, and unit tests", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/check", "Run unit tests with optional test coverage", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/generate", "Generate build caches", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/purge", "Remove build caches", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/fpp-check", "Run fpp-check utility", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/fpp-to-dict", "Run fpp-to-dict utility", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/visualize", "Visualize FPP model in web GUI", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/impl", "Generate implementation templates", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/hash-to-file", "Convert FW_ASSERT hash to path", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/new", "Generate a new fprime object (component, deployment, etc.)", {TUIMode.MISSION_CONTROL}),
    CommandMetadata("/format", "Format C/C++ files using clang-format", {TUIMode.MISSION_CONTROL}),
]
