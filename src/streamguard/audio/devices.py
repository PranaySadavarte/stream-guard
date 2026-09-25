"""Device selection and OBS route readiness; does not change system defaults."""
import sounddevice as sd


def devices():
    apis = sd.query_hostapis()
    return [{'id':i, 'name':d['name'], 'host':apis[d['hostapi']]['name'],
             'input_channels':d['max_input_channels'], 'output_channels':d['max_output_channels'],
             'sample_rate':d['default_samplerate']} for i,d in enumerate(sd.query_devices())]


def routing_report():
    found = devices()
    playback = [d for d in found if d['output_channels'] and 'cable input' in d['name'].casefold()]
    capture = [d for d in found if d['input_channels'] and 'cable output' in d['name'].casefold()]
    return {'virtual_playback':playback, 'obs_capture':capture,
            'ready':bool(playback and capture),
            'instructions':'StreamGuard → CABLE Input; OBS Audio Input Capture → CABLE Output. Disable raw mic sources.'}
