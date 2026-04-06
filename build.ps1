# Build script for MultiTool application using PyInstaller
# This script packages the application into a standalone executable

Write-Host "Building MultiTool application..." -ForegroundColor Green
Write-Host ""

# Run PyInstaller with the package structure
$pyinstallerArgs = @(
    "--onefile",
    "--windowed",
    "--noconsole",
    "--clean",
    "--icon=Assets/icon.ico",
    "--add-data", "Assets/icon.ico;.",
    "--hidden-import=multitool",
    "--hidden-import=multitool.widgets",
    "--hidden-import=multitool.helpers",
    "MultiTool.py"
)

& pyinstaller $pyinstallerArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Build complete!" -ForegroundColor Green
    Write-Host "The executable is located in: dist/MultiTool.exe" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Build failed with exit code: $LASTEXITCODE" -ForegroundColor Red
}

Write-Host ""
Read-Host "Press Enter to exit"
