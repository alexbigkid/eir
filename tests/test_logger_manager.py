"""Tests for logger_manager.py module."""

import pytest
import logging
import queue
import yaml
from unittest.mock import Mock, patch

from eir.logger_manager import LoggerManager, LoggerType


class TestLoggerType:
    """Test the LoggerType enum."""

    def test_logger_type_values(self):
        """Test that LoggerType enum has correct values."""
        assert LoggerType.CONSOLE_LOGGER.value == "consoleLogger"
        assert LoggerType.FILE_LOGGER.value == "fileLogger"
        assert LoggerType.THREADED_CONSOLE_LOGGER.value == "threadedConsoleLogger"
        assert LoggerType.THREADED_FILE_LOGGER.value == "threadedFileLogger"

    def test_logger_type_enum_members(self):
        """Test that all expected enum members exist."""
        expected_members = {
            "CONSOLE_LOGGER",
            "FILE_LOGGER",
            "THREADED_CONSOLE_LOGGER",
            "THREADED_FILE_LOGGER",
        }
        actual_members = {member.name for member in LoggerType}
        assert actual_members == expected_members


class TestLoggerManager:
    """Test the LoggerManager class."""

    def setup_method(self):
        """Reset LoggerManager singleton before each test."""
        LoggerManager._instance = None

    def teardown_method(self):
        """Clean up after each test."""
        if (
            LoggerManager._instance
            and hasattr(LoggerManager._instance, "_queue_listener")
            and LoggerManager._instance._queue_listener
        ):
            LoggerManager._instance._queue_listener.stop()
        LoggerManager._instance = None

    def test_singleton_pattern(self):
        """Test that LoggerManager follows singleton pattern."""
        manager1 = LoggerManager()
        manager2 = LoggerManager()
        assert manager1 is manager2

    def test_init_default_state(self):
        """Test initial state of LoggerManager."""
        manager = LoggerManager()
        assert not manager._configured
        assert manager._logger.disabled is True
        assert manager._queue_listener is None
        assert manager._log_queue is None

    def test_init_only_once(self):
        """Test that __init__ only initializes once."""
        manager = LoggerManager()
        manager._configured = True
        original_logger = manager._logger

        # Create another instance (should be same due to singleton)
        manager2 = LoggerManager()
        assert manager2._configured is True
        assert manager2._logger is original_logger

    def test_get_logger_not_configured(self):
        """Test get_logger raises error when not configured."""
        manager = LoggerManager()

        with pytest.raises(RuntimeError, match="LoggerManager not configured yet"):
            manager.get_logger()

    def test_configure_quiet_mode(self, reset_logger_manager, clean_logging):
        """Test configure in quiet mode."""
        manager = LoggerManager()

        with patch("logging.disable") as mock_disable:
            manager.configure(quiet=True)

        assert manager._configured is True
        assert manager._logger.disabled is True
        mock_disable.assert_called_once_with(logging.CRITICAL)

    def test_configure_prevents_reconfiguration(self, reset_logger_manager, clean_logging):
        """Test that configure prevents reconfiguration."""
        manager = LoggerManager()

        with patch.object(manager, "_setup_yaml_threaded_logging") as mock_setup:
            manager.configure()
            manager.configure()  # Second call should do nothing

        mock_setup.assert_called_once()

    def test_configure_file_logging_creates_logs_dir(
        self, project_root_dir, reset_logger_manager, clean_logging
    ):
        """Test that configure creates logs directory for file logging."""
        manager = LoggerManager()

        with (
            patch.object(manager, "_find_project_root", return_value=project_root_dir),
            patch.object(manager, "_setup_yaml_threaded_logging"),
        ):
            manager.configure(log_into_file=True)

        logs_dir = project_root_dir / "logs"
        assert logs_dir.exists()
        assert logs_dir.is_dir()

    def test_configure_handles_file_not_found(self, reset_logger_manager, clean_logging):
        """Test configure handles FileNotFoundError."""
        manager = LoggerManager()

        with (
            patch.object(
                manager, "_find_project_root", side_effect=FileNotFoundError("test error")
            ),
            pytest.raises(FileNotFoundError, match="logging.yaml not found: test error"),
        ):
            manager.configure()

    def test_configure_handles_general_exception(self, reset_logger_manager, clean_logging):
        """Test configure handles general exceptions."""
        manager = LoggerManager()

        with (
            patch.object(manager, "_find_project_root", side_effect=Exception("test error")),
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            manager.configure()

        assert manager._configured is True
        assert manager._logger.disabled is True
        mock_logger.exception.assert_called_once()

    def test_find_project_root_success(self, project_root_dir, reset_logger_manager):
        """Test _find_project_root finds project root successfully."""
        manager = LoggerManager()

        # Create subdirectory to test upward search
        sub_dir = project_root_dir / "subdir"
        sub_dir.mkdir()

        with patch("eir.logger_manager.Path.cwd", return_value=sub_dir):
            root = manager._find_project_root()

        assert root == project_root_dir

    def test_find_project_root_not_found(self, temp_dir, reset_logger_manager):
        """Test _find_project_root raises error when not found."""
        manager = LoggerManager()

        with (
            patch("eir.logger_manager.Path.cwd", return_value=temp_dir),
            pytest.raises(FileNotFoundError, match="pyproject.toml not found"),
        ):
            manager._find_project_root()

    def test_setup_yaml_threaded_logging_console_mode(
        self, project_root_dir, reset_logger_manager, clean_logging
    ):
        """Test _setup_yaml_threaded_logging in console mode."""
        manager = LoggerManager()

        # Create logging.yaml
        logging_yaml = project_root_dir / "logging.yaml"
        yaml_content = {
            "version": 1,
            "handlers": {
                "queueHandler": {"class": "logging.handlers.QueueHandler", "level": "DEBUG"},
                "consoleHandler": {"class": "logging.StreamHandler", "level": "DEBUG"},
            },
            "loggers": {
                "consoleLogger": {"level": "DEBUG", "handlers": ["consoleHandler"]},
                "threadedConsoleLogger": {"level": "DEBUG", "handlers": ["queueHandler"]},
            },
        }

        with open(logging_yaml, "w") as f:
            yaml.dump(yaml_content, f)

        with (
            patch("logging.config.dictConfig") as mock_dict_config,
            patch("logging.handlers.QueueListener") as mock_queue_listener,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_console_logger = Mock()
            mock_console_logger.handlers = [Mock()]
            mock_threaded_logger = Mock()

            def logger_side_effect(name):
                if name == "consoleLogger":
                    return mock_console_logger
                elif name == "threadedConsoleLogger":
                    return mock_threaded_logger
                return Mock()

            mock_get_logger.side_effect = logger_side_effect

            manager._setup_yaml_threaded_logging(project_root_dir, log_into_file=False)

        assert isinstance(manager._log_queue, queue.Queue)
        assert manager._logger is mock_threaded_logger
        mock_dict_config.assert_called_once()
        mock_queue_listener.assert_called_once()

    def test_setup_yaml_threaded_logging_file_mode(
        self, project_root_dir, reset_logger_manager, clean_logging
    ):
        """Test _setup_yaml_threaded_logging in file mode."""
        manager = LoggerManager()

        # Create logging.yaml
        logging_yaml = project_root_dir / "logging.yaml"
        yaml_content = {
            "version": 1,
            "handlers": {
                "queueHandler": {"class": "logging.handlers.QueueHandler", "level": "DEBUG"},
                "fileHandler": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "DEBUG",
                },
            },
            "loggers": {
                "fileLogger": {"level": "DEBUG", "handlers": ["fileHandler"]},
                "threadedFileLogger": {"level": "DEBUG", "handlers": ["queueHandler"]},
            },
        }

        with open(logging_yaml, "w") as f:
            yaml.dump(yaml_content, f)

        with (
            patch("logging.config.dictConfig") as mock_dict_config,
            patch("logging.handlers.QueueListener") as mock_queue_listener,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_file_logger = Mock()
            mock_file_logger.handlers = [Mock()]
            mock_threaded_logger = Mock()

            def logger_side_effect(name):
                if name == "fileLogger":
                    return mock_file_logger
                elif name == "threadedFileLogger":
                    return mock_threaded_logger
                return Mock()

            mock_get_logger.side_effect = logger_side_effect

            manager._setup_yaml_threaded_logging(project_root_dir, log_into_file=True)

        assert isinstance(manager._log_queue, queue.Queue)
        assert manager._logger is mock_threaded_logger
        mock_dict_config.assert_called_once()
        mock_queue_listener.assert_called_once()

    def test_cleanup_logging(self, reset_logger_manager):
        """Test _cleanup_logging method."""
        manager = LoggerManager()
        mock_listener = Mock()
        manager._queue_listener = mock_listener

        manager._cleanup_logging()

        mock_listener.stop.assert_called_once()
        assert manager._queue_listener is None

    def test_cleanup_logging_no_listener(self, reset_logger_manager):
        """Test _cleanup_logging when no listener exists."""
        manager = LoggerManager()
        manager._queue_listener = None

        # Should not raise any exceptions
        manager._cleanup_logging()

    def test_get_logger_after_configuration(self, reset_logger_manager, clean_logging):
        """Test get_logger returns logger after configuration."""
        manager = LoggerManager()
        mock_logger = Mock()
        manager._logger = mock_logger
        manager._configured = True

        result = manager.get_logger()
        assert result is mock_logger

    @patch("atexit.register")
    def test_atexit_registration(
        self, mock_atexit, project_root_dir, reset_logger_manager, clean_logging
    ):
        """Test that cleanup is registered with atexit."""
        manager = LoggerManager()

        # Create minimal logging.yaml
        logging_yaml = project_root_dir / "logging.yaml"
        yaml_content = {
            "version": 1,
            "handlers": {
                "queueHandler": {"class": "logging.handlers.QueueHandler"},
                "consoleHandler": {"class": "logging.StreamHandler"},
            },
            "loggers": {
                "consoleLogger": {"handlers": ["consoleHandler"]},
                "threadedConsoleLogger": {"handlers": ["queueHandler"]},
            },
        }

        with open(logging_yaml, "w") as f:
            yaml.dump(yaml_content, f)

        with (
            patch("logging.config.dictConfig"),
            patch("logging.handlers.QueueListener"),
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_console_logger = Mock()
            mock_console_logger.handlers = [Mock()]  # Make handlers subscriptable
            mock_threaded_logger = Mock()

            def logger_side_effect(name):
                if name == "consoleLogger":
                    return mock_console_logger
                elif name == "threadedConsoleLogger":
                    return mock_threaded_logger
                return Mock()

            mock_get_logger.side_effect = logger_side_effect
            manager._setup_yaml_threaded_logging(project_root_dir, log_into_file=False)

        mock_atexit.assert_called_once_with(manager._cleanup_logging)

    def test_yaml_loading_error(self, project_root_dir, reset_logger_manager):
        """Test handling of YAML loading errors."""
        manager = LoggerManager()

        # Create malformed YAML
        logging_yaml = project_root_dir / "logging.yaml"
        logging_yaml.write_text("invalid: yaml: content: [")

        with pytest.raises(yaml.YAMLError):
            manager._setup_yaml_threaded_logging(project_root_dir, log_into_file=False)

    def test_queue_injection_into_config(
        self, project_root_dir, reset_logger_manager, clean_logging
    ):
        """Test that queue is properly injected into YAML configuration."""
        manager = LoggerManager()

        # Create logging.yaml
        logging_yaml = project_root_dir / "logging.yaml"
        yaml_content = {
            "version": 1,
            "handlers": {
                "queueHandler": {
                    "class": "logging.handlers.QueueHandler",
                    "level": "DEBUG",
                    "queue": "will_be_replaced",
                }
            },
            "loggers": {
                "consoleLogger": {"handlers": []},
                "threadedConsoleLogger": {"handlers": ["queueHandler"]},
            },
        }

        with open(logging_yaml, "w") as f:
            yaml.dump(yaml_content, f)

        captured_config = {}

        def capture_config(config):
            captured_config.update(config)

        with (
            patch("logging.config.dictConfig", side_effect=capture_config),
            patch("logging.handlers.QueueListener"),
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_console_logger = Mock()
            mock_console_logger.handlers = [Mock()]  # Make handlers subscriptable
            mock_threaded_logger = Mock()

            def logger_side_effect(name):
                if name == "consoleLogger":
                    return mock_console_logger
                elif name == "threadedConsoleLogger":
                    return mock_threaded_logger
                return Mock()

            mock_get_logger.side_effect = logger_side_effect
            manager._setup_yaml_threaded_logging(project_root_dir, log_into_file=False)

        # Verify that the queue was injected
        assert captured_config["handlers"]["queueHandler"]["queue"] is manager._log_queue


class TestLoggerManagerIntegration:
    """Integration tests for LoggerManager."""

    def setup_method(self):
        """Reset LoggerManager singleton before each test."""
        LoggerManager._instance = None

    def teardown_method(self):
        """Clean up after each test."""
        if (
            LoggerManager._instance
            and hasattr(LoggerManager._instance, "_queue_listener")
            and LoggerManager._instance._queue_listener
        ):
            LoggerManager._instance._queue_listener.stop()
        LoggerManager._instance = None

    @pytest.mark.integration
    def test_full_configuration_workflow(self, project_root_dir, clean_logging):
        """Test complete configuration workflow."""
        # Create proper logging.yaml
        logging_yaml = project_root_dir / "logging.yaml"
        yaml_content = """
version: 1
disable_existing_loggers: True

formatters:
    abkFormatterShort:
        format: '[%(asctime)s]:[%(funcName)s]:[%(levelname)s]: %(message)s'
        datefmt: '%Y%m%d %H:%M:%S'

handlers:
    consoleHandler:
        class: logging.StreamHandler
        level: DEBUG
        formatter: abkFormatterShort
        stream: ext://sys.stdout
    queueHandler:
        class: logging.handlers.QueueHandler
        level: DEBUG
        queue: ext://queue.Queue

loggers:
    consoleLogger:
        level: DEBUG
        handlers: [consoleHandler]
        qualname: consoleLogger
        propagate: no
    threadedConsoleLogger:
        level: DEBUG
        handlers: [queueHandler]
        qualname: threadedConsoleLogger
        propagate: no
"""
        logging_yaml.write_text(yaml_content)

        with patch.object(LoggerManager, "_find_project_root", return_value=project_root_dir):
            manager = LoggerManager()
            manager.configure(log_into_file=False, quiet=False)

            assert manager._configured is True
            logger = manager.get_logger()
            assert logger is not None

            # Test logging works
            logger.info("Test message")

            # Cleanup
            manager._cleanup_logging()
