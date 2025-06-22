$ErrorActionPreference = 'Stop'

$packageName = 'eir'
$toolsDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"

# Remove the shim
Uninstall-BinFile -Name 'eir'

# Clean up the executable
$exePath = Join-Path $toolsDir "eir.exe"
if (Test-Path $exePath) {
    Remove-Item $exePath -Force
}