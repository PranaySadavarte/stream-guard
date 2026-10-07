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


def migrate_live_test_settings(root, legacy):
    """Unify the temporary live-test launcher with the regular app, once."""
    root,legacy=Path(root),Path(legacy)
    destination=root/'settings.json'
    current=load_settings(destination)
    if current.get('settings_version')==2:return
    if legacy.exists() and (not destination.exists() or legacy.stat().st_mtime>destination.stat().st_mtime):
        candidate=load_settings(legacy)
        if destination.exists():
            backup=root/'settings-before-unification.json'
            if not backup.exists():backup.write_bytes(destination.read_bytes())
        current=candidate
    current['settings_version']=2
    save_settings(destination,current)
