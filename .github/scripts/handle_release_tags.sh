#!/bin/bash
# Release tag handling script
set -e

RUFF_SUCCESS="$1"
BUILD_SUCCESS="$2"

echo "🏷️ Handling release tags..."

# Configure git
git config --local user.email "action@github.com"
git config --local user.name "GitHub Action"

# Always clean up rel-* tags first
REL_TAGS=$(git tag -l | grep -E '^rel-(patch|minor|major)$' || true)
if [ -n "$REL_TAGS" ]; then
    echo "🧹 Found release candidate tags: $REL_TAGS"
    for tag in $REL_TAGS; do
        echo "Deleting tag: $tag"
        git push --delete origin "$tag" 2>/dev/null || true
    done
else
    echo "ℹ️ No release candidate tags found"
    exit 0
fi

# Check if all previous jobs succeeded
echo "📊 Job results:"
echo "  - Ruff: $RUFF_SUCCESS"  
echo "  - Build: $BUILD_SUCCESS"

if [ "$RUFF_SUCCESS" = "success" ] && [ "$BUILD_SUCCESS" = "success" ]; then
    # Extract the release type from the rel-* tag
    RELEASE_TAG=$(echo "$REL_TAGS" | head -1 | sed 's/^rel-//')
    echo "✅ All tests passed! Creating release tag: $RELEASE_TAG"
    
    git tag "$RELEASE_TAG"
    git push origin "$RELEASE_TAG"
    echo "🚀 Release pipeline will be triggered with tag: $RELEASE_TAG"
else
    echo "❌ Tests failed, no release tag created"
    echo "   Ruff result: $RUFF_SUCCESS"
    echo "   Build result: $BUILD_SUCCESS"
fi