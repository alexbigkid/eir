"""Integration tests using real image files - runs only in CI pipeline."""

import os
import shutil
import subprocess  # noqa: S404
import tempfile
import platform
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

            # Use quiet mode to suppress INFO logging during integration tests
            cmd = [str(binary_path), "-q", "-d", str(target_dir)]
        else:
            # Use uv run for local development with quiet mode
            cmd = ["uv", "run", "eir", "-q", "-d", str(target_dir)]

        try:
            result = subprocess.run(  # noqa: S603
                cmd, capture_output=True, text=True, cwd=target_dir.parent, check=False, timeout=300
            )
        except subprocess.TimeoutExpired as e:
            error_msg = "Binary timed out after 300 seconds"
            if e.stdout:
                stdout_text = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
                error_msg += f"\nSTDOUT: {stdout_text}"
            if e.stderr:
                stderr_text = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
                error_msg += f"\nSTDERR: {stderr_text}"
            print(f"\n=== EIR BINARY TIMEOUT FOR {target_dir.name} ===")
            print(error_msg)
            print("=== END EIR BINARY TIMEOUT ===\n")
            self._last_error = error_msg
            return -1  # Return non-zero exit code for timeout

        # Always show stdout/stderr for DNG conversion debugging
        if result.stdout:
            print(f"\n=== EIR BINARY OUTPUT FOR {target_dir.name} ===")
            print(result.stdout)
            print("=== END EIR BINARY OUTPUT ===\n")

        if result.stderr:
            print(f"\n=== EIR BINARY STDERR FOR {target_dir.name} ===")
            print(result.stderr)
            print("=== END EIR BINARY STDERR ===\n")

        # If binary failed, include stdout/stderr in the error for debugging
        if result.returncode != 0:
            error_msg = f"Binary exited with code {result.returncode}"
            if result.stdout:
                error_msg += f"\nSTDOUT: {result.stdout}"
            if result.stderr:
                error_msg += f"\nSTDERR: {result.stderr}"
            # Store error details for debugging
            if not hasattr(self, "_last_error"):
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

    def show_directory_tree(self, directory: Path, title: str) -> None:
        """Show directory structure using tree command."""
        print(f"\n{title}")
        print("=" * len(title))

        try:
            # Try native tree cmd on Unix systems only (Windows tree output is poorly formatted)
            if platform.system().lower() != "windows":
                # Unix tree command with file sizes
                result = subprocess.run(["tree", "-s", str(directory)], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    print(result.stdout)
                    return

            # Use Python-based tree display for Windows or when tree command fails
            self._show_directory_tree_python(directory)
        except Exception as e:
            print(f"Could not display tree structure: {e}")
            # Simple fallback listing
            print(f"Directory contents of {directory}:")
            for item in sorted(directory.iterdir()):
                if item.is_dir():
                    file_count = len([f for f in item.rglob("*") if f.is_file()])
                    print(f"  {item.name}/ ({file_count} files)")
                else:
                    size_bytes = item.stat().st_size
                    if size_bytes > 1024 * 1024:
                        size_mb = size_bytes / (1024 * 1024)
                        size_unit = "MB"
                    else:
                        size_mb = size_bytes / 1024
                        size_unit = "KB"
                    print(f"  {item.name} ({size_mb:.1f} {size_unit})")

    def _show_directory_tree_python(self, directory: Path, prefix: str = "", is_last: bool = True) -> None:
        """Show directory tree using Python with clean formatting."""
        # Use ASCII-compatible characters for Windows compatibility
        is_windows = platform.system().lower() == "windows"
        branch = "+-- " if is_windows else "├── "
        last_branch = "`-- " if is_windows else "└── "
        vertical = "|   " if is_windows else "│   "

        if prefix == "":
            # Root directory
            if directory.is_file():
                size_bytes = directory.stat().st_size
                size_str = self._format_file_size(size_bytes)
                print(f"[{size_str:>12}]  {directory.name}")
            else:
                print(f"[       4096]  {directory}")

        # Get and sort directory contents
        try:
            items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return

        for i, item in enumerate(items):
            is_last_item = i == len(items) - 1

            if item.is_file():
                size_bytes = item.stat().st_size
                size_str = self._format_file_size(size_bytes)
                connector = last_branch if is_last_item else branch
                print(f"{prefix}{connector}[{size_str:>12}]  {item.name}")
            else:
                connector = last_branch if is_last_item else branch
                print(f"{prefix}{connector}[       4096]  {item.name}")

                # Recursively show subdirectory contents
                extension = "    " if is_last_item else vertical
                self._show_directory_tree_python(item, prefix + extension, is_last_item)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes >= 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}G"
        elif size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}M"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f}K"
        else:
            return str(size_bytes)

    def get_mixed_date_directories(self, test_images_dir: Path) -> list[str]:
        """Discover all mixed date range directories (YYYYMMDD-YYYYMMDD pattern)."""
        mixed_dirs = []
        for item in test_images_dir.iterdir():
            # Check if it looks like a date range (YYYYMMDD-YYYYMMDD pattern)
            # Must start with 8 digits followed by hyphen and more digits
            if (
                item.is_dir()
                and "-" in item.name
                and len(item.name) >= 17
                and item.name[:8].isdigit()
                and item.name[8] == "-"
                and item.name[9:17].isdigit()
            ):
                mixed_dirs.append(item.name)
        return sorted(mixed_dirs)

    def setup_mixed_directory(self, test_images_dir: Path, temp_workspace: Path) -> Path:
        """Set up the mixed date range directory with files from all single-date directories."""
        # Find date range for naming (earliest to latest single-date directory)
        single_date_dirs = self.get_single_date_directories(test_images_dir)
        if single_date_dirs:
            earliest_date = single_date_dirs[0][:8]  # YYYYMMDD
            latest_date = single_date_dirs[-1][:8]  # YYYYMMDD
            mixed_dir_name = f"{earliest_date}-{latest_date}_mixed_images"
        else:
            mixed_dir_name = "mixed_images"

        mixed_dir = temp_workspace / mixed_dir_name
        mixed_dir.mkdir(parents=True, exist_ok=True)

        # Copy files from all single-date directories
        copied_count = 0
        for source_dir_name in single_date_dirs:
            source_dir = test_images_dir / source_dir_name
            if source_dir.exists():
                for file_path in source_dir.iterdir():
                    if file_path.is_file():
                        shutil.copy2(file_path, mixed_dir)
                        copied_count += 1

        print(f"Created mixed directory '{mixed_dir_name}' with {copied_count} files from {len(single_date_dirs)} source folders")
        return mixed_dir

    def check_dng_conversion_results(self, processed_dir: Path, dir_name: str) -> None:
        """Check DNG conversion results and report any issues."""
        print(f"\n=== DNG CONVERSION ANALYSIS FOR {dir_name} ===")

        dng_dirs = []
        raw_dirs = []

        for item in processed_dir.iterdir():
            if item.is_dir():
                if "_dng" in item.name:
                    dng_dirs.append(item)
                elif any(ext in item.name for ext in ["_cr2", "_cr3", "_arw", "_raf", "_nef"]):
                    raw_dirs.append(item)

        print(f"Found {len(raw_dirs)} RAW directories and {len(dng_dirs)} DNG directories")

        for raw_dir in raw_dirs:
            raw_files = [f for f in raw_dir.iterdir() if f.is_file()]
            corresponding_dng = processed_dir / raw_dir.name.replace(raw_dir.name.split("_")[-1], "dng")

            print(f"\nRAW Directory: {raw_dir.name}")
            print(f"  - RAW files: {len(raw_files)}")
            for raw_file in raw_files:
                print(f"    - {raw_file.name} ({raw_file.stat().st_size} bytes)")

            if corresponding_dng.exists():
                dng_files = [f for f in corresponding_dng.iterdir() if f.is_file()]
                print(f"  - Corresponding DNG directory: {corresponding_dng.name}")
                print(f"  - DNG files: {len(dng_files)}")
                for dng_file in dng_files:
                    print(f"    - {dng_file.name} ({dng_file.stat().st_size} bytes)")

                if len(dng_files) == 0:
                    print(f"  WARNING: DNG directory {corresponding_dng.name} is EMPTY!")
                    print(f"           Expected {len(raw_files)} DNG files but found 0")
                elif len(dng_files) != len(raw_files):
                    print("  WARNING: File count mismatch!")
                    print(f"           RAW files: {len(raw_files)}, DNG files: {len(dng_files)}")
                else:
                    print(f"  SUCCESS: {len(dng_files)} DNG files created successfully")
            else:
                print("  ERROR: No corresponding DNG directory found!")

        print("=== END DNG CONVERSION ANALYSIS ===\n")

    def get_single_date_directories(self, test_images_dir: Path) -> list[str]:
        """Discover all single-date format directories (YYYYMMDD_* pattern)."""
        single_date_dirs = []
        for item in test_images_dir.iterdir():
            # Look for directories that match single date pattern (YYYYMMDD_*)
            # Must start with 8 digits followed by underscore
            if item.is_dir() and len(item.name) >= 9 and item.name[8] == "_" and item.name[:8].isdigit():
                single_date_dirs.append(item.name)
        return sorted(single_date_dirs)

    def test_single_date_directories(self, eir_binary, test_images_dir, temp_workspace):
        """Test processing of single-date format directories."""
        # Dynamically discover single-date directories
        single_date_dirs = self.get_single_date_directories(test_images_dir)

        if not single_date_dirs:
            pytest.skip("No single-date format directories found in test_images")

        print(f"Found {len(single_date_dirs)} single-date directories: {single_date_dirs}")
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

                # Directory structure will be shown after all tests complete

                if exit_code == 0:
                    # Show directory structure before analysis
                    self.show_directory_tree(test_dir, f"Directory structure after processing {dir_name}")

                    # Check for empty DNG directories and report
                    self.check_dng_conversion_results(test_dir, dir_name)

                    # Analyze results
                    results[dir_name] = self.analyze_processing_results(test_dir, dir_name)
                    results[dir_name]["original_count"] = original_count
                    results[dir_name]["success"] = True
                else:
                    error_msg = getattr(self, "_last_error", f"Binary exited with code {exit_code}")
                    results[dir_name] = {"success": False, "error": error_msg, "original_count": original_count}

            except Exception as e:
                results[dir_name] = {"success": False, "error": str(e), "original_count": original_count}

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

            # Directory structure will be shown after all tests complete

            if exit_code == 0:
                # Show directory structure before analysis
                self.show_directory_tree(mixed_dir, "Directory structure after processing mixed date range")

                # Check for empty DNG directories and report
                self.check_dng_conversion_results(mixed_dir, mixed_dir.name)

                # Analyze results
                results = self.analyze_processing_results(mixed_dir, mixed_dir.name)
                results["original_count"] = original_count
                results["success"] = True

                # Verify date range processing
                self.verify_date_range_results(results)
            else:
                error_msg = getattr(self, "_last_error", f"binary exited with code {exit_code}")
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
        assert len(successful_dirs) > 0, f"No directories processed successfully. Failures: {failed_dirs}"

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
            for subdir, files in result["files_by_subdirectory"].items():
                numbered_files = [f for f in files if "_001" in f or "_002" in f or "_003" in f]
                # Allow empty directories (e.g., after DNG conversion)
                if len(files) > 0:
                    assert len(numbered_files) > 0, f"No sequential numbering found in {subdir}. Files: {files}"

    def verify_date_range_results(self, results: dict):
        """Verify results from date range directory processing."""
        # Should have processed files
        assert results["total_processed_files"] > 0, "No files processed in mixed directory"

        # Should have created subdirectories
        assert len(results["subdirectories"]) > 0, "No subdirectories created"

        # Should have both EXIF success and fallback patterns since we have various image types
        patterns = results["file_naming_patterns"]
        assert len(patterns) > 0, "No naming patterns detected"

        # Verify that files have proper sequential numbering (where files exist)
        for subdir, files in results["files_by_subdirectory"].items():
            if len(files) > 0:  # Only check directories that have files
                numbered_files = [f for f in files if "_001" in f or "_002" in f or "_003" in f]
                assert len(numbered_files) > 0, f"No sequential numbering found in {subdir}. Files: {files}"

    def get_camera_brand_from_dirname(self, dir_name: str) -> str:
        """Extract expected camera brand from directory name."""
        name_lower = dir_name.lower()
        if "canon" in name_lower:
            return "canon"
        elif "sony" in name_lower:
            return "sony"
        elif "fujifilm" in name_lower or "fuji" in name_lower:
            return "fujifilm"
        elif "leica" in name_lower:
            return "leica"
        elif "iphone" in name_lower or "apple" in name_lower:
            return "apple"
        elif "nikon" in name_lower:
            return "nikon"
        else:
            return "unknown"

    def test_camera_brand_organization(self, eir_binary, test_images_dir, temp_workspace):
        """Test that different camera brands are organized correctly."""
        # Dynamically test all single-date directories for camera brand detection
        single_date_dirs = self.get_single_date_directories(test_images_dir)

        if not single_date_dirs:
            pytest.skip("No single-date directories found for camera brand testing")

        print(f"Testing camera brand organization for {len(single_date_dirs)} directories")

        for dir_name in single_date_dirs:
            expected_brand = self.get_camera_brand_from_dirname(dir_name)
            if expected_brand == "unknown":
                continue  # Skip directories where we can't determine expected brand
            source_dir = test_images_dir / dir_name
            if not source_dir.exists():
                continue

            test_dir = self.copy_test_directory(source_dir, temp_workspace)

            # Run eir binary on the test directory
            exit_code = self.run_eir_binary(eir_binary, test_dir)

            # Directory structure will be shown after all tests complete

            if exit_code == 0:
                # Show directory structure before analysis
                self.show_directory_tree(test_dir, f"Camera brand organization for {dir_name}")

                # Check for empty DNG directories and report
                self.check_dng_conversion_results(test_dir, dir_name)
            else:
                error_msg = getattr(self, "_last_error", f"Binary failed with exit code {exit_code}")
                raise AssertionError(error_msg)

            # Check that subdirectories contain expected camera brand
            created_dirs = [d.name for d in test_dir.iterdir() if d.is_dir()]
            brand_dirs = [d for d in created_dirs if expected_brand in d.lower()]
            assert len(brand_dirs) > 0, (
                f"No {expected_brand} directories found in {dir_name}. Expected brand: {expected_brand}, Created: {created_dirs}"
            )

    def find_directory_with_multiple_file_types(self, test_images_dir: Path) -> Path | None:
        """Find a directory that contains both RAW and regular image files."""
        single_date_dirs = self.get_single_date_directories(test_images_dir)

        for dir_name in single_date_dirs:
            source_dir = test_images_dir / dir_name
            if not source_dir.exists():
                continue

            files = list(source_dir.iterdir())
            if not files:
                continue

            # Check for RAW files
            raw_extensions = {".arw", ".cr2", ".cr3", ".nef", ".raf", ".dng"}
            regular_extensions = {".jpg", ".jpeg", ".heic", ".png", ".tiff"}

            file_extensions = {f.suffix.lower() for f in files if f.is_file()}
            has_raw = bool(file_extensions & raw_extensions)
            has_regular = bool(file_extensions & regular_extensions)

            if has_raw and has_regular:
                return source_dir

        # If no directory has both, return the first directory with RAW files
        for dir_name in single_date_dirs:
            source_dir = test_images_dir / dir_name
            if source_dir.exists():
                files = list(source_dir.iterdir())
                file_extensions = {f.suffix.lower() for f in files if f.is_file()}
                if file_extensions & raw_extensions:
                    return source_dir

        return None

    def test_file_type_processing(self, eir_binary, test_images_dir, temp_workspace):
        """Test that different file types (RAW, compressed) are processed correctly."""
        # Find a directory with multiple file types for testing
        source_dir = self.find_directory_with_multiple_file_types(test_images_dir)

        if source_dir:
            test_dir = self.copy_test_directory(source_dir, temp_workspace)

            # Run eir binary on the test directory
            exit_code = self.run_eir_binary(eir_binary, test_dir)

            if exit_code == 0:
                # Show directory structure before analysis
                self.show_directory_tree(test_dir, "File type processing results (RAW + compressed)")

                # Check for empty DNG directories and report
                self.check_dng_conversion_results(test_dir, source_dir.name)
            else:
                error_msg = getattr(self, "_last_error", f"Binary failed with exit code {exit_code}")
                raise AssertionError(error_msg)

            # Verify that appropriate directories were created based on file types
            created_dirs = [d.name for d in test_dir.iterdir() if d.is_dir()]
            print(f"File type processing test - created directories: {created_dirs}")

            # Should have at least one directory (files were processed)
            assert len(created_dirs) > 0, f"No directories created for {source_dir.name}"
        else:
            pytest.skip("No directory with multiple file types found for file type processing test")
