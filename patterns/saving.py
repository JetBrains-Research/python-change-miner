import os
import pickle
import shutil

import settings
from log import logger
from patterns import Miner

DUMP_DIR = settings.get('patterns_dump_dir')
OUTPUT_DIR = settings.get('patterns_output_dir')


def print_patterns_from_dump():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    size_to_patterns = {}
    for size in os.listdir(DUMP_DIR):
        same_size_path = os.path.join(DUMP_DIR, size)
        for pattern_file_pickle in os.listdir(same_size_path):
            with open(os.path.join(same_size_path, pattern_file_pickle), 'rb') as f:
                pattern = pickle.load(f)
            size_to_patterns.setdefault(size, []).append(pattern)

    for size, patterns in sorted(size_to_patterns.items()):
        if not patterns:
            continue

        logger.log(logger.WARNING, f'Exporting patterns of size {size}')

        same_size_dir = os.path.join(OUTPUT_DIR, str(size))
        os.makedirs(same_size_dir, exist_ok=True)

        for pattern in patterns:
            Miner._print_pattern(same_size_dir, pattern)

        Miner._generate_contents(
            same_size_dir,
            f'Size {size} contents',
            [{'name': f'Pattern #{p.id}', 'url': f'{p.id}/details.html'}
             for p in sorted(patterns, key=lambda p: p.id)],
            styles='../../styles.css', has_upper_contents=True)

    Miner._generate_contents(
        OUTPUT_DIR,
        'Contents',
        [{'name': f'Size {size}', 'url': f'{size}/contents.html'}
         for size in sorted(size_to_patterns.keys())])

    logger.warning('Done patterns output')
