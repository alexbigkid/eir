# Binary testing script for Windows PowerShell
param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$ArchBinExt
)

# Enable strict error handling
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrEmpty($Version) -or [string]::IsNullOrEmpty($ArchBinExt)) {
    Write-Host "❌ Error: VERSION and ARCH_BIN_EXT required" -ForegroundColor Red
    Write-Host "Usage: .\test_binary.ps1 <version> <arch_bin_ext>"
    Write-Host "Example: .\test_binary.ps1 0.1.19 windows-x86_64.exe"
    exit 1
}

$BinaryName = "eir-$Version-$ArchBinExt"
$BinaryPath = ".\dist\$BinaryName"

Write-Host "🧪 Testing binary: $BinaryName" -ForegroundColor Yellow

# Check if binary exists
if (!(Test-Path $BinaryPath)) {
    Write-Host "❌ Error: Binary not found: $BinaryPath" -ForegroundColor Red
    Write-Host "Available files in dist/:"
    if (Test-Path ".\dist\") {
        Get-ChildItem ".\dist\" | Format-Table -AutoSize
    } else {
        Write-Host "  (dist directory not found)"
    }
    exit 1
}

Write-Host "✅ Binary found: $BinaryName" -ForegroundColor Green

# Test version command
Write-Host "🧪 Testing --version command..." -ForegroundColor Yellow
try {
    $VersionOutput = & $BinaryPath --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Version test passed" -ForegroundColor Green
        Write-Host "📄 Version output:" -ForegroundColor Cyan
        # Handle multi-line output properly
        if ($VersionOutput -is [array]) {
            $VersionOutput | ForEach-Object { Write-Host $_ }
        } else {
            Write-Host $VersionOutput
        }
    } else {
        Write-Host "❌ Version test failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Version test failed with exception: $_" -ForegroundColor Red
    exit 1
}

# Test help command
Write-Host "🧪 Testing --help command..." -ForegroundColor Yellow
try {
    $HelpOutput = & $BinaryPath --help 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Help test passed" -ForegroundColor Green
        Write-Host "📄 Help output:" -ForegroundColor Cyan
        # Handle multi-line output properly
        if ($HelpOutput -is [array]) {
            $HelpOutput | ForEach-Object { Write-Host $_ }
        } else {
            Write-Host $HelpOutput
        }
    } else {
        Write-Host "❌ Help test failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Help test failed with exception: $_" -ForegroundColor Red
    exit 1
}

# Test about command
Write-Host "🧪 Testing --about command..." -ForegroundColor Yellow
try {
    $AboutOutput = & $BinaryPath --about 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ About test passed" -ForegroundColor Green
        Write-Host "📄 About output:" -ForegroundColor Cyan
        # Handle multi-line output properly
        if ($AboutOutput -is [array]) {
            $AboutOutput | ForEach-Object { Write-Host $_ }
        } else {
            Write-Host $AboutOutput
        }
    } else {
        Write-Host "❌ About test failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ About test failed with exception: $_" -ForegroundColor Red
    exit 1
}

# Get binary size for reporting
$BinarySize = (Get-Item $BinaryPath).Length
$BinarySizeMB = [math]::Round($BinarySize / 1MB, 2)
Write-Host "📊 Binary size: $BinarySizeMB MB" -ForegroundColor Cyan

Write-Host "🎉 All tests passed for $BinaryName!" -ForegroundColor Green