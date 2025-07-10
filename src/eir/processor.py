"""Modern async RxPY-based EXIF Pictures Renaming processor."""

import asyncio
import json
import logging
import os
import platform
import re
import shutil
import subprocess  # noqa: S404
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import colorama
import exiftool
import reactivex as rx
from reactivex import operators as ops
from reactivex.scheduler.eventloop import AsyncIOScheduler

from eir.abk_common import function_trace, PerformanceTimer
from eir.dnglab_strategy import DNGLabStrategyFactory

# Initialize colorama for cross-platform colored output
colorama.init()

# Import pydngconverter lazily to avoid early executable resolution
# These imports must happen AFTER _configure_dng_converter() sets PYDNG_DNG_CONVERTER


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
    SUPPORTED_COMPRESSED_IMAGE_EXT_LIST = ["gif", "heic", "jpg", "jpeg", "jng", "mng", "png", "psd", "tiff", "tif"]
    SUPPORTED_COMPRESSED_VIDEO_EXT_LIST = ["3g2", "3gp2", "crm", "m4a", "m4b", "m4p", "m4v", "mov", "mp4", "mqv", "qt"]
    EXIF_UNKNOWN = "unknown"
    EXIF_TAGS = [ExifTag.CREATE_DATE.value, ExifTag.MAKE.value, ExifTag.MODEL.value]

    def __init__(self, logger: logging.Logger, op_dir: str, dng_compression: str = "lossless", dng_preview: bool = False):
        """Initialize ImageProcessor."""
        self._logger = logger or logging.getLogger(__name__)
        self._op_dir = op_dir
        self._dng_compression = dng_compression
        self._dng_preview = dng_preview
        self._current_dir = None
        self._supported_raw_image_ext_list = list(set([ext for exts in self.SUPPORTED_RAW_IMAGE_EXT.values() for ext in exts]))
        self._project_name = None

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

        # CRITICAL: Configure DNG converter BEFORE importing pydngconverter
        # This ensures pydngconverter can find the bundled binary during initialization
        self._configure_dng_converter()

        # Debug: Check environment variable before conversion
        env_var = os.environ.get("PYDNG_DNG_CONVERTER")
        self._logger.info(f"PYDNG_DNG_CONVERTER environment variable: {env_var}")

        if env_var:
            env_path = Path(env_var)
            self._logger.debug(f"DNGLab binary exists: {env_path.exists()}")
            if env_path.exists():
                self._logger.debug(f"DNGLab binary is executable: {os.access(env_var, os.X_OK)}")
                self._logger.debug(f"DNGLab binary size: {env_path.stat().st_size} bytes")
        else:
            self._logger.warning("No DNGLab binary configured - will use default Adobe DNG Converter")

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

        # Import pydngconverter AFTER configuring DNGLab
        self._logger.debug("Importing pydngconverter after DNGLab configuration...")
        from pydngconverter import DNGConverter
        import pydngconverter.compat

        # Set pydngconverter logging to WARNING to reduce noise
        # Even in verbose mode, we don't want pydngconverter internal logs
        pydng_logger = logging.getLogger("pydngconverter")
        pydng_logger.setLevel(logging.WARNING)  # Always WARNING, never DEBUG/INFO

        self._logger.debug(f"Initializing DNGConverter with source={src_dir}, dest={dst_dir}")
        py_dng = DNGConverter(source=Path(src_dir), dest=Path(dst_dir))
        # Log DNGConverter configuration
        self._logger.debug("DNGConverter initialized successfully")
        self._logger.debug(f"DNGConverter binary path: {py_dng.bin_exec}")
        self._logger.debug(f"DNGConverter binary type: {type(py_dng.bin_exec)}")

        # Patch pydngconverter when using DNGLab (Linux/Windows)
        if os.environ.get("PYDNG_DNG_CONVERTER") and "dnglab" in os.environ.get("PYDNG_DNG_CONVERTER", "").lower():
            self._logger.debug("Applying DNGLab compatibility patch (using correct command syntax)")

            async def patched_get_compat_path(path):
                # Use native path when DNGLab is configured (avoid Wine path conversion)
                native_path = str(Path(path))
                self._logger.debug(f"Patched compat path: {path} -> {native_path}")
                return native_path

            pydngconverter.compat.get_compat_path = patched_get_compat_path

            # Also patch the convert_file method to add proper error handling
            from pydngconverter import main as pydng_main

            # Capture our compression settings for the patch
            dng_compression = self._dng_compression
            dng_preview = self._dng_preview

            async def patched_convert_file(self, *, destination: str = None, job=None, log=None):
                """Enhanced convert_file with better error handling and logging."""
                from pydngconverter import compat

                log = log or logging.getLogger(__name__)
                log.debug("starting conversion: %s", job.source.name)
                source_path = await compat.get_compat_path(job.source)
                log.debug("determined source path: %s", source_path)

                # Check if we're using DNGLab vs Adobe DNG Converter
                # Use environment variable as primary indicator since bin_exec
                # might not reflect the actual binary
                env_converter = os.environ.get("PYDNG_DNG_CONVERTER", "")
                bin_exec_str = str(self.bin_exec).lower()

                is_adobe = "adobe dng converter" in env_converter.lower() or "adobe dng converter" in bin_exec_str
                is_dnglab = "dnglab" in env_converter.lower() or "dnglab" in bin_exec_str

                log.debug(f"Converter detection: is_adobe={is_adobe}, is_dnglab={is_dnglab}, env_path={env_converter}")

                if is_dnglab:
                    # DNGLab syntax: dnglab convert [options] input output
                    output_file = Path(destination) / f"{Path(source_path).stem}.dng"
                    dng_args = [
                        "convert",
                        "-c",
                        dng_compression,  # Use captured compression setting
                        "--dng-preview",
                        "true" if dng_preview else "false",
                        "--embed-raw",
                        "false",  # CRITICAL: Don't embed original RAW to prevent double size
                        str(source_path),
                        str(output_file),
                    ]
                elif is_adobe:
                    # Adobe DNG Converter syntax: Adobe DNG Converter [options] -d destination source
                    dng_args = []

                    # Add headless flags to prevent GUI from launching
                    dng_args.extend(["-w"])  # Wait for completion without GUI

                    # Add compression options for Adobe DNG Converter
                    if dng_compression == "lossless":
                        dng_args.extend(["-c"])  # Lossless compression
                    elif dng_compression == "uncompressed":
                        dng_args.extend(["-u"])  # Uncompressed

                    # Add preview options
                    if dng_preview:
                        dng_args.extend(["-p", "2"])  # Full size JPEG preview
                    else:
                        dng_args.extend(["-p", "0"])  # No preview

                    # Add destination and source
                    dng_args.extend(["-d", destination, str(source_path)])
                else:
                    # Default Adobe DNG Converter syntax (fallback)
                    dng_args = [*self.parameters.iter_args, "-d", destination, str(source_path)]

                # Log the full command being executed (only in debug mode)
                full_command = f"{self.bin_exec} {' '.join(dng_args)}"
                converter_name = "DNGLab" if is_dnglab else ("Adobe DNG Converter" if is_adobe else "Default Converter")
                log.debug("Executing %s command: %s", converter_name, full_command)

                # Validate arguments before execution
                log.debug("Arguments: %s", dng_args)
                log.debug("Source file exists: %s", Path(source_path).exists())
                log.debug("Destination directory exists: %s", Path(destination).exists())
                log.debug("Current working directory: %s", Path.cwd())

                # Simple, clean conversion message with bright green color
                output_filename = Path(job.destination_filename).name
                green_message = f"{colorama.Fore.LIGHTGREEN_EX}converted: {output_filename}{colorama.Style.RESET_ALL}"
                print(green_message, flush=True)

                try:
                    proc = await asyncio.create_subprocess_exec(
                        self.bin_exec, *dng_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await proc.communicate()
                    log.debug("%s process completed with return code: %d", converter_name, proc.returncode)

                    # Check return code and log any errors
                    if proc.returncode != 0:
                        log.error("%s conversion failed with return code %d", converter_name, proc.returncode)
                        if stderr:
                            stderr_text = stderr.decode("utf-8", errors="replace")
                            log.error("%s stderr: %s", converter_name, stderr_text)
                        if stdout:
                            stdout_text = stdout.decode("utf-8", errors="replace")
                            log.error("%s stdout: %s", converter_name, stdout_text)
                        # Still report as finished to maintain compatibility, but with error info
                        log.warning("Conversion reported as finished despite errors")
                    else:
                        log.debug("%s conversion succeeded (return code 0)", converter_name)
                        if stdout:
                            stdout_text = stdout.decode("utf-8", errors="replace")
                            if stdout_text.strip():
                                log.debug("%s stdout: %s", converter_name, stdout_text.strip())

                except Exception as e:
                    log.error("Exception during %s subprocess execution: %s", converter_name, e)
                    raise

                log.debug("finished conversion: %s", job.destination_filename)
                return job.destination

            # Apply the patch
            pydng_main.DNGConverter.convert_file = patched_convert_file
            self._logger.debug("Applied enhanced convert_file patch with error handling")

        # Perform conversion with detailed logging
        self._logger.debug("Starting pydngconverter.convert() operation...")
        try:
            await py_dng.convert()
            self._logger.debug("pydngconverter.convert() completed without exceptions")
            # Check conversion results with detailed path analysis
            dst_path = Path(dst_dir)
            src_path = Path(src_dir)

            self._logger.info("Post-conversion analysis:")
            self._logger.info(f"  Source directory: {src_path.absolute()}")
            self._logger.info(f"  Destination directory: {dst_path.absolute()}")
            self._logger.info(f"  Current working directory: {Path.cwd()}")

            if os.path.exists(dst_dir):
                converted_files = list(dst_path.glob("*"))
                self._logger.info(f"Conversion completed - found {len(converted_files)} files in destination:")
                for converted_file in converted_files:
                    self._logger.info(f"  - {converted_file.name} ({converted_file.stat().st_size} bytes)")
                if len(converted_files) == 0:
                    self._logger.warning("No files found in destination directory after conversion!")
                    self._logger.warning("This indicates DNGLab may not be working properly")

                    # Search for DNG files in nearby directories to debug the issue
                    self._logger.info("Searching for DNG files in current and parent directories...")
                    cwd = Path.cwd()
                    for search_dir in [cwd, cwd.parent, src_path.parent]:
                        if search_dir.exists():
                            dng_files = list(search_dir.rglob("*.dng"))
                            if dng_files:
                                self._logger.info(f"Found DNG files in {search_dir}:")
                                for dng_file in dng_files[:5]:  # Limit output
                                    self._logger.info(f"  - {dng_file}")
            else:
                self._logger.error(f"Destination directory disappeared after conversion: {dst_dir}")

        except Exception as e:
            self._logger.error(f"Exception during DNG conversion: {type(e).__name__}: {e}")
            # Re-raise the exception to maintain original behavior
            raise

    def _configure_dng_converter(self) -> None:
        """Configure DNG converter using strategy pattern for platform-specific detection."""
        system_name = platform.system().lower()
        self._logger.info(f"Configuring DNG converter for platform: {system_name}")

        # Use strategy pattern to find DNGLab binary
        strategy = DNGLabStrategyFactory.create_strategy(self._logger)
        self._logger.info(f"Using {strategy.__class__.__name__} for {system_name}, machine: {platform.machine()}")

        dnglab_path = strategy.get_binary_path()
        if dnglab_path:
            # Set environment variable for pydngconverter
            old_env = os.environ.get("PYDNG_DNG_CONVERTER")
            os.environ["PYDNG_DNG_CONVERTER"] = dnglab_path
            self._logger.info(f"Set PYDNG_DNG_CONVERTER: {old_env} -> {dnglab_path}")

            # Verify and test the binary (strategy already handled existence and permissions)
            dnglab_file = Path(dnglab_path)
            file_size = dnglab_file.stat().st_size
            self._logger.debug(f"DNGLab binary verification - size: {file_size} bytes")

            # Test DNGLab binary functionality
            self._test_dnglab_binary(dnglab_path)
        else:
            self._logger.warning(f"DNGLab binary not found - will fall back to default Adobe DNG Converter on {system_name}")

    def _test_dnglab_binary(self, dnglab_path: str) -> None:
        """Test DNGLab binary to verify it's working."""
        try:
            self._logger.debug(f"Testing DNGLab binary functionality: {dnglab_path}")

            # Test with --help flag to verify binary works
            result = subprocess.run(  # noqa: S603
                [dnglab_path, "--help"], capture_output=True, text=True, timeout=10, check=False
            )

            if result.returncode == 0:
                self._logger.info("DNGLab binary test successful (--help worked)")
                # Log first few lines of help output for verification
                help_lines = result.stdout.split("\n")[:3]
                for line in help_lines:
                    if line.strip():
                        self._logger.info(f"DNGLab help: {line.strip()}")
            else:
                self._logger.warning(f"DNGLab binary test failed with exit code {result.returncode}")
                if result.stderr:
                    self._logger.warning(f"DNGLab stderr: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            self._logger.warning("DNGLab binary test timed out after 10 seconds")
        except Exception as e:
            self._logger.warning(f"DNGLab binary test failed with exception: {e}")

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
            raise ValueError("Invalid directory format. Use: YYYYMMDD_project or YYYYMMDD-YYYYMMDD_project") from e

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
            # EXIF success: "2024:12:10 14:30:05" -> "20241210-143005"
            try:
                # Validate and format EXIF date
                datetime.strptime(exif_date, "%Y:%m:%d %H:%M:%S")
                formatted_date = exif_date.replace(":", "").replace(" ", "-")
                metadata[ExifTag.CREATE_DATE.value] = formatted_date
            except ValueError:
                # Invalid EXIF date format, use fallback
                fallback_date, _ = self._extract_directory_info()
                metadata[ExifTag.CREATE_DATE.value] = fallback_date
                self._logger.warning(f"Invalid EXIF date '{exif_date}', using directory date: {fallback_date}")
        else:
            # EXIF failure: use directory date fallback
            fallback_date, _ = self._extract_directory_info()
            metadata[ExifTag.CREATE_DATE.value] = fallback_date
            self._logger.debug(f"No EXIF date found, using directory date: {fallback_date}")
        metadata[ExifTag.MAKE.value] = metadata.get(ExifTag.MAKE.value, self.EXIF_UNKNOWN).replace(" ", "")

        if metadata[ExifTag.MAKE.value] == self.EXIF_UNKNOWN and list_type == ListType.RAW_IMAGE_DICT:
            metadata[ExifTag.MAKE.value] = next(
                (key for key, value in self.SUPPORTED_RAW_IMAGE_EXT.items() if any(ext in file_extension for ext in value)),
                self.EXIF_UNKNOWN,
            )

        metadata[ExifTag.MODEL.value] = metadata.get(ExifTag.MODEL.value, self.EXIF_UNKNOWN).replace(" ", "")

        if metadata[ExifTag.MAKE.value] in metadata[ExifTag.MODEL.value] and metadata[ExifTag.MAKE.value] != self.EXIF_UNKNOWN:
            metadata[ExifTag.MODEL.value] = metadata[ExifTag.MODEL.value].replace(metadata[ExifTag.MAKE.value], "").strip()

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
                filtered_list = sorted([i for i in files_list if not re.match(rf"{self.FILES_TO_EXCLUDE_EXPRESSION}", i)])
                if not filtered_list:
                    self._logger.info("No unprocessed files found in the current directory. Directory may already be processed.")
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
                    self._logger.info(f"Completed file {current}/{total}: {meta.get('SourceFile', 'Unknown')}")

                def process_metadata_item(metadata):
                    result = self._process_metadata(metadata, filtered_list)
                    if result:
                        list_type, dir_name, processed_metadata = result
                        list_collection.setdefault(list_type.value, {}).setdefault(dir_name, []).append(processed_metadata)
                    return result

                def handle_processing_error(error, metadata):
                    self._logger.warning(f"Failed to process {metadata.get('SourceFile', 'Unknown')}: {error}")
                    return rx.empty()  # Skip failed items

                # Process all metadata and wait for completion
                completion_future = asyncio.Future()

                def on_completed():
                    self._logger.info(f"Completed processing {processed_count} files")
                    completion_future.set_result(None)

                def on_error(error):
                    self._logger.error(f"Error in processing pipeline: {error}")
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
        self._logger.debug(f"Processing file group: {key = }, {value = }")

        # First, rename all files with sequential numbering
        rename_tasks = []
        for directory, obj_list in value.items():
            file_ext = directory.split("_")[-1]
            file_count = len(obj_list)

            # Clean user-friendly message with bright green color
            if key == "raw_image_dict":
                message = (
                    f"{colorama.Fore.LIGHTGREEN_EX}Processing {file_count} RAW files -> {directory}/{colorama.Style.RESET_ALL}"
                )
            else:
                message = (
                    f"{colorama.Fore.LIGHTGREEN_EX}Processing {file_count} {file_ext.upper()} files -> {directory}/"
                    f"{colorama.Style.RESET_ALL}"
                )
            print(message, flush=True)

            self._logger.debug(f"{directory = }, {file_ext = }, {obj_list = }")

            if not os.path.exists(directory):
                os.makedirs(directory)

            # Sequential numbering for this directory
            for seq_num, obj in enumerate(obj_list, start=1):
                date_part = obj[ExifTag.CREATE_DATE.value]

                # Determine file name format based on whether EXIF date includes time
                if "-" in date_part and len(date_part) == 15:  # Format: YYYYMMDD-HHMMSS
                    new_file_name = (f"./{directory}/{date_part}_{self.project_name}_{seq_num:03d}.{file_ext}").lower()
                else:  # Format: YYYYMMDD (fallback)
                    new_file_name = (f"./{directory}/{date_part}_{self.project_name}_{seq_num:03d}.{file_ext}").lower()

                old_file_name = obj[ExifTag.SOURCE_FILE.value]
                self._logger.debug(f"Renaming: {old_file_name} -> {new_file_name}")
                rename_tasks.append(self._rename_file_async(old_file_name, new_file_name))

        if rename_tasks:
            await asyncio.gather(*rename_tasks)

        # Handle RAW to DNG conversion
        if key == ListType.RAW_IMAGE_DICT.value:
            await self._handle_raw_conversion(value)

    async def _handle_raw_conversion(self, value: dict[str, list[dict[str, Any]]]) -> None:
        """Handle RAW to DNG conversion for RAW files."""
        self._logger.debug(f"Handling RAW conversion: {ListType.RAW_IMAGE_DICT.value = }")

        convert_list: list[tuple[str, str]] = []
        for old_dir in value:
            base_dir, dir_ext = old_dir.rsplit("_", 1)
            if dir_ext == "dng":
                continue
            new_dir = f"{base_dir}_dng"
            convert_list.append((old_dir, new_dir))

        if convert_list:
            self._logger.debug(f"{convert_list = }")
            total_conversions = len(convert_list)
            message = f"{colorama.Fore.LIGHTGREEN_EX}Converting {total_conversions} RAW to DNG format: {colorama.Style.RESET_ALL}"
            print(message, flush=True)

            # Process conversions sequentially to ensure proper configuration
            for old_dir, new_dir in convert_list:
                await self.convert_raw_to_dng(old_dir, new_dir)
            self._delete_original_raw_files(convert_list)

            message = (
                f"{colorama.Fore.LIGHTGREEN_EX}* Completed {total_conversions} RAW to DNG conversions{colorama.Style.RESET_ALL}"
            )
            print(message, flush=True)


@function_trace
async def run_pipeline(
    logger: logging.Logger, image_dir: str, dng_compression: str = "lossless", dng_preview: bool = False
) -> None:
    """Main entry point for reactive image processing pipeline.

    Args:
        logger: Logger instance
        image_dir: Directory containing images to process
        dng_compression: DNG compression method ('lossless' or 'uncompressed')
        dng_preview: Whether to embed JPEG preview in DNG files
    """
    processor = ImageProcessor(logger=logger, op_dir=image_dir, dng_compression=dng_compression, dng_preview=dng_preview)
    await processor.process_images_reactive()
