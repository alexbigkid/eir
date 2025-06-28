"""DNGLab binary management strategies for different platforms."""

import logging
import os
import platform
import shutil
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
        dnglab_bundled = self._get_bundled_binary_path(
            bundled_detection, system_name, arch, binary_name
        )

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
        )

        is_nuitka_onefile = (
            "/tmp/onefile_" in str(current_file_path)  # Linux pattern
            or "onefile" in current_path_str  # General onefile pattern
            or "onefil" in current_path_str  # Windows short name pattern
            or is_nuitka_temp  # Temp extraction patterns
        )

        is_frozen = getattr(sys, "frozen", False)
        is_pyinstaller = hasattr(sys, "_MEIPASS")

        # Log detection info
        self.logger.info(
            f"Bundled detection: frozen={is_frozen}, "
            f"pyinstaller={is_pyinstaller}, nuitka_onefile={is_nuitka_onefile}"
        )
        self.logger.info(f"Current file path: {current_file_path}")

        return {
            "is_bundled": is_frozen or is_pyinstaller or is_nuitka_onefile,
            "is_pyinstaller": is_pyinstaller,
            "is_nuitka_onefile": is_nuitka_onefile,
            "current_path": str(current_file_path),
        }

    def _get_bundled_binary_path(
        self, detection: dict[str, bool | str], system_name: str, arch: str, binary_name: str
    ) -> Path:
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
        # For Nuitka onefile, bundled files are extracted to the same temp directory
        # Since we used --include-data-dir=nuitka_data=., the structure should be:
        # <extraction_dir>/tools/system/arch/binary
        current_file_dir = Path(__file__).parent
        self.logger.info(f"Searching from extraction directory: {current_file_dir}")

        # Find the extraction root that contains the tools directory
        extraction_root = self._find_extraction_root(current_file_dir)
        dnglab_path = extraction_root / "tools" / system_name / arch / binary_name
        self.logger.info(f"Computed bundled path: {dnglab_path}")
        return dnglab_path

    def _find_extraction_root(self, start_dir: Path) -> Path:
        """Find the extraction root directory containing bundled data."""
        extraction_root = start_dir
        levels_checked = 0
        max_levels = 5  # Limit how far up we search to prevent issues

        while extraction_root.parent != extraction_root and levels_checked < max_levels:
            # Check if this directory contains the tools directory
            if (extraction_root / "tools").exists():
                break
            # Check if we're in a Nuitka extraction directory (including Windows short names)
            nuitka_patterns = ["onefile_", "onefil"]  # Include Windows short name pattern
            if any(
                any(pattern in name.lower() for pattern in nuitka_patterns)
                for name in extraction_root.parts
            ):
                # Look for tools in this directory or parent directories (limited search)
                for check_dir in [
                    extraction_root,
                    extraction_root.parent,
                    extraction_root.parent.parent,
                ]:
                    if (check_dir / "tools").exists():
                        extraction_root = check_dir
                        break
                break
            extraction_root = extraction_root.parent
            levels_checked += 1

        # If we couldn't find a tools directory, just return the start directory
        if levels_checked >= max_levels:
            self.logger.warning(
                f"Could not find tools directory after searching {max_levels} levels up from "
                f"{start_dir}"
            )
            return start_dir

        return extraction_root

    def _debug_extraction_directory(self) -> None:
        """Debug helper to list extraction directory contents."""
        extraction_dir = Path(__file__).parent
        levels_checked = 0
        max_debug_levels = 3  # Limit debug search to prevent massive output

        while extraction_dir.parent != extraction_dir and levels_checked < max_debug_levels:
            nuitka_patterns = ["onefile_", "onefil"]  # Include Windows short name pattern
            if any(
                any(pattern in name.lower() for pattern in nuitka_patterns)
                for name in extraction_dir.parts
            ):
                break
            extraction_dir = extraction_dir.parent
            levels_checked += 1

        # Skip debug if we're at filesystem root or in a suspicious location
        if str(extraction_dir) in ["/", "C:\\", "C:"]:
            self.logger.warning("Skipping debug listing - at filesystem root")
            return

        self.logger.info(f"Extraction directory contents (for debugging): {extraction_dir}")
        try:
            # Only check immediate children, limit the number shown
            max_items = 20  # Limit to prevent spam

            for items_shown, item in enumerate(extraction_dir.iterdir()):
                if items_shown >= max_items:
                    self.logger.info(f"  ... (showing only first {max_items} items)")
                    break

                if item.is_file() and "dnglab" in item.name:
                    self.logger.info(f"Found dnglab-related file: {item}")
                elif item.is_dir() and item.name == "tools":
                    self.logger.info(f"Found tools directory: {item}")
                    # Only show top-level structure of tools directory
                    for tool_items_shown, tool_item in enumerate(item.iterdir()):
                        if tool_items_shown >= 5:  # Limit tools listing
                            self.logger.info("    ... (showing only first 5 tools items)")
                            break
                        self.logger.info(f"  Tools content: {tool_item}")
                elif item.is_dir():
                    self.logger.info(f"Found directory: {item}")
        except (OSError, PermissionError) as e:
            self.logger.warning(f"Could not list extraction directory for debugging: {e}")

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
            f"Searching for DNGLab binary - system: {system_name}, "
            f"machine: {machine}, mapped_arch: {arch}, binary_name: {binary_name}"
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
            f"Searching for DNGLab binary - system: {system_name}, "
            f"machine: {machine}, mapped_arch: {arch}, binary_name: {binary_name}"
        )

        # Try bundled binary first
        binary_path = self._check_bundled_binary(system_name, arch, binary_name)
        if binary_path:
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


class MacOSDNGStrategy(DNGLabBinaryStrategy):
    """DNGLab binary strategy for macOS platforms."""

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
            f"Searching for DNGLab binary - system: {system_name}, "
            f"machine: {machine}, mapped_arch: {arch}, binary_name: {binary_name}"
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
    """Factory for creating appropriate DNGLab binary strategies."""

    @staticmethod
    def create_strategy(logger: logging.Logger) -> DNGLabBinaryStrategy:
        """Create the appropriate strategy based on the current platform."""
        system_name = platform.system().lower()

        if system_name == "linux":
            return LinuxDNGLabStrategy(logger)
        if system_name == "windows":
            return WindowsDNGLabStrategy(logger)
        if system_name == "darwin":
            return MacOSDNGStrategy(logger)

        # Default to Linux strategy for unknown platforms
        logger.warning(f"Unknown platform: {system_name}, using Linux strategy")
        return LinuxDNGLabStrategy(logger)
