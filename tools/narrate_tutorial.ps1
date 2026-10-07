# Synthesize narration to local WAV files, never to speakers.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$tutorialRoot = Join-Path $PSScriptRoot '..\artifacts\tutorial'
$scenes = Get-Content -LiteralPath (Join-Path $tutorialRoot 'scenes.json') -Raw | ConvertFrom-Json
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
try {
    $voice = $speaker.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -like '*Zira*' } | Select-Object -First 1
    if ($voice) { $speaker.SelectVoice($voice.VoiceInfo.Name) }
    $speaker.Rate = 1
    for ($index=0; $index -lt $scenes.Count; $index++) {
        $speaker.SetOutputToWaveFile((Join-Path $tutorialRoot "voice-$index.wav"), $format)
        $speaker.Speak($scenes[$index].narration)
        $speaker.SetOutputToNull()
    }
} finally { $speaker.Dispose() }
Write-Output 'Tutorial narration saved.'
