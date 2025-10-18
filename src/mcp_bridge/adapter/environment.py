"""Utilities for detecting the local R/ospsuite environment."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..logging import get_logger
from .interface import AdapterConfig

logger = get_logger(__name__)


@dataclass
class REnvironmentStatus:
    available: bool
    r_path: str | None
    ospsuite_libs: str | None
    r_version: str | None
    ospsuite_available: bool
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "rPath": self.r_path,
            "ospsuiteLibs": self.ospsuite_libs,
            "rVersion": self.r_version,
            "ospsuiteAvailable": self.ospsuite_available,
            "issues": self.issues,
        }


def detect_environment(config: AdapterConfig) -> REnvironmentStatus:
    issues: list[str] = []

    r_path = _resolve_r_path(config)
    ospsuite_libs = _resolve_ospsuite_libs(config)
    ospsuite_available = bool(ospsuite_libs and os.path.exists(ospsuite_libs))
    if ospsuite_libs and not ospsuite_available:
        issues.append(f"ospsuite libs path not found: {ospsuite_libs}")

    r_version: str | None = None
    if r_path:
        r_version = _probe_r_version(r_path, config.default_timeout_seconds, issues)
    else:
        issues.append("R binary not found on PATH or configured via R_PATH/r_path")

    available = bool(r_path and ospsuite_available)
    status = REnvironmentStatus(
        available=available,
        r_path=r_path,
        ospsuite_libs=ospsuite_libs,
        r_version=r_version,
        ospsuite_available=ospsuite_available,
        issues=issues,
    )

    if issues:
        logger.warning("adapter.environment.issues", issues=issues)
    else:
        logger.info("adapter.environment.ok", rPath=r_path, rVersion=r_version)

    return status


def _resolve_r_path(config: AdapterConfig) -> str | None:
    candidates: Sequence[str | None] = (
        config.r_path,
        os.getenv("R_PATH"),
        os.getenv("R_HOME"),
    )
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if not resolved and os.path.isfile(candidate):
            resolved = candidate
        if resolved:
            return resolved

    return shutil.which("R")


def _resolve_ospsuite_libs(config: AdapterConfig) -> str | None:
    return config.ospsuite_libs or os.getenv("OSPSUITE_LIBS") or os.getenv("R_LIBS")


def _probe_r_version(r_path: str, timeout: float, issues: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            [r_path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        issues.append(f"Failed to execute R binary: {exc}")
        return None

    output = proc.stdout or proc.stderr
    if proc.returncode != 0:
        issues.append(f"R --version exited with {proc.returncode}")
        return None

    first_line = (output or "").splitlines()[0] if output else None
    return first_line
