import json
from typing import Any, Dict, Optional

import httpx
import structlog

from finrag.agent.base import BaseLLM
from finrag.core.config import settings

logger = structlog.get_logger(__name__)


class OpenAIProvider(BaseLLM):
    """OpenAI API provider implementation using raw HTTP requests via HTTPX."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o") -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY.get_secret_value()
        self.model = model
        self.is_mock = self.api_key == "mock-openai-key"

        if self.is_mock:
            logger.info("Initializing OpenAIProvider in MOCK mode.")
        else:
            logger.info("Initializing OpenAIProvider in PRODUCTION mode.", model=self.model)

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Call OpenAI chat completion API or generate a mock response if keys are default."""
        if self.is_mock:
            return self._generate_mock_response(prompt)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]
                prompt_tokens = data.get("usage", {}).get("prompt_tokens", 0)
                completion_tokens = data.get("usage", {}).get("completion_tokens", 0)

                return {
                    "text": content,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
        except httpx.HTTPStatusError as e:
            logger.error("OpenAI API HTTP error", status_code=e.response.status_code, error=e.response.text)
            raise e
        except Exception as e:
            logger.exception("OpenAI API call failed", error=str(e))
            raise e

    def _generate_mock_response(self, prompt: str) -> Dict[str, Any]:
        """Generate deterministic mock responses for testing purposes."""
        logger.debug("Generating mock OpenAI response")

        # Basic parser queries
        lower_prompt = prompt.lower()

        # Check if this is a verification prompt (contains math mismatch guidance)
        if "recalculate" in lower_prompt or "validation failed" in lower_prompt or "correct your calculation" in lower_prompt:
            # The LLM is being asked to correct itself!
            mock_text = (
                "After recalculating, the correct operating margin is 40.0%.\n"
                "Here is the verified arithmetic calculation:\n"
                "```python\n"
                "result = 120 / 300\n"
                "```\n"
                "Citation: (doc_abc page 2)"
            )
        elif "margin" in lower_prompt or "calculate" in lower_prompt:
            # First attempt: let's output a wrong number to trigger validation / self-correction!
            # For testing, we can simulate an incorrect calculation:
            mock_text = (
                "The operating margin is 45.0% based on revenue of $300M and operating income of $120M.\n"
                "Calculation:\n"
                "```python\n"
                "result = 120 / 300\n"
                "```\n"
                "Citation: (doc_abc page 2)"
            )
        elif "lease" in lower_prompt:
            mock_text = (
                "The lease liability for 2026 is $120 million according to the footnotes.\n"
                "Citation: (doc_abc page 14)"
            )
        else:
            mock_text = (
                "Based on the retrieved context, the requested metric is $1.5 billion.\n"
                "Citation: (doc_abc page 5)"
            )

        return {
            "text": mock_text,
            "prompt_tokens": 150,
            "completion_tokens": 80,
        }
