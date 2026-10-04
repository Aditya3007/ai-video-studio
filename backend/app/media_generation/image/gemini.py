"""Gemini image generation provider adapter."""

import base64
import os

from app.media_generation.image.errors import ImageGenerationError
from app.media_generation.image.provider import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageReference,
    ImageUsage,
)


class GeminiImageProvider:
    """Gemini image generation provider adapter using Google Gen AI SDK."""

    def __init__(
        self,
        *,
        model: str = "gemini-3.1-flash-image",
        api_key: str | None = None,
    ) -> None:
        """Initialize Gemini provider.

        Args:
            model: Gemini model identifier (image generation model).
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY environment variable.
        """
        self._model = model
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not self._api_key:
            raise ImageGenerationError(
                "Gemini API key is required. Set GEMINI_API_KEY environment "
                "variable or pass api_key parameter."
            )

        try:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        except ImportError as exc:
            raise ImageGenerationError(
                "Google Gen AI SDK is not installed. Install with: pip install google-genai"
            ) from exc

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate images using Gemini.

        Args:
            request: Provider-neutral image generation request.

        Returns:
            Provider-neutral image generation result.

        Raises:
            ImageGenerationError: If generation fails.
        """
        try:
            from google import genai

            # Use the interactions API for image generation
            # For Nano Banana image models, we need to specify response modalities
            response = self._client.models.generate_content(
                model=self._model,
                contents=request.prompt,
                config=genai.GenerateContentConfig(
                    response_modalities=["Image", "Text"],
                ),
            )

            # Extract generated image data
            if response.output_image:
                # Get the image data as bytes
                image_data = response.output_image.data
                # Create base64 URI for the image
                uri = f"data:image/png;base64,{base64.b64encode(image_data).decode('utf-8')}"

                # Determine dimensions from aspect ratio or use defaults
                width = 1080
                height = 1920
                if request.aspect_ratio:
                    parts = request.aspect_ratio.split(":")
                    if len(parts) == 2:
                        try:
                            ar_w = int(parts[0])
                            ar_h = int(parts[1])
                            # Scale to reasonable dimensions
                            if ar_w / ar_h > 1:
                                width = 1080
                                height = int(1080 * ar_h / ar_w)
                            else:
                                height = 1920
                                width = int(1920 * ar_w / ar_h)
                        except ValueError:
                            pass  # Use defaults

                image_ref = ImageReference(
                    uri=uri,
                    width=width,
                    height=height,
                    content_type="image/png",
                )

                return ImageGenerationResult(
                    images=[image_ref],
                    provider="gemini",
                    model=self._model,
                    usage=ImageUsage(
                        cost_usd=0.0,  # Placeholder for actual pricing
                    ),
                    metadata={
                        "request_id": getattr(response, "id", None),
                    },
                )

            # If no image data returned
            raise ImageGenerationError(
                "Gemini did not return image data. "
                "Ensure the model supports image generation "
                "and response_modalities include 'Image'."
            )

        except Exception as exc:
            raise ImageGenerationError(f"Gemini image generation failed: {exc}") from exc
