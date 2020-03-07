import copy
import json
import os
from pathlib import Path


def _load():
    p = os.path.join(Path(__file__).parent.absolute(), 'conf', 'settings.json')
    with open(p, 'r+') as f:
        loaded = json.load(f)
    return loaded


def get(option, default=None):
    result = _settings.get(option)
    return copy.copy(result) if result else default


_settings = _load()
