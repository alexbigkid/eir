"""DNGLab binary management strategies for different platforms."""

import logging
import os
import platform
import shutil
import subprocess  # noqa: S404
import sys
from abc import ABC, abstractmethod
from pathlib import Path


class DNGLabBinaryStrategy(ABC):
    """Abstract base class for DNGLab binary location strategies."""

    def __init__(self, logger: logging.Logger):
        """Initialize the strategy with a logger."""
        self.logger = logger

    @abstractmethod
    def get_binary_path(self) -> str | None:
        """Get the path to the DNGLab binary for this platform."""

    @abstractmethod
    def get_architecture_mapping(self) -> str:
        """Get the architecture string used for this platform."""

    @abstractmethod
    def get_binary_filename(self) -> str:
        """Get the binary filename for this platform."""

    def _find_project_root(self) -> Path:
        """Find project root by looking for pyproject.toml."""
        search_paths = [Path.cwd(), Path(__file__).parent.parent.parent]

        for start in search_paths:
            for parent in [start, *start.parents]:
                if (parent / "pyproject.toml").exists():
                    return parent

        return Path.cwd()

    def _check_system_path(self, binary_name: str) -> str | None:
        """Check if binary is available in system PATH."""
        binary_path = shutil.which(binary_name)
        if binary_path:
            self.logger.info(f"Found DNGLab in system PATH: {binary_path}")
            return binary_path
        else:
            self.logger.info("DNGLab not found in system PATH")
            return None

    def _check_bundled_binary(self, system_name: str, arch: str, binary_name: str) -> str | None:
        """Check for bundled binary in Nuitka or PyInstaller bundle."""
        # Check if we're running as a bundled executable
        bundled_detection = self._detect_bundled_execution()
        if not bundled_detection["is_bundled"]:
            self.logger.info("Not running as bundled executable - skipping bundled binary search")
            return None

        # Get the bundled binary path based on the bundle type
        dnglab_bundled = self._get_bundled_binary_path(bundled_detection, system_name, arch, binary_name)

        # Verify the bundled binary exists
        if dnglab_bundled.exists():
            self.logger.info(f"Found bundled DNGLab: {dnglab_bundled}")
            return str(dnglab_bundled)

        self.logger.warning(f"Bundled DNGLab not found at: {dnglab_bundled}")
        self._debug_extraction_directory()
        return None

    def _detect_bundled_execution(self) -> dict[str, bool | str]:
        """Detect if we're running as a bundled executable and what type."""
        current_file_path = Path(__file__).absolute()
        current_path_str = str(current_file_path).lower()

        # Check for various Nuitka onefile patterns (including Windows short names)
        is_nuitka_temp = (
            ("temp" in current_path_str and "onefil" in current_path_str)  # Windows: ONEFIL~1
            or ("temp" in current_path_str and "onefile" in current_path_str)  # Full name
            or "/tmp/onefile_" in str(current_file_path)  # Linux pattern
            or "\\onefil" in current_path_str  # Windows backslash pattern
            or "appdata" in current_path_str  # Windows AppData temp extractions
            or ("windows" in current_path_str and "temp" in current_path_str)  # Windows temp
        )

        is_nuitka_onefile = (
            "/tmp/onefile_" in str(current_file_path)  # Linux pattern
            or "onefile" in current_path_str  # General onefile pattern
            or "onefil" in current_path_str  # Windows short name pattern
            or is_nuitka_temp  # Temp extraction patterns
        )

        is_frozen = getattr(sys, "frozen", False)
        is_pyinstaller = hasattr(sys, "_MEIPASS")

        # Log detection info at debug level
        self.logger.debug(
            f"Bundled detection: frozen={is_frozen}, pyinstaller={is_pyinstaller}, nuitka_onefile={is_nuitka_onefile}"
        )

        return {
            "is_bundled": is_frozen or is_pyinstaller or is_nuitka_onefile,
            "is_pyinstaller": is_pyinstaller,
            "is_nuitka_onefile": is_nuitka_onefile,
            "current_path": str(current_file_path),
        }

    def _get_bundled_binary_path(self, detection: dict[str, bool | str], system_name: str, arch: str, binary_name: str) -> Path:
        """Get the path to the bundled binary based on bundle type."""
        # Try PyInstaller first for backward compatibility (_MEIPASS)
        bundle_dir = getattr(sys, "_MEIPASS", "")
        if bundle_dir and detection["is_pyinstaller"]:
            self.logger.info(f"Using PyInstaller bundle directory: {bundle_dir}")
            return Path(bundle_dir) / "tools" / system_name / arch / binary_name

        # Handle Nuitka onefile extraction
        return self._get_nuitka_bundled_path(system_name, arch, binary_name)

    def _get_nuitka_bundled_path(self, system_name: str, arch: str, binary_name: str) -> Path:
        """Get the bundled binary path for Nuitka onefile."""
        # Method 1: Check for sys.executable's directory (Nuitka onefile extraction)
        try:
            import sys

            executable_dir = Path(sys.executable).parent
            tools_path_1 = executable_dir / "tools" / system_name / arch / binary_name
            if tools_path_1.exists():
                self.logger.info(f"Found bundled DNGLab via executable dir: {tools_path_1}")
                return tools_path_1
        except Exception as e:
            self.logger.debug(f"Method 1 failed: {e}")

        # Method 2: Check current working directory and its parents
        try:
            cwd = Path.cwd()
            for check_dir in [cwd, cwd.parent, cwd.parent.parent]:
                tools_path_2 = check_dir / "tools" / system_name / arch / binary_name
                if tools_path_2.exists():
                    self.logger.info(f"Found bundled DNGLab via working dir: {tools_path_2}")
                    return tools_path_2
        except Exception as e:
            self.logger.debug(f"Method 2 failed: {e}")

        # Method 3: Check __file__ location and traverse up (main approach)
        try:
            current_file_dir = Path(__file__).parent
            extraction_root = self._find_extraction_root(current_file_dir)
            tools_path_3 = extraction_root / "tools" / system_name / arch / binary_name
            if tools_path_3.exists():
                self.logger.info(f"Found bundled DNGLab via extraction root: {tools_path_3}")
                return tools_path_3
        except Exception as e:
            self.logger.debug(f"Method 3 failed: {e}")

        # Method 4: Brute force search in temp directories (Windows specific)
        if system_name == "windows":
            try:
                import tempfile

                temp_dir = Path(tempfile.gettempdir())
                # Look for Nuitka onefile patterns in temp
                for item in temp_dir.iterdir():
                    if item.is_dir() and ("onefile" in item.name.lower() or "onefil" in item.name.lower()):
                        tools_path_4 = item / "tools" / system_name / arch / binary_name
                        if tools_path_4.exists():
                            self.logger.info(f"Found bundled DNGLab via temp search: {tools_path_4}")
                            return tools_path_4

                        # Also check one level down for eir subdirectory
                        eir_tools_path = item / "eir" / "tools" / system_name / arch / binary_name
                        if eir_tools_path.exists():
                            self.logger.info(f"Found bundled DNGLab in eir subdir: {eir_tools_path}")
                            return eir_tools_path
            except Exception as e:
                self.logger.debug(f"Method 4 failed: {e}")

        # If all methods failed, return the best guess from Method 3
        fallback_path = self._find_extraction_root(Path(__file__).parent) / "tools" / system_name / arch / binary_name
        self.logger.warning(f"All detection methods failed. Using fallback: {fallback_path}")
        return fallback_path

    def _debug_windows_extraction(self, extraction_root: Path, system_name: str, arch: str, binary_name: str) -> None:
        """Debug Windows extraction directory structure."""
        try:
            if extraction_root.exists():
                items = list(extraction_root.iterdir())
                self.logger.debug(f"Extraction root contains {len(items)} items")

                # Check if tools directory exists
                tools_found = any(item.is_dir() and item.name.lower() == "tools" for item in items)
                if not tools_found:
                    self.logger.warning("No 'tools' directory found in extraction root")
            else:
                self.logger.warning(f"Extraction root does not exist: {extraction_root}")
        except Exception as e:
            self.logger.debug(f"Could not analyze extraction directory: {e}")

    def _find_extraction_root(self, start_dir: Path) -> Path:
        """Find the extraction root directory containing bundled data."""
        self.logger.info(f"Finding extraction root starting from: {start_dir}")

        # Special case: If we're running from inside an 'eir' directory within a Nuitka
        # extraction, we need to go up to find the actual extraction root
        if start_dir.name == "eir":
            # Check if the parent directory has Nuitka patterns
            parent_str = str(start_dir.parent).lower()
            nuitka_patterns = ["onefile_", "onefil"]
            if any(pattern in parent_str for pattern in nuitka_patterns):
                self.logger.info(f"Detected 'eir' subdirectory in Nuitka extraction: {start_dir}")
                candidate_root = start_dir.parent
                if (candidate_root / "tools").exists():
                    self.logger.info(f"Found tools directory at parent: {candidate_root}")
                    return candidate_root
                else:
                    self.logger.info(f"Parent has no tools, using as extraction root: {candidate_root}")
                    return candidate_root

        extraction_root = start_dir
        levels_checked = 0
        max_levels = 8  # Increase max levels to handle deeper nesting

        while extraction_root.parent != extraction_root and levels_checked < max_levels:
            self.logger.debug(f"Checking level {levels_checked}: {extraction_root}")

            # Check if this directory contains the tools directory
            tools_path = extraction_root / "tools"
            if tools_path.exists():
                self.logger.info(f"Found tools directory at: {extraction_root}")
                break

            # Check if we're in a Nuitka extraction directory pattern
            # Look for onefile patterns in the path components
            nuitka_patterns = ["onefile_", "onefil"]  # Include Windows short name pattern

            # Check if current directory name suggests it's a Nuitka extraction directory
            current_dir_name = extraction_root.name.lower()
            is_nuitka_extraction = any(pattern in current_dir_name for pattern in nuitka_patterns)

            # Also check if any parent directories have nuitka patterns
            has_nuitka_pattern = any(
                any(pattern in part.lower() for pattern in nuitka_patterns) for part in extraction_root.parts
            )

            if is_nuitka_extraction or has_nuitka_pattern:
                self.logger.info(f"Found Nuitka extraction pattern in path: {extraction_root}")
                # Look for tools in parent directories first, then current directory
                # For Nuitka onefile, the tools are usually in the extraction root,
                # not in the subdirectory where our code runs
                search_dirs = [
                    extraction_root.parent,  # Most likely location for Nuitka onefile
                    extraction_root.parent.parent,
                    extraction_root.parent.parent.parent,
                    extraction_root,  # Check current directory last
                ]

                for check_dir in search_dirs:
                    if check_dir.exists() and (check_dir / "tools").exists():
                        self.logger.info(f"Found tools directory at: {check_dir}")
                        extraction_root = check_dir
                        return extraction_root

                # If we found a Nuitka pattern but no tools, use the parent directory
                # as that's where the extraction root should be for onefile bundles
                self.logger.warning(f"Found Nuitka pattern but no tools. Using parent: {extraction_root.parent}")
                extraction_root = extraction_root.parent
                break

            extraction_root = extraction_root.parent
            levels_checked += 1

        # If we couldn't find a tools directory, check if we hit the search limit
        if levels_checked >= max_levels:
            self.logger.warning(
                f"Could not find tools directory after searching {max_levels} levels up from "
                f"{start_dir}. Using last checked directory: {extraction_root}"
            )

        self.logger.info(f"Final extraction root: {extraction_root}")
        return extraction_root

    def _debug_extraction_directory(self) -> None:
        """Debug helper to check extraction directory for tools."""
        try:
            extraction_dir = Path(__file__).parent
            levels_checked = 0
            max_debug_levels = 3

            while extraction_dir.parent != extraction_dir and levels_checked < max_debug_levels:
                nuitka_patterns = ["onefile_", "onefil"]
                if any(any(pattern in name.lower() for pattern in nuitka_patterns) for name in extraction_dir.parts):
                    break
                extraction_dir = extraction_dir.parent
                levels_checked += 1

            # Check for tools directory
            tools_dir = extraction_dir / "tools"
            if tools_dir.exists():
                self.logger.debug(f"Found tools directory at: {tools_dir}")
            else:
                self.logger.debug(f"No tools directory found in: {extraction_dir}")
        except Exception as e:
            self.logger.debug(f"Could not check extraction directory: {e}")

    def _check_local_build(self, system_name: str, arch: str, binary_name: str) -> str | None:
        """Check for binary in local build directory (development)."""
        project_root = self._find_project_root()
        dnglab_local = project_root / "build" / system_name / "tools" / arch / binary_name

        self.logger.info(f"Checking local build directory: {dnglab_local}")

        if dnglab_local.exists():
            self.logger.info(f"Found local DNGLab: {dnglab_local}")
            return str(dnglab_local.absolute())

        self.logger.info(f"Local DNGLab not found: {dnglab_local}")
        return None

    def _make_executable(self, binary_path: str) -> bool:
        """Make binary executable on Unix-like systems."""
        try:
            if not os.access(binary_path, os.X_OK):
                self.logger.warning(f"DNGLab binary is not executable: {binary_path}")
                self.logger.info("Attempting to make DNGLab executable...")
                os.chmod(binary_path, 0o755)  # noqa: S103
                self.logger.info("Successfully made DNGLab executable")
            return True
        except (OSError, PermissionError) as e:
            self.logger.error(f"Failed to make DNGLab executable: {e}")
            return False


class LinuxDNGLabStrategy(DNGLabBinaryStrategy):
    """DNGLab binary strategy for Linux platforms."""

    def get_architecture_mapping(self) -> str:
        """Get Linux architecture mapping."""
        machine = platform.machine().lower()
        return "aarch64" if machine in ["aarch64", "arm64"] else "x64"

    def get_binary_filename(self) -> str:
        """Get Linux binary filename."""
        return "dnglab"

    def get_binary_path(self) -> str | None:
        """Get DNGLab binary path for Linux."""
        system_name = "linux"
        arch = self.get_architecture_mapping()
        binary_name = self.get_binary_filename()
        machine = platform.machine().lower()

        self.logger.debug(
            f"Searching for DNGLab bin - system: {system_name}, machine: {machine}, mapped_arch: {arch}, bin_name: {binary_name}"
        )

        # Try bundled binary first
        binary_path = self._check_bundled_binary(system_name, arch, binary_name)
        if binary_path:
            self._make_executable(binary_path)
            return binary_path

        # Try system PATH
        binary_path = self._check_system_path(binary_name)
        if binary_path:
            return binary_path

        # Try local build directory
        binary_path = self._check_local_build(system_name, arch, binary_name)
        if binary_path:
            self._make_executable(binary_path)
            return binary_path

        self.logger.warning("No DNGLab binary found in any search location")
        return None


