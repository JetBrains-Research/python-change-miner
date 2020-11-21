import os
import json
import shutil

import settings
from patterns import Miner

_BASE_URL = settings.get('research_patterns_site_base_url')
_IN_DIR = settings.get('research_patterns_in_dir')
_OUT_DIR = settings.get('research_patterns_out_dir')
_DATA_FILE_PATH = os.path.join(_OUT_DIR, 'email-data.json')


def _set_default_if_needed(data, k, v):
    d = data.setdefault(k, v)
    data[k] = d


def _get_sample_info(sample_dir, sample_id):
    with open(os.path.join(sample_dir, f'sample-details-{sample_id}.json'), 'r+') as f:
        sample_info = json.loads(f.read())
    return sample_info


def _load_email_data():
    with open(_DATA_FILE_PATH, 'a+') as f:
        f.seek(0)
        data = f.read()

    try:
        email_data = json.loads(data)
    except:
        email_data = {}

    return email_data


def _save_email_data(email_data):
    with open(_DATA_FILE_PATH, 'w+') as f:
        json.dump(email_data, f, indent=4)


def _clone_dir(old_dir, new_dir):
    os.makedirs(new_dir, exist_ok=True)
    for file_name in os.listdir(old_dir):
        old_file_path = os.path.join(old_dir, file_name)
        if file_name.startswith('.') or file_name.endswith('.json') or not os.path.isfile(old_file_path):
            continue

        new_file_path = os.path.join(new_dir, file_name)
        shutil.copy(old_file_path, new_file_path)


def _is_new_authored_sample(sample_info, email_data):
    author_email = sample_info.get('author', {}).get('email')
    if not author_email:
        print('invalid author for this sample')
        return False

    if author_email in email_data['email_to_author_data']:
        print(f'author {author_email} was already added, data={email_data["email_to_author_data"][author_email]}')
        return False

    return True


def manual_collect():
    email_data = _load_email_data()
    _set_default_if_needed(email_data, 'email_to_author_data', {})

    while True:
        print('enter size')
        size = input()

        try:
            int(size)
        except:
            print('invalid size')
            continue

        print('enter sample ids (separated by commas)')
        sample_ids = input().split(',')

        for sample_id in sample_ids:
            sample_id = sample_id.strip()
            print(f'processing sample {sample_id}')
            if '-' not in sample_id:
                print('incorrect sample id')
                continue

            pattern_id, sample_id = sample_id.split('-')

            old_dir = os.path.join(_IN_DIR, size, pattern_id)
            new_dir = os.path.join(_OUT_DIR, size, pattern_id)

            if email_data['pattern_id_to_info'].get(pattern_id):
                print(f'pattern {pattern_id} was already added')
                continue

            sample_info = _get_sample_info(old_dir, sample_id)
            author_email = sample_info.get('author', {}).get('email')
            if not _is_new_authored_sample(sample_info, email_data):
                # continue
                if author_email:
                    print('replace?')
                    ans = input()

                    if ans != 'y':
                        print('skipping')
                        continue
                    data = email_data['email_to_author_data'][author_email]
                    shutil.rmtree(os.path.join(_OUT_DIR, data['pattern']['size'], data['pattern']['id']))

            if not os.path.isdir(new_dir):
                _clone_dir(old_dir, new_dir)
            else:
                print(f'WARNING: DIR EXISTS FOR {pattern_id} {sample_id} {author_email}')

            url = f'{_BASE_URL}/{size}/{pattern_id}/sample-{sample_id}.html'
            email_data['email_to_author_data'][author_email] = {
                'author': sample_info['author'],
                'url': url,
                'pattern': {
                    'id': pattern_id,
                    'size': size,
                    'sample_id': sample_id
                }
            }

            _save_email_data(email_data)
            print(f'saved: author {author_email}, url={url}, {pattern_id}-{sample_id}')


def generate_contents(out_dir):
    email_data = _load_email_data()
    size_to_pattern_ids = {}

    for email, author_data in email_data['email_to_author_data'].items():
        pattern = author_data['pattern']
        size = int(pattern['size'])

        _set_default_if_needed(size_to_pattern_ids, size, set())
        size_to_pattern_ids[size].add(int(pattern['id']))

    for size, pattern_ids in size_to_pattern_ids.items():
        same_size_dir = os.path.join(out_dir, str(size))

        Miner._generate_contents(
            same_size_dir,
            f'Size {size} contents',
            [{'name': f'Pattern #{pid}', 'url': f'{pid}/details.html'} for pid in sorted(pattern_ids)],
            styles='../../styles.css', has_upper_contents=True)

    Miner._generate_contents(
        out_dir,
        'Contents',
        [{'name': f'Size {size}', 'url': f'{size}/contents.html'}
         for size in sorted(size_to_pattern_ids.keys())])


if __name__ == '__main__':
    manual_collect()
    # generate_contents(out_dir=_OUT_DIR)
