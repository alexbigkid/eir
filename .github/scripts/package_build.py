#!/usr/bin/env python3
"""Build script for creating distribution packages (Homebrew, APT, Chocolatey)."""

import hashlib
import os
import platform
import re
import shutil
import subprocess  # noqa: S404
import tomllib
from datetime import datetime
from pathlib import Path


def get_version():
    """Get version from pyproject.toml."""
    try:
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        return config["project"]["version"]
    except Exception:
        return "dev"


def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def update_homebrew_formula(version, sha256_hash):
    """Update Homebrew formula with actual version and SHA256."""
    # Get OS name and architecture from environment
    os_name = os.environ.get("OS_NAME", "macos")
    arch = os.environ.get("ARCH", "universal")
    # Create packages directory based on OS and architecture
    packages_dir = Path(f"packages-{os_name}-{arch}")
    packages_dir.mkdir(exist_ok=True)

    formula_path = Path("packaging/homebrew/eir.rb")
    content = formula_path.read_text()

    # Update version and SHA256
    content = content.replace("REPLACE_WITH_ACTUAL_SHA256", sha256_hash)
    content = content.replace("REPLACE_WITH_VERSION", version)

    # Write to packages directory
    updated_formula_path = packages_dir / "eir.rb"
    updated_formula_path.write_text(content)
    print(f"Updated Homebrew formula: {updated_formula_path}")


def create_debian_package(version):
    """Create Debian packages for all available Linux architectures."""
    print("Creating Debian packages...")

    # Find all Linux binaries
    linux_binaries = []
    for file in Path("dist").glob(f"eir-{version}-linux-*"):
        if file.is_file():
            linux_binaries.append(file)

    if not linux_binaries:
        print(f"Warning: No Linux binaries found for version {version}")
        return

    created_packages = []

    for linux_binary in linux_binaries:
        # Extract architecture from filename
        filename = linux_binary.name
        if "linux-x86_64" in filename:
            deb_arch = "amd64"
        elif "linux-aarch64" in filename:
            deb_arch = "arm64"
        else:
            print(f"Unknown architecture in {filename}, skipping")
            continue

        print(f"Creating {deb_arch} package from {linux_binary}")

        # Get OS name and architecture from environment
        os_name = os.environ.get("OS_NAME", "linux")
        arch = os.environ.get("ARCH", "x86_64")

        # Create package directory structure
        pkg_dir = Path(f"packages-{os_name}-{arch}/eir_{version}_{deb_arch}")
        pkg_dir.mkdir(parents=True, exist_ok=True)

        # Copy binary to package
        bin_dir = pkg_dir / "usr/bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(linux_binary, bin_dir / "eir")
        os.chmod(bin_dir / "eir", 0o755)  # noqa: S103

        # Create architecture-specific control file
        debian_dir = pkg_dir / "DEBIAN"
        debian_dir.mkdir(exist_ok=True)

        # Update control file with current version and architecture
        control_content = Path("packaging/debian/control").read_text(encoding="utf-8")
        # Replace any existing version with the new one
        control_content = re.sub(r"Version:\s+[^\s]+", f"Version: {version}", control_content)
        control_content = control_content.replace("Architecture: amd64", f"Architecture: {deb_arch}")

        control_file = debian_dir / "control"
        control_file.write_text(control_content, encoding="utf-8")

        # Copy other debian files
        for other_file in ["copyright"]:
            if Path(f"packaging/debian/{other_file}").exists():
                shutil.copy2(f"packaging/debian/{other_file}", debian_dir / other_file)

        # Build the .deb package
        try:
            deb_filename = f"packages-{os_name}-{arch}/eir_{version}_{deb_arch}.deb"
            print(f"Running: dpkg-deb --build {pkg_dir} {deb_filename}")

            # Debug: Show package structure before building
            print(f"📂 Package directory structure for {pkg_dir}:")
            for path in sorted(pkg_dir.rglob("*")):
                if path.is_file():
                    perms = oct(path.stat().st_mode)[-3:]
                    size = path.stat().st_size
                    rel_path = path.relative_to(pkg_dir)
                    print(f"  {perms} {size:>8} {rel_path}")

            # Ensure the target directory exists
            Path(deb_filename).parent.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(  # noqa: S603,S607
                ["dpkg-deb", "--build", str(pkg_dir), deb_filename], check=True, capture_output=True, text=True
            )
            print(f"stdout: {result.stdout}")

            if Path(deb_filename).exists():
                print(f"✅ Created Debian package: {deb_filename}")
                created_packages.append(deb_filename)
            else:
                print(f"❌ dpkg-deb command succeeded but file not found: {deb_filename}")

        except subprocess.CalledProcessError as e:
            print(f"❌ dpkg-deb failed with exit code {e.returncode}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
        except FileNotFoundError as e:
            print(f"❌ dpkg-deb command not found: {e}")
            print("Note: dpkg-deb is required to build Debian packages")

    # Create APT repository with all packages
    if created_packages:
        create_apt_repository(version, created_packages)


def create_apt_repository(_version, deb_packages):
    """Create a proper APT repository structure for multiple architectures."""
    print("Creating APT repository...")

    repo_dir = Path("packages/apt-repo")
    dist = "stable"
    component = "main"
    architectures = ["amd64", "arm64"]  # Support both x86_64 and ARM64

    # Create repository structure for each architecture
    pool_dir = repo_dir / f"pool/{component}"
    pool_dir.mkdir(parents=True, exist_ok=True)

    # Copy all .deb files to pool
    for deb_package in deb_packages:
        deb_file = Path(deb_package)
        if deb_file.exists():
            shutil.copy2(deb_file, pool_dir)
            print(f"Copied {deb_file.name} to repository pool")

    # Create binary directories for each architecture
    arch_packages_dirs = {}
    for arch in architectures:
        packages_dir = repo_dir / f"dists/{dist}/{component}/binary-{arch}"
        packages_dir.mkdir(parents=True, exist_ok=True)
        arch_packages_dirs[arch] = packages_dir

    # Generate Packages file
    original_cwd = os.getcwd()
    try:
        # Change to repo directory and scan packages
        os.chdir(repo_dir)

        # Create Packages file
        result = subprocess.run(  # noqa: S603,S607
            ["dpkg-scanpackages", f"pool/{component}", "/dev/null"], capture_output=True, text=True, check=True
        )

        # Write Packages file for each architecture
        for _arch, packages_dir in arch_packages_dirs.items():
            packages_file = packages_dir / "Packages"
            packages_file.write_text(result.stdout, encoding="utf-8")

            # Compress Packages file using context manager
            with open(packages_dir / "Packages.gz", "wb") as gz_file:
                subprocess.run(  # noqa: S603,S607
                    ["gzip", "-c", str(packages_file)], stdout=gz_file, check=True
                )

        # Create Release file
        release_dir = repo_dir / f"dists/{dist}"
        release_file = release_dir / "Release"

        # Use timezone-aware datetime
        now = datetime.now(tz=None).strftime("%a, %d %b %Y %H:%M:%S UTC")
        arch_list = " ".join(architectures)
        release_content = f"""Origin: Eir Repository
Label: Eir
Suite: {dist}
Codename: {dist}
Version: 1.0
Architectures: {arch_list}
Components: {component}
Description: EXIF-based image renamer and RAW format converter
Date: {now}
"""

        # Add checksums for all architectures
        all_packages_files = []
        for arch in architectures:
            all_packages_files.extend([f"{component}/binary-{arch}/Packages", f"{component}/binary-{arch}/Packages.gz"])

        # MD5Sum (keeping for compatibility even though it's insecure)
        release_content += "MD5Sum:\n"
        for pkg_file in all_packages_files:
            file_path = release_dir / pkg_file
            if file_path.exists():
                md5_hash = hashlib.md5(file_path.read_bytes()).hexdigest()  # noqa: S324
                size = file_path.stat().st_size
                release_content += f" {md5_hash} {size} {pkg_file}\n"

        # SHA256
        release_content += "SHA256:\n"
        for pkg_file in all_packages_files:
            file_path = release_dir / pkg_file
            if file_path.exists():
                sha256_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                size = file_path.stat().st_size
                release_content += f" {sha256_hash} {size} {pkg_file}\n"

        release_file.write_text(release_content, encoding="utf-8")

        print(f"APT repository created at: {repo_dir}")
        print("\nTo use this repository, users should:")
        print(
            "1. Add repository: echo 'deb [trusted=yes] "
            f"https://yourdomain.com/apt-repo {dist} {component}' | "
            "sudo tee /etc/apt/sources.list.d/eir.list"
        )
        print("2. Update: sudo apt update")
        print("3. Install: sudo apt install eir")

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Failed to create APT repository: {e}")
        print("Note: dpkg-scanpackages is required to build APT repositories")
    finally:
        os.chdir(original_cwd)


def update_chocolatey_package(version, checksum):
    """Update Chocolatey package with actual version and checksum."""
    # Get OS name and architecture from environment
    os_name = os.environ.get("OS_NAME", "windows")
    arch = os.environ.get("ARCH", "amd64")

    # Create packages directory based on OS and architecture
    packages_dir = Path(f"packages-{os_name}-{arch}")
    packages_dir.mkdir(exist_ok=True)

    # Copy chocolatey directory structure directly to packages directory
    shutil.copytree("packaging/chocolatey", packages_dir, dirs_exist_ok=True)

    # Update nuspec file
    nuspec_path = packages_dir / "eir.nuspec"
    content = nuspec_path.read_text(encoding="utf-8")
    # Replace any existing version with the new one
    content = re.sub(r"<version>[^<]+</version>", f"<version>{version}</version>", content)
    nuspec_path.write_text(content, encoding="utf-8")

    # Update install script
    install_path = packages_dir / "tools/chocolateyinstall.ps1"
    content = install_path.read_text(encoding="utf-8")
    content = re.sub(r"\$version\s*=\s*'[^']*'", f"$version = '{version}'", content)
    content = content.replace("REPLACE_WITH_ACTUAL_CHECKSUM", checksum)
    # Fix the URL to match the actual binary filename format
    content = re.sub(r"eir-\$version-windows-amd64\.exe", "eir-$version-windows-x86_64.exe", content)
    install_path.write_text(content, encoding="utf-8")

    print(f"Updated Chocolatey package files for version {version}")


def create_chocolatey_package(version):
    """Create Chocolatey package."""
    print("Creating Chocolatey package...")

    # Check if we have the Windows binary
    windows_binary = None
    for file in Path("dist").glob(f"eir-{version}-windows-*.exe"):
        if file.is_file():
            windows_binary = file
            break

    if not windows_binary:
        print(f"Warning: No Windows binary found for version {version}")
        return

    # Calculate checksum for Windows binary
    checksum = calculate_sha256(windows_binary)
    update_chocolatey_package(version, checksum)

    # Create nupkg using proper Chocolatey tools
    os_name = os.environ.get("OS_NAME", "windows")
    arch = os.environ.get("ARCH", "amd64")
    packages_dir = Path(f"packages-{os_name}-{arch}")

    # Store original working directory
    original_cwd = os.getcwd()

    try:
        # Change to package directory for choco pack (required by Chocolatey)
        os.chdir(packages_dir)

        # Try choco pack first (proper method)
        subprocess.run(["choco", "pack", "eir.nuspec"], check=True)  # noqa: S603,S607
        print(f"Created Chocolatey package: {packages_dir}/eir.{version}.nupkg")

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"choco pack failed: {e}")
        print("Trying alternative method with NuGet...")

        try:
            # Try with nuget.exe as fallback
            subprocess.run(["nuget", "pack", "eir.nuspec"], check=True)  # noqa: S603,S607
            print(f"Created Chocolatey package with NuGet: {packages_dir}/eir.{version}.nupkg")

        except (subprocess.CalledProcessError, FileNotFoundError) as e2:
            print(f"NuGet pack also failed: {e2}")
            print("Creating package manually as last resort...")

            # Manual creation with proper structure
            import zipfile

            nupkg_path = Path(f"eir.{version}.nupkg")
            with zipfile.ZipFile(nupkg_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add nuspec to root
                zipf.write("eir.nuspec", "eir.nuspec")

                # Add tools directory with correct structure
                tools_dir = Path("tools")
                if tools_dir.exists():
                    for tool_file in tools_dir.rglob("*"):
                        if tool_file.is_file():
                            # Ensure forward slashes in archive paths
                            arcname = str(tool_file).replace("\\", "/")
                            zipf.write(tool_file, arcname)

            print(f"Created Chocolatey package manually: {packages_dir}/{nupkg_path}")

    finally:
        # Always restore original working directory
        os.chdir(original_cwd)


def main():
    """Main packaging process."""
    print("Starting package build process...")

    version = get_version()
    print(f"Building packages for version: {version}")

    # Get OS name and architecture from environment
    os_name = os.environ.get("OS_NAME", platform.system().lower())
    arch = os.environ.get("ARCH", "unknown")

    print(f"Environment: OS_NAME={os_name}, ARCH={arch}")
    print("Available files in dist/:")
    if Path("dist").exists():
        for file in Path("dist").iterdir():
            print(f"  - {file.name}")
    else:
        print("  (dist directory not found)")

    # Run platform-specific package creation based on OS
    if os_name == "macos":
        # Check for macOS binary and update Homebrew formula
        macos_binary = None
        search_pattern = f"eir-{version}-macos-{arch}"
        print(f"Searching for macOS binary with pattern: {search_pattern}")

        # Look for binary with the actual architecture name (universal)
        for file in Path("dist").glob(search_pattern):
            print(f"Found candidate file: {file}")
            if file.is_file():
                macos_binary = file
                break

        if macos_binary:
            sha256_hash = calculate_sha256(macos_binary)
            update_homebrew_formula(version, sha256_hash)
            print(f"Homebrew formula updated for {macos_binary}")
        else:
            print(f"Warning: No macOS binary found for version {version}")
            print(f"Searched for pattern: {search_pattern}")
            print("Available files in dist/:")
            if Path("dist").exists():
                for file in Path("dist").iterdir():
                    print(f"  - {file.name}")

    elif os_name == "linux":
        # Create Debian package
        create_debian_package(version)

    elif os_name == "windows":
        # Create/update Chocolatey package
        create_chocolatey_package(version)

    print(f"\nPackage build complete for {os_name}-{arch}!")
    packages_dir = Path(f"packages-{os_name}-{arch}")
    print(f"Files created in {packages_dir}/ directory:")
    if packages_dir.exists():
        for file in packages_dir.rglob("*"):
            if file.is_file():
                print(f"  - {file.relative_to(packages_dir)}")
    else:
        print("  (no files created)")


if __name__ == "__main__":
    main()
