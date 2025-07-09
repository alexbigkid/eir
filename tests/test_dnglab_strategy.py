"""Tests for DNGLab strategy pattern implementation."""

from unittest.mock import Mock, patch


from eir.dnglab_strategy import (
    DNGLabStrategyFactory,
    LinuxDNGLabStrategy,
    MacOSAdobeDNGStrategy,
    MacOSDNGLabStrategy,
    WindowsDNGLabStrategy,
)


class TestDNGLabStrategyFactory:
    """Test cases for DNGLabStrategyFactory."""

    @patch("platform.system")
    def test_create_linux_strategy(self, mock_system):
        """Test factory creates Linux strategy for Linux platform."""
        mock_system.return_value = "Linux"
        mock_logger = Mock()

        strategy = DNGLabStrategyFactory.create_strategy(mock_logger)

        assert isinstance(strategy, LinuxDNGLabStrategy)
        assert strategy.logger is mock_logger

    @patch("platform.system")
    def test_create_windows_strategy(self, mock_system):
        """Test factory creates Windows strategy for Windows platform."""
        mock_system.return_value = "Windows"
        mock_logger = Mock()

        strategy = DNGLabStrategyFactory.create_strategy(mock_logger)

        assert isinstance(strategy, WindowsDNGLabStrategy)
        assert strategy.logger is mock_logger

    @patch("platform.system")
    def test_create_macos_strategy_adobe_preferred(self, mock_system):
        """Test factory creates Adobe DNG strategy for Darwin platform when available."""
        mock_system.return_value = "Darwin"
        mock_logger = Mock()

        # This will actually test with the real system - if Adobe DNG Converter is available
        # it will return MacOSAdobeDNGStrategy, otherwise MacOSDNGLabStrategy
        strategy = DNGLabStrategyFactory.create_strategy(mock_logger)

        # Should be either Adobe (preferred) or DNGLab (fallback) strategy
        assert isinstance(strategy, (MacOSAdobeDNGStrategy, MacOSDNGLabStrategy))
        assert strategy.logger is mock_logger

    @patch("platform.system")
    def test_create_unknown_platform_strategy(self, mock_system):
        """Test factory defaults to Linux strategy for unknown platforms."""
        mock_system.return_value = "UnknownOS"
        mock_logger = Mock()

        strategy = DNGLabStrategyFactory.create_strategy(mock_logger)

        assert isinstance(strategy, LinuxDNGLabStrategy)
        mock_logger.warning.assert_called_once_with("Unknown platform: unknownos, using Linux strategy")


class TestLinuxDNGLabStrategy:
    """Test cases for LinuxDNGLabStrategy."""

    def test_architecture_mapping_x86_64(self):
        """Test x86_64 architecture mapping for Linux."""
        mock_logger = Mock()
        strategy = LinuxDNGLabStrategy(mock_logger)

        with patch("platform.machine", return_value="x86_64"):
            arch = strategy.get_architecture_mapping()

        assert arch == "x64"

    def test_architecture_mapping_arm64(self):
        """Test ARM64 architecture mapping for Linux."""
        mock_logger = Mock()
        strategy = LinuxDNGLabStrategy(mock_logger)

        with patch("platform.machine", return_value="aarch64"):
            arch = strategy.get_architecture_mapping()

        assert arch == "aarch64"

    def test_binary_filename(self):
        """Test Linux binary filename."""
        mock_logger = Mock()
        strategy = LinuxDNGLabStrategy(mock_logger)

        filename = strategy.get_binary_filename()

        assert filename == "dnglab"


class TestWindowsDNGLabStrategy:
    """Test cases for WindowsDNGLabStrategy."""

    def test_architecture_mapping_x64(self):
        """Test x64 architecture mapping for Windows."""
        mock_logger = Mock()
        strategy = WindowsDNGLabStrategy(mock_logger)

        with patch("platform.machine", return_value="AMD64"):
            arch = strategy.get_architecture_mapping()

        assert arch == "x64"

    def test_architecture_mapping_arm64(self):
        """Test ARM64 architecture mapping for Windows."""
        mock_logger = Mock()
        strategy = WindowsDNGLabStrategy(mock_logger)

        with patch("platform.machine", return_value="arm64"):
            arch = strategy.get_architecture_mapping()

        assert arch == "arm64"

    def test_binary_filename(self):
        """Test Windows binary filename."""
        mock_logger = Mock()
        strategy = WindowsDNGLabStrategy(mock_logger)

        filename = strategy.get_binary_filename()

        assert filename == "dnglab.exe"


class TestMacOSDNGLabStrategy:
    """Test cases for MacOSDNGLabStrategy."""

    def test_architecture_mapping_x86_64(self):
        """Test x86_64 architecture mapping for macOS."""
        mock_logger = Mock()
        strategy = MacOSDNGLabStrategy(mock_logger)

        with patch("platform.machine", return_value="x86_64"):
            arch = strategy.get_architecture_mapping()

        assert arch == "x86_64"

    def test_architecture_mapping_arm64(self):
        """Test ARM64 architecture mapping for macOS."""
        mock_logger = Mock()
        strategy = MacOSDNGLabStrategy(mock_logger)

        with patch("platform.machine", return_value="arm64"):
            arch = strategy.get_architecture_mapping()

        assert arch == "arm64"

    def test_binary_filename(self):
        """Test macOS binary filename."""
        mock_logger = Mock()
        strategy = MacOSDNGLabStrategy(mock_logger)

        filename = strategy.get_binary_filename()

        assert filename == "dnglab"


class TestMacOSAdobeDNGStrategy:
    """Test cases for MacOSAdobeDNGStrategy."""

    def test_architecture_mapping(self):
        """Test architecture mapping for Adobe DNG Converter."""
        mock_logger = Mock()
        strategy = MacOSAdobeDNGStrategy(mock_logger)

        arch = strategy.get_architecture_mapping()

        assert arch == "universal"

    def test_binary_filename(self):
        """Test Adobe DNG Converter binary filename."""
        mock_logger = Mock()
        strategy = MacOSAdobeDNGStrategy(mock_logger)

        filename = strategy.get_binary_filename()

        assert filename == "Adobe DNG Converter"

    @patch("pathlib.Path.exists")
    def test_get_binary_path_applications_directory(self, mock_exists):
        """Test finding Adobe DNG Converter in Applications directory."""
        mock_logger = Mock()
        strategy = MacOSAdobeDNGStrategy(mock_logger)

        # Mock that only the Applications path exists
        mock_exists.return_value = True

        binary_path = strategy.get_binary_path()

        assert binary_path == "/Applications/Adobe DNG Converter.app/Contents/MacOS/Adobe DNG Converter"

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_get_binary_path_homebrew_fallback(self, mock_exists, mock_subprocess):
        """Test finding Adobe DNG Converter via Homebrew when not in Applications."""
        mock_logger = Mock()
        strategy = MacOSAdobeDNGStrategy(mock_logger)

        # Mock that Applications path doesn't exist but Homebrew paths do
        mock_exists.return_value = False

        # Mock successful homebrew commands
        mock_subprocess.side_effect = [
            Mock(returncode=0),  # brew list adobe-dng-converter succeeds
            Mock(returncode=0, stdout="/opt/homebrew\n"),  # brew --prefix succeeds
        ]

        with patch("pathlib.Path.iterdir") as mock_iterdir:
            # Mock version directory structure
            version_dir = Mock()
            version_dir.is_dir.return_value = True
            version_dir.__truediv__ = lambda self, other: Mock(exists=lambda: True)
            mock_iterdir.return_value = [version_dir]

            strategy.get_binary_path()

        # Should attempt to find via Homebrew
        assert mock_subprocess.call_count == 2


class TestBinaryPathSearch:
    """Test cases for binary path search functionality."""

    @patch("shutil.which")
    def test_check_system_path_found(self, mock_which):
        """Test system PATH check when binary is found."""
        mock_logger = Mock()
        strategy = LinuxDNGLabStrategy(mock_logger)
        mock_which_return = "/usr/local/bin/dnglab"
        mock_which.return_value = mock_which_return

        result = strategy._check_system_path("dnglab")

        assert result == mock_which_return
        mock_logger.info.assert_called_with(f"Found DNGLab in system PATH: {mock_which_return}")

    @patch("shutil.which")
    def test_check_system_path_not_found(self, mock_which):
        """Test system PATH check when binary is not found."""
        mock_logger = Mock()
        strategy = LinuxDNGLabStrategy(mock_logger)
        mock_which.return_value = None

        result = strategy._check_system_path("dnglab")

        assert result is None
        mock_logger.info.assert_called_with("DNGLab not found in system PATH")
