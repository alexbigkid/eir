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
