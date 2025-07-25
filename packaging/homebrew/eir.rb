class Eir < Formula
  desc "EXIF-based image renamer and RAW format converter"
  homepage "https://github.com/alexbigkid/eir"
  version "REPLACE_WITH_VERSION"
  url "https://github.com/alexbigkid/eir/releases/download/v#{version}/eir-#{version}-macos-universal"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"

  depends_on "exiftool"

  def install
    bin.install "eir-#{version}-macos-universal" => "eir"
  end

  def caveats
    <<~EOS
      This formula requires Adobe DNG Converter for RAW to DNG conversion on macOS.
      Install it with:
        brew install --cask adobe-dng-converter
    EOS
  end

  test do
    system "#{bin}/eir", "--version"
  end
end
