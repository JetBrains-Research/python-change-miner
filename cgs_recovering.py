import argparse
import os
import pickle
import uuid

import settings
from log import logger
from pyflowgraph.models import Node
from vcs.traverse import GitAnalyzer

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--src',
                        help='Path to current cgs storage dir, default from settings',
                        type=str, default=settings.get('change_graphs_storage_dir'))
    parser.add_argument('-d', '--dest',
                        help='Path to final cgs storage dir after recovering, equals to `src` by default',
                        type=str, required=True)
    args = parser.parse_args()

    # Load old cgs
    file_names = os.listdir(args.src)
    change_graphs = []
    for file_num, file_name in enumerate(file_names):
        file_path = os.path.join(args.src, file_name)
        try:
            with open(file_path, 'rb') as f:
                graphs = pickle.load(f)
            for graph in graphs:
                change_graphs.append(pickle.loads(graph))
        except:
            logger.error(f'Incorrect file {file_path}')
            continue

    # Remove old cgs
    if not os.path.exists(args.dest):
        os.makedirs(args.dest)

    # Restore cgs with recovered SYNTAX_TOKEN_INTERVALS
    batch = []
    for cg in change_graphs:
        batch.append(cg)

        for node in cg.nodes:
            if node.label == 'for' or node.label == 'while':
                node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                  [[node.ast.first_token.startpos, node.ast.first_token.endpos]])

        if len(batch) >= GitAnalyzer.STORE_INTERVAL:
            pickled_batch = []
            for graph in batch:
                try:
                    pickled = pickle.dumps(graph, protocol=5)
                    pickled_batch.append(pickled)
                except:
                    logger.error(f'Unable to pickle graph, '
                                 f'file_path={graph.repo_info.old_method.file_path}, '
                                 f'method={graph.repo_info.old_method.full_name}', exc_info=True)
            filename = uuid.uuid4().hex
            logger.info(f'Trying to store graphs to {filename}', show_pid=True)
            with open(os.path.join(args.dest, f'{filename}.pickle'), 'w+b') as f:
                pickle.dump(pickled_batch, f)
            logger.info(f'Storing graphs to {filename} finished', show_pid=True)

            batch.clear()
