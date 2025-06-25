# Download DNGLab binary for Windows DNG conversion
param(
    [string]$Platform = "windows"
)

$ErrorActionPreference = "Stop"

# Function to auto-detect latest DNGLab version from GitHub API
function Get-LatestDNGLabVersion {
    Write-Host "🔍 Detecting latest DNGLab version..." -ForegroundColor Cyan
    
    try {
        $response = Invoke-RestMethod -Uri "https://api.github.com/repos/dnglab/dnglab/releases/latest"
        $version = $response.tag_name
        Write-Host "✅ Latest DNGLab version: $version" -ForegroundColor Green
        return $version
    }
    catch {
        Write-Host "❌ Failed to detect latest DNGLab version. Falling back to v0.7.0" -ForegroundColor Red
        return "v0.7.0"
    }
}

# Function to detect architecture and map to DNGLab release naming
function Get-DNGLabBinaryInfo {
    $arch = $env:PROCESSOR_ARCHITECTURE
    Write-Host "🔍 Detecting architecture: $arch" -ForegroundColor Cyan
    
    switch ($arch) {
        "AMD64" {
            return @{
                Arch = "x64"
                Binary = "dnglab-win-x64"
                Extension = ".zip"
            }
        }
        "ARM64" {
            return @{
                Arch = "arm64"
                Binary = "dnglab-win-arm64"
                Extension = ".zip"
            }
        }
        default {
            Write-Host "❌ Unsupported architecture: $arch" -ForegroundColor Red
            throw "Unsupported architecture: $arch"
        }
    }
}

# Function to download and setup DNGLab binary
function Download-AndSetupDNGLab {
    param(
        [string]$Version,
        [hashtable]$BinaryInfo,
        [string]$Platform
    )
    
    $url = "https://github.com/dnglab/dnglab/releases/download/$Version/$($BinaryInfo.Binary)_$Version$($BinaryInfo.Extension)"
    $buildPath = "./build/$Platform/tools/$($BinaryInfo.Arch)"
    $zipPath = "$buildPath/dnglab.zip"
    $exePath = "$buildPath/dnglab.exe"
    
    Write-Host "📥 Downloading DNGLab $Version for $($BinaryInfo.Arch)..." -ForegroundColor Cyan
    Write-Host "🔗 URL: $url" -ForegroundColor Yellow
    
    # Create build directory structure if it doesn't exist
    if (-not (Test-Path $buildPath)) {
        New-Item -ItemType Directory -Path $buildPath -Force | Out-Null
    }
    
    # Download DNGLab ZIP file
    try {
        Invoke-WebRequest -Uri $url -OutFile $zipPath
        Write-Host "✅ Download completed" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Download failed: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
    
    # Extract the ZIP file
    try {
        Write-Host "📦 Extracting DNGLab binary..." -ForegroundColor Cyan
        Expand-Archive -Path $zipPath -DestinationPath $buildPath -Force
        
        # Find the extracted dnglab.exe file
        $extractedExe = Get-ChildItem -Path $buildPath -Name "dnglab.exe" -Recurse | Select-Object -First 1
        if ($extractedExe) {
            $sourcePath = Join-Path $buildPath $extractedExe
            if ($sourcePath -ne $exePath) {
                Move-Item -Path $sourcePath -Destination $exePath -Force
            }
        }
        else {
            throw "dnglab.exe not found in extracted ZIP"
        }
        
        # Clean up ZIP file
        Remove-Item -Path $zipPath -Force
        Write-Host "✅ Extraction completed" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Extraction failed: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
}

# Function to verify and test DNGLab binary
function Test-DNGLabBinary {
    param(
        [string]$Platform,
        [string]$Arch
    )
    
    $exePath = "./build/$Platform/tools/$Arch/dnglab.exe"
    
    # Verify download
    if (Test-Path $exePath) {
        $fileSize = (Get-Item $exePath).Length
        Write-Host "✅ DNGLab downloaded successfully" -ForegroundColor Green
        Write-Host "📁 Path: $exePath" -ForegroundColor Yellow
        Write-Host "📊 Size: $fileSize bytes" -ForegroundColor Yellow
        
        # Test the binary
        Write-Host "🧪 Testing DNGLab binary..." -ForegroundColor Cyan
        try {
            $output = & $exePath --help 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ DNGLab binary is working correctly" -ForegroundColor Green
            }
            else {
                Write-Host "⚠️  DNGLab binary test failed - may still work for conversion" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "⚠️  DNGLab binary test failed - may still work for conversion" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "❌ Download failed - DNGLab binary not found" -ForegroundColor Red
        throw "DNGLab binary not found: $exePath"
    }
}

# =============================================================================
# Main execution
# =============================================================================
Write-Host ""
Write-Host "Start: $PSCommandPath ($args)" -ForegroundColor Magenta

try {
    $version = Get-LatestDNGLabVersion
    $binaryInfo = Get-DNGLabBinaryInfo
    Download-AndSetupDNGLab -Version $version -BinaryInfo $binaryInfo -Platform $Platform
    Test-DNGLabBinary -Platform $Platform -Arch $binaryInfo.Arch
    
    Write-Host "🎉 DNGLab setup complete!" -ForegroundColor Green
    Write-Host "Exit: $PSCommandPath (0)" -ForegroundColor Magenta
    exit 0
}
catch {
    Write-Host "❌ DNGLab setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Exit: $PSCommandPath (1)" -ForegroundColor Magenta
    exit 1
}