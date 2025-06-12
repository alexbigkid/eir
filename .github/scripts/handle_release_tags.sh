#!/bin/bash
# Release tag handling script
set -e

RUFF_SUCCESS="$1"
BUILD_SUCCESS="$2"
BRANCH_NAME="$3"

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

# Also clean up any existing release tags to avoid conflicts
EXISTING_RELEASE_TAGS=$(git tag -l | grep -E '^(patch|minor|major)$' || true)
if [ -n "$EXISTING_RELEASE_TAGS" ]; then
    echo "🧹 Found existing release tags: $EXISTING_RELEASE_TAGS"
    for tag in $EXISTING_RELEASE_TAGS; do
        echo "Deleting existing release tag: $tag"
        git push --delete origin "$tag" 2>/dev/null || true
        git tag -d "$tag" 2>/dev/null || true
    done
fi

# Check if all previous jobs succeeded
echo "📊 Job results:"
echo "  - Ruff: $RUFF_SUCCESS"  
echo "  - Build: $BUILD_SUCCESS"

if [ "$RUFF_SUCCESS" = "success" ] && [ "$BUILD_SUCCESS" = "success" ]; then
    # Check if current commit is on main branch (handles both branch pushes and tag pushes)
    CURRENT_COMMIT=$(git rev-parse HEAD)
    MAIN_COMMIT=$(git rev-parse origin/main 2>/dev/null || git rev-parse main 2>/dev/null || echo "")
    
    if [ "$CURRENT_COMMIT" = "$MAIN_COMMIT" ] || [ "$BRANCH_NAME" = "main" ]; then
        # Extract the release type from the rel-* tag
        RELEASE_TAG=$(echo "$REL_TAGS" | head -1 | sed 's/^rel-//')
        echo "✅ All tests passed on main branch! Creating release tag: $RELEASE_TAG"
        
        # Delete local tag if it exists, then create new one
        git tag -d "$RELEASE_TAG" 2>/dev/null || true
        git tag "$RELEASE_TAG"
        git push origin "$RELEASE_TAG" --force
        echo "🚀 Release pipeline will be triggered with tag: $RELEASE_TAG"
    else
        echo "✅ All tests passed on branch/ref '$BRANCH_NAME', but release tags are only created on main branch"
        echo "   Current commit: $CURRENT_COMMIT"
        echo "   Main commit: $MAIN_COMMIT"
    fi
else
    echo "❌ Tests failed, no release tag created"
    echo "   Ruff result: $RUFF_SUCCESS"
    echo "   Build result: $BUILD_SUCCESS"
    echo "   Branch: $BRANCH_NAME"
fi