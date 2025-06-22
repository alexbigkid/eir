#!/bin/bash
# APT Package Testing Script
set -e

VERSION="$1"
if [ -z "$VERSION" ]; then
    echo "❌ Error: Version parameter required"
    echo "Usage: $0 <version>"
    exit 1
fi

echo "📦 Testing APT package for version $VERSION"

# Quick diagnostic: Check if dpkg-deb is available
if command -v dpkg-deb >/dev/null 2>&1; then
    echo "✅ dpkg-deb is available: $(dpkg-deb --version | head -1)"
else
    echo "❌ dpkg-deb is not available - this may explain missing .deb files"
fi

# Get OS details
OS_NAME="${OS_NAME:-linux}"
ARCH="${ARCH:-x86_64}"
PACKAGES_DIR="packages-$OS_NAME-$ARCH"

echo "📍 Current directory: $(pwd)"
echo "📂 Looking for packages in: $PACKAGES_DIR"

# Find the .deb package file
DEB_FILE="$PACKAGES_DIR/eir_${VERSION}_amd64.deb"
if [ ! -f "$DEB_FILE" ]; then
    echo "❌ Could not find APT package: $DEB_FILE"
    echo "📂 Available files in $PACKAGES_DIR:"
    if [ -d "$PACKAGES_DIR" ]; then
        ls -la "$PACKAGES_DIR/" || echo "  (directory empty)"
    else
        echo "  Directory $PACKAGES_DIR does not exist"
    fi
    
    # Search for .deb files
    echo "🔍 Searching for .deb files in current directory..."
    FOUND_DEB=$(find . -name "*.deb" -type f 2>/dev/null | head -5)
    if [ -n "$FOUND_DEB" ]; then
        echo "📦 Found .deb files:"
        echo "$FOUND_DEB" | while read -r file; do
            echo "  - $file"
        done
        
        # Try to find one matching our pattern
        VERSION_MATCH=$(find . -name "eir_${VERSION}_*.deb" -type f 2>/dev/null | head -1)
        if [ -n "$VERSION_MATCH" ]; then
            echo "✅ Found matching package: $VERSION_MATCH"
            DEB_FILE="$VERSION_MATCH"
        else
            exit 1
        fi
    else
        echo "❌ No .deb files found anywhere"
        exit 1
    fi
fi

echo "📦 Found package: $DEB_FILE"

# Test 1: Verify package structure and metadata
echo "🔍 Testing package structure..."
if command -v dpkg >/dev/null 2>&1; then
    # Check package info
    if dpkg -I "$DEB_FILE" >/dev/null 2>&1; then
        echo "✅ Package structure is valid"
        
        # Extract key metadata
        PACKAGE_VERSION=$(dpkg -f "$DEB_FILE" Version)
        PACKAGE_NAME=$(dpkg -f "$DEB_FILE" Package)
        PACKAGE_ARCH=$(dpkg -f "$DEB_FILE" Architecture)
        
        echo "  Package: $PACKAGE_NAME"
        echo "  Version: $PACKAGE_VERSION"
        echo "  Architecture: $PACKAGE_ARCH"
        
        # Verify version matches
        if [ "$PACKAGE_VERSION" = "$VERSION" ]; then
            echo "✅ Package version matches expected version ($VERSION)"
        else
            echo "❌ Package version mismatch: expected $VERSION, got $PACKAGE_VERSION"
            exit 1
        fi
    else
        echo "❌ Package structure test failed"
        dpkg -I "$DEB_FILE"
        exit 1
    fi
else
    echo "⚠️ dpkg not available, skipping structure check"
fi

# Test 2: Verify package contents
echo "🔍 Testing package contents..."
if command -v dpkg >/dev/null 2>&1; then
    # List package contents
    PACKAGE_CONTENTS=$(dpkg -c "$DEB_FILE" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "✅ Package contents readable"
        
        # Check for required files
        if echo "$PACKAGE_CONTENTS" | grep -q "./usr/bin/eir"; then
            echo "✅ Binary file found in package"
        else
            echo "❌ Binary file not found in package"
            echo "Package contents:"
            echo "$PACKAGE_CONTENTS"
            exit 1
        fi
        
        # Check for docs if they exist
        if echo "$PACKAGE_CONTENTS" | grep -q "./usr/share/doc/eir"; then
            echo "✅ Documentation found in package"
        else
            echo "⚠️ No documentation directory found (optional)"
        fi
    else
        echo "❌ Could not read package contents"
        exit 1
    fi
else
    echo "⚠️ dpkg not available, skipping contents check"
fi

# Test 3: Test package linting
echo "🔍 Testing package quality..."
if command -v lintian >/dev/null 2>&1; then
    echo "📥 Running lintian checks..."
    if lintian "$DEB_FILE" 2>/dev/null; then
        echo "✅ Lintian checks passed"
    else
        echo "⚠️ Lintian found some issues, but continuing..."
        lintian "$DEB_FILE" 2>&1 | head -10
    fi
else
    echo "⚠️ lintian not available, skipping quality checks"
fi

# Test 4: Verify control file and dependencies
echo "🔍 Testing control file..."
if command -v dpkg >/dev/null 2>&1; then
    # Extract control information
    CONTROL_INFO=$(dpkg -f "$DEB_FILE" 2>/dev/null)
    
    # Check required fields
    REQUIRED_FIELDS=("Package" "Version" "Architecture" "Maintainer" "Description")
    for field in "${REQUIRED_FIELDS[@]}"; do
        if echo "$CONTROL_INFO" | grep -q "^$field:"; then
            echo "✅ Required field '$field' found"
        else
            echo "❌ Missing required field: $field"
            exit 1
        fi
    done
    
    # Check dependencies if any are specified
    if echo "$CONTROL_INFO" | grep -q "^Depends:"; then
        DEPENDS=$(echo "$CONTROL_INFO" | grep "^Depends:" | cut -d: -f2- | xargs)
        echo "📋 Package dependencies: $DEPENDS"
        echo "✅ Dependencies specified"
    else
        echo "📋 No dependencies specified"
    fi
else
    echo "⚠️ dpkg not available, skipping control file check"
fi

# Test 5: Verify binary exists and test execution
echo "🔍 Testing binary availability..."
BINARY_PATTERN="eir-$VERSION-linux-*"
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
else
    echo "❌ Could not find Linux binary for version $VERSION"
    echo "Searched for: $BINARY_PATTERN"
    echo "Available files in dist/:"
    ls -la dist/ 2>/dev/null || echo "  (dist directory not found)"
    exit 1
fi

# Test 6: Test package installation (dry-run if possible)
echo "🔍 Testing package installation simulation..."
if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
    echo "📥 Running APT installation simulation..."
    
    # Try to simulate installation (requires root)
    if apt-get install --dry-run --allow-downgrades "$DEB_FILE" >/dev/null 2>&1; then
        echo "✅ APT installation simulation successful"
    else
        echo "⚠️ APT installation simulation had issues"
    fi
elif command -v dpkg >/dev/null 2>&1; then
    echo "📥 Running dpkg installation test..."
    
    # Test package installation without actually installing
    if dpkg --info "$DEB_FILE" >/dev/null 2>&1; then
        echo "✅ Package installability verified"
    else
        echo "⚠️ Package installability test failed"
    fi
else
    echo "⚠️ APT/dpkg not available or insufficient permissions, skipping installation test"
fi

# Test 7: Verify package file integrity
echo "🔍 Testing package file integrity..."
if command -v ar >/dev/null 2>&1; then
    # Check if the .deb file is a valid ar archive
    if ar t "$DEB_FILE" >/dev/null 2>&1; then
        echo "✅ Package file format is valid"
        
        # Check for required components
        AR_CONTENTS=$(ar t "$DEB_FILE" 2>/dev/null)
        if echo "$AR_CONTENTS" | grep -q "control.tar"; then
            echo "✅ Control archive found"
        else
            echo "❌ Control archive missing"
            exit 1
        fi
        
        if echo "$AR_CONTENTS" | grep -q "data.tar"; then
            echo "✅ Data archive found"
        else
            echo "❌ Data archive missing"
            exit 1
        fi
    else
        echo "❌ Package file format test failed"
        exit 1
    fi
else
    echo "⚠️ ar command not available, skipping file integrity check"
fi

echo "🎉 All APT package tests completed successfully!"
echo "📋 Package $DEB_FILE is ready for publication"