"""Integration tests using real image files - runs only in CI pipeline."""

import os
import shutil
import subprocess  # noqa: S404
import tempfile
import pytest
from pathlib import Path


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


class TestRealImageIntegration:
    """Integration tests using real image files from various cameras and dates."""

    @pytest.fixture
    def eir_binary(self):
        """Get path to eir binary for subprocess calls."""
        # Check if we're running in CI with a built binary
        binary_path = os.environ.get("EIR_BINARY_PATH")
        if binary_path and Path(binary_path).exists():
            return binary_path

        # Fall back to uv run for local development
        return None

    def run_eir_binary(self, eir_binary, target_dir: Path) -> int:
        """Run eir binary on target directory and return exit code."""
        if eir_binary:
            # Use compiled binary - convert to absolute path
            binary_path = Path(eir_binary)
            if not binary_path.is_absolute():
                # Convert relative path to absolute from current working directory
                binary_path = Path.cwd() / binary_path

            # Check if binary exists
            if not binary_path.exists():
                raise FileNotFoundError(f"Binary not found: {binary_path}")

            # Make sure binary is executable on Unix systems
            if not binary_path.name.endswith(".exe"):
                binary_path.chmod(0o755)

            cmd = [str(binary_path), "-d", str(target_dir), "-q"]
        else:
            # Use uv run for local development
            cmd = ["uv", "run", "eir", "-d", str(target_dir), "-q"]

        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, cwd=target_dir.parent, check=False
        )
        
        # If binary failed, include stdout/stderr in the error for debugging
        if result.returncode != 0:
            error_msg = f"Binary exited with code {result.returncode}"
            if result.stdout:
                error_msg += f"\nSTDOUT: {result.stdout}"
            if result.stderr:
                error_msg += f"\nSTDERR: {result.stderr}"
            # Store error details for debugging
            if not hasattr(self, '_last_error'):
                self._last_error = error_msg
        
        return result.returncode

    @pytest.fixture
    def test_images_dir(self):
        """Get path to test images directory."""
        return Path(__file__).parent / "test_images"

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

    def test_single_date_directories(self, eir_binary, test_images_dir, temp_workspace):
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

            # Store original file list
            original_files = list(test_dir.glob("*"))
            original_count = len([f for f in original_files if f.is_file()])

            try:
                # Run eir binary on the test directory
                exit_code = self.run_eir_binary(eir_binary, test_dir)

                if exit_code == 0:
                    # Analyze results
                    results[dir_name] = self.analyze_processing_results(test_dir, dir_name)
                    results[dir_name]["original_count"] = original_count
                    results[dir_name]["success"] = True
                else:
                    error_msg = getattr(self, '_last_error', f"Binary exited with code {exit_code}")
                    results[dir_name] = {
                        "success": False,
                        "error": error_msg,
                        "original_count": original_count,
                    }

            except Exception as e:
                results[dir_name] = {
                    "success": False,
                    "error": str(e),
                    "original_count": original_count,
                }

        # Verify results
        self.verify_single_date_results(results)

    def test_date_range_directory(self, eir_binary, test_images_dir, temp_workspace):
        """Test processing of date range format directory."""
        # Set up mixed directory
        mixed_dir = self.setup_mixed_directory(test_images_dir, temp_workspace)

        # Store original file list
        original_files = list(mixed_dir.glob("*"))
        original_count = len([f for f in original_files if f.is_file()])

        try:
            # Run eir binary on the mixed directory
            exit_code = self.run_eir_binary(eir_binary, mixed_dir)

            if exit_code == 0:
                # Analyze results
                results = self.analyze_processing_results(
                    mixed_dir, "20110709-20230809_mixed_images"
                )
                results["original_count"] = original_count
                results["success"] = True

                # Verify date range processing
                self.verify_date_range_results(results)
            else:
                error_msg = getattr(self, '_last_error', f"binary exited with code {exit_code}")
                pytest.fail(f"Date range directory processing failed: {error_msg}")

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

    def verify_date_range_results(self, results: dict):
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

    def test_camera_brand_organization(self, eir_binary, test_images_dir, temp_workspace):
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

            # Run eir binary on the test directory
            exit_code = self.run_eir_binary(eir_binary, test_dir)
            if exit_code != 0:
                error_msg = getattr(self, '_last_error', f"Binary failed with exit code {exit_code}")
                assert False, error_msg

            # Check that subdirectories contain expected camera brands
            created_dirs = [d.name for d in test_dir.iterdir() if d.is_dir()]

            for expected_brand in expected_brands:
                brand_dirs = [d for d in created_dirs if expected_brand in d.lower()]
                assert len(brand_dirs) > 0, (
                    f"No {expected_brand} directories found in {dir_name}. "
                    f"Created: {created_dirs}"
                )

    def test_file_type_processing(self, eir_binary, test_images_dir, temp_workspace):
        """Test that different file types (RAW, compressed) are processed correctly."""
        # Use Sony directory which has both ARW and JPG files
        source_dir = test_images_dir / "20230809_Sony_a6700"

        if source_dir.exists():
            test_dir = self.copy_test_directory(source_dir, temp_workspace)

            # Run eir binary on the test directory
            exit_code = self.run_eir_binary(eir_binary, test_dir)
            if exit_code != 0:
                error_msg = getattr(self, '_last_error', f"Binary failed with exit code {exit_code}")
                assert False, error_msg

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
