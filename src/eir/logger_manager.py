"""Logger Manager for centralized logging configuration."""

from enum import Enum
import logging
import logging.config
import logging.handlers
from pathlib import Path
import queue
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

    def configure(self, log_into_file=False, quiet=False):
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
            if log_into_file:
                (root_dir / "logs").mkdir(parents=True, exist_ok=True)

            # Setup threaded logging using YAML configuration
            self._setup_yaml_threaded_logging(root_dir, log_into_file)
            self._configured = True

        except FileNotFoundError as e:
            raise FileNotFoundError(f"logging.yaml not found: {e}") from e
        except Exception as e:
            self._logger = logging.getLogger(__name__)
            self._logger.exception(f"ERROR: Logging setup failed due to: {e}")
            self._logger.disabled = True
            self._configured = True

    def _setup_yaml_threaded_logging(self, root_dir: Path, log_into_file: bool):
        """Setup threaded logging using YAML configuration with QueueHandler."""
        # Create a queue for log records
        self._log_queue = queue.Queue(-1)  # Unlimited size

        # Load and configure logging from YAML
        config_path = root_dir / "logging.yaml"
        with config_path.open("r", encoding="utf-8") as stream:
            config_yaml = yaml.safe_load(stream)

        # Inject the queue instance into the configuration
        config_yaml["handlers"]["queueHandler"]["queue"] = self._log_queue

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
        start = Path.cwd()
        for parent in [start, *start.parents]:
            if (parent / "pyproject.toml").exists():
                return parent
        raise FileNotFoundError("pyproject.toml not found")
