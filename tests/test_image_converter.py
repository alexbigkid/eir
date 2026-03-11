"""Tests for the image_converter script."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import image_converter


class TestConvertFormat:
    """Test ConvertFormat enum."""

    def test_all_formats_have_dot_prefix(self):
        """All format values start with a dot."""
        for fmt in image_converter.ConvertFormat:
            assert fmt.value.startswith(".")

    def test_expected_formats_exist(self):
        """All expected formats are defined."""
        expected = {".dng", ".heic", ".heif", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
        actual = {fmt.value for fmt in image_converter.ConvertFormat}
        assert actual == expected


class TestCollectConvertibleFiles:
    """Test collect_convertible_files function."""

    def test_collects_supported_files(self, tmp_path):
        """Collects files with supported extensions."""
        (tmp_path / "photo.jpg").write_bytes(b"fake")
        (tmp_path / "image.png").write_bytes(b"fake")
        (tmp_path / "raw.dng").write_bytes(b"fake")
        (tmp_path / "readme.txt").write_bytes(b"fake")

        result = image_converter.collect_convertible_files(tmp_path)

        names = [f.name for f in result]
        assert "photo.jpg" in names
        assert "image.png" in names
        assert "raw.dng" in names
        assert "readme.txt" not in names

    def test_excludes_hidden_files(self, tmp_path):
        """Hidden files are excluded."""
        (tmp_path / ".hidden.jpg").write_bytes(b"fake")
        (tmp_path / "visible.jpg").write_bytes(b"fake")

        result = image_converter.collect_convertible_files(tmp_path)

        names = [f.name for f in result]
        assert ".hidden.jpg" not in names
        assert "visible.jpg" in names

    def test_excludes_directories(self, tmp_path):
        """Directories are excluded even if named with image extension."""
        (tmp_path / "subdir.jpg").mkdir()
        (tmp_path / "real.jpg").write_bytes(b"fake")

        result = image_converter.collect_convertible_files(tmp_path)

        assert len(result) == 1
        assert result[0].name == "real.jpg"

    def test_returns_sorted(self, tmp_path):
        """Results are sorted by name."""
        (tmp_path / "c.jpg").write_bytes(b"fake")
        (tmp_path / "a.jpg").write_bytes(b"fake")
        (tmp_path / "b.jpg").write_bytes(b"fake")

        result = image_converter.collect_convertible_files(tmp_path)

        assert [f.name for f in result] == ["a.jpg", "b.jpg", "c.jpg"]

    def test_empty_directory(self, tmp_path):
        """Empty directory returns empty list."""
        result = image_converter.collect_convertible_files(tmp_path)
        assert result == []

    def test_case_insensitive_extensions(self, tmp_path):
        """Extensions are matched case-insensitively."""
        (tmp_path / "photo.JPG").write_bytes(b"fake")
        (tmp_path / "image.Png").write_bytes(b"fake")

        result = image_converter.collect_convertible_files(tmp_path)

        assert len(result) == 2


class TestExtractAndSortByDate:
    """Test extract_and_sort_by_date function."""

    @patch("image_converter.exiftool.ExifToolHelper")
    def test_sorts_by_exif_date(self, mock_exiftool_cls, tmp_path):
        """Files are sorted by EXIF date, earliest first."""
        file_a = tmp_path / "a.jpg"
        file_b = tmp_path / "b.jpg"
        file_a.write_bytes(b"fake")
        file_b.write_bytes(b"fake")

        mock_instance = MagicMock()
        mock_exiftool_cls.return_value.__enter__.return_value = mock_instance
        mock_instance.get_tags.return_value = [
            {"SourceFile": str(file_a), "EXIF:CreateDate": "2024:06:15 10:00:00"},
            {"SourceFile": str(file_b), "EXIF:CreateDate": "2024:01:01 08:00:00"},
        ]

        result = image_converter.extract_and_sort_by_date([file_a, file_b])

        assert result[0][0] == file_b
        assert result[1][0] == file_a

    @patch("image_converter.exiftool.ExifToolHelper")
    def test_falls_back_to_mtime(self, mock_exiftool_cls, tmp_path):
        """Falls back to file modification time when no EXIF date."""
        file_a = tmp_path / "a.jpg"
        file_a.write_bytes(b"fake")

        mock_instance = MagicMock()
        mock_exiftool_cls.return_value.__enter__.return_value = mock_instance
        mock_instance.get_tags.return_value = [{"SourceFile": str(file_a), "EXIF:CreateDate": ""}]

        result = image_converter.extract_and_sort_by_date([file_a])

        assert len(result) == 1
        assert result[0][0] == file_a
        assert isinstance(result[0][1], datetime)

    @patch("image_converter.exiftool.ExifToolHelper")
    def test_handles_invalid_exif_date(self, mock_exiftool_cls, tmp_path):
        """Falls back to mtime on invalid EXIF date format."""
        file_a = tmp_path / "a.jpg"
        file_a.write_bytes(b"fake")

        mock_instance = MagicMock()
        mock_exiftool_cls.return_value.__enter__.return_value = mock_instance
        mock_instance.get_tags.return_value = [{"SourceFile": str(file_a), "EXIF:CreateDate": "not-a-date"}]

        result = image_converter.extract_and_sort_by_date([file_a])

        assert len(result) == 1

    def test_empty_list(self):
        """Empty input returns empty output."""
        assert image_converter.extract_and_sort_by_date([]) == []


class TestGenerateOutputName:
    """Test generate_output_name function."""

    def test_basic_output_name(self, tmp_path):
        """Generates correct output filename."""
        output_dir = tmp_path / "MyHouse"
        dt = datetime(2024, 1, 15, 14, 30, 0)

        result = image_converter.generate_output_name(output_dir, 1, dt)

        assert result == output_dir / "20240115_143000_MyHouse_001.jpg"

    def test_counter_padding(self, tmp_path):
        """Counter is zero-padded to 3 digits."""
        output_dir = tmp_path / "Apt"
        dt = datetime(2024, 6, 1, 9, 0, 0)

        result = image_converter.generate_output_name(output_dir, 42, dt)

        assert result.name == "20240601_090000_Apt_042.jpg"

    def test_large_counter(self, tmp_path):
        """Large counter values work correctly."""
        output_dir = tmp_path / "Place"
        dt = datetime(2024, 12, 31, 23, 59, 59)

        result = image_converter.generate_output_name(output_dir, 999, dt)

        assert result.name == "20241231_235959_Place_999.jpg"


class TestResizePreserveAspect:
    """Test resize_preserve_aspect function."""

    def test_no_resize_when_smaller(self):
        """No-op when image is smaller than max_dim."""
        img = Image.new("RGB", (1000, 500))
        result = image_converter.resize_preserve_aspect(img, 2048)
        assert result.size == (1000, 500)

    def test_no_resize_when_equal(self):
        """No-op when image matches max_dim exactly."""
        img = Image.new("RGB", (2048, 1024))
        result = image_converter.resize_preserve_aspect(img, 2048)
        assert result.size == (2048, 1024)

    def test_resize_landscape(self):
        """Landscape image resized by width."""
        img = Image.new("RGB", (4096, 2048))
        result = image_converter.resize_preserve_aspect(img, 2048)
        assert result.size == (2048, 1024)

    def test_resize_portrait(self):
        """Portrait image resized by height."""
        img = Image.new("RGB", (2048, 4096))
        result = image_converter.resize_preserve_aspect(img, 2048)
        assert result.size == (1024, 2048)

    def test_resize_square(self):
        """Square image resized correctly."""
        img = Image.new("RGB", (4000, 4000))
        result = image_converter.resize_preserve_aspect(img, 2000)
        assert result.size == (2000, 2000)

    @pytest.mark.parametrize(
        ("original", "max_dim", "expected"),
        [((6000, 4000), 2048, (2048, 1365)), ((3000, 2000), 1200, (1200, 800)), ((800, 600), 2048, (800, 600))],
    )
    def test_various_dimensions(self, original, max_dim, expected):
        """Various resize scenarios produce correct dimensions."""
        img = Image.new("RGB", original)
        result = image_converter.resize_preserve_aspect(img, max_dim)
        assert result.size == expected


class TestOpenAnyImage:
    """Test open_any_image function."""

    def test_open_jpeg(self, tmp_path):
        """Opens a JPEG file directly with Pillow."""
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (100, 100), color="red").save(img_path, "JPEG")

        result = image_converter.open_any_image(img_path)

        assert result.size == (100, 100)

    def test_open_png(self, tmp_path):
        """Opens a PNG file directly with Pillow."""
        img_path = tmp_path / "test.png"
        Image.new("RGB", (200, 100)).save(img_path, "PNG")

        result = image_converter.open_any_image(img_path)

        assert result.size == (200, 100)

    @patch("image_converter._open_dng")
    def test_dispatches_dng(self, mock_open_dng, tmp_path):
        """DNG files are dispatched to _open_dng."""
        img_path = tmp_path / "test.dng"
        img_path.write_bytes(b"fake")
        mock_open_dng.return_value = Image.new("RGB", (100, 100))

        image_converter.open_any_image(img_path)

        mock_open_dng.assert_called_once_with(img_path)

    @patch("image_converter._open_heic")
    def test_dispatches_heic(self, mock_open_heic, tmp_path):
        """HEIC files are dispatched to _open_heic."""
        img_path = tmp_path / "test.heic"
        img_path.write_bytes(b"fake")
        mock_open_heic.return_value = Image.new("RGB", (100, 100))

        image_converter.open_any_image(img_path)

        mock_open_heic.assert_called_once_with(img_path)


class TestConvertSingle:
    """Test convert_single function."""

    def test_successful_conversion(self, tmp_path):
        """Successfully converts and saves a JPEG."""
        src = tmp_path / "input.jpg"
        Image.new("RGB", (4000, 3000), color="blue").save(src, "JPEG")
        dest = tmp_path / "output" / "result.jpg"

        task = image_converter.ConversionTask(
            source=src, destination=dest, exif_date=datetime.now(), quality=85, max_dimension=2048
        )

        result = image_converter.convert_single(task)

        assert result.success is True
        assert dest.exists()
        output_img = Image.open(dest)
        assert max(output_img.size) <= 2048

    def test_converts_to_rgb(self, tmp_path):
        """RGBA images are converted to RGB."""
        src = tmp_path / "input.png"
        Image.new("RGBA", (100, 100)).save(src, "PNG")
        dest = tmp_path / "output.jpg"

        task = image_converter.ConversionTask(
            source=src, destination=dest, exif_date=datetime.now(), quality=85, max_dimension=2048
        )

        result = image_converter.convert_single(task)

        assert result.success is True
        output_img = Image.open(dest)
        assert output_img.mode == "RGB"

    def test_failed_conversion_returns_error(self, tmp_path):
        """Failed conversion returns error result."""
        src = tmp_path / "nonexistent.jpg"
        dest = tmp_path / "output.jpg"

        task = image_converter.ConversionTask(
            source=src, destination=dest, exif_date=datetime.now(), quality=85, max_dimension=2048
        )

        result = image_converter.convert_single(task)

        assert result.success is False
        assert result.error is not None


class TestConvertAll:
    """Test convert_all function."""

    def test_empty_tasks(self):
        """Empty task list returns empty results."""
        assert image_converter.convert_all([]) == []

    def test_converts_multiple_files(self, tmp_path):
        """Converts multiple files concurrently."""
        tasks = []
        for i in range(3):
            src = tmp_path / f"input_{i}.jpg"
            Image.new("RGB", (100, 100), color="green").save(src, "JPEG")
            dest = tmp_path / "output" / f"result_{i}.jpg"
            tasks.append(
                image_converter.ConversionTask(
                    source=src, destination=dest, exif_date=datetime.now(), quality=85, max_dimension=2048
                )
            )

        results = image_converter.convert_all(tasks)

        assert len(results) == 3
        assert all(r.success for r in results)


class TestRun:
    """Test run function."""

    @patch("image_converter.convert_all")
    @patch("image_converter.extract_and_sort_by_date")
    @patch("image_converter.collect_convertible_files")
    def test_no_files_found(self, mock_collect, mock_extract, mock_convert, tmp_path):
        """Exits early when no convertible files found."""
        mock_collect.return_value = []

        image_converter.run(tmp_path, tmp_path / "out")

        mock_extract.assert_not_called()
        mock_convert.assert_not_called()

    @patch("image_converter.convert_all")
    @patch("image_converter.extract_and_sort_by_date")
    @patch("image_converter.collect_convertible_files")
    def test_builds_tasks_and_converts(self, mock_collect, mock_extract, mock_convert, tmp_path):
        """Builds conversion tasks from sorted files and converts them."""
        file_a = tmp_path / "a.jpg"
        file_a.write_bytes(b"fake")
        dt = datetime(2024, 1, 1, 12, 0, 0)

        mock_collect.return_value = [file_a]
        mock_extract.return_value = [(file_a, dt)]
        mock_convert.return_value = [
            image_converter.ConversionResult(source=file_a, destination=tmp_path / "out" / "x.jpg", success=True)
        ]

        output_dir = tmp_path / "out"
        image_converter.run(tmp_path, output_dir)

        mock_convert.assert_called_once()
        tasks = mock_convert.call_args[0][0]
        assert len(tasks) == 1
        assert tasks[0].source == file_a
        assert tasks[0].quality == 85
        assert tasks[0].max_dimension == 2048
