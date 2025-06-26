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

        # Check if we're in a Nuitka bundle (primary build system - frozen but no _MEIPASS)
        if getattr(sys, "frozen", False):
            # For Nuitka onefile, bundled files are in the same directory as __file__
            # The directory structure in Nuitka onefile is: /tmp/onefile_xxx/.../
            current_file_dir = Path(__file__).parent

            # Check current directory and parent directories for bundled files
            # Also check the extraction root directory (where bundled data goes)
            search_dirs = [
                current_file_dir,
                current_file_dir.parent,
                current_file_dir.parent.parent,
                current_file_dir.parent.parent.parent,  # Sometimes deeper
            ]

            # Debug: Print search directories and what files exist
            print(f"Debug: Nuitka bundle detection in {current_file_dir}")
            print(f"Debug: sys.frozen = {getattr(sys, 'frozen', False)}")

            for bundle_dir in search_dirs:
                print(f"Debug: Checking {bundle_dir}")
                if bundle_dir.exists():
                    files = list(bundle_dir.glob("*"))[:10]  # Limit output
                    print(f"Debug: Files in {bundle_dir}: {[f.name for f in files]}")

                if (bundle_dir / "pyproject.toml").exists():
                    print(f"Debug: Found pyproject.toml in {bundle_dir}")
                    return bundle_dir
                # Also check if logging.yaml exists directly (might be in same dir)
                if (bundle_dir / "logging.yaml").exists():
                    print(f"Debug: Found logging.yaml in {bundle_dir}")
                    return bundle_dir

        # Try multiple starting points to find project root
        search_paths = [
            Path.cwd(),  # Current working directory
            Path(__file__).parent.parent.parent,  # Relative to this source file (src/eir/../..)
        ]

        for start in search_paths:
            for parent in [start, *start.parents]:
                if (parent / "pyproject.toml").exists():
                    return parent

        # If we're frozen (compiled) and still can't find pyproject.toml,
        # create a minimal fallback structure to avoid crashes
        if getattr(sys, "frozen", False):
            print("Debug: Creating fallback for frozen executable")
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
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: default
    stream: ext://sys.stdout

loggers:
  consoleLogger:
    level: INFO
    handlers: [console]
    propagate: false

root:
  level: INFO
  handlers: [console]
"""
                try:
                    with open(fallback_dir / "logging.yaml", "w") as f:
                        f.write(minimal_logging.strip())
                    print("Debug: Created fallback logging.yaml")
                except Exception as e:
                    print(f"Debug: Failed to create fallback logging.yaml: {e}")

            return fallback_dir

        raise FileNotFoundError("pyproject.toml not found")
