$ErrorActionPreference = 'Stop'

$packageName = 'eir'
$toolsDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"
$version = '0.1.10'
$url64 = "https://github.com/alexbigkid/eir/releases/download/v$version/eir-$version-windows-x86_64.exe"

# Download the executable using Get-ChocolateyWebFile with correct parameters
$downloadPath = Join-Path $toolsDir "eir-$version-windows-x86_64.exe"
Get-ChocolateyWebFile -PackageName $packageName -FileFullPath $downloadPath -Url64bit $url64 -Checksum64 'REPLACE_WITH_ACTUAL_CHECKSUM' -ChecksumType64 'sha256'

# Rename the downloaded file to eir.exe
$targetPath = Join-Path $toolsDir "eir.exe"
if (Test-Path $downloadPath) {
    Move-Item $downloadPath $targetPath -Force
}

# Create a shim for the executable
Install-BinFile -Name 'eir' -Path $targetPath