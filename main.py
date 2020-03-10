import ast
import shutil
import os
import pickle
import logging
import sys
import stackimpact
import datetime

from patterns import Miner
from patterns.models import Fragment, Pattern
from vcs.traverse import GitAnalyzer, RepoInfo, Method

import pyflowgraph
import changegraph
import settings


class RunModes:
    TEST_PYFLOWGRAPH_BUILDER = 1
    TEST_CHANGEGRAPH_BUILDER = 2
    TEST_PATTERNS_MINING = 3
    TEST_PATTERNS_OUTPUT = 6

    COLLECT_CHANGE_GRAPHS = 4
    MINE_PATTERNS = 5


def main():
    if settings.get('use_stackimpact'):
        _ = stackimpact.start(
            agent_key=settings.get('stackimpact_agent_key'),
            app_name='CodeChangesMiner',
            debug=True,
            app_version=str(datetime.datetime.now())
        )

    sys.setrecursionlimit(10000)
    if os.path.exists('images'):
        shutil.rmtree('images')

    current_mode = RunModes.COLLECT_CHANGE_GRAPHS  # TODO: make cli?

    if current_mode == RunModes.TEST_PYFLOWGRAPH_BUILDER:
        args = {
            'input': 'examples/1_old.py',
            'output': 'pyflowgraph',
            'build_closure': False,
            'show_dependencies': False
        }

        fg = pyflowgraph.build_from_file(
            args['input'], show_dependencies=args['show_dependencies'], build_closure=args['build_closure'])
        pyflowgraph.export_graph_image(fg, args['output'])
    elif current_mode == RunModes.TEST_CHANGEGRAPH_BUILDER:
        args = {
            'input1': 'examples/1_old.py',
            'input2': 'examples/1_new.py',
            'output': 'changegraph'
        }

        fg = changegraph.build_from_files(args['input1'], args['input2'])
        changegraph.export_graph_image(fg, f'images/{args["output"]}')
    elif current_mode == RunModes.TEST_PATTERNS_MINING:
        args = {
            'input': [
                ('examples/1_old.py', 'examples/1_new.py'),
                ('examples/2_old.py', 'examples/2_new.py')
            ],
            'output': 'pyflowgraph',
        }

        graphs = []
        for old_path, new_path in args['input']:
            cg = changegraph.build_from_files(old_path, new_path)
            graphs.append(cg)
            changegraph.export_graph_image(cg, f'images/cg-{len(graphs)}')

        patterns_miner = Miner()
        raise NotImplementedError
        # size_to_patterns = patterns_miner.mine_patterns(graphs)
        #
        # _export_pattern_images(size_to_patterns)
    elif current_mode == RunModes.COLLECT_CHANGE_GRAPHS:
        GitAnalyzer().build_change_graphs()
    elif current_mode == RunModes.MINE_PATTERNS:
        change_graphs = []
        for filename in os.listdir('storage'):
            file_path = os.path.join('storage', filename)
            try:
                with open(file_path, 'rb') as f:
                    change_graphs += pickle.load(f)
            except:
                logging.warning(f'ops {file_path}')

        logging.warning('Pattern mining has started')

        miner = Miner()
        miner.mine_patterns(change_graphs)
        miner.print_result()
    elif current_mode == RunModes.TEST_PATTERNS_OUTPUT:
        args = {
            'input1': 'examples/1_old.py',
            'input2': 'examples/1_new.py',
            'output': 'changegraph'
        }

        with open(args['input1'], 'r+') as f:
            src = f.read()
            old_method = Method('test_name', ast.parse(src, mode='exec').body[0], src)

        with open(args['input2'], 'r+') as f:
            src = f.read()
            new_method = Method('test_name', ast.parse(src, mode='exec').body[0], src)

        repo_info = RepoInfo('mock name', 'mock path', 'mock hash', old_method, new_method)

        cg = changegraph.build_from_files(args['input1'], args['input2'], repo_info=repo_info)
        fragment = Fragment()
        fragment.graph = cg
        fragment.nodes = cg.nodes
        pattern = Pattern([fragment])

        miner = Miner()
        miner.add_pattern(pattern)
        miner.print_result()


if __name__ == '__main__':
    main()
