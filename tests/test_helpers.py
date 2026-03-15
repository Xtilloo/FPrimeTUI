import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from textual.events import Key

from TUI.fprime_ai_client import FPrimeAIClient


async def submit_query(pilot, app, text: str):
    """Helper to reliably submit a query in tests."""
    await pilot.pause()
    input_widget = app.query_one("#ai-input")

    # Wait for input to be enabled if it's currently disabled (AI is thinking)
    # In tests, we should probably just assert it's enabled to catch logic errors.
    assert not input_widget.disabled, f"Cannot submit query '{text}', input is disabled!"

    await pilot.click("#ai-input")
    if text:
        await pilot.press(*text)
        await pilot.pause()

    # Hide autocomplete list to ensure Enter triggers query, not selection
    app.query_one("#autocomplete-list").display = False

    # Manually trigger the on_key handler of the input widget
    input_widget.on_key(Key("enter", "\r"))
    await pilot.pause()

class MockAIClient(FPrimeAIClient):
    """
    A mock AI client for deterministic testing of the TUI.
    This class mirrors the public interface of the real FPrimeAIClient
    but uses a pre-filled queue for responses instead of calling Ollama.
    """
    def __init__(self, model: str = "mock_model", mode=None):
        # We do NOT call super().__init__() because we don't want to create
        # a real ollama.AsyncClient.
        self.model = model
        self.mode = mode
        self.chat_history = []
        self.responses: asyncio.Queue[list[str]] = asyncio.Queue()
        self.stream_chat_calls: list[dict[str, Any]] = []

    def add_message(self, role: str, content: str):
        """Adds a message to the internal chat history."""
        self.chat_history.append({"role": role, "content": content})

    def clear_history(self):
        """Clears the internal chat history."""
        self.chat_history = []

    async def queue_response(self, response_chunks: list[str]):
        """Queues a complete, chunked response to be yielded by stream_chat."""
        await self.responses.put(response_chunks)

    def _get_system_prompt(self, context: str = "") -> str:
        from TUI.command_definitions import TUIMode
        if self.mode == TUIMode.MISSION_CONTROL:
            personality = (
                "You are Mission Control, an autonomous, Senior Principal Flight Software Engineer at NASA JPL specializing in the F' (F Prime) framework. You assist developers directly within their terminal.\n\n"
                "You have access to the user's local file system and build environment through specific Tools.\n\n"
                "### RULES\n"
                "1. You cannot execute commands or read files directly. You MUST request the user's terminal to do it for you by emitting a Tool Request.\n"
                "2. If the user asks you to perform an action (e.g., 'build the project', 'edit this file'), you MUST emit a Tool Request immediately. Do not respond with conversational text if an action is required.\n"
                "3. You must wait for the 'Tool Response' before proceeding to the next step of a complex task.\n"
                "4. When writing F' code, you strictly adhere to JPL C++ coding standards.\n"
                "5. Do not hallucinate file contents. If you need to edit a file, use the `read_file` tool first.\n"
                "6. ALWAYS wrap code snippets or file contents in triple backticks (e.g., ```cpp) with the appropriate language identifier.\n\n"
            )
        else: # ACADEMY
            personality = (
                "You are an F' Academy instructor. You are patient, educational, and focused on helping users understand F' (F Prime) concepts, architecture, and why it is important for flight software.\n\n"
                "Your goal is to teach and guide. Do not propose code changes or execute tools unless explicitly asked to explain a snippet or help with a learning exercise.\n\n"
                "### RULES\n"
                "1. Focus on explanations and conceptual understanding.\n"
                "2. Use analogies to explain complex flight software concepts (e.g., components as Lego blocks, ports as electrical connectors).\n"
                "3. If a user asks for a technical action that requires a tool (like building), politely explain that in Academy mode, we focus on learning, and they should switch to Mission Control for engineering tasks.\n\n"
            )

        prompt = (
            personality +
            "### AVAILABLE TOOLS\n"
            "You can request the following tools by outputting a JSON block wrapped in ```json tags.\n\n"
            "1. `run_fprime_command`\n"
            "   Use this to compile, check, or generate F' code.\n"
            "   Schema: {\"tool_name\": \"run_fprime_command\", \"command\": \"<build|check|generate|purge|fpp-check|fpp-to-dict|visualize|impl|hash-to-file|info|version-check|new|format>\", \"args\": \"<optional args>\", \"cwd\": \"<optional_path>\"}\n\n"
            "2. `read_file`\n"
            "   Use this to read a file from the project.\n"
            "   Schema: {\"tool_name\": \"read_file\", \"path\": \"<file_path>\"}\n\n"
            "3. `replace_in_file`\n"
            "   Use this to edit an existing file. You must provide the exact existing content to replace.\n"
            "   Schema: {\"tool_name\": \"replace_in_file\", \"path\": \"<path>\", \"old_content\": \"<exact literal text to replace>\", \"new_content\": \"<new text>\"}\n\n"
            "4. `list_directory`\n"
            "   Use this to see what files exist in a directory.\n"
            "   Schema: {\"tool_name\": \"list_directory\", \"path\": \"<dir_path>\"}\n\n"
            "### FORMATTING\n"
            "To use a tool, your entire response should be the JSON block. Do NOT add conversational text before or after the JSON block if you are using a tool.\n\n"
            "Example Tool Request:\n"
            "```json\n"
            "{\n"
            "  \"tool_name\": \"read_file\",\n"
            "  \"path\": \"Top/topology.fpp\"\n"
            "}\n"
            "```\n\n"
            "If no tools are needed (e.g., answering a general question, or after completing all steps of a task), reply with normal Markdown text.\n"
        )
        if context:
            prompt += f"\n### CURRENT FILE CONTEXT ###\n{context}\n###########################\n"
        return prompt

    async def stream_chat(self, context: str = "") -> AsyncGenerator[str, None]:
        """
        Yields chunks from the pre-queued response and records the call.
        """
        system_prompt = self._get_system_prompt(context)
        # Record the state of the client at the time of the call for assertions
        self.stream_chat_calls.append({
            "history": list(self.chat_history), # Record a copy
            "system_prompt": system_prompt
        })

        if self.responses.empty():
            # If no response is queued, yield nothing.
            if False: # This is a trick to make this a generator
                yield
            return

        response_chunks = await self.responses.get()
        full_response_for_history = ""
        for chunk in response_chunks:
            full_response_for_history += chunk
            yield chunk
            await asyncio.sleep(0.05) # Small sleep to allow cancellation between chunks

        # The real client adds the assistant's full response to history *after* streaming.
        self.add_message("assistant", full_response_for_history)
