#!/bin/bash
# Chocolatey publishing script
set -e

VERSION="$1"
CHOCOLATEY_API_KEY="${CHOCOLATEY_API_KEY:-}"

echo "🍫 Publishing to Chocolatey for version $VERSION..."

# Check if Chocolatey API key is available
if [ -z "$CHOCOLATEY_API_KEY" ]; then
    echo "⚠️ CHOCOLATEY_API_KEY not set, skipping Chocolatey upload"
    exit 0
fi

# Debug: Show what packages are available
echo "🔍 Debugging package organization..."
echo "Current directory contents:"
ls -la ./ || true
echo "Packages directory contents:"
ls -la packages/ 2>/dev/null || echo "  (packages directory not found)"
echo "Artifacts directory contents:"
find ./artifacts -name "*.nupkg" 2>/dev/null || echo "  (no .nupkg files found in artifacts)"

# Find Chocolatey package
NUPKG_FILE=$(find packages/ -name "*.nupkg" | head -1)
if [ -z "$NUPKG_FILE" ]; then
    echo "⚠️ No Chocolatey package found to upload"
    echo "🔍 Searching in all directories for .nupkg files..."
    find . -name "*.nupkg" 2>/dev/null || echo "  (no .nupkg files found anywhere)"
    exit 0
fi

echo "📦 Found package: $NUPKG_FILE"

# Upload package directly via Chocolatey API
echo "🚀 Uploading to Chocolatey..."

if curl -X PUT \
    -H "X-NuGet-ApiKey: $CHOCOLATEY_API_KEY" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@$NUPKG_FILE" \
    "https://push.chocolatey.org/api/v2/package"; then
    echo "✅ Chocolatey package uploaded successfully"
else
    echo "❌ Failed to upload Chocolatey package"
    exit 1
fi