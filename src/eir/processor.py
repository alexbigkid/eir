"""Modern async RxPY-based EXIF Pictures Renaming processor."""

import logging
import os
import re
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from enum import Enum
import shutil
import json
from typing import Any

import reactivex as rx
from reactivex import operators as ops
from reactivex.scheduler.eventloop import AsyncIOScheduler
from pydngconverter import DNGConverter
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
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)

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

        py_dng = DNGConverter(source=Path(src_dir), dest=Path(dst_dir))
        await py_dng.convert()

    def _configure_dng_converter(self) -> None:
        """Configure DNG converter based on platform and available tools."""
        import platform

        if platform.system().lower() == "linux":
            # On Linux, try to use bundled DNGLab
            self._logger.info(
                f"Configuring DNG converter for Linux, machine: {platform.machine()}"
            )
            dnglab_path = self._find_dnglab_binary()
            if dnglab_path:
                os.environ["PYDNG_DNG_CONVERTER"] = dnglab_path
                self._logger.info(f"Configured DNGLab for DNG conversion: {dnglab_path}")
                # Verify the binary is executable
                dnglab_file = Path(dnglab_path)
                if dnglab_file.exists() and os.access(dnglab_path, os.X_OK):
                    self._logger.info(f"DNGLab binary is executable: {dnglab_path}")
                else:
                    self._logger.warning(f"DNGLab binary is not executable: {dnglab_path}")
            else:
                self._logger.warning("DNGLab not found - DNG conversion may fail on Linux")

    def _find_dnglab_binary(self) -> str | None:
        """Find DNGLab binary in bundled resources or system PATH."""
        import platform
        import sys
        import shutil

        machine = platform.machine().lower()
        dnglab_arch = "aarch64" if machine in ["aarch64", "arm64"] else "x86_64"

        self._logger.info(f"Looking for DNGLab binary, machine: {machine}, arch: {dnglab_arch}")

        # Try bundled DNGLab first (PyInstaller extracts to temp dir)
        if getattr(sys, "frozen", False):
            # Running as compiled binary
            bundle_dir = sys._MEIPASS  # PyInstaller temp directory
            self._logger.info(f"Running as compiled binary, bundle_dir: {bundle_dir}")
            dnglab_bundled = Path(bundle_dir) / "tools" / "linux" / f"dnglab_{dnglab_arch}"
            self._logger.info(f"Checking bundled DNGLab: {dnglab_bundled}")
            if dnglab_bundled.exists():
                self._logger.info(f"Found bundled DNGLab: {dnglab_bundled}")
                return str(dnglab_bundled)
            else:
                self._logger.warning(f"Bundled DNGLab not found: {dnglab_bundled}")
                # List available files in bundle tools directory for debugging
                tools_dir = Path(bundle_dir) / "tools" / "linux"
                if tools_dir.exists():
                    available_files = list(tools_dir.glob("*"))
                    self._logger.warning(f"Available files in {tools_dir}: {available_files}")
                else:
                    self._logger.warning(f"Tools directory not found: {tools_dir}")

        # Try system PATH
        dnglab_system = shutil.which("dnglab")
        if dnglab_system:
            self._logger.info(f"Found DNGLab in system PATH: {dnglab_system}")
            return dnglab_system

        # Try local tools directory (development)
        dnglab_local = Path("tools") / "linux" / f"dnglab_{dnglab_arch}"
        self._logger.info(f"Checking local DNGLab: {dnglab_local}")
        if dnglab_local.exists():
            self._logger.info(f"Found local DNGLab: {dnglab_local}")
            return str(dnglab_local.absolute())

        self._logger.warning("No DNGLab binary found")
        return None

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
        for old_dir, _obj_list in value.items():
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
