#!/bin/bash
# Binary testing script
set -e

VERSION="$1"
ARCH_BIN_EXT="$2"

if [ -z "$VERSION" ] || [ -z "$ARCH_BIN_EXT" ]; then
    echo "❌ Error: VERSION and ARCH_BIN_EXT required"
    echo "Usage: $0 <version> <arch_bin_ext>"
    echo "Example: $0 0.1.19 linux-x86_64"
    exit 1
fi

BINARY_NAME="eir-$VERSION-$ARCH_BIN_EXT"
BINARY_PATH="./dist/$BINARY_NAME"

echo "🧪 Testing binary: $BINARY_NAME"

# Check if binary exists
if [ ! -f "$BINARY_PATH" ]; then
    echo "❌ Error: Binary not found: $BINARY_PATH"
    echo "Available files in dist/:"
    ls -la ./dist/ 2>/dev/null || echo "  (dist directory not found)"
    exit 1
fi

# Make binary executable (skip for .exe files)
if [[ "$BINARY_NAME" != *.exe ]]; then
    chmod +x "$BINARY_PATH"
fi

echo "✅ Binary found: $BINARY_NAME"

# Test version command
echo "🧪 Testing --version command..."
VERSION_OUTPUT=$("$BINARY_PATH" --version 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ Version test passed"
    echo "📄 Version output:"
    echo "$VERSION_OUTPUT"
else
    echo "❌ Version test failed"
    exit 1
fi

# Test help command  
echo "🧪 Testing --help command..."
HELP_OUTPUT=$("$BINARY_PATH" --help 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ Help test passed"
    echo "📄 Help output:"
    echo "$HELP_OUTPUT"
else
    echo "❌ Help test failed"
    exit 1
fi

# Test about command
echo "🧪 Testing --about command..."
ABOUT_OUTPUT=$("$BINARY_PATH" --about 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ About test passed"
    echo "📄 About output:"
    echo "$ABOUT_OUTPUT"
else
    echo "❌ About test failed"
    exit 1
fi

# Get binary size for reporting
BINARY_SIZE=$(du -h "$BINARY_PATH" | cut -f1)
echo "📊 Binary size: $BINARY_SIZE"

echo "🎉 All tests passed for $BINARY_NAME!"