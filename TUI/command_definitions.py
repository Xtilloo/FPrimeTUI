from enum import Enum
from dataclasses import dataclass
from typing import List, Set

class TUIMode(Enum):
    MISSION_CONTROL = "dev"
    ACADEMY = "academy"

@dataclass
class CommandMetadata:
    name: str
    description: str
    allowed_modes: Set[TUIMode]

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

"""
command_definitions.py - Structured Registry for F' Commands
"""

COMMAND_REGISTRY = {
    "generate": {
        "executable": "fprime-util",
        "required_files": ["settings.ini", "CMakeLists.txt"],
        "safe_args": ["-p", "--platform", "-t", "--toolchain", "--no-alias", "--help"],
        "description": "Generate build cache (CMake). Required before build.",
        "preflight_checks": ["check_cmake", "check_settings_ini"]
    },
    "build": {
        "executable": "fprime-util",
        "required_files": ["CMakeLists.txt"],
        "safe_args": ["-j", "--jobs", "--ut", "--help"],
        "description": "Compile the project, component, or deployment.",
        "preflight_checks": ["check_build_cache"]
    },
    "check": {
        "executable": "fprime-util",
        "required_files": ["CMakeLists.txt"],
        "safe_args": ["-j", "--jobs", "--coverage", "--help"],
        "description": "Run unit tests.",
        "preflight_checks": ["check_build_cache"]
    },
    "impl": {
        "executable": "fprime-util",
        "required_files": [".fpp", ".fpc"],
        "safe_args": ["--help"],
        "description": "Generate C++ implementation templates from FPP.",
    },
    "fpp-check": {
        "executable": "fpp-check",
        "required_files": [],
        "safe_args": ["-i", "--imports", "--help"],
        "description": "Run FPP syntax and semantic checks.",
    },
    "new": {
        "executable": "fprime-util",
        "required_files": ["settings.ini"],
        "safe_args": ["--component", "--deployment", "--module", "--help"],
        "description": "Create new F' objects (Interactive Wizard).",
    },
    "channels": {
        "executable": "fprime-cli",
        "required_files": ["settings.ini"],
        "safe_args": ["-l", "--logs", "--list", "-i", "-c", "--help"],
        "description": "GDS: Monitor telemetry channels.",
    },
    "events": {
        "executable": "fprime-cli",
        "required_files": ["settings.ini"],
        "safe_args": ["-l", "--logs", "--list", "-i", "-c", "--help"],
        "description": "GDS: Monitor events data.",
    },
    "command-send": {
        "executable": "fprime-cli",
        "required_files": ["settings.ini"],
        "safe_args": ["--arguments", "--help"],
        "description": "GDS: Send commands to flight software.",
    }
}

ERROR_FINGERPRINTS = [
    {
        "id": "missing_cmake",
        "regex": r"cmake: command not found",
        "hint": "CMake is not installed or not in PATH. Please install CMake 3.16+."
    },
    {
        "id": "missing_settings_ini",
        "regex": r"Could not find settings.ini",
        "hint": "settings.ini is missing from the project root. Run this command from the project root or create settings.ini."
    },
    {
        "id": "build_cache_missing",
        "regex": r"Build directory .* does not exist",
        "hint": "The build cache is missing. You MUST run 'fprime-util generate' first."
    },
    {
        "id": "build_cache_invalid",
        "regex": r"is not a valid build cache",
        "hint": "The build cache is invalid or missing. You MUST run 'fprime-util generate' at the project root before this command will work."
    },
    {
        "id": "autocoder_error",
        "regex": r"\[ERROR\] Autocoder failed",
        "hint": "Autocoder failed. Check your FPP files for syntax errors or missing port connections."
    },
    {
        "id": "linker_error",
        "regex": r"undefined reference to",
        "hint": "Linker error. This usually means a source file is missing from CMakeLists.txt or a port is not implemented."
    },
    {
        "id": "python_dependency",
        "regex": r"ModuleNotFoundError: No module named '(\w+)'",
        "hint": "Missing Python dependency: {0}. Try running 'pip install {0}' in the fprime-venv."
    },
    {
        "id": "command_not_found",
        "regex": r"/bin/bash: ([\w-]+): command not found",
        "hint": "Command '{0}' not found. Most F' tasks use 'fprime-util <command>'. For creating components, use 'fprime-util new --component'."
    },
    {
        "id": "gds_artifacts_missing",
        "regex": r"Exception: (.*) does not exist\. Make sure to build\.",
        "hint": "GDS artifacts not found at {0}. You must run 'fprime-util build' to generate artifacts before using 'fprime-cli'."
    },
    {
        "id": "ninja_missing",
        "regex": r"ninja: error: loading 'build.ninja': No such file or directory",
        "hint": "Build control file (build.ninja) is missing. You MUST run 'fprime-util generate' first."
    },
    {
        "id": "invalid_object_name",
        "regex": r"ValueError: Unacceptable (\w+) name:? (.*)\. Do not use spaces or special characters",
        "hint": "Invalid {0} name '{1}'. F' object names (components, deployments, etc.) must not contain spaces or special characters."
    }
]
