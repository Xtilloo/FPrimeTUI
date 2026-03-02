import pytest
import asyncio
from TUI.controllers.ai_handler import AIHandler

class MockAIClient:
    def __init__(self, response_chunks):
        self.response_chunks = response_chunks
        self.chat_history = []

    async def stream_chat(self, context=""):
        for chunk in self.response_chunks:
            yield chunk

    def add_message(self, role, content):
        self.chat_history.append({"role": role, "content": content})

@pytest.mark.asyncio
async def test_ai_handler_robust_parsing():
    # Scenario: AI emits JSON without backticks and with conversational filler
    chunks = ["Here is the action:\n", "{\n  \"tool_name\": \"run_fprime_command\",\n", "  \"command\": \"build\"\n}"]
    client = MockAIClient(chunks)
    handler = AIHandler(client)
    
    full_text, tool_json = await handler.stream_and_parse()
    
    assert "Here is the action" in full_text
    assert tool_json is not None
    assert tool_json["tool_name"] == "run_fprime_command"

@pytest.mark.asyncio
async def test_ai_handler_no_tool():
    # Scenario: AI just talks
    chunks = ["I have finished the mission."]
    client = MockAIClient(chunks)
    handler = AIHandler(client)
    
    full_text, tool_json = await handler.stream_and_parse()
    
    assert "finished the mission" in full_text
    assert tool_json is None

@pytest.mark.asyncio
async def test_ai_handler_with_backticks():
    # Scenario: Standard markdown backticks
    chunks = ["```json\n{\n  \"tool_name\": \"list_directory\"\n}\n```"]
    client = MockAIClient(chunks)
    handler = AIHandler(client)
    
    full_text, tool_json = await handler.stream_and_parse()
    
    assert tool_json["tool_name"] == "list_directory"
