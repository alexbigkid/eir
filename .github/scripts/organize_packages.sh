#!/bin/bash
# Package organization script
set -e

echo "📦 Organizing packages from artifacts..."

# Debug: Show what artifacts we have
echo "🔍 Available artifacts:"
find ./artifacts -type d -name "*-*-*" | head -10

# Create packages directory and collect all package files
mkdir -p packages

# Find and copy package files from all artifacts
# Look for .deb files in Linux package artifacts
find ./artifacts -path "*/packages-linux-*/*.deb" -exec cp {} ./packages/ \; 2>/dev/null || true
# Fallback: look for .deb files directly in Linux artifacts
find ./artifacts -name "*-linux-*" -type d -exec find {} -name "*.deb" -exec cp {} ./packages/ \; 2>/dev/null || true

# Look for .nupkg files in Windows package artifacts  
find ./artifacts -path "*/packages-windows-*/*.nupkg" -exec cp {} ./packages/ \; 2>/dev/null || true
# Fallback: look for .nupkg files directly in Windows artifacts
find ./artifacts -name "*-windows-*" -type d -exec find {} -name "*.nupkg" -exec cp {} ./packages/ \; 2>/dev/null || true

# Look for .rb files in macOS package artifacts
mkdir -p ./homebrew
echo "🔍 Looking for .rb files in macOS artifacts..."
find ./artifacts -name "*-macos-*" -type d | while read dir; do
    echo "  Checking directory: $dir"
    find "$dir" -name "*.rb" | while read file; do
        echo "    Found .rb file: $file"
        cp "$file" ./homebrew/
    done
done
# Primary search pattern
find ./artifacts -path "*/packages-macos-*/*.rb" -exec cp {} ./homebrew/ \; 2>/dev/null || true

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