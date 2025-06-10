"""Tests for cli.py module."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from argparse import Namespace

from eir.cli import main


class TestMain:
    """Test the main function."""

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_basic_execution(self, mock_clo_class, mock_run_pipeline, mock_asyncio_run):
        """Test basic execution flow of main function."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/test/path")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Call main
        main()

        # Verify the flow
        mock_clo_class.assert_called_once()
        mock_clo_instance.handle_options.assert_called_once()
        mock_asyncio_run.assert_called_once()

        # Verify run_pipeline was called with correct arguments
        # The call_args is a coroutine, we need to check if run_pipeline was called correctly
        mock_run_pipeline.assert_called_once_with(logger=mock_logger, image_dir="/test/path")

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_with_different_directory(
        self, mock_clo_class, mock_run_pipeline, mock_asyncio_run
    ):
        """Test main function with different directory."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/another/test/directory")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Call main
        main()

        # Verify run_pipeline was called with correct directory
        mock_run_pipeline.assert_called_once_with(
            logger=mock_logger, image_dir="/another/test/directory"
        )

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_with_current_directory(
        self, mock_clo_class, mock_run_pipeline, mock_asyncio_run
    ):
        """Test main function with current directory (default)."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir=".")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Call main
        main()

        # Verify run_pipeline was called with current directory
        mock_run_pipeline.assert_called_once_with(logger=mock_logger, image_dir=".")

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_handles_clo_exception(
        self, mock_clo_class, mock_run_pipeline, mock_asyncio_run
    ):
        """Test main function handles CommandLineOptions exceptions."""
        # Setup mocks to raise exception
        mock_clo_instance = Mock()
        mock_clo_instance.handle_options.side_effect = Exception("CLO Error")
        mock_clo_class.return_value = mock_clo_instance

        # Should re-raise the exception
        with pytest.raises(Exception, match="CLO Error"):
            main()

        # asyncio.run should not be called if handle_options fails
        mock_asyncio_run.assert_not_called()

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_handles_asyncio_exception(
        self, mock_clo_class, mock_run_pipeline, mock_asyncio_run
    ):
        """Test main function handles asyncio.run exceptions."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/test/path")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Make asyncio.run raise an exception
        mock_asyncio_run.side_effect = RuntimeError("Asyncio Error")

        # Should re-raise the exception
        with pytest.raises(RuntimeError, match="Asyncio Error"):
            main()

        # Verify that handle_options was still called
        mock_clo_instance.handle_options.assert_called_once()

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_logger_parameter_passing(
        self, mock_clo_class, mock_run_pipeline, mock_asyncio_run
    ):
        """Test that logger is passed correctly to run_pipeline."""
        # Setup mocks with specific logger
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_logger.name = "test_logger"
        mock_options = Namespace(dir="/test/path")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Call main
        main()

        # Verify the logger object is passed correctly
        mock_run_pipeline.assert_called_once_with(logger=mock_logger, image_dir="/test/path")

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_integration_flow(self, mock_clo_class, mock_run_pipeline, mock_asyncio_run):
        """Test the integration flow of main function."""
        # Setup complete mock chain
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/integration/test")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Mock run_pipeline to return a mock coroutine

        mock_run_pipeline.return_value = AsyncMock(return_value="pipeline_result")

        # Call main
        main()

        # Verify the complete flow
        assert mock_clo_class.call_count == 1
        assert mock_clo_instance.handle_options.call_count == 1
        assert mock_run_pipeline.call_count == 1
        assert mock_asyncio_run.call_count == 1

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_no_return_value(self, mock_clo_class, mock_run_pipeline, mock_asyncio_run):
        """Test that main function doesn't return a value."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/test/path")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Call main and check return value
        result = main()

        # main() should not return anything (implicit None)
        assert result is None

    def test_main_imports(self):
        """Test that main function imports are correct."""
        # Test that we can import the required modules
        import eir.cli
        import eir.clo
        from eir.processor import run_pipeline
        import asyncio

        # Basic checks that imports work
        assert hasattr(eir.cli, "main")
        assert hasattr(eir.clo, "CommandLineOptions")
        assert callable(run_pipeline)
        assert hasattr(asyncio, "run")

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_parameter_types(self, mock_clo_class, mock_run_pipeline, mock_asyncio_run):
        """Test that main passes parameters with correct types."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/test/path")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Call main
        main()

        # Get the call arguments
        call_args, call_kwargs = mock_run_pipeline.call_args

        # Verify parameter types and names
        assert "logger" in call_kwargs
        assert "image_dir" in call_kwargs
        assert call_kwargs["logger"] is mock_logger
        assert isinstance(call_kwargs["image_dir"], str)
        assert call_kwargs["image_dir"] == "/test/path"


class TestMainAsyncBehavior:
    """Test async behavior of main function."""

    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_calls_asyncio_run_with_coroutine(self, mock_clo_class):
        """Test that main calls asyncio.run with a coroutine."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/test/path")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Track if asyncio.run was called properly
        run_called_with_coro = False

        def capture_and_run_coroutine(coro):
            nonlocal run_called_with_coro
            if asyncio.iscoroutine(coro):
                run_called_with_coro = True
                # Actually run the coroutine to avoid warnings
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()
            return Mock()

        with (
            patch("eir.cli.asyncio.run", side_effect=capture_and_run_coroutine),
            patch("eir.cli.run_pipeline") as mock_run_pipeline,
        ):
            # Create a proper coroutine function
            async def mock_coro():
                return "test_result"

            # Use the coroutine function, not the coroutine instance
            mock_run_pipeline.side_effect = lambda **kwargs: mock_coro()

            main()

        # Verify that asyncio.run was called with a coroutine
        assert run_called_with_coro is True

    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_async_exception_propagation(self, mock_clo_class):
        """Test that async exceptions are properly propagated."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/test/path")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Create a coroutine function that raises an exception
        async def failing_pipeline(logger, image_dir):
            raise ValueError("Pipeline failed")

        with (
            patch(
                "eir.cli.run_pipeline",
                side_effect=lambda **kwargs: failing_pipeline(
                    kwargs.get("logger"), kwargs.get("image_dir")
                ),
            ),
            pytest.raises(ValueError, match="Pipeline failed"),
        ):
            main()


class TestMainDocumentation:
    """Test documentation and metadata of main function."""

    def test_main_function_exists(self):
        """Test that main function is properly defined."""
        from eir.cli import main

        assert callable(main)
        assert main.__name__ == "main"

    def test_main_function_docstring(self):
        """Test that main function has proper docstring."""
        from eir.cli import main

        assert main.__doc__ is not None
        assert "Main function" in main.__doc__

    def test_main_function_annotations(self):
        """Test main function type annotations."""
        from eir.cli import main

        # Check if function has annotations (even if empty)
        assert hasattr(main, "__annotations__")

    def test_module_structure(self):
        """Test the overall module structure."""
        import eir.cli

        # Check that module has expected attributes
        assert hasattr(eir.cli, "main")
        assert hasattr(eir.cli, "asyncio")
        assert hasattr(eir.cli, "clo")

        # Check imports
        assert "run_pipeline" in dir(eir.cli)


class TestMainEdgeCases:
    """Test edge cases and error conditions."""

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_with_none_logger(self, mock_clo_class, mock_run_pipeline, mock_asyncio_run):
        """Test main function when logger is None."""
        # Setup mocks with None logger
        mock_clo_instance = Mock()
        mock_clo_instance.logger = None
        mock_options = Namespace(dir="/test/path")
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Call main
        main()

        # Should still work and pass None as logger
        mock_run_pipeline.assert_called_once_with(logger=None, image_dir="/test/path")

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_with_empty_directory(self, mock_clo_class, mock_run_pipeline, mock_asyncio_run):
        """Test main function with empty directory string."""
        # Setup mocks with empty directory
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Call main
        main()

        # Should pass empty string as directory
        mock_run_pipeline.assert_called_once_with(logger=mock_logger, image_dir="")

    @patch("eir.cli.asyncio.run")
    @patch("eir.cli.run_pipeline")
    @patch("eir.cli.clo.CommandLineOptions")
    def test_main_keyboard_interrupt(self, mock_clo_class, mock_run_pipeline, mock_asyncio_run):
        """Test main function handles KeyboardInterrupt."""
        # Setup mocks
        mock_clo_instance = Mock()
        mock_logger = Mock()
        mock_options = Namespace(dir="/test/path")

        mock_clo_instance.logger = mock_logger
        mock_clo_instance.options = mock_options
        mock_clo_class.return_value = mock_clo_instance

        # Make asyncio.run raise KeyboardInterrupt
        mock_asyncio_run.side_effect = KeyboardInterrupt("User interrupted")

        # Should re-raise the KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt, match="User interrupted"):
            main()

        # Verify that setup was done before interruption
        mock_clo_instance.handle_options.assert_called_once()
