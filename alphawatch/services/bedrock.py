"""AWS Bedrock client wrapper for Claude models."""

import json
import logging
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from alphawatch.config import get_settings

logger = logging.getLogger(__name__)


class BedrockClient:
    """Wrapper for AWS Bedrock Runtime API with Claude models.

    Provides a simplified interface for invoking Claude models via
    AWS Bedrock. Uses the Messages API format for Claude 3+ models.

    Args:
        region: AWS region name. Defaults to settings.aws_region.
        model_id: Default model ID. Can be overridden per call.
    """

    def __init__(
        self,
        region: str | None = None,
        model_id: str | None = None,
    ) -> None:
        settings = get_settings()
        self._region = region or settings.aws_region
        self._default_model_id = model_id or settings.bedrock_sentiment_model_id

        # Configure boto3 client with retry logic
        config = Config(
            region_name=self._region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        self._client = boto3.client("bedrock-runtime", config=config)

    def invoke(
        self,
        prompt: str,
        model_id: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        top_p: float = 1.0,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """Invoke a Claude model and return the response text.

        Args:
            prompt: User prompt text.
            model_id: Bedrock model ID. Defaults to instance default.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic).
            top_p: Nucleus sampling parameter.
            stop_sequences: List of stop sequences.

        Returns:
            The generated response text.

        Raises:
            ClientError: If the Bedrock API call fails.
            ValueError: If the response format is invalid.
        """
        model_id = model_id or self._default_model_id

        # Build request body in Claude Messages API format
        body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        if system_prompt:
            body["system"] = system_prompt

        if stop_sequences:
            body["stop_sequences"] = stop_sequences

        try:
            response = self._client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            content_blocks = response_body.get("content", [])

            if not content_blocks:
                raise ValueError("No content blocks in Bedrock response")

            # Extract text from first content block
            text = content_blocks[0].get("text", "")
            if not text:
                raise ValueError("Empty text in Bedrock response content block")

            logger.debug(
                "Bedrock invoke: model=%s tokens=%d",
                model_id,
                response_body.get("usage", {}).get("output_tokens", 0),
            )

            return text

        except ClientError as exc:
            logger.error("Bedrock API error: %s", exc)
            raise
        except Exception as exc:
            logger.error("Bedrock invoke failed: %s", exc)
            raise

    def invoke_with_json(
        self,
        prompt: str,
        model_id: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Invoke a Claude model expecting JSON output.

        Instructs the model to respond with valid JSON and parses
        the response. Useful for structured outputs like sentiment scores.

        Args:
            prompt: User prompt text (should request JSON output).
            model_id: Bedrock model ID. Defaults to instance default.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic).

        Returns:
            Parsed JSON response as a dict.

        Raises:
            ClientError: If the Bedrock API call fails.
            json.JSONDecodeError: If the response is not valid JSON.
        """
        # Append JSON instruction to prompt if not already present
        if "JSON" not in prompt and "json" not in prompt:
            prompt = f"{prompt}\n\nRespond with valid JSON only, no other text."

        response_text = self.invoke(
            prompt=prompt,
            model_id=model_id,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Strip markdown code blocks if present
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        return json.loads(response_text.strip())

    def score_sentiment(
        self,
        text: str,
        company_name: str,
        ticker: str,
    ) -> int:
        """Score the sentiment of text toward a company.

        Uses Claude Haiku to analyze sentiment and return a score
        from -100 (very negative) to +100 (very positive).

        Args:
            text: Text to analyze (news article, filing excerpt, etc.).
            company_name: Company name for context.
            ticker: Stock ticker symbol for context.

        Returns:
            Sentiment score from -100 to +100.

        Raises:
            ClientError: If the Bedrock API call fails.
            ValueError: If the score is not in the expected range.
        """
        settings = get_settings()

        system_prompt = (
            "You are a financial sentiment analyzer. Analyze the sentiment "
            "of the provided text toward the specified company and return "
            "a sentiment score from -100 (very negative) to +100 (very positive). "
            "Consider financial implications, tone, and context."
        )

        prompt = f"""Analyze the sentiment of the following text toward {company_name} ({ticker}).

Text:
{text[:2000]}

Respond with a JSON object containing:
- "score": integer from -100 to +100
- "reasoning": brief explanation (1-2 sentences)

Example response:
{{"score": 25, "reasoning": "The article highlights positive earnings growth but notes increased competition."}}
"""

        try:
            result = self.invoke_with_json(
                prompt=prompt,
                model_id=settings.bedrock_sentiment_model_id,
                system_prompt=system_prompt,
                max_tokens=500,
                temperature=0.0,
            )

            score = result.get("score")
            if not isinstance(score, int):
                raise ValueError(f"Invalid sentiment score type: {type(score)}")

            if not -100 <= score <= 100:
                raise ValueError(f"Sentiment score out of range: {score}")

            logger.info(
                "Sentiment scored: company=%s score=%d",
                ticker,
                score,
            )

            return score

        except Exception as exc:
            logger.error("Sentiment scoring failed: %s", exc)
            # Return neutral score on error rather than failing the whole pipeline
            return 0

    def generate_summary(
        self,
        text: str,
        max_words: int = 150,
        model_id: str | None = None,
    ) -> str:
        """Generate a concise summary of text.

        Args:
            text: Text to summarize.
            max_words: Target summary length in words.
            model_id: Bedrock model ID. Defaults to instance default.

        Returns:
            Summary text.

        Raises:
            ClientError: If the Bedrock API call fails.
        """
        prompt = f"""Summarize the following text in approximately {max_words} words.
Focus on the most important information and maintain a professional tone.

Text:
{text[:4000]}

Summary:"""

        return self.invoke(
            prompt=prompt,
            model_id=model_id,
            max_tokens=max_words * 2,  # rough token estimate
            temperature=0.3,
        )
