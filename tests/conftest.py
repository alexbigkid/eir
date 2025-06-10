"""Pytest configuration and fixtures for eir tests."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import logging
import os


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def project_root_dir(temp_dir):
    """Create a temporary project root with pyproject.toml."""
    pyproject_content = """
[project]
name = "eir"
version = "0.1.0"
description = "Test project"
license = {text = "MIT"}
keywords = ["image", "processing", "exif"]
authors = [
    {name = "Test Author", email = "test@example.com"}
]
maintainers = [
    {name = "Test Maintainer", email = "maintainer@example.com"}
]
"""
    pyproject_path = temp_dir / "pyproject.toml"
    pyproject_path.write_text(pyproject_content.strip())
    return temp_dir


@pytest.fixture
def test_image_dir(temp_dir):
    """Create a test image directory with valid name format."""
    image_dir = temp_dir / "20110709_test_project"
    image_dir.mkdir()
    return image_dir


@pytest.fixture
def invalid_image_dir(temp_dir):
    """Create an invalid image directory name for testing."""
    image_dir = temp_dir / "invalid_dir_name"
    image_dir.mkdir()
    return image_dir


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return Mock(spec=logging.Logger)


@pytest.fixture
def sample_metadata():
    """Sample EXIF metadata for testing."""
    return {
        "SourceFile": "test_image.cr2",
        "EXIF:CreateDate": "2021:12:18 17:04:05",
        "EXIF:Make": "SONY",
        "EXIF:Model": "ILCE-7M3",
    }


@pytest.fixture
def sample_files_list():
    """Sample files list for testing."""
    return [
        "DSC06803.ARW",
        "DSC06828.ARW",
        "test_image.jpg",
        "video.mp4",
        ".hidden_file",
        "Thumbs.db",
    ]


@pytest.fixture
def mock_exiftool():
    """Mock ExifTool for testing."""
    with patch("eir.processor.exiftool.ExifToolHelper") as mock:
        instance = Mock()
        mock.return_value.__enter__.return_value = instance
        instance.get_tags.return_value = [
            {
                "SourceFile": "test.cr2",
                "EXIF:CreateDate": "2021:12:18 17:04:05",
                "EXIF:Make": "SONY",
                "EXIF:Model": "ILCE-7M3",
            }
        ]
        yield instance


@pytest.fixture
def clean_logging():
    """Clean up logging handlers before and after tests."""
    # Store original handlers
    original_handlers = logging.root.handlers[:]

    yield

    # Restore original handlers and clean up
    logging.root.handlers = original_handlers
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        if logger_name.startswith("eir") or logger_name in [
            "threadedLogger",
            "threadedConsoleLogger",
            "threadedFileLogger",
        ]:
            logger = logging.getLogger(logger_name)
            logger.handlers.clear()
            logger.disabled = False


@pytest.fixture
def reset_logger_manager():
    """Reset LoggerManager singleton between tests."""
    from eir.logger_manager import LoggerManager

    # Store original instance
    original_instance = LoggerManager._instance

    # Reset for test
    LoggerManager._instance = None

    yield

    # Restore original instance
    LoggerManager._instance = original_instance


@pytest.fixture(autouse=True)
def change_test_dir(request, temp_dir):
    """Change to temp directory for tests that need it."""
    # Only change directory for tests that are marked with 'needs_temp_dir'
    if request.node.get_closest_marker("needs_temp_dir"):
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        yield temp_dir
        os.chdir(original_cwd)
    else:
        yield temp_dir


# Custom markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "needs_temp_dir: mark test as needing temporary directory as cwd"
    )
    config.addinivalue_line("markers", "integration: mark test as integration test")
