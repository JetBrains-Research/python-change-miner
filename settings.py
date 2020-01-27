import copy
import json
import os


def _load():
    p = os.path.join(os.getcwd(), 'conf', 'settings.json')
    with open(p, 'r+') as f:
        loaded = json.load(f)
    return loaded


def get(option):
    result = _settings.get(option)
    return copy.copy(result)


_settings = _load()
