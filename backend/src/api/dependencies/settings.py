"""Settings resolution for the request path.

`create_app` stores the Settings instance it was built with on application
state, and everything downstream reads it from there. Routes must not call
`get_settings()` directly: that returns the process-wide cached instance built
from the environment, so an application constructed with explicit settings
would run its middleware on one configuration and its routes on another. One
application, one Settings.
"""

from __future__ import annotations

from fastapi import Request

from src.core.config import Settings, get_settings

SETTINGS_STATE_KEY = "settings"


def get_request_settings(request: Request) -> Settings:
    configured = getattr(request.app.state, SETTINGS_STATE_KEY, None)
    if isinstance(configured, Settings):
        return configured
    return get_settings()
