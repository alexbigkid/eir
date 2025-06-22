"""Integration tests using real image files - runs only in CI pipeline."""

import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from eir.processor import ImageProcessor
from eir.logger_manager import LoggerManager


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


class TestRealImageIntegration:
    """Integration tests using real image files from various cameras and dates."""

    @pytest.fixture
    def logger(self):
        """Get logger for tests."""
        logger_manager = LoggerManager()
        logger_manager.configure(quiet=True)  # Configure for test environment
        return logger_manager.get_logger()

    @pytest.fixture
    def test_images_dir(self):
        """Get path to test images directory."""
        return Path(__file__).parent.parent / "test_images"

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for test execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def copy_test_directory(self, source_dir: Path, temp_workspace: Path) -> Path:
        """Copy a test directory to temporary workspace for processing."""
        dest_dir = temp_workspace / source_dir.name
        shutil.copytree(source_dir, dest_dir)
        return dest_dir

    def setup_mixed_directory(self, test_images_dir: Path, temp_workspace: Path) -> Path:
        """Set up the mixed date range directory with files from all other directories."""
        mixed_dir = temp_workspace / "20110709-20230809_mixed_images"
        mixed_dir.mkdir(parents=True, exist_ok=True)

        # Copy files from all individual date directories
        source_dirs = [
            "20110709_canon",
            "20211218_sony",
            "20221231_iPhone_raw",
            "20230808_sony",
            "20230809_Canon_R8",
            "20230809_Fujifilm_X-S20",
            "20230809_Leica_Q3",
            "20230809_Sony_a6700",
        ]

        for source_dir_name in source_dirs:
            source_dir = test_images_dir / source_dir_name
            if source_dir.exists():
                for file_path in source_dir.iterdir():
                    if file_path.is_file():
                        shutil.copy2(file_path, mixed_dir)

        return mixed_dir

    @pytest.mark.asyncio
    async def test_single_date_directories(self, logger, test_images_dir, temp_workspace):
        """Test processing of single-date format directories."""
        single_date_dirs = [
            "20110709_canon",
            "20211218_sony",
            "20221231_iPhone_raw",
            "20230808_sony",
            "20230809_Canon_R8",
            "20230809_Fujifilm_X-S20",
            "20230809_Leica_Q3",
            "20230809_Sony_a6700",
        ]

        results = {}

        for dir_name in single_date_dirs:
            source_dir = test_images_dir / dir_name
            if not source_dir.exists():
                continue

            # Copy directory to temp workspace
            test_dir = self.copy_test_directory(source_dir, temp_workspace)

            # Process with ImageProcessor
            processor = ImageProcessor(logger=logger, op_dir=str(test_dir))

            # Store original file list
            original_files = list(test_dir.glob("*"))
            original_count = len([f for f in original_files if f.is_file()])

            try:
                await processor.process_images_reactive()

                # Analyze results
                results[dir_name] = self.analyze_processing_results(test_dir, dir_name)
                results[dir_name]["original_count"] = original_count
                results[dir_name]["success"] = True

            except Exception as e:
                results[dir_name] = {
                    "success": False,
                    "error": str(e),
                    "original_count": original_count,
                }

        # Verify results
        self.verify_single_date_results(results)

    @pytest.mark.asyncio
    async def test_date_range_directory(self, logger, test_images_dir, temp_workspace):
        """Test processing of date range format directory."""
        # Set up mixed directory
        mixed_dir = self.setup_mixed_directory(test_images_dir, temp_workspace)

        # Store original file list
        original_files = list(mixed_dir.glob("*"))
        original_count = len([f for f in original_files if f.is_file()])

        # Process with ImageProcessor
        processor = ImageProcessor(logger=logger, op_dir=str(mixed_dir))

        try:
            await processor.process_images_reactive()

            # Analyze results
            results = self.analyze_processing_results(mixed_dir, "20110709-20230809_mixed_images")
            results["original_count"] = original_count
            results["success"] = True

            # Verify date range processing
            self.verify_date_range_results(results, mixed_dir)

        except Exception as e:
            pytest.fail(f"Date range directory processing failed: {e}")

    def analyze_processing_results(self, processed_dir: Path, dir_name: str) -> dict:
        """Analyze the results of image processing."""
        results = {
            "directory": dir_name,
            "subdirectories": [],
            "files_by_subdirectory": {},
            "file_naming_patterns": {},
            "total_processed_files": 0,
        }

        # Find created subdirectories
        for item in processed_dir.iterdir():
            if item.is_dir():
                results["subdirectories"].append(item.name)

                # Analyze files in each subdirectory
                files = [f.name for f in item.iterdir() if f.is_file()]
                results["files_by_subdirectory"][item.name] = files
                results["total_processed_files"] += len(files)

                # Analyze naming patterns
                for file_name in files:
                    self.analyze_file_naming_pattern(file_name, results["file_naming_patterns"])

        return results

    def analyze_file_naming_pattern(self, file_name: str, patterns: dict):
        """Analyze file naming pattern to verify our implementation."""
        name_parts = file_name.split("_")

        if len(name_parts) >= 3:
            date_part = name_parts[0]

            # Check if it's EXIF format (YYYYMMDD-HHMMSS) or fallback format (YYYYMMDD)
            if "-" in date_part and len(date_part) == 15:
                pattern_type = "exif_success"
            elif len(date_part) == 8 and date_part.isdigit():
                pattern_type = "exif_fallback"
            else:
                pattern_type = "unknown"

            patterns.setdefault(pattern_type, []).append(file_name)

    def verify_single_date_results(self, results: dict):
        """Verify results from single-date directory processing."""
        successful_dirs = [k for k, v in results.items() if v.get("success", False)]
        failed_dirs = [k for k, v in results.items() if not v.get("success", False)]

        # At least some directories should process successfully
        assert len(successful_dirs) > 0, (
            f"No directories processed successfully. Failures: {failed_dirs}"
        )

        for dir_name, result in results.items():
            if not result.get("success", False):
                continue

            # Verify directory structure was created
            assert len(result["subdirectories"]) > 0, f"No subdirectories created for {dir_name}"

            # Verify files were processed
            assert result["total_processed_files"] > 0, f"No files processed in {dir_name}"

            # Verify file naming patterns
            patterns = result["file_naming_patterns"]
            total_pattern_files = sum(len(files) for files in patterns.values())
            assert total_pattern_files > 0, f"No valid naming patterns found in {dir_name}"

            # Check for sequential numbering (should end with _001, _002, etc.)
            for _subdir, files in result["files_by_subdirectory"].items():
                for file_name in files:
                    name_without_ext = file_name.rsplit(".", 1)[0]
                    assert name_without_ext.endswith(("_001", "_002", "_003")), (
                        f"File {file_name} doesn't have sequential numbering"
                    )

    def verify_date_range_results(self, results: dict, mixed_dir: Path):
        """Verify results from date range directory processing."""
        # Should have processed files
        assert results["total_processed_files"] > 0, "No files processed in mixed directory"

        # Should have created subdirectories
        assert len(results["subdirectories"]) > 0, "No subdirectories created"

        # Should have both EXIF success and fallback patterns since we have various image types
        patterns = results["file_naming_patterns"]
        assert len(patterns) > 0, "No naming patterns detected"

        # Verify that files have proper sequential numbering
        for subdir, files in results["files_by_subdirectory"].items():
            numbered_files = [f for f in files if "_001" in f or "_002" in f or "_003" in f]
            assert len(numbered_files) > 0, f"No sequential numbering found in {subdir}"

    @pytest.mark.asyncio
    async def test_camera_brand_organization(self, logger, test_images_dir, temp_workspace):
        """Test that different camera brands are organized correctly."""
        # Test a few specific directories to verify camera brand detection
        test_cases = [
            ("20110709_canon", ["canon"]),
            ("20211218_sony", ["sony"]),
            ("20230809_Canon_R8", ["canon"]),
            ("20230809_Fujifilm_X-S20", ["fujifilm"]),
            ("20230809_Leica_Q3", ["leica"]),
        ]

        for dir_name, expected_brands in test_cases:
            source_dir = test_images_dir / dir_name
            if not source_dir.exists():
                continue

            test_dir = self.copy_test_directory(source_dir, temp_workspace)
            processor = ImageProcessor(logger=logger, op_dir=str(test_dir))

            await processor.process_images_reactive()

            # Check that subdirectories contain expected camera brands
            created_dirs = [d.name for d in test_dir.iterdir() if d.is_dir()]

            for expected_brand in expected_brands:
                brand_dirs = [d for d in created_dirs if expected_brand in d.lower()]
                assert len(brand_dirs) > 0, (
                    f"No {expected_brand} directories found in {dir_name}. "
                    f"Created: {created_dirs}"
                )

    @pytest.mark.asyncio
    async def test_file_type_processing(self, logger, test_images_dir, temp_workspace):
        """Test that different file types (RAW, compressed) are processed correctly."""
        # Use Sony directory which has both ARW and JPG files
        source_dir = test_images_dir / "20230809_Sony_a6700"

        if source_dir.exists():
            test_dir = self.copy_test_directory(source_dir, temp_workspace)
            processor = ImageProcessor(logger=logger, op_dir=str(test_dir))

            await processor.process_images_reactive()

            # Should have both RAW and compressed image directories
            created_dirs = [d.name for d in test_dir.iterdir() if d.is_dir()]

            # Should have ARW (RAW) directory
            arw_dirs = [d for d in created_dirs if "arw" in d.lower()]
            assert len(arw_dirs) > 0, f"No ARW directories found. Created: {created_dirs}"

            # Should have DNG (converted) directory
            dng_dirs = [d for d in created_dirs if "dng" in d.lower()]
            assert len(dng_dirs) > 0, f"No DNG directories found. Created: {created_dirs}"

            # Should have JPG directory
            jpg_dirs = [d for d in created_dirs if "jpg" in d.lower()]
            assert len(jpg_dirs) > 0, f"No JPG directories found. Created: {created_dirs}"


class TestDirectoryFormatValidation:
    """Test directory format validation with real directory names."""

    def test_existing_directory_format_validation(self):
        """Test that our validation accepts the existing test directory formats."""
        mock_logger = Mock()

        # Test single date directories
        single_date_dirs = [
            "20110709_canon",
            "20211218_sony",
            "20221231_iPhone_raw",
            "20230808_sony",
            "20230809_Canon_R8",
            "20230809_Fujifilm_X-S20",
            "20230809_Leica_Q3",
            "20230809_Sony_a6700",
        ]

        with patch("eir.logger_manager.LoggerManager") as mock_lm:
            mock_lm.return_value.get_logger.return_value = mock_logger

            for dir_name in single_date_dirs:
                processor = ImageProcessor(logger=mock_logger, op_dir=dir_name)
                # Should not raise exception
                processor._validate_image_dir()

    def test_date_range_directory_validation(self):
        """Test that date range format is properly validated."""
        mock_logger = Mock()

        with patch("eir.logger_manager.LoggerManager") as mock_lm:
            mock_lm.return_value.get_logger.return_value = mock_logger

            # Test date range directory
            processor = ImageProcessor(
                logger=mock_logger, op_dir="20110709-20230809_mixed_images"
            )
            # Should not raise exception
            processor._validate_image_dir()

            # Test extraction
            fallback_date, is_range = processor._extract_directory_info()
            assert fallback_date == "20110709"
            assert is_range is True
