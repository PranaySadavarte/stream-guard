# Build a portable Windows folder. Model is separate and selected on first launch.
param([string]$Python = 'python')
$ErrorActionPreference='Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    & $Python -m PyInstaller --noconfirm --windowed --name StreamGuard --paths src --collect-binaries vosk --collect-data vosk --collect-all _sounddevice_data --exclude-module pandas --exclude-module scipy --exclude-module matplotlib --exclude-module openpyxl --exclude-module IPython tools\desktop_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    # Qt on supported Windows 10/11 uses the OS ICU ABI. A Python environment's
    # renamed ICU exports can be collected accidentally and shadow System32.
    # Do not redistribute that incompatible runtime DLL with this application.
    $packageRuntime = Join-Path (Get-Location) 'dist\StreamGuard\_internal'
    foreach ($dllName in @('icuuc.dll','icudt78.dll')) {
        $candidate = Join-Path $packageRuntime $dllName
        if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate -Force }
    }
    Copy-Item -LiteralPath README.md -Destination dist\StreamGuard\README.md
    Copy-Item -LiteralPath docs -Destination dist\StreamGuard\docs -Recurse -Force
    Write-Output (Join-Path (Get-Location) 'dist\StreamGuard\StreamGuard.exe')
} finally { Pop-Location }
