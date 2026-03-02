import asyncio
import os
import sys
sys.path.append(os.getcwd())
from TUI.app import FPrimeTUI

async def run_live_mission():
    app = FPrimeTUI()
    app._show_agent_thoughts = True
    
    async with app.run_test() as pilot:
        print("\n[LIVE PILOT]: Sending prompt: 'Create a new component called TempSensor'...")
        await pilot.click("#ai-input")
        await pilot.press(*"Create a new component called TempSensor")
        await pilot.press("enter")
        
        # Wait for generation to START (Indicator becomes visible)
        print("[LIVE PILOT]: Waiting for AI to start thinking...")
        for _ in range(100):
            await pilot.pause(0.1)
            if app.is_generating:
                print("[LIVE PILOT]: AI is generating...")
                break
        
        # Wait for full autonomous loop to FINISH
        print("[LIVE PILOT]: Monitoring autonomous loop (streaming + tool calls)...")
        for i in range(1800): # 3 minute timeout
            await pilot.pause(0.1)
            # We check if input is re-enabled AND is_generating is false
            # and if we have at least some content in history beyond the user prompt
            if not app.is_generating and i > 50:
                # Small buffer to ensure any background tool results are processed
                await pilot.pause(1.0)
                if not app.is_generating:
                    break
        
        print("\n" + "="*30)
        print("REAL TUI OUTPUT (GLM-4.7-FLASH)")
        print("="*30)
        print(app.chat_history)
        print("="*30)

if __name__ == "__main__":
    asyncio.run(run_live_mission())
