#!/usr/bin/env python3
"""Compute next Evil RLBot release and select known-good packaged runtimes."""
from __future__ import annotations

import json
import os
import re
import subprocess

RELEASE_PATTERN = re.compile(r"^v(\d{4})\.(\d{1,2})\.(\d{1,2})\.(\d+)$")


def fetch_releases() -> list[dict]:
    repo = os.environ["GITHUB_REPOSITORY"]
    raw = subprocess.check_output(
        ["gh", "api", f"repos/{repo}/releases?per_page=100"],
        text=True, encoding="utf-8",
    )
    return [r for r in json.loads(raw) if not r.get("draft")]


def select_assets(releases: list[dict]) -> dict[str, str]:
    versions = []
    for release in releases:
        match = RELEASE_PATTERN.fullmatch(release["tag_name"])
        if match:
            versions.append((tuple(int(p) for p in match.groups()), release))
    if not versions:
        raise SystemExit("No previous versioned release; bootstrap a runtime release first.")
    versions.sort(reverse=True, key=lambda pair: pair[0])
    version = versions[0][0]
    next_version = (*version[:3], version[3] + 1)
    output = {
        "version": ".".join(str(part) for part in next_version),
        "tag": "v" + ".".join(str(part) for part in next_version),
    }
    patterns = {
        "windows": lambda name: name.lower().endswith("-portable.zip") and "windows" in name.lower(),
        "linux": lambda name: name.endswith(".AppImage") and "x86_64" in name,
    }
    for platform, matches in patterns.items():
        for _, release in versions:
            found = next((a for a in release.get("assets", []) if matches(a["name"])), None)
            if found is not None:
                output[f"{platform}_tag"] = release["tag_name"]
                output[f"{platform}_asset"] = found["name"]
                break
        if f"{platform}_asset" not in output:
            raise SystemExit(f"No existing {platform} release artifact to build upon.")
    return output


if __name__ == "__main__":
    result = select_assets(fetch_releases())
    for key, value in result.items():
        print(f"{key}={value}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            for key, value in result.items():
                output.write(f"{key}={value}\n")
