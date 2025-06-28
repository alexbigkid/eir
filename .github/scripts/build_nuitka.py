#!/usr/bin/env python3
"""Build script for creating standalone executables with Nuitka."""

import os
import platform
import shutil

# Ensure all subprocess.run calls use argument lists, not shell=True or str cmd
import subprocess  # noqa: S404
import sys
from pathlib import Path

from download_dnglab import DNGLabDownloader


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
    try:
        # Use the DNGLab downloader directly
        downloader = DNGLabDownloader()
        success = downloader.download_and_setup()

        if not success:
            print("ERROR: DNGLab download failed - build cannot continue")
            print("CRITICAL: Exiting build process due to missing DNGLab binary")
            sys.exit(1)

    except ImportError as e:
        print(f"ERROR: Could not import DNGLab downloader: {e}")
        print("CRITICAL: Exiting build process due to import failure")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: DNGLab download failed: {e}")
        print("CRITICAL: Exiting build process due to download failure")
        sys.exit(1)


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
    machine = platform.machine().lower()

    print("=== DNGLab Bundle Setup ===")
    print(f"System: {system_name}")
    print(f"Machine: {machine}")

    match system_name:
        case "linux":
            dnglab_arch = "aarch64" if machine in ["aarch64", "arm64"] else "x64"
            dnglab_path = Path(f"build/linux/tools/{dnglab_arch}/dnglab")
        case "windows":
            dnglab_arch = "arm64" if machine in ["aarch64", "arm64"] else "x64"
            dnglab_path = Path(f"build/windows/tools/{dnglab_arch}/dnglab.exe")
        case "darwin":
            dnglab_arch = "arm64" if machine in ["aarch64", "arm64"] else "x86_64"
            dnglab_path = Path(f"build/darwin/tools/{dnglab_arch}/dnglab")
        case _:
            print(f"Unsupported platform: {system_name}")
            return False

    print(f"Looking for DNGLab at: {dnglab_path.absolute()}")
    print(f"DNGLab exists: {dnglab_path.exists()}")

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
        print(f"Absolute dest path: {dest_path.absolute()}")

        # Verify the bundled structure
        print("=== Nuitka Data Directory Structure ===")
        try:
            for item in data_dir.rglob("*"):
                print(f"  {item}")
        except Exception as e:
            print(f"Could not list nuitka_data contents: {e}")

        # Make executable on Unix systems
        if system_name != "windows":
            os.chmod(dest_path, 0o755)  # noqa: S103

        return True
    else:
        print(f"DNGLab binary not found at: {dnglab_path}")
        print(f"Absolute path checked: {dnglab_path.absolute()}")

        # Debug: Show what's in the build directory
        build_dir = Path("build")
        if build_dir.exists():
            print("=== Build Directory Contents ===")
            try:
                for item in build_dir.rglob("*"):
                    if "dnglab" in item.name.lower():
                        print(f"  Found DNGLab file: {item}")
                    elif item.is_dir():
                        print(f"  Directory: {item}")
            except Exception as e:
                print(f"Could not list build directory: {e}")
        else:
            print("Build directory does not exist")

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

    # Enhanced debugging for data directory bundling
    print("=== Nuitka Data Directory Info ===")
    print(f"Data dir path: {data_dir}")
    print(f"Data dir absolute: {data_dir.absolute()}")
    print(f"Data dir exists: {data_dir.exists()}")

    if data_dir.exists():
        print("Data dir contents:")
        try:
            for item in data_dir.rglob("*"):
                print(f"  {item}")
        except Exception as e:
            print(f"Could not list data dir: {e}")

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
        # Performance optimizations
        "--enable-plugin=anti-bloat",
        "--show-anti-bloat-changes",
        # Disable problematic features that can cause issues
        "--assume-yes-for-downloads",
        # Enhanced debugging for build process
        "--show-progress",
        "--show-memory",
    ]

    # Handle data directory inclusion with platform-specific approach
    if platform.system().lower() == "windows":
        # Windows: Use individual file inclusion due to Nuitka subdirectory bundling issues

        # Include top-level data files
        for top_level_file in data_dir.glob("*"):
            if top_level_file.is_file():
                file_forward = str(top_level_file.absolute()).replace("\\", "/")
                cmd.append(f"--include-data-files={file_forward}={top_level_file.name}")
                print(f"Windows: Including data file: {top_level_file.name}")

        # Include DNGLab binary explicitly with full path structure
        for tool_file in data_dir.glob("tools/**/*"):
            if tool_file.is_file():
                # Calculate relative path from data_dir
                rel_path = tool_file.relative_to(data_dir)
                file_forward = str(tool_file.absolute()).replace("\\", "/")
                rel_path_forward = str(rel_path).replace("\\", "/")
                cmd.append(f"--include-data-files={file_forward}={rel_path_forward}")
                print(f"Windows: Including tool file: {rel_path_forward}")

        print("Windows: Using individual file inclusion instead of data dir")
    else:
        # Linux/macOS: Use standard approach
        cmd.append(f"--include-data-dir={data_dir.absolute()}=.")
        print(f"Unix: Using standard path for Nuitka: {data_dir.absolute()}")

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

    # Verify the build output exists
    exe_path = Path(f"dist/{output_name}")
    if exe_path.exists():
        exe_size = exe_path.stat().st_size
        print(f"Executable size: {exe_size} bytes")

        # Additional verification for Windows bundling
        if platform.system().lower() == "windows":
            print("=== Windows Build Verification ===")
            print("Note: DNGLab bundling will be verified during runtime in integration tests")
            print("Expected bundled path structure: <extraction>/tools/windows/x64/dnglab.exe")
    else:
        print(f"ERROR: Executable not found at expected location: {exe_path}")

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
