# TUI/fprime_ai_client.py
import ollama
from typing import AsyncGenerator

class FPrimeAIClient:
    """
    Handles asynchronous communication with the local Ollama instance.
    """
    def __init__(self, model: str = "qwen3:8b"):
        self.model = model
        self.client = ollama.AsyncClient()

    def _get_system_prompt(self, context: str = "") -> str:
        """
        Constructs a context-aware system prompt for F' v4.0.
        """
        prompt = (
            "You are a Senior Principal Flight Software Engineer at NASA JPL, "
            "an expert in the F' (F Prime) v4.0 framework.\n"
            "Provide concise, high-performance, and flight-safe code (FPP or C++).\n"
            "Follow JPL's C++ Coding Standards and F' best practices.\n"
        )
        if context:
            prompt += f"\n### CURRENT FILE CONTEXT ###\n{context}\n###########################\n"
        
        return prompt

    async def stream_chat(self, prompt: str, context: str = "") -> AsyncGenerator[str, None]:
        """
        Streams a chat response from Ollama.
        """
        system_content = self._get_system_prompt(context)
        
        # Note: client.chat is an async function that returns an async generator when stream=True
        async for chunk in await self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            stream=True,
        ):
            yield chunk['message']['content']
