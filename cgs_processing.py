import os
import pickle

import settings
from log import logger
from pyflowgraph.models import Node
from vcs.traverse import GitAnalyzer

if __name__ == '__main__':
    storage_dir = settings.get('change_graphs_storage_dir')
    file_names = os.listdir(storage_dir)

    # Load old cgs
    change_graphs = []
    for file_num, file_name in enumerate(file_names):
        file_path = os.path.join(storage_dir, file_name)
        try:
            with open(file_path, 'rb') as f:
                graphs = pickle.load(f)
            for graph in graphs:
                change_graphs.append(pickle.loads(graph))
        except:
            logger.warning(f'Incorrect file {file_path}')
            continue

    # Remove old cgs
    for root, _, files in os.walk(storage_dir):
        for f in files:
            os.unlink(os.path.join(root, f))

    # Restore cgs with recovered SYNTAX_TOKEN_INTERVALS
    batch = []
    for cg in change_graphs:
        batch.append(cg)
        for node in cg.nodes:
            if node.label == 'for' or node.label == 'while':
                node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                  [[node.ast.first_token.startpos, node.ast.first_token.endpos]])
        if len(batch) >= GitAnalyzer.STORE_INTERVAL:
            GitAnalyzer._store_change_graphs(batch)
            batch.clear()
