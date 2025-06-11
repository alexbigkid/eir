#!/usr/bin/env python3
"""Build script for creating standalone executables with PyInstaller."""

# Ensure all subprocess.run calls use argument lists, not shell=True or str cmd
import subprocess  # noqa: S404
import os
import platform
import shutil
import sys
from pathlib import Path


def get_platform_name():
    """Get the platform name for binary naming."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    platform_map = {
        "darwin": "macos-universal",  # Use universal for macOS to support both Intel A& Apple SoC
        "linux": f"linux-{machine}",
        "windows": f"windows-{machine}",
    }
    return platform_map.get(system, f"{system}-{machine}")


def clean_build_dirs():
    """Clean previous build artifacts."""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 Cleaning {dir_name}...")
            shutil.rmtree(dir_name)


def install_build_deps():
    """Install build dependencies."""
    deps = ["pyinstaller>=6.0"]
    print(f"📦 Installing build dependencies: {', '.join(deps)}")
    subprocess.run([sys.executable, "-m", "pip", "install"] + deps, check=True)  # noqa: S603


def build_executable():
    """Build the standalone executable."""
    platform_name = get_platform_name()
    app_name = "eir"

    # Get version from pyproject.toml
    try:
        import tomllib

        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        version = config["project"]["version"]
    except Exception:
        version = "dev"

    output_name = f"{app_name}-{version}-{platform_name}"

    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",
        "--console",
        "--name",
        output_name,
        "--distpath",
        "dist",
        "--workpath",
        "build",
        "--specpath",
        "build",
        # Include data files
        "--add-data",
        "logging.yaml:.",
        # Hidden imports to ensure all modules are included
        "--hidden-import",
        "eir.cli",
        "--hidden-import",
        "eir.processor",
        "--hidden-import",
        "eir.logger_manager",
        "--hidden-import",
        "eir.abk_common",
        "--hidden-import",
        "eir.constants",
        "--hidden-import",
        "eir.clo",
        "--hidden-import",
        "colorama",
        "--hidden-import",
        "reactivex",
        "--hidden-import",
        "exiftool",
        "--hidden-import",
        "pydngconverter",
        "--hidden-import",
        "PyYAML",
        "--hidden-import",
        "yaml",
        # Optimize
        "--strip",
        "--optimize",
        "2",
        # Entry point
        "src/eir/cli.py",
    ]

    print(f"🔨 Building {app_name} v{version} for {platform_name}...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, check=False)  # noqa: S603
    if result.returncode != 0:
        print("❌ Build failed!")
        sys.exit(1)

    # Handle Windows executable extension
    if platform.system().lower() == "windows":
        old_path = Path(f"dist/{output_name}")
        new_path = Path(f"dist/{output_name}.exe")
        if old_path.exists() and not str(old_path).endswith(".exe"):
            old_path.rename(new_path)
            output_name += ".exe"

    print("✅ Build completed successfully!")
    print(f"📍 Executable location: dist/{output_name}")
    return output_name


def create_archive(executable_name):
    """Create a compressed archive of the binary."""
    version = executable_name.split("-")[1]  # Extract version from filename
    platform_name = get_platform_name()

    # Create archive name
    if platform.system().lower() == "windows":
        archive_name = f"eir-{version}-{platform_name}.zip"

        import zipfile

        with zipfile.ZipFile(f"dist/{archive_name}", "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(f"dist/{executable_name}", executable_name)
            zipf.write("README.md", "README.md")
            zipf.write("LICENSE", "LICENSE")
            if Path("CHANGELOG.md").exists():
                zipf.write("CHANGELOG.md", "CHANGELOG.md")
    else:
        archive_name = f"eir-{version}-{platform_name}.tar.gz"

        subprocess.run(  # noqa: S603
            [
                "tar",
                "-czf",
                f"dist/{archive_name}",
                "-C",
                "dist",
                executable_name,
                "-C",
                "..",
                "README.md",
                "LICENSE",
            ]
            + (["-C", "..", "CHANGELOG.md"] if Path("CHANGELOG.md").exists() else []),
            check=True,
        )

    print(f"📦 Archive created: dist/{archive_name}")
    return archive_name


def test_executable(executable_name):
    """Test the built executable."""
    exe_path = Path(f"dist/{executable_name}")

    if not exe_path.exists():
        print(f"❌ Executable not found: {exe_path}")
        return False

    print(f"🧪 Testing executable: {exe_path}")

    # Test --version
    try:
        # The command uses a trusted, built executable and fixed arguments
        result = subprocess.run(  # noqa: S603
            [str(exe_path), "--version"], capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode == 0:
            print(f"✅ Version test passed: {result.stdout.strip()}")
        else:
            print(f"⚠️  Version test failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("⚠️  Version test timed out")
        return False
    except Exception as e:
        print(f"⚠️  Version test error: {e}")
        return False

    # Test --help
    try:
        result = subprocess.run(  # noqa: S603
            [str(exe_path), "--help"], capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode == 0:
            print("✅ Help test passed")
        else:
            print(f"⚠️  Help test failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"⚠️  Help test error: {e}")
        return False

    return True


def main():
    """Main build process."""
    print("🚀 Starting Eir PyInstaller build process...")
    print(f"🖥️  Platform: {get_platform_name()}")
    print(f"🐍 Python: {sys.version}")

    # Ensure we're in the project root
    if not Path("src/eir").exists():
        print("❌ Error: Must run from project root directory")
        sys.exit(1)

    try:
        clean_build_dirs()
        install_build_deps()
        executable_name = build_executable()

        # Test the executable
        if test_executable(executable_name):
            archive_name = create_archive(executable_name)
            print("✅ Build process completed successfully!")
            print("📁 Files created:")
            print(f"   - dist/{executable_name}")
            print(f"   - dist/{archive_name}")
        else:
            print("⚠️  Build completed but tests failed")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
