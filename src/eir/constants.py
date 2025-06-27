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
        # First, check if we're in a PyInstaller bundle (backward compatibility)
        if hasattr(sys, "_MEIPASS"):
            bundle_dir = Path(sys._MEIPASS)
            if (bundle_dir / "pyproject.toml").exists():
                return bundle_dir

        # Check if we're in a Nuitka bundle - improved detection
        current_file_path = Path(__file__).absolute()
        current_path_str = str(current_file_path).lower()
        is_nuitka_onefile = (
            "onefile" in current_path_str
            or "onefil" in current_path_str  # Windows short names like ONEFIL~1
        )
        is_frozen = getattr(sys, "frozen", False)

        if is_frozen or is_nuitka_onefile:
            # For bundled executables, try to find bundled files
            current_file_dir = Path(__file__).parent

            # Simple check - look in current directory and up to 3 parent levels
            for level in range(4):
                check_dir = current_file_dir
                for _ in range(level):
                    check_dir = check_dir.parent
                    if check_dir.parent == check_dir:  # Reached filesystem root
                        break

                if (check_dir / "pyproject.toml").exists():
                    return check_dir

        # Fall back to normal project root search
        if start is None:
            start = Path.cwd()
        for parent in [start, *start.parents]:
            if (parent / "pyproject.toml").exists():
                return parent

        # If we can't find pyproject.toml, check if we're in a compiled environment
        # and return current directory as fallback to avoid crashes

        # Detect if we're in a compiled/bundled environment (Nuitka, PyInstaller, etc.)
        current_path = str(Path(__file__).absolute()).lower()
        # Check for various Nuitka onefile patterns (including Windows short names)
        is_nuitka_temp = (
            ("temp" in current_path and "onefil" in current_path)  # Windows: ONEFIL~1
            or ("temp" in current_path and "onefile" in current_path)  # Full name
        )
        is_compiled = (
            getattr(sys, "frozen", False)  # PyInstaller/Nuitka frozen
            or hasattr(sys, "_MEIPASS")  # PyInstaller bundle
            or "onefile" in current_path  # Nuitka onefile pattern
            or "onefil" in current_path  # Windows short name pattern
            or is_nuitka_temp  # Nuitka temp extraction
        )

        if is_compiled:
            return Path.cwd()

        raise FileNotFoundError("pyproject.toml not found")

    def _load_from_pyproject(self):
        try:
            root = self._find_project_root()
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
