# Setup Chocolatey Test Environment (Optional - for local development)
param(
    [string]$TestEnvironmentPath = "C:\ChocolateyTestEnvironment",
    [string]$PackageVersion,
    [switch]$SetupOnly = $false
)

$ErrorActionPreference = "Stop"

Write-Host "🔧 Setting up Chocolatey Test Environment" -ForegroundColor Yellow

# Check prerequisites
$Prerequisites = @(
    @{ Name = "git"; Command = "git --version" },
    @{ Name = "Vagrant"; Command = "vagrant --version" },
    @{ Name = "VirtualBox"; Command = "VBoxManage --version" }
)

Write-Host "🔍 Checking prerequisites..." -ForegroundColor Cyan
foreach ($prereq in $Prerequisites) {
    try {
        $null = Invoke-Expression $prereq.Command
        Write-Host "✅ $($prereq.Name) is available" -ForegroundColor Green
    } catch {
        Write-Host "❌ $($prereq.Name) is not available or not in PATH" -ForegroundColor Red
        Write-Host "Please install $($prereq.Name) before continuing" -ForegroundColor Yellow
        exit 1
    }
}

# Clone or update the test environment
if (-not (Test-Path $TestEnvironmentPath)) {
    Write-Host "📥 Cloning Chocolatey Test Environment..." -ForegroundColor Blue
    git clone https://github.com/chocolatey-community/chocolatey-test-environment.git $TestEnvironmentPath
} else {
    Write-Host "🔄 Updating existing test environment..." -ForegroundColor Blue
    Push-Location $TestEnvironmentPath
    try {
        git pull origin master
    } finally {
        Pop-Location
    }
}

if ($SetupOnly) {
    Write-Host "✅ Test environment setup complete at: $TestEnvironmentPath" -ForegroundColor Green
    Write-Host "📋 Next steps:" -ForegroundColor Cyan
    Write-Host "  1. cd $TestEnvironmentPath" -ForegroundColor Gray
    Write-Host "  2. vagrant up" -ForegroundColor Gray
    Write-Host "  3. vagrant snapshot save good" -ForegroundColor Gray
    Write-Host "  4. Copy your .nupkg to the packages folder" -ForegroundColor Gray
    Write-Host "  5. vagrant provision" -ForegroundColor Gray
    exit 0
}

# If PackageVersion provided, run the test
if ($PackageVersion) {
    Write-Host "🧪 Running package test for version $PackageVersion..." -ForegroundColor Yellow
    
    Push-Location $TestEnvironmentPath
    try {
        # Find the package file
        $PackageFile = Get-ChildItem -Path "..\packages-windows-*" -Name "eir.$PackageVersion.nupkg" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        
        if (-not $PackageFile) {
            Write-Host "❌ Could not find package file for version $PackageVersion" -ForegroundColor Red
            exit 1
        }
        
        # Copy package to test environment
        $PackagesDir = "packages"
        if (-not (Test-Path $PackagesDir)) {
            New-Item -ItemType Directory -Path $PackagesDir -Force
        }
        
        Copy-Item $PackageFile.FullName -Destination $PackagesDir -Force
        Write-Host "📦 Copied package to test environment" -ForegroundColor Green
        
        # Run the test
        Write-Host "🚀 Starting Vagrant test environment..." -ForegroundColor Blue
        Write-Host "This may take several minutes on first run..." -ForegroundColor Yellow
        
        # Check if VM is already running
        $VagrantStatus = vagrant status 2>&1
        if ($VagrantStatus -match "running") {
            Write-Host "🔄 VM is already running, running provision..." -ForegroundColor Blue
            vagrant provision
        } else {
            Write-Host "🔄 Starting VM and provisioning..." -ForegroundColor Blue
            vagrant up
        }
        
        # Check the results
        Write-Host "📋 Test completed. Check the VM for results." -ForegroundColor Cyan
        Write-Host "💡 Use 'vagrant snapshot restore good' to reset the environment" -ForegroundColor Yellow
        
    } finally {
        Pop-Location
    }
} else {
    Write-Host "⚠️ No package version specified, setup complete" -ForegroundColor Yellow
    Write-Host "Use -PackageVersion parameter to run tests" -ForegroundColor Gray
}

Write-Host "✅ Chocolatey test environment ready!" -ForegroundColor Green