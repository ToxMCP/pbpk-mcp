"""Global test fixtures and environment setup."""

from __future__ import annotations

import os


# Ensure development secret is available for tests that rely on default config.
os.environ.setdefault("AUTH_DEV_SECRET", "test-suite-secret")
os.environ.setdefault("AUTH_ALLOW_ANONYMOUS", "1")
