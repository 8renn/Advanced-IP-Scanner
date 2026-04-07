# build_msstore.ps1
# Builds the Microsoft Store version of Advanced Network Tool
# - Sets DIST_CHANNEL to "msstore" (skips GitHub update check, skips Install/Run screen)
# - Builds with PyInstaller
# - Restores DIST_CHANNEL to "github" when done
#
# Usage: .\build_msstore.ps1

$ErrorActionPreference = "Stop"
$versionFile = "core\version.py"

Write-Host "=== Building Microsoft Store version ===" -ForegroundColor Cyan

# Step 1: Backup version.py
Copy-Item $versionFile "$versionFile.bak" -Force
Write-Host "[1/4] Backed up version.py"

# Step 2: Set DIST_CHANNEL to msstore
(Get-Content $versionFile) -replace 'DIST_CHANNEL = "github"', 'DIST_CHANNEL = "msstore"' | Set-Content $versionFile
Write-Host "[2/4] Set DIST_CHANNEL = msstore"

# Step 3: Build with PyInstaller
try {
    Write-Host "[3/4] Building with PyInstaller..."
    python -m PyInstaller ANT.spec --clean
} finally {
    # Step 4: Restore version.py (always, even if build fails)
    Copy-Item "$versionFile.bak" $versionFile -Force
    Remove-Item "$versionFile.bak" -Force
    Write-Host "[4/4] Restored DIST_CHANNEL = github"
}

Write-Host ""
Write-Host "=== Microsoft Store build complete ===" -ForegroundColor Green
Write-Host "Output: dist\AdvancedNetworkTool\"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Copy dist\AdvancedNetworkTool\* to your MSIX staging folder"
Write-Host "  2. Update version in AppxManifest.xml to 1.1.0.0"
Write-Host "  3. Run makeappx.exe to create the MSIX"
Write-Host "  4. Submit to Partner Center"