class WindowsDNGLabStrategy(DNGLabBinaryStrategy):
    """DNGLab binary strategy for Windows platforms."""

    def get_architecture_mapping(self) -> str:
        """Get Windows architecture mapping."""
        machine = platform.machine().lower()
        return "arm64" if machine in ["aarch64", "arm64"] else "x64"

    def get_binary_filename(self) -> str:
        """Get Windows binary filename."""
        return "dnglab.exe"

    def get_binary_path(self) -> str | None:
        """Get DNGLab binary path for Windows."""
        system_name = "windows"
        arch = self.get_architecture_mapping()
        binary_name = self.get_binary_filename()
        machine = platform.machine().lower()

        self.logger.debug(
            f"Windows DNGLab search: system={system_name}, machine={machine}, mapped_arch={arch}, binary_name={binary_name}"
        )

        # Try bundled binary first
        binary_path = self._check_bundled_binary(system_name, arch, binary_name)
        if binary_path:
            self.logger.info(f"Found bundled DNGLab at {binary_path}")
            return binary_path

        # Try system PATH
        binary_path = self._check_system_path(binary_name)
        if binary_path:
            return binary_path

        # Try local build directory
        binary_path = self._check_local_build(system_name, arch, binary_name)
        if binary_path:
            return binary_path

        self.logger.warning("No DNGLab binary found in any search location")
        return None


class MacOSAdobeDNGStrategy(DNGLabBinaryStrategy):
    """Adobe DNG Converter strategy for macOS platforms."""

    def get_architecture_mapping(self) -> str:
        """Get macOS architecture mapping (not used for Adobe DNG Converter)."""
        return "universal"

    def get_binary_filename(self) -> str:
        """Get Adobe DNG Converter binary filename."""
        return "Adobe DNG Converter"

    def get_binary_path(self) -> str | None:
        """Get Adobe DNG Converter binary path for macOS."""
        self.logger.info("Searching for Adobe DNG Converter on macOS")

        # Try common Adobe DNG Converter installation paths
        adobe_paths = [
            "/Applications/Adobe DNG Converter.app/Contents/MacOS/Adobe DNG Converter",
            "/usr/local/bin/Adobe DNG Converter",
            "/opt/homebrew/Caskroom/adobe-dng-converter/*/Adobe DNG Converter.app/Contents/MacOS/Adobe DNG Converter",
        ]

        for path_pattern in adobe_paths:
            if "*" in path_pattern:
                # Handle glob patterns for homebrew cask installations
                import glob

                matching_paths = glob.glob(path_pattern)
                for path in matching_paths:
                    if Path(path).exists():
                        self.logger.info(f"Found Adobe DNG Converter at: {path}")
                        return path
            else:
                if Path(path_pattern).exists():
                    self.logger.info(f"Found Adobe DNG Converter at: {path_pattern}")
                    return path_pattern

        # Try system PATH
        binary_path = self._check_system_path("Adobe DNG Converter")
        if binary_path:
            return binary_path

        # Check if Adobe DNG Converter is installed via Homebrew Cask
        try:
            result = subprocess.run(
                ["brew", "list", "adobe-dng-converter"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,  # noqa: S603,S607
            )
            if result.returncode == 0:
                self.logger.info("Adobe DNG Converter is installed via Homebrew Cask")
                # Try to find the installation path
                cask_info = subprocess.run(
                    ["brew", "--prefix"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    check=False,  # noqa: S603,S607
                )
                if cask_info.returncode == 0:
                    brew_prefix = cask_info.stdout.strip()
                    cask_path = f"{brew_prefix}/Caskroom/adobe-dng-converter"
                    if Path(cask_path).exists():
                        # Find the version directory
                        for version_dir in Path(cask_path).iterdir():
                            if version_dir.is_dir():
                                app_path = version_dir / "Adobe DNG Converter.app" / "Contents" / "MacOS" / "Adobe DNG Converter"
                                if app_path.exists():
                                    self.logger.info(f"Found Adobe DNG Converter via Homebrew at: {app_path}")
                                    return str(app_path)
        except FileNotFoundError:
            self.logger.debug("Homebrew not found in PATH")

        self.logger.warning("Adobe DNG Converter not found. Install via: brew install --cask adobe-dng-converter")
        return None


class MacOSDNGLabStrategy(DNGLabBinaryStrategy):
    """DNGLab binary strategy for macOS platforms (fallback)."""

    def get_architecture_mapping(self) -> str:
        """Get macOS architecture mapping."""
        machine = platform.machine().lower()
        return "arm64" if machine in ["aarch64", "arm64"] else "x86_64"

    def get_binary_filename(self) -> str:
        """Get macOS binary filename."""
        return "dnglab"

    def get_binary_path(self) -> str | None:
        """Get DNGLab binary path for macOS."""
        system_name = "darwin"
        arch = self.get_architecture_mapping()
        binary_name = self.get_binary_filename()
        machine = platform.machine().lower()

        self.logger.debug(
            f"Searching for DNGLab bin - system: {system_name}, machine: {machine}, mapped_arch: {arch}, bin_name: {binary_name}"
        )

        # Try bundled binary first
        binary_path = self._check_bundled_binary(system_name, arch, binary_name)
        if binary_path:
            self._make_executable(binary_path)
            return binary_path

        # Try system PATH
        binary_path = self._check_system_path(binary_name)
        if binary_path:
            return binary_path

        # Try local build directory
        binary_path = self._check_local_build(system_name, arch, binary_name)
        if binary_path:
            self._make_executable(binary_path)
            return binary_path

        self.logger.warning("No DNGLab binary found in any search location")
        return None


class DNGLabStrategyFactory:
    """Factory for creating appropriate DNG conversion strategies."""

    @staticmethod
    def create_strategy(logger: logging.Logger) -> DNGLabBinaryStrategy:
        """Create the appropriate strategy based on the current platform."""
        system_name = platform.system().lower()

        if system_name == "linux":
            return LinuxDNGLabStrategy(logger)
        if system_name == "windows":
            return WindowsDNGLabStrategy(logger)
        if system_name == "darwin":
            # Try Adobe DNG Converter first on macOS for better quality
            adobe_strategy = MacOSAdobeDNGStrategy(logger)
            adobe_path = adobe_strategy.get_binary_path()
            if adobe_path:
                logger.info("Using Adobe DNG Converter for macOS (preferred)")
                return adobe_strategy
            else:
                logger.info("Adobe DNG Converter not found, falling back to DNGLab")
                return MacOSDNGLabStrategy(logger)

        # Default to Linux strategy for unknown platforms
        logger.warning(f"Unknown platform: {system_name}, using Linux strategy")
        return LinuxDNGLabStrategy(logger)
