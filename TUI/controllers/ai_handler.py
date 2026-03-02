import re
import json
from typing import Optional, Tuple, Any

class AIHandler:
    """
    Manages the AI interaction loop, including streaming and robust tool parsing.
    """
    def __init__(self, ai_client):
        self.client = ai_client

    async def stream_and_parse(self, context: str = "") -> Tuple[str, Optional[dict]]:
        """
        Streams from the AI client and extracts the first JSON tool call found.
        Returns (full_text, parsed_json).
        """
        full_text = ""
        async for chunk in self.client.stream_chat(context=context):
            full_text += chunk
        
        # Add to client history after full stream to maintain state
        self.client.add_message("assistant", full_text)
        
        tool_json = self.parse_tool_call(full_text)
        return full_text, tool_json

    def parse_tool_call(self, text: str) -> Optional[dict]:
        """
        Robustly extracts JSON tool calls from text.
        Tries backticks first, then fallbacks to raw { "tool_name": ... } blocks.
        """
        # Try finding markdown JSON blocks first
        markdown_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if markdown_match:
            try:
                return json.loads(markdown_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Fallback: search for the first { that looks like a tool call
        raw_match = re.search(r"({[\s\n]*\"tool_name\".*?})", text, re.DOTALL)
        if raw_match:
            try:
                return json.loads(raw_match.group(1))
            except json.JSONDecodeError:
                pass
                
        return None

    def add_message(self, role: str, content: str):
        self.client.add_message(role, content)
