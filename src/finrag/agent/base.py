from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseLLM(ABC):
    """Abstract interface for all LLM providers in the FinRAG platform."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Send a prompt to the LLM and return the generated content and token usage statistics.

        Args:
            prompt: The user query context prompt.
            system_prompt: Guidelines instructing model behavior.
            temperature: Sampling temperature (default 0.0 for deterministic output).

        Returns:
            A dict containing:
            - "text": The generated text response string.
            - "prompt_tokens": Number of tokens in input context.
            - "completion_tokens": Number of tokens generated in response.
        """
        pass
