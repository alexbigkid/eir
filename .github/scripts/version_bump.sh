#!/bin/bash
# Version bumping script for GitHub Actions
set -e

RELEASE_TYPE="$1"

if [ -z "$RELEASE_TYPE" ]; then
    echo "❌ Error: Release type required (patch|minor|major)"
    exit 1
fi

echo "🔖 Processing $RELEASE_TYPE version bump..."

# Read current version from pyproject.toml
current_version=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "Current version: $current_version"

# Validate current version format
if [[ ! "$current_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Error: Invalid version format: $current_version"
    exit 1
fi

# Parse version components
IFS='.' read -r major minor patch <<< "$current_version"

# Determine new version based on tag
case $RELEASE_TYPE in
    "major")
        new_major=$((major + 1))
        new_minor=0
        new_patch=0
        ;;
    "minor")
        new_major=$major
        new_minor=$((minor + 1))
        new_patch=0
        ;;
    "patch")
        new_major=$major
        new_minor=$minor
        new_patch=$((patch + 1))
        ;;
    *)
        echo "❌ Error: Invalid release tag: $RELEASE_TYPE"
        exit 1
        ;;
esac

new_version="${new_major}.${new_minor}.${new_patch}"

echo "New version: $new_version"
echo "Version tag: v$new_version"

# Validate new version format
if [[ ! "$new_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Error: Generated invalid version: $new_version"
    exit 1
fi

# Update pyproject.toml
sed -i "s/^version = \".*\"/version = \"$new_version\"/" pyproject.toml

# Set GitHub Actions outputs if running in CI
if [ -n "$GITHUB_OUTPUT" ]; then
    echo "new_version=$new_version" >> "$GITHUB_OUTPUT"
fi

echo "✅ Version bumped to $new_version"