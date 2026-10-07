# Build a portable Windows folder. Model is separate and selected on first launch.
param([string]$Python = 'python', [string]$DistPath = 'release')
$ErrorActionPreference='Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    & $Python -m PyInstaller --clean --noconfirm --windowed --name StreamGuard --distpath $DistPath --paths src --collect-binaries vosk --collect-data vosk --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers --collect-all av --collect-all _sounddevice_data --exclude-module torch --exclude-module transformers --exclude-module pandas --exclude-module scipy --exclude-module matplotlib --exclude-module openpyxl --exclude-module IPython tools\desktop_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    # Qt on supported Windows 10/11 uses the OS ICU ABI. A Python environment's
    # renamed ICU exports can be collected accidentally and shadow System32.
    # Do not redistribute that incompatible runtime DLL with this application.
    $packageDirectory = Join-Path $DistPath 'StreamGuard'
    $packageRuntime = Join-Path $packageDirectory '_internal'
    foreach ($dllName in @('icuuc.dll','icudt78.dll')) {
        $candidate = Join-Path $packageRuntime $dllName
        if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate -Force }
    }
    Copy-Item -LiteralPath README.md -Destination (Join-Path $packageDirectory 'README.md')
    $packageDocs = Join-Path $packageDirectory 'docs'
    New-Item -ItemType Directory -Path $packageDocs -Force | Out-Null
    Get-ChildItem -LiteralPath docs | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $packageDocs -Recurse -Force
    }
    Write-Output (Join-Path $packageDirectory 'StreamGuard.exe')
} finally { Pop-Location }
