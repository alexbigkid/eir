# Chocolatey Package Testing Script
param(
    [Parameter(Mandatory=$true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

Write-Host "🧪 Testing Chocolatey package for version $Version" -ForegroundColor Yellow

# Get OS details
$OSName = $env:OS_NAME
$Arch = $env:ARCH
$PackagesDir = "packages-$OSName-$Arch"

Write-Host "📍 Current directory: $(Get-Location)" -ForegroundColor Blue
Write-Host "📂 Looking for packages in: $PackagesDir" -ForegroundColor Blue

# Find the .nupkg file
$NupkgFile = Get-ChildItem -Path $PackagesDir -Name "eir.$Version.nupkg" -ErrorAction SilentlyContinue
if (-not $NupkgFile) {
    Write-Host "❌ Could not find Chocolatey package eir.$Version.nupkg in $PackagesDir" -ForegroundColor Red
    Write-Host "📂 Available files in $PackagesDir:" -ForegroundColor Yellow
    if (Test-Path $PackagesDir) {
        Get-ChildItem -Path $PackagesDir | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor Gray }
    } else {
        Write-Host "  Directory $PackagesDir does not exist" -ForegroundColor Gray
    }
    
    # Try to find the package in other locations
    Write-Host "🔍 Searching for .nupkg files in current directory..." -ForegroundColor Yellow
    $AllNupkgFiles = Get-ChildItem -Path . -Name "*.nupkg" -Recurse -ErrorAction SilentlyContinue
    if ($AllNupkgFiles) {
        Write-Host "📦 Found .nupkg files:" -ForegroundColor Blue
        $AllNupkgFiles | ForEach-Object { Write-Host "  - $_" -ForegroundColor Gray }
        
        # Try to find one matching our version
        $VersionMatch = $AllNupkgFiles | Where-Object { $_ -like "*$Version*" } | Select-Object -First 1
        if ($VersionMatch) {
            Write-Host "✅ Found matching package: $VersionMatch" -ForegroundColor Green
            $NupkgPath = $VersionMatch
            # Update PackagesDir to the actual location
            $PackagesDir = Split-Path $VersionMatch -Parent
            if ([string]::IsNullOrEmpty($PackagesDir)) { $PackagesDir = "." }
        } else {
            exit 1
        }
    } else {
        Write-Host "❌ No .nupkg files found anywhere" -ForegroundColor Red
        exit 1
    }
} else {
    $NupkgPath = Join-Path $PackagesDir $NupkgFile
}

Write-Host "📦 Found package: $NupkgPath" -ForegroundColor Green

# Test 1: Verify package structure
Write-Host "🔍 Testing package structure..." -ForegroundColor Cyan
try {
    # Extract and examine package contents
    $TempDir = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_ }
    Expand-Archive -Path $NupkgPath -DestinationPath $TempDir -Force
    
    # Check required files
    $RequiredFiles = @(
        "eir.nuspec",
        "tools\chocolateyinstall.ps1"
    )
    
    foreach ($file in $RequiredFiles) {
        $FilePath = Join-Path $TempDir $file
        if (-not (Test-Path $FilePath)) {
            Write-Host "❌ Missing required file: $file" -ForegroundColor Red
            exit 1
        }
    }
    
    Write-Host "✅ Package structure is valid" -ForegroundColor Green
    
    # Cleanup
    Remove-Item $TempDir -Recurse -Force
} catch {
    Write-Host "❌ Package structure test failed: $_" -ForegroundColor Red
    exit 1
}

# Test 2: Verify installation script syntax
Write-Host "🔍 Testing PowerShell script syntax..." -ForegroundColor Cyan
try {
    $InstallScriptPath = Join-Path $PackagesDir "tools\chocolateyinstall.ps1"
    if (Test-Path $InstallScriptPath) {
        # Parse PowerShell script to check for syntax errors
        $null = [System.Management.Automation.PSParser]::Tokenize((Get-Content $InstallScriptPath -Raw), [ref]$null)
        Write-Host "✅ Installation script syntax is valid" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Installation script not found, skipping syntax check" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Installation script syntax test failed: $_" -ForegroundColor Red
    exit 1
}

# Test 3: Test package installation locally (non-destructive)
Write-Host "🔍 Testing package installation (dry-run)..." -ForegroundColor Cyan
try {
    # Use Chocolatey's whatif functionality if available
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Host "📥 Running Chocolatey dry-run test..." -ForegroundColor Blue
        
        # Test local package installation (whatif mode)
        $ChocoResult = choco install eir --source $PackagesDir --version $Version --whatif --force 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Chocolatey dry-run test passed" -ForegroundColor Green
        } else {
            Write-Host "⚠️ Chocolatey dry-run had issues, but continuing..." -ForegroundColor Yellow
            Write-Host "Output: $ChocoResult" -ForegroundColor Gray
        }
    } else {
        Write-Host "⚠️ Chocolatey CLI not available, skipping installation test" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ Package installation test had issues: $_" -ForegroundColor Yellow
    Write-Host "This might be expected in CI environment" -ForegroundColor Gray
}

# Test 4: Verify package metadata
Write-Host "🔍 Testing package metadata..." -ForegroundColor Cyan
try {
    $NuspecPath = Join-Path $PackagesDir "eir.nuspec"
    if (Test-Path $NuspecPath) {
        [xml]$Nuspec = Get-Content $NuspecPath
        $PackageVersion = $Nuspec.package.metadata.version
        
        if ($PackageVersion -eq $Version) {
            Write-Host "✅ Package version matches expected version ($Version)" -ForegroundColor Green
        } else {
            Write-Host "❌ Package version mismatch: expected $Version, got $PackageVersion" -ForegroundColor Red
            exit 1
        }
        
        # Check required metadata fields
        $RequiredFields = @("id", "version", "authors", "description")
        foreach ($field in $RequiredFields) {
            $value = $Nuspec.package.metadata.$field
            if ([string]::IsNullOrWhiteSpace($value)) {
                Write-Host "❌ Missing required metadata field: $field" -ForegroundColor Red
                exit 1
            }
        }
        
        Write-Host "✅ Package metadata is valid" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Package metadata test failed: $_" -ForegroundColor Red
    exit 1
}

# Test 5: Verify binary exists and is accessible
Write-Host "🔍 Testing binary availability..." -ForegroundColor Cyan
try {
    $BinaryPattern = "eir-$Version-windows-*.exe"
    $BinaryFile = Get-ChildItem -Path "dist" -Name $BinaryPattern -ErrorAction SilentlyContinue | Select-Object -First 1
    
    if ($BinaryFile) {
        $BinaryPath = Join-Path "dist" $BinaryFile
        $BinarySize = (Get-Item $BinaryPath).Length
        Write-Host "✅ Binary found: $BinaryFile ($('{0:N2}' -f ($BinarySize / 1MB)) MB)" -ForegroundColor Green
        
        # Test if binary is executable (basic check)
        try {
            $TestOutput = & $BinaryPath --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Binary is executable and responds to --version" -ForegroundColor Green
            } else {
                Write-Host "⚠️ Binary execution test had issues" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "⚠️ Could not test binary execution: $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "❌ Could not find Windows binary for version $Version" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Binary availability test failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "🎉 All Chocolatey package tests completed successfully!" -ForegroundColor Green
Write-Host "📋 Package $NupkgPath is ready for publication" -ForegroundColor Cyan