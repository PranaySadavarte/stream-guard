"""Experimental overlapping finite decoders, independent of sentence endpoints.

Each recognizer owns a window. Only its prefix is committed, leaving the overlap
as right context. Results are genuine FinalResult outputs, not stable partials.
ASR accuracy at window edges still needs real-voice validation.
"""
import json
from pathlib import Path
import numpy as np
from .base import Detection,Word
from .vocabulary import validate_vocabulary

# Generic conversational context keeps the keyword grammar from forcing every
# ordinary word into either a blocked term or a single unknown token.
CONTEXT_WORDS=frozenset('''a about after all also am an and any are as at back be because been before being
but by can come could day did do does down even first for from get give go good got had has have he her
here him his how i if in into is it its just know like look make me more most my new no not now of on
one only or other our out over people say see she so some take than that the their them then there these
they think this time to too two up us use very want was way we well were what when which who will with
would you your'''.split())


class BoundedVoskDetector:
    def __init__(self,model_path,window_ms=1500,hop_ms=500,terms=None):
        if not 500<=window_ms<=2500 or not 100<=hop_ms<=window_ms/2:
            raise ValueError('window must be 500–2500 ms; hop must be 100 ms to half the window')
        if window_ms%hop_ms:raise ValueError('window must be an exact multiple of hop')
        self.model_path=str(model_path);self.window_ms=window_ms;self.hop_ms=hop_ms
        self.terms=tuple(sorted(set(terms))) if terms is not None else None
        if self.terms is not None and not self.terms:raise ValueError('provide at least one keyword')
        self.model=None;self.active=[];self.processed=self.finalized=0

    def start(self,rate):
        from vosk import Model,KaldiRecognizer,SetLogLevel
        if not Path(self.model_path).is_dir():raise ValueError('select an extracted Vosk model directory')
        SetLogLevel(-1);self.model=Model(self.model_path);self.recognizer_type=KaldiRecognizer
        self.rate=rate;self.window=round(rate*self.window_ms/1000);self.hop=round(rate*self.hop_ms/1000)
        if self.terms is not None:
            if hasattr(self.model,'vosk_model_find_word'):
                validate_vocabulary(self.model,self.terms)
            context=[word for word in CONTEXT_WORDS if not hasattr(self.model,'vosk_model_find_word') or self.model.vosk_model_find_word(word)>=0]
            self.grammar=json.dumps(sorted(set(self.terms)|set(context))+['[unk]'])
        self.active=[];self.processed=self.finalized=0;self.next_start=0

    def _new(self,start):
        recognizer=(self.recognizer_type(self.model,self.rate,self.grammar) if self.terms is not None else
                    self.recognizer_type(self.model,self.rate))
        recognizer.SetWords(True)
        return {'start':start,'recognizer':recognizer,'words':[]}

    def _words(self,payload,start):
        return [Word(row['word'],start/self.rate+float(row['start']),
                     start/self.rate+float(row['end']),float(row.get('conf',1)))
                for row in json.loads(payload).get('result',[])]

    def process_audio(self,audio):
        if self.model is None:raise RuntimeError('detector is not started')
        pcm=np.rint(np.clip(np.asarray(audio).reshape(-1),-1,32767/32768)*32768).astype('<i2')
        offset=0;words=[]
        while offset<len(pcm):
            if self.processed==self.next_start:
                self.active.append(self._new(self.next_start));self.next_start+=self.hop
            boundary=min(self.next_start,min(w['start']+self.window for w in self.active))
            count=min(len(pcm)-offset,boundary-self.processed)
            chunk=pcm[offset:offset+count].tobytes()
            for w in self.active:
                if w['recognizer'].AcceptWaveform(chunk):
                    w['words'].extend(self._words(w['recognizer'].Result(),w['start']))
            self.processed+=count;offset+=count
            for w in list(self.active):
                if self.processed==w['start']+self.window:
                    w['words'].extend(self._words(w['recognizer'].FinalResult(),w['start']))
                    # The next window begins at this committed prefix boundary.
                    # All newly emitted timestamps are >= the previous boundary.
                    words.extend(word for word in w['words'] if word.start*self.rate>=self.finalized-1)
                    self.finalized=w['start']+self.hop
                    self.active.remove(w)
        return Detection(tuple(words),self.finalized)

    def finish(self):
        words=[]
        for w in self.active:
            w['words'].extend(self._words(w['recognizer'].FinalResult(),w['start']))
            words.extend(word for word in w['words'] if word.start*self.rate>=self.finalized-1)
        self.active=[];self.finalized=self.processed
        return Detection(tuple(words),self.finalized)

    def stop(self):self.active=[];self.model=None
