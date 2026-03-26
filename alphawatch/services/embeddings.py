"""Amazon Titan Embeddings v2 service via AWS Bedrock."""

import json
import logging

import boto3

from alphawatch.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """Client for Amazon Titan Embeddings v2 via AWS Bedrock.

    Generates 1536-dimensional embeddings for text inputs.

    Args:
        region: AWS region for the Bedrock endpoint.
        model_id: Bedrock model identifier.
    """

    def __init__(
        self,
        region: str | None = None,
        model_id: str | None = None,
    ) -> None:
        settings = get_settings()
        self._region = region or settings.aws_region
        self._model_id = model_id or settings.bedrock_embeddings_model_id
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=self._region,
        )

    def embed_text(self, text: str) -> list[float]:
        """Generate an embedding for a single text string.

        Args:
            text: The input text to embed.

        Returns:
            A 1536-dimensional float vector.
        """
        body = json.dumps({"inputText": text})
        response = self._client.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    def embed_batch(self, texts: list[str], log_interval: int = 25) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Each text is embedded individually via ``invoke_model`` (Titan v2
        does not support native batching). Progress is logged every
        ``log_interval`` texts.

        Args:
            texts: List of input texts to embed.
            log_interval: Log progress every N texts.

        Returns:
            List of 1536-dimensional float vectors, one per input text.
        """
        embeddings: list[list[float]] = []
        for i, text in enumerate(texts):
            embeddings.append(self.embed_text(text))
            if (i + 1) % log_interval == 0 or (i + 1) == len(texts):
                logger.info("Embedded %d / %d texts", i + 1, len(texts))
        return embeddings
