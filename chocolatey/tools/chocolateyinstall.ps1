$ErrorActionPreference = 'Stop'

$packageName = 'eir'
$toolsDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"
$version = '0.1.10'
$url64 = "https://github.com/alexbigkid/eir/releases/download/v$version/eir-$version-windows-x86_64.exe"

# For portable applications, use Install-ChocolateyZipPackage or Get-ChocolateyWebFile
# According to Chocolatey docs, this is the correct approach for standalone executables
$packageArgs = @{
    packageName    = $packageName
    fileFullPath   = Join-Path $toolsDir "eir.exe"
    url64bit       = $url64
    checksum64     = 'REPLACE_WITH_ACTUAL_CHECKSUM'
    checksumType64 = 'sha256'
}

# Download the executable directly to the tools directory
Get-ChocolateyWebFile @packageArgs

Write-Host "eir has been installed and is available in your PATH" -ForegroundColor Green