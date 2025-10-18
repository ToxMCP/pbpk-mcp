"""Basic sanity tests for project scaffolding."""

from mcp_bridge import __version__


def test_version_is_semver_like() -> None:
    """Ensure the package exposes a version string."""
    assert __version__
    assert __version__[0].isdigit()
