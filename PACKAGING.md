# Package Distribution Guide

This document explains how to distribute Eir through various package managers.

## Automated Package Building

The release pipeline automatically creates packages for all supported package managers when a new version is released. The `package_build.py` script handles:

- Updating Homebrew formula with correct SHA256 hashes
- Creating Debian `.deb` packages
- Preparing Chocolatey `.nupkg` packages

## Homebrew (macOS)

### Setup
1. Create a separate repository for the Homebrew tap: `homebrew-eir`
2. Copy the generated `homebrew/eir.rb` formula to the tap repository
3. Users can then install with:
   ```bash
   brew tap alexbigkid/eir
   brew install eir
   ```

### Updates
The formula is automatically updated with each release, including:
- Version number
- SHA256 hash of the macOS binary
- Download URL

## Debian/Ubuntu (APT)

### APT Repository
The build process automatically creates a proper APT repository structure that enables `sudo apt install eir`:

1. **Repository Structure**: Created in `packages/apt-repo/` with proper `dists/` and `pool/` directories
2. **Metadata Files**: Generates `Packages`, `Packages.gz`, and `Release` files with checksums
3. **Hosting**: Repository should be hosted via GitHub Pages at `https://alexbigkid.github.io/eir/apt-repo`

### Setup GitHub Pages APT Repository
1. Create a separate `gh-pages` branch or use docs folder
2. Copy the `apt-repo/` contents to the web root
3. Users can then install with:
   ```bash
   echo 'deb [trusted=yes] https://alexbigkid.github.io/eir/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/eir.list
   sudo apt update
   sudo apt install eir
   ```

### Manual Distribution
For users who prefer manual installation:
```bash
wget https://github.com/alexbigkid/eir/releases/download/v<version>/eir_<version>_amd64.deb
sudo dpkg -i eir_<version>_amd64.deb
```

### Repository Signing (Future Enhancement)
For production use, consider:
1. GPG signing of packages and Release files
2. Removing `[trusted=yes]` from sources.list
3. Distributing public GPG keys

## Chocolatey (Windows)

### Setup
1. Create an account on [chocolatey.org](https://chocolatey.org)
2. Submit the generated `.nuspec` package
3. The package will be reviewed and published

### Updates
Each release automatically:
- Updates version numbers
- Calculates SHA256 checksums
- Updates download URLs

### Manual Upload
```powershell
# Build the package
choco pack chocolatey/eir.nuspec

# Upload to Chocolatey (requires API key)
choco push eir.<version>.nupkg --source https://push.chocolatey.org/
```

## Package Contents

### Homebrew Formula (`homebrew/eir.rb`)
- Downloads macOS universal binary
- Installs to `/usr/local/bin/eir`
- Includes basic test

### Debian Package
- Contains Linux x86_64 binary
- Installs to `/usr/bin/eir`
- Includes control files with dependencies and metadata
- Proper copyright and licensing information

### Chocolatey Package
- Downloads Windows x86_64 executable
- Creates command-line shim
- Includes install/uninstall scripts
- Metadata with tags and descriptions

## Testing Packages

### Homebrew
```bash
# Test formula locally
brew install --build-from-source ./homebrew/eir.rb
brew test eir
```

### Debian
```bash
# Test package installation
sudo dpkg -i packages/eir_<version>_amd64.deb
eir --version
sudo dpkg -r eir
```

### Chocolatey
```powershell
# Test local package
choco install eir --source="'packages;https://chocolatey.org/api/v2/'"
eir --version
choco uninstall eir
```

## Maintenance

1. **Version Updates**: Automated through the release pipeline
2. **Security**: Monitor for vulnerabilities in dependencies
3. **Compatibility**: Test with new OS versions
4. **User Feedback**: Monitor package manager specific issues

## Distribution Checklist

- [ ] Homebrew formula updated and tested
- [ ] Debian package created and validated
- [ ] Chocolatey package prepared and tested
- [ ] All checksums verified
- [ ] Installation instructions updated
- [ ] Package repositories updated (if applicable)

## Troubleshooting

### Common Issues
1. **SHA256 Mismatch**: Ensure binaries haven't changed after package creation
2. **Missing Dependencies**: Update package metadata if new system dependencies are added
3. **Permission Issues**: Ensure install scripts have proper permissions
4. **Path Issues**: Verify binary installation paths are correct

### Support
- GitHub Issues: Report package-specific problems
- Package Manager Communities: For platform-specific distribution issues