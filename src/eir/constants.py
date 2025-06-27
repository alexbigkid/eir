"""Constants for the eir package."""

from pathlib import Path
from importlib.metadata import version as get_version, PackageNotFoundError
import tomllib
import sys


class _Const:
    """Constants class."""

    _version: str
    _name: str
    _license: dict
    _keywords: list[str]
    _authors: list[dict]
    _maintainers: list[dict]

    def __init__(self):
        # Try to get version from importlib.metadata first
        try:
            self._version = get_version("eir")
            self._name = "eir"
        except PackageNotFoundError:
            self._version = "0.0.0-dev"
            self._name = "unknown"

        # Set defaults
        self._license = {"text": "unknown"}
        self._keywords = ["unknown"]
        self._authors = [{"name": "ABK", "email": "unknown"}]
        self._maintainers = [{"name": "ABK", "email": "unknown"}]

        # Try to load from pyproject.toml (development)
        self._load_from_pyproject()

        # Try to load from build constants (bundled executable)
        self._load_from_build_constants()

    def _find_project_root(self, start: Path | None = None) -> Path:
        # Skip bundled detection entirely during tests to prevent hanging
        if "pytest" in sys.modules:
            return self._find_normal_project_root(start)

        # First, check if we're in a PyInstaller bundle (backward compatibility)
        if hasattr(sys, "_MEIPASS"):
            bundle_dir = Path(sys._MEIPASS)
            if (bundle_dir / "pyproject.toml").exists():
                return bundle_dir

        # Simple Nuitka onefile detection - only check if we're clearly in a bundled environment
        current_file_path = Path(__file__).absolute()
        current_path_str = str(current_file_path).lower()
        is_onefile = (
            "onefile" in current_path_str
            or "onefil" in current_path_str  # Windows short names like ONEFIL~1
        )
        if is_onefile or getattr(sys, "frozen", False):
            # For Nuitka bundles, try just the parent directories - simple and fast
            current_dir = Path(__file__).parent
            for _level in range(4):  # Check up to 4 levels up
                if (current_dir / "pyproject.toml").exists():
                    return current_dir
                parent = current_dir.parent
                if parent == current_dir:  # Reached root
                    break
                current_dir = parent

        # Fall back to normal search (like original PyInstaller version)
        return self._find_normal_project_root(start)

    def _find_normal_project_root(self, start: Path | None = None) -> Path:
        """Normal project root search without bundled environment detection."""
        # Fall back to normal project root search
        if start is None:
            start = Path.cwd()
        for parent in [start, *start.parents]:
            if (parent / "pyproject.toml").exists():
                return parent

        # Fallback: return current working directory if nothing found
        return Path.cwd()

    def _load_from_pyproject(self):
        try:
            root = self._find_normal_project_root()
            pyproject_path = root / "pyproject.toml"

            with pyproject_path.open("rb") as f:
                project = tomllib.load(f).get("project", {})
                object.__setattr__(self, "_version", project.get("version", self._version))
                object.__setattr__(self, "_name", project.get("name", self._name))
                object.__setattr__(self, "_license", project.get("license", self._license))
                object.__setattr__(self, "_keywords", project.get("keywords", self._keywords))
                object.__setattr__(self, "_authors", project.get("authors", self._authors))
                object.__setattr__(
                    self, "_maintainers", project.get("maintainers", self._maintainers)
                )
        except Exception as e:
            print(f"Warning: failed to load pyproject.toml metadata: {e}")

    def _load_from_build_constants(self):
        """Load constants from build-time generated file."""
        try:
            from eir import build_constants  # type: ignore

            object.__setattr__(self, "_version", build_constants.VERSION)
            object.__setattr__(self, "_name", build_constants.NAME)
            object.__setattr__(self, "_license", {"text": build_constants.LICENSE})
            object.__setattr__(self, "_keywords", build_constants.KEYWORDS)
            object.__setattr__(self, "_authors", build_constants.AUTHORS)
            object.__setattr__(self, "_maintainers", build_constants.MAINTAINERS)
        except ImportError:
            # build_constants.py not found - use hardcoded fallback for bundled executable
            # (PyInstaller compatibility)
            if hasattr(sys, "_MEIPASS"):
                object.__setattr__(self, "_version", "XX.XX.XX")
                object.__setattr__(self, "_name", "eir")
                object.__setattr__(self, "_license", {"text": "MIT"})
                object.__setattr__(
                    self,
                    "_keywords",
                    [
                        "exif",
                        "images",
                        "photos",
                        "rename",
                        "convert",
                        "raw",
                        "dng",
                        "photography",
                    ],
                )
                object.__setattr__(
                    self,
                    "_authors",
                    [{"name": "ABK", "email": "alexbigkid@users.noreply.github.com"}],
                )
                object.__setattr__(
                    self,
                    "_maintainers",
                    [{"name": "ABK", "email": "alexbigkid@users.noreply.github.com"}],
                )
        except Exception as e:
            print(f"Warning: failed to load build constants: {e}")

    @property
    def VERSION(self) -> str:
        return self._version

    @property
    def NAME(self) -> str:
        return self._name

    @property
    def LICENSE(self) -> str:
        return self._license.get("text", "unknown")

    @property
    def KEYWORDS(self) -> list[str]:
        return self._keywords

    @property
    def AUTHORS(self) -> list[dict]:
        return self._authors

    @property
    def MAINTAINERS(self) -> list[dict]:
        return self._maintainers

    def __setattr__(self, key, value):
        if hasattr(self, key):
            raise AttributeError(f"{key} is read-only")
        super().__setattr__(key, value)


CONST = _Const()
