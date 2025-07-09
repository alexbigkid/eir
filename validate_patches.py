#!/usr/bin/env python3
"""Validate that our pydngconverter patches are working correctly."""

import os
import sys
import logging
import platform
from pathlib import Path

# Add the src directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from eir.processor import ImageProcessor


def setup_logging():
    """Set up detailed logging to see our patches in action."""
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    return logging.getLogger(__name__)


def simulate_linux_environment():
    """Simulate the Linux environment where the issue occurs."""
    # Set environment variable to simulate having DNGLab available
    test_dnglab_path = "/tmp/fake_dnglab"
    os.environ["PYDNG_DNG_CONVERTER"] = test_dnglab_path

    # Create a fake binary file to simulate DNGLab being present
    Path(test_dnglab_path).parent.mkdir(exist_ok=True)
    Path(test_dnglab_path).touch()
    Path(test_dnglab_path).chmod(0o755)

    return test_dnglab_path


def test_patches():
    """Test that our patches are applied correctly."""
    logger = setup_logging()

    logger.info("=== Testing pydngconverter Patches ===")
    logger.info(f"Platform: {platform.system()}")

    # Only test on Linux or simulate Linux environment
    if platform.system().lower() != "linux":
        logger.info("Not on Linux - simulating Linux environment for testing")

    dnglab_path = simulate_linux_environment()
    logger.info(f"Using test DNGLab path: {dnglab_path}")

    # Create a temporary directory structure for testing
    test_dir = Path("/tmp/test_eir_patches")
    test_dir.mkdir(exist_ok=True)

    # Initialize ImageProcessor - this should trigger our patches
    logger.info("Initializing ImageProcessor...")
    processor = ImageProcessor(logger=logger, op_dir=str(test_dir))

    # Test the DNGLab configuration
    logger.info("Testing _configure_dng_converter...")
    processor._configure_dng_converter()

    # Create test source and destination directories
    src_dir = test_dir / "test_src"
    dst_dir = test_dir / "test_dst"
    src_dir.mkdir(exist_ok=True)
    dst_dir.mkdir(exist_ok=True)

    # Create a fake RAW file
    fake_arw = src_dir / "test.arw"
    fake_arw.write_text("fake raw file content")

    logger.info("Testing convert_raw_to_dng method...")

    # Import pydngconverter modules to check if our patches are applied
    try:
        import pydngconverter.compat
        import pydngconverter.main

        # Check if our patches are in place
        logger.info("Checking if patches are applied...")

        # Test the compat patch
        if platform.system().lower() == "linux" or True:  # Force test
            test_path = Path("/tmp/test/path")

            # This should use our patched version (native path) instead of Wine conversion
            import asyncio

            async def test_compat_patch():
                result = await pydngconverter.compat.get_compat_path(test_path)
                logger.info(f"Compat path result: {test_path} -> {result}")
                return result == str(test_path)  # Should be native path, not Wine path

            compat_success = asyncio.run(test_compat_patch())
            logger.info(f"Compat patch test: {'SUCCESS' if compat_success else 'FAILED'}")

            # Test if convert_file method has been patched
            converter_class = pydngconverter.main.DNGConverter
            convert_method = getattr(converter_class, "convert_file", None)

            if convert_method:
                # Check if it's our patched version by looking at the function name or docstring
                if hasattr(convert_method, "__doc__") and convert_method.__doc__:
                    if "Enhanced convert_file" in convert_method.__doc__:
                        logger.info("convert_file patch test: SUCCESS")
                    else:
                        logger.info("convert_file patch test: NOT DETECTED")
                else:
                    logger.info("convert_file patch test: UNCLEAR")
            else:
                logger.error("convert_file method not found!")

        # Test the actual conversion method (won't work with fake binary, but will show patches)
        logger.info("Testing conversion with patches (will likely fail due to fake binary)...")
        try:
            # This will fail but should show our enhanced logging
            import asyncio

            asyncio.run(processor.convert_raw_to_dng(str(src_dir), str(dst_dir)))
        except Exception as e:
            logger.info(f"Expected failure during fake conversion: {e}")

    except ImportError as e:
        logger.error(f"Failed to import pydngconverter: {e}")
        return False

    # Cleanup
    import shutil

    shutil.rmtree(test_dir, ignore_errors=True)
    Path(dnglab_path).unlink(missing_ok=True)

    logger.info("=== Patches Test Completed ===")
    return True


if __name__ == "__main__":
    SUCCESS = test_patches()
    sys.exit(0 if SUCCESS else 1)
