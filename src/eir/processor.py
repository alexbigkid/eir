"""Modern async RxPY-based EXIF Pictures Renaming processor."""

import logging
import os
import re
import asyncio
import threading
import platform
import sys
import shutil
from pathlib import Path
from datetime import datetime
from enum import Enum
import json
from typing import Any

import reactivex as rx
from reactivex import operators as ops
from reactivex.scheduler.eventloop import AsyncIOScheduler
from pydngconverter import DNGConverter
import pydngconverter.compat
import exiftool

from eir.abk_common import function_trace, PerformanceTimer


class ListType(Enum):
    """ListType is type of image or video list."""

    RAW_IMAGE_DICT = "raw_image_dict"
    THUMB_IMAGE_DICT = "thumb_image_dict"
    COMPRESSED_IMAGE_DICT = "compressed_image_dict"
    COMPRESSED_VIDEO_DICT = "compressed_video_dict"


class ExifTag(Enum):
    """ExifTags contains all exif meta data tags."""

    SOURCE_FILE = "SourceFile"
    CREATE_DATE = "EXIF:CreateDate"
    MAKE = "EXIF:Make"
    MODEL = "EXIF:Model"


class ImageProcessor:
    """Modern async RxPY-based image processor with complete EXIF functionality."""

    FILES_TO_EXCLUDE_EXPRESSION = r"Adobe Bridge Cache|Thumbs.db|^\."
    THMB = {"ext": "jpg", "dir": "thmb"}
    SUPPORTED_RAW_IMAGE_EXT = {
        "Adobe": ["dng"],
        "Canon": ["crw", "cr2", "cr3"],
        "FujiFilm": ["raf"],
        "Leica": ["rwl"],
        "Minolta": ["mrw"],
        "Nikon": ["nef", "nrw"],
        "Olympus": ["orw"],
        "Panasonic": ["raw", "rw2"],
        "Pentax": ["pef"],
        "Samsung": ["srw"],
        "Sony": ["arw", "sr2"],
    }
    SUPPORTED_COMPRESSED_IMAGE_EXT_LIST = [
        "gif",
        "heic",
        "jpg",
        "jpeg",
        "jng",
        "mng",
        "png",
        "psd",
        "tiff",
        "tif",
    ]
    SUPPORTED_COMPRESSED_VIDEO_EXT_LIST = [
        "3g2",
        "3gp2",
        "crm",
        "m4a",
        "m4b",
        "m4p",
        "m4v",
        "mov",
        "mp4",
        "mqv",
        "qt",
    ]
    EXIF_UNKNOWN = "unknown"
    EXIF_TAGS = [ExifTag.CREATE_DATE.value, ExifTag.MAKE.value, ExifTag.MODEL.value]

    def __init__(self, logger: logging.Logger, op_dir: str):
        """Initialize ImageProcessor."""
        self._logger = logger or logging.getLogger(__name__)
        self._op_dir = op_dir
        self._current_dir = None
        self._supported_raw_image_ext_list = list(
            set([ext for exts in self.SUPPORTED_RAW_IMAGE_EXT.values() for ext in exts])
        )
        self._project_name = None

        # Configure DNG converter early
        self._configure_dng_converter()

    @property
    def project_name(self) -> str:
        """Returns project name extracted from directory."""
        if self._project_name is None:
            current_dir = os.getcwd()
            norm_path = os.path.basename(os.path.normpath(current_dir))
            dir_parts = norm_path.split("_")
            # Project name is everything after the first underscore
            # This works for both YYYYMMDD_name and YYYYMMDD-YYYYMMDD_name formats
            self._project_name = "_".join(dir_parts[1:])
            self._logger.info(f"{self._project_name = }")
        return self._project_name

    @function_trace
    async def extract_exif_metadata(self, files_list: list[str]) -> list[dict[str, Any]]:
        """Extract EXIF metadata from files using ExifTool."""
        with exiftool.ExifToolHelper() as etp:
            etp.logger = self._logger
            metadata_list = etp.get_tags(files_list, self.EXIF_TAGS)
            self._logger.debug(f"{metadata_list = }")
            return metadata_list

    async def convert_raw_to_dng(self, src_dir: str, dst_dir: str) -> None:
        """Convert RAW files to DNG format."""
        self._logger.info(f"Starting DNG conversion: {src_dir} -> {dst_dir}")
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
            self._logger.info(f"Created destination directory: {dst_dir}")

        # Configure DNG converter based on platform
        self._configure_dng_converter()

        # Debug: Check environment variable before conversion
        env_var = os.environ.get("PYDNG_DNG_CONVERTER")
        self._logger.info(f"PYDNG_DNG_CONVERTER environment variable: {env_var}")

        if env_var:
            env_path = Path(env_var)
            self._logger.info(f"DNGLab binary exists: {env_path.exists()}")
            if env_path.exists():
                self._logger.info(f"DNGLab binary is executable: {os.access(env_var, os.X_OK)}")
                self._logger.info(f"DNGLab binary size: {env_path.stat().st_size} bytes")
        else:
            self._logger.warning(
                "No DNGLab binary configured - will use default Adobe DNG Converter"
            )

        # List RAW files to be converted (if source directory exists)
        src_path = Path(src_dir)
        if os.path.exists(src_dir):
            raw_files = list(src_path.glob("*"))
            self._logger.info(f"Found {len(raw_files)} files in source directory:")
            for raw_file in raw_files:
                self._logger.info(f"  - {raw_file.name} ({raw_file.stat().st_size} bytes)")
        else:
            self._logger.warning(f"Source directory does not exist: {src_dir}")
            # Continue anyway to maintain compatibility with existing tests

        self._logger.info(f"Initializing DNGConverter with source={src_dir}, dest={dst_dir}")
        py_dng = DNGConverter(source=Path(src_dir), dest=Path(dst_dir))
        # Log DNGConverter configuration
        self._logger.info("DNGConverter initialized successfully")
        self._logger.info(f"DNGConverter binary path: {py_dng.bin_exec}")
        self._logger.info(f"DNGConverter binary type: {type(py_dng.bin_exec)}")

        # Patch pydngconverter to avoid Wine on Linux when using DNGLab
        if platform.system().lower() == "linux" and os.environ.get("PYDNG_DNG_CONVERTER"):
            self._logger.info("Applying Linux DNGLab compatibility patch (avoiding Wine)")

            async def patched_get_compat_path(path):
                # Use native path on Linux when DNGLab is configured
                native_path = str(Path(path))
                self._logger.debug(f"Patched compat path: {path} -> {native_path}")
                return native_path

            pydngconverter.compat.get_compat_path = patched_get_compat_path

            # Also patch the convert_file method to add proper error handling
            from pydngconverter import main as pydng_main

            async def patched_convert_file(self, *, destination: str = None, job=None, log=None):
                """Enhanced convert_file with better error handling and logging."""
                import asyncio
                import os
                from pydngconverter import compat

                log = log or self._logger
                log.debug("starting conversion: %s", job.source.name)
                source_path = await compat.get_compat_path(job.source)
                log.debug("determined source path: %s", source_path)

                # Check if we're using DNGLab vs Adobe DNG Converter
                # Use environment variable as primary indicator since bin_exec
                # might not reflect the actual binary
                env_dnglab = os.environ.get("PYDNG_DNG_CONVERTER", "")
                is_dnglab = (
                    "dnglab" in env_dnglab.lower() or "dnglab" in str(self.bin_exec).lower()
                )
                log.debug(
                    f"Binary path: {self.bin_exec}, env var: {env_dnglab}, is_dnglab: {is_dnglab}"
                )

                if is_dnglab:
                    # DNGLab syntax: dnglab convert [options] input output
                    output_file = Path(destination) / f"{Path(source_path).stem}.dng"
                    dng_args = [
                        "convert",
                        "--compression",
                        "lossless",
                        "--dng-preview",
                        "true",
                        str(source_path),
                        str(output_file),
                    ]
                else:
                    # Adobe DNG Converter syntax (original)
                    dng_args = [*self.parameters.iter_args, "-d", destination, str(source_path)]

                # Log the full command being executed
                full_command = f"{self.bin_exec} {' '.join(dng_args)}"
                log.info(
                    "Executing %s command: %s",
                    "DNGLab" if is_dnglab else "Adobe DNG Converter",
                    full_command,
                )

                # Validate arguments before execution
                log.debug("DNGLab binary: %s", self.bin_exec)
                log.debug("DNGLab arguments: %s", dng_args)
                log.debug("Source file exists: %s", Path(source_path).exists())
                log.debug("Destination directory exists: %s", Path(destination).exists())
                log.debug("Current working directory: %s", Path.cwd())

                log.info("converting: %s => %s", job.source.name, job.destination_filename)

                try:
                    proc = await asyncio.create_subprocess_exec(
                        self.bin_exec,
                        *dng_args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()

                    # Check return code and log any errors
                    if proc.returncode != 0:
                        log.error("DNGLab conversion failed with return code %d", proc.returncode)
                        if stderr:
                            stderr_text = stderr.decode("utf-8", errors="replace")
                            log.error("DNGLab stderr: %s", stderr_text)
                        if stdout:
                            stdout_text = stdout.decode("utf-8", errors="replace")
                            log.error("DNGLab stdout: %s", stdout_text)
                        # Still report as finished to maintain compatibility, but with error info
                        log.warning("Conversion reported as finished despite errors")
                    else:
                        log.info("DNGLab conversion succeeded (return code 0)")
                        if stdout:
                            stdout_text = stdout.decode("utf-8", errors="replace")
                            if stdout_text.strip():
                                log.debug("DNGLab stdout: %s", stdout_text.strip())

                except Exception as e:
                    log.error("Exception during DNGLab subprocess execution: %s", e)
                    raise

                log.info("finished conversion: %s", job.destination_filename)
                return job.destination

            # Apply the patch
            pydng_main.DNGConverter.convert_file = patched_convert_file
            self._logger.info("Applied enhanced convert_file patch with error handling")

        # Perform conversion with detailed logging
        self._logger.info("Starting pydngconverter.convert() operation...")
        try:
            await py_dng.convert()
            self._logger.info("pydngconverter.convert() completed without exceptions")
            # Check conversion results with detailed path analysis
            dst_path = Path(dst_dir)
            src_path = Path(src_dir)

            self._logger.info("Post-conversion analysis:")
            self._logger.info(f"  Source directory: {src_path.absolute()}")
            self._logger.info(f"  Destination directory: {dst_path.absolute()}")
            self._logger.info(f"  Current working directory: {Path.cwd()}")

            if os.path.exists(dst_dir):
                converted_files = list(dst_path.glob("*"))
                self._logger.info(
                    f"Conversion completed - found {len(converted_files)} files in destination:"
                )
                for converted_file in converted_files:
                    self._logger.info(
                        f"  - {converted_file.name} ({converted_file.stat().st_size} bytes)"
                    )
                if len(converted_files) == 0:
                    self._logger.warning(
                        "No files found in destination directory after conversion!"
                    )
                    self._logger.warning("This indicates DNGLab may not be working properly")

                    # Search for DNG files in nearby directories to debug the issue
                    self._logger.info(
                        "Searching for DNG files in current and parent directories..."
                    )
                    cwd = Path.cwd()
                    for search_dir in [cwd, cwd.parent, src_path.parent]:
                        if search_dir.exists():
                            dng_files = list(search_dir.rglob("*.dng"))
                            if dng_files:
                                self._logger.info(f"Found DNG files in {search_dir}:")
                                for dng_file in dng_files[:5]:  # Limit output
                                    self._logger.info(f"  - {dng_file}")
            else:
                self._logger.error(
                    f"Destination directory disappeared after conversion: {dst_dir}"
                )

        except Exception as e:
            self._logger.error(f"Exception during DNG conversion: {type(e).__name__}: {e}")
            # Re-raise the exception to maintain original behavior
            raise

    def _configure_dng_converter(self) -> None:
        """Configure DNG converter based on platform and available tools."""
        system_name = platform.system().lower()
        self._logger.info(f"Configuring DNG converter for platform: {system_name}")

        if system_name in ["linux", "windows"]:
            # On Linux and Windows, try to use bundled DNGLab
            self._logger.info(
                f"Attempting DNGLab configuration for {system_name}, "
                f"machine: {platform.machine()}"
            )
            dnglab_path = self._find_dnglab_binary()
            if dnglab_path:
                # Set environment variable for pydngconverter
                old_env = os.environ.get("PYDNG_DNG_CONVERTER")
                os.environ["PYDNG_DNG_CONVERTER"] = dnglab_path
                self._logger.info(f"Set PYDNG_DNG_CONVERTER: {old_env} -> {dnglab_path}")

                # Verify the binary exists and is executable (Linux) or just exists (Windows)
                dnglab_file = Path(dnglab_path)
                if dnglab_file.exists():
                    file_size = dnglab_file.stat().st_size
                    self._logger.info(f"DNGLab binary verification - size: {file_size} bytes")

                    if system_name == "linux":
                        is_executable = os.access(dnglab_path, os.X_OK)
                        self._logger.info(f"DNGLab executable check (Linux): {is_executable}")
                        if not is_executable:
                            self._logger.warning(
                                f"DNGLab binary is not executable: {dnglab_path}"
                            )
                            self._logger.info("Attempting to make DNGLab executable...")
                            try:
                                os.chmod(dnglab_path, 0o755)  # noqa: S103
                                self._logger.info("Successfully made DNGLab executable")
                            except Exception as e:
                                self._logger.error(f"Failed to make DNGLab executable: {e}")

                    # Test DNGLab binary functionality
                    self._test_dnglab_binary(dnglab_path)
                else:
                    self._logger.error(f"DNGLab binary file not found at path: {dnglab_path}")
                    # Unset environment variable if binary doesn't exist
                    if "PYDNG_DNG_CONVERTER" in os.environ:
                        del os.environ["PYDNG_DNG_CONVERTER"]
                        self._logger.info(
                            "Removed invalid PYDNG_DNG_CONVERTER environment variable"
                        )
            else:
                self._logger.warning(
                    f"DNGLab binary not found - will fall back to default "
                    f"Adobe DNG Converter on {system_name}"
                )
        else:
            self._logger.info(f"Platform {system_name} will use default Adobe DNG Converter")

    def _test_dnglab_binary(self, dnglab_path: str) -> None:
        """Test DNGLab binary to verify it's working."""
        try:
            import subprocess  # noqa: S404

            self._logger.info(f"Testing DNGLab binary functionality: {dnglab_path}")

            # Test with --help flag to verify binary works
            result = subprocess.run(  # noqa: S603
                [dnglab_path, "--help"], capture_output=True, text=True, timeout=10, check=False
            )

            if result.returncode == 0:
                self._logger.info("✅ DNGLab binary test successful (--help worked)")
                # Log first few lines of help output for verification
                help_lines = result.stdout.split("\n")[:3]
                for line in help_lines:
                    if line.strip():
                        self._logger.info(f"DNGLab help: {line.strip()}")
            else:
                self._logger.warning(
                    f"⚠️  DNGLab binary test failed with exit code {result.returncode}"
                )
                if result.stderr:
                    self._logger.warning(f"DNGLab stderr: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            self._logger.warning("DNGLab binary test timed out after 10 seconds")
        except Exception as e:
            self._logger.warning(f"DNGLab binary test failed with exception: {e}")

    def _find_dnglab_binary(self) -> str | None:
        """Find DNGLab binary in bundled resources or system PATH."""
        machine = platform.machine().lower()
        system_name = platform.system().lower()

        # Map machine architecture to binary naming conventions
        if system_name == "windows":
            dnglab_arch = "arm64" if machine in ["aarch64", "arm64"] else "x64"
            binary_name = "dnglab.exe"
        else:  # Linux
            dnglab_arch = "aarch64" if machine in ["aarch64", "arm64"] else "x86_64"
            binary_name = "dnglab"

        self._logger.info(
            f"Searching for DNGLab binary - system: {system_name}, "
            f"machine: {machine}, mapped_arch: {dnglab_arch}, binary_name: {binary_name}"
        )

        search_locations = []
        found_binary = None

        # Try bundled DNGLab first (PyInstaller extracts to temp dir)
        if getattr(sys, "frozen", False):
            # Running as compiled binary
            bundle_dir = getattr(sys, "_MEIPASS", "")  # PyInstaller temp directory
            self._logger.info(f"Running as compiled binary, bundle_dir: {bundle_dir}")
            dnglab_bundled = Path(bundle_dir) / "tools" / system_name / dnglab_arch / binary_name
            search_locations.append(("bundled", str(dnglab_bundled)))

            self._logger.info(f"Checking bundled location: {dnglab_bundled}")
            if dnglab_bundled.exists():
                self._logger.info(f"✅ Found bundled DNGLab: {dnglab_bundled}")
                found_binary = str(dnglab_bundled)
            else:
                self._logger.warning(f"❌ Bundled DNGLab not found: {dnglab_bundled}")
                # List available files in bundle tools directory for debugging
                tools_dir = Path(bundle_dir) / "tools" / system_name / dnglab_arch
                if tools_dir.exists():
                    available_files = list(tools_dir.glob("*"))
                    self._logger.warning(f"Available files in {tools_dir}: {available_files}")
                    # Also check parent directories
                    parent_tools = Path(bundle_dir) / "tools"
                    if parent_tools.exists():
                        subdirs = [d for d in parent_tools.iterdir() if d.is_dir()]
                        self._logger.warning(
                            f"Available platform directories: {[d.name for d in subdirs]}"
                        )
                else:
                    self._logger.warning(f"❌ Tools directory not found: {tools_dir}")
                    # Check if tools directory exists at all
                    bundle_tools = Path(bundle_dir) / "tools"
                    if bundle_tools.exists():
                        self._logger.warning(
                            f"Tools directory exists but missing platform/arch: {bundle_tools}"
                        )
                        subdirs = list(bundle_tools.iterdir())
                        self._logger.warning(
                            f"Available items in tools: {[str(d) for d in subdirs]}"
                        )
                    else:
                        self._logger.warning(f"No tools directory in bundle: {bundle_dir}")
                        bundle_contents = (
                            list(Path(bundle_dir).iterdir()) if Path(bundle_dir).exists() else []
                        )
                        self._logger.warning(
                            f"Bundle directory contents: {[d.name for d in bundle_contents[:10]]}"
                        )

        # Try system PATH if not found in bundle
        if not found_binary:
            self._logger.info(f"Checking system PATH for: {binary_name}")
            dnglab_system = shutil.which(binary_name)
            search_locations.append(("system_path", dnglab_system or "not found"))
            if dnglab_system:
                self._logger.info(f"✅ Found DNGLab in system PATH: {dnglab_system}")
                found_binary = dnglab_system
            else:
                self._logger.info("❌ DNGLab not found in system PATH")

        # Try local build directory (development) if still not found
        if not found_binary:
            dnglab_local = Path("build") / system_name / "tools" / dnglab_arch / binary_name
            search_locations.append(("local_build", str(dnglab_local)))
            self._logger.info(f"Checking local build directory: {dnglab_local}")
            if dnglab_local.exists():
                self._logger.info(f"✅ Found local DNGLab: {dnglab_local}")
                found_binary = str(dnglab_local.absolute())
            else:
                self._logger.info(f"❌ Local DNGLab not found: {dnglab_local}")
                # Check if build directory structure exists
                build_dir = Path("build")
                if build_dir.exists():
                    platform_dir = build_dir / system_name
                    if platform_dir.exists():
                        tools_dir = platform_dir / "tools"
                        if tools_dir.exists():
                            arch_dirs = list(tools_dir.iterdir())
                            arch_names = [d.name for d in arch_dirs if d.is_dir()]
                            self._logger.info(f"Available architectures in build: {arch_names}")
                        else:
                            self._logger.info(
                                f"No tools directory in platform build: {platform_dir}"
                            )
                    else:
                        available_platforms = [d.name for d in build_dir.iterdir() if d.is_dir()]
                        self._logger.info(f"Available platforms in build: {available_platforms}")
                else:
                    self._logger.info(
                        "No build directory found (normal in CI/packaged environments)"
                    )

        # Log search summary
        self._logger.info("DNGLab binary search summary:")
        for location_type, path in search_locations:
            status = "✅ FOUND" if found_binary and path == found_binary else "❌ not found"
            self._logger.info(f"  {location_type}: {path} - {status}")

        if not found_binary:
            self._logger.warning("❌ No DNGLab binary found in any search location")
        return found_binary

    @function_trace
    def _validate_image_dir(self) -> None:
        """Validate directory follows YYYYMMDD_project or YYYYMMDD-YYYYMMDD_project format."""
        self._logger.debug(f"{self._op_dir = }")
        try:
            dir_name_to_validate = self._op_dir if self._op_dir != "." else os.getcwd()
            last_part_of_dir = os.path.basename(os.path.normpath(dir_name_to_validate))

            # Support both single date and date range formats
            match = re.match(r"^(\d{8}(?:-\d{8})?)_[\w-]+$", last_part_of_dir)
            if not match:
                raise ValueError("Regex match failed")

            # Validate the date(s)
            date_part = match.group(1)
            if "-" in date_part:
                # Date range format: YYYYMMDD-YYYYMMDD
                start_date, end_date = date_part.split("-")
                datetime.strptime(start_date, "%Y%m%d")
                datetime.strptime(end_date, "%Y%m%d")
                # Validate that start_date <= end_date
                if start_date > end_date:
                    raise ValueError("Start date must be before or equal to end date")
            else:
                # Single date format: YYYYMMDD
                datetime.strptime(date_part, "%Y%m%d")

        except (AttributeError, ValueError) as e:
            raise ValueError(
                "Invalid directory format. Use: YYYYMMDD_project or YYYYMMDD-YYYYMMDD_project"
            ) from e

    def _extract_directory_info(self) -> tuple[str, bool]:
        """Extract directory date and determine if it's a date range format.

        Returns:
            tuple: (fallback_date, is_date_range)
                - fallback_date: YYYYMMDD format for fallback use
                - is_date_range: True if directory uses YYYYMMDD-YYYYMMDD format
        """
        dir_name_to_extract = self._op_dir if self._op_dir != "." else os.getcwd()
        last_part_of_dir = os.path.basename(os.path.normpath(dir_name_to_extract))

        # Extract date part (before first underscore)
        date_part = last_part_of_dir.split("_")[0]

        if "-" in date_part:
            # Date range format: use start date as fallback
            start_date = date_part.split("-")[0]
            return start_date, True
        else:
            # Single date format
            return date_part, False

    @function_trace
    def _change_to_image_dir(self) -> None:
        """Change to image directory."""
        if self._op_dir != ".":
            self._current_dir = os.getcwd()
            os.chdir(self._op_dir)
            self._logger.info(f"inside directory: {self._op_dir}")

    def _change_from_image_dir(self) -> None:
        """Return from image directory."""
        if self._current_dir is not None:
            os.chdir(self._current_dir)
            self._logger.info(f"inside directory: {self._current_dir}")

    def _process_metadata(
        self, metadata: dict[str, Any], filtered_list: list[str]
    ) -> tuple[ListType, str, dict[str, Any]] | None:
        """Process individual metadata and classify file type."""
        file_name = metadata.get(ExifTag.SOURCE_FILE.value)
        if not file_name:
            return None
        file_base, file_extension = os.path.splitext(os.path.basename(file_name))
        file_extension = file_extension.replace(".", "").lower()

        list_type: ListType | None = None

        if file_extension in self._supported_raw_image_ext_list:
            list_type = ListType.RAW_IMAGE_DICT
        elif file_extension in self.SUPPORTED_COMPRESSED_IMAGE_EXT_LIST:
            if file_extension == self.THMB["ext"]:
                if any(
                    f"{file_base.lower()}.{raw_ext}" in [j.lower() for j in filtered_list]
                    for raw_ext in self._supported_raw_image_ext_list
                ):
                    file_extension = self.THMB["dir"]
                    list_type = ListType.THUMB_IMAGE_DICT
                else:
                    list_type = ListType.COMPRESSED_IMAGE_DICT
            else:
                list_type = ListType.COMPRESSED_IMAGE_DICT
        elif file_extension in self.SUPPORTED_COMPRESSED_VIDEO_EXT_LIST:
            list_type = ListType.COMPRESSED_VIDEO_DICT

        if not list_type:
            return None

        # Process EXIF date with fallback to directory date
        exif_date = metadata.get(ExifTag.CREATE_DATE.value)
        if exif_date and exif_date != self.EXIF_UNKNOWN:
            # EXIF success: "2024:12:10 14:30:05" → "20241210-143005"
            try:
                # Validate and format EXIF date
                datetime.strptime(exif_date, "%Y:%m:%d %H:%M:%S")
                formatted_date = exif_date.replace(":", "").replace(" ", "-")
                metadata[ExifTag.CREATE_DATE.value] = formatted_date
            except ValueError:
                # Invalid EXIF date format, use fallback
                fallback_date, _ = self._extract_directory_info()
                metadata[ExifTag.CREATE_DATE.value] = fallback_date
                self._logger.warning(
                    f"Invalid EXIF date '{exif_date}', using directory date: {fallback_date}"
                )
        else:
            # EXIF failure: use directory date fallback
            fallback_date, _ = self._extract_directory_info()
            metadata[ExifTag.CREATE_DATE.value] = fallback_date
            self._logger.debug(f"No EXIF date found, using directory date: {fallback_date}")
        metadata[ExifTag.MAKE.value] = metadata.get(
            ExifTag.MAKE.value, self.EXIF_UNKNOWN
        ).replace(" ", "")

        if (
            metadata[ExifTag.MAKE.value] == self.EXIF_UNKNOWN
            and list_type == ListType.RAW_IMAGE_DICT
        ):
            metadata[ExifTag.MAKE.value] = next(
                (
                    key
                    for key, value in self.SUPPORTED_RAW_IMAGE_EXT.items()
                    if any(ext in file_extension for ext in value)
                ),
                self.EXIF_UNKNOWN,
            )

        metadata[ExifTag.MODEL.value] = metadata.get(
            ExifTag.MODEL.value, self.EXIF_UNKNOWN
        ).replace(" ", "")

        if (
            metadata[ExifTag.MAKE.value] in metadata[ExifTag.MODEL.value]
            and metadata[ExifTag.MAKE.value] != self.EXIF_UNKNOWN
        ):
            metadata[ExifTag.MODEL.value] = (
                metadata[ExifTag.MODEL.value].replace(metadata[ExifTag.MAKE.value], "").strip()
            )

        dir_parts = [metadata[ExifTag.MAKE.value], metadata[ExifTag.MODEL.value], file_extension]
        dir_name = "_".join(dir_parts).lower()

        return list_type, dir_name, metadata

    async def _rename_file_async(self, old_name: str, new_file: str) -> None:
        """Rename file asynchronously."""
        try:
            os.rename(old_name, new_file)
            self._logger.debug(f"renamed file: {old_name} to {new_file}")
        except OSError as exp:
            self._logger.error(f"Error renaming: {old_name}: {str(exp)}")

    def _delete_original_raw_files(self, convert_list: list[tuple[str, str]]) -> None:
        """Delete original raw files after successful DNG conversion."""
        for raw_dir, dng_dir in convert_list:
            raw_files = [file_name.rsplit(".", 1)[0] for file_name in os.listdir(raw_dir)]
            dng_files = [file_name.rsplit(".", 1)[0] for file_name in os.listdir(dng_dir)]
            if all(file_name in dng_files for file_name in raw_files):
                self._logger.info(f"Deleting directory: {raw_dir}")
                shutil.rmtree(raw_dir)
            else:
                self._logger.info(f"Not deleting directory: {raw_dir}")
                raw_file_ext = raw_dir.split("_")[-1]
                matching_files = set(raw_files).intersection(dng_files)
                for file_name in matching_files:
                    full_file_name = os.path.join(raw_dir, f"{file_name}.{raw_file_ext}")
                    self._logger.info(f"Deleting file: {full_file_name}")
                    os.remove(full_file_name)

    @function_trace
    async def process_images_reactive(self) -> None:
        """Main reactive pipeline to process images using RxPY."""
        self._validate_image_dir()
        self._change_to_image_dir()

        try:
            with PerformanceTimer(timer_name="ProcessingImages", logger=self._logger):
                # Get files list
                files_list = [f for f in os.listdir(".") if os.path.isfile(f)]
                filtered_list = sorted(
                    [
                        i
                        for i in files_list
                        if not re.match(rf"{self.FILES_TO_EXCLUDE_EXPRESSION}", i)
                    ]
                )
                if not filtered_list:
                    self._logger.info(
                        "No unprocessed files found in the current directory. "
                        "Directory may already be processed."
                    )
                    return
                self._logger.debug(f"filtered_list = {filtered_list}")

                # Extract metadata using ExifTool
                metadata_list = await self.extract_exif_metadata(filtered_list)

                # Create reactive pipeline
                scheduler = AsyncIOScheduler(asyncio.get_event_loop())

                # Process metadata and group by type
                list_collection = {}
                processed_count = 0
                count_lock = threading.Lock()
                total = len(metadata_list)

                def log_progress(item):
                    nonlocal processed_count
                    with count_lock:
                        processed_count += 1
                        current = processed_count
                    # item is a tuple (list_type, dir_name, metadata)
                    _, _, meta = item
                    self._logger.info(
                        f"Completed file {current}/{total}: {meta.get('SourceFile', 'Unknown')}"
                    )

                def process_metadata_item(metadata):
                    result = self._process_metadata(metadata, filtered_list)
                    if result:
                        list_type, dir_name, processed_metadata = result
                        list_collection.setdefault(list_type.value, {}).setdefault(
                            dir_name, []
                        ).append(processed_metadata)
                    return result

                def handle_processing_error(error, metadata):
                    self._logger.warning(
                        f"Failed to process {metadata.get('SourceFile', 'Unknown')}: {error}"
                    )
                    return rx.empty()  # Skip failed items

                # Process all metadata and wait for completion
                completion_future = asyncio.Future()

                def on_completed():
                    self._logger.info(f"✅ Completed processing {processed_count} files")
                    completion_future.set_result(None)

                def on_error(error):
                    self._logger.error(f"❌ Error in processing pipeline: {error}")
                    completion_future.set_exception(error)

                rx.from_iterable(metadata_list).pipe(
                    ops.flat_map(
                        lambda metadata: rx.of(metadata).pipe(
                            ops.subscribe_on(scheduler),
                            ops.map(process_metadata_item),
                            ops.retry(2),  # retry up to 2 times
                            ops.catch(lambda e, _: handle_processing_error(e, metadata)),
                            ops.filter(lambda x: x is not None),
                            ops.do_action(log_progress),
                        )
                    )
                ).subscribe(on_completed=on_completed, on_error=on_error)

                # Wait for the reactive pipeline to complete
                await completion_future

                if not list_collection:
                    raise ValueError("No files to process for the current directory.")

                self._logger.debug(f"list_collection = {json.dumps(list_collection, indent=4)}")

                # Process each file type group
                for key, value in list_collection.items():
                    await self._process_file_group(key, value)

        finally:
            self._change_from_image_dir()

    async def _process_file_group(self, key: str, value: dict[str, list[dict[str, Any]]]) -> None:
        """Process a group of files of the same type."""
        self._logger.info(f"Processing file group: {key = }, {value = }")

        # First, rename all files with sequential numbering
        rename_tasks = []
        for directory, obj_list in value.items():
            file_ext = directory.split("_")[-1]
            self._logger.info(f"{directory = }, {file_ext = }, {obj_list = }")

            if not os.path.exists(directory):
                os.makedirs(directory)

            # Sequential numbering for this directory
            for seq_num, obj in enumerate(obj_list, start=1):
                date_part = obj[ExifTag.CREATE_DATE.value]

                # Determine file name format based on whether EXIF date includes time
                if "-" in date_part and len(date_part) == 15:  # Format: YYYYMMDD-HHMMSS
                    new_file_name = (
                        f"./{directory}/{date_part}_{self.project_name}_{seq_num:03d}.{file_ext}"
                    ).lower()
                else:  # Format: YYYYMMDD (fallback)
                    new_file_name = (
                        f"./{directory}/{date_part}_{self.project_name}_{seq_num:03d}.{file_ext}"
                    ).lower()

                old_file_name = obj[ExifTag.SOURCE_FILE.value]
                self._logger.debug(f"Renaming: {old_file_name} → {new_file_name}")
                rename_tasks.append(self._rename_file_async(old_file_name, new_file_name))

        if rename_tasks:
            await asyncio.gather(*rename_tasks)

        # Handle RAW to DNG conversion
        if key == ListType.RAW_IMAGE_DICT.value:
            await self._handle_raw_conversion(value)

    async def _handle_raw_conversion(self, value: dict[str, list[dict[str, Any]]]) -> None:
        """Handle RAW to DNG conversion for RAW files."""
        self._logger.info(f"Handling RAW conversion: {ListType.RAW_IMAGE_DICT.value = }")

        convert_list: list[tuple[str, str]] = []
        for old_dir in value:
            base_dir, dir_ext = old_dir.rsplit("_", 1)
            if dir_ext == "dng":
                continue
            new_dir = f"{base_dir}_dng"
            convert_list.append((old_dir, new_dir))

        if convert_list:
            self._logger.info(f"{convert_list = }")
            convert_tasks = [
                self.convert_raw_to_dng(old_dir, new_dir) for old_dir, new_dir in convert_list
            ]
            await asyncio.gather(*convert_tasks)
            self._delete_original_raw_files(convert_list)


@function_trace
async def run_pipeline(logger: logging.Logger, image_dir: str) -> None:
    """Main entry point for reactive image processing pipeline.

    Args:
        logger: Logger instance
        image_dir: Directory containing images to process
    """
    processor = ImageProcessor(logger=logger, op_dir=image_dir)
    await processor.process_images_reactive()
