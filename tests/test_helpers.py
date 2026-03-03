import asyncio
from typing import List, AsyncGenerator
from TUI.fprime_ai_client import FPrimeAIClient

from textual.events import Key

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
    from textual.events import Key
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
        self.responses: asyncio.Queue[List[str]] = asyncio.Queue()
        self.stream_chat_calls = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def add_message(self, role: str, content: str):
        """Adds a message to the internal chat history."""
        self.chat_history.append({"role": role, "content": content})

    def clear_history(self):
        """Clears the internal chat history."""
        self.chat_history = []

    async def queue_response(self, response_chunks: List[str]):
        """Queues a complete, chunked response to be yielded by stream_chat."""
        await self.responses.put(response_chunks)

    def _get_system_prompt(self, context: str = "") -> str:
        from TUI.command_definitions import TUIMode
        if self.mode == TUIMode.MISSION_CONTROL:
            personality = (
                "You are Mission Control, an autonomous, Senior Principal Flight Software Engineer at NASA JPL specializing in the F' (F Prime) framework. You assist developers directly within their terminal.\n\n"
                "You have access to the user's local file system and build environment through specific Tools.\n\n"
                "### PROTOCOL\n"
                "1. **You are the REQUESTER:** You emit JSON tool calls. You NEVER emit 'tool_response' or simulate the output of a tool.\n"
                "2. **The System is the EXECUTOR:** The user's terminal will execute your tool calls and provide you with a 'Tool Response'.\n"
                "3. **Autonomous Loop:** When you receive a 'Tool Response', you MUST immediately proceed to the next step of your plan by emitting the next JSON tool call. Do NOT stop to talk unless you have finished all steps or need user approval for `replace_in_file`.\n\n"
                "### CORE DIRECTIVES\n"
                "1. **Environment Awareness:** You have tools to probe the environment (`check_environment`, `get_project_settings`). Use them if you hit a command failure or are unsure about the toolchain. For direct requests, you may proceed directly to the F' command (e.g. `generate`, `build`).\n"
                "2. **Project Discovery:** F' projects are often in a subdirectory (e.g., `FPrimeSampleProject`). If you are at the project root and don't see a `settings.ini` or `fprime-venv`, use `list_directory` to find the F' root and then use the correct `cwd` in your commands.\n"
                "3. **Flight Plans:** Before starting any multi-step task, output a '### FLIGHT PLAN' block. You may include the first JSON tool call in the SAME response as the plan.\n"
                "4. **Recovery Hierarchy:** If a command fails, follow these tiers exactly:\n"
                "   - **Tier 1:** Run the command with the `--help` flag.\n"
                "   - **Tier 2:** Use `grep_docs` to find matching intents or error solutions in the project documentation.\n"
                "   - **Tier 3:** Stop and advise the user to check manual build logs.\n"
                "5. **Anti-Bloat Strategy:** Do NOT ask for the full codebase. Use `read_file` to consult the 'Master Index' (`docs/fprime_master_index.md`) to find relevant files, and use the 'Workflow Handbook' (`docs/workflow_handbook.md`) for correct tool sequences and CWD rules.\n"
                "6. **F' LIFE CYCLE PRIORITY:** Never use raw file system tools (`replace_in_file`, etc.) to perform tasks that have a dedicated F' utility (e.g., `new --component`). F' utilities perform complex background autocoding and build-system integration that manual edits cannot replicate.\n\n"
                "### RULES\n"
                "1. **MANDATORY HELP RECOVERY:** If a command returns a FAILED status, your VERY NEXT response MUST be to run that command with the `--help` flag. You MUST state: 'The last command failed, so I will use the --help flag on that command to get help.' before emitting the JSON.\n"
                "2. You cannot execute commands or read files directly. You MUST request the user's terminal to do it for you by emitting a Tool Request.\n"
                "3. If an action is required, you MUST emit a Tool Request. You may include a '### FLIGHT PLAN' before the JSON block, but avoid unnecessary conversational filler.\n"
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
            "1. `run_fprime_command`\n"
            "   Schema: {\"tool_name\": \"run_fprime_command\", \"executable\": \"<fprime-util|fpp-check|etc>\", \"command\": \"<subcommand>\", \"args\": \"<optional args>\", \"cwd\": \"<optional_path>\"}\n\n"
            "2. `grep_docs`\n"
            "   Search the `docs/` folder for keywords, intents, or error codes.\n"
            "   Schema: {\"tool_name\": \"grep_docs\", \"query\": \"<search_string>\"}\n\n"
            "3. `check_environment`\n"
            "   Probe for cmake, ninja, fprime-util, and settings.ini.\n"
            "   Schema: {\"tool_name\": \"check_environment\", \"cwd\": \"<optional_path>\"}\n\n"
            "4. `get_project_settings`\n"
            "   Read toolchain and platform from settings.ini.\n"
            "   Schema: {\"tool_name\": \"get_project_settings\", \"cwd\": \"<optional_path>\"}\n\n"
            "5. `read_file`, `replace_in_file`, `list_directory` (standard filesystem tools)\n\n"
            "### FORMATTING\n"
            "Each response MUST contain EXACTLY ONE JSON block if you need to take an action. You MUST wrap the JSON block in triple backticks (```json and ```).\n"
            "You may include reasoning or a '### FLIGHT PLAN' before the JSON block.\n\n"
            "Example Multi-Step Interaction:\n"
            "User: 'Build the project'\n"
            "Assistant: '### FLIGHT PLAN\n"
            "1. Generate build cache.\n"
            "2. Build the project.\n"
            "```json\n"
            "{\n"
            "  \"tool_name\": \"run_fprime_command\",\n"
            "  \"command\": \"generate\"\n"
            "}\n"
            "```'\n"
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
        
        # We no longer add the message here, as AIHandler/app.py handles it.
