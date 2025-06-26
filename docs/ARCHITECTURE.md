← [Back to Main Documentation](../README.md)

# Architecture Support

This document explains the CPU architecture support for Eir binaries and packages.

## Current Architecture Support

### ✅ Fully Supported
- **Linux x86_64 (AMD64)**: Full support including APT packages
- **Linux ARM64 (aarch64)**: Full support including APT packages (Raspberry Pi, ARM servers, AWS Graviton)
- **macOS Universal**: Supports both Intel x64 and Apple Silicon ARM64 in one binary
- **Windows x86_64 (AMD64)**: Full support including Chocolatey packages
- **Windows ARM64**: Full support (Surface Pro X, Windows on ARM devices)

### ❌ Not Currently Supported
- **Linux i386**: 32-bit Intel systems
- **Windows i386**: 32-bit Windows systems

## Architecture Compatibility

### AMD vs Intel
- **AMD64 and Intel x64 are compatible**: Our x86_64 binaries work on both AMD and Intel processors
- The term "AMD64" refers to the 64-bit instruction set originally developed by AMD
- Intel adopted this instruction set as "Intel 64" or "x64"
- **Result**: ✅ Our Linux and Windows binaries work on both AMD and Intel CPUs

### ARM Compatibility
- **ARM64 (aarch64) is now fully supported**: Native ARM64 binaries available
- Common ARM64 systems that are **✅ NOW SUPPORTED**:
  - Raspberry Pi 4/5 (64-bit) - use Linux ARM64 binary
  - AWS Graviton instances - use Linux ARM64 binary
  - Apple Silicon Macs - use macOS Universal binary
  - ARM-based servers - use Linux ARM64 binary
  - Surface Pro X - use Windows ARM64 binary

## Package Manager Architecture Mapping

### APT (Debian/Ubuntu)
```bash
# Available packages
eir_<version>_amd64.deb     # Intel/AMD 64-bit
eir_<version>_arm64.deb     # ARM 64-bit (Raspberry Pi, ARM servers, AWS Graviton)
```

**Future support could include:**
```bash
eir_<version>_armhf.deb     # ARM 32-bit (older Raspberry Pi)
eir_<version>_i386.deb      # Intel/AMD 32-bit
```

### Homebrew (macOS)
```bash
# Current package (Universal)
eir-<version>-macos-universal    # Works on: Intel x64, Apple Silicon ARM64
```

### Chocolatey (Windows)
```bash
# Current package
eir-<version>-windows-amd64.exe  # Works on: Intel x64, AMD64
```

## Adding ARM64 Support

To add Linux ARM64 support, we would need:

### 1. GitHub Actions Matrix Update
```yaml
strategy:
  matrix:
    include:
      - os: ubuntu-latest
        arch: x86_64
      - os: ubuntu-latest  
        arch: aarch64  # ARM64 support
        cross-compile: true
```

### 2. Cross-Compilation Setup
- Use Docker with ARM64 emulation
- Install ARM64 Python and dependencies
- Cross-compile Nuitka binaries

### 3. Package Updates
- Create separate `.deb` packages for each architecture
- Update APT repository structure for multi-arch
- Modify package detection logic

## Manual Installation for Unsupported Architectures

### For ARM64 Linux systems:
```bash
# Option 1: Install from source
git clone https://github.com/alexbigkid/eir
cd eir
pip install -e .

# Option 2: Install from PyPI (if published)
pip install eir
```

### Checking Your Architecture
```bash
# Linux/macOS
uname -m

# Common outputs:
# x86_64    = Intel/AMD 64-bit (✅ supported)
# aarch64   = ARM 64-bit (❌ not supported)
# armv7l    = ARM 32-bit (❌ not supported)
# i386/i686 = Intel/AMD 32-bit (❌ not supported)
```

```powershell
# Windows
echo $env:PROCESSOR_ARCHITECTURE

# Common outputs:
# AMD64 = Intel/AMD 64-bit (✅ supported)
# ARM64 = ARM 64-bit (❌ not supported)
# x86   = Intel/AMD 32-bit (❌ not supported)
```

## Performance Considerations

### Native vs Emulated
- **Native binaries**: Best performance, direct CPU execution
- **Emulated binaries**: Significant performance penalty (2-5x slower)
- **Universal binaries** (macOS): Native performance on both architectures

### Recommendations
1. **Use native binaries when available** for best performance
2. **Fall back to source installation** for unsupported architectures
3. **Consider containerization** for consistent cross-platform deployment

## Future Roadmap

### Priority Order for New Architecture Support
1. **Linux ARM64** (most requested, growing server market)
2. **Windows ARM64** (Surface Pro X, Windows on ARM)
3. **Linux i386** (legacy 32-bit systems)
4. **Windows i386** (legacy 32-bit Windows)

### Implementation Effort
- **Linux ARM64**: Medium effort (cross-compilation setup)
- **Windows ARM64**: High effort (Windows ARM development tools)
- **32-bit architectures**: Low priority (declining usage)

## Contributing

To help add architecture support:
1. Test source installation on your architecture
2. Report compatibility issues
3. Contribute cross-compilation scripts
4. Help with testing on different architectures