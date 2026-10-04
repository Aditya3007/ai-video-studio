"""Tests for JSON2Video provider."""

import os

import pytest

from app.media_generation.video.errors import VideoGenerationError
from app.media_generation.video.json2video import JSON2VideoProvider

pytestmark = pytest.mark.usefixtures("block_network")


class TestJSON2VideoProvider:
    """Tests for JSON2Video provider adapter."""

    def test_init_without_api_key(self) -> None:
        """Test initialization without API key raises error."""
        os.environ.pop("JSON2VIDEO_API_KEY", None)

        with pytest.raises(VideoGenerationError, match="API key is required"):
            JSON2VideoProvider()

    def test_init_with_api_key_param(self) -> None:
        """Test initialization with API key parameter."""
        provider = JSON2VideoProvider(api_key="test_key")
        assert provider._api_key == "test_key"

    def test_init_with_env_var(self) -> None:
        """Test initialization with environment variable."""
        os.environ["JSON2VIDEO_API_KEY"] = "test_key_from_env"

        try:
            provider = JSON2VideoProvider()
            assert provider._api_key == "test_key_from_env"
        finally:
            os.environ.pop("JSON2VIDEO_API_KEY", None)

    def test_init_parameters(self) -> None:
        """Test initialization with custom parameters."""
        provider = JSON2VideoProvider(api_key="test_key", mode="composition")
        assert provider._mode == "composition"

    def test_generate_without_sdk(self) -> None:
        """Test generate method raises error without SDK."""
        provider = JSON2VideoProvider(api_key="test_key")

        from app.media_generation.video.provider import VideoGenerationRequest

        request = VideoGenerationRequest(prompt="Test video")

        with pytest.raises(VideoGenerationError, match="SDK integration is not yet implemented"):
            provider.generate(request)

    def test_composition_mode_distinction(self) -> None:
        """Test that JSON2Video is marked as composition mode."""
        provider = JSON2VideoProvider(api_key="test_key", mode="composition")
        assert provider._mode == "composition"
