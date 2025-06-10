"""EXIF Pictures Renaming app."""
import logging
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime
from reactivex import from_iterable
from reactivex.operators import flat_map
from reactivex.scheduler.eventloop import AsyncIOScheduler

from eir.abk_common import function_trace

# Placeholder for EXIF reading
async def extract_exif_metadata(image_path):
    await asyncio.sleep(0.01)
    return {
        "datetime": datetime.now(),
        "make": "Canon",
        "model": "EOS_5D"
    }


# Placeholder for DNG conversion
async def convert_to_dng(image_path):
    await asyncio.sleep(0.02)
    return image_path.with_suffix(".dng")


# Rename image with proper pattern
def format_new_filename(base_datetime, project_name, index, ext):
    """Formats new filename.

    Args:
        base_datetime (_type_): _description_
        project_name (_type_): _description_
        index (_type_): _description_
        ext (_type_): _description_

    Returns:
        _type_: _description_
    """
    timestamp = base_datetime.strftime("%Y%m%d-%H%M")
    return f"{timestamp}_{project_name}_{index:03d}{ext}"


@function_trace
# RxPy + asyncio pipeline
async def run_pipeline(logger: logging.Logger, image_dir: str):
    """Run pipeline to process images.

    Args:
        logger (logging.logger): logger to use
        image_dir (str): directory with images
    """
    logger.info(f"Processing directory: {image_dir}")
    path = Path(image_dir)
    if not path.exists():
        raise FileNotFoundError(f"Input directory not found: {image_dir}")

    last_part = path.name
    match = re.match(r"^(\d{8})_(.+)$", last_part)
    if not match:
        raise ValueError("Directory name must be in format YYYYMMDD_project_name")

    date_prefix, project_name = match.groups()

    files = sorted([f for f in path.iterdir() if f.is_file() and not f.name.startswith(".")])
    scheduler = AsyncIOScheduler(asyncio.get_event_loop())
    counter = {"i": 1}

    def process_file(file_path: str):
        """process_file _summary_

        Args:
            file_path (str): _description_
        """
        async def inner():
            metadata = await extract_exif_metadata(file_path)
            make_model = f"{metadata['make']}_{metadata['model']}".replace(" ", "_")
            output_dir = path / make_model
            output_dir.mkdir(exist_ok=True)

            base_datetime = metadata["datetime"]
            ext = file_path.suffix.lower()
            index = counter["i"]
            counter["i"] += 1

            if ext in [".cr2", ".nef", ".arw", ".rw2", ".orf"]:
                file_path = await convert_to_dng(file_path)
                ext = ".dng"

            new_name = format_new_filename(base_datetime, project_name, index, ext)
            target_path = output_dir / new_name
            file_path.rename(target_path)
            print(f"Renamed: {file_path.name} -> {target_path}")
        return inner()

    await from_iterable(files).pipe(
        flat_map(lambda f: asyncio.ensure_future(process_file(f)))
    ).run_async()
"""Modern async RxPY-based EXIF Pictures Renaming processor."""
import logging
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime
from enum import Enum
import shutil
import json
from typing import Any

