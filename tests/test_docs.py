from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_local_documentation_links_resolve():
    broken: list[str] = []

    for document in MARKDOWN_FILES:
        text = document.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            target = target.strip()
            if (
                not target
                or target.startswith("#")
                or "://" in target
                or target.startswith("mailto:")
            ):
                continue

            path_part = target.split("#", 1)[0]
            if not path_part:
                continue

            resolved = (document.parent / path_part).resolve()
            if not resolved.exists():
                broken.append(
                    f"{document.relative_to(ROOT)} -> {target}"
                )

    assert not broken, "broken documentation links:\n" + "\n".join(broken)
