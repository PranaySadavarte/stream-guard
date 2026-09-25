import numpy as np
import pytest
from streamguard.audio.censor import CensorSettings, CensorSpan, censor_into, word_span
from streamguard.detection.base import Word
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.offline import write_wav, read_wav, censor_file


@pytest.mark.parametrize('word', ['FUCK!', 'fucking', "fuckin'", 'shitty', 'Bitch.'])
def test_normalization(word):
    assert ProfanityDictionary().matches(word)


@pytest.mark.parametrize('word', ['class', 'shitake', 'Scunthorpe', 'hello'])
def test_no_substring_false_positives(word):
    assert not ProfanityDictionary().matches(word)


def test_custom_words_and_padding():
    assert ProfanityDictionary(['Sponsor']).matches('SPONSOR!')
    assert word_span(Word('shit', .3, .6), 1000, CensorSettings()).start == 150
    assert word_span(Word('shit', .3, .6), 1000, CensorSettings()).end == 750


@pytest.mark.parametrize('mode', ['beep', 'silence'])
def test_replacement_independent_of_original_and_chunk_boundaries(mode):
    rate = 16000
    settings = CensorSettings(mode=mode)
    spans = [CensorSpan(300, 1300), CensorSpan(900, 1600), CensorSpan(2100, 2600)]
    source = np.random.default_rng(1).uniform(-.8, .8, (4000, 2)).astype(np.float32)
    full = source.copy()
    censor_into(full, 0, spans, rate, settings)
    chunked = source.copy()
    for offset in range(0, 4000, 320):
        censor_into(chunked[offset:offset+320], offset, spans, rate, settings)
    np.testing.assert_array_equal(full, chunked)
    other = -source.copy()
    censor_into(other, 0, spans, rate, settings)
    np.testing.assert_array_equal(full[300:1600], other[300:1600])
    np.testing.assert_array_equal(full[:200], source[:200])
    assert np.max(np.abs(full[300:1600])) <= settings.volume
    if mode == 'beep':
        assert np.max(np.abs(full[400:1200])) > .19
    else:
        assert not np.any(full[300:1600])


def test_offline_wav_integration(tmp_path):
    rate = 16000
    source = np.full((rate * 2, 1), .42, dtype=np.float32)
    input_file, output_file = tmp_path/'input.wav', tmp_path/'censored.wav'
    write_wav(input_file, source, rate)
    spans = censor_file(input_file, output_file, words=[Word('hello', .1, .2),
        Word('fucking', .5, .8), Word('shit', 1.1, 1.3)])
    actual, actual_rate = read_wav(output_file)
    assert len(spans) == 2 and actual_rate == rate
    expected = source.copy()
    censor_into(expected, 0, spans, rate, CensorSettings())
    np.testing.assert_allclose(actual, expected, atol=1/32768)


def test_invalid_censor_configuration():
    for kw in ({'mode':'mix'}, {'volume':2}, {'frequency':float('nan')}, {'before_ms':-1}):
        with pytest.raises(ValueError): CensorSettings(**kw)
