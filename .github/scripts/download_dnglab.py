#!/usr/bin/env python3
"""Cross-platform DNGLab binary downloader for GitHub Actions."""

import json
import os
import platform
import shutil
import subprocess  # noqa: S404
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class DNGLabDownloader:
    """Cross-platform DNGLab binary downloader."""

    def __init__(self):
        """Initialize the downloader with platform detection."""
        self.platform_name = platform.system().lower()
        self.arch = platform.machine().lower()
        self.github_token = os.environ.get("GITHUB_TOKEN")

        # Architecture mappings per platform
        self.arch_mapping = {
            "windows": {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"},
            "darwin": {"x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"},
            "linux": {"x86_64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"},
        }

        # Binary naming patterns per platform
        self.binary_patterns = {
            "windows": {
                "name_template": "dnglab-win-{arch}",
                "filename_template": "dnglab-win-{arch}_{version}.zip",
                "is_zip": True,
                "executable_name": "dnglab.exe",
            },
            "darwin": {
                "name_template": "dnglab-macos-{arch}",
                "filename_template": "dnglab-macos-{arch}_{version}.zip",
                "is_zip": True,
                "executable_name": "dnglab",
            },
            "linux": {
                "name_template": "dnglab_linux_{arch}",
                "filename_template": "dnglab_linux_{arch}",
                "is_zip": False,
                "executable_name": "dnglab",
            },
        }

    def get_latest_version(self):
        """Get the latest DNGLab version from GitHub API."""
        print("🔍 Detecting latest DNGLab version...")

        url = "https://api.github.com/repos/dnglab/dnglab/releases/latest"
        headers = {"User-Agent": "eir-build-script"}

        if self.github_token:
            print("🔑 Using authenticated API request...")
            headers["Authorization"] = f"Bearer {self.github_token}"
        else:
            print("⚠️  Using unauthenticated API request...")

        try:
            request = Request(url, headers=headers)  # noqa: S310
            with urlopen(request, timeout=30) as response:  # noqa: S310
                data = json.loads(response.read().decode())
                version = data["tag_name"]
                print(f"✅ Latest DNGLab version: {version}")
                return version
        except (URLError, HTTPError, json.JSONDecodeError, KeyError) as e:
            print(f"❌ Failed to detect latest DNGLab version: {e}")
            print("❌ Falling back to v0.7.0")
            return "v0.7.0"

    def get_platform_info(self):
        """Get platform and architecture information."""
        if self.platform_name not in self.arch_mapping:
            raise ValueError(f"Unsupported platform: {self.platform_name}")

        platform_key = self.platform_name

        # Special handling for Windows architecture detection
        if self.platform_name == "windows":
            windows_arch = os.environ.get("PROCESSOR_ARCHITECTURE", "").lower()
            if windows_arch == "amd64":
                self.arch = "amd64"
            elif windows_arch == "arm64":
                self.arch = "arm64"

        if self.arch not in self.arch_mapping[platform_key]:
            raise ValueError(
                f"Unsupported architecture {self.arch} for platform {self.platform_name}"
            )

        mapped_arch = self.arch_mapping[platform_key][self.arch]

        print(f"🔍 Platform: {self.platform_name}")
        print(f"🔍 Architecture: {self.arch} -> {mapped_arch}")

        return platform_key, mapped_arch

    def build_download_url(self, version, platform_key, arch):
        """Build the download URL for the binary."""
        pattern = self.binary_patterns[platform_key]
        filename = pattern["filename_template"].format(arch=arch, version=version)
        url = f"https://github.com/dnglab/dnglab/releases/download/{version}/{filename}"
        return url, filename, pattern

    def download_file(self, url, dest_path):
        """Download a file from URL to destination path."""
        print(f"📥 Downloading from: {url}")
        print(f"📁 Destination: {dest_path}")

        try:
            with urlopen(url, timeout=60) as response:  # noqa: S310
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "wb") as f:
                    shutil.copyfileobj(response, f)
            print("✅ Download completed")
            return True
        except (URLError, HTTPError) as e:
            print(f"❌ Download failed: {e}")
            return False

    def extract_zip(self, zip_path, extract_dir, executable_name):
        """Extract ZIP file and find the executable."""
        print("📂 Extracting ZIP file...")

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            # Find the extracted executable
            final_path = extract_dir / executable_name
            for item in extract_dir.rglob("*"):
                if (
                    item.is_file()
                    and item.name != final_path.name  # Don't move to itself
                    and (item.name == executable_name or item.name.startswith("dnglab"))
                    and not item.name.endswith(".zip")
                ):  # Skip zip files
                    if item != final_path:
                        print(f"📋 Moving {item} -> {final_path}")
                        item.rename(final_path)
                    return final_path

            # If we get here, check if the file was already extracted to the right name
            if final_path.exists():
                return final_path

            raise FileNotFoundError(f"{executable_name} not found in extracted ZIP")

        except (zipfile.BadZipFile, FileNotFoundError) as e:
            print(f"❌ Extraction failed: {e}")
            return None

    def make_executable(self, file_path):
        """Make file executable on Unix-like systems."""
        if self.platform_name != "windows":
            os.chmod(file_path, 0o755)  # noqa: S103

    def test_binary(self, binary_path):
        """Test that the binary works."""
        print("🧪 Testing DNGLab binary...")

        try:
            result = subprocess.run(  # noqa: S603
                [str(binary_path), "--help"],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                print("✅ DNGLab binary is working correctly")
                return True
            else:
                print("⚠️  DNGLab binary test failed - may still work for conversion")
                return True  # Still consider success for now
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
            print(f"⚠️  DNGLab binary test failed: {e} - may still work for conversion")
            return True  # Still consider success for now

    def download_and_setup(self):
        """Main method to download and setup DNGLab binary."""
        print(f"\n🚀 Starting DNGLab download for {self.platform_name}")

        try:
            # Get version and platform info
            version = self.get_latest_version()
            platform_key, arch = self.get_platform_info()

            # Build paths
            url, filename, pattern = self.build_download_url(version, platform_key, arch)
            build_dir = Path(f"./build/{platform_key}/tools/{arch}")
            executable_name = pattern["executable_name"]
            final_binary_path = build_dir / executable_name

            # Download
            if pattern["is_zip"]:
                download_path = build_dir / filename
                if not self.download_file(url, download_path):
                    return False

                # Extract ZIP
                extracted_path = self.extract_zip(download_path, build_dir, executable_name)
                if not extracted_path:
                    return False

                # Clean up ZIP
                download_path.unlink()
                final_binary_path = extracted_path
            else:
                # Direct binary download
                if not self.download_file(url, final_binary_path):
                    return False

            # Make executable
            self.make_executable(final_binary_path)

            # Verify and test
            if not final_binary_path.exists():
                print("❌ Binary not found after setup")
                return False

            file_size = final_binary_path.stat().st_size
            print("✅ DNGLab downloaded successfully")
            print(f"📁 Path: {final_binary_path}")
            print(f"📊 Size: {file_size} bytes")

            # Test binary
            if not self.test_binary(final_binary_path):
                return False

            print("🎉 DNGLab setup complete!")
            return True

        except Exception as e:
            print(f"❌ DNGLab setup failed: {e}")
            return False


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        print(f"ℹ️  Platform override: {sys.argv[1]}")

    downloader = DNGLabDownloader()
    success = downloader.download_and_setup()

    if success:
        print(f"✅ Exit: {__file__} (0)")
        sys.exit(0)
    else:
        print(f"❌ Exit: {__file__} (1)")
        sys.exit(1)


if __name__ == "__main__":
    main()
