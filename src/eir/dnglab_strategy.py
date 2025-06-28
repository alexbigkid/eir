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

        # Log detection info
        self.logger.info(
            f"Bundled detection: frozen={is_frozen}, "
            f"pyinstaller={is_pyinstaller}, nuitka_onefile={is_nuitka_onefile}"
        )
        self.logger.info(f"Current file path: {current_file_path}")
        self.logger.info(f"Current path string (lowercase): {current_path_str}")
        self.logger.info(f"Nuitka temp detection: {is_nuitka_temp}")
        self.logger.info(f"sys.frozen attribute: {getattr(sys, 'frozen', 'Not set')}")
        self.logger.info(f"sys._MEIPASS attribute: {getattr(sys, '_MEIPASS', 'Not set')}")

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
        # We start from __file__ which is inside the eir/ subdirectory,
        # so we need to go up to find the extraction root
        current_file_dir = Path(__file__).parent
        self.logger.info(f"Starting from current file directory: {current_file_dir}")
        self.logger.info(f"Absolute current file directory: {current_file_dir.absolute()}")

        # Find the extraction root that contains the tools directory
        # Start from the current directory and work our way up
        extraction_root = self._find_extraction_root(current_file_dir)
        self.logger.info(f"Found extraction root: {extraction_root}")
        self.logger.info(f"Absolute extraction root: {extraction_root.absolute()}")

        # Enhanced Windows path debugging - address path length and short name issues
        if system_name == "windows":
            self.logger.info("=== Windows Path Analysis ===")

            # Check path length (Windows has 260 char limit for full paths)
            extraction_path_str = str(extraction_root.absolute())
            self.logger.info(
                f"Windows extraction root path length: {len(extraction_path_str)} chars"
            )
            self.logger.info(f"Windows extraction root path: {extraction_path_str}")

            if len(extraction_path_str) > 240:  # Close to 260 limit
                self.logger.warning(
                    f"Windows path is long ({len(extraction_path_str)} chars) - may cause issues"
                )

            # Check for Windows short names (8.3 format) indicators
            short_name_indicators = ["~1", "~2", "~3", "ONEFIL~", "PROGRA~", "DOCUME~"]
            has_short_names = any(
                indicator in extraction_path_str.upper() for indicator in short_name_indicators
            )
            if has_short_names:
                self.logger.info("Windows path contains short name patterns (8.3 format)")

            # Try to resolve any short names to long names
            try:
                import ctypes
                from ctypes import wintypes

                # Try to get the long path name
                get_long_path_name = ctypes.windll.kernel32.GetLongPathNameW
                get_long_path_name.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
                get_long_path_name.restype = wintypes.DWORD

                buffer_size = 500
                buffer = ctypes.create_unicode_buffer(buffer_size)
                result = get_long_path_name(extraction_path_str, buffer, buffer_size)

                if result > 0:
                    long_path = buffer.value
                    self.logger.info(f"Windows long path name: {long_path}")
                    if long_path != extraction_path_str:
                        self.logger.info("Windows path was expanded from short name")
                        extraction_root = Path(long_path)
                        self.logger.info(f"Updated extraction root: {extraction_root}")
                else:
                    self.logger.info("Windows GetLongPathName did not return a different path")

            except Exception as e:
                self.logger.warning(f"Could not resolve Windows long path name: {e}")

            # Standard path resolution
            try:
                resolved_root = extraction_root.resolve()
                self.logger.info(f"Windows resolved extraction root: {resolved_root}")
                if str(resolved_root) != str(extraction_root):
                    self.logger.info("Windows extraction root changed after resolve()")
                    extraction_root = resolved_root
            except Exception as e:
                self.logger.warning(f"Could not resolve Windows extraction root: {e}")

        # Compute the DNGLab path
        dnglab_path = extraction_root / "tools" / system_name / arch / binary_name
        self.logger.info(f"Computed bundled path: {dnglab_path}")
        self.logger.info(f"Absolute bundled path: {dnglab_path.absolute()}")
        tools_exists = (extraction_root / "tools").exists()
        self.logger.info(f"Does tools directory exist at extraction root: {tools_exists}")

        # Enhanced Windows debugging - comprehensive directory analysis
        if system_name == "windows":
            self.logger.info("=== Windows Directory Analysis ===")
            try:
                if extraction_root.exists():
                    items = list(extraction_root.iterdir())
                    self.logger.info(f"Windows extraction root item count: {len(items)}")
                    self.logger.info(
                        f"Windows extraction root contents: {[item.name for item in items[:15]]}"
                    )

                    # Check the computed path length
                    computed_path_str = str(dnglab_path.absolute())
                    self.logger.info(
                        f"Windows computed DNGLab path length: {len(computed_path_str)} chars"
                    )
                    if len(computed_path_str) > 260:
                        self.logger.error(
                            f"Windows computed path exceeds 260 char limit: {computed_path_str}"
                        )

                    # Check if tools directory exists with different casing or names
                    tools_found = False
                    for item in items:
                        if item.is_dir():
                            item_name_lower = item.name.lower()
                            if item_name_lower == "tools":
                                tools_found = True
                                self.logger.info(
                                    f"Found tools directory with casing: '{item.name}'"
                                )
                                if item.name != "tools":
                                    # Use the actual casing found
                                    dnglab_path = (
                                        extraction_root
                                        / item.name
                                        / system_name
                                        / arch
                                        / binary_name
                                    )
                                    self.logger.info(
                                        f"Corrected path with actual casing: {dnglab_path}"
                                    )
                                break
                            elif "tool" in item_name_lower:
                                self.logger.info(f"Found tool-related directory: '{item.name}'")

                    if not tools_found:
                        self.logger.warning(
                            "Windows: No 'tools' directory found in extraction root"
                        )

                        # Check if bundled files are in a different structure
                        self.logger.info("Windows: Searching for any dnglab-related files...")
                        for item in items:
                            if item.is_file() and "dnglab" in item.name.lower():
                                self.logger.info(f"Found dnglab file in root: {item}")
                            elif item.is_dir():
                                # Check one level down for dnglab files
                                try:
                                    sub_items = list(item.iterdir())
                                    for sub_item in sub_items[:5]:  # Limit search
                                        if (
                                            sub_item.is_file()
                                            and "dnglab" in sub_item.name.lower()
                                        ):
                                            self.logger.info(
                                                f"Found dnglab file in {item.name}: {sub_item}"
                                            )
                                except Exception as e:
                                    # Skip directories we can't read, but log briefly
                                    self.logger.debug(
                                        f"Could not read directory {item.name}: {e}"
                                    )
                else:
                    self.logger.error(
                        f"Windows extraction root does not exist: {extraction_root}"
                    )

            except Exception as e:
                self.logger.warning(f"Could not analyze Windows extraction directory: {e}")

        return dnglab_path

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
                self.logger.info(
                    f"Detected 'eir' subdirectory in Nuitka extraction: {start_dir}"
                )
                candidate_root = start_dir.parent
                if (candidate_root / "tools").exists():
                    self.logger.info(f"Found tools directory at parent: {candidate_root}")
                    return candidate_root
                else:
                    self.logger.info(
                        f"Parent has no tools, using as extraction root: {candidate_root}"
                    )
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
                any(pattern in part.lower() for pattern in nuitka_patterns)
                for part in extraction_root.parts
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
                self.logger.warning(
                    f"Found Nuitka pattern but no tools. Using parent: {extraction_root.parent}"
                )
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

        self.logger.info(
            f"Windows DNGLab search: system={system_name}, "
            f"machine={machine}, mapped_arch={arch}, binary_name={binary_name}"
        )

        # Try bundled binary first
        self.logger.info("Windows: Checking for bundled DNGLab binary...")
        binary_path = self._check_bundled_binary(system_name, arch, binary_name)
        if binary_path:
            self.logger.info(f"Windows: Found bundled DNGLab at {binary_path}")
            return binary_path
        else:
            self.logger.warning("Windows: Bundled DNGLab binary not found")

        # Try system PATH
        self.logger.info("Windows: Checking system PATH for DNGLab...")
        binary_path = self._check_system_path(binary_name)
        if binary_path:
            self.logger.info(f"Windows: Found DNGLab in PATH at {binary_path}")
            return binary_path
        else:
            self.logger.info("Windows: DNGLab not found in system PATH")

        # Try local build directory
        self.logger.info("Windows: Checking local build directory...")
        binary_path = self._check_local_build(system_name, arch, binary_name)
        if binary_path:
            self.logger.info(f"Windows: Found local DNGLab at {binary_path}")
            return binary_path
        else:
            self.logger.info("Windows: DNGLab not found in local build directory")

        self.logger.warning("Windows: No DNGLab binary found in any search location")
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
