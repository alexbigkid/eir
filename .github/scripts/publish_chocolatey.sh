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

# Debug: Inspect package contents
echo "🔍 Package inspection:"
echo "Package size: $(ls -lh "$NUPKG_FILE" | awk '{print $5}')"
echo "Package contents:"
unzip -l "$NUPKG_FILE" 2>/dev/null || echo "  (could not list package contents)"

# Upload package using .NET CLI (cross-platform approach)
echo "🚀 Uploading to Chocolatey using .NET CLI..."

# Check if dotnet is available
if command -v dotnet >/dev/null 2>&1; then
    echo "📤 Pushing package with dotnet nuget push..."
    if dotnet nuget push "$NUPKG_FILE" --source https://push.chocolatey.org/ --api-key "$CHOCOLATEY_API_KEY"; then
        echo "✅ Chocolatey package uploaded successfully"
        exit 0
    else
        echo "⚠️ dotnet nuget push failed, trying alternative method..."
    fi
fi

# Fallback: Install NuGet CLI if dotnet failed or isn't available
echo "📥 Installing NuGet CLI as fallback..."
# Download and install nuget.exe
wget -q https://dist.nuget.org/win-x86-commandline/latest/nuget.exe

# Install mono to run nuget.exe on Linux
sudo apt-get update -qq
sudo apt-get install -y mono-complete

# Create a wrapper script
cat > nuget << 'EOF'
#!/bin/bash
mono nuget.exe "$@"
EOF
chmod +x nuget
export PATH="$PWD:$PATH"

# Push package using NuGet CLI
echo "📤 Pushing package with NuGet CLI..."
if nuget push "$NUPKG_FILE" -Source https://push.chocolatey.org/ -ApiKey "$CHOCOLATEY_API_KEY"; then
    echo "✅ Chocolatey package uploaded successfully"
else
    echo "❌ Failed to upload Chocolatey package"
    echo ""
    echo "💡 Troubleshooting steps:"
    echo "   1. Verify CHOCOLATEY_API_KEY is valid and not expired"
    echo "   2. Check if package name 'eir' is available or you own it"
    echo "   3. Ensure package version doesn't already exist"
    exit 1
fi