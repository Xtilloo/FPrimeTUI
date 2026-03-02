import asyncio
import os
import sys
from pathlib import Path

# Add project root to path so we can import TUI
sys.path.append(os.getcwd())

from TUI.app import FPrimeTUI

async def run_live_mission(prompt: str):
    """
    Runs a headless mission against the real AI and reports flight logs.
    """
    app = FPrimeTUI()
    app._show_agent_thoughts = True
    
    print(f"\n🚀 [MISSION INITIATED]: '{prompt}'")
    
    async with app.run_test() as pilot:
        # 1. Inject Prompt
        await pilot.click("#ai-input")
        await pilot.press(*prompt)
        await pilot.press("enter")
        
        # 2. Monitor Autonomous Loop
        print("🛰️  [PILOT]: AI is taking control. Monitoring flight logs...")
        
        last_history_len = 0
        timeout_counter = 0
        
        # Monitor for up to 5 minutes for complex operations
        for i in range(3000): 
            await pilot.pause(0.1)
            
            # Real-time progress detection
            current_history_len = len(app.chat_history)
            if current_history_len > last_history_len:
                new_content = app.chat_history[last_history_len:].strip()
                # Print only status lines or tool calls to keep it clean
                for line in new_content.splitlines():
                    if any(x in line for x in ["> *[Step", "[SYNTAX ERROR", "SYSTEM ERROR", "RECOVERY HINT"]):
                        print(f"📡 {line}")
                last_history_len = current_history_len
                timeout_counter = 0 # Reset timeout on activity
            else:
                timeout_counter += 1

            # Exit condition: Loop is inactive and AI is no longer generating
            if not app.is_generating and timeout_counter > 50: # 5 seconds of silence
                if i > 50: # Ensure we gave it a chance to start
                    break
        
        # 3. Final Report
        print("\n" + "="*40)
        print("🏁 [MISSION COMPLETE] - FINAL FLIGHT LOGS")
        print("="*40)
        print(app.chat_history.strip())
        print("="*40)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: PYTHONPATH=. ./venv/bin/python3 scripts/live_test.py \"your prompt here\"")
        sys.exit(1)
        
    user_prompt = sys.argv[1]
    asyncio.run(run_live_mission(user_prompt))
