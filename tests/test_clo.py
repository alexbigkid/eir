"""Tests for clo.py module."""

import pytest
import sys
from argparse import Namespace
from unittest.mock import Mock, patch

from eir.clo import CommandLineOptions, LoggerType


class TestLoggerType:
    """Test the LoggerType enum in clo.py."""

    def test_logger_type_values(self):
        """Test that LoggerType enum has correct values."""
        assert LoggerType.CONSOLE_LOGGER.value == "consoleLogger"
        assert LoggerType.FILE_LOGGER.value == "fileLogger"
        assert LoggerType.THREAD_LOGGER.value == "threadLogger"

    def test_logger_type_enum_members(self):
        """Test that all expected enum members exist."""
        expected_members = {"CONSOLE_LOGGER", "FILE_LOGGER", "THREAD_LOGGER"}
        actual_members = {member.name for member in LoggerType}
        assert actual_members == expected_members


class TestCommandLineOptions:
    """Test the CommandLineOptions class."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        clo = CommandLineOptions()
        assert clo._args is None
        assert clo.options is None
        assert clo.logger is None

    def test_init_with_parameters(self):
        """Test initialization with provided parameters."""
        args = ["--help"]
        options = Namespace(help=True)

        clo = CommandLineOptions(args=args, options=options)
        assert clo._args == args
        assert clo.options == options
        assert clo.logger is None

    def test_handle_options_default_arguments(self, reset_logger_manager, clean_logging):
        """Test handle_options with default command line arguments."""
        clo = CommandLineOptions()

        test_args = ["eir"]  # Default case - no additional arguments

        with (
            patch.object(sys, "argv", test_args),
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        # Check default values
        assert clo.options.about is False
        assert clo.options.dir == "."
        assert clo.options.log_into_file is False
        assert clo.options.quiet is False
        assert clo.options.version is False
        assert clo.logger is mock_logger

    def test_handle_options_directory_argument(self, reset_logger_manager, clean_logging):
        """Test handle_options with directory argument."""
        clo = CommandLineOptions()

        test_args = ["eir", "-d", "/test/directory"]

        with (
            patch.object(sys, "argv", test_args),
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        assert clo.options.dir == "/test/directory"

    def test_handle_options_long_directory_argument(self, reset_logger_manager, clean_logging):
        """Test handle_options with long form directory argument."""
        clo = CommandLineOptions()

        test_args = ["eir", "--directory", "/another/test/path"]

        with (
            patch.object(sys, "argv", test_args),
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        assert clo.options.dir == "/another/test/path"

    def test_handle_options_log_into_file(self, reset_logger_manager, clean_logging):
        """Test handle_options with log into file flag."""
        clo = CommandLineOptions()

        test_args = ["eir", "-l"]

        with (
            patch.object(sys, "argv", test_args),
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        assert clo.options.log_into_file is True
        mock_manager.configure.assert_called_once_with(log_into_file=True, quiet=False)

    def test_handle_options_quiet_flag(self, reset_logger_manager, clean_logging):
        """Test handle_options with quiet flag."""
        clo = CommandLineOptions()

        test_args = ["eir", "-q"]

        with (
            patch.object(sys, "argv", test_args),
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        assert clo.options.quiet is True
        mock_manager.configure.assert_called_once_with(log_into_file=False, quiet=True)

    def test_handle_options_version_flag_exits(self):
        """Test handle_options with version flag exits program."""
        clo = CommandLineOptions()

        test_args = ["eir", "-v"]

        with (
            patch.object(sys, "argv", test_args),
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
            patch("eir.clo.CONST") as mock_const,
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_const.NAME = "eir"
            mock_const.VERSION = "1.0.0"
            # Mock the LoggerManager to prevent real logger configuration
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        mock_print.assert_called_once_with("eir version: 1.0.0", flush=True)
        mock_exit.assert_called_once_with(0)

    def test_handle_options_version_long_flag_exits(self):
        """Test handle_options with long version flag exits program."""
        clo = CommandLineOptions()
        test_args = ["eir", "--version"]

        with (
            patch.object(sys, "argv", test_args),
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
            patch("eir.clo.CONST") as mock_const,
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_const.NAME = "eir"
            mock_const.VERSION = "2.0.0"
            # Mock the LoggerManager to prevent real logger configuration
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        mock_print.assert_called_once_with("eir version: 2.0.0", flush=True)
        mock_exit.assert_called_once_with(0)

    def test_handle_options_about_flag_exits(self):
        """Test handle_options with about flag exits program."""
        clo = CommandLineOptions()

        test_args = ["eir", "-a"]

        with (
            patch.object(sys, "argv", test_args),
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
            patch("eir.clo.CONST") as mock_const,
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_const.NAME = "eir"
            mock_const.VERSION = "1.0.0"
            mock_const.LICENSE = "MIT"
            mock_const.KEYWORDS = ["image", "processing"]
            mock_const.AUTHORS = [
                {"name": "Author 1", "email": "author1@test.com"},
                {"name": "Author 2", "email": "author2@test.com"},
            ]
            mock_const.MAINTAINERS = [{"name": "Maintainer 1", "email": "maint1@test.com"}]
            # Mock the LoggerManager to prevent real logger configuration
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        # Check that all expected information was printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]

        assert "Name       : eir" in print_calls
        assert "Version    : 1.0.0" in print_calls
        assert "License    : MIT" in print_calls
        assert "Keywords   : image, processing" in print_calls
        assert "Authors:" in print_calls
        assert "  - Author 1 <author1@test.com>" in print_calls
        assert "  - Author 2 <author2@test.com>" in print_calls
        assert "Maintainers:" in print_calls
        assert "  - Maintainer 1 <maint1@test.com>" in print_calls

        mock_exit.assert_called_once_with(0)

    def test_handle_options_about_long_flag_exits(self):
        """Test handle_options with long about flag exits program."""
        clo = CommandLineOptions()

        test_args = ["eir", "--about"]

        with (
            patch.object(sys, "argv", test_args),
            patch("builtins.print"),
            patch("sys.exit") as mock_exit,
            patch("eir.clo.CONST") as mock_const,
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_const.NAME = "test_app"
            mock_const.VERSION = "0.5.0"
            mock_const.LICENSE = "GPL"
            mock_const.KEYWORDS = ["test"]
            mock_const.AUTHORS = [{"name": "Test Author", "email": "test@test.com"}]
            mock_const.MAINTAINERS = [{"name": "Test Maintainer", "email": "maint@test.com"}]
            # Mock the LoggerManager to prevent real logger configuration
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        mock_exit.assert_called_once_with(0)

    def test_handle_options_combined_flags(self, reset_logger_manager, clean_logging):
        """Test handle_options with multiple flags combined."""
        clo = CommandLineOptions()

        test_args = ["eir", "-d", "/test/path", "-l", "-q"]

        with (
            patch.object(sys, "argv", test_args),
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager

            clo.handle_options()

        assert clo.options.dir == "/test/path"
        assert clo.options.log_into_file is True
        assert clo.options.quiet is True
        mock_manager.configure.assert_called_once_with(log_into_file=True, quiet=True)

    def test_handle_options_logger_configuration(self, reset_logger_manager, clean_logging):
        """Test that LoggerManager is configured correctly."""
        clo = CommandLineOptions()

        test_args = ["eir", "-l"]

        with (
            patch.object(sys, "argv", test_args),
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager

            clo.handle_options()

        # Verify LoggerManager was instantiated and configured
        mock_manager_class.assert_called()
        mock_manager.configure.assert_called_once_with(log_into_file=True, quiet=False)
        mock_manager.get_logger.assert_called_once()

    def test_handle_options_logger_logging_calls(self, reset_logger_manager, clean_logging):
        """Test that logger methods are called with correct information."""
        clo = CommandLineOptions()

        test_args = ["eir", "-d", "/test", "-l"]

        with (
            patch.object(sys, "argv", test_args),
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager

            with patch("eir.clo.CONST") as mock_const:
                mock_const.VERSION = "1.0.0"

                clo.handle_options()

        # Verify logger was called with expected information
        assert mock_logger.info.call_count == 5

        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("self.options=" in call for call in info_calls)
        assert any("self._args=" in call for call in info_calls)
        assert any("self.options.log_into_file=True" in call for call in info_calls)
        assert any("self.options.quiet=False" in call for call in info_calls)
        assert any("CONST.VERSION='1.0.0'" in call for call in info_calls)

    def test_handle_options_about_missing_author_fields(self):
        """Test handle_options about with missing author/maintainer fields."""
        clo = CommandLineOptions()

        test_args = ["eir", "-a"]

        with (
            patch.object(sys, "argv", test_args),
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
            patch("eir.clo.CONST") as mock_const,
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_const.NAME = "test"
            mock_const.VERSION = "1.0.0"
            mock_const.LICENSE = "MIT"
            mock_const.KEYWORDS = []
            # Missing name/email fields
            mock_const.AUTHORS = [{"name": "Author"}, {"email": "test@test.com"}, {}]
            mock_const.MAINTAINERS = [{"name": "Maintainer"}, {}]
            # Mock the LoggerManager to prevent real logger configuration
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        print_calls = [call[0][0] for call in mock_print.call_args_list]

        # Should handle missing fields gracefully with '?'
        assert "  - Author <?>" in print_calls
        assert "  - ? <test@test.com>" in print_calls
        assert "  - ? <?>" in print_calls
        assert "  - Maintainer <?>" in print_calls

        mock_exit.assert_called_once_with(0)

    def test_argument_parser_help_text(self):
        """Test that argument parser has correct help text."""
        clo = CommandLineOptions()

        test_args = ["eir", "--help"]

        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            clo.handle_options()

        # argparse exits with code 0 for help
        assert exc_info.value.code == 0

    def test_argument_parser_program_name(self):
        """Test that argument parser has correct program name."""
        clo = CommandLineOptions()

        # Test invalid arguments to see program name in error
        test_args = ["eir", "--invalid-argument"]

        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            clo.handle_options()

        # argparse exits with code 2 for argument errors
        assert exc_info.value.code == 2

    def test_class_attributes_type_annotations(self):
        """Test that class has correct type annotations."""
        CommandLineOptions()

        # Check that class attributes exist (type annotations create them)
        assert hasattr(CommandLineOptions, "__annotations__")
        annotations = CommandLineOptions.__annotations__

        expected_annotations = {
            "_args": "list",
            "options": "Namespace",
            "logger": "logging.Logger",
        }

        for attr, expected_type in expected_annotations.items():
            assert attr in annotations
            assert expected_type in str(annotations[attr])


class TestCommandLineOptionsEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_authors_and_maintainers(self):
        """Test about flag with empty authors and maintainers lists."""
        clo = CommandLineOptions()

        test_args = ["eir", "-a"]

        with (
            patch.object(sys, "argv", test_args),
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
            patch("eir.clo.CONST") as mock_const,
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_const.NAME = "test"
            mock_const.VERSION = "1.0.0"
            mock_const.LICENSE = "MIT"
            mock_const.KEYWORDS = []
            mock_const.AUTHORS = []
            mock_const.MAINTAINERS = []
            # Mock the LoggerManager to prevent real logger configuration
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        print_calls = [call[0][0] for call in mock_print.call_args_list]

        # Should still print headers even with empty lists
        assert "Authors:" in print_calls
        assert "Maintainers:" in print_calls

        mock_exit.assert_called_once_with(0)

    def test_keywords_join_behavior(self):
        """Test that keywords are properly joined with commas."""
        clo = CommandLineOptions()

        test_args = ["eir", "-a"]

        with (
            patch.object(sys, "argv", test_args),
            patch("builtins.print") as mock_print,
            patch("sys.exit"),
            patch("eir.clo.CONST") as mock_const,
            patch("eir.clo.LoggerManager") as mock_manager_class,
        ):
            mock_const.NAME = "test"
            mock_const.VERSION = "1.0.0"
            mock_const.LICENSE = "MIT"
            mock_const.KEYWORDS = ["keyword1", "keyword2", "keyword3"]
            mock_const.AUTHORS = []
            mock_const.MAINTAINERS = []
            # Mock the LoggerManager to prevent real logger configuration
            mock_manager = Mock()
            mock_logger = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager
            clo.handle_options()

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert "Keywords   : keyword1, keyword2, keyword3" in print_calls
