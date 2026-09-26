import re
import unicodedata

DEFAULT_TERMS = ('fuck', 'fucking', 'fucked', 'fucker', 'fuckers', 'fucks',
                 'shit', 'shitty', 'shitting', 'bullshit', 'bitch', 'bitches',
                 'asshole', 'assholes', 'motherfucker', 'motherfuckers')


def normalize(text):
    return re.sub(r"[^\w]+", '', unicodedata.normalize('NFKC', text).casefold())


class ProfanityDictionary:
    def __init__(self, terms=DEFAULT_TERMS):
        self.terms = frozenset(normalize(x) for x in terms if x.strip())
        if not self.terms or '' in self.terms:
            raise ValueError('provide at least one word containing letters or digits')
        if any(len(x.split()) != 1 for x in terms if x.strip()):
            raise ValueError('use one word per line; phrases are not supported yet')

    def matches(self, word):
        value = normalize(word)
        # A common ASR spelling of the -ing suffix; do not substring-match.
        return value in self.terms or (value.endswith('in') and value + 'g' in self.terms)
