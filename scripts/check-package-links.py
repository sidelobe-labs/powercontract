#!/usr/bin/env python3
"""Check links in the metadata that PyPI renders for the project page."""

import re
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def check_wheel(path: Path) -> list[str]:
    problems = []
    with ZipFile(path) as wheel:
        metadata_paths = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            return [f"{path}: expected one METADATA file, found {len(metadata_paths)}"]
        metadata = BytesParser(policy=policy.default).parsebytes(wheel.read(metadata_paths[0]))

    description = metadata.get_payload()
    for match in MARKDOWN_LINK.finditer(description):
        target = match.group(1).strip().split(" ", 1)[0]
        if not target.startswith(("https://", "http://", "mailto:", "#")):
            problems.append(f"{path}: relative README link {target!r} would resolve on pypi.org")

    project_urls = metadata.get_all("Project-URL", [])
    if not project_urls:
        problems.append(f"{path}: missing Project-URL metadata")
    for item in project_urls:
        label, separator, url = item.partition(",")
        if not separator or not url.strip().startswith("https://"):
            problems.append(f"{path}: invalid project URL {item!r}")

    return problems


def main() -> int:
    sample = "[local](docs/getting-started.md) [web](https://example.com)"
    if MARKDOWN_LINK.findall(sample) != ["docs/getting-started.md", "https://example.com"]:
        print("Markdown link parser failed its self-check", file=sys.stderr)
        return 2

    if len(sys.argv) < 2:
        print("Usage: check-package-links.py dist/*.whl", file=sys.stderr)
        return 2

    problems = [issue for arg in sys.argv[1:] for issue in check_wheel(Path(arg))]
    for issue in problems:
        print(issue, file=sys.stderr)
    if problems:
        return 1

    print("PyPI description and project URLs: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
