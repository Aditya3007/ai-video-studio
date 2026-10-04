#!/usr/bin/env python3
"""
Real Provider Smoke Test

This script performs minimal connectivity validation for configured real providers.
It requires explicit user intent and will NOT run automatically during pytest or CI.

Usage:
    python scripts/smoke_test_real_providers.py [--profile PROFILE]

Warning:
    This script may incur costs if you have configured paid API providers.
    Do not run this in CI/CD pipelines without explicit authorization.
"""

import argparse
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.config.loader import load_provider_config_for_profile  # noqa: E402
from app.media_generation.image.factory import (  # noqa: E402
    ImageGenerationProviderFactory,
)
from app.media_generation.tts.factory import TTSProviderFactory  # noqa: E402
from app.media_generation.video.factory import (  # noqa: E402
    VideoGenerationProviderFactory,
)
from app.story_intelligence.llm.factory import LLMProviderFactory  # noqa: E402


def check_api_keys() -> dict[str, bool]:
    """Check which API keys are present."""
    keys = {
        "GROQ_API_KEY": bool(os.getenv("GROQ_API_KEY")),
        "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
        "SARVAM_API_KEY": bool(os.getenv("SARVAM_API_KEY")),
        "JSON2VIDEO_API_KEY": bool(os.getenv("JSON2VIDEO_API_KEY")),
        "KLING_API_KEY": bool(os.getenv("KLING_API_KEY")),
    }
    return keys


def print_api_key_status(keys: dict[str, bool]) -> None:
    """Print API key presence status."""
    print("\n" + "=" * 60)
    print("API Key Status")
    print("=" * 60)
    for key, present in keys.items():
        status = "✓ PRESENT" if present else "✗ MISSING"
        print(f"{key:30s} {status}")
    print("=" * 60 + "\n")


def test_llm_provider(provider_id: str) -> bool:
    """Test LLM provider instantiation."""
    print(f"Testing LLM provider: {provider_id}")
    try:
        # Test through factory
        from app.core.config import Settings

        settings = Settings(llm_provider=provider_id)
        _ = LLMProviderFactory.create(settings)
        print(f"  ✓ {provider_id} provider instantiated successfully")
        return True
    except Exception as e:
        print(f"  ✗ Failed to instantiate {provider_id}: {e}")
        return False


def test_image_provider(provider_id: str) -> bool:
    """Test image provider instantiation."""
    print(f"Testing Image provider: {provider_id}")
    try:
        from app.core.config import Settings

        settings = Settings(image_generation_provider=provider_id)
        _ = ImageGenerationProviderFactory.create(settings)
        print(f"  ✓ {provider_id} provider instantiated successfully")
        return True
    except Exception as e:
        print(f"  ✗ Failed to instantiate {provider_id}: {e}")
        return False


def test_tts_provider(provider_id: str) -> bool:
    """Test TTS provider instantiation."""
    print(f"Testing TTS provider: {provider_id}")
    try:
        from app.core.config import Settings

        settings = Settings(tts_provider=provider_id)
        _ = TTSProviderFactory.create(settings)
        print(f"  ✓ {provider_id} provider instantiated successfully")
        return True
    except Exception as e:
        print(f"  ✗ Failed to instantiate {provider_id}: {e}")
        return False


def test_video_provider(provider_id: str) -> bool:
    """Test video provider instantiation."""
    print(f"Testing Video provider: {provider_id}")
    try:
        from app.core.config import Settings

        settings = Settings(video_generation_provider=provider_id)
        _ = VideoGenerationProviderFactory.create(settings)
        print(f"  ✓ {provider_id} provider instantiated successfully")
        return True
    except Exception as e:
        print(f"  ✗ Failed to instantiate {provider_id}: {e}")
        return False


def main() -> int:
    """Main smoke test entry point."""
    parser = argparse.ArgumentParser(
        description="Smoke test real provider configuration and instantiation"
    )
    parser.add_argument(
        "--profile",
        default="real_e2e",
        help="Provider configuration profile to test (default: real_e2e)",
    )
    parser.add_argument(
        "--skip-api-key-check",
        action="store_true",
        help="Skip API key presence check",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Real Provider Smoke Test")
    print("=" * 60)
    print(f"Profile: {args.profile}")
    print()
    print("WARNING: This test may incur costs if you have configured paid API providers.")
    print("Do not run this in CI/CD pipelines without explicit authorization.")
    print()

    # Check API keys
    if not args.skip_api_key_check:
        keys = check_api_keys()
        print_api_key_status(keys)

        missing_keys = [k for k, v in keys.items() if not v]
        if missing_keys:
            print(f"⚠ Missing API keys: {', '.join(missing_keys)}")
            print("  Some provider tests may fail.")
            print()

    # Load profile configuration
    try:
        config = load_provider_config_for_profile(args.profile)
        print(f"✓ Loaded profile configuration: {args.profile}")
        print()
    except FileNotFoundError as e:
        print(f"✗ Failed to load profile: {e}")
        return 1
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        return 1

    # Test providers
    results = []

    print("=" * 60)
    print("Provider Instantiation Tests")
    print("=" * 60)
    print()

    # LLM
    if config.llm.provider != "fake":
        results.append(("LLM", test_llm_provider(config.llm.provider)))
    else:
        print("Skipping LLM test (fake provider)")

    # Image
    if config.image.provider != "fake":
        results.append(("Image", test_image_provider(config.image.provider)))
    else:
        print("Skipping Image test (fake provider)")

    # TTS
    if config.tts.provider != "fake":
        results.append(("TTS", test_tts_provider(config.tts.provider)))
    else:
        print("Skipping TTS test (fake provider)")

    # Video
    if config.video.provider != "fake":
        results.append(("Video", test_video_provider(config.video.provider)))
    else:
        print("Skipping Video test (fake provider)")

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for category, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{category:10s} {status}")

    print()
    print(f"Results: {passed}/{total} passed")

    if passed == total:
        print("✓ All provider instantiation tests passed")
        return 0
    else:
        print("✗ Some provider tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
