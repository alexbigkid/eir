#!/bin/bash
# GitHub release creation script
set -e

VERSION="$1"

if [ -z "$VERSION" ]; then
    echo "❌ Error: VERSION required"
    echo "Usage: $0 <version>"
    exit 1
fi

VERSION_TAG="v$VERSION"
echo "🚀 Creating GitHub Release for $VERSION_TAG..."

# Prepare release assets
echo "📦 Preparing release assets..."
mkdir -p release-assets
find ./artifacts -name "eir-*" -type f -exec cp {} ./release-assets/ \; 2>/dev/null || true

# Copy package files if they exist
if [ -d "./artifacts/eir-$VERSION-packages" ]; then
    cp -r "./artifacts/eir-$VERSION-packages"/* ./release-assets/ 2>/dev/null || true
fi

echo "📋 Release assets inventory:"
ls -la ./release-assets/

# Count assets for summary
BINARY_COUNT=$(find ./release-assets -name "eir-$VERSION-*" -type f | wc -l)
PACKAGE_COUNT=$(find ./release-assets -name "*.deb" -o -name "*.nupkg" | wc -l)

echo "📊 Asset Summary:"
echo "  - Binaries: $BINARY_COUNT"
echo "  - Packages: $PACKAGE_COUNT"

if [ "$BINARY_COUNT" -eq 0 ]; then
    echo "⚠️ Warning: No binaries found for release"
fi

# Create release body
cat > release_body.md << EOF
## 🚀 Eir $VERSION

### 📦 Downloads

**macOS (Universal - Intel + Apple Silicon):**
- \`eir-$VERSION-macos-universal\`

**Linux:**
- **x86_64** (Intel/AMD): \`eir-$VERSION-linux-x86_64\`
- **ARM64** (ARM/Graviton): \`eir-$VERSION-linux-aarch64\`

**Windows:**
- **x86_64** (Intel/AMD): \`eir-$VERSION-windows-x86_64.exe\`
- **ARM64** (Surface Pro X): \`eir-$VERSION-windows-arm64.exe\`

### 🏗️ Architecture Support
- **✅ Intel/AMD x86_64**: Full support (Linux, Windows, macOS)
- **✅ ARM64**: Full support (Linux, Windows, macOS)
- **✅ Apple Silicon**: Native support via macOS Universal binary
- **✅ AWS Graviton**: Native ARM64 Linux support
- **✅ Raspberry Pi 4/5**: Native ARM64 Linux support
- **❌ 32-bit systems**: Not supported

### 🔧 Installation

**macOS (Homebrew):**
\`\`\`bash
# Add our tap and install
brew tap alexbigkid/eir https://github.com/alexbigkid/eir
brew install eir
\`\`\`

**Ubuntu/Debian (APT):**
\`\`\`bash
# Add Eir APT repository (supports both amd64 and arm64)
echo 'deb [trusted=yes] https://alexbigkid.github.io/eir/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/eir.list
sudo apt update
sudo apt install eir
\`\`\`

**Manual .deb installation:**
\`\`\`bash
wget https://github.com/alexbigkid/eir/releases/download/v$VERSION/eir_${VERSION}_amd64.deb
sudo dpkg -i eir_${VERSION}_amd64.deb
\`\`\`

**Windows (Chocolatey):**
\`\`\`cmd
# Install via Chocolatey (coming soon)
choco install eir
\`\`\`

**Manual Installation:**

*macOS/Linux:*
\`\`\`bash
# Download the binary for your platform
chmod +x eir-$VERSION-<platform>
sudo mv eir-$VERSION-<platform> /usr/local/bin/eir
\`\`\`

*Windows:*
\`\`\`cmd
# Download eir-$VERSION-windows-amd64.exe
# Add to your PATH or run directly
\`\`\`

**Unsupported Architectures (ARM64 Linux, 32-bit systems):**
\`\`\`bash
# Install from source using pip
pip install git+https://github.com/alexbigkid/eir.git@v$VERSION
\`\`\`

### 📝 Changes
- Automated release build for version $VERSION
- Multi-platform binaries (macOS, Linux, Windows)
- Package manager support (Homebrew, APT, Chocolatey)
- See commit history for detailed changes

---
🤖 Generated with [Claude Code](https://claude.ai/code)
EOF

echo "📄 Release body created"
echo "✅ Ready to create GitHub Release: $VERSION_TAG"