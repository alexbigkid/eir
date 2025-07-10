"""Simplified tests for the processor module with working examples."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from eir.processor import ExifTag, ImageProcessor, ListType


class TestEnums:
    """Test cases for enum classes."""

    def test_list_type_enum_values(self):
        """Test ListType enum has correct values."""
        assert ListType.RAW_IMAGE_DICT.value == "raw_image_dict"
        assert ListType.THUMB_IMAGE_DICT.value == "thumb_image_dict"
        assert ListType.COMPRESSED_IMAGE_DICT.value == "compressed_image_dict"
        assert ListType.COMPRESSED_VIDEO_DICT.value == "compressed_video_dict"

    def test_exif_tag_enum_values(self):
        """Test ExifTag enum has correct values."""
        assert ExifTag.SOURCE_FILE.value == "SourceFile"
        assert ExifTag.CREATE_DATE.value == "EXIF:CreateDate"
        assert ExifTag.MAKE.value == "EXIF:Make"
        assert ExifTag.MODEL.value == "EXIF:Model"


class TestImageProcessorInitialization:
    """Test cases for ImageProcessor initialization."""

    def test_init_with_logger(self, mock_logger):
        """Test initialization with provided logger."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        assert processor._logger == mock_logger
        assert processor._op_dir == "/test/dir"
        assert processor._current_dir is None
        assert processor._project_name is None

    def test_init_without_logger(self):
        """Test initialization without logger creates default logger."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            processor = ImageProcessor(logger=None, op_dir="/test/dir")

            assert processor._logger == mock_logger
            mock_get_logger.assert_called_once_with("eir.processor")

    def test_supported_extensions_initialization(self, mock_logger):
        """Test that supported extensions list is correctly initialized."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        # Check that all raw extensions are included
        expected_extensions = {
            "dng",
            "crw",
            "cr2",
            "cr3",
            "raf",
            "rwl",
            "mrw",
            "nef",
            "nrw",
            "orw",
            "raw",
            "rw2",
            "pef",
            "srw",
            "arw",
            "sr2",
        }
        assert set(processor._supported_raw_image_ext_list) == expected_extensions


class TestProjectNameProperty:
    """Test cases for project_name property."""

    @patch("os.getcwd")
    @patch("os.path.basename")
    @patch("os.path.normpath")
    def test_project_name_extraction(self, mock_normpath, mock_basename, mock_getcwd, mock_logger):
        """Test project name extraction from directory."""
        mock_getcwd.return_value = "/path/to/20241210_test_project"
        mock_normpath.return_value = "/path/to/20241210_test_project"
        mock_basename.return_value = "20241210_test_project"

        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        result = processor.project_name

        assert result == "test_project"
        mock_logger.info.assert_any_call("self._project_name = 'test_project'")

    @patch("pathlib.Path.cwd")
    @patch("os.getcwd")
    @patch("os.path.basename")
    @patch("os.path.normpath")
    def test_project_name_caching(self, mock_normpath, mock_basename, mock_getcwd, mock_path_cwd, mock_logger):
        """Test that project name is cached after first access."""
        mock_getcwd.return_value = "/path/to/20241210_test_project"
        mock_normpath.return_value = "/path/to/20241210_test_project"
        mock_basename.return_value = "20241210_test_project"
        mock_path_cwd.return_value = Path("/path/to/20241210_test_project")

        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        # Access twice
        result1 = processor.project_name
        result2 = processor.project_name

        assert result1 == result2 == "test_project"
        # Should only call os functions once due to caching
        mock_getcwd.assert_called_once()
        mock_basename.assert_called_once()


class TestExifExtraction:
    """Test cases for EXIF metadata extraction."""

    @pytest.mark.asyncio
    @patch("eir.logger_manager.LoggerManager")
    @patch("exiftool.ExifToolHelper")
    async def test_extract_exif_metadata_success(
        self, mock_exiftool_helper, mock_logger_manager, mock_logger, reset_logger_manager, clean_logging
    ):
        """Test successful EXIF metadata extraction."""
        # Setup LoggerManager mock
        mock_logger_manager.return_value.get_logger.return_value = mock_logger

        mock_helper = Mock()
        mock_metadata = [
            {"SourceFile": "test1.jpg", "EXIF:Make": "Canon"},
            {"SourceFile": "test2.cr2", "EXIF:Make": "Canon", "EXIF:Model": "EOS R5"},
        ]
        mock_helper.get_tags.return_value = mock_metadata
        mock_exiftool_helper.return_value.__enter__ = Mock(return_value=mock_helper)
        mock_exiftool_helper.return_value.__exit__ = Mock(return_value=None)

        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")
        files_list = ["test1.jpg", "test2.cr2"]

        result = await processor.extract_exif_metadata(files_list)

        assert result == mock_metadata
        mock_helper.get_tags.assert_called_once_with(files_list, processor.EXIF_TAGS)
        assert mock_helper.logger == mock_logger

    @pytest.mark.asyncio
    @patch("eir.logger_manager.LoggerManager")
    @patch("exiftool.ExifToolHelper")
    async def test_extract_exif_metadata_empty_list(
        self, mock_exiftool_helper, mock_logger_manager, mock_logger, reset_logger_manager, clean_logging
    ):
        """Test EXIF extraction with empty file list."""
        # Setup LoggerManager mock
        mock_logger_manager.return_value.get_logger.return_value = mock_logger

        mock_helper = Mock()
        mock_helper.get_tags.return_value = []
        mock_exiftool_helper.return_value.__enter__ = Mock(return_value=mock_helper)
        mock_exiftool_helper.return_value.__exit__ = Mock(return_value=None)

        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        result = await processor.extract_exif_metadata([])

        assert result == []


class TestMetadataProcessing:
    """Test cases for metadata processing."""

    def test_process_metadata_raw_image(self, mock_logger, reset_logger_manager, clean_logging):
        """Test processing metadata for RAW image file."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")
        metadata = {
            "SourceFile": "test.cr2",
            "EXIF:CreateDate": "2024:12:10 14:30:00",
            "EXIF:Make": "Canon",
            "EXIF:Model": "Canon EOS R5",
        }
        filtered_list = ["test.cr2"]

        result = processor._process_metadata(metadata, filtered_list)

        assert result is not None
        list_type, dir_name, processed_metadata = result
        assert list_type == ListType.RAW_IMAGE_DICT
        assert dir_name == "canon_eosr5_cr2"
        assert processed_metadata["EXIF:CreateDate"] == "20241210-143000"
        assert processed_metadata["EXIF:Make"] == "Canon"
        assert processed_metadata["EXIF:Model"] == "EOSR5"

    def test_process_metadata_compressed_image(self, mock_logger):
        """Test processing metadata for compressed image file."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")
        metadata = {
            "SourceFile": "test.jpg",
            "EXIF:CreateDate": "2024:12:10 14:30:00",
            "EXIF:Make": "Canon",
            "EXIF:Model": "EOS R5",
        }
        filtered_list = ["test.jpg"]

        result = processor._process_metadata(metadata, filtered_list)

        assert result is not None
        list_type, dir_name, processed_metadata = result
        assert list_type == ListType.COMPRESSED_IMAGE_DICT
        assert dir_name == "canon_eosr5_jpg"

    def test_process_metadata_missing_source_file(self, mock_logger):
        """Test processing metadata without source file."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")
        metadata = {"EXIF:CreateDate": "2024:12:10 14:30:00", "EXIF:Make": "Canon"}
        filtered_list = []

        result = processor._process_metadata(metadata, filtered_list)

        assert result is None

    def test_process_metadata_unknown_extension(self, mock_logger):
        """Test processing metadata for unsupported file extension."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")
        metadata = {"SourceFile": "test.txt", "EXIF:CreateDate": "2024:12:10 14:30:00"}
        filtered_list = ["test.txt"]

        result = processor._process_metadata(metadata, filtered_list)

        assert result is None


class TestFileOperations:
    """Test cases for file operations."""

    @pytest.mark.asyncio
    @patch("os.rename")
    async def test_rename_file_async_success(self, mock_rename, mock_logger):
        """Test successful file renaming."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        await processor._rename_file_async("old_name.jpg", "new_name.jpg")

        mock_rename.assert_called_once_with("old_name.jpg", "new_name.jpg")
        # Check that the specific rename debug message was called
        mock_logger.debug.assert_any_call("renamed file: old_name.jpg to new_name.jpg")

    @pytest.mark.asyncio
    @patch("os.rename")
    async def test_rename_file_async_error(self, mock_rename, mock_logger):
        """Test file renaming with OS error."""
        mock_rename.side_effect = OSError("Permission denied")
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        await processor._rename_file_async("old_name.jpg", "new_name.jpg")

        mock_logger.error.assert_called_once_with("Error renaming: old_name.jpg: Permission denied")

    @pytest.mark.asyncio
    @patch("eir.processor.ImageProcessor._configure_dng_converter")
    @patch("pydngconverter.DNGConverter")
    @patch("os.makedirs")
    @patch("os.path.exists")
    async def test_convert_raw_to_dng(self, mock_exists, mock_makedirs, mock_dng_converter, mock_configure_dng, mock_logger):
        """Test RAW to DNG conversion."""
        mock_exists.return_value = False
        mock_converter = AsyncMock()
        mock_dng_converter.return_value = mock_converter

        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        await processor.convert_raw_to_dng("/src/dir", "/dst/dir")

        mock_makedirs.assert_called_once_with("/dst/dir")
        mock_configure_dng.assert_called_once()
        mock_dng_converter.assert_called_once_with(source=Path("/src/dir"), dest=Path("/dst/dir"))
        mock_converter.convert.assert_called_once()


class TestEdgeCases:
    """Test cases for edge cases and error conditions."""

    def test_supported_extensions_completeness(self, mock_logger):
        """Test that all supported extensions are properly categorized."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        # All extensions should be categorized
        all_extensions = (
            processor._supported_raw_image_ext_list
            + processor.SUPPORTED_COMPRESSED_IMAGE_EXT_LIST
            + processor.SUPPORTED_COMPRESSED_VIDEO_EXT_LIST
        )

        # Should have comprehensive coverage
        assert len(all_extensions) > 25  # Reasonable threshold
        assert "cr2" in processor._supported_raw_image_ext_list
        assert "jpg" in processor.SUPPORTED_COMPRESSED_IMAGE_EXT_LIST
        assert "mp4" in processor.SUPPORTED_COMPRESSED_VIDEO_EXT_LIST

    def test_exif_unknown_constant(self, mock_logger):
        """Test EXIF_UNKNOWN constant is properly defined."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")
        assert processor.EXIF_UNKNOWN == "unknown"

    def test_files_to_exclude_expression(self, mock_logger):
        """Test files exclusion regex pattern."""
        import re

        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        pattern = processor.FILES_TO_EXCLUDE_EXPRESSION

        # Should match system files
        assert re.match(pattern, "Adobe Bridge Cache")
        assert re.match(pattern, "Thumbs.db")
        assert re.match(pattern, ".hidden_file")

        # Should not match regular files
        assert not re.match(pattern, "normal_file.jpg")

    def test_constants_and_mappings(self, mock_logger):
        """Test that constants and mappings are correctly defined."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        # Test EXIF tags
        assert len(processor.EXIF_TAGS) == 3
        assert "EXIF:CreateDate" in processor.EXIF_TAGS
        assert "EXIF:Make" in processor.EXIF_TAGS
        assert "EXIF:Model" in processor.EXIF_TAGS

        # Test supported extensions structure
        assert "Canon" in processor.SUPPORTED_RAW_IMAGE_EXT
        assert "cr2" in processor.SUPPORTED_RAW_IMAGE_EXT["Canon"]

        # Test thumbnail configuration
        assert processor.THMB["ext"] == "jpg"
        assert processor.THMB["dir"] == "thmb"


class TestComplexScenarios:
    """Test cases for complex real-world scenarios."""

    def test_thumbnail_detection_logic(self, mock_logger):
        """Test logic for detecting thumbnail files."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        # Test case: JPG file with corresponding RAW file should be thumbnail
        metadata = {"SourceFile": "DSC001.jpg", "EXIF:Make": "Canon"}
        filtered_list = ["DSC001.jpg", "DSC001.cr2"]  # RAW file exists

        result = processor._process_metadata(metadata, filtered_list)
        list_type, dir_name, _ = result

        assert list_type == ListType.THUMB_IMAGE_DICT
        assert "thmb" in dir_name

    def test_make_model_deduplication(self, mock_logger):
        """Test removal of duplicate make from model name."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        metadata = {
            "SourceFile": "test.cr2",
            "EXIF:Make": "Sony",
            "EXIF:Model": "Sony ILCE-7M3",  # Make is duplicated in model
        }
        filtered_list = ["test.cr2"]

        result = processor._process_metadata(metadata, filtered_list)
        _, _, processed_metadata = result

        assert processed_metadata["EXIF:Model"] == "ILCE-7M3"  # Make removed

    def test_unknown_make_inference_from_raw_extension(self, mock_logger):
        """Test inference of camera make from RAW file extension when EXIF missing."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        metadata = {
            "SourceFile": "test.nef"  # Nikon extension
            # No EXIF:Make provided
        }
        filtered_list = ["test.nef"]

        result = processor._process_metadata(metadata, filtered_list)
        _, _, processed_metadata = result

        assert processed_metadata["EXIF:Make"] == "Nikon"  # Inferred from .nef extension

    def test_date_time_formatting(self, mock_logger):
        """Test proper formatting of date/time from EXIF."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        metadata = {
            "SourceFile": "test.jpg",
            "EXIF:CreateDate": "2024:12:10 14:30:05",  # Standard EXIF format
        }
        filtered_list = ["test.jpg"]

        result = processor._process_metadata(metadata, filtered_list)
        _, _, processed_metadata = result

        assert processed_metadata["EXIF:CreateDate"] == "20241210-143005"  # Formatted for filename

    def test_file_extension_case_handling(self, mock_logger):
        """Test handling of different file extension cases."""
        processor = ImageProcessor(logger=mock_logger, op_dir="/test/dir")

        # Test uppercase extension
        metadata = {"SourceFile": "test.CR2"}
        filtered_list = ["test.CR2"]

        result = processor._process_metadata(metadata, filtered_list)
        assert result is not None
        list_type, _, _ = result
        assert list_type == ListType.RAW_IMAGE_DICT
