#!/usr/bin/env python3
"""Version bumping script for GitHub Actions - Cross-platform Python implementation."""

import os
import re
import sys
from pathlib import Path


def main():
    """Main version bump logic."""
    if len(sys.argv) != 2:
        print("❌ Error: Release type required (patch|minor|major)")
        sys.exit(1)

    release_type = sys.argv[1]

    print(f"🔖 Processing {release_type} version bump...")

    # Find pyproject.toml file
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("❌ Error: pyproject.toml not found")
        sys.exit(1)

    # Read current version from pyproject.toml
    content = pyproject_path.read_text(encoding="utf-8")
    version_match = re.search(r'^version = "([^"]+)"', content, re.MULTILINE)

    if not version_match:
        print("❌ Error: Version not found in pyproject.toml")
        sys.exit(1)

    current_version = version_match.group(1)
    print(f"Current version: {current_version}")

    # Validate current version format
    if not re.match(r"^\d+\.\d+\.\d+$", current_version):
        print(f"❌ Error: Invalid version format: {current_version}")
        sys.exit(1)

    # Parse version components
    major, minor, patch = map(int, current_version.split("."))

    # Determine new version based on release type
    if release_type == "major":
        new_major = major + 1
        new_minor = 0
        new_patch = 0
    elif release_type == "minor":
        new_major = major
        new_minor = minor + 1
        new_patch = 0
    elif release_type == "patch":
        new_major = major
        new_minor = minor
        new_patch = patch + 1
    else:
        print(f"❌ Error: Invalid release tag: {release_type}")
        sys.exit(1)

    new_version = f"{new_major}.{new_minor}.{new_patch}"

    print(f"New version: {new_version}")
    print(f"Version tag: v{new_version}")

    # Validate new version format
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print(f"❌ Error: Generated invalid version: {new_version}")
        sys.exit(1)

    # Update pyproject.toml
    new_content = re.sub(
        r'^version = "[^"]+"', f'version = "{new_version}"', content, flags=re.MULTILINE
    )

    pyproject_path.write_text(new_content, encoding="utf-8")

    # Set GitHub Actions outputs if running in CI
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"new_version={new_version}\n")

    print(f"✅ Version bumped to {new_version}")


if __name__ == "__main__":
    main()
