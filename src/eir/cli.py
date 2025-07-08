"""Cli - entry point to the eir package."""

import asyncio
from eir import clo


def _configure_dnglab_early():
    """Configure DNGLab binary BEFORE any pydngconverter imports."""
    import logging
    import platform
    from eir.dnglab_strategy import DNGLabStrategyFactory

    # Create a temporary logger for early configuration
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Only configure on Windows where the issue occurs
    if platform.system().lower() == "windows":
        logger.info("Early DNGLab configuration for Windows...")
        strategy = DNGLabStrategyFactory.create_strategy(logger)
        dnglab_path = strategy.get_binary_path()
        if dnglab_path:
            import os

            os.environ["PYDNG_DNG_CONVERTER"] = dnglab_path
            logger.info(f"Early configuration: Set PYDNG_DNG_CONVERTER={dnglab_path}")
        else:
            logger.warning("Early configuration: No DNGLab binary found")


def main():
    """Main function."""
    # Configure DNGLab BEFORE any imports that might trigger pydngconverter
    _configure_dnglab_early()

    # Import processor AFTER DNGLab configuration
    from eir.processor import run_pipeline

    command_line_options = clo.CommandLineOptions()
    command_line_options.handle_options()
    asyncio.run(
        run_pipeline(
            logger=command_line_options.logger,
            image_dir=command_line_options.options.dir,
            dng_compression=command_line_options.options.dng_compression,
            dng_preview=command_line_options.options.dng_preview,
        )
    )


if __name__ == "__main__":
    main()
