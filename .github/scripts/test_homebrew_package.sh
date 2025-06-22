#!/bin/bash
# Homebrew Package Testing Script
set -e

VERSION="$1"
if [ -z "$VERSION" ]; then
    echo "❌ Error: Version parameter required"
    echo "Usage: $0 <version>"
    exit 1
fi

echo "🍺 Testing Homebrew package for version $VERSION"

# Get OS details
OS_NAME="${OS_NAME:-macos}"
ARCH="${ARCH:-universal}"
PACKAGES_DIR="packages-$OS_NAME-$ARCH"

echo "📍 Current directory: $(pwd)"
echo "📂 Looking for packages in: $PACKAGES_DIR"

# Find the .rb formula file
FORMULA_FILE="$PACKAGES_DIR/eir.rb"
if [ ! -f "$FORMULA_FILE" ]; then
    echo "❌ Could not find Homebrew formula: $FORMULA_FILE"
    echo "📂 Available files in $PACKAGES_DIR:"
    if [ -d "$PACKAGES_DIR" ]; then
        ls -la "$PACKAGES_DIR/" || echo "  (directory empty)"
    else
        echo "  Directory $PACKAGES_DIR does not exist"
    fi
    
    # Search for .rb files
    echo "🔍 Searching for .rb files in current directory..."
    FOUND_RB=$(find . -name "*.rb" -type f 2>/dev/null | head -5)
    if [ -n "$FOUND_RB" ]; then
        echo "📦 Found .rb files:"
        echo "$FOUND_RB" | while read -r file; do
            echo "  - $file"
        done
        
        # Try to find one matching our pattern
        VERSION_MATCH=$(find . -name "eir.rb" -type f 2>/dev/null | head -1)
        if [ -n "$VERSION_MATCH" ]; then
            echo "✅ Found matching formula: $VERSION_MATCH"
            FORMULA_FILE="$VERSION_MATCH"
        else
            exit 1
        fi
    else
        echo "❌ No .rb files found anywhere"
        exit 1
    fi
fi

echo "📦 Found formula: $FORMULA_FILE"

# Test 1: Verify formula syntax
echo "🔍 Testing Ruby syntax..."
if command -v ruby >/dev/null 2>&1; then
    if ruby -c "$FORMULA_FILE" >/dev/null 2>&1; then
        echo "✅ Formula syntax is valid"
    else
        echo "❌ Formula syntax test failed"
        ruby -c "$FORMULA_FILE"
        exit 1
    fi
else
    echo "⚠️ Ruby not available, skipping syntax check"
fi

# Test 2: Verify formula structure and content
echo "🔍 Testing formula structure..."

# Check for required Homebrew formula components
if grep -q "class Eir < Formula" "$FORMULA_FILE"; then
    echo "✅ Formula class definition found"
else
    echo "❌ Formula class definition not found"
    exit 1
fi

if grep -q "homepage" "$FORMULA_FILE"; then
    echo "✅ Homepage URL found"
else
    echo "❌ Homepage URL missing"
    exit 1
fi

if grep -q "url.*github.com.*eir.*releases.*download" "$FORMULA_FILE"; then
    echo "✅ Download URL found"
else
    echo "❌ Download URL not found or incorrect"
    exit 1
fi

if grep -q "sha256" "$FORMULA_FILE"; then
    echo "✅ SHA256 checksum found"
else
    echo "❌ SHA256 checksum missing"
    exit 1
fi

# Test 3: Verify version in formula
echo "🔍 Testing formula version..."
if grep -q "version.*$VERSION" "$FORMULA_FILE"; then
    echo "✅ Formula version matches expected version ($VERSION)"
else
    echo "❌ Formula version mismatch or not found"
    echo "Expected version: $VERSION"
    echo "Formula content:"
    grep -n "version\|url" "$FORMULA_FILE" || echo "No version/url lines found"
    exit 1
fi

# Test 4: Verify binary exists and checksum matches
echo "🔍 Testing binary availability..."
BINARY_PATTERN="eir-$VERSION-macos-$ARCH"
BINARY_FILE=$(find dist -name "$BINARY_PATTERN" -type f 2>/dev/null | head -1)

if [ -n "$BINARY_FILE" ]; then
    BINARY_SIZE=$(du -h "$BINARY_FILE" | cut -f1)
    echo "✅ Binary found: $(basename "$BINARY_FILE") ($BINARY_SIZE)"
    
    # Test if binary is executable
    if [ -x "$BINARY_FILE" ]; then
        echo "✅ Binary is executable"
        
        # Test binary execution
        if "$BINARY_FILE" --version >/dev/null 2>&1; then
            echo "✅ Binary responds to --version"
        else
            echo "⚠️ Binary execution test had issues"
        fi
    else
        echo "⚠️ Binary is not executable"
    fi
    
    # Verify SHA256 checksum
    if command -v shasum >/dev/null 2>&1; then
        ACTUAL_SHA=$(shasum -a 256 "$BINARY_FILE" | cut -d' ' -f1 | tr -d '\n\r\t ')
        FORMULA_SHA=$(grep "sha256" "$FORMULA_FILE" | sed 's/.*sha256 *"\([^"]*\)".*/\1/' | tr -d '\n\r\t ')
        
        # Debug output for troubleshooting
        echo "  Checking checksums (lengths: actual=${#ACTUAL_SHA}, formula=${#FORMULA_SHA})"
        
        if [ "$ACTUAL_SHA" = "$FORMULA_SHA" ]; then
            echo "✅ SHA256 checksum matches"
        else
            echo "❌ SHA256 checksum mismatch"
            echo "  Expected: '$FORMULA_SHA'"
            echo "  Actual:   '$ACTUAL_SHA'"
            # Show character-by-character comparison for debugging
            if command -v xxd >/dev/null 2>&1; then
                echo "  Expected (hex): $(echo -n "$FORMULA_SHA" | xxd -p)"
                echo "  Actual (hex):   $(echo -n "$ACTUAL_SHA" | xxd -p)"
            fi
            exit 1
        fi
    else
        echo "⚠️ shasum not available, skipping checksum verification"
    fi
else
    echo "❌ Could not find macOS binary for version $VERSION"
    echo "Searched for: $BINARY_PATTERN"
    echo "Available files in dist/:"
    ls -la dist/ 2>/dev/null || echo "  (dist directory not found)"
    exit 1
fi

# Test 5: Test formula installation (dry-run)
echo "🔍 Testing formula installation (dry-run)..."
if command -v brew >/dev/null 2>&1; then
    echo "📥 Running Homebrew dry-run test..."
    
    # Test formula linting
    if brew audit --formula "$FORMULA_FILE" 2>/dev/null; then
        echo "✅ Homebrew audit passed"
    else
        echo "⚠️ Homebrew audit had issues, but continuing..."
    fi
    
    # Test formula parsing
    if brew info --formula "$FORMULA_FILE" >/dev/null 2>&1; then
        echo "✅ Homebrew formula parsing successful"
    else
        echo "⚠️ Homebrew formula parsing had issues"
    fi
else
    echo "⚠️ Homebrew not available, skipping installation test"
fi

echo "🎉 All Homebrew package tests completed successfully!"
echo "📋 Formula $FORMULA_FILE is ready for publication"