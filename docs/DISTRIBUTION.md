← [Back to Main Documentation](../README.md)

# Package Distribution Guide

This guide explains how to distribute Eir packages to various package managers after a successful release build.

## Prerequisites

The release pipeline automatically creates all package files. To distribute them, you need:

### 1. Homebrew Distribution
- **No account needed** - just a GitHub repository
- Create repository: `https://github.com/alexbigkid/homebrew-eir`
- The build pipeline creates `homebrew/eir.rb` with correct checksums

**Setup:**
```bash
# Create the tap repository
git clone https://github.com/alexbigkid/homebrew-eir ../homebrew-eir
# Run distribution script
./scripts/distribute_packages.sh
```

### 2. APT Repository (Debian/Ubuntu)
- **No account needed** - uses GitHub Pages
- Enable GitHub Pages in repository settings (Settings → Pages → Source: GitHub Actions)
- The build pipeline creates `.deb` files and repository metadata

**Setup:**
```bash
# After running the release, commit the docs/ directory
git add docs/
git commit -m "Update APT repository"
git push origin main
```

Users install with:
```bash
echo 'deb [trusted=yes] https://alexbigkid.github.io/eir/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/eir.list
sudo apt update
sudo apt install eir
```

### 3. Chocolatey Distribution
- **Account required**: Create free account at https://chocolatey.org
- Get API key from profile settings
- The build pipeline creates `.nupkg` file

**Setup:**
```bash
# Upload to Chocolatey (requires API key)
choco push packages/eir.VERSION.nupkg --source https://push.chocolatey.org/ --api-key YOUR_API_KEY
```

## Distribution Workflow

1. **Tag a release**: `git tag patch && git push origin patch`
2. **Wait for build**: GitHub Actions creates all packages
3. **Run distribution script**: `./scripts/distribute_packages.sh`
4. **Manual steps**:
   - Homebrew: Automatic via script
   - APT: Commit and push `docs/` directory
   - Chocolatey: Upload with `choco push` command

## File Locations After Build

- **Binaries**: GitHub Releases (automatic)
- **Homebrew**: `homebrew/eir.rb` (auto-updated with checksums)
- **Debian**: `packages/eir_VERSION_ARCH.deb`
- **APT repo**: `packages/apt-repo/` (copied to `docs/`)
- **Chocolatey**: `packages/eir.VERSION.nupkg`

## Current Status

✅ **GitHub Releases**: Automatic binary distribution  
🔄 **Homebrew**: Need to create `homebrew-eir` repository  
🔄 **APT**: Need to enable GitHub Pages  
🔄 **Chocolatey**: Need chocolatey.org account and API key  

The infrastructure is complete - just need the external accounts/repositories set up.