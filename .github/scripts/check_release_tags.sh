#!/bin/bash
# Release tag checking script
set -e

echo "🔍 Checking for release tags..."

# Check if there are any patch/minor/major tags
if git tag -l | grep -E '^(patch|minor|major)$' > /dev/null; then
    latest_tag=$(git tag -l | grep -E '^(patch|minor|major)$' | tail -1)
    echo "✅ Found release tag: $latest_tag"
    
    # Verify tag points to the latest commit
    tag_commit=$(git rev-list -n 1 "$latest_tag")
    main_commit=$(git rev-parse HEAD)
    
    if [ "$tag_commit" != "$main_commit" ]; then
        echo "❌ Error: Tag must point to the latest commit on main branch"
        echo "Tag commit: $tag_commit"
        echo "Main commit: $main_commit"
        exit 1
    fi
    
    echo "✅ Confirmed: Tag points to latest main branch commit"
    
    # Set GitHub Actions outputs if running in CI
    if [ -n "$GITHUB_OUTPUT" ]; then
        echo "should_release=true" >> "$GITHUB_OUTPUT"
        echo "release_type=$latest_tag" >> "$GITHUB_OUTPUT"
    fi
    
    echo "🚀 Release type: $latest_tag"
    echo "✅ Ready to proceed with release"
else
    echo "⚠️ No release tags found, skipping release"
    
    # Set GitHub Actions outputs if running in CI
    if [ -n "$GITHUB_OUTPUT" ]; then
        echo "should_release=false" >> "$GITHUB_OUTPUT"
    fi
    
    exit 0
fi