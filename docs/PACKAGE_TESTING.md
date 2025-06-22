# Package Testing Guide

This document describes how to test packages for the `eir` project across different package managers (Chocolatey, APT, Homebrew) both in CI/CD pipelines and locally.

## Overview

The project includes comprehensive package testing for all supported package managers:

### Package Manager Support
- **Chocolatey** (Windows) - `.nupkg` packages
- **APT** (Linux) - `.deb` packages  
- **Homebrew** (macOS) - `.rb` formula files

### Testing Levels
1. **Automated CI Testing** - Runs on every platform build in GitHub Actions
2. **Local Testing** - Quick verification on developer machines  
3. **Full Environment Testing** - Using official test environments

## Automated CI Testing

### What's Tested

The CI pipeline automatically tests all package formats:

#### Chocolatey (Windows)
- ✅ Package structure validation (.nupkg)
- ✅ PowerShell script syntax checking
- ✅ Metadata verification
- ✅ Binary availability and execution
- ✅ Version consistency

#### APT (Linux)
- ✅ Package structure validation (.deb)
- ✅ Control file verification
- ✅ File contents and permissions
- ✅ Package quality checks (lintian)
- ✅ Binary availability and execution

#### Homebrew (macOS)
- ✅ Formula syntax validation (.rb)
- ✅ Formula structure verification
- ✅ SHA256 checksum validation
- ✅ Binary availability and execution
- ✅ Homebrew audit checks

### Test Scripts

Tests run automatically on platform-specific builds:

```bash
# Chocolatey (Windows)
.\.github\scripts\test_chocolatey_package.ps1 -Version $VERSION

# APT (Linux)
./.github/scripts/test_apt_package.sh $VERSION

# Homebrew (macOS)
./.github/scripts/test_homebrew_package.sh $VERSION
```

## Local Testing

### Quick Testing

For basic validation on your local machine:

#### Chocolatey (Windows)
```powershell
# Run the same tests as CI
.\.github\scripts\test_chocolatey_package.ps1 -Version "0.1.58"
```

#### APT (Linux)
```bash
# Run the same tests as CI
./.github/scripts/test_apt_package.sh "0.1.58"
```

#### Homebrew (macOS)
```bash
# Run the same tests as CI
./.github/scripts/test_homebrew_package.sh "0.1.58"
```

### Manual Package Testing

#### Chocolatey (Windows)
```powershell
# Build the package locally
uv run python .github/scripts/package_build.py

# Test installation (dry-run)
choco install eir --source .\packages-windows-amd64 --version 0.1.58 --whatif

# Full local installation test
choco install eir --source .\packages-windows-amd64 --version 0.1.58 --force
```

#### APT (Linux)
```bash
# Build the package locally
uv run python .github/scripts/package_build.py

# Test package info
dpkg -I ./packages-linux-x86_64/eir_0.1.58_amd64.deb

# Test installation (requires sudo)
sudo dpkg -i ./packages-linux-x86_64/eir_0.1.58_amd64.deb
```

#### Homebrew (macOS)
```bash
# Build the package locally
uv run python .github/scripts/package_build.py

# Test formula installation (local)
brew install --build-from-source ./packages-macos-universal/eir.rb
```

## Full Environment Testing

### Prerequisites

For comprehensive testing using Chocolatey's official test environment:

- **64-bit Windows computer**
- **Vagrant 2.1+** - [Download](https://www.vagrantup.com/downloads)
- **VirtualBox 5.2+** - [Download](https://www.virtualbox.org/wiki/Downloads)
- **At least 50GB free space**
- **Intel VT-x enabled** in BIOS

### Setup Test Environment

```powershell
# Setup the test environment (one-time)
.\.github\scripts\setup_chocolatey_test_env.ps1 -SetupOnly

# Or manually:
git clone https://github.com/chocolatey-community/chocolatey-test-environment.git C:\ChocolateyTestEnvironment
cd C:\ChocolateyTestEnvironment
vagrant up
vagrant snapshot save good
```

### Run Full Package Tests

```powershell
# Test specific package version
.\.github\scripts\setup_chocolatey_test_env.ps1 -PackageVersion "0.1.58"

# Or manually:
cd C:\ChocolateyTestEnvironment
copy ..\packages-windows-amd64\eir.0.1.58.nupkg packages\
vagrant provision
```

### Test Workflow

1. **Start Clean**: `vagrant snapshot restore good`
2. **Copy Package**: Place your `.nupkg` in the `packages` folder
3. **Run Test**: `vagrant provision`
4. **Inspect Results**: SSH into VM or check logs
5. **Reset**: `vagrant snapshot restore good` for next test

## Common Issues and Solutions

### Package Installation Failures

**Symptom**: Installation fails with parameter errors
```
ERROR: Cannot process command because of one or more missing mandatory parameters
```

**Solution**: Check `chocolateyinstall.ps1` parameters:
```powershell
# Correct usage
Get-ChocolateyWebFile -PackageName $packageName -FileFullPath $downloadPath -Url64bit $url64 -Checksum64 $checksum -ChecksumType64 'sha256'
```

### Checksum Mismatches

**Symptom**: Download fails with checksum validation error

**Solution**: The build script automatically calculates correct checksums. Ensure you're using the package built by the pipeline, not manually created ones.

### Binary Execution Issues

**Symptom**: Binary doesn't execute or hangs

**Solution**: Test the binary directly:
```powershell
# Test binary execution
.\dist\eir-0.1.58-windows-x86_64.exe --version
.\dist\eir-0.1.58-windows-x86_64.exe --help
```

## Testing Best Practices

### Before Submitting to Chocolatey

1. **Always test locally first** using the CI test script
2. **Test on clean environment** using the full test environment
3. **Verify all commands work**: `--version`, `--help`, `--about`
4. **Check package size** - ensure it's reasonable
5. **Test uninstallation** if you have an uninstall script

### CI Integration

The tests are integrated into the GitHub Actions workflow and will:
- ✅ **Block releases** if package tests fail
- ✅ **Provide detailed logs** for debugging
- ✅ **Test on every Windows build** automatically

### Debugging Failed Tests

1. **Check CI logs** for specific error messages
2. **Run tests locally** to reproduce issues
3. **Use Vagrant environment** for deeper investigation
4. **Check Chocolatey documentation** for function usage

## Resources

- [Chocolatey Package Creation Guide](https://docs.chocolatey.org/en-us/create/create-packages-quick-start/)
- [Chocolatey Test Environment](https://github.com/chocolatey-community/chocolatey-test-environment)
- [Chocolatey PowerShell Functions](https://docs.chocolatey.org/en-us/create/functions/)
- [Package Troubleshooting](https://docs.chocolatey.org/en-us/troubleshooting/)

## Contributing

When making changes to Chocolatey packaging:

1. **Update tests** if adding new functionality
2. **Test on multiple platforms** when possible
3. **Document any new requirements** or procedures
4. **Ensure CI tests pass** before merging