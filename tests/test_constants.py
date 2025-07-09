"""Tests for constants.py module."""

import pytest
from unittest.mock import patch
from pathlib import Path

from eir.constants import _Const, CONST


class TestConst:
    """Test the _Const class."""

    def test_init_with_package_found(self):
        """Test initialization when package is found."""
        with (
            patch("eir.constants.get_version", return_value="1.0.0"),
            patch.object(_Const, "_load_from_pyproject", return_value=None),
            patch.object(_Const, "_load_from_build_constants", return_value=None),
        ):
            const = _Const()
            assert const.VERSION == "1.0.0"
            assert const.NAME == "eir"

    def test_init_with_package_not_found(self):
        """Test initialization when package is not found."""
        from importlib.metadata import PackageNotFoundError

        with (
            patch("eir.constants.get_version", side_effect=PackageNotFoundError),
            patch.object(_Const, "_load_from_pyproject", return_value=None),
            patch.object(_Const, "_load_from_build_constants", return_value=None),
        ):
            const = _Const()
            assert const.VERSION == "0.0.0-dev"
            assert const.NAME == "unknown"

    def test_default_values(self):
        """Test default values are set correctly."""
        from importlib.metadata import PackageNotFoundError

        with (
            patch("eir.constants.get_version", side_effect=PackageNotFoundError("Package not found")),
            patch.object(_Const, "_load_from_pyproject", return_value=None),
            patch.object(_Const, "_load_from_build_constants", return_value=None),
        ):
            const = _Const()
            assert const.LICENSE == "unknown"
            assert const.KEYWORDS == ["unknown"]
            assert const.AUTHORS == [{"name": "ABK", "email": "unknown"}]
            assert const.MAINTAINERS == [{"name": "ABK", "email": "unknown"}]

    def test_find_project_root_success(self, project_root_dir):
        """Test finding project root successfully."""
        const = _Const()

        # Create a subdirectory to test searching upward
        sub_dir = project_root_dir / "subdir" / "deeper"
        sub_dir.mkdir(parents=True)

        root = const._find_project_root(sub_dir)
        assert root == project_root_dir
        assert (root / "pyproject.toml").exists()

    def test_find_project_root_not_found(self, temp_dir):
        """Test finding project root when pyproject.toml doesn't exist - returns fallback."""
        const = _Const()

        # Should return the fallback directory (current working directory)
        result = const._find_project_root(temp_dir)
        assert isinstance(result, Path)
        # Should return the current working directory as fallback
        assert result == Path.cwd()

    def test_find_project_root_none_start(self):
        """Test finding project root with None start parameter - returns fallback."""
        const = _Const()

        with patch("eir.constants.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/nonexistent")
            # Should return the current working directory as fallback
            result = const._find_project_root(None)
            assert result == Path("/nonexistent")
            mock_cwd.assert_called()

    def test_load_from_pyproject_success(self, project_root_dir):
        """Test loading from pyproject.toml successfully."""
        with (
            patch.object(_Const, "_find_normal_project_root", return_value=project_root_dir),
            patch.object(_Const, "_load_from_build_constants", return_value=None),
        ):
            const = _Const()

            assert const.NAME == "eir"
            assert const.VERSION == "0.1.0"
            assert const.LICENSE == "MIT"
            assert const.KEYWORDS == ["image", "processing", "exif"]
            assert const.AUTHORS == [{"name": "Test Author", "email": "test@example.com"}]
            assert const.MAINTAINERS == [{"name": "Test Maintainer", "email": "maintainer@example.com"}]

    def test_load_from_pyproject_file_not_found(self, temp_dir):
        """Test loading when pyproject.toml doesn't exist."""
        with patch.object(_Const, "_find_normal_project_root", return_value=temp_dir), patch("builtins.print") as mock_print:
            _Const()
            # Should fall back to defaults and print warning
            mock_print.assert_called_once()
            assert "Warning: failed to load pyproject.toml metadata" in str(mock_print.call_args[0][0])

    def test_load_from_pyproject_malformed_toml(self, project_root_dir):
        """Test loading with malformed TOML file."""
        # Create malformed pyproject.toml
        malformed_toml = project_root_dir / "pyproject.toml"
        malformed_toml.write_text('[project\nname = "invalid')  # Missing closing bracket and quote

        with (
            patch.object(_Const, "_find_normal_project_root", return_value=project_root_dir),
            patch("builtins.print") as mock_print,
        ):
            _Const()
            mock_print.assert_called_once()
            assert "Warning: failed to load pyproject.toml metadata" in str(mock_print.call_args[0][0])

    def test_properties_return_correct_values(self):
        """Test that all properties return the expected values."""
        with (
            patch("eir.constants.get_version", return_value="2.0.0"),
            patch.object(_Const, "_load_from_pyproject", return_value=None),
            patch.object(_Const, "_load_from_build_constants", return_value=None),
        ):
            const = _Const()
            # Use object.__setattr__ to bypass read-only protection for testing
            object.__setattr__(const, "_name", "test_name")
            object.__setattr__(const, "_license", {"text": "GPL"})
            object.__setattr__(const, "_keywords", ["test", "keywords"])
            object.__setattr__(const, "_authors", [{"name": "Author", "email": "author@test.com"}])
            object.__setattr__(const, "_maintainers", [{"name": "Maintainer", "email": "maint@test.com"}])

            assert const.VERSION == "2.0.0"
            assert const.NAME == "test_name"
            assert const.LICENSE == "GPL"
            assert const.KEYWORDS == ["test", "keywords"]
            assert const.AUTHORS == [{"name": "Author", "email": "author@test.com"}]
            assert const.MAINTAINERS == [{"name": "Maintainer", "email": "maint@test.com"}]

    def test_license_property_fallback(self):
        """Test LICENSE property fallback when license doesn't have text."""
        with patch.object(_Const, "_load_from_pyproject", return_value=None):
            const = _Const()
            object.__setattr__(const, "_license", {})  # No 'text' key
            assert const.LICENSE == "unknown"

    def test_setattr_read_only(self):
        """Test that existing attributes cannot be modified."""
        with patch.object(_Const, "_load_from_pyproject", return_value=None):
            const = _Const()
            # First set the attribute properly
            object.__setattr__(const, "_version", "1.0.0")

            # Now test that it can't be modified
            with pytest.raises(AttributeError, match="_version is read-only"):
                const._version = "2.0.0"

    def test_setattr_new_attribute(self):
        """Test that new attributes can be set."""
        const = _Const()
        const.new_attribute = "test_value"
        assert const.new_attribute == "test_value"


class TestCONSTSingleton:
    """Test the CONST singleton instance."""

    def test_const_is_instance_of_const_class(self):
        """Test that CONST is an instance of _Const."""
        assert isinstance(CONST, _Const)

    def test_const_properties_accessible(self):
        """Test that CONST properties are accessible."""
        # These should not raise exceptions
        assert isinstance(CONST.VERSION, str)
        assert isinstance(CONST.NAME, str)
        assert isinstance(CONST.LICENSE, str)
        assert isinstance(CONST.KEYWORDS, list)
        assert isinstance(CONST.AUTHORS, list)
        assert isinstance(CONST.MAINTAINERS, list)

    def test_const_singleton_behavior(self):
        """Test that CONST behaves like a singleton (though it's just a module-level instance)."""
        from eir.constants import CONST as CONST2

        assert CONST is CONST2


class TestRealProjectFile:
    """Test loading from the actual project file."""

    def test_loads_actual_project_metadata(self):
        """Test that it can load from the real pyproject.toml file."""
        # This test uses the actual project file
        const = _Const()

        # Basic checks - these should match the actual project
        assert const.NAME == "eir"
        assert isinstance(const.VERSION, str)
        assert len(const.VERSION) > 0
        assert isinstance(const.AUTHORS, list)
        assert len(const.AUTHORS) > 0
