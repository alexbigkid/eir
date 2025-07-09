#!/usr/bin/env python3
"""Debug script to test DNGLab execution issues on Linux."""

import os
import sys
import logging
from pathlib import Path
import shutil
import asyncio
import platform


def setup_logging():
    """Set up detailed logging."""
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    return logging.getLogger(__name__)


async def test_dnglab_directly(dnglab_path: str, test_files_dir: str):
    """Test DNGLab directly with a simple command."""
    logger = logging.getLogger(__name__)

    # Create test output directory
    output_dir = Path(test_files_dir) / "direct_test_output"
    output_dir.mkdir(exist_ok=True)

    # Find a test file
    test_files = list(Path(test_files_dir).glob("*.arw"))
    if not test_files:
        logger.error("No ARW files found in test directory")
        return False

    test_file = test_files[0]
    logger.info(f"Testing with file: {test_file}")

    # Build DNGLab command with correct syntax
    output_file = output_dir / f"{test_file.stem}.dng"
    cmd = [
        dnglab_path,
        "convert",  # DNGLab convert subcommand
        "--compression",
        "lossless",
        "--dng-preview",
        "true",
        str(test_file),  # source
        str(output_file),  # destination file
    ]

    logger.info(f"Executing direct DNGLab command: {' '.join(cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=str(output_dir.parent)
        )

        stdout, stderr = await proc.communicate()

        logger.info(f"DNGLab return code: {proc.returncode}")

        if stdout:
            stdout_text = stdout.decode("utf-8", errors="replace")
            logger.info(f"DNGLab stdout:\n{stdout_text}")

        if stderr:
            stderr_text = stderr.decode("utf-8", errors="replace")
            logger.info(f"DNGLab stderr:\n{stderr_text}")

        # Check if output files were created
        output_files = list(output_dir.glob("*.dng"))
        logger.info(f"Output files created: {[f.name for f in output_files]}")

        return proc.returncode == 0 and len(output_files) > 0

    except Exception as e:
        logger.error(f"Exception during direct DNGLab test: {e}")
        return False


async def test_pydngconverter(test_files_dir: str):
    """Test using pydngconverter with our patches."""
    logger = logging.getLogger(__name__)

    # Import after setting up environment
    from pydngconverter import DNGConverter
    from pathlib import Path

    output_dir = Path(test_files_dir) / "pydng_test_output"
    output_dir.mkdir(exist_ok=True)

    logger.info(f"Testing pydngconverter: {test_files_dir} -> {output_dir}")

    try:
        converter = DNGConverter(source=test_files_dir, dest=output_dir, debug=True)
        await converter.convert()

        # Check results
        output_files = list(output_dir.glob("*.dng"))
        logger.info(f"pydngconverter output files: {[f.name for f in output_files]}")

        return len(output_files) > 0

    except Exception as e:
        logger.error(f"Exception during pydngconverter test: {e}")
        return False


def find_dnglab_binary():
    """Find DNGLab binary using the same logic as the main code."""
    machine = platform.machine().lower()
    system_name = platform.system().lower()

    if system_name == "linux":
        dnglab_arch = "aarch64" if machine in ["aarch64", "arm64"] else "x86_64"
        binary_name = "dnglab"
    else:
        return None

    # Check environment variable first
    env_path = os.environ.get("PYDNG_DNG_CONVERTER")
    if env_path and Path(env_path).exists():
        return env_path

    # Check system PATH
    system_path = shutil.which(binary_name)
    if system_path:
        return system_path

    # Check if running as compiled binary
    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", "")
        dnglab_bundled = Path(bundle_dir) / "tools" / system_name / dnglab_arch / binary_name
        if dnglab_bundled.exists():
            return str(dnglab_bundled)

    return None


async def main():
    """Main test function."""
    logger = setup_logging()

    logger.info("=== DNGLab Debug Test Script ===")
    logger.info(f"Platform: {platform.system()} {platform.machine()}")

    # Find DNGLab binary
    dnglab_path = find_dnglab_binary()
    if not dnglab_path:
        logger.error("DNGLab binary not found!")
        return 1

    logger.info(f"Found DNGLab binary: {dnglab_path}")

    # Set environment variable for tests
    os.environ["PYDNG_DNG_CONVERTER"] = dnglab_path

    # Create temporary test directory with a sample file
    # Note: You'll need to provide a directory with actual RAW files
    test_dir = input("Enter path to directory containing RAW files for testing: ").strip()

    if not os.path.exists(test_dir):
        logger.error(f"Test directory does not exist: {test_dir}")
        return 1

    # Test 1: Direct DNGLab execution
    logger.info("\n=== Test 1: Direct DNGLab Execution ===")
    direct_success = await test_dnglab_directly(dnglab_path, test_dir)
    logger.info(f"Direct test result: {'SUCCESS' if direct_success else 'FAILED'}")

    # Test 2: pydngconverter with patches
    logger.info("\n=== Test 2: pydngconverter with patches ===")
    pydng_success = await test_pydngconverter(test_dir)
    logger.info(f"pydngconverter test result: {'SUCCESS' if pydng_success else 'FAILED'}")

    # Summary
    logger.info("\n=== Test Summary ===")
    logger.info(f"Direct DNGLab test: {'PASS' if direct_success else 'FAIL'}")
    logger.info(f"pydngconverter test: {'PASS' if pydng_success else 'FAIL'}")

    if direct_success and not pydng_success:
        logger.error("DNGLab works directly but fails through pydngconverter - likely a path or argument issue")
    elif not direct_success:
        logger.error("DNGLab fails even when called directly - binary or permission issue")
    elif direct_success and pydng_success:
        logger.info("All tests passed - the issue may be resolved!")

    return 0 if (direct_success and pydng_success) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
