"""Validate live keywords without opening an audio device."""


class UnsupportedWordsError(ValueError):
    def __init__(self, words):
        self.words = tuple(sorted(words))
        super().__init__('English live recognition does not support: ' + ', '.join(self.words)
                         + '. Edit these words or remove them below. Nothing was silently ignored.')


def validate_vocabulary(model, terms):
    missing = [word for word in terms if model.vosk_model_find_word(word) < 0]
    if missing:
        raise UnsupportedWordsError(missing)


def check_live_words(model_path, terms):
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    model = Model(str(model_path))
    validate_vocabulary(model, terms)
