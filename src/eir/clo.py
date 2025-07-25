"""Clo module handles all parameters passed in to the python script."""

# Standard library imports
import logging
from enum import Enum
from argparse import ArgumentParser, Namespace
import sys

# Third party imports

# Local application imports
from eir.constants import CONST
from eir.logger_manager import LoggerManager


class LoggerType(Enum):
    """Logger type."""

    CONSOLE_LOGGER = "consoleLogger"
    FILE_LOGGER = "fileLogger"
    THREAD_LOGGER = "threadLogger"


class CommandLineOptions:
    """CommandLineOptions module handles all parameters passed in to the python script."""

    _args: list = None  # type: ignore
    options: Namespace = None  # type: ignore
    logger: logging.Logger = None  # type: ignore

    def __init__(self, args: list = None, options: Namespace = None):  # type: ignore
        """Init for Command Line Options."""
        self._args = args
        self.options = options

    def handle_options(self) -> None:
        """Handles user specified options and arguments."""
        parser = ArgumentParser(prog="eir", description="eir - rename and translate images from raw to dng format")
        parser.add_argument("-a", "--about", action="store_true", help="Show detailed project metadata")
        parser.add_argument(
            "-d",
            "--directory",
            action="store",
            dest="dir",
            default=".",
            help="directory, where images will be converted and renamed",
        )
        parser.add_argument(
            "-l", "--log_into_file", action="store_true", dest="log_into_file", default=False, help="log into logs/eir.log"
        )
        parser.add_argument("-q", "--quiet", action="store_true", help="Suppresses all logs")
        parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging (shows DEBUG level messages)")
        parser.add_argument("-v", "--version", action="store_true", help="Show version info and exit")
        parser.add_argument(
            "--dng-compression",
            choices=["lossless", "uncompressed"],
            default="lossless",
            help="DNG compression method: lossless (default) or uncompressed",
        )
        parser.add_argument(
            "--dng-preview", action="store_true", default=False, help="Embed JPEG preview in DNG files (increases file size)"
        )
        self.options = parser.parse_args()

        if self.options.version:
            print(f"{CONST.VERSION}", flush=True)
            sys.exit(0)

        if self.options.about:
            print(f"Name       : {CONST.NAME}", flush=True)
            print(f"Version    : {CONST.VERSION}", flush=True)
            print(f"License    : {CONST.LICENSE}", flush=True)
            print(f"Keywords   : {', '.join(CONST.KEYWORDS)}", flush=True)
            print("Authors:", flush=True)
            for a in CONST.AUTHORS:
                print(f"  - {a.get('name', '?')} <{a.get('email', '?')}>", flush=True)
            print("Maintainers:", flush=True)
            for m in CONST.MAINTAINERS:
                print(f"  - {m.get('name', '?')} <{m.get('email', '?')}>", flush=True)
            sys.exit(0)

        LoggerManager().configure(
            log_into_file=self.options.log_into_file, quiet=self.options.quiet, verbose=self.options.verbose
        )
        self.logger = LoggerManager().get_logger()
        self.logger.info(f"{self.options=}")
        self.logger.info(f"{self._args=}")
        self.logger.info(f"{self.options.log_into_file=}")
        self.logger.info(f"{self.options.quiet=}")
        self.logger.info(f"{CONST.VERSION=}")
