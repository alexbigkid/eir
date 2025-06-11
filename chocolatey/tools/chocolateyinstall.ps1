$ErrorActionPreference = 'Stop'

$packageName = 'eir'
$toolsDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"
$version = '0.1.10'
$url64 = "https://github.com/alexbigkid/eir/releases/download/v$version/eir-$version-windows-amd64.exe"

$packageArgs = @{
    packageName    = $packageName
    unzipLocation  = $toolsDir
    fileType       = 'exe'
    url64bit       = $url64
    softwareName   = 'eir*'
    checksum64     = 'REPLACE_WITH_ACTUAL_CHECKSUM'
    checksumType64 = 'sha256'
    silentArgs     = '/S'
    validExitCodes = @(0)
}

# Download and place the executable
Get-ChocolateyWebFile @packageArgs

# Rename the downloaded file to eir.exe
$exePath = Join-Path $toolsDir "eir-$version-windows-amd64.exe"
$targetPath = Join-Path $toolsDir "eir.exe"

if (Test-Path $exePath) {
    Move-Item $exePath $targetPath -Force
}

# Create a shim for the executable
Install-BinFile -Name 'eir' -Path $targetPath