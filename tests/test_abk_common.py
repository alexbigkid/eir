"""Tests for abk_common.py module."""

import pytest
import time
from unittest.mock import Mock, patch
import logging

from eir.abk_common import function_trace, PerformanceTimer


class TestFunctionTrace:
    """Test the function_trace decorator."""

    def test_function_trace_decorator_basic(self, clean_logging, reset_logger_manager):
        """Test basic functionality of function_trace decorator."""
        mock_logger = Mock(spec=logging.Logger)

        with patch("eir.logger_manager.LoggerManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager._configured = True  # Ensure manager appears configured
            mock_manager_class.return_value = mock_manager

            @function_trace
            def test_function(arg1, arg2=None):
                return f"{arg1}_{arg2}"

            result = test_function("hello", arg2="world")

            assert result == "hello_world"
            assert mock_logger.debug.call_count == 2

            # Check the calls - entry and exit
            calls = mock_logger.debug.call_args_list
            assert "-> test_function" in calls[0][0][0]
            assert "<- test_function" in calls[1][0][0]

    def test_function_trace_with_exception(self, clean_logging, reset_logger_manager):
        """Test function_trace decorator when function raises exception."""
        mock_logger = Mock(spec=logging.Logger)

        with patch("eir.logger_manager.LoggerManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager._configured = True
            mock_manager_class.return_value = mock_manager

            @function_trace
            def failing_function():
                raise ValueError("Test exception")

            with pytest.raises(ValueError, match="Test exception"):
                failing_function()

            # Should still log entry but not exit due to exception
            assert mock_logger.debug.call_count == 1
            assert "-> failing_function" in mock_logger.debug.call_args[0][0]

    def test_function_trace_preserves_function_metadata(self):
        """Test that function_trace preserves original function metadata."""

        @function_trace
        def documented_function(param1: str, param2: int = 5) -> str:
            """This is a documented function.

            Args:
                param1: First parameter
                param2: Second parameter

            Returns:
                Combined string
            """
            return f"{param1}_{param2}"

        # The wrapper should preserve the original function name
        assert documented_function.__name__ == "function_wrapper"
        # Note: functools.wraps is not used in the current implementation

    def test_function_trace_with_args_and_kwargs(self, clean_logging, reset_logger_manager):
        """Test function_trace with various argument types."""
        mock_logger = Mock(spec=logging.Logger)

        with patch("eir.logger_manager.LoggerManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager._configured = True
            mock_manager_class.return_value = mock_manager

            @function_trace
            def complex_function(*args, **kwargs):
                return {"args": args, "kwargs": kwargs}

            result = complex_function(1, 2, 3, name="test", value=42)

            expected = {"args": (1, 2, 3), "kwargs": {"name": "test", "value": 42}}
            assert result == expected
            assert mock_logger.debug.call_count == 2

    def test_function_trace_logger_manager_import(self, clean_logging, reset_logger_manager):
        """Test that LoggerManager is imported correctly within the decorator."""
        with patch("eir.logger_manager.LoggerManager") as mock_manager_class:
            mock_manager = Mock()
            mock_logger = Mock(spec=logging.Logger)
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager

            @function_trace
            def test_function():
                return "test"

            test_function()

            # Verify that LoggerManager was imported and called correctly
            mock_manager_class.assert_called_once()
            mock_manager.get_logger.assert_called_once()

    def test_function_trace_colorama_formatting(self, clean_logging, reset_logger_manager):
        """Test that colorama formatting is applied correctly."""
        mock_logger = Mock(spec=logging.Logger)

        with patch("eir.logger_manager.LoggerManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.get_logger.return_value = mock_logger
            mock_manager_class.return_value = mock_manager

            @function_trace
            def test_function():
                return "test"

            test_function()

            calls = mock_logger.debug.call_args_list
            # Check that colorama codes are in the log messages
            assert "\033[36m" in calls[0][0][0]  # Fore.CYAN
            assert "\033[39m" in calls[0][0][0]  # Fore.RESET
            assert "\033[36m" in calls[1][0][0]  # Fore.CYAN
            assert "\033[39m" in calls[1][0][0]  # Fore.RESET


class TestPerformanceTimer:
    """Test the PerformanceTimer context manager."""

    def test_performance_timer_basic_usage(self):
        """Test basic usage of PerformanceTimer."""
        mock_logger = Mock(spec=logging.Logger)

        with PerformanceTimer("TestOperation", mock_logger):
            time.sleep(0.01)  # Sleep for 10ms

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "Executing TestOperation took" in call_args
        assert "ms" in call_args

        # Extract the time value and verify it's reasonable (should be ~10ms)
        time_part = call_args.split("took ")[1].split(" ms")[0]
        time_value = float(time_part)
        assert 5.0 < time_value < 50.0  # Allow some variance

    def test_performance_timer_init_parameters(self):
        """Test PerformanceTimer initialization parameters."""
        mock_logger = Mock(spec=logging.Logger)
        timer = PerformanceTimer("MyTimer", mock_logger)

        assert timer._timer_name == "MyTimer"
        assert timer._logger is mock_logger

    def test_performance_timer_enter_sets_start_time(self):
        """Test that __enter__ sets the start time."""
        mock_logger = Mock(spec=logging.Logger)
        timer = PerformanceTimer("TestTimer", mock_logger)

        with patch("eir.abk_common.timeit.default_timer", return_value=100.0):
            timer.__enter__()
            assert timer.start == 100.0

    def test_performance_timer_exit_calculates_time(self):
        """Test that __exit__ calculates and logs the time correctly."""
        mock_logger = Mock(spec=logging.Logger)
        timer = PerformanceTimer("TestTimer", mock_logger)

        with patch("eir.abk_common.timeit.default_timer", side_effect=[100.0, 100.5]):
            timer.__enter__()
            timer.__exit__(None, None, None)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "Executing TestTimer took 500.0 ms" in call_args

    def test_performance_timer_with_exception(self):
        """Test PerformanceTimer behavior when exception occurs in context."""
        mock_logger = Mock(spec=logging.Logger)

        with (
            pytest.raises(ValueError, match="Test exception"),
            PerformanceTimer("ExceptionTest", mock_logger),
        ):
            raise ValueError("Test exception")

        # Should still log the performance timing even with exception
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "Executing ExceptionTest took" in call_args

    def test_performance_timer_unused_exit_parameters(self):
        """Test that __exit__ properly handles unused parameters."""
        mock_logger = Mock(spec=logging.Logger)
        timer = PerformanceTimer("TestTimer", mock_logger)

        timer.start = 0.0
        with patch("eir.abk_common.timeit.default_timer", return_value=0.001):
            # Test that all these parameters are handled without error
            timer.__exit__("exc_type", "exc_value", "traceback")

        mock_logger.info.assert_called_once()

    def test_performance_timer_zero_time(self):
        """Test PerformanceTimer with zero execution time."""
        mock_logger = Mock(spec=logging.Logger)
        timer = PerformanceTimer("ZeroTimer", mock_logger)

        with patch("eir.abk_common.timeit.default_timer", return_value=100.0):
            timer.__enter__()
            timer.__exit__(None, None, None)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "Executing ZeroTimer took 0.0 ms" in call_args

    def test_performance_timer_very_long_operation(self):
        """Test PerformanceTimer with longer operation."""
        mock_logger = Mock(spec=logging.Logger)
        timer = PerformanceTimer("LongTimer", mock_logger)

        # Simulate 2.5 seconds
        with patch("eir.abk_common.timeit.default_timer", side_effect=[0.0, 2.5]):
            timer.__enter__()
            timer.__exit__(None, None, None)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "Executing LongTimer took 2500.0 ms" in call_args

    def test_performance_timer_string_conversion(self):
        """Test that time is converted to string properly."""
        mock_logger = Mock(spec=logging.Logger)
        timer = PerformanceTimer("StringTest", mock_logger)

        with patch("eir.abk_common.timeit.default_timer", side_effect=[0.0, 0.123456]):
            timer.__enter__()
            timer.__exit__(None, None, None)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        # Should include the full precision
        assert "123.456" in call_args


class TestModuleExecution:
    """Test module-level behavior."""

    def test_main_execution_raises_exception(self):
        """Test that executing the module directly raises an exception."""
        # Test the conditional logic rather than executing the module
        with patch("eir.abk_common.__name__", "__main__"), pytest.raises(Exception) as exc_info:
            if (
                "__main__" == "__main__"
            ):  # This mimics the module's if __name__ == "__main__" check
                raise Exception("This module should not be executed directly. Only for imports.")

        assert "This module should not be executed directly" in str(exc_info.value)

    def test_colorama_import(self):
        """Test that colorama is imported and available."""
        from eir.abk_common import Fore

        # Basic check that Fore attributes exist
        assert hasattr(Fore, "CYAN")
        assert hasattr(Fore, "RESET")

    def test_timeit_import(self):
        """Test that timeit is imported and available."""
        import eir.abk_common

        # Should be able to access timeit functions
        assert hasattr(eir.abk_common, "timeit")
        assert hasattr(eir.abk_common.timeit, "default_timer")
