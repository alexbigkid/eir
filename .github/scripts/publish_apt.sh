#!/bin/bash
# APT repository setup script
set -e

VERSION="$1"

if [ -z "$VERSION" ]; then
    echo "❌ Error: Version required"
    exit 1
fi

echo "📦 Setting up APT repository for version $VERSION..."

# Create docs directory for GitHub Pages
mkdir -p docs/apt-repo
if [ -d "packages/apt-repo" ]; then
    cp -r packages/apt-repo/* docs/apt-repo/
fi

# Create index page for APT repository
cat > docs/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Eir APT Repository</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .code { background: #f5f5f5; padding: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Eir APT Repository</h1>
    <p>EXIF-based image renamer and RAW format converter</p>
    
    <h2>Installation</h2>
    <div class="code">
        <pre>echo 'deb [trusted=yes] https://alexbigkid.github.io/eir/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/eir.list
sudo apt update
sudo apt install eir</pre>
    </div>
    
    <h2>Supported Architectures</h2>
    <ul>
        <li>amd64 (Intel/AMD 64-bit)</li>
        <li>arm64 (ARM 64-bit)</li>
    </ul>
    
    <p><a href="https://github.com/alexbigkid/eir">View source on GitHub</a></p>
</body>
</html>
EOF

# Commit APT repository changes
git add docs/
if git diff --staged --quiet; then
    echo "⚠️ No changes to APT repository"
else
    git commit -m "Update APT repository for v$VERSION"
    git push origin main
    echo "✅ APT repository updated"
fi