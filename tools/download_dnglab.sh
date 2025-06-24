#!/bin/bash
# Download DNGLab binary for Linux DNG conversion

set -e

DNGLAB_VERSION="v0.7.0"
ARCH=$(uname -m)

echo "🔍 Detecting architecture: $ARCH"

# Map architecture names to DNGLab release naming
case $ARCH in
    x86_64)
        DNGLAB_ARCH="x86_64"
        ;;
    aarch64|arm64)
        DNGLAB_ARCH="aarch64"
        ;;
    *)
        echo "❌ Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

DNGLAB_URL="https://github.com/dnglab/dnglab/releases/download/${DNGLAB_VERSION}/dnglab_linux_${DNGLAB_ARCH}"
DNGLAB_PATH="./tools/linux/dnglab_${DNGLAB_ARCH}"

echo "📥 Downloading DNGLab ${DNGLAB_VERSION} for ${DNGLAB_ARCH}..."
echo "🔗 URL: $DNGLAB_URL"

# Create directory if it doesn't exist
mkdir -p "./tools/linux"

# Download DNGLab binary
if command -v curl >/dev/null 2>&1; then
    curl -L -o "$DNGLAB_PATH" "$DNGLAB_URL"
elif command -v wget >/dev/null 2>&1; then
    wget -O "$DNGLAB_PATH" "$DNGLAB_URL"
else
    echo "❌ Neither curl nor wget found. Cannot download DNGLab."
    exit 1
fi

# Make executable
chmod +x "$DNGLAB_PATH"

# Verify download
if [ -f "$DNGLAB_PATH" ]; then
    FILE_SIZE=$(stat -c%s "$DNGLAB_PATH" 2>/dev/null || stat -f%z "$DNGLAB_PATH" 2>/dev/null || echo "0")
    echo "✅ DNGLab downloaded successfully"
    echo "📁 Path: $DNGLAB_PATH"
    echo "📊 Size: $FILE_SIZE bytes"
    
    # Test the binary
    echo "🧪 Testing DNGLab binary..."
    if "$DNGLAB_PATH" --help >/dev/null 2>&1; then
        echo "✅ DNGLab binary is working correctly"
    else
        echo "⚠️  DNGLab binary test failed - may still work for conversion"
    fi
else
    echo "❌ Download failed - DNGLab binary not found"
    exit 1
fi

echo "🎉 DNGLab setup complete!"