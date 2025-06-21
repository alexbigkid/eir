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

# Store the response to check for errors
RESPONSE=$(curl -X PUT \
    -H "X-NuGet-ApiKey: $CHOCOLATEY_API_KEY" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@$NUPKG_FILE" \
    -w "\n%{http_code}" \
    "https://push.chocolatey.org/api/v2/package" 2>&1)

# Extract HTTP status code from response
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$RESPONSE" | head -n -1)

echo "📋 HTTP Status Code: $HTTP_CODE"

if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Chocolatey package uploaded successfully"
elif [ "$HTTP_CODE" = "403" ]; then
    echo "❌ Upload failed: 403 Forbidden - Invalid API key or insufficient permissions"
    echo "🔍 Response body:"
    echo "$RESPONSE_BODY"
    echo ""
    echo "💡 Troubleshooting steps:"
    echo "   1. Verify CHOCOLATEY_API_KEY is valid and not expired"
    echo "   2. Check if API key has push permissions"
    echo "   3. Ensure package name 'eir' is available or you own it"
    echo ""
    echo "⚠️ Chocolatey publish failed, but continuing pipeline..."
    exit 0
elif [ "$HTTP_CODE" = "409" ]; then
    echo "❌ Upload failed: 409 Conflict - Package version already exists"
    echo "🔍 Response body:"
    echo "$RESPONSE_BODY"
    echo "⚠️ Version conflict, but continuing pipeline..."
    exit 0
else
    echo "❌ Upload failed with HTTP code: $HTTP_CODE"
    echo "🔍 Response body:"
    echo "$RESPONSE_BODY"
    echo "⚠️ Chocolatey publish failed, but continuing pipeline..."
    exit 0
fi