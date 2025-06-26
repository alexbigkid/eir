#!/bin/bash
# Download DNGLab binary for macOS DNG conversion

set -e

# Function to auto-detect latest DNGLab version from GitHub API
get_latest_dnglab_version() {
    local LCL_VERSION_VAR=$1
    local LCL_VERSION=""
    local LCL_EXIT_CODE=0

    echo "🔍 Detecting latest DNGLab version..." >&2

    if command -v curl >/dev/null 2>&1; then
        echo "🔍 Using curl to fetch latest version..." >&2
        API_RESPONSE=$(curl -s --connect-timeout 10 --max-time 30 -H "User-Agent: eir-build-script" https://api.github.com/repos/dnglab/dnglab/releases/latest 2>&1)
        API_EXIT_CODE=$?
        echo "🔍 API response length: ${#API_RESPONSE}" >&2
        if [ $API_EXIT_CODE -eq 0 ] && [ -n "$API_RESPONSE" ]; then
            LCL_VERSION=$(echo "$API_RESPONSE" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/' || echo "")
        else
            echo "❌ curl failed with exit code $API_EXIT_CODE" >&2
            echo "❌ curl output: $API_RESPONSE" >&2
            LCL_VERSION=""
        fi
    elif command -v wget >/dev/null 2>&1; then
        echo "🔍 Using wget to fetch latest version..." >&2
        API_RESPONSE=$(wget --timeout=30 --user-agent="eir-build-script" -qO- https://api.github.com/repos/dnglab/dnglab/releases/latest 2>&1)
        API_EXIT_CODE=$?
        if [ $API_EXIT_CODE -eq 0 ] && [ -n "$API_RESPONSE" ]; then
            LCL_VERSION=$(echo "$API_RESPONSE" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/' || echo "")
        else
            echo "❌ wget failed with exit code $API_EXIT_CODE" >&2
            LCL_VERSION=""
        fi
    else
        echo "❌ Neither curl nor wget found. Cannot detect latest version." >&2
        LCL_EXIT_CODE=1
        return $LCL_EXIT_CODE
    fi

    if [ -z "$LCL_VERSION" ]; then
        echo "❌ Failed to detect latest DNGLab version. Falling back to v0.7.0" >&2
        eval "$LCL_VERSION_VAR"="v0.7.0"
    else
        echo "✅ Latest DNGLab version: $LCL_VERSION" >&2
        eval "$LCL_VERSION_VAR"="$LCL_VERSION"
    fi

    return $LCL_EXIT_CODE
}

# Function to detect architecture and map to DNGLab release naming
get_dnglab_binary_info() {
    local LCL_ARCH_VAR=$1
    local LCL_BINARY_VAR=$2
    local LCL_ARCH
    local LCL_EXIT_CODE=0

    LCL_ARCH=$(uname -m)

    echo "🔍 Detecting architecture: $LCL_ARCH" >&2

    case $LCL_ARCH in
        x86_64)
            eval "$LCL_ARCH_VAR"="x86_64"
            eval "$LCL_BINARY_VAR"="dnglab-macos-x64"
            ;;
        arm64)
            eval "$LCL_ARCH_VAR"="arm64"
            eval "$LCL_BINARY_VAR"="dnglab-macos-arm64"
            ;;
        *)
            echo "❌ Unsupported architecture: $LCL_ARCH" >&2
            LCL_EXIT_CODE=1
            ;;
    esac

    return $LCL_EXIT_CODE
}

# Function to download and setup DNGLab binary
download_and_setup_dnglab() {
    local LCL_VERSION=$1
    local LCL_ARCH=$2
    local LCL_BINARY=$3
    local LCL_PLATFORM=$4
    local LCL_URL
    local LCL_ZIP_PATH
    local LCL_PATH
    local LCL_EXIT_CODE=0

    LCL_URL="https://github.com/dnglab/dnglab/releases/download/${LCL_VERSION}/${LCL_BINARY}_${LCL_VERSION}.zip"
    LCL_ZIP_PATH="./build/${LCL_PLATFORM}/tools/${LCL_ARCH}/${LCL_BINARY}_${LCL_VERSION}.zip"
    LCL_PATH="./build/${LCL_PLATFORM}/tools/${LCL_ARCH}/dnglab"

    echo "📥 Downloading DNGLab ${LCL_VERSION} for ${LCL_ARCH}..."
    echo "🔗 URL: $LCL_URL"

    # Create build directory structure if it doesn't exist
    mkdir -p "./build/${LCL_PLATFORM}/tools/${LCL_ARCH}"

    # Download DNGLab ZIP file
    if command -v curl >/dev/null 2>&1; then
        curl -L -o "$LCL_ZIP_PATH" "$LCL_URL"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$LCL_ZIP_PATH" "$LCL_URL"
    else
        echo "❌ Neither curl nor wget found. Cannot download DNGLab."
        LCL_EXIT_CODE=1
        return $LCL_EXIT_CODE
    fi

    # Extract the ZIP file
    if [ -f "$LCL_ZIP_PATH" ]; then
        echo "📂 Extracting ZIP file..."
        cd "./build/${LCL_PLATFORM}/tools/${LCL_ARCH}"
        if command -v unzip >/dev/null 2>&1; then
            unzip -o "$(basename "$LCL_ZIP_PATH")"
        else
            echo "❌ unzip command not found. Cannot extract DNGLab."
            LCL_EXIT_CODE=1
            return $LCL_EXIT_CODE
        fi
        cd - >/dev/null

        # Find and rename the extracted binary to 'dnglab' (macOS compatible)
        EXTRACTED_BINARY=$(find "./build/${LCL_PLATFORM}/tools/${LCL_ARCH}" -name "dnglab*" -type f | head -1)
        if [ -n "$EXTRACTED_BINARY" ] && [ "$EXTRACTED_BINARY" != "$LCL_PATH" ]; then
            echo "📋 Renaming extracted binary: $EXTRACTED_BINARY -> $LCL_PATH"
            mv "$EXTRACTED_BINARY" "$LCL_PATH"
        fi

        # Clean up ZIP file
        rm -f "$LCL_ZIP_PATH"
    else
        echo "❌ ZIP file not found after download"
        LCL_EXIT_CODE=1
        return $LCL_EXIT_CODE
    fi

    # Make executable
    if [ -f "$LCL_PATH" ]; then
        chmod +x "$LCL_PATH"
    else
        echo "❌ DNGLab binary not found after extraction"
        LCL_EXIT_CODE=1
    fi

    return $LCL_EXIT_CODE
}

# Function to verify and test DNGLab binary
verify_and_test_dnglab() {
    local LCL_PLATFORM=$1
    local LCL_ARCH=$2
    local LCL_PATH
    local LCL_FILE_SIZE
    local LCL_EXIT_CODE=0

    LCL_PATH="./build/${LCL_PLATFORM}/tools/${LCL_ARCH}/dnglab"

    # Verify download
    if [ -f "$LCL_PATH" ]; then
        LCL_FILE_SIZE=$(stat -f%z "$LCL_PATH" 2>/dev/null || stat -c%s "$LCL_PATH" 2>/dev/null || echo "0")
        echo "✅ DNGLab downloaded successfully"
        echo "📁 Path: $LCL_PATH"
        echo "📊 Size: $LCL_FILE_SIZE bytes"

        # Test the binary
        echo "🧪 Testing DNGLab binary..."
        if "$LCL_PATH" --help >/dev/null 2>&1; then
            echo "✅ DNGLab binary is working correctly"
        else
            echo "⚠️  DNGLab binary test failed - may still work for conversion"
        fi
    else
        echo "❌ Download failed - DNGLab binary not found"
        LCL_EXIT_CODE=1
    fi

    return $LCL_EXIT_CODE
}


# =============================================================================
# main
# =============================================================================
echo ""
echo "-> $0 ($*)"

PLATFORM="darwin"
get_latest_dnglab_version DNGLAB_VERSION || exit 1
get_dnglab_binary_info DNGLAB_ARCH DNGLAB_BINARY || exit 1
download_and_setup_dnglab "$DNGLAB_VERSION" "$DNGLAB_ARCH" "$DNGLAB_BINARY" "$PLATFORM" || exit 1
verify_and_test_dnglab "$PLATFORM" "$DNGLAB_ARCH" || exit 1

echo "🎉 DNGLab setup complete!"

echo "<- $0 (0)"
exit 0