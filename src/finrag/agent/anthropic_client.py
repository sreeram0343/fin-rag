import json
from typing import Any, Dict, Optional

import httpx
import structlog

from finrag.agent.base import BaseLLM
from finrag.core.config import settings

logger = structlog.get_logger(__name__)


class AnthropicProvider(BaseLLM):
    """Anthropic API provider implementation using raw HTTP requests via HTTPX."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20240620") -> None:
        self.api_key = api_key or settings.ANTHROPIC_API_KEY.get_secret_value()
        self.model = model
        self.is_mock = self.api_key == "mock-anthropic-key"

        if self.is_mock:
            logger.info("Initializing AnthropicProvider in MOCK mode.")
        else:
            logger.info("Initializing AnthropicProvider in PRODUCTION mode.", model=self.model)

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Call Anthropic API or generate a mock response if keys are default."""
        if self.is_mock:
            return self._generate_mock_response(prompt)

        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                content = data["content"][0]["text"]
                prompt_tokens = data.get("usage", {}).get("input_tokens", 0)
                completion_tokens = data.get("usage", {}).get("output_tokens", 0)

                return {
                    "text": content,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
        except httpx.HTTPStatusError as e:
            logger.error("Anthropic API HTTP error", status_code=e.response.status_code, error=e.response.text)
            raise e
        except Exception as e:
            logger.exception("Anthropic API call failed", error=str(e))
            raise e

    def _generate_mock_response(self, prompt: str) -> Dict[str, Any]:
        """Generate deterministic mock responses for testing purposes."""
        logger.debug("Generating mock Anthropic response")

        lower_prompt = prompt.lower()

        if "recalculate" in lower_prompt or "validation failed" in lower_prompt or "correct your calculation" in lower_prompt:
            mock_text = (
                "After recalculating, the correct operating margin is 40.0%.\n"
                "Calculation:\n"
                "```python\n"
                "result = 120 / 300\n"
                "```\n"
                "Citation: (doc_abc page 2)"
            )
        elif "margin" in lower_prompt or "calculate" in lower_prompt:
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
