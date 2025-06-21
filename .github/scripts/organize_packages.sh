#!/bin/bash
# Package organization script
set -e

echo "📦 Organizing packages from artifacts..."

# Debug: Show artifact structure
echo "Available artifacts and their contents:"
find ./artifacts -type f -name "*.rb" | head -5

# Create packages directory and collect all package files
mkdir -p packages

# Find and copy package files from all artifacts
# Look for .deb files in Linux package artifacts
find ./artifacts -path "*/packages-linux-*/*.deb" -exec cp {} ./packages/ \; 2>/dev/null || true
# Fallback: look for .deb files directly in Linux artifacts
find ./artifacts -name "*-linux-*" -type d -exec find {} -name "*.deb" -exec cp {} ./packages/ \; 2>/dev/null || true

# Look for .nupkg files in Windows package artifacts
echo "🔍 Searching for Windows .nupkg files..."
find ./artifacts -path "*/packages-windows-*/*.nupkg" -print -exec cp {} ./packages/ \; 2>/dev/null || true
# Fallback: look for .nupkg files directly in Windows artifacts
find ./artifacts -name "*-windows-*" -type d | while IFS= read -r dir; do
    echo "  Checking Windows artifact directory: $dir"
    if find "$dir" -name "*.nupkg" -print -exec cp {} ./packages/ \; 2>/dev/null | grep -q ".nupkg"; then
        echo "  Found and copied .nupkg file from $dir"
    fi
done

# Look for .rb files in macOS package artifacts
mkdir -p ./homebrew
echo "Looking for homebrew formula files..."
find ./artifacts -path "*/packages-macos-*/*.rb" -exec cp {} ./homebrew/ \; 2>/dev/null || true
# Fallback: look for .rb files directly in macOS artifacts
find ./artifacts -name "*-macos-*" -type d | while IFS= read -r dir; do
    if find "$dir" -name "*.rb" -print -exec cp {} ./homebrew/ \; | grep -q ".rb"; then
        echo "Found and copied .rb file from $dir"
    fi
done

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