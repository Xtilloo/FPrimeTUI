#!/bin/bash
# Evaluator Agent launcher — run this in the Evaluator pane
# Starts Gemini with the evaluator script as initial prompt.
# Detects the TUI surface automatically via cmux list-panels.

cd /Users/xtilloo/Projects/FPrimeTUI

EVAL_SCRIPT="docs/training/scripts/evaluator_agent.md"

# TUI surface ID is written by the Orchestrator (Claude Code, surface:1) to tui_surface.txt
# because cmux read-screen cross-pane is only available from surface:1.
TUI_SURFACE=$(cat /Users/xtilloo/Projects/FPrimeTUI/docs/training/tui_surface.txt 2>/dev/null | tr -d '[:space:]')

if [[ -z "$TUI_SURFACE" ]]; then
    echo "WARNING: Could not auto-detect TUI surface (MY_SURFACE=$MY_SURFACE)"
    echo "Available panels:"
    cmux list-panels
    TUI_SURFACE="UNKNOWN_CHECK_cmux_list-panels"
fi

echo "=== Starting Gemini Evaluator Agent ==="
echo "Training data: docs/training/fprime_training.md"
echo "My surface:    (this pane)"
echo "TUI surface:   $TUI_SURFACE"
echo "Exchange file: docs/training/eval_exchange.json"
echo "======================================="
echo ""

HINT="CRITICAL RUNTIME NOTE: The TUI surface is $TUI_SURFACE.

The EXACT working command to send to the TUI is:
  cmux send --surface $TUI_SURFACE \"<text>\\n\"

You MUST include the full surface ref including the 'surface:' prefix (e.g. 'surface:11').
Using just '11' or 'surface 11' will FAIL. The ':' is required.

Example that WORKS:
  cmux send --surface $TUI_SURFACE \"/clear\\n\"

Do NOT use cmux read-screen at all — it is not available cross-pane."

gemini --yolo -m gemini-2.5-flash -p "$(cat $EVAL_SCRIPT)

---
$HINT"
