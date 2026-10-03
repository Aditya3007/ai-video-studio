"""Main application entry point."""

from app.core.config import get_settings
from app.factory import create_app

# Validate configuration at startup. This will raise a clear error and prevent
# the application from launching if required configuration is malformed.
_ = get_settings()

app = create_app()