from reactivex import from_iterable
from reactivex.operators import map as rx_map, filter as rx_filter
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
        "gif", "heic", "jpg", "jpeg", "jng", "mng", "png", "psd", "tiff", "tif"
    ]
    SUPPORTED_COMPRESSED_VIDEO_EXT_LIST = [
        "3g2", "3gp2", "crm", "m4a", "m4b", "m4p", "m4v", "mov", "mp4", "mqv", "qt"
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

    @property
    def project_name(self) -> str:
        """Returns project name extracted from directory."""
        if self._project_name is None:
            current_dir = os.getcwd()
            norm_path = os.path.basename(os.path.normpath(current_dir))
            dir_parts = norm_path.split("_")
            self._project_name = "_".join(dir_parts[1:])
            self._logger.info(f"{self._project_name = }")
        return self._project_name

    async def extract_exif_metadata(self, files_list: list[str]) -> list[dict[str, Any]]:
        """Extract EXIF metadata from files using ExifTool."""
        with exiftool.ExifToolHelper() as etp:
            etp.logger = self._logger
            metadata_list = etp.get_tags(files=files_list, tags=self.EXIF_TAGS)
            self._logger.debug(f"{metadata_list = }")
            return metadata_list

    async def convert_raw_to_dng(self, src_dir: str, dst_dir: str) -> None:
        """Convert RAW files to DNG format."""
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        py_dng = DNGConverter(source=Path(src_dir), dest=Path(dst_dir))
        await py_dng.convert()

    def _validate_image_dir(self) -> None:
        """Validate that directory follows YYYYMMDD_project_name format."""
        self._logger.debug(f"{self._op_dir = }")
        try:
            dir_name_to_validate = self._op_dir if self._op_dir != "." else os.getcwd()
            last_part_of_dir = os.path.basename(os.path.normpath(dir_name_to_validate))

            match = re.match(r"^(\d{8})_\w+$", last_part_of_dir)
            if not match:
                raise ValueError("Regex match failed")

            datetime.strptime(match.group(1), "%Y%m%d")

        except (AttributeError, ValueError) as e:
            raise Exception(
                "Not a valid date / directory format, please use: YYYYMMDD_name_of_the_project"
            ) from e

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

        # Process metadata
        metadata[ExifTag.CREATE_DATE.value] = (
            metadata.get(ExifTag.CREATE_DATE.value, self.EXIF_UNKNOWN)
            .replace(":", "")
            .replace(" ", "_")
        )
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
                metadata[ExifTag.MODEL.value]
                .replace(metadata[ExifTag.MAKE.value], "")
                .strip()
            )

        dir_parts = [
            metadata[ExifTag.MAKE.value],
            metadata[ExifTag.MODEL.value],
            file_extension,
        ]
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
                filtered_list = sorted([
                    i for i in files_list
                    if not re.match(rf"{self.FILES_TO_EXCLUDE_EXPRESSION}", i)
                ])

                if not filtered_list:
                    raise Exception("No files to process for the current directory.")

                self._logger.debug(f"filtered_list = {filtered_list}")

                # Extract metadata using ExifTool
                metadata_list = await self.extract_exif_metadata(filtered_list)

                # Create reactive pipeline
                scheduler = AsyncIOScheduler(asyncio.get_event_loop())

                # Process metadata and group by type
                list_collection = {}

                def process_metadata_item(metadata):
                    result = self._process_metadata(metadata, filtered_list)
                    if result:
                        list_type, dir_name, processed_metadata = result
                        list_collection.setdefault(list_type.value, {}).setdefault(
                            dir_name, []
                        ).append(processed_metadata)
                    return result

                # Process all metadata
                await from_iterable(metadata_list).pipe(
                    rx_map(process_metadata_item),
                    rx_filter(lambda x: x is not None)
                ).run_async(scheduler=scheduler)

                if not list_collection:
                    raise Exception("No files to process for the current directory.")

                self._logger.debug(f"list_collection = {json.dumps(list_collection, indent=4)}")

                # Process each file type group
                for key, value in list_collection.items():
                    await self._process_file_group(key, value)

        finally:
            self._change_from_image_dir()

    async def _process_file_group(self, key: str, value: dict[str, list[dict[str, Any]]]) -> None:
        """Process a group of files of the same type."""
        self._logger.info(f"Processing file group: {key = }, {value = }")

        # First, rename all files
        rename_tasks = []
        for directory, obj_list in value.items():
            file_ext = directory.split("_")[-1]
            self._logger.info(f"{directory = }, {file_ext = }, {obj_list = }")

            if not os.path.exists(directory):
                os.makedirs(directory)

            for obj in obj_list:
                new_file_name = (
                    f"./{directory}/{obj[ExifTag.CREATE_DATE.value]}_"
                    f"{obj[ExifTag.MAKE.value]}_{obj[ExifTag.MODEL.value]}_"
                    f"{self.project_name}.{file_ext}"
                ).lower()
                old_file_name = obj[ExifTag.SOURCE_FILE.value]
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
                self.convert_raw_to_dng(old_dir, new_dir)
                for old_dir, new_dir in convert_list
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
