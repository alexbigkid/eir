#!/bin/bash
# Homebrew tap update script
set -e

VERSION="$1"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

if [ -z "$VERSION" ]; then
    echo "❌ Error: Version required"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Error: GITHUB_TOKEN required"
    exit 1
fi

echo "🍺 Updating Homebrew tap for version $VERSION..."

# Set up Git
git config --global user.email "action@github.com"
git config --global user.name "GitHub Action"

# Clone the homebrew-eir repository with authentication
git clone "https://x-access-token:$GITHUB_TOKEN@github.com/alexbigkid/homebrew-eir.git" ../homebrew-eir

# Copy the updated formula
mkdir -p ../homebrew-eir/Formula
cp homebrew/eir.rb ../homebrew-eir/Formula/eir.rb

# Commit and push changes
cd ../homebrew-eir
git add Formula/eir.rb
if git diff --staged --quiet; then
    echo "⚠️ No changes to Homebrew formula"
else
    git commit -m "Update eir formula to v$VERSION"
    git push origin main
    echo "✅ Homebrew formula updated"
fi