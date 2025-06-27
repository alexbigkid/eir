#!/usr/bin/env python3
"""Build script for creating standalone executables with Nuitka."""

import os
import platform
import shutil

# Ensure all subprocess.run calls use argument lists, not shell=True or str cmd
import subprocess  # noqa: S404
import sys
from pathlib import Path


def get_platform_name():
    """Get the platform name for binary naming."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize machine architecture names for consistency
    machine_map = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }
    machine = machine_map.get(machine, machine)

    # Platform-specific naming
    if system == "darwin":
        return "macos-universal"  # macOS builds are universal
    elif system == "linux":
        return f"linux-{machine}"
    elif system == "windows":
        # Windows uses different naming for architectures
        if machine == "aarch64":
            return "windows-arm64"
        else:
            return f"windows-{machine}"
    else:
        return f"{system}-{machine}"


def clean_build_dirs():
    """Clean previous build artifacts."""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_name)


def download_dnglab():
    """Download DNGLab binary for DNG conversion using unified cross-platform script."""
    print(f"Downloading DNGLab for {platform.system()}...")
    print(f"Current working directory: {Path.cwd()}")

    # Run the unified Python download script
    script_path = Path(".github/scripts/download_dnglab.py")
    print(f"Looking for download script: {script_path}")

    if script_path.exists():
        print(f"Found download script: {script_path}")
        print("Running DNGLab download script...")
        result = subprocess.run([sys.executable, str(script_path)], check=False)  # noqa: S603
        if result.returncode == 0:
            print("DNGLab downloaded successfully")
        else:
            print(f"DNGLab download failed with exit code {result.returncode}")
            print("DNG conversion may not work")
    else:
        print(f"DNGLab download script not found: {script_path}")
        print(f"Skipping DNGLab download - not supported on {platform.system()}")


def setup_data_files():
    """Set up data files for Nuitka bundling."""
    # Create a data directory for Nuitka to bundle
    data_dir = Path("nuitka_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir()

    # Copy required data files
    required_files = ["logging.yaml", "pyproject.toml"]
    for file_name in required_files:
        file_path = Path(file_name)
        if file_path.exists():
            shutil.copy2(file_path, data_dir / file_name)
            print(f"Copied {file_name} to data directory")
        else:
            print(f"Warning: {file_name} not found")

    return data_dir


def setup_dnglab_bundle():
    """Set up DNGLab binary for bundling."""
    system_name = platform.system().lower()
    dnglab_path = None

    if system_name == "linux":
        machine = platform.machine().lower()
        dnglab_arch = "aarch64" if machine in ["aarch64", "arm64"] else "x86_64"
        dnglab_path = Path(f"build/linux/tools/{dnglab_arch}/dnglab")
    elif system_name == "windows":
        machine = platform.machine().lower()
        dnglab_arch = "arm64" if machine in ["aarch64", "arm64"] else "x64"
        dnglab_path = Path(f"build/windows/tools/{dnglab_arch}/dnglab.exe")
    elif system_name == "darwin":
        machine = platform.machine().lower()
        dnglab_arch = "arm64" if machine in ["aarch64", "arm64"] else "x86_64"
        dnglab_path = Path(f"build/darwin/tools/{dnglab_arch}/dnglab")

    if dnglab_path and dnglab_path.exists():
        # Create tools directory structure in nuitka_data
        data_dir = Path("nuitka_data")
        tools_dir = data_dir / "tools" / system_name / dnglab_arch
        tools_dir.mkdir(parents=True, exist_ok=True)

        # Copy DNGLab binary
        dest_path = tools_dir / dnglab_path.name
        shutil.copy2(dnglab_path, dest_path)

        file_size = dest_path.stat().st_size
        print(f"Bundled DNGLab binary: {dest_path} (size: {file_size} bytes)")

        # Make executable on Unix systems
        if system_name != "windows":
            os.chmod(dest_path, 0o755)  # noqa: S103

        return True
    else:
        print(f"DNGLab binary not found at: {dnglab_path}")
        return False


def build_executable():
    """Build the standalone executable with Nuitka."""
    platform_name = get_platform_name()
    app_name = "eir"

    # Get version and metadata from pyproject.toml
    try:
        import tomllib

        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        project = config.get("project", {})
        version = project.get("version", "dev")

        # Generate a build_constants.py file with embedded metadata
        build_constants = f'''"""Build-time constants generated by build script."""

VERSION = "{version}"
NAME = "{project.get("name", "eir")}"
LICENSE = "{project.get("license", {}).get("text", "MIT")}"
KEYWORDS = {project.get("keywords", ["unknown"])}
AUTHORS = {project.get("authors", [{"name": "ABK", "email": "unknown"}])}
MAINTAINERS = {project.get("maintainers", [{"name": "ABK", "email": "unknown"}])}
'''

        with open("src/eir/build_constants.py", "w") as f:
            f.write(build_constants)
        print(f"Generated build_constants.py with version {version}")

    except Exception as e:
        print(f"Error reading pyproject.toml: {e}")
        version = "dev"

    output_name = f"{app_name}-{version}-{platform_name}"

    download_dnglab()

    # Set up data files and DNGLab bundling
    data_dir = setup_data_files()
    dnglab_bundled = setup_dnglab_bundle()

    if not dnglab_bundled:
        print("Warning: DNGLab binary not bundled - DNG conversion may not work")

    # Handle Windows executable extension
    if platform.system().lower() == "windows":
        output_name += ".exe"

    # Nuitka command (use uv run to ensure Nuitka is available)
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        f"--output-filename={output_name}",
        "--output-dir=dist",
        # Include data files
        f"--include-data-dir={data_dir}=.",
        # Performance optimizations
        "--enable-plugin=anti-bloat",
        "--show-anti-bloat-changes",
        # Disable problematic features that can cause issues
        "--assume-yes-for-downloads",
    ]

    # Add platform-specific options
    if platform.system().lower() == "windows":
        cmd.extend(["--windows-console-mode=force"])
        if Path("src/eir/icon.ico").exists():
            cmd.append("--windows-icon-from-ico=src/eir/icon.ico")
    elif platform.system().lower() == "darwin":
        # For macOS, don't use app bundle for CLI tool
        pass
    elif platform.system().lower() == "linux":
        pass

    # Add entry point
    cmd.append("src/eir/cli.py")

    print(f"Building {app_name} v{version} for {platform_name} with Nuitka...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, check=False)  # noqa: S603
    if result.returncode != 0:
        print("Build failed!")
        sys.exit(1)

    print("Build completed successfully!")
    print(f"Executable location: dist/{output_name}")

    # Clean up temporary data directory
    if data_dir.exists():
        shutil.rmtree(data_dir)
        print("Cleaned up temporary data directory")

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

    print(f"Archive created: dist/{archive_name}")
    return archive_name


def test_executable(executable_name):
    """Test the built executable."""
    exe_path = Path(f"dist/{executable_name}")

    if not exe_path.exists():
        print(f"Executable not found: {exe_path}")
        return False

    print(f"Testing executable: {exe_path}")

    # Test --version
    try:
        result = subprocess.run(  # noqa: S603
            [str(exe_path.resolve()), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode == 0:
            print(f"Version test passed: {result.stdout.strip()}")
        else:
            print(f"Version test failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("Version test timed out")
        return False
    except Exception as e:
        print(f"Version test error: {e}")
        return False

    # Test --help
    try:
        result = subprocess.run(  # noqa: S603
            [str(exe_path.resolve()), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode == 0:
            print("Help test passed")
        else:
            print(f"Help test failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"Help test error: {e}")
        return False

    return True


def main():
    """Main build process."""
    print("Starting Eir Nuitka build process...")
    print(f"Platform: {get_platform_name()}")
    print(f"Python: {sys.version}")

    # Ensure we're in the project root
    if not Path("src/eir").exists():
        print("Error: Must run from project root directory")
        sys.exit(1)

    try:
        clean_build_dirs()
        executable_name = build_executable()

        # Test the executable
        if test_executable(executable_name):
            archive_name = create_archive(executable_name)
            print("Build process completed successfully!")
            print("Files created:")
            print(f"   - dist/{executable_name}")
            print(f"   - dist/{archive_name}")
        else:
            print("Build completed but tests failed")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
