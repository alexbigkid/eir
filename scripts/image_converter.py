"""Image converter for real estate listing websites.

Converts images (DNG, HEIC, JPG, PNG, TIFF, BMP, WebP) to optimized JPEG
for platforms like Zillow, Apartments.com, and Facebook.
"""

import argparse
import asyncio
import io
import logging
import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import colorama
import exiftool
import rawpy
import reactivex as rx
from PIL import Image, ImageEnhance, ImageStat
from reactivex import operators as ops
from reactivex.scheduler.eventloop import AsyncIOScheduler

colorama.init()

logger = logging.getLogger("image_converter")


class ConvertFormat(StrEnum):
    """Supported input formats for image conversion."""

    DNG = ".dng"
    HEIC = ".heic"
    HEIF = ".heif"
    JPG = ".jpg"
    JPEG = ".jpeg"
    PNG = ".png"
    TIFF = ".tiff"
    TIF = ".tif"
    BMP = ".bmp"
    WEBP = ".webp"


CONVERTIBLE_EXTENSIONS = {fmt.value for fmt in ConvertFormat}


@dataclass
class ConversionTask:
    """Represents a single image conversion task."""

    source: Path
    destination: Path
    exif_date: datetime
    quality: int
    max_dimension: int


@dataclass
class ConversionResult:
    """Result of a single image conversion."""

    source: Path
    destination: Path
    success: bool
    error: str | None = None


def collect_convertible_files(input_dir: Path) -> list[Path]:
    """Scan top-level directory for files with convertible extensions."""
    files = []
    for entry in input_dir.iterdir():
        if entry.is_file() and not entry.name.startswith(".") and entry.suffix.lower() in CONVERTIBLE_EXTENSIONS:
            files.append(entry)
    return sorted(files)


def extract_and_sort_by_date(files: list[Path]) -> list[tuple[Path, datetime]]:
    """Extract EXIF dates and sort files earliest first."""
    if not files:
        return []

    file_dates: list[tuple[Path, datetime]] = []
    with exiftool.ExifToolHelper() as etp:
        etp.logger = logger
        metadata_list = etp.get_tags([str(f) for f in files], ["EXIF:CreateDate"])

    for meta in metadata_list:
        source = Path(meta["SourceFile"])
        date_str = meta.get("EXIF:CreateDate", "")
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                logger.warning(f"Invalid EXIF date '{date_str}' for {source.name}, using file mtime")
                dt = datetime.fromtimestamp(source.stat().st_mtime)
        else:
            logger.debug(f"No EXIF date for {source.name}, using file mtime")
            dt = datetime.fromtimestamp(source.stat().st_mtime)
        file_dates.append((source, dt))

    file_dates.sort(key=lambda x: x[1])
    return file_dates


def generate_output_name(output_dir: Path, index: int, exif_date: datetime) -> Path:
    """Build output filename with date, directory name, and counter."""
    dir_name = output_dir.name
    date_str = exif_date.strftime("%Y%m%d_%H%M%S")
    filename = f"{date_str}_{dir_name}_{index:03d}.jpg"
    return output_dir / filename


def _convert_icc_to_srgb(img: Image.Image, file_path: Path) -> Image.Image:
    """Convert image from embedded ICC color profile to sRGB."""
    from PIL import ImageCms

    icc_data = img.info.get("icc_profile")
    if not icc_data:
        return img

    try:
        src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_data))
        srgb_profile = ImageCms.createProfile("sRGB")
        converted = ImageCms.profileToProfile(img, src_profile, srgb_profile, outputMode="RGB")
        if converted is not None:
            img = converted
        logger.debug(f"Color-managed conversion for {file_path.name}")
    except (ImageCms.PyCMSError, OSError) as e:
        logger.warning(f"ICC profile conversion failed for {file_path.name}: {e}")

    return img


def open_any_image(file_path: Path) -> Image.Image:
    """Open image dispatching by format and convert to sRGB."""
    suffix = file_path.suffix.lower()

    if suffix == ".dng":
        return _open_dng(file_path)
    if suffix in (".heic", ".heif"):
        return _open_heic(file_path)

    img = Image.open(file_path)
    return _convert_icc_to_srgb(img, file_path)


_DNG_TARGET_BRIGHTNESS = 115.0
_DNG_DARK_THRESHOLD = 80.0


def _open_dng(file_path: Path) -> Image.Image:
    """Open DNG file using rawpy (LibRaw) and return as PIL Image."""
    with rawpy.imread(str(file_path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True)
    img = Image.fromarray(rgb)

    # Auto-brighten if rawpy produced a dark result
    mean_brightness = sum(ImageStat.Stat(img).mean) / 3
    if mean_brightness < _DNG_DARK_THRESHOLD:
        factor = _DNG_TARGET_BRIGHTNESS / mean_brightness
        img = ImageEnhance.Brightness(img).enhance(factor)
        logger.debug(f"Auto-brightened {file_path.name}: factor={factor:.2f}")

    return img


def _open_heic(file_path: Path) -> Image.Image:
    """Open HEIC/HEIF file via pillow-heif and convert to sRGB."""
    import pillow_heif

    pillow_heif.register_heif_opener()
    img = Image.open(file_path)
    return _convert_icc_to_srgb(img, file_path)


def resize_preserve_aspect(img: Image.Image, max_dim: int) -> Image.Image:
    """Resize longest side to max_dim with LANCZOS resampling. No-op if already smaller."""
    width, height = img.size
    longest = max(width, height)
    if longest <= max_dim:
        return img

    ratio = max_dim / longest
    new_width = int(width * ratio)
    new_height = int(height * ratio)
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def convert_single(task: ConversionTask) -> ConversionResult:
    """Open, resize, convert to RGB, and save as optimized JPEG."""
    try:
        img = open_any_image(task.source)
        img = resize_preserve_aspect(img, task.max_dimension)
        if img.mode != "RGB":
            img = img.convert("RGB")
        task.destination.parent.mkdir(parents=True, exist_ok=True)
        img.save(task.destination, "JPEG", optimize=True, quality=task.quality)

        green = f"{colorama.Fore.LIGHTGREEN_EX}converted: {task.destination.name}{colorama.Style.RESET_ALL}"
        print(green, flush=True)
        return ConversionResult(source=task.source, destination=task.destination, success=True)
    except Exception as e:
        logger.error(f"Failed to convert {task.source.name}: {e}")
        return ConversionResult(source=task.source, destination=task.destination, success=False, error=str(e))


def convert_all(tasks: list[ConversionTask]) -> list[ConversionResult]:
    """RxPY reactive pipeline for concurrent image conversion."""
    if not tasks:
        return []

    results: list[ConversionResult] = []
    processed_count = 0
    count_lock = threading.Lock()
    total = len(tasks)

    loop = asyncio.new_event_loop()
    scheduler = AsyncIOScheduler(loop)
    completion_event = threading.Event()
    pipeline_error = None

    def process_task(task):
        nonlocal processed_count
        result = convert_single(task)
        with count_lock:
            processed_count += 1
            current = processed_count
        logger.info(f"Processed {current}/{total}: {task.source.name}")
        results.append(result)
        return result

    def on_completed():
        logger.info(f"Completed converting {processed_count} images")
        completion_event.set()

    def on_error(error):
        nonlocal pipeline_error
        logger.error(f"Error in conversion pipeline: {error}")
        pipeline_error = error
        completion_event.set()

    rx.from_iterable(tasks).pipe(
        ops.flat_map(
            lambda task: rx.of(task).pipe(
                ops.subscribe_on(scheduler), ops.map(process_task), ops.retry(2), ops.catch(lambda e, _: rx.empty())
            )
        )
    ).subscribe(on_completed=on_completed, on_error=on_error)

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    completion_event.wait()
    loop.call_soon_threadsafe(loop.stop)
    loop_thread.join(timeout=5)

    if pipeline_error:
        raise pipeline_error

    return results


def run(input_dir: Path, output_dir: Path, quality: int = 85, max_dimension: int = 2048) -> None:
    """Main entry point for image conversion."""
    logger.info(f"Input: {input_dir}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Quality: {quality}, Max dimension: {max_dimension}")

    files = collect_convertible_files(input_dir)
    if not files:
        logger.info("No convertible files found.")
        return

    logger.info(f"Found {len(files)} convertible files")

    sorted_files = extract_and_sort_by_date(files)

    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for index, (source, exif_date) in enumerate(sorted_files, start=1):
        dest = generate_output_name(output_dir, index, exif_date)
        tasks.append(
            ConversionTask(source=source, destination=dest, exif_date=exif_date, quality=quality, max_dimension=max_dimension)
        )

    message = f"{colorama.Fore.LIGHTGREEN_EX}Converting {len(tasks)} images...{colorama.Style.RESET_ALL}"
    print(message, flush=True)

    results = convert_all(tasks)

    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    message = f"{colorama.Fore.LIGHTGREEN_EX}Done: {succeeded} converted, {failed} failed{colorama.Style.RESET_ALL}"
    print(message, flush=True)


def main():
    """Parse CLI arguments and run the image converter."""
    parser = argparse.ArgumentParser(
        prog="image_converter", description="Convert images to optimized JPEG for real estate listing websites"
    )
    parser.add_argument(
        "-i", "--input_dir", type=str, default="~/Pictures", help="Input directory containing images (default: ~/Pictures)"
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default="~/Pictures/converted",
        help="Output directory for converted JPEGs (default: ~/Pictures/converted)",
    )
    parser.add_argument("-q", "--quality", type=int, default=85, help="JPEG quality 1-100 (default: 85)")
    parser.add_argument("-d", "--max_dimension", type=int, default=2048, help="Max pixel dimension, longest side (default: 2048)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    input_dir = Path(os.path.expanduser(args.input_dir))
    output_dir = Path(os.path.expanduser(args.output_dir))

    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)

    if not input_dir.is_dir():
        logger.error(f"Input path is not a directory: {input_dir}")
        sys.exit(1)

    run(input_dir, output_dir, args.quality, args.max_dimension)


if __name__ == "__main__":
    main()
