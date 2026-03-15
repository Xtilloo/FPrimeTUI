#!/bin/bash
# Launch autonomous Claude agent for RAG evaluation Q41-Q262
cd /Users/xtilloo/Projects/FPrimeTUI
claude --dangerously-skip-permissions -p "$(cat /Users/xtilloo/Projects/FPrimeTUI/ClaudesLogs/scratch/autonomous-agent-prompt.md)"
