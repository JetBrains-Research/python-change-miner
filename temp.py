import json
import os
import pickle
import tempfile

from tqdm import tqdm

import changegraph
import settings
from log import logger
from vcs.traverse import GitAnalyzer


def extract_relevant_commits(path_to_patterns: str):
    hashes, repos = set(), set()
    for root, dirs, files in os.walk(path_to_patterns):
        for file in files:
            if file.startswith('sample-details') and file.endswith('.json'):
                with open(os.path.join(root, file), 'r') as json_file:
                    details = json.load(json_file)
                    hashes.add(details['commit']['hash'])
                    repos.add(details['repo']['url'])
    for hash in hashes:
        print(hash)
    return repos, hashes


def run_extraction():
    repos, hashes = extract_relevant_commits('/home/oleg/prog/data/plugin/output_final_best/')
    res = {
        'repos': list(repos),
        'hashes': list(hashes)
    }
    with open('11_patterns_details.json', 'w') as json_file:
        json.dump(res, json_file)


def main():
    storage_dir = settings.get('change_graphs_storage_dir')
    GitAnalyzer.STORAGE_DIR = storage_dir + '_new'
    file_names = os.listdir(storage_dir)
    change_graphs = []
    for file_num, file_name in enumerate(file_names):
        file_path = os.path.join(storage_dir, file_name)
        with open(file_path, 'rb') as f:
            graphs = pickle.load(f)
        for graph in graphs:
            change_graphs.append(pickle.loads(graph))

    new_cgs = []
    for cg in tqdm(change_graphs):
        old_method_src = cg.repo_info.old_method.get_source()
        new_method_src = cg.repo_info.new_method.get_source()

        with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t1, \
                tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t2:
            t1.writelines(old_method_src)
            t1.seek(0)
            t2.writelines(new_method_src)
            t2.seek(0)

            try:
                new_cg = changegraph.build_from_files(
                    os.path.realpath(t1.name), os.path.realpath(t2.name), repo_info=cg.repo_info)
                new_cgs.append(new_cg)
            except Exception as e:
                logger.error(e)

            if len(new_cgs) >= 5:
                GitAnalyzer._store_change_graphs(new_cgs)
                new_cgs.clear()

    if len(new_cgs) >= 5:
        GitAnalyzer._store_change_graphs(new_cgs)
        new_cgs.clear()


if __name__ == '__main__':
    main()
