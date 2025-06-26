# Download DNGLab binary for Windows DNG conversion
param(
    [string]$Platform = "windows"
)

$ErrorActionPreference = "Stop"

function Get-LatestDNGLabVersion {
    Write-Host "Detecting latest DNGLab version..." -ForegroundColor Cyan
    
    try {
        $headers = @{}
        $headers["User-Agent"] = "eir-build-script"
        
        if ($env:GITHUB_TOKEN) {
            Write-Host "Using authenticated API request..." -ForegroundColor Cyan
            $headers["Authorization"] = "Bearer $($env:GITHUB_TOKEN)"
        } else {
            Write-Host "Using unauthenticated API request..." -ForegroundColor Cyan
        }
        
        $response = Invoke-RestMethod -Uri "https://api.github.com/repos/dnglab/dnglab/releases/latest" -Headers $headers -TimeoutSec 30
        $version = $response.tag_name
        Write-Host "Latest DNGLab version: $version" -ForegroundColor Green
        return $version
    }
    catch {
        Write-Host "Failed to detect latest DNGLab version. Error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Falling back to v0.7.0" -ForegroundColor Red
        return "v0.7.0"
    }
}

function Get-DNGLabBinaryInfo {
    $arch = $env:PROCESSOR_ARCHITECTURE
    Write-Host "Detecting architecture: $arch" -ForegroundColor Cyan
    
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
            Write-Host "Unsupported architecture: $arch" -ForegroundColor Red
            throw "Unsupported architecture: $arch"
        }
    }
}

function Download-AndSetupDNGLab {
    param(
        [string]$Version,
        [hashtable]$BinaryInfo,
        [string]$Platform
    )
    
    $binaryName = $BinaryInfo.Binary
    $extension = $BinaryInfo.Extension
    $archName = $BinaryInfo.Arch
    
    $url = "https://github.com/dnglab/dnglab/releases/download/$Version/$binaryName" + "_$Version" + "$extension"
    $buildPath = ".\build\$Platform\tools\$archName"
    $zipPath = "$buildPath\dnglab.zip"
    $exePath = "$buildPath\dnglab.exe"
    
    Write-Host "Downloading DNGLab $Version for $archName..." -ForegroundColor Cyan
    Write-Host "URL: $url" -ForegroundColor Yellow
    
    # Create build directory structure
    if (!(Test-Path $buildPath)) {
        New-Item -ItemType Directory -Path $buildPath -Force | Out-Null
    }
    
    # Download DNGLab ZIP file
    try {
        Invoke-WebRequest -Uri $url -OutFile $zipPath
        Write-Host "Download completed" -ForegroundColor Green
    }
    catch {
        Write-Host "Download failed: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
    
    # Extract the ZIP file
    try {
        Write-Host "Extracting DNGLab binary..." -ForegroundColor Cyan
        Expand-Archive -Path $zipPath -DestinationPath $buildPath -Force
        
        # Find the extracted dnglab.exe file
        $extractedExe = Get-ChildItem -Path $buildPath -Name "dnglab.exe" -Recurse | Select-Object -First 1
        if ($extractedExe) {
            $sourcePath = "$buildPath\$extractedExe"
            if ($sourcePath -ne $exePath) {
                Move-Item -Path $sourcePath -Destination $exePath -Force
            }
        }
        else {
            throw "dnglab.exe not found in extracted ZIP"
        }
        
        # Clean up ZIP file
        Remove-Item -Path $zipPath -Force
        Write-Host "Extraction completed" -ForegroundColor Green
    }
    catch {
        Write-Host "Extraction failed: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
}

function Test-DNGLabBinary {
    param(
        [string]$Platform,
        [string]$Arch
    )
    
    $exePath = ".\build\$Platform\tools\$Arch\dnglab.exe"
    
    # Verify download
    if (Test-Path $exePath) {
        $fileSize = (Get-Item $exePath).Length
        Write-Host "DNGLab downloaded successfully" -ForegroundColor Green
        Write-Host "Path: $exePath" -ForegroundColor Yellow
        Write-Host "Size: $fileSize bytes" -ForegroundColor Yellow
        
        # Test the binary
        Write-Host "Testing DNGLab binary..." -ForegroundColor Cyan
        try {
            $output = & $exePath --help 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "DNGLab binary is working correctly" -ForegroundColor Green
            }
            else {
                Write-Host "DNGLab binary test failed - may still work for conversion" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "DNGLab binary test failed - may still work for conversion" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "Download failed - DNGLab binary not found" -ForegroundColor Red
        throw "DNGLab binary not found at path: $exePath"
    }
}

# Main execution
Write-Host ""
Write-Host "Start: $PSCommandPath" -ForegroundColor Magenta

try {
    $version = Get-LatestDNGLabVersion
    $binaryInfo = Get-DNGLabBinaryInfo
    Download-AndSetupDNGLab -Version $version -BinaryInfo $binaryInfo -Platform $Platform
    Test-DNGLabBinary -Platform $Platform -Arch $binaryInfo.Arch
    
    Write-Host "DNGLab setup complete!" -ForegroundColor Green
    Write-Host "Exit: $PSCommandPath (0)" -ForegroundColor Magenta
    exit 0
}
catch {
    Write-Host "DNGLab setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Exit: $PSCommandPath (1)" -ForegroundColor Magenta
    exit 1
}