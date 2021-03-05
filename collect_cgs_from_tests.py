import argparse
import json
import multiprocessing
import os
import pickle
import sys
import tempfile
import uuid
from pathlib import Path
from typing import List

from tqdm import tqdm

import changegraph
import settings
from changegraph.models import ChangeGraph
from deployment import set_all_environment_variables
from log import logger
from vcs.traverse import GitAnalyzer, RepoInfo

STORAGE_DIR = settings.get('change_graphs_storage_dir')

finished_files = {}


def init(finished):
    global finished_files
    finished_files = finished


def store_change_graphs(change_graphs: List[ChangeGraph]):
    pickled_graphs = []
    for graph in change_graphs:
        try:
            pickled = pickle.dumps(graph, protocol=5)
            pickled_graphs.append(pickled)
        except RecursionError:
            logger.error(f'Unable to pickle graph {graph}')
    filename = uuid.uuid4().hex
    logger.info(f'Trying to store graphs to {filename}', show_pid=True)
    with open(os.path.join(STORAGE_DIR, f'{filename}.pickle'), 'w+b') as f:
        pickle.dump(pickled_graphs, f)
    logger.info(f'Storing graphs to {filename} finished', show_pid=True)


def mine_changes(path_to_repo_dir: str):
    change_graphs = []
    for dirname, _, files in os.walk(path_to_repo_dir):
        try:
            old_file_path, new_file_path = None, None
            for filename in files:
                if filename.endswith('.before.py'):
                    old_file_path = os.path.join(dirname, filename)
                elif filename.endswith('.after.py'):
                    new_file_path = os.path.join(dirname, filename)

            if not old_file_path or not new_file_path:
                continue

            if old_file_path in finished_files:
                continue

            with open(old_file_path, 'r') as before_file, open(new_file_path, 'r') as after_file:
                before_src = before_file.read()
                after_src = after_file.read()

            old_method_to_new = GitAnalyzer._get_methods_mapping(
                GitAnalyzer._extract_methods(old_file_path, before_src),
                GitAnalyzer._extract_methods(new_file_path, after_src)
            )

            for old_method, new_method in old_method_to_new.items():
                old_method_src = old_method.get_source()
                new_method_src = new_method.get_source()

                if not all([old_method_src, new_method_src]) or old_method_src.strip() == new_method_src.strip():
                    continue

                line_count = max(old_method_src.count('\n'), new_method_src.count('\n'))
                if line_count > settings.get('traverse_file_max_line_count'):
                    logger.info(f'Ignored files due to line limit: {old_file_path}')
                    continue

                with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t1, \
                        tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t2:

                    t1.writelines(old_method_src)
                    t1.seek(0)
                    t2.writelines(new_method_src)
                    t2.seek(0)

                    local_repo_path = Path(old_file_path).parent.parent
                    repo_info = RepoInfo(
                        repo_name=local_repo_path.name,
                        repo_path=local_repo_path,
                        repo_url='',
                        commit_hash='',
                        commit_dtm='',
                        old_file_path=old_file_path,
                        new_file_path=new_file_path,
                        old_method=old_method,
                        new_method=new_method
                    )

                    try:
                        cg = changegraph.build_from_files(os.path.realpath(t1.name),
                                                          os.path.realpath(t2.name),
                                                          repo_info)
                    except Exception:
                        logger.log(logger.ERROR,
                                   f'Unable to build a change graph for '
                                   f'method={old_method.full_name}, '
                                   f'line={old_method.ast.lineno}', exc_info=True, show_pid=True)
                        continue

                    change_graphs.append(cg)

                    if len(change_graphs) > GitAnalyzer.STORE_INTERVAL:
                        store_change_graphs(change_graphs)
                        change_graphs.clear()

            finished_files[old_file_path] = True

        except Exception:
            continue

    if change_graphs:
        store_change_graphs(change_graphs)


def main(src_dir: str, parallel: bool = False):
    # Load (or create empty) already finished files collection
    global finished_files
    path_to_finished = Path(src_dir) / 'finished.json'
    if path_to_finished.exists():
        try:
            with open(path_to_finished, 'r') as file:
                finished_files = json.load(file)
        except Exception:
            finished_files = {}
    else:
        finished_files = {}

    # Traverse all the subdirectories to find before-after pairs
    paths = []
    for repo_name in os.listdir(src_dir):
        paths.append(os.path.join(src_dir, repo_name))

    # Build and save change graphs
    try:
        if parallel:
            manager = multiprocessing.Manager()
            finished_files = manager.dict(finished_files)
            with multiprocessing.Pool(initializer=init, initargs=(finished_files,)) as pool:
                list(tqdm(pool.imap(mine_changes, paths), total=len(paths)))
        else:
            for path in tqdm(paths):
                mine_changes(path)
    except BaseException:
        with open(path_to_finished, 'w') as file:
            json.dump(finished_files.copy(), file)


if __name__ == '__main__':
    set_all_environment_variables()
    sys.setrecursionlimit(2 ** 31 - 1)
    multiprocessing.set_start_method('spawn', force=True)

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--src', help='Path to directory with before and after versions', type=str, required=True)
    parser.add_argument('--parallel', help='Run in parallel', action='store_true')
    args = parser.parse_args()

    main(args.src, args.parallel)
