# Generate local Windows TTS test speech. No recorded human voice or dataset.
param([string]$OutputDirectory = "$PSScriptRoot\..\recordings\fixtures")
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$destination = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$phrases = @{
    clean = 'Hello this is a normal sentence.'
    profanity = 'That was fucking unbelievable.'
    repeated = 'What the shit was that. That was fucking insane.'
}
try {
    foreach ($name in $phrases.Keys) {
        $speaker.SetOutputToWaveFile((Join-Path $destination "$name.wav"), $format)
        $speaker.Speak($phrases[$name])
        $speaker.SetOutputToNull()
    }
} finally { $speaker.Dispose() }
Write-Output $destination
