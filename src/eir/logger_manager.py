"""Logger Manager for centralized logging configuration."""

from enum import Enum
import logging
import logging.config
import logging.handlers
from pathlib import Path
import queue
import sys
import yaml
import atexit


class LoggerType(Enum):
    """Logger type."""

    CONSOLE_LOGGER = "consoleLogger"
    FILE_LOGGER = "fileLogger"
    THREADED_CONSOLE_LOGGER = "threadedConsoleLogger"
    THREADED_FILE_LOGGER = "threadedFileLogger"


class LoggerManager:
    """Singleton LoggerManager that configures and exposes a global logger."""

    _instance = None

    def __new__(cls):
        """Creates an instance of the LoggerManager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the LoggerManager."""
        if not hasattr(self, "_configured"):
            self._configured = False
            self._logger = logging.getLogger("consoleLogger")
            self._logger.disabled = True
            self._queue_listener = None
            self._log_queue = None

    def configure(self, log_into_file=False, quiet=False, verbose=False):
        """Configure logging once based on flags with simplified YAML-based threaded logging."""
        if self._configured:
            return  # Prevent reconfiguration

        try:
            if quiet:
                logging.disable(logging.CRITICAL)
                self._logger = logging.getLogger("consoleLogger")
                self._logger.disabled = True
                self._configured = True
                return

            root_dir = self._find_project_root()

            # Create logs directory if needed for file logging
            if log_into_file:
                logs_dir = root_dir / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)

            # Setup threaded logging using YAML configuration
            self._setup_yaml_threaded_logging(root_dir, log_into_file, verbose)
            self._configured = True

        except FileNotFoundError as e:
            raise FileNotFoundError(f"logging.yaml not found: {e}") from e
        except Exception as e:
            self._logger = logging.getLogger(__name__)
            self._logger.exception(f"ERROR: Logging setup failed due to: {e}")
            self._logger.disabled = True
            self._configured = True

    def _setup_yaml_threaded_logging(self, root_dir: Path, log_into_file: bool, verbose: bool):
        """Setup threaded logging using YAML configuration with QueueHandler."""
        # Create a queue for log records
        self._log_queue = queue.Queue(-1)  # Unlimited size

        # Load and configure logging from YAML
        config_path = root_dir / "logging.yaml"
        with config_path.open("r", encoding="utf-8") as stream:
            config_yaml = yaml.safe_load(stream)

        # Ensure logs directory exists before configuring file handler
        logs_dir = root_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Update the file handler path to be absolute (if it exists)
        if "fileHandler" in config_yaml.get("handlers", {}):
            config_yaml["handlers"]["fileHandler"]["filename"] = str(logs_dir / "eir.log")

        # Inject the queue instance into the configuration
        config_yaml["handlers"]["queueHandler"]["queue"] = self._log_queue

        # Override levels for verbose mode
        if verbose:
            # Set all console handlers and loggers to DEBUG level for verbose output
            for handler_name in ["consoleHandler", "queueHandler"]:
                if handler_name in config_yaml.get("handlers", {}):
                    config_yaml["handlers"][handler_name]["level"] = "DEBUG"

            for logger_name in ["root", "consoleLogger", "threadedConsoleLogger"]:
                if logger_name in config_yaml.get("loggers", {}):
                    config_yaml["loggers"][logger_name]["level"] = "DEBUG"
                elif logger_name == "root":
                    config_yaml["root"]["level"] = "DEBUG"

        # Apply the logging configuration
        logging.config.dictConfig(config_yaml)

        # Determine target handlers for the queue listener
        if log_into_file:
            # File mode: route queue to file handler
            target_handler = logging.getLogger("fileLogger").handlers[0]
            logger_name = LoggerType.THREADED_FILE_LOGGER.value
        else:
            # Console mode: route queue to console handler
            target_handler = logging.getLogger("consoleLogger").handlers[0]
            logger_name = LoggerType.THREADED_CONSOLE_LOGGER.value

        # Create and start the queue listener with the appropriate target handler
        self._queue_listener = logging.handlers.QueueListener(
            self._log_queue, target_handler, respect_handler_level=True
        )
        self._queue_listener.start()

        # Get the configured threaded logger
        self._logger = logging.getLogger(logger_name)

        # Register cleanup on exit
        atexit.register(self._cleanup_logging)

    def _cleanup_logging(self):
        """Clean up threaded logging resources."""
        if self._queue_listener:
            self._queue_listener.stop()
            self._queue_listener = None

    def get_logger(self) -> logging.Logger:
        """Get the configured threaded logger."""
        if not self._configured:
            raise RuntimeError("LoggerManager not configured yet. Call configure() first.")
        return self._logger

    def _find_project_root(self) -> Path:
        # First, check if we're in a PyInstaller bundle (backward compatibility)
        if hasattr(sys, "_MEIPASS"):
            bundle_dir = Path(sys._MEIPASS)
            if (bundle_dir / "pyproject.toml").exists():
                return bundle_dir

        # Check if we're in a Nuitka bundle - improved detection
        current_file_path = Path(__file__).absolute()
        is_nuitka_onefile = "onefile" in str(current_file_path).lower()
        is_frozen = getattr(sys, "frozen", False)

        if is_frozen or is_nuitka_onefile:
            # For Nuitka onefile, bundled files are extracted to the same temp directory
            # Since we used --include-data-dir=nuitka_data=., the files should be
            # at the extraction root level
            current_file_dir = Path(__file__).parent

            # Find the extraction root that contains our bundled files
            extraction_root = current_file_dir
            while extraction_root.parent != extraction_root:
                # Check if this directory contains the bundled files
                if (extraction_root / "pyproject.toml").exists():
                    return extraction_root
                if (extraction_root / "logging.yaml").exists():
                    return extraction_root

                # Check if we're in a Nuitka extraction directory
                if any(name.startswith("onefile") for name in extraction_root.parts):
                    # Look for bundled files in this directory or parent directories
                    for check_dir in [
                        extraction_root,
                        extraction_root.parent,
                        extraction_root.parent.parent,
                    ]:
                        if (check_dir / "pyproject.toml").exists():
                            return check_dir
                        if (check_dir / "logging.yaml").exists():
                            return check_dir
                    break
                extraction_root = extraction_root.parent

        # Try multiple starting points to find project root
        search_paths = [
            Path.cwd(),  # Current working directory
            Path(__file__).parent.parent.parent,  # Relative to this source file (src/eir/../..)
        ]

        for start in search_paths:
            for parent in [start, *start.parents]:
                if (parent / "pyproject.toml").exists():
                    return parent

        # If we can't find pyproject.toml, check if we're in a compiled environment
        # and create fallback configuration to avoid crashes

        # Detect if we're in a compiled/bundled environment (Nuitka, PyInstaller, etc.)
        current_path = str(Path(__file__).absolute()).lower()
        # Check for various Nuitka onefile patterns (including Windows short names)
        is_nuitka_temp = (
            ("temp" in current_path and "onefil" in current_path)  # Windows: ONEFIL~1
            or ("temp" in current_path and "onefile" in current_path)  # Full name
        )
        is_compiled = (
            getattr(sys, "frozen", False)  # PyInstaller/Nuitka frozen
            or hasattr(sys, "_MEIPASS")  # PyInstaller bundle
            or "onefile" in current_path  # Nuitka onefile pattern
            or "onefil" in current_path  # Windows short name pattern
            or is_nuitka_temp  # Nuitka temp extraction
        )

        if is_compiled:
            # Create a temporary config in the current directory
            fallback_dir = Path.cwd()

            # Create minimal logging.yaml if it doesn't exist
            if not (fallback_dir / "logging.yaml").exists():
                minimal_logging = """
version: 1
disable_existing_loggers: false

formatters:
  default:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

handlers:
  consoleHandler:
    class: logging.StreamHandler
    level: INFO
    formatter: default
    stream: ext://sys.stdout
  queueHandler:
    class: logging.handlers.QueueHandler
    level: INFO
    queue: '!!python/object/apply:queue.Queue []'
  fileHandler:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: default
    filename: logs/eir.log
    maxBytes: 10485760
    backupCount: 5

loggers:
  consoleLogger:
    level: INFO
    handlers: [consoleHandler]
    propagate: false
  threadedConsoleLogger:
    level: INFO
    handlers: [queueHandler]
    propagate: false
  fileLogger:
    level: INFO
    handlers: [fileHandler]
    propagate: false
  threadedFileLogger:
    level: INFO
    handlers: [queueHandler]
    propagate: false

root:
  level: INFO
  handlers: [consoleHandler]
"""
                try:
                    with open(fallback_dir / "logging.yaml", "w") as f:
                        f.write(minimal_logging.strip())
                except OSError:
                    # Silently ignore file write failures in compiled environment
                    pass

            return fallback_dir

        raise FileNotFoundError("pyproject.toml not found")
