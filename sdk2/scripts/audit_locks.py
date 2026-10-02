"""Audit every locked registry version, including platform-specific variants."""

import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

for argument in sys.argv[1:]:
    lock = Path(argument)
    records = sorted(
        {
            (item["name"], item["version"])
            for item in tomllib.loads(lock.read_text())["package"]
            if "registry" in item.get("source", {})
        }
    )
    variants = {}
    for name, version in records:
        variants.setdefault(name, []).append(version)
    with tempfile.TemporaryDirectory() as directory:
        for index in range(max(map(len, variants.values()))):
            requirements = Path(directory) / f"requirements-{index}.txt"
            requirements.write_text(
                "".join(
                    f"{name}=={versions[index]}\n"
                    for name, versions in variants.items()
                    if index < len(versions)
                )
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip_audit",
                    "--strict",
                    "--disable-pip",
                    "--no-deps",
                    "-r",
                    str(requirements),
                ],
                check=True,
            )
    print(lock, len(records), "locked registry records audited", flush=True)
