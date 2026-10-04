"""Tests for Gemini image generation provider.

The provider is built on the modern ``google-genai`` SDK (``from google import genai``).
The legacy ``google.generativeai`` package is not a dependency and must not be
reintroduced here.
"""

import base64
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest import mock

import pytest
from google.genai import errors as genai_errors

from app.media_generation.image.errors import ImageGenerationError
from app.media_generation.image.gemini import GeminiImageProvider
from app.media_generation.image.provider import ImageGenerationRequest

pytestmark = pytest.mark.usefixtures("block_network")

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-payload"


def _build_response(
    *,
    image: bytes | None = PNG_BYTES,
    request_id: str | None = "gen-request-123",
) -> mock.MagicMock:
    """Build a fake google-genai models.generate_content response."""
    response = mock.MagicMock()
    response.output_image = mock.MagicMock() if image is not None else None
    if image is not None:
        response.output_image.data = image
    response.id = request_id
    return response


@contextmanager
def _gemini_client(
    **generate_content: Any,
) -> Iterator[tuple[GeminiImageProvider, mock.MagicMock]]:
    """Yield a provider whose entire google-genai client is mocked.

    Both ``genai.Client`` and ``genai.GenerateContentConfig`` are patched so no
    network traffic is possible. ``GenerateContentConfig`` is patched with
    ``create=True`` because ``google-genai`` 2.x only re-exports it from
    ``google.genai.types``, while the provider references the top-level name.
    Stubbing the symbol here keeps these tests focused on the provider's own
    response-mapping logic rather than on SDK symbol availability.

    Returns:
        Tuple of the provider under test and the patched ``GenerateContentConfig``.
    """
    with mock.patch("google.genai.Client"):
        with mock.patch("google.genai.GenerateContentConfig", create=True) as config_cls:
            provider = GeminiImageProvider(api_key="test_key")
            provider._client.models.generate_content.configure_mock(**generate_content)
            yield provider, config_cls


class TestGeminiImageProvider:
    """Tests for Gemini image generation provider adapter."""

    def test_init_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization without API key raises error."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with pytest.raises(ImageGenerationError, match="API key is required"):
            GeminiImageProvider()

    def test_init_with_api_key_param(self) -> None:
        """Test initialization with API key parameter."""
        provider = GeminiImageProvider(api_key="test_key")
        assert provider._api_key == "test_key"

    def test_init_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with environment variable."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key_from_env")

        provider = GeminiImageProvider()
        assert provider._api_key == "test_key_from_env"

    def test_init_without_sdk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization without the google-genai SDK raises a clear error.

        The provider imports ``from google import genai``. Setting the
        ``sys.modules`` entry to ``None`` makes that import fail, and dropping the
        already-cached ``google.genai`` attribute forces the import machinery to
        be consulted even when an earlier test imported the SDK.
        """
        monkeypatch.setitem(sys.modules, "google.genai", None)
        monkeypatch.delattr(sys.modules["google"], "genai", raising=False)

        with pytest.raises(ImageGenerationError, match="Google Gen AI SDK is not installed"):
            GeminiImageProvider(api_key="test_key")

    def test_init_builds_client_with_api_key(self) -> None:
        """Test that the Gen AI client is constructed with the configured API key."""
        with mock.patch("google.genai.Client") as client_cls:
            provider = GeminiImageProvider(api_key="test_key")

        client_cls.assert_called_once_with(api_key="test_key")
        assert provider._client is client_cls.return_value

    def test_generate_without_real_api_call(self) -> None:
        """Test generate method structure without real API calls.

        ``gemini-3.1-flash-image`` is the deliberate current default; it matches
        ``app/config/providers.yaml`` (``image.model``).
        """
        provider = GeminiImageProvider(api_key="test_key")
        assert provider._model == "gemini-3.1-flash-image"

    def test_init_with_custom_model(self) -> None:
        """Test that an explicit model overrides the default."""
        provider = GeminiImageProvider(api_key="test_key", model="gemini-custom-image")
        assert provider._model == "gemini-custom-image"

    def test_generate_returns_provider_neutral_result(self) -> None:
        """Test generate maps a Gemini response onto the provider-neutral contract."""
        with _gemini_client(return_value=_build_response()) as (provider, _):
            result = provider.generate(ImageGenerationRequest(prompt="a cinematic cityscape"))

        assert result.provider == "gemini"
        assert result.model == "gemini-3.1-flash-image"
        assert len(result.images) == 1

        image = result.images[0]
        assert image.content_type == "image/png"
        expected_uri = f"data:image/png;base64,{base64.b64encode(PNG_BYTES).decode('utf-8')}"
        assert image.uri == expected_uri
        assert result.metadata == {"request_id": "gen-request-123"}

    def test_generate_requests_image_response_modalities(self) -> None:
        """Test generate requests image modality for the configured model."""
        with _gemini_client(return_value=_build_response()) as (provider, config_cls):
            provider.generate(ImageGenerationRequest(prompt="a cinematic cityscape"))

        config_cls.assert_called_once_with(response_modalities=["Image", "Text"])

        _, kwargs = provider._client.models.generate_content.call_args
        assert kwargs["model"] == "gemini-3.1-flash-image"
        assert kwargs["contents"] == "a cinematic cityscape"
        assert kwargs["config"] is config_cls.return_value

    def test_generate_derives_dimensions_from_landscape_aspect_ratio(self) -> None:
        """Test that a landscape aspect ratio maps to landscape dimensions."""
        with _gemini_client(return_value=_build_response()) as (provider, _):
            result = provider.generate(
                ImageGenerationRequest(prompt="a wide shot", aspect_ratio="16:9")
            )

        assert (result.images[0].width, result.images[0].height) == (1080, 607)

    def test_generate_derives_dimensions_from_portrait_aspect_ratio(self) -> None:
        """Test that a portrait aspect ratio maps to portrait dimensions."""
        with _gemini_client(return_value=_build_response()) as (provider, _):
            result = provider.generate(
                ImageGenerationRequest(prompt="a vertical shot", aspect_ratio="9:16")
            )

        assert (result.images[0].width, result.images[0].height) == (1080, 1920)

    def test_generate_without_image_data(self) -> None:
        """Test generate raises when the model returns no image payload."""
        with _gemini_client(return_value=_build_response(image=None)) as (provider, _):
            with pytest.raises(ImageGenerationError, match="did not return image data"):
                provider.generate(ImageGenerationRequest(prompt="a cinematic cityscape"))

    def test_generate_wraps_authentication_error(self) -> None:
        """Test generate surfaces google-genai credential errors as ImageGenerationError."""
        auth_error = genai_errors.ClientError(
            403,
            {
                "error": {
                    "message": "API key not valid. Please pass a valid API key.",
                    "status": "INVALID_ARGUMENT",
                    "code": 400,
                }
            },
        )

        with _gemini_client(side_effect=auth_error) as (provider, _):
            with pytest.raises(ImageGenerationError, match="Gemini image generation failed") as exc:
                provider.generate(ImageGenerationRequest(prompt="a cinematic cityscape"))

        assert "API key not valid" in str(exc.value)
