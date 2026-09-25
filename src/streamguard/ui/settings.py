import json
import os
from pathlib import Path


def data_directory():
    root = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'StreamGuard'
    root.mkdir(parents=True, exist_ok=True)
    return root


def load_settings(path):
    if not Path(path).exists(): return {}
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError('settings must be an object')
    return data


def save_settings(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.tmp')
    pending.write_text(json.dumps(data, indent=2), encoding='utf-8')
    pending.replace(path)
