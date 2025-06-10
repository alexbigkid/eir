"""Cli - entry point to the eir package."""

import asyncio
from eir import clo
from eir.processor import run_pipeline


def main():
    """Main function."""
    command_line_options = clo.CommandLineOptions()
    command_line_options.handle_options()
    asyncio.run(
        run_pipeline(
            logger=command_line_options.logger, image_dir=command_line_options.options.dir
        )
    )
    # asyncio.run(eir())
