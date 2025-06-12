#!/bin/bash
# Package organization script
set -e

echo "📦 Organizing packages from artifacts..."

# Create packages directory and collect all package files
mkdir -p packages

# Find and copy package files from all artifacts
find ./artifacts -name "*.deb" -exec cp {} ./packages/ \; 2>/dev/null || true
find ./artifacts -name "*.nupkg" -exec cp {} ./packages/ \; 2>/dev/null || true
find ./artifacts -name "*.rb" -exec cp {} ./homebrew/ \; 2>/dev/null || true

# List what we found
echo "📋 Package inventory:"
echo "Packages directory:"
ls -la ./packages/ 2>/dev/null || echo "  (empty)"

echo "Homebrew directory:"
ls -la ./homebrew/ 2>/dev/null || echo "  (empty)"

# Count packages for summary
DEB_COUNT=$(find ./packages -name "*.deb" 2>/dev/null | wc -l)
NUPKG_COUNT=$(find ./packages -name "*.nupkg" 2>/dev/null | wc -l)

echo "📊 Summary:"
echo "  - Debian packages: $DEB_COUNT"
echo "  - Chocolatey packages: $NUPKG_COUNT"

if [ "$DEB_COUNT" -eq 0 ] && [ "$NUPKG_COUNT" -eq 0 ]; then
    echo "⚠️ Warning: No packages found in artifacts"
else
    echo "✅ Packages organized successfully"
fi