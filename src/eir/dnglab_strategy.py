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
        if not getattr(sys, "frozen", False):
            return None

        # Try PyInstaller first for backward compatibility (_MEIPASS)
        bundle_dir = getattr(sys, "_MEIPASS", "")
        if bundle_dir:
            self.logger.debug(f"Running as PyInstaller binary, bundle_dir: {bundle_dir}")
            dnglab_bundled = Path(bundle_dir) / "tools" / system_name / arch / binary_name
        else:
            # Try Nuitka (primary build system) - bundled files are in the extraction directory
            self.logger.debug("Running as Nuitka binary, checking extraction directory")

            # For Nuitka onefile, bundled files are extracted to a temporary directory
            # The bundled data is accessible relative to where the code is running
            # Since we used --include-data-dir=nuitka_data=., the structure is:
            # <extraction_dir>/tools/system/arch/binary

            # Get the directory where this Python file is running from
            current_file_dir = Path(__file__).parent

            # Try multiple possible locations for bundled data
            possible_locations = [
                # Direct from extraction root (most likely for Nuitka onefile)
                current_file_dir / "tools" / system_name / arch / binary_name,
                # One level up from current module
                current_file_dir.parent / "tools" / system_name / arch / binary_name,
                # Two levels up (in case we're in src/eir/)
                current_file_dir.parent.parent / "tools" / system_name / arch / binary_name,
                # From current working directory as fallback
                Path.cwd() / "tools" / system_name / arch / binary_name,
            ]

            for location in possible_locations:
                self.logger.debug(f"Trying Nuitka bundle path: {location}")
                if location.exists():
                    self.logger.debug(f"Found in Nuitka bundle at: {location}")
                    dnglab_bundled = location
                    break
            else:
                # None of the locations worked
                self.logger.debug("Not found in any Nuitka bundle location")
                dnglab_bundled = possible_locations[0]  # Use first for error reporting

        self.logger.debug(f"Checking bundled location: {dnglab_bundled}")

        if dnglab_bundled.exists():
            self.logger.info(f"Found bundled DNGLab: {dnglab_bundled}")
            return str(dnglab_bundled)
        else:
            self.logger.warning(f"Bundled DNGLab not found: {dnglab_bundled}")
            return None

    def _check_local_build(self, system_name: str, arch: str, binary_name: str) -> str | None:
        """Check for binary in local build directory (development)."""
        project_root = self._find_project_root()
        dnglab_local = project_root / "build" / system_name / "tools" / arch / binary_name

        self.logger.info(f"Checking local build directory: {dnglab_local}")

        if dnglab_local.exists():
            self.logger.info(f"Found local DNGLab: {dnglab_local}")
            return str(dnglab_local.absolute())
        else:
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
        except Exception as e:
            self.logger.error(f"Failed to make DNGLab executable: {e}")
            return False


class LinuxDNGLabStrategy(DNGLabBinaryStrategy):
    """DNGLab binary strategy for Linux platforms."""

    def get_architecture_mapping(self) -> str:
        """Get Linux architecture mapping."""
        machine = platform.machine().lower()
        return "aarch64" if machine in ["aarch64", "arm64"] else "x86_64"

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


class MacOSDNGLabStrategy(DNGLabBinaryStrategy):
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
        elif system_name == "windows":
            return WindowsDNGLabStrategy(logger)
        elif system_name == "darwin":
            return MacOSDNGLabStrategy(logger)
        else:
            # Default to Linux strategy for unknown platforms
            logger.warning(f"Unknown platform: {system_name}, using Linux strategy")
            return LinuxDNGLabStrategy(logger)
