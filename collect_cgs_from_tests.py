import argparse
import multiprocessing
import os
import pickle
import sys
import tempfile
import uuid
from pathlib import Path
from typing import List

import changegraph
import settings
from changegraph.models import ChangeGraph
from deployment import set_all_environment_variables
from log import logger
from vcs.traverse import GitAnalyzer, RepoInfo

STORAGE_DIR = settings.get('change_graphs_storage_dir')


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


def main(src_dir: str):
    change_graphs = []

    try:

        for dirname, _, files in os.walk(src_dir):
            before_path, after_path = None, None
            for filename in files:
                if filename.endswith('.before.py'):
                    before_path = os.path.join(dirname, filename)
                elif filename.endswith('.after.py'):
                    after_path = os.path.join(dirname, filename)

            if before_path and after_path:
                with open(before_path, 'r') as before_file, open(after_path, 'r') as after_file:
                    before_src = before_file.read()
                    after_src = after_file.read()

                old_method_to_new = GitAnalyzer._get_methods_mapping(
                    GitAnalyzer._extract_methods(before_path, before_src),
                    GitAnalyzer._extract_methods(after_path, after_src)
                )

                for old_method, new_method in old_method_to_new.items():
                    old_method_src = old_method.get_source()
                    new_method_src = new_method.get_source()

                    if not all([old_method_src, new_method_src]) or old_method_src.strip() == new_method_src.strip():
                        continue

                    line_count = max(old_method_src.count('\n'), new_method_src.count('\n'))
                    if line_count > settings.get('traverse_file_max_line_count'):
                        logger.info(f'Ignored files due to line limit: {before_path}')
                        continue

                    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t1, \
                            tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t2:

                        t1.writelines(old_method_src)
                        t1.seek(0)
                        t2.writelines(new_method_src)
                        t2.seek(0)

                        repo_info = RepoInfo(
                            Path(dirname).parent.name,
                            dirname,
                            '',
                            '',
                            '',
                            before_path,
                            after_path,
                            old_method,
                            new_method
                        )

                        try:
                            cg = changegraph.build_from_files(os.path.realpath(t1.name), os.path.realpath(t2.name),
                                                              repo_info=repo_info)
                        except:
                            logger.log(logger.ERROR,
                                       f'Unable to build a change graph for '
                                       f'method={old_method.full_name}, '
                                       f'line={old_method.ast.lineno}', exc_info=True, show_pid=True)
                            continue

                        change_graphs.append(cg)

                        if len(change_graphs) >= GitAnalyzer.STORE_INTERVAL:
                            store_change_graphs(change_graphs)
                            change_graphs.clear()

    except KeyboardInterrupt:
        logger.info('KeyboardInterrupt: change-graphs will be stored before exit')

    if change_graphs:
        GitAnalyzer._store_change_graphs(change_graphs)
        change_graphs.clear()


if __name__ == '__main__':
    set_all_environment_variables()
    sys.setrecursionlimit(2 ** 31 - 1)
    multiprocessing.set_start_method('spawn', force=True)

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--src', help='Path to directory with before and after versions', type=str, required=True)
    args = parser.parse_args()

    main(args.src)
