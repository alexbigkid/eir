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
    formula_path = Path("homebrew/eir.rb")
    content = formula_path.read_text()

    # Update version and SHA256
    content = content.replace("REPLACE_WITH_ACTUAL_SHA256", sha256_hash)
    content = content.replace("REPLACE_WITH_VERSION", version)

    formula_path.write_text(content)
    print(f"Updated Homebrew formula: {formula_path}")


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

        # Create package directory structure
        pkg_dir = Path(f"packages/eir_{version}_{deb_arch}")
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
        control_content = Path("debian/control").read_text(encoding="utf-8")
        # Replace any existing version with the new one
        control_content = re.sub(r'Version:\s+[^\s]+', f'Version: {version}', control_content)
        control_content = control_content.replace(
            "Architecture: amd64", f"Architecture: {deb_arch}"
        )

        control_file = debian_dir / "control"
        control_file.write_text(control_content, encoding="utf-8")

        # Copy other debian files
        for other_file in ["copyright"]:
            if Path(f"debian/{other_file}").exists():
                shutil.copy2(f"debian/{other_file}", debian_dir / other_file)

        # Build the .deb package
        try:
            deb_filename = f"packages/eir_{version}_{deb_arch}.deb"
            subprocess.run(  # noqa: S603,S607
                ["dpkg-deb", "--build", str(pkg_dir), deb_filename], check=True
            )
            print(f"Created Debian package: {deb_filename}")
            created_packages.append(deb_filename)

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Failed to create {deb_arch} Debian package: {e}")
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
            ["dpkg-scanpackages", f"pool/{component}", "/dev/null"],
            capture_output=True,
            text=True,
            check=True,
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
            all_packages_files.extend(
                [f"{component}/binary-{arch}/Packages", f"{component}/binary-{arch}/Packages.gz"]
            )

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
    # Update nuspec file
    nuspec_path = Path("chocolatey/eir.nuspec")
    content = nuspec_path.read_text(encoding="utf-8")
    # Replace any existing version with the new one
    content = re.sub(r'<version>[^<]+</version>', f'<version>{version}</version>', content)
    nuspec_path.write_text(content, encoding="utf-8")

    # Update install script
    install_path = Path("chocolatey/tools/chocolateyinstall.ps1")
    content = install_path.read_text(encoding="utf-8")
    content = re.sub(r"\$version\s*=\s*'[^']*'", f"$version = '{version}'", content)
    content = content.replace("REPLACE_WITH_ACTUAL_CHECKSUM", checksum)
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

    # Create nupkg if choco is available
    try:
        subprocess.run(  # noqa: S603,S607
            ["choco", "pack", "chocolatey/eir.nuspec", "--outputdirectory", "packages"],
            check=True,
        )
        print(f"Created Chocolatey package: packages/eir.{version}.nupkg")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Failed to create Chocolatey package: {e}")
        print("Note: Chocolatey CLI is required to build .nupkg files")


def main():
    """Main packaging process."""
    print("Starting package build process...")

    version = get_version()
    print(f"Building packages for version: {version}")

    # Ensure packages directory exists
    Path("packages").mkdir(exist_ok=True)

    # Check for macOS binary and update Homebrew formula
    macos_binary = None
    for file in Path("dist").glob(f"eir-{version}-macos-*"):
        if file.is_file():
            macos_binary = file
            break

    if macos_binary:
        sha256_hash = calculate_sha256(macos_binary)
        update_homebrew_formula(version, sha256_hash)
        print(f"Homebrew formula updated for {macos_binary}")
    else:
        print(f"Warning: No macOS binary found for version {version}")

    # Create Debian package
    if platform.system().lower() in ["linux", "darwin"]:  # Can build on Linux or macOS
        create_debian_package(version)
    else:
        print("Skipping Debian package creation (requires Linux/macOS)")

    # Create/update Chocolatey package
    create_chocolatey_package(version)

    print("\nPackage build complete!")
    print("Files created in packages/ directory:")
    if Path("packages").exists():
        for file in Path("packages").iterdir():
            if file.is_file():
                print(f"  - {file.name}")


if __name__ == "__main__":
    main()
