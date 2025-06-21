$ErrorActionPreference = 'Stop'

$packageName = 'eir'
$toolsDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"
$version = '0.1.10'
$url64 = "https://github.com/alexbigkid/eir/releases/download/v$version/eir-$version-windows-x86_64.exe"

# Download the executable using proper Chocolatey function
$packageArgs = @{
    packageName   = $packageName
    fileType      = 'exe'
    url64bit      = $url64
    checksum64    = 'REPLACE_WITH_ACTUAL_CHECKSUM'
    checksumType64= 'sha256'
    
    # For portable executables, don't use silentArgs
    # Just download to tools directory
    unzipLocation = $toolsDir
}

# Download the file
$downloadedFile = Get-ChocolateyWebFile -PackageName $packageArgs.packageName -FileFullPath (Join-Path $toolsDir "eir.exe") -Url64bit $packageArgs.url64bit -Checksum64 $packageArgs.checksum64 -ChecksumType64 $packageArgs.checksumType64

# Create a shim for the executable so it's available in PATH
# Chocolatey will automatically create a shim for any .exe in the tools directory
Write-Host "eir.exe has been installed to $toolsDir and is now available in your PATH"