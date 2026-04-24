from __future__ import annotations

from pathlib import Path
import re
import unittest


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = [WORKSPACE_ROOT / "README.md", WORKSPACE_ROOT / "CONTRIBUTING.md"] + sorted(
    WORKSPACE_ROOT.glob("docs/**/*.md")
)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class DocsReferenceDriftTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self) -> None:
        missing: list[str] = []
        for path in MARKDOWN_FILES:
            text = path.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK_RE.findall(text):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                clean = target.split("#", 1)[0].split("?", 1)[0]
                if not clean:
                    continue
                resolved = (path.parent / clean).resolve()
                if not resolved.exists():
                    missing.append(f"{path.relative_to(WORKSPACE_ROOT)} -> {target}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
