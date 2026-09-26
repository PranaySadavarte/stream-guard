"""Explicit first-run download from Vosk's official model host; no auto-download."""
import hashlib
from pathlib import Path
import urllib.request
import zipfile

NAME = 'vosk-model-small-en-us-0.15'
URL = f'https://alphacephei.com/vosk/models/{NAME}.zip'


def main():
    root = Path(__file__).resolve().parents[1] / 'models'
    root.mkdir(exist_ok=True)
    if (root / NAME / 'am' / 'final.mdl').is_file():
        print(root / NAME)
        return
    archive = root / f'{NAME}.zip'
    with urllib.request.urlopen(URL, timeout=120) as response, archive.open('wb') as target:
        while chunk := response.read(1024*1024):
            target.write(chunk)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (root / member.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError('unsafe model archive path')
        bundle.extractall(root)
    print('Downloaded from:', URL)
    print('SHA256 (local provenance, not vendor signature):', hashlib.sha256(archive.read_bytes()).hexdigest())
    print('Model:', root / NAME)


if __name__ == '__main__': main()
